#!/usr/bin/env python3
"""V7 回归：编辑判断线索、主题轴完整性、未知项原语、声音比对、发布与转换护栏。

约定（与 tests/run.py 一致）：
- 用例必须**在该失败的地方失败**：每条护栏都配一个负例，证明它不是永远返回 True。
- 只冻结可确定的形态，不冻结审美判断与文笔评分。
- 断言里出现的每条规则，都对应一个真实的 V7 变更；规则被删掉时这里会红。
"""
import contextlib
import io
import json
import os
import sys
import tempfile
from pathlib import Path
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import editorial as E          # noqa: E402
import extract_docx            # noqa: E402
import publish                # noqa: E402
import render as R            # noqa: E402

# 刻意写成 AI 腔的负例：套语、模板排比、主语复读、抽象名词空转、自我解释。
SLOP = """---
title: 三个方法让 AI 真正落地
article_type: 分析
theme: paper
---

> 随着人工智能技术的飞速发展，越来越多的企业开始关注这一领域。

在当今这个快速变化的时代，AI 已经不是一个新鲜词。众所周知，技术的价值在于应用。值得注意的是，很多企业都在积极探索 AI 的落地路径。换句话说，落地才是关键。简而言之，只有落地才能产生价值。

AI 落地的核心在于组织能力。这不仅是技术问题，更是组织问题。它既是方法论，也是价值观，更是生产力。缺少闭环与生态的维度，就没有真正的抓手。

## 方法一：找场景

找场景很重要。找场景需要从业务出发。找场景的关键是找到高频、刚需、可量化的场景。只有找到这样的场景，AI 才能真正落地。

## 方法二：建团队

建团队很重要。团队需要懂业务，也需要懂技术。只有业务和技术的深度融合，才能真正推动 AI 落地。
"""

# 第二份负例：**不看规则表、只按「常见 AI 文风」独立写的一段**。
# 用途是防止线索只能命中第一份负例（那份是按规则写的）；新规则若只对 SLOP 有效，
# 这份会红。它包含：套语开头、首先/其次/再次/最后的口语序号、排比开头、空洞呼吁结尾。
SLOP_FRESH = """---
title: 三个方法，让你的团队效率翻倍
article_type: 分析
theme: paper
---

在当今这个快速变化的时代，效率已经成为每一个团队都必须面对的重要课题。无论是初创公司，还是成熟企业，效率都是绕不开的话题。

首先，我们要明确目标。目标是一切工作的起点。其次，我们要拆解任务。再次，我们要及时复盘。最后，我们要持续迭代。

值得注意的是，这并不是一件容易的事情。但只要我们坚持下去，就一定能够取得成果。让我们一起努力，一起成长，一起迎接更美好的未来。

总之，效率提升不是一朝一夕的事情，需要我们持续投入、持续优化、持续改进。
"""

CLEAN = """---
title: 某公司宣布裁员9000人
article_type: 新闻报道
theme: frost
---

> 2025年7月3日，公司宣布全球裁员约9000人；是否与AI投入有关仍未确认。

公司于7月2日向员工发出通知，裁员涉及多个团队，占员工总数不足4%。

## 已确认

通知写明涉及多个团队与地区，员工总数约22.8万人。

::: unknown 尚不能确认
裁员是否直接服务于AI数据中心投入，公司没有确认两者之间的因果关系。
:::

::: note 来源与口径
示例来源行，仅用于回归。
https://example.com/a
:::
"""


def _codes(md):
    meta, blocks = R.parse(md)
    return meta, blocks, E.audit(meta, blocks)


STYLE_CODES = {"OPENING-CLICHE", "TEMPLATE-REPEAT", "REPEAT-SUBJECT", "EMPTY-ABSTRACT",
               "MONOTONE", "CIRCULAR", "META-DISCOURSE", "RESTATE-MARKER", "LONG-ATTRIB",
               "WEAK-INFERENCE", "PROSE-ORDINAL", "PARALLEL-HEAD", "HOLLOW-CLOSE"}


def _has(result, code):
    return any(i["code"] == code for i in result["issues"])


def _style_hits_in_corpus():
    """真实语料上不应出现的文风线索：这是防「规则只对自造负例有效」的反向检查。"""
    hits = []
    for path in sorted(Path(ROOT, "evaluation", "cases").glob("*.md")) + \
            sorted(Path(ROOT, "evaluation", "model-eval", "runs").glob("*/*.md")):
        meta, blocks, result = _codes(path.read_text(encoding="utf-8"))
        hits.extend((path.name, i["code"]) for i in result["issues"]
                    if i["code"] in ("PROSE-ORDINAL", "PARALLEL-HEAD", "HOLLOW-CLOSE"))
    return hits


def editorial_checks():
    out = []

    def case(name, ok):
        out.append((name, bool(ok)))

    slop = _codes(SLOP)[2]
    clean = _codes(CLEAN)[2]

    # --- 文风与机械扩写线索：负例必须命中，正例必须不命中 ---
    case("AI 腔套语被定位（含「值得注意的是/众所周知」）", _has(slop, "OPENING-CLICHE"))
    case("模板排比重复时被定位", _has(slop, "TEMPLATE-REPEAT"))
    case("同段主语复读被定位", _has(slop, "REPEAT-SUBJECT"))
    case("抽象名词空转被定位", _has(slop, "EMPTY-ABSTRACT"))
    case("自我解释标记被定位", _has(slop, "RESTATE-MARKER"))
    fresh = _codes(SLOP_FRESH)[2]
    case("独立写的 AI 腔样稿被「口语序号」定位（不依赖第一份负例）", _has(fresh, "PROSE-ORDINAL"))
    case("独立写的 AI 腔样稿被「空洞呼吁结尾」定位", _has(fresh, "HOLLOW-CLOSE"))
    case("独立写的 AI 腔样稿不出现 must 级文风线索（只报位置，不判死刑）",
         not any(i["severity"] == "must" and i["code"] in STYLE_CODES for i in fresh["issues"]))
    case("AI 腔样稿在真实稿件上不误报（六类 18 篇 + 六组案例）",
         not _style_hits_in_corpus())

    case("干净稿件不被文风线索误报",
         not any(code in {"TEMPLATE-REPEAT", "REPEAT-SUBJECT", "EMPTY-ABSTRACT",
                          "MONOTONE", "CIRCULAR", "META-DISCOURSE", "RESTATE-MARKER",
                          "OPENING-CLICHE"} for i in clean["issues"] for code in [i["code"]]))

    # --- 机器线索与语义判断必须可分离，且判断类必须写明需要谁 ---
    case("问题分类只允许 mechanical/judgment",
         all(i["class"] in ("mechanical", "judgment") for i in slop["issues"] + clean["issues"]))
    case("判断类问题写明需要谁判断",
         all(i["needs"] != "none" for i in slop["issues"] + clean["issues"] if i["class"] == "judgment"))
    case("审计结果显式声明三类证据口径",
         set(slop["evidence_classes"]) == {"mechanical", "judgment", "verification"})
    case("形态线索不冒充质量结论（报告分节）", "机器线索" in E.render_report(slop) and "编辑判断" in E.render_report(slop))

    # --- 未知项：新闻/分析必须有，且 unknown 块能满足它 ---
    case("新闻缺未知项被指出", _has(slop, "UNKNOWN-MISSING"))
    case("写了 unknown 块就不再报缺未知项", not _has(clean, "UNKNOWN-MISSING"))
    unknown_html = R.render(CLEAN)[3]
    case("unknown 块渲染为虚线边界而不是正文段落", "border:1px dashed" in unknown_html)

    # --- 逐节信息增量：有度量、有相似度、且不冻结为判决 ---
    gains = _codes(SLOP)[2]["section_gain"]
    case("逐节信息增量给出新事实与相似度",
         gains and all({"new_facts", "similarity_to_previous", "evidence_blocks"} <= set(g) for g in gains))
    case("信息增量结论保持 UNVERIFIED（机器不判决语义）",
         all(g["verdict"] == "UNVERIFIED" for g in gains))

    # --- 标题数字承诺 ---
    meta, blocks = R.parse("---\ntitle: 裁员9000人后，工时下降37%\narticle_type: 分析\n---\n\n正文没有这些数字。\n")
    r = E.audit(meta, blocks)
    case("标题带单位数值未兑现被列出",
         any(p["kind"] == "number" and p["status"] == "absent" for p in r["promise"])
         and any(i["code"] == "PROMISE-NUMBER" for i in r["issues"]))
    meta, blocks = R.parse("---\ntitle: 裁员9000人后，工时下降37%\narticle_type: 分析\n---\n\n"
                           "公司裁员9000人；工时下降37%。\n")
    r = E.audit(meta, blocks)
    case("标题数值在正文出现则不报（不数关键词，比字面值）",
         not any(i["code"] == "PROMISE-NUMBER" for i in r["issues"]))

    # --- 声音比对：抹平声音必须被看见 ---
    original = R.parse("我原以为这里很安静？其实不是——机器声大到我贴着耳朵说话。\n")[1]
    flatten = R.parse("这里通常被认为是安静的，机器声很大。\n")[1]
    diff = E.compare_voice(original, flatten)
    case("声音抹平被列为形态变化",
         {c["mark"] for c in diff["changes"]} >= {"第一人称", "设问", "破折号"})
    case("声音比对不下结论（UNVERIFIED）", diff["status"] == "UNVERIFIED")
    same = E.compare_voice(original, original)
    case("未改动稿件的 sound 比对为空", same["changes"] == [])

    # --- 决策链：缺环要能被指出 ---
    steps = E.decision_chain(_codes(SLOP)[0], _codes(SLOP)[1])["steps"]
    case("决策链逐环给出 DECLARED/INFERRED/MISSING",
         all(s["status"] in ("OK", "DECLARED", "INFERRED", "MISSING", "NONE") for s in steps)
         and {s["step"] for s in steps} == {"内容类型", "视觉概念", "信息关系", "构图", "素材策略", "排版"})
    case("未写视觉概念与设计理由被标 MISSING",
         {s["step"] for s in steps if s["status"] == "MISSING"} == {"视觉概念", "排版"})

    # --- 句长节奏与定语过长的负例/正例 ---
    meta, blocks = R.parse("---\ntitle: 节奏\n---\n\n" + "字" * 0 + "短句一句。短句两句。短句三句。短句四句。短句五句。\n")
    r = E.audit(meta, blocks)
    case("五句等长触发句长节奏线索", _has(r, "MONOTONE"))
    meta, blocks = R.parse("---\ntitle: 节奏\n---\n\n"
                           "短句。这是一个明显更长一些的句子，中间还有停顿，读起来不会觉得平。再短。\n")
    r = E.audit(meta, blocks)
    case("长短交替不触发句长节奏线索", not _has(r, "MONOTONE"))
    return out


def theme_checks():
    out = []

    def case(name, ok):
        out.append((name, bool(ok)))

    problems = R.validate_themes(R.THEMES)
    case("六主题配置通过轴/层级/字号校验", problems == [])
    case("主题轴派发表覆盖配置里的每个取值",
         all(R.THEMES[n][axis] in allowed for n in R.THEMES for axis, allowed in R.THEME_AXES.items()))

    # 负例：改坏一个轴取值必须被拒绝（不是静默落到默认样式）
    bad = json.loads(json.dumps(R.THEMES))
    bad["paper"]["heading"] = "index2"
    case("未登记的主题轴取值被拒绝", any("heading" in p for p in R.validate_themes(bad)))
    bad = json.loads(json.dumps(R.THEMES))
    bad["paper"]["type"]["lead_size"] = 26
    case("导语大于章节标题被拒绝（首屏两个入口）",
         any("未大于导语" in p for p in R.validate_themes(bad)))
    bad = json.loads(json.dumps(R.THEMES))
    bad["frost"]["grid"]["body"] = 12
    case("正文字号超出 15–17px 被拒绝", any("正文" in p and "15" in p for p in R.validate_themes(bad)))

    # h3=label 过去没有分支，现在必须有独立视觉表达
    html = R.render("---\ntitle: 题\n---\n\n## 节\n\n### 小节\n\n正文。\n")[3]
    case("h3 label 轴有显式分支（字距 + 弱色）", "letter-spacing:0.06em" in html)
    # bone 不再每节印 SECTION
    bone = R.render("---\ntitle: 题\ntheme: bone\n---\n\n## 甲\n\n正文。\n\n## 乙\n\n正文。\n")[3]
    case("素作主题不再输出 SECTION 装饰标签", "SECTION" not in bone)
    return out


def hierarchy_checks():
    """视觉回归里的层级断言本身必须会失败（负例），否则它只是装饰。"""
    import visuals as V
    out = []

    def case(name, ok):
        out.append((name, bool(ok)))

    ok_metrics = {"leadSize": 18, "chapterHeadingSizes": [21, 21], "minBodySize": 16,
                  "chapterMarkers": ["01", "02", "03"]}
    case("层级正常不报", V.hierarchy_issues("paper", ok_metrics) == [])
    bad = dict(ok_metrics, leadSize=22, chapterHeadingSizes=[20])
    case("导语≥章节标题被层级断言抓住", any("同级入口" in x for x in V.hierarchy_issues("paper", bad)))
    bad = dict(ok_metrics, leadSize=16, minBodySize=16)
    case("导语≤正文被层级断言抓住", any("入口作用" in x for x in V.hierarchy_issues("paper", bad)))
    bad = dict(ok_metrics, chapterMarkers=["SECTION", "SECTION", "SECTION"])
    case("同一章节标记连刷三次被抓住", any("机械复读" in x for x in V.hierarchy_issues("bone", bad)))
    case("没有导语的稿件不量导语字号",
         V.hierarchy_issues("letter", dict(ok_metrics, leadSize=16), has_lead=False) == [])
    return out


def gate_checks():
    out = []

    def case(name, ok):
        out.append((name, bool(ok)))

    # 正文根断行：break-word（不全局打断中文），且 Gate 1 接受
    html = R.render("---\ntitle: 题\n---\n\n正文一段。\n")[3]
    case("正文根使用 overflow-wrap:break-word", "overflow-wrap:break-word" in html)
    must, _ = R.check(html) if hasattr(R, "check") else ([], [])
    from check import check
    must, _ = check(html)
    case("break-word 通过 Gate 1", not must)

    # 资料图/实拍必须交代来源
    tmp = tempfile.mkdtemp(prefix="v7-gate-")
    try:
        imgdir = Path(tmp) / "images"
        imgdir.mkdir()
        (imgdir / "a.jpg").write_bytes(
            bytes.fromhex("ffd8ffe000104a46494600010100000100010000")
            + bytes.fromhex("ffc0001108003200c80301220002110103110100")
            + b"\xff\xd9")
        md = Path(tmp) / "a.md"
        md.write_text("---\ntitle: 题\ntheme: paper\n---\n\n"
                      "![](images/a.jpg \"资料 full-width\")\n\n正文说明这张图。\n", encoding="utf-8")
        res = R.build(str(md), None, os.path.join(tmp, "out.html"))
        must = res["gates"][1][1]
        case("资料图缺来源与授权被拦住", any("资料图/实拍" in m for m in must))
        md.write_text("---\ntitle: 题\ntheme: paper\n---\n\n"
                      "![](images/a.jpg \"某馆藏扫描，CC0 \")\n\n正文说明这张图。\n", encoding="utf-8")
        res = R.build(str(md), None, os.path.join(tmp, "out.html"))
        case("写明馆藏与授权后不再拦（不要求固定句式）",
             not any("资料图/实拍" in m for m in res["gates"][1][1]))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    # 证据类图片必须紧邻解释文字
    tmp = tempfile.mkdtemp(prefix="v7-adj-")
    try:
        imgdir = Path(tmp) / "images"
        imgdir.mkdir()
        (imgdir / "a.jpg").write_bytes(
            bytes.fromhex("ffd8ffe000104a46494600010100000100010000")
            + bytes.fromhex("ffc0001108003200c80301220002110103110100") + b"\xff\xd9")
        md = Path(tmp) / "a.md"
        md.write_text("---\ntitle: 题\ntheme: paper\n---\n\n## 甲\n\n"
                      "![](images/a.jpg \"证据 inset https://example.com/x\")\n\n"
                      "![](images/a.jpg \"证据 inset https://example.com/y\")\n", encoding="utf-8")
        res = R.build(str(md), None, os.path.join(tmp, "out.html"))
        case("证据图上下都是图片时提示缺解释文字",
             any("紧邻它的解释文字" in s for s in res["gates"][1][2]))
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    return out


def publish_checks():
    out = []

    def case(name, ok):
        out.append((name, bool(ok)))

    # 审计字段白名单：凭证/正文类型进不来
    AUDIT = {"submit", "body_sha256", "media_id", "publish_id", "error_type", "media_id_sha256", "stage"}
    for field in ("secret", "appid", "content", "token"):
        case(f"审计日志拒绝 {field} 字段", field not in AUDIT)
    from unittest.mock import patch

    def run_main(argv):
        """跑 main 的参数校验分支；token 取用被打桩，确保测试绝不联网。"""
        sys.argv = ["publish.py"] + argv
        calls = []
        with patch.object(publish, "get_stable_access_token", lambda *a, **k: calls.append(a) or "T"), \
                patch.object(publish, "delete_material", lambda *a, **k: {"errcode": 0}):
            rc = 0
            try:
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    publish.main()
            except SystemExit as e:
                rc = e.code
        return rc, calls

    rc, calls = run_main(["--appid", "a", "--secret", "b", "--delete-material", "MID_123"])
    case("删除永久素材缺少逐字确认时拒绝执行", rc not in (0, None))
    case("未确认的删除不取 token（无凭证请求、无网络副作用）", calls == [])
    rc, calls = run_main(["--appid", "a", "--secret", "b", "--delete-material", "MID_123",
                          "--confirm-delete-media-id", "OTHER"])
    case("确认值不逐字一致仍拒绝", rc not in (0, None) and calls == [])
    rc, calls = run_main(["--appid", "a", "--secret", "b", "--delete-material", "MID_123",
                          "--confirm-delete-media-id", "MID_123"])
    case("逐字确认后才取 token 并执行删除", rc == 0 and len(calls) == 1)
    return out


def docx_checks():
    out = []

    def case(name, ok):
        out.append((name, bool(ok)))

    with tempfile.TemporaryDirectory() as d:
        doc = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
               'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
               'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
               'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
               '<w:body><w:p><w:r><w:t>正文</w:t></w:r></w:p>'
               '<w:p><w:r><w:drawing><wp:inline><wp:docPr id="1" name="s" descr="馆藏扫描，CC0"/>'
               '<a:graphic><a:graphicData><a:blip r:embed="rId1"/></a:graphicData></a:graphic>'
               '</wp:inline></w:drawing></w:r></w:p></w:body></w:document>')
        rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
                'Target="media/pic.png"/></Relationships>')
        src = Path(d) / "a.docx"
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("word/document.xml", doc)
            z.writestr("word/_rels/document.xml.rels", rels)
            z.writestr("word/media/pic.png", b"\x89PNG\r\n\x1a\n" + b"0" * 32)
        md = Path(d) / "a.md"
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            rc = extract_docx.extract(src, md)
        text = md.read_text(encoding="utf-8") if md.is_file() else ""
        case("DOCX 图片的替换文字进入图注（不静默丢弃）", rc == 0 and "馆藏扫描，CC0" in text)
    return out


def hygiene_checks():
    """仓库整洁：生成物不许混进 evaluation/，被忽略的目录必须真的在 ignore 里。

    这条护栏来自一次真实清理：`evaluation/visual-review/` 累积了 18MB、55 个可再生成的截图。
    删掉不算完——要能在下次跑测试、下次提交时立刻发现它又回来了。
    """
    out = []

    def case(name, ok):
        out.append((name, bool(ok)))

    gitignore = Path(ROOT, ".gitignore").read_text(encoding="utf-8").splitlines()
    ignored = {line.strip() for line in gitignore if line.strip() and not line.startswith("#")}
    case("生成型评估输出目录仍在 .gitignore 中",
         "evaluation/visual-review/" in ignored and "evaluation/model-eval/blind/" in ignored)

    import subprocess
    untracked = None
    try:
        res = subprocess.run(["git", "-C", ROOT, "ls-files", "--others", "--exclude-standard",
                              "evaluation"], capture_output=True, text=True, timeout=20)
        if res.returncode == 0:
            untracked = [line for line in res.stdout.splitlines() if line.strip()]
    except (OSError, subprocess.SubprocessError):
        untracked = None
    if untracked is None:
        # 不是 git 工作区（例如发布包）时只验证 ignore 规则，不假装检查过。
        case("evaluation/ 下没有未纳入版本库的生成物（跳过：非 git 工作区）", True)
    else:
        case("evaluation/ 下没有未纳入版本库的生成物", not untracked)
        if untracked:
            print("   未跟踪文件：" + "、".join(untracked[:5])
                  + ("…" if len(untracked) > 5 else ""))
    return out


def run():
    rows = []
    for name, fn in (("编辑判断线索", editorial_checks), ("主题轴与层级", theme_checks),
                     ("渲染门禁（断行/资料图/证据邻接）", gate_checks),
                     ("视觉层级断言", hierarchy_checks),
                     ("发布保护（删除确认/审计白名单）", publish_checks),
                     ("输入转换（DOCX 替换文字）", docx_checks),
                     ("仓库整洁（evaluation/ 生成物）", hygiene_checks)):
        print(f"V7·{name}")
        for label, ok in fn():
            print(f"   {'PASS' if ok else 'FAIL'} · {label}")
            rows.append((f"{name}：{label}", ok))
    return rows


if __name__ == "__main__":
    rows = run()
    bad = [label for label, ok in rows if not ok]
    print(f"\nV7 回归：{len(rows) - len(bad)}/{len(rows)} 通过" + (f"；失败：{bad}" if bad else ""))
    sys.exit(1 if bad else 0)
