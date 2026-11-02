#!/usr/bin/env python3
"""回归：合成语料必须 Gate 1/2 全过；用负例守护视觉判断的确定性部分。

    python3 tests/run.py            退出码 1 = 回归失败
    python3 tests/run.py --shots   截取 320/360/390/430px 证据（需 playwright，未装则失败）

合成语料与素材不入库：tests/fixtures.py 每次在临时目录生成；真实来源对照保留在 evaluation/。
三条铁律：用例必须过；护栏必须仍会在该失败的地方失败；测试只冻结可确定缺陷，不冻结审美配额。
"""
import argparse
import contextlib
import io
from pathlib import Path
import unittest
from unittest.mock import patch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.join(ROOT, "scripts")
sys.path.insert(0, SCRIPTS)
import publish
from safety import local_path
import render as _r
import fixtures as _fx

FIX = None          # main() 生成的临时语料目录；用例、素材与负例都在这里解析
CASES = _fx.CASES
HEAD = "---\ntitle: 回归用例|固定标题\n"   # 固定内容；不写 date，避免每天产生 diff


def run(args, cwd):
    p = subprocess.run([sys.executable] + args, capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def case_ok(name):
    """在语料目录原地渲染：相对图片路径必须像真实使用一样解析。"""
    out = os.path.join(FIX, f"_shots_{name}.html")
    code, log = run([os.path.join(SCRIPTS, "render.py"), f"{name}.md", "-o", out], FIX)
    return code == 0, log


# 负例：(标签, frontmatter 附加行, 正文, 关键词, 级别)
GUARDS = (
    ("封面写了但文件不存在", "cover: images/not-there.jpg\n", "正文一段。\n",
     "封面文件不存在", "must"),
    ("图片分辨率过低", "", "正文一段。\n\n![小图](fixtures/tiny.png \"场景\")\n",
     "分辨率过低", "should"),
    ("bars 值不是数字", "", "::: bars\n多｜甲\n少｜乙\n:::\n", "bars 的值必须是数字", "must"),
    ("bars 只有一项", "", "::: bars\n10｜甲\n:::\n", "bars 至少 2 项", "must"),
    ("bars 缺来源", "", "::: bars 件\n1｜甲\n2｜乙\n:::\n", "缺少紧邻来源", "must"),
    ("bars 缺单位", "", "::: bars\n1｜甲\n2｜乙\n:::\n", "必须声明单一单位", "must"),
    ("证据类图片没有说明", "", "正文一段。\n\n![](images/fig.jpg \"证据\")\n",
     "证据类图必须写清出处", "must"),
    ("density 写错静默降级", "density: campact\n", "正文一段。\n", "density", "must"),

)


def guard_ok(label, fm, body, kw, level):
    meta, blocks = _r.parse(HEAD + fm + "---\n\n" + body)
    must, should = _r.compose_gate(meta, blocks, FIX)
    found = must if level == "must" else should
    return any(kw in m for m in found), "\n".join(must + should)


# 原语渲染断言：(标签, frontmatter 附加行, markdown, 必须出现, 必须不出现)
# 覆盖的是「渲染出来是不是我以为的样子」——只跑 Gate 是看不见这类错的。
RENDER_CHECKS = (
    ("data 的全角/半角分隔符都要拆开", "",
     "::: data\n3｜甲标签\n11|乙标签\n:::\n\n::: note 演示\n假设演示计数，非统计。\n:::\n", ("甲标签", "乙标签"), ("3｜甲标签",)),
    # 线上事故回归：title/author 走平台原生字段（草稿标题栏/作者栏），
    # 正文若再印一遍，草稿里标题、作者各出现两次。正文只允许留 cta/bio。
    ("正文不重印原生标题与作者",
     "author: 甲木\nbio: 观察内容与商业的人\ncta: 欢迎留言聊聊。\n",
     "> 钩子。\n\n正文一段。\n",
     ("欢迎留言聊聊。", "观察内容与商业的人"),
     ("回归用例", "固定标题", "甲木")),
    # 线上反馈回归：正文顶部元信息块（kicker/阅读时长/日期）整块多余，已删；
    # 只保留 deck 副题。
    ("正文无顶部元信息块，只保留 deck",
     "date: 2026年10月8日\ndeck: 一句副题\n",
     "正文一段。\n",
     ("一句副题",),
     ("分钟阅读", "2026年10月8日")),
)


# ---- 人格签名：决定一个主题是「编辑语言」还是「换色」----
# 这些轴都由真实渲染器消费：导语 / 章节 / 小标题 / 引文 / 重点 / 转场 / 图片 / 数据 / 表格 / 列表。
STRUCTURAL_AXES = ("lead", "heading", "h3", "quote", "peak", "divider", "image", "data", "table", "list")
SIGNATURE = STRUCTURAL_AXES + ("display",)
COLOR_KEYS = ("text", "sub", "muted", "line", "field", "accent", "dark", "on_dark")
TYPE_KEYS = ("heading_size", "heading_weight", "heading_leading", "chapter_gap", "paragraph_gap")


def theme_audit():
    """人格键必须完整且结构轴真实分开；不以配色差异代替构图差异。"""
    from itertools import combinations
    bad, sig = [], {}
    if tuple(_r.THEMES) != ("paper", "letter", "ink", "frost", "bone", "folio"):
        bad.append("主题必须固定为 paper / letter / ink / frost / bone / folio，不能增删或换序")
    for key, theme in _r.THEMES.items():
        missing = [k for k in SIGNATURE + COLOR_KEYS
                   + ("name", "intent", "leading", "radius", "seal", "toc_label", "type") if k not in theme]
        missing_type = [k for k in TYPE_KEYS if k not in theme.get("type", {})]
        if missing or missing_type:
            bad.append(f"{key} 缺少键 {missing + ['type.' + x for x in missing_type]}")
        sig[key] = tuple(theme.get(axis) for axis in SIGNATURE)
    # 每个结构轴都应有六个实际实现；否则至少有两人格在该维只剩颜色差。
    for axis in STRUCTURAL_AXES:
        values = [theme.get(axis) for theme in _r.THEMES.values()]
        if len(set(values)) != len(values):
            bad.append(f"结构轴 {axis} 存在重复：{values}")
    for left, right in combinations(sorted(sig), 2):
        differences = [axis for axis, a, b in zip(SIGNATURE, sig[left], sig[right]) if a != b]
        if not differences:
            bad.append(f"{left} 与 {right} 编辑语言参数完全重复")
    return bad


def specimen_ok():
    """themes.json、渲染器和入库展示板必须由同一次生成得到。"""
    with tempfile.TemporaryDirectory() as directory, contextlib.redirect_stdout(io.StringIO()):
        generated = os.path.join(directory, "themes.html")
        _r.specimen(generated)
        actual = Path(generated).read_bytes()
    committed = Path(ROOT, "assets", "themes.html")
    if not committed.is_file():
        return False, "assets/themes.html 不存在"
    expected = committed.read_bytes()
    marker = f"themes sha256 {_r.THEME_CONFIG_SHA256}".encode()
    return actual == expected and marker in expected, (
        "themes.json / render.py / themes.html 一致" if actual == expected and marker in expected
        else "展示板已漂移：运行 python3 scripts/render.py --specimen")


def render_check_ok(fm, md, must_have, must_not):
    _, meta, blocks, html = _r.render(HEAD + fm + "---\n\n" + md)
    log = "\n".join(sum(_r.compose_gate(meta, blocks, FIX), []))
    missing = [x for x in must_have if x not in html]
    leaked = [x for x in must_not if x in html]
    return not missing and not leaked, log, missing, leaked


def platform_fields_ok():
    """所见即所得：正文不印 title/author；预览模拟原生标题栏/作者行；
    meta sidecar 字段符合官方上限（title≤32 / author≤16 / digest≤120），摘要取自 lead。"""
    with tempfile.TemporaryDirectory() as d:
        md = os.path.join(d, "a.md")
        open(md, "w", encoding="utf-8").write(
            HEAD + "author: 幻海低语者   # 行内注释不能混进值里\nbio: 一句话\ndate: 2026年10月8日\n---\n\n"
                  "> 所有人都在问 AI 会不会让自己失业。\n\n正文一段。\n")
        code, log = run([os.path.join(SCRIPTS, "render.py"), md, "-o", os.path.join(d, "o.html")], d)
        if code != 0:
            return False, log
        body = open(os.path.join(d, "o.html"), encoding="utf-8").read()
        prev = open(os.path.join(d, "o_预览.html"), encoding="utf-8").read()
        meta = json.load(open(os.path.join(d, "o.meta.json"), encoding="utf-8"))
    problems = []
    for bad in ("回归用例", "固定标题", "幻海低语者", "2026年10月8日"):
        if bad in body:
            problems.append(f"正文泄漏原生字段：{bad}")
    if "回归用例｜固定标题" not in prev or "幻海低语者" not in prev:
        problems.append("预览没有模拟原生标题栏/作者行")
    if "2026年10月8日" not in prev:
        problems.append("预览原生元信息行没有日期（日期应只在这一行出现）")
    if meta["api_title"] != "回归用例｜固定标题":
        problems.append(f"api_title 未转换断行标记：{meta['api_title']}")
    if meta["author"] != "幻海低语者":
        problems.append(f"frontmatter 行内注释混进值：author={meta['author']!r}")
    if meta["digest"] != "所有人都在问 AI 会不会让自己失业。":
        problems.append(f"digest 未取 lead：{meta['digest']!r}")
    if len(meta["api_title"]) > 32 or len(meta["author"]) > 16 or len(meta["digest"]) > 120:
        problems.append("meta 字段超官方上限")
    return not problems, ("；".join(problems) if problems else "正文无重印 · 预览模拟原生栏 · meta 上限合规")


def draft_payload_ok():
    """publish.py 实际发给 draft/add 的 payload：超限拒绝、断行标记转换、
    留言默认与编辑器对齐（1）、原文链接落到底部字段。"""
    sys.path.insert(0, SCRIPTS)
    import publish as _p
    calls = []

    def fake_post(url, payload, **kwargs):
        calls.append(payload)
        return {"media_id": "MID"}

    old = _p._post_json
    _p._post_json = fake_post
    try:
        _p.create_draft("tok", "回归用例|固定标题", "<section>x</section>", "THUMB",
                        author="作者", digest="摘要", source_url="https://example.com/a")
        try:
            _p.create_draft("tok", "标题" * 20, "正文", "THUMB")
            return False, "超限未拒绝"
        except ValueError:
            pass
        _p.create_draft("tok", "t", "<section>x</section>", "THUMB", need_open_comment=0)
    finally:
        _p._post_json = old
    a = calls[0]["articles"][0]
    b = calls[1]["articles"][0]
    problems = []
    if a["title"] != "回归用例｜固定标题":
        problems.append(f"title 断行标记未转换：{a['title']}")
    if len(a["title"]) > 32 or len(a["author"]) > 16 or len(a["digest"]) > 120:
        problems.append(f"字段超上限：{len(a['title'])}/{len(a['author'])}/{len(a['digest'])}")
    if a["need_open_comment"] != 1:
        problems.append("留言默认不是 1（会与编辑器默认不一致）")
    if a["only_fans_can_comment"] != 0:
        problems.append("only_fans_can_comment 默认不是 0")
    if a.get("content_source_url") != "https://example.com/a":
        problems.append("原文链接没进 content_source_url")
    if b["need_open_comment"] != 0:
        problems.append("显式关闭留言未生效")
    return not problems, ("；".join(problems) if problems else "title｜·上限·留言默认·原文链接 全对")


def material_ok():
    """封面永久素材：首传写缓存、同图复用不重传、后台已删（40007）重传；
    get_materialcount 走 GET；batchget 翻页取全且 count≤20；del_material payload 正确。"""
    sys.path.insert(0, SCRIPTS)
    import publish as _p
    with tempfile.TemporaryDirectory() as d:
        cover = os.path.join(d, "cover.jpg")
        with open(cover, "wb") as f:
            f.write(b"fake-jpeg-bytes" * 8)
        cache = os.path.join(d, "cache.json")
        calls = {"upload": [], "del": [], "batch_counts": []}
        state = {"alive": True}

        def fake_post(url, payload, **kwargs):
            if "/material/batchget_material?" in url:
                calls["batch_counts"].append(payload["count"])
                items = [{"media_id": f"I{i}"} for i in range(25)]
                off = payload["offset"]
                batch = items[off:off + payload["count"]]
                return {"total_count": 25, "item_count": len(batch), "item": batch}
            if "/material/get_material?" in url:
                if not state["alive"]:
                    raise _p.WeChatAPIError(40007, "invalid media_id")
                return {"url": "http://mmbiz.qpic.cn/cached"}
            if "/material/del_material?" in url:
                calls["del"].append(payload)
                return {"errcode": 0, "errmsg": "ok"}
            return {}

        def fake_get(url):
            return {"voice_count": 0, "video_count": 0, "image_count": 2, "news_count": 0}

        def fake_upload(url, path, field_name="media", extra_fields=None):
            calls["upload"].append(os.path.basename(path))
            return {"media_id": f"M{len(calls['upload'])}", "url": "http://mmbiz.qpic.cn/new"}

        old = (_p._post_json, _p._get_json, _p._post_multipart_file)
        _p._post_json, _p._get_json, _p._post_multipart_file = fake_post, fake_get, fake_upload
        try:
            m1 = _p.upload_thumb_material_cached("tok", cover, cache)
            up1 = len(calls["upload"])
            m2 = _p.upload_thumb_material_cached("tok", cover, cache)
            up2 = len(calls["upload"])
            state["alive"] = False
            m3 = _p.upload_thumb_material_cached("tok", cover, cache)
            up3 = len(calls["upload"])
            cnt = _p.get_material_count("tok")
            total, items = _p.list_materials("tok")
            _p.delete_material("tok", "M1")
        finally:
            _p._post_json, _p._get_json, _p._post_multipart_file = old

    problems = []
    if not (m1 == "M1" and up1 == 1):
        problems.append(f"首传应上传并写缓存：{m1}/{up1}")
    if not (m2 == "M1" and up2 == 1):
        problems.append(f"同封面复用不应重传：{m2}/{up2}")
    if not (m3 == "M2" and up3 == 2):
        problems.append(f"素材被删后应重传：{m3}/{up3}")
    if cnt.get("image_count") != 2:
        problems.append("get_materialcount（GET）异常")
    if not (total == 25 and len(items) == 25):
        problems.append(f"batchget 翻页未取全：{total}/{len(items)}")
    if any(c > 20 for c in calls["batch_counts"]):
        problems.append(f"batchget count 超 20：{calls['batch_counts']}")
    if calls["del"] != [{"media_id": "M1"}]:
        problems.append(f"del_material payload 异常：{calls['del']}")
    return not problems, ("；".join(problems) if problems else "复用·验活·删除重传·总数·翻页·删除 全对")


# ---- P3：Word 抽取回归 ----
# extract_docx.py 是三条输入路径之一，此前零覆盖。构造最小 .docx（zipfile + 最小 XML），
# 不引入 python-docx，也不入库二进制。
DOC_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><w:body>
<w:p><w:pPr><w:pStyle w:val="Heading2"/></w:pPr><w:r><w:t>来自 Word 的标题</w:t></w:r></w:p>
<w:p><w:r><w:t>一段普通正文，</w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>加粗的一句</w:t></w:r></w:p>
<w:p><w:pPr><w:numPr><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>编号列表项</w:t></w:r></w:p>
<w:p><w:pPr><w:pStyle w:val="ListParagraph"/></w:pPr><w:r><w:t>样式列表项</w:t></w:r></w:p>
<w:p><w:r><w:t>插图：</w:t></w:r><w:r><w:drawing><a:blip r:embed="rId5"/></w:drawing></w:r></w:p>
<w:tbl><w:tr><w:tc><w:p><w:r><w:t>列A</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>列B</w:t></w:r></w:p></w:tc></w:tr>
<w:tr><w:tc><w:p><w:r><w:t>1</w:t></w:r></w:p></w:tc>
<w:tc><w:p><w:r><w:t>2</w:t></w:r></w:p></w:tc></w:tr></w:tbl>
</w:body></w:document>"""

STYLES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:styleId="Heading2"><w:name w:val="heading 2"/></w:style>
<w:style w:styleId="ListParagraph"><w:name w:val="List Paragraph"/></w:style>
</w:styles>"""

RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId5" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
 Target="media/fig1.png"/></Relationships>"""

DOCX_EXPECT = ("## 来自 Word 的标题", "**加粗的一句**", "- 编号列表项", "- 样式列表项",
               "![](images/01-fig1.png)", r"| 列A\|内 | 列B |", "|---|---|")


def docx_ok():
    """返回 (是否通过, 说明)。真实读一遍产物，不只看退出码。"""
    import zipfile
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "a.docx")
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("word/document.xml", DOC_XML.replace("列A", "列A|内"))
            z.writestr("word/styles.xml", STYLES_XML)
            z.writestr("word/_rels/document.xml.rels", RELS_XML)
            z.write(os.path.join(FIX, "fixtures", "tiny.png"), "word/media/fig1.png")
        out = os.path.join(d, "a.md")
        code, log = run([os.path.join(SCRIPTS, "extract_docx.py"), src, "-o", out], d)
        if code != 0 or not os.path.exists(out):
            return False, f"退出码 {code}\n{log}"
        md = open(out, encoding="utf-8").read()
        missing = [x for x in DOCX_EXPECT if x not in md]
        # 抽完直接渲染：真实路径上用户就是这么做的，图还没补职责也不能崩
        _, meta3, blocks3, body3 = _r.render(md)
        errors3 = _r.compose_gate(meta3, blocks3, d)[0]
        code3, log3 = bool(errors3), "\n".join(errors3)
        if code3 != 1 or "没有声明职责" not in log3 or "Traceback" in log3:
            missing.append(f"抽取图无职责没有正确拒绝\n{log3[-400:]}")
        img = os.path.join(d, "images", "01-fig1.png")
        if not os.path.exists(img):
            missing.append("图片未解包到 images/")
        # 深标题不丢成普通正文，损坏XML不Traceback。
        deep = os.path.join(d, "deep.docx")
        with zipfile.ZipFile(deep, "w") as z:
            z.writestr("word/document.xml", DOC_XML.replace("Heading2", "Heading4"))
            z.writestr("word/styles.xml", STYLES_XML.replace("Heading2", "Heading4").replace("heading 2", "heading 4"))
            z.writestr("word/_rels/document.xml.rels", RELS_XML)
            z.write(os.path.join(FIX, "fixtures", "tiny.png"), "word/media/fig1.png")
        import extract_docx, io, contextlib
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = extract_docx.extract(deep, os.path.join(d, "deep.md"))
        if rc or "### 来自 Word 的标题" not in open(os.path.join(d, "deep.md"), encoding="utf-8").read():
            missing.append("深标题层级未归一化")
        malformed = os.path.join(d, "malformed.docx")
        with zipfile.ZipFile(malformed, "w") as z:
            z.writestr("word/document.xml", "<broken")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as errors:
            rc = extract_docx.extract(malformed, os.path.join(d, "malformed.md"))
        msg = errors.getvalue()
        if rc != 1 or "Traceback" in msg:
            missing.append("损坏XML错误处理")
        # 反例：不是 docx 的文件必须失败，不能假装成功
        bad = os.path.join(d, "b.docx")
        open(bad, "w").write("不是 zip")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            code2 = extract_docx.extract(bad, os.path.join(d, "b.md"))
        return (not missing and code2 == 1), f"缺 {missing} · 非 docx 退出码 {code2}"


def shots(shoot=None):
    """把每篇预览截成 320/360/390/430px PNG —— Gate 3 通读（人眼或视觉模型）的**证据**，不是视觉合格证。

    产出证据包：全页 + 首屏截图、REVIEW.md 逐张检查清单与复现命令。截图成功只证明渲染与
    截图流程顺利；构图、层级、密度、小字清晰度、封面裁切的结论只能由通读的人给出。
    --shoot 额外指定稿件 md（如 evals 样稿），同样进证据包，供缺陷复现与人工审阅。
    需要 playwright（skill 本身不需要）；显式请求但未安装即失败。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\n截图失败：未安装 playwright"
              "（pip install playwright && python3 -m playwright install chromium）")
        return False
    font = subprocess.run(["fc-match", "-f", "%{family}", "Noto Sans CJK SC"], capture_output=True, text=True)
    if font.returncode or "Noto Sans CJK" not in font.stdout:
        print("截图失败：须安装 fonts-noto-cjk，不能用缺字截图通过")
        return False
    out_dir = os.path.join(ROOT, "assets", "shots")
    os.makedirs(out_dir, exist_ok=True)
    made, failed, manifest = [], [], []
    look = {  # 语料的视觉审阅重点：给通读的人的指引，不是自动判定项
        "skills": "纯文字层级：段距/章标/重点与正文的权重差",
        "portrait": "图注可读性、引文出处行、叙事段落节奏",
        "visual": "bars 数值口径、表头基线、来源紧邻、airy 密度",
        "brief": "dense 节奏、表格与 data 大字、待补封面提示",
        "longread": "目录位置与编号、代码块小字、长文转场留白",
    }

    def one_shot(pg, prev, stem):
        """截全页 + 首屏，并跑元素级溢出检查。返回 (png路径, 失败原因或 None)。"""
        pg.goto("file://" + prev)
        pg.wait_for_function("() => [...document.images].every(i => i.complete)")
        pg.evaluate("() => document.fonts.ready")
        # Verify the browser actually uses a CJK font, not only a fontconfig alias.
        pg.evaluate("""() => { const p=document.createElement('p'); p.id='font-probe'; p.textContent='中文排版验证'; p.style.fontFamily="Noto Sans CJK SC";document.body.append(p); }""")
        pg.evaluate("""() => document.fonts.load('16px "Noto Sans CJK SC"', '中文排版验证')""")
        pg.locator("#font-probe").screenshot()  # force layout/paint before querying platform glyphs
        cdp = pg.context.new_cdp_session(pg)
        cdp.send("DOM.enable"); cdp.send("CSS.enable")
        root = cdp.send("DOM.getDocument")["root"]["nodeId"]
        node = cdp.send("DOM.querySelector", {"nodeId": root, "selector": "#font-probe"})["nodeId"]
        fonts = cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node})["fonts"]
        pg.evaluate("document.querySelector('#font-probe').remove()")
        cdp.detach()
        if not any("Noto Sans CJK" in f["familyName"] and f["glyphCount"] >= 6 for f in fonts):
            return "", f"{stem}（浏览器中文字体未实际生效：{fonts}）"
        pg.evaluate("scrollTo(0, 0)")
        png = os.path.join(out_dir, stem + ".png")
        pg.screenshot(path=png, full_page=True)
        pg.screenshot(path=os.path.join(out_dir, stem + "_首屏.png"),
                      clip={"x": 0, "y": 0, "width": 390, "height": 844})
        if "<img" in open(prev, encoding="utf-8").read() and not pg.evaluate(
                "() => [...document.images].every(i => i.naturalWidth > 0)"):
            return png, f"{stem}（图片未加载）"
        for width in (320, 360, 390, 430):
            pg.set_viewport_size({"width": width, "height": 844})
            pg.screenshot(path=os.path.join(out_dir, f"{stem}_{width}.png"), full_page=True)
            if pg.evaluate("document.documentElement.scrollWidth > innerWidth || [...document.querySelectorAll('#c p,#c img,#c table,#c th,#c td')].some(e=>e.scrollWidth>e.clientWidth+1 || e.getBoundingClientRect().right>document.querySelector('#c').getBoundingClientRect().right+1)"):
                return png, f"{stem}（{width}px横向溢出）"
        pg.set_viewport_size({"width": 390, "height": 844})
        return png, None

    with sync_playwright() as p:
        b = p.chromium.launch()
        for name in CASES:
            pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            # 复用case_ok已生成的预览，不再次渲染
            html = os.path.join(FIX, f"_shots_{name}.html")
            if not os.path.isfile(html):
                failed.append(name)
                pg.close()
                continue
            prev = os.path.splitext(html)[0] + "_预览.html"
            png, err = one_shot(pg, prev, name)
            if err:
                failed.append(err)
            # Browser evidence: #c vs publication body, and real copy event payload.
            body = open(html, encoding="utf-8").read()
            expected = pg.evaluate("h => {const n=document.createElement('section');n.innerHTML=h;return n.textContent}", body)
            if pg.locator("#c").text_content() != expected:
                failed.append(f"{name}（预览/正文内容不一致）")
            pg.evaluate("document.addEventListener('copy', e => {const put=e.clipboardData.setData.bind(e.clipboardData); e.clipboardData.setData=(type,data)=>{if(type==='text/html')window.copied=data;return put(type,data)}})")
            pg.locator("button").click()
            pg.wait_for_function("typeof window.copied === 'string'")
            copied = pg.evaluate("window.copied")
            if any(x in copied for x in ("<script", "data:image", 'class="', 'data-local=')):
                failed.append(f"{name}（剪贴板混入预览资源）")
            from check import image_sources
            if image_sources(copied) != image_sources(body):
                failed.append(f"{name}（复制图片路径不一致）")
            del_copy = pg.evaluate("h => {const n=document.createElement('section');n.innerHTML=h;return n.textContent}", copied)
            # inline styles survive the browser's copy serialization, not WeChat sanitation.
            copied_style = pg.evaluate("h=>{const n=document.createElement('section');n.innerHTML=h;return [...n.querySelectorAll('[style]')].map(e=>e.getAttribute('style'))}", copied)
            body_style = pg.evaluate("h=>{const n=document.createElement('section');n.innerHTML=h;return [...n.querySelectorAll('[style]')].map(e=>e.getAttribute('style'))}", body)
            if copied_style != body_style:
                failed.append(f"{name}（复制内联样式不一致）")
            if del_copy != expected:
                failed.append(f"{name}（复制内容不一致）")
            pg.evaluate("delete window.copied")
            made.append(png)
            manifest.append((name + ".png", f"fixtures 合成语料 {name}", look.get(name, "")))
            pg.close()
        from render import THEMES
        personality_source = os.path.join(ROOT, "evaluation", "cases", "business.edited.md")
        for theme in THEMES:
            output = os.path.join(FIX, f"personality_{theme}.html")
            code, log = run([os.path.join(SCRIPTS, "render.py"), personality_source,
                             "--theme", theme, "-o", output], os.path.dirname(personality_source))
            if code:
                failed.append(f"{theme}（人格渲染失败）{log[-300:]}")
                continue
            prev = os.path.splitext(output)[0] + "_预览.html"
            pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            png, err = one_shot(pg, prev, f"personality_{theme}")
            if err:
                failed.append(err)
            else:
                made.append(png)
                manifest.append((f"personality_{theme}.png", "真实来源商业分析优化稿 · 同稿六人格",
                                 "导语/章节/引文/数据/表格/空间节奏的区别"))
            pg.close()
        # Exercise grouped layouts in the browser, including a style-stripped reading-order fallback.
        sample = os.path.join(FIX, "composition.md")
        with open(sample, "w", encoding="utf-8") as f:
            f.write('# 构图回归\n\n![甲对象](images/fig.jpg "对比 comparison")\n'
                    '![乙对象](images/fig.jpg "对比 comparison")\n\n'
                    '![第一步](images/fig.jpg "场景 sequence")\n'
                    '![第二步](images/fig.jpg "场景 sequence")\n')
        code, log = run([os.path.join(SCRIPTS, "render.py"), sample], FIX)
        if code:
            failed.append("构图样张渲染失败：" + log[-300:])
        else:
            pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            prev = os.path.join(FIX, "composition_paper_预览.html")
            png, err = one_shot(pg, prev, "composition")
            if err: failed.append(err)
            else:
                made.append(png)
                manifest.append(("composition.png", "合成构图样张", "并列几何、顺序、图注与微信降级"))
            pg.set_viewport_size({"width": 320, "height": 844})
            geometry = pg.evaluate("""() => {let a=[...document.querySelectorAll('#c table td')];
                let x=a.map(e=>e.getBoundingClientRect());
                return x.length===2 && x[1].left>=x[0].right-1 && Math.abs(x[0].top-x[1].top)<2;}""")
            if not geometry: failed.append("comparison 未实际并列")
            text = pg.locator('#c').text_content()
            pg.evaluate("() => document.querySelectorAll('#c [style]').forEach(e=>e.removeAttribute('style'))")
            if pg.locator('#c').text_content() != text or not (text.index('甲对象') < text.index('乙对象') < text.index('第一步') < text.index('第二步')):
                failed.append("清除样式后图注顺序丢失")
            pg.close()
        for md in (shoot or []):
            md = os.path.abspath(md)
            stem = os.path.splitext(os.path.basename(md))[0]
            out_html = os.path.join(FIX, f"shoot_{stem}.html")
            code, log = run([os.path.join(SCRIPTS, "render.py"), md, "-o", out_html], os.path.dirname(md))
            if code != 0:
                failed.append(f"{stem}（渲染失败）\n{log[-300:]}")
                continue
            pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
            prev = os.path.splitext(out_html)[0] + "_预览.html"
            png, err = one_shot(pg, prev, f"eval_{stem}")
            if err:
                failed.append(err)
            else:
                made.append(png)
                manifest.append((f"eval_{stem}.png", md.replace(ROOT + os.sep, ""),
                                 "按稿件实际：断行/小字来源/层级/密度/图表/中英混排"))
            pg.close()
        b.close()
    review = os.path.join(out_dir, "REVIEW.md")
    with open(review, "w", encoding="utf-8") as f:
        f.write("# Gate 3 截图证据包（320/360/390/430px · 2x）\n\n"
                "**截图通过 ≠ 视觉通过。** 本目录只证明渲染与截图流程顺利完成；构图、层级、密度、"
                "小字清晰度、封面裁切由通读的人（视觉总监）判定，结论写回验收记录，可无需修改。\n\n"
                "复现：`python3 tests/run.py --shots [--shoot 文章.md ...]`；"
                "单稿另可 `python3 scripts/render.py 文章.md` 得正文、预览与 meta。\n\n"
                "## 逐张必看\n\n"
                "- 中文断行、标点避头尾；标题／正文／图注层级一眼可分\n"
                "- 图注、来源、表头等 12–14px 小字放大 100% 是否读得清（结论以真机为准）\n"
                "- 长表是否需要改结构（不缩字号硬塞）；数值图的口径与来源是否紧邻\n"
                "- 长文密度与转场留白；首屏信息量与视觉重心（对照 *_首屏.png）\n"
                "- 封面 2.35:1 与 1:1 裁切的主体是否成立（见各预览的封面区）\n"
                "- 每个问题给 保留／修改／删除 + 理由\n\n"
                "## 证据清单\n\n| 文件 | 来源 | 审阅重点 |\n|---|---|---|\n")
        for png_name, src, w in manifest:
            f.write(f"| {png_name} + {png_name[:-4]}_首屏.png + {png_name[:-4]}_{{320,360,390,430}}.png | {src} | {w or '按稿件实际'} |\n")
    print(f"\nGate 3 截图证据（390px · 2x · 4宽度元素级与复制样式检查）：{out_dir}")
    for m in made:
        print("   " + os.path.basename(m))
    print("   证据清单 → REVIEW.md（截图是审阅输入，不是视觉合格证）")
    if failed:
        print("   失败：" + "、".join(failed))
        return False
    return True


# ---- 结构基准：5 篇语料的「机器可验证」快照 ----
# 只锁判断的落点（人格 / 资产数 / 结构 / 首屏层数），不锁文笔。
# 改稿不该动这张表；这张表动了，说明这套 Skill 对这批文章的判断变了——那必须是有意的。
def baseline_ok():
    """退回「只看退出码」是不够的：图全丢了、目录没了、主题换了，退出码照样是 0。

    期望值与语料同源于 fixtures.CORPUS，避免两张表各说一套。
    语料是合成的，所以这里锁的是解析与首屏推导；对真实稿件的编辑判断仍属 Gate 3 通读。
    """
    problems = []
    for case, spec in _fx.CORPUS.items():
        meta, blocks = _r.parse(spec["md"])
        got = {
            "theme": meta.get("theme", "paper"),
            "imgs": sum(1 for k, _ in blocks if k == "img"),
            "peak": any(k == "peak" for k, _ in blocks),
            "toc": meta.get("toc", "").lower() in ("true", "yes", "1")
                   and len([b for k, b in blocks if k == "h2"]) >= 3,
            "layers": len(_r.first_screen(meta, blocks)),
        }
        for k, v in spec["baseline"].items():
            if got[k] != v:
                problems.append(f"{case}.{k} 期望 {v} 实为 {got[k]}")
    return not problems, ("；".join(problems) if problems
                          else f"{len(CASES)} 篇合成稿 · 人格/资产/结构/首屏 全部对齐基准")


def preflight_ok():
    """发布预检：不联网，验证 Gate 1 + 原生字段 + 封面按文章目录解析（换个 cwd 也得找得到）。"""
    import io
    import contextlib
    sys.path.insert(0, SCRIPTS)
    import publish as _p
    with tempfile.TemporaryDirectory() as d:
        art = os.path.join(d, "art")
        os.makedirs(os.path.join(art, "images"))
        for n in ("cover.jpg", "fig.jpg"):
            shutil.copy(os.path.join(FIX, "images", n), os.path.join(art, "images", n))
        md = os.path.join(art, "a.md")
        open(md, "w", encoding="utf-8").write(
            HEAD + "author: 甲木\ncover: images/cover.jpg\n---\n\n"
            "> 钩子一句。\n\n正文一段。\n\n![说明](images/fig.jpg \"解释\")\n")
        run([os.path.join(SCRIPTS, "render.py"), md, "-o", os.path.join(art, "a.html")], art)
        side = json.load(open(os.path.join(art, "a.html".replace(".html", ".meta.json")), encoding="utf-8"))
        ns = argparse.Namespace(appid=None, secret=None, title=None, cover=None, author=None, digest=None,
                                source_url=None, no_open_comment=False, fans_only_comment=False, submit=False)
        cwd0 = os.getcwd()
        os.chdir(d)                       # 故意从别处执行：封面相对路径必须仍解析到文章目录
        try:
            s1 = _p.resolve_settings(ns, side, {})
            s1["cover"] = _p.resolve_cover(s1["cover"], os.path.join(art, "a.html"))
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = _p.preflight(os.path.join(art, "a.html"), s1)
            out = buf.getvalue()
            s2 = dict(s1, cover=os.path.join(art, "nope.jpg"))
            with contextlib.redirect_stdout(io.StringIO()) as buf2:
                rc_bad = _p.preflight(os.path.join(art, "a.html"), s2)
            out_bad = buf2.getvalue()
        finally:
            os.chdir(cwd0)
    problems = []
    if rc != 0:
        problems.append(f"正常稿预检应通过（rc={rc}）")
    if "a" not in out or "预检通过" not in out:
        problems.append("预检输出缺少结论")
    if "images/cover.jpg" not in out or "文件不存在" in out:
        problems.append("封面未按文章目录解析")
    if "1 张待上传" not in out:
        problems.append("未列出待上传的正文图片")
    if not rc_bad or "文件不存在" not in out_bad:
        problems.append("封面缺失时预检应判未通过")
    return not problems, ("；".join(problems) if problems else "Gate 1 · 原生字段 · 封面路径 · 待传图片 全对")


def toc_after_first_para_ok():
    md = HEAD + "toc: true\n---\n> 钩子。\n\n第一段正文。\n\n##甲\n\n一。\n\n## 乙\n\n二。\n\n## 丙\n\n三。\n\n## 丁\n\n四。\n"
    html = _r.render(md)[3]
    return 0 <= html.find("第一段正文") < html.find("目录"), "首段 → 目录"


def delivery_defects_ok():
    """具体缺陷，不以mock成功代替真实平台测试。"""
    import contextlib
    import io
    from unittest.mock import patch
    import publish as pub
    from check import check, image_sources
    results = []
    def test(name, ok):
        results.append((name, bool(ok)))
    r = _r.R(_r.THEMES["paper"], "standard")
    test("零值不造2%长度，小值保持比例", "width:0%" in r.bars(["0｜甲", "10｜乙"]) and "width:0.1%" in r.bars(["1｜甲", "1000｜乙"]))
    for value in ("-2", "NaN", "多", "9" * 400):
        md = HEAD + "---\n::: bars 件\n" + value + "｜甲\n10｜乙\n:::\n"
        try:
            _, meta, blocks, body = _r.render(md)
            errors, _ = _r.compose_gate(meta, blocks, FIX)
            test("坏bars无崩溃并报具体错误：" + value[:8], any("值必须" in e for e in errors))
        except Exception:
            test("坏bars无崩溃：" + value[:8], False)
    _bars_md = HEAD + "---\n::: bars 件\n1｜甲\n2｜乙\n:::\n\n::: note 来源\n{}\n:::\n"
    test("来源短写主体＋日期被接受",
          not any("缺少紧邻来源" in m for m in _r.compose_gate(*_r.parse(_bars_md.format("来源：21经济网（2025-01-14）。口径：媒体转述。")))[0]))
    test("来源仅主体无日期无地址被拦",
          any("缺少紧邻来源" in m for m in _r.compose_gate(*_r.parse(_bars_md.format("来源：网友说的。")))[0]))
    _link = r.inline("[短名](https://example.com/a/very/long/path?x=1)")
    test("链接保留href而不追加长地址", "短名" in _link and 'href="https://example.com' in _link)
    test("裸地址仍原样可见（要就整行写）", "https://example.com/x" in r.inline("https://example.com/x"))
    test("来源/口径行过长被提醒",
          any("过长" in m for m in _r.compose_gate(*_r.parse(HEAD + "---\n::: note 口径\n" + "长句" * 50 + "\n:::\n"))[1]))
    _note3 = HEAD + "---\n::: note 来源与口径\n{}\n:::\n"
    test("来源与口径两行内（一行来源一行口径）",
          not any("两行内" in m for m in _r.compose_gate(*_r.parse(_note3.format("来源：21经济网（2025-01-14）。\n口径：媒体转述，非审计。")))[0]))
    test("来源与口径三行被拦",
          any("两行内" in m for m in _r.compose_gate(*_r.parse(_note3.format("来源：甲（2025）。\n口径：第一条。\n口径：第二条多写一句。")))[0]))
    test("地址单独一行不占来源行数",
          not any("两行内" in m for m in _r.compose_gate(*_r.parse(_note3.format("来源：甲（2025）。\n口径：媒体转述。\nhttps://example.com/x")))[0]))
    _dup = r.note("来源", ["来源: 甲（2025）。", "口径：媒体转述。"])
    test("标签点明来源，正文不重复「来源」", _dup.count("来源") == 1 and "甲（2025）" in _dup and "口径：" in _dup)
    _dup2 = r.note("来源与口径", ["来源：甲（2025）。", "口径：媒体转述。"])
    test("来源与口径标签剥两个前缀", _dup2.count("来源") == 1 and _dup2.count("口径") == 1 and "甲（2025）" in _dup2)
    test("代码内CSS字面量不误判", not check(r.code("css", ["position:fixed; display:grid; float:left; {{demo}};"]))[0])
    test("事件与协议相对图片被拦", bool(check('<img src="//bad/x" onerror="x()" style="max-width:100%">')[0]))
    malformed = check('<section><p><span leaf="">文字</span></section>')[0]
    test("Gate 1 拦截错序或未闭合标签", any("嵌套顺序" in x or "未闭合" in x for x in malformed))
    test("img/br不泄漏等宽状态", bool(check(r.code("", ["x"]) + '<br><p>未包裹</p>')[0]))
    test("首屏引文来源不丢失", "来源人物" in r.quote("引文", "来源人物", "lead"))
    meta, blocks = _r.parse(HEAD + "---\n::: data\n10\n:::\n\n::: note 演示\n演示计数，非统计。\n:::\n")
    test("data 不静默吞标签", any("数值与标签" in e for e in _r.compose_gate(meta, blocks)[0]))
    test("中文逗号不变成分号", _r.typo("你好,世界;再见!") == "你好，世界；再见！")
    test("表格转义管道保住列", _r.parse("| 甲\\|乙 | 丙 |\n|---|---|\n")[1][0][1] == [["甲|乙", "丙"]])
    for text in ("::: note\n没有闭合", "```python\nx", '![坏图](a b "说明")'):
        try:
            _r.parse(text)
            test("不合法输入显式失败", False)
        except ValueError:
            test("不合法输入显式失败", True)
    test("裸URL含数字/标点不被中文化", 'https://example.com/v1,a?x=1.2&amp;y=3' in r.inline('来源 https://example.com/v1,a?x=1.2&y=3 中文。'))
    test("保留原引号不制造引言", '"原话"' in r.inline('他说"原话"') and '「' not in _r.R(_r.THEMES['ink'], 'standard').quote('这是作者判断', '', 'peak'))
    test("中文与混排自然左对齐，表头不拉字距", 'text-align:justify' not in r.para('纯中文正文') and 'letter-spacing:2px' not in r.table([['长表头', '数值'], ['中文', '12%']]))
    wide = _r.col_widths([["方案", "研发占比", "备注"], ["甲：重研发", "60%", "产品迭代快，获客慢，留存中等"]])
    test("表格列宽按内容分配，数值列不被挤窄", wide[1] >= 9 and wide[2] > wide[1] and abs(sum(wide) - 100) < 1e-6)
    header_rows = [["观察对象", "年工时", "文中位置"], ["柬埔寨", "约2500小时", "高工时、较低人均收入"]]
    header_width = _r.col_widths(header_rows)[0] / 100 * 288
    test("四字中文表头在320px不形成单字孤行", header_width + 1 >= _r.cell_min_px("观察对象"))
    _t4 = [["一季度", "二季度", "三季度", "四季度"],
           ["12345678元", "23456789元", "34567890元", "45678901元"]]
    test("表格数值列小屏放不下被拦（320px 溢出）",
         any("小屏放不下" in m for m in _r.compose_gate({"title": "回归"}, [("table", _t4)])[0]))
    test("表格删低价值列后小屏放得下",
         not any("小屏放不下" in m for m in _r.compose_gate({"title": "回归"},
                                                           [("table", [row[:3] for row in _t4])])[0]))
    test("纯数字单元格禁止断行", "white-space:nowrap" in r.table([["列", "值"], ["甲", "60%"]]) and "white-space:nowrap" not in r.table([["列", "值"], ["甲", "中文很长的一格"]]))
    test("近似数值与中文单位保持同线", "white-space:nowrap" in r.table([["对象", "年工时"], ["甲", "约2500小时"], ["乙", "不足1600小时"]]))
    toc_md = HEAD + "toc: true\n---\n> 导语。\n\n第一段。\n\n## **重点**结论\n\n一。\n\n## ==关键词==\n\n二。\n\n## 第三\n\n三。\n"
    toc_html = _r.render(toc_md)[3]
    toc_block = toc_html[toc_html.find("目录") - 200:toc_html.find("目录") + 400] if "目录" in toc_html else ""
    test("目录不外露行内标记", "重点结论" in toc_html and "**重点**" not in toc_block and "==关键词==" not in toc_block)
    test("引文侧线使用主题强调色而非发丝线", 'border-left:2px solid' in r.quote("引文", "出处", "quote") and 'border-left:1px solid' not in r.quote("引文", "出处", "quote"))
    test("引用原标点不被归一", '中文,原句...' in r.quote('中文,原句...', '出处', 'quote'))
    test("表格语义与正负单位保持", '<th ' in r.table([['列', '值'], ['甲', '−8 百分点']]) and '−8 百分点' in r.table([['列', '值'], ['甲', '−8 百分点']]))
    meta, blocks = _r.parse(HEAD + '---\n|甲|乙|\n|---|---|\n|只有一列|\n')
    test("表格行列不齐明确失败", any('行列数' in e for e in _r.compose_gate(meta, blocks)[0]))
    test("BOM/CRLF不丢原生字段", _r.parse('\ufeff' + HEAD.replace('\n', '\r\n') + '---\r\n正文')[0]['title'] == '回归用例|固定标题')
    code = r.code('python', ['  x = 1', '    y = 2', ''])
    test("代码保留原空格不换全角，pre-wrap不误拦", '  x = 1' in code and 'white-space:pre-wrap' in code and not check(code)[0])
    test("图表零轴与最长项解释可见", '零起点' in r.bars(['1｜甲','2｜乙'], '件') and '本组最大值' in r.bars(['1｜甲','2｜乙']))
    meta, blocks = _r.parse(HEAD + '---\n正文\n\n![图](todo "   ")\n')
    test("空白职责不崩溃且拒绝", any('没有声明职责' in e for e in _r.compose_gate(meta, blocks)[0]))
    test("深色重点加粗继承反色不变黑", 'color:inherit' in _r.R(_r.THEMES['ink'],'standard').quote('**核心主张**', '', 'peak'))
    test("frontmatter带引号的井号不截内容", _r.parse('---\ntitle: "标题 # 内文" # 注释\n---\n正文')[0]['title'] == '标题 # 内文')
    meta, blocks = _r.parse(HEAD + 'deck: 副题\n---\n> 导语\n\n::: peak\n主张一\n:::\n\n::: peak\n主张二\n:::\n')
    test("多重点和副题/导语由编辑判断，不机械阻断", not _r.compose_gate(meta, blocks)[0] and not any('两个钩子' in e for e in _r.compose_gate(meta, blocks)[1]))
    # ---- 本次视觉审计固化的缺陷：章标叠加、重点无形态、来源悬空、表头无基线 ----
    def text_of(md):
        return re.sub(r'<[^>]+>', '', _r.render(md)[3])
    t1 = text_of(HEAD + '---\n## 一、问题\n\n正文。\n\n## 二、办法\n\n正文。\n\n## 三、收尾\n\n正文。\n')
    test("章标不叠加标题自带序号", '01　一、问题' not in t1 and '02　二、办法' not in t1 and '一、问题' in t1)
    t2 = text_of(HEAD + '---\n## 问题\n\n正文。\n\n## 办法\n\n正文。\n\n## 收尾\n\n正文。\n')
    test("无序号标题仍获得章标", '01　问题' in t2 and '02　办法' in t2)
    t3 = text_of(HEAD + 'toc: true\n---\n> 钩。\n\n首段。\n\n## 一、问题\n\n一。\n\n## 二、办法\n\n二。\n\n## 三、收尾\n\n三。\n')
    test("目录行跟随同一套编号规则", '01　一、问题' not in t3 and '一、问题' in t3)
    t4 = text_of(HEAD + '---\n## 第一段：准备\n\n正文。\n\n## 第二段：装箱\n\n正文。\n\n## 第三段：收尾\n\n正文。\n')
    test("第X段式标题同样不叠加章标", '01　第一段' not in t4 and '第一段：准备' in t4 and '02　第二段' not in t4)
    rp, rb, rfr, rl, rfo, ri = (_r.R(_r.THEMES[k], 'standard') for k in ('paper', 'bone', 'frost', 'letter', 'folio', 'ink'))
    structural = set()
    for theme in _r.THEMES:
        renderer = _r.R(_r.THEMES[theme], 'standard')
        sample = (renderer.quote('导语', '', 'lead') + renderer.h2('章节', 1)
                  + renderer.h3('小标题') + renderer.quote('引文', '出处', 'quote')
                  + renderer.data(['10｜甲', '20｜乙']) + renderer.table([['项', '值'], ['甲', '10']])
                  + renderer.lst(True, ['一步', '二步']) + renderer.img('说明', 'x.jpg', '解释') + renderer.hr())
        structural.add(re.sub(r'#[0-9A-Fa-f]{6}', '#COLOR', sample))
    test("六人格真实组件输出在去色后仍各不相同", len(structural) == 6)
    test("paper 重点是短强调线，与标题层级不同貌", 'background:#5C6758' in rp.quote('主张', '', 'peak') and 'width:28px' in rp.quote('主张', '', 'peak'))
    test("bone 重点是衬线上下细线", ('border-top:1px solid' in rb.quote('主张', '', 'peak')
          and 'border-bottom:1px solid' in rb.quote('主张', '', 'peak') and _r.SERIF in rb.quote('主张', '', 'peak')))
    test("frost 重点是加粗侧线", 'border-left:3px solid' in rfr.quote('主张', '', 'peak'))
    test("letter 重点是暖底色块，引文是无侧线的人声层级", ('background:#F6EBDC' in rl.quote('主张', '', 'peak')
          and 'border-left' not in rl.quote('引文', '出处', 'quote') and '—— 出处' in rl.quote('引文', '出处', 'quote')))
    test("folio 反色紧凑、ink 反色舒展", 'padding:13px 15px' in rfo.quote('主张', '', 'peak') and 'padding:20px 18px' in ri.quote('主张', '', 'peak'))
    html = _r.render(HEAD + '---\n::: bars 件\n1｜甲\n2｜乙\n:::\n\n::: note 来源\nhttps://example.com/x\n:::\n')[3]
    test("来源 note 紧贴图示而非悬空", 'margin:32px 0 10px' in html and 'margin:10px 0 16px;' in html)
    html = _r.render(HEAD + '---\n![图](images/fig.jpg "证据")\n\n::: note 来源\nhttps://example.com/x\n:::\n')[3]
    test("证据图来源紧贴图片", 'margin:24px 0 10px' in html and 'margin:10px 0 16px;' in html)
    test("表头基线重于行线", 'border-bottom:1px solid #746F66' in r.table([['列', '值'], ['甲', '1']])
          and 'border-bottom:1px solid #E8E4DB' in r.table([['列', '值'], ['甲', '1']]))
    long_one = '这是一句足够长的测试句子。' * 12
    d = _r.auto_digest(*_r.parse(HEAD + '---\n' + long_one + '\n'))
    test("自动摘要在句末收口，不腰斩", len(d) <= 120 and d.endswith('。') and '测试句子。' in d)
    class Response:
        def __init__(self, raw): self.raw = raw
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self): return self.raw
    with patch.object(pub.urllib.request, "urlopen", return_value=Response(b"\xff\xd8jpeg")):
        test("真实响应解析支持图片二进制", pub.get_material("tok", "MID") == b"\xff\xd8jpeg")
    with patch.object(pub.urllib.request, "urlopen", return_value=Response(b'{"errcode":40007,"errmsg":"invalid"}')):
        try:
            pub.get_material("tok", "MID")
            test("二进制路径仍识别JSON错误", False)
        except pub.WeChatAPIError as e:
            test("二进制路径仍识别JSON错误", e.errcode == 40007)
    with tempfile.TemporaryDirectory() as d, contextlib.redirect_stdout(io.StringIO()):
        art = os.path.join(d, "article")
        dest = os.path.join(d, "delivery")
        os.makedirs(art)
        shutil.copytree(os.path.join(FIX, "images"), os.path.join(art, "images"))
        path = os.path.join(art, "a.md")
        open(path, "w", encoding="utf-8").write(HEAD + 'cover: images/cover.jpg\n---\n正文。\n\n![解释](images/fig.jpg "解释")\n')
        html = os.path.join(dest, "body.html")
        rc, log = run([os.path.join(SCRIPTS, "render.py"), path, "-o", html], d)
        side = json.load(open(os.path.splitext(html)[0] + ".meta.json", encoding="utf-8"))
        src = open(html, encoding="utf-8").read()
        preview = open(os.path.splitext(html)[0] + "_预览.html", encoding="utf-8").read()
        settings = dict(title=side["api_title"], author=None, digest=side["digest"], source=None,
                        cover=pub.resolve_cover(side["cover"], html), open_comment=True, fans_only=False, submit=False)
        test("跨目录正文/封面路径可预检", rc == 0 and pub.preflight(html, settings) == 0 and os.path.isfile(os.path.join(dest, image_sources(src)[0])))
        test("预览本地嵌图，正文不含base64/工具栏", 'src="data:image/jpeg;base64,' in preview and 'data:image' not in src and '<script' not in src)
        # 路径实体、单双引号、重复图共一次上传。
        entity_path = os.path.join(dest, "a&b.jpg")
        shutil.copy(os.path.join(FIX, "images", "fig.jpg"), entity_path)
        frag = '<img src = "a&amp;b.jpg"><img src=\'a&amp;b.jpg\'><IMG SRC=a&amp;b.jpg>'
        with patch.object(pub, "upload_content_image", return_value="https://mmbiz.qpic.cn/x?a=1&b=2") as upload:
            rewritten = pub.rewrite_local_images(frag, "tok", dest)
            test("实体路径/重复图片只上传一次", upload.call_count == 1 and rewritten.count("&amp;b=2") == 3)
        cache = os.path.join(d, "cache.json")
        cover = settings["cover"]
        open(cache, "w").write(json.dumps({pub.sha256(cover): "MID"}))
        with patch.object(pub, "get_material", side_effect=pub.WeChatAPIError(40001, "token")), patch.object(pub, "upload_thumb_material") as upload:
            try:
                pub.upload_thumb_material_cached("tok", cover, cache)
                test("权限错误不重传", False)
            except pub.WeChatAPIError:
                test("权限错误不重传", upload.call_count == 0)
        for invalid in ('[]', '{"submit":"false"}', '{"need_open_comment":1}'):
            config = os.path.join(d, "bad.json")
            open(config, 'w').write(invalid)
            try:
                pub.load_config(config)
                test("配置JSON类型拒绝", False)
            except ValueError:
                test("配置JSON类型拒绝", True)
        test("空白CLI标题不能绕过原生标题转换", pub.resolve_settings(argparse.Namespace(appid=None, secret=None,title=" ",cover=None,author=None,digest=None,source_url=None,no_open_comment=False,fans_only_comment=False,submit=False), {}, {})['title'] == '')
        meta_path = os.path.splitext(html)[0] + '.meta.json'
        open(meta_path, 'w').write('[]')
        try:
            pub.preflight(html, settings)
            test("meta JSON非对象明确拒绝", False)
        except ValueError:
            test("meta JSON非对象明确拒绝", True)
        open(meta_path, 'w').write(json.dumps(dict(side, pending_assets=True)))
        test("pending_assets在真实预检阻断", pub.preflight(html, settings) == 1)
        open(meta_path, 'w').write(json.dumps(side))
        open(cache, 'w').write('[]')
        with patch.object(pub, 'upload_thumb_material', return_value='NEW') as upload:
            test("坏缓存形状不崩且重建", pub.upload_thumb_material_cached('tok', cover, cache) == 'NEW' and upload.call_count == 1)
        # 不仅测试手动preflight，也调用实际发布入口，坏稿应0网络。
        for label, content, title in (("待补", r.img("缺图", "todo", "场景"), "标题"), ("超限", src, "题" * 33), ("旧正文", src + r.para("外部改动"), "标题"), ("空标题", src, "")):
            open(html, "w", encoding="utf-8").write(content)
            with patch.object(pub, "get_stable_access_token") as token:
                try:
                    pub.publish_html_article("app", "secret", html, cover, title, material_cache=None)
                    test("真实入口预检阻断：" + label, False)
                except ValueError:
                    test("真实入口预检阻断：" + label, token.call_count == 0)
        open(html, "w", encoding="utf-8").write(src)
        with patch.object(pub, "get_stable_access_token", return_value="tok"), patch.object(pub, "check_draft_switch", return_value=True), patch.object(pub, "upload_thumb_material", return_value="THUMB"), patch.object(pub, "upload_content_image", return_value="https://mmbiz.qpic.cn/img"), patch.object(pub, "create_draft", return_value="DRAFT") as draft, patch.object(pub, "verify_draft", return_value=[]), patch.object(pub, "read_draft", return_value={}), patch.object(pub, "submit_publish") as submit:
            result = pub.publish_html_article("app", "secret", html, cover, "标题", material_cache=None)
            test("真实入口默认草稿且仅替换正文图", not submit.called and result["media_id"] == "DRAFT" and "https://mmbiz.qpic.cn/img" in draft.call_args.args[2])
        # 正式发布单次授权：config 不能持久授权；--submit 之外还须逐字确认标题；缺确认 0 网络。
        with open(os.path.join(d, "cfg_submit.json"), "w", encoding="utf-8") as f:
            json.dump({"appid": "wx", "secret": "s", "submit": True}, f)
        try:
            pub.load_config(os.path.join(d, "cfg_submit.json"))
            test("config 持久授权发布被拒绝", False)
        except ValueError as e:
            test("config 持久授权发布被拒绝", "单次" in str(e) or "submit" in str(e))
        with patch.object(pub, "get_stable_access_token") as token:
            try:
                pub.publish_html_article("app", "secret", html, cover, "标题", material_cache=None, do_submit=True)
                test("正式发布缺单次确认被拦（0 网络）", False)
            except ValueError as e:
                test("正式发布缺单次确认被拦（0 网络）", token.call_count == 0 and "确认" in str(e))
            try:
                pub.publish_html_article("app", "secret", html, cover, "标题", material_cache=None,
                                         do_submit=True, submit_confirm="别的标题")
                test("确认标题不符被拦", False)
            except ValueError:
                test("确认标题不符被拦", token.call_count == 0)
        with patch.object(pub, "get_stable_access_token", return_value="tok"), patch.object(pub, "upload_thumb_material", return_value="THUMB"), patch.object(pub, "upload_content_image", return_value="https://mmbiz.qpic.cn/img"), patch.object(pub, "create_draft", return_value="DRAFT"), patch.object(pub, "verify_draft", return_value=[]), patch.object(pub, "read_draft", return_value={}), patch.object(pub, "submit_publish", return_value="PID") as submit, patch.object(pub, "poll_publish_status", return_value={"status": 0, "status_text": "ok", "article_urls": []}):
            pub.publish_html_article("app", "secret", html, cover, "标题", material_cache=None,
                                     do_submit=True, submit_confirm="标题")
            test("单次确认后才走到发布", submit.called)
        with patch.object(pub, "_post_json", return_value={"publish_status":1}) as post, patch.object(pub.time, "sleep") as sleep:
            result = pub.poll_publish_status("tok", "PID", timeout=0)
            test("单次查询不额外睡眠或轮询", result["status"] == 1 and post.call_count == 1 and not sleep.called)
    # 原 eval/ 语料已删。这两条曾经锁「具体案例的事实边界」，现在改锁同一批规则本身：
    # 用合成负例验证——链接存在不等于内容核真，机器只拦可确定的错。
    meta, blocks = _r.parse(HEAD + '---\n正文一段。\n\n![AI 生成示意](images/fig.jpg "证据")\n\n'
                                   '::: note 来源\nhttps://example.com/synthetic-data\n:::\n')
    test("生成示意图不能担任证据职责", any("生成示意" in e for e in _r.compose_gate(meta, blocks, FIX)[0]))
    meta, blocks = _r.parse(HEAD + '---\n正文一段。\n\n![母线排布](images/fig.jpg "证据")\n')
    test("证据图缺可核对来源被拦", any("缺少可核对来源" in e for e in _r.compose_gate(meta, blocks, FIX)[0]))
    test("合成语料自带可见声明，不冒充事实",
         all(re.search(r"合成|演示|虚构", spec["md"]) for spec in _fx.CORPUS.values()))
    for label, ok in results:
        print(f"   {'PASS' if ok else 'FAIL'} · {label}")
    return all(ok for _, ok in results), "；".join(label for label, ok in results if not ok)



class DeliveryTests(unittest.TestCase):
    def test_composition_and_lossy_lists(self):
        pair = ('# 测试标题\n\n![甲对象](images/fig.jpg "对比 comparison")\n'
                '![乙对象](images/fig.jpg "对比 comparison")\n')
        _, meta, blocks, html = _r.render(pair)
        self.assertEqual(html.count('<td style="width:50%'), 2)
        self.assertLess(html.index('甲对象'), html.index('乙对象'))
        self.assertFalse(_r.check(html)[0])
        must, _ = _r.compose_gate(meta, blocks, FIX)
        self.assertFalse(must, must)
        _, meta, blocks, _ = _r.render(pair + '![丙](images/fig.jpg "对比 comparison")\n')
        self.assertTrue(any('恰好两张' in x for x in _r.compose_gate(meta, blocks, FIX)[0]))
        seq = pair.replace('comparison', 'sequence')
        html = _r.render(seq)[3]
        self.assertLess(html.index('顺序 1'), html.index('顺序 2'))
        self.assertIn('甲对象', html)
        for bad in ('- 一\n  - 二\n', '1. 一\n3. 三\n', '- 一\n1. 二\n', '- 一\n  续行\n'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                _r.parse(bad)

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        _fx.build(str(self.root))
        self.md = self.root / 'v2.md'
        self.md.write_text('---\ntitle: 测试\ncover: images/cover.jpg\ncomposition: explainer\n---\n正文。\n\n![说明](images/fig.jpg "解释 inset")\n', encoding='utf-8')
        self.html = self.root / 'delivery' / 'body.html'
        run = subprocess.run([sys.executable, str(Path(SCRIPTS)/'render.py'), str(self.md), '-o', str(self.html)], capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr + run.stdout)
        self.side = json.loads(self.html.with_suffix('.meta.json').read_text())
        self.settings = dict(title=self.side['api_title'], author=None, digest=self.side['digest'], source=None, cover=publish.resolve_cover(self.side['cover'], str(self.html)), open_comment=True, fans_only=False, submit=False)

    def flight(self):
        with contextlib.redirect_stdout(io.StringIO()):
            return publish.preflight(str(self.html), self.settings)

    def test_docx_complex_table_refused_before_output(self):
        import zipfile
        base = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{}</w:body></w:document>'
        cells = ('<w:tbl><w:tr><w:tc><w:p/><w:p/></w:tc></w:tr></w:tbl>',
                 '<w:tbl><w:tr><w:tc><w:p/></w:tc></w:tr><w:tr><w:tc><w:p/></w:tc><w:tc><w:p/></w:tc></w:tr></w:tbl>',
                 '<w:tbl><w:tr><w:tc><w:p><w:r><w:br/></w:r></w:p></w:tc></w:tr></w:tbl>')
        for n, table in enumerate(cells):
            src, out = self.root / f'complex{n}.docx', self.root / f'complex{n}.md'
            with zipfile.ZipFile(src, 'w') as z:
                z.writestr('word/document.xml', base.format(table))
            result = subprocess.run([sys.executable, str(Path(SCRIPTS)/'extract_docx.py'), str(src), '-o', str(out)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0, result.stdout)
            self.assertFalse(out.exists())
            self.assertIn('正文块', result.stderr)

    def test_integrity(self):
        self.assertEqual(self.flight(), 0)
        for file in [self.md, self.html, self.html.parent/'images/cover.jpg', self.html.parent/'images/fig.jpg', self.root/'images/fig.jpg', self.root/'images/cover.jpg']:
            old = file.read_bytes()
            file.write_bytes(old + b'x')
            self.assertEqual(self.flight(), 1, str(file))
            file.write_bytes(old)
        side_path = self.html.with_suffix('.meta.json')
        for key, value in (("skill_version", "0.0.0"), ("theme_config_sha256", "stale")):
            altered = dict(self.side, **{key: value})
            side_path.write_text(json.dumps(altered, ensure_ascii=False), encoding='utf-8')
            self.assertEqual(self.flight(), 1, key)
        side_path.write_text(json.dumps(self.side, ensure_ascii=False), encoding='utf-8')
        self.assertEqual(self.flight(), 0)
        self.assertEqual(self.side['integrity_version'], 2)
        self.assertEqual(self.side['decision']['composition'], 'explainer')

    def test_boundaries(self):
        outside = self.root/'outside.jpg'; outside.write_bytes(b'private')
        link = self.html.parent/'link.jpg'; link.symlink_to(outside)
        for path in ('../outside.jpg', str(outside), 'link.jpg', 'C:/file.jpg', 'https://example.com/x', 'x\\y'):
            with self.assertRaises(ValueError, msg=path): local_path(path, str(self.html.parent))
            with patch.object(publish, 'upload_content_image') as upload:
                with self.assertRaises(ValueError):
                    publish.rewrite_local_images('<img src="'+path+'">', 'token', str(self.html.parent)) if not path.startswith('https:') else local_path(path, str(self.html.parent))
                upload.assert_not_called()

    def test_render_rejects_escaping_cover(self):
        self.md.write_text('---\ntitle: 测试\ncover: ../outside.jpg\n---\n正文。\n', encoding='utf-8')
        output = self.root/'bad.html'
        result = subprocess.run([sys.executable, str(Path(SCRIPTS)/'render.py'), str(self.md), '-o', str(output)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(output.exists())

    def test_readback_blocks_submission(self):
        with contextlib.redirect_stdout(io.StringIO()), \
             patch.object(publish, 'get_stable_access_token', return_value='token'), \
             patch.object(publish, 'upload_thumb_material', return_value='thumb'), \
             patch.object(publish, 'upload_content_image', return_value='https://img.example/test'), \
             patch.object(publish, 'create_draft', return_value='existing-draft'), \
             patch.object(publish, 'read_draft', side_effect=OSError('network')), \
             patch.object(publish, 'submit_publish') as submit:
            with self.assertRaisesRegex(RuntimeError, 'existing-draft'):
                publish.publish_html_article('app', 'secret', str(self.html), self.settings['cover'], self.settings['title'], material_cache=None, do_submit=True, submit_confirm=self.settings['title'])
            submit.assert_not_called()

    def test_readback(self):
        self.assertEqual(publish.verify_draft({'news_item':[{'title':'题','content':'文','thumb_media_id':'x'}]}, '题','文','x'), [])
        self.assertEqual(publish.verify_draft({'news_item':[{'title':'错','content':'文','thumb_media_id':'x'}]}, '题','文','x'), ['title'])
        with self.assertRaises(ValueError): publish.verify_draft({}, '题','文','x')


    def test_editorial_and_input(self):
        import render
        meta, blocks = render.parse('---\ntitle: 标题\n---\n重复段落。\n\n重复段落。\n\n增长20%。')
        review = render.editorial_review(meta, blocks)
        self.assertTrue(any(x['action'] == '合并或删除' for x in review['issues']))
        self.assertTrue(any(x['action'] == '核查数字' for x in review['issues']))
        self.assertEqual(review['fact_verification'], 'not_performed')
        for text in ('#### 深层标题', '正文 ![图](x.jpg)'):
            with self.assertRaises(ValueError): render.parse(text)
        with self.assertRaises(ValueError): render.render('# 标题\n\n|甲|乙|\n|---|---|\n|只有一列|')
        with self.assertRaises(ValueError): render.R(render.THEMES['paper'], 'standard').inline('[危险](javascript:alert)')
        must, _ = render.compose_gate({'title':'标题'}, [('img', ('第一步', 'todo', '解释 sequence'))])
        self.assertTrue(any('相邻同组' in x for x in must))

    def test_plaintext_and_personality(self):
        import render
        signatures = set()
        for key in render.THEMES:
            theme = render.THEMES[key]
            signature = tuple(theme['type'].values()) + (theme['display'], theme['heading'], theme['peak'])
            signatures.add(signature)
            body = render.render(render.SPECIMEN_MD, key)[3]
            self.assertIn(f"font-size:{theme['type']['heading_size']}px", body)
            self.assertFalse(render.check(body)[0])
        self.assertEqual(len(signatures), 6)
        txt = self.root/'source.txt'
        txt.write_text('# 纯文本测试\n\n正文和English 2026。', encoding='utf-8')
        result = subprocess.run([sys.executable, str(Path(SCRIPTS)/'render.py'), str(txt)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('正文和English 2026。', (self.root/'source_paper.html').read_text())
        pdf = self.root/'wrong.pdf'; pdf.write_text('not a PDF')
        result = subprocess.run([sys.executable, str(Path(SCRIPTS)/'render.py'), str(pdf)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('仅支持', result.stderr)

    def test_docx_link_and_loss(self):
        import extract_docx, zipfile
        xml = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><w:body><w:p><w:hyperlink r:id="r1"><w:r><w:t>原文</w:t></w:r></w:hyperlink></w:p></w:body></w:document>'
        rels = '<Relationships><Relationship Id="r1" Type="x/hyperlink" Target="https://example.org/report" TargetMode="External"/></Relationships>'
        src, out = self.root/'links.docx', self.root/'links.md'
        with zipfile.ZipFile(src, 'w') as z:
            z.writestr('word/document.xml', xml)
            z.writestr('word/_rels/document.xml.rels', rels)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(extract_docx.extract(src, out), 0)
        self.assertIn('[原文](https://example.org/report)', out.read_text())
        out.unlink()
        with zipfile.ZipFile(src, 'w') as z:
            z.writestr('word/document.xml', xml.replace('<w:p>', '<w:p><w:txbxContent/>'))
            z.writestr('word/_rels/document.xml.rels', rels)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(extract_docx.extract(src, out), 1)
        self.assertFalse(out.exists())


def run_all(a):
    """跑完全部回归，返回失败项。语料目录 FIX 由 main() 生成并回收。"""
    fails = []

    print("① 用例回归（Gate 1/2 必须全过）")
    for c in CASES:
        ok, log = case_ok(c)
        print(f"   {'PASS' if ok else 'FAIL'} · {c}")
        if not ok:
            fails.append(c)
            print("   " + log.strip().replace("\n", "\n   "))

    print("② 结构基准（5 篇合成稿的机器可验证快照）")
    ok, why = baseline_ok()
    print(f"   {'PASS' if ok else 'FAIL'} · {why}")
    if not ok:
        fails.append("质量基准")

    # themes.json 是所有人格共用的唯一来源：一个键写坏，选到它的人就整篇渲染不出来。
    print("③ 人格系统（themes.json）：可渲染 · 不重复 · 键完整")
    sys.path.insert(0, SCRIPTS)
    import render as _r
    for key in _r.THEMES:
        try:
            _r.render(_r.SPECIMEN_MD, key)
            print(f"   可渲染 · {key}（{_r.THEMES[key]['name']}）")
        except Exception as e:  # noqa: BLE001 —— 回归要报告任何一种崩
            fails.append(f"主题 {key}")
            print(f"   FAIL · {key} → {type(e).__name__}: {e}")

    theme_bad = theme_audit()
    if theme_bad:
        fails.extend(theme_bad)
        for m in theme_bad:
            print(f"   FAIL · {m}")
    else:
        print(f"   独立结构轴 · {len(_r.THEMES)} 套人格在导语/标题/引文/信息/图片/节奏键上完整且不重复")
    ok, why = specimen_ok()
    print(f"   {'PASS' if ok else 'FAIL'} · {why}")
    if not ok:
        fails.append("主题配置/渲染器/展示板一致性")

    print("④ 护栏回归（负例必须仍被拦住）")
    for label, fm, body, kw, level in GUARDS:
        hit, log = guard_ok(label, fm, body, kw, level)
        print(f"   {'PASS' if hit else 'FAIL'} · {label}（{level} → {kw}）")
        if not hit:
            fails.append(label)
            print("   " + log.strip().replace("\n", "\n   "))

    print("⑤ 原语渲染（渲染出来是不是我以为的样子）")
    for label, fm, md, must_have, must_not in RENDER_CHECKS:
        ok, log, missing, leaked = render_check_ok(fm, md, must_have, must_not)
        print(f"   {'PASS' if ok else 'FAIL'} · {label}")
        if not ok:
            fails.append(label)
            print(f"   缺 {missing} · 泄漏 {leaked}\n   " + log.strip().replace("\n", "\n   "))

    ok, why = toc_after_first_para_ok()
    print(f"   {'PASS' if ok else 'FAIL'} · 目录不占首屏（toc 排在第一段之后）")
    if not ok:
        fails.append("目录位置")
        print(f"   {why}")

    print("⑥ Word 抽取回归（三条输入路径之一，此前零覆盖）")
    ok, why = docx_ok()
    print(f"   {'PASS' if ok else 'FAIL'} · docx → Markdown（标题/加粗/两种列表/图片/表格）")
    if not ok:
        fails.append("docx 抽取")
        print(f"   {why}")

    print("⑦ 平台原生字段（正文不重印标题/作者 · 预览模拟原生栏 · meta 上限）")
    ok, why = platform_fields_ok()
    print(f"   {'PASS' if ok else 'FAIL'} · {why}")
    if not ok:
        fails.append("平台原生字段")

    print("⑧ draft/add payload（超限拒绝 · 留言默认 · 原文链接）")
    ok, why = draft_payload_ok()
    print(f"   {'PASS' if ok else 'FAIL'} · {why}")
    if not ok:
        fails.append("draft payload")

    print("⑨ 永久素材管理（封面复用 · 验活 · 删除重传 · 总数 · 翻页 · 删除）")
    ok, why = material_ok()
    print(f"   {'PASS' if ok else 'FAIL'} · {why}")
    if not ok:
        fails.append("素材管理")

    print("⑩ config.json 默认与优先级（命令行 > meta > config）")
    import publish as _p
    ns = argparse.Namespace(appid=None, secret=None, title=None, cover=None, author=None, digest=None,
                            source_url=None, no_open_comment=False, fans_only_comment=False, submit=False)
    cfg = {"appid": "wx_cfg", "secret": "s_cfg", "author": "配置作者", "source_url": "https://cfg",
           "need_open_comment": False, "submit": True}
    s = _p.resolve_settings(ns, {"author": "meta作者", "digest": "meta摘要"}, cfg)
    s2 = _p.resolve_settings(
        argparse.Namespace(**{**vars(ns), "author": "CLI作者", "appid": "wx_cli"}), {}, cfg)
    s3 = _p.resolve_settings(ns, {}, {"appid": "", "author": ""})
    with tempfile.TemporaryDirectory() as td:
        with open(os.path.join(td, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"appid": "wx_tmp"}, f)
        cwd0 = os.getcwd()
        os.chdir(td)
        found = _p.load_config()
        os.chdir(cwd0)
    try:
        _p.load_config("/nonexistent/config.json")
        missing_raises = False
    except FileNotFoundError:
        missing_raises = True
    for ok, why in [
        (s["appid"] == "wx_cfg" and s["secret"] == "s_cfg", "凭证默认来自 config"),
        (s["author"] == "meta作者" and s["digest"] == "meta摘要", "meta > config"),
        (s["source"] == "https://cfg", "原文链接回落到 config"),
        (s["open_comment"] is False and s["submit"] is False, "留言开关跟随 config；submit 只来自本次命令行"),
        (s2["author"] == "CLI作者" and s2["appid"] == "wx_cli", "命令行 > meta/config"),
        (s3["appid"] is None and s3["author"] is None, "空字符串视同未配置"),
        (found.get("appid") == "wx_tmp", "默认查找命中 ./config.json"),
        (missing_raises, "显式路径不存在时报错"),
    ]:
        print(f"   {'PASS' if ok else 'FAIL'} · {why}")
        if not ok:
            fails.append(f"config: {why}")

    print("⑪ 发布预检（不联网：Gate 1 · 原生字段 · 封面路径解析 · 待传图片）")
    ok, why = preflight_ok()
    print(f"   {'PASS' if ok else 'FAIL'} · {why}")
    if not ok:
        fails.append("发布预检")

    print("⑫ 真实缺陷回归（数值/路径/剪贴板边界/上传/坏稿0网络）")
    ok, why = delivery_defects_ok()
    if not ok:
        fails.append("真实缺陷：" + why)

    print("⑬ 真实来源编辑评估（五类型 · 修改台账 · A/B · 重复任务）")
    code, log = run([os.path.join(HERE, "editorial_eval.py"), "--check-report",
                     os.path.join(ROOT, "evaluation", "RESULTS.md")], ROOT)
    print("   " + log.strip().replace("\n", "\n   "))
    if code:
        fails.append("真实来源编辑评估")

    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(DeliveryTests))
    if not result.wasSuccessful():
        fails.append("交付完整性与输入回归")
    if a.shots:
        shot_ok = shots(a.shoot)
        if not shot_ok:
            fails.append("Gate 3 截图")

    return fails


def main():
    """语料与素材不入库：每次在临时目录现生成（tests/fixtures.py），跑完整体回收。"""
    global FIX
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", action="store_true")
    ap.add_argument("--shoot", nargs="*", default=None, metavar="文章.md",
                    help="把指定稿件一并截进证据包（如 evals 样稿），供人工审阅与缺陷复现")
    a = ap.parse_args()
    FIX = _fx.build(tempfile.mkdtemp(prefix="wechat-selftest-"))
    try:
        fails = run_all(a)
    finally:
        shutil.rmtree(FIX, ignore_errors=True)
    print("\n回归：" + ("全部通过" if not fails else f"{len(fails)} 项失败 → {fails}"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
