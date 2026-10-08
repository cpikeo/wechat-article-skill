#!/usr/bin/env python3
"""回归：eval/ 用例必须 Gate 1/2 全过；用合成用例守护视觉判断的确定性部分。

    python3 scripts/selftest.py            退出码 1 = 回归失败
    python3 scripts/selftest.py --shots   额外准备真机截图源（需 playwright/Pillow，未装则跳过）

三条铁律：用例必须过；护栏必须仍会在该失败的地方失败；判断一旦确定下来就冻结成测试。
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EVAL = os.path.join(ROOT, "eval")
CASES = ("skills", "letter", "ink", "visual", "atelier",
         "brief", "portrait", "longread")
HEAD = "---\ntitle: 回归用例|固定标题\nkicker: TEST\n"   # 固定内容；不写 date，避免每天产生 diff


def run(args, cwd):
    p = subprocess.run([sys.executable] + args, capture_output=True, text=True, cwd=cwd)
    return p.returncode, p.stdout + p.stderr


def case_ok(name):
    """在 eval/ 原地渲染：相对图片路径必须像真实使用一样解析。"""
    out = os.path.join(tempfile.gettempdir(), f"selftest_{name}.html")
    code, log = run([os.path.join(HERE, "render.py"), f"{name}.md", "-o", out], EVAL)
    return code == 0, log


# 负例：(标签, frontmatter 附加行, 正文, 关键词, 级别)
GUARDS = (
    ("两张图之间没有承接", "", "![甲](todo \"场景\")\n\n短。\n\n![乙](todo \"场景\")\n",
     "两张图片之间缺少文字承接", "should"),
    ("封面写了但文件不存在", "cover: images/not-there.jpg\n", "正文一段。\n",
     "封面文件不存在", "must"),
    ("图片分辨率过低", "", "正文一段。\n\n![小图](fixtures/tiny.png \"证据\")\n",
     "分辨率过低", "must"),
    ("bars 值不是数字", "", "::: bars\n多｜甲\n少｜乙\n:::\n", "bars 的值必须是数字", "must"),
    ("bars 只有一项", "", "::: bars\n10｜甲\n:::\n", "bars 至少 2 项", "must"),
    ("正文图超出预算", "", "正文。\n" + "\n\n".join(
        f"![第{i}张](images/fig-busbar.jpg \"证据\")\n\n这是一段足够长的承接文字，用来把第 {i} 张图与下一张图隔开。" for i in range(1, 5)),
     "正文图 > 本文字数档位的预算", "should"),
    ("todo 图位也要占预算", "", "短文一段，只有一句话。\n\n"
     "![待补一](todo \"锚点\")\n\n一段承接的话，短。\n\n![待补二](todo \"停顿\")\n",
     "正文图 > 本文字数档位的预算", "should"),
    ("首屏压了三层", "deck: 副题也要占位\n", "> 钩子。\n\n![首屏图](todo \"锚点\")\n\n正文第一段才开始。\n",
     "首屏压了", "should"),
    ("图示把正文数字又画一遍", "", "去年是 485，今年 950，几乎翻倍。\n\n"
     "::: bars\n485｜去年\n950｜今年\n:::\n",
     "图示数字与正文重复", "should"),
    ("封面顺手用了正文图", "cover: images/cover.jpg\n", "正文一段。\n\n"
     "![同一张图](images/cover.jpg \"锚点\")\n",
     "封面必须独立做 art direction", "should"),
    ("证据类图片没有说明", "", "正文一段。\n\n![](images/fig-busbar.jpg \"证据\")\n",
     "证据类图必须写清出处", "should"),
    ("短文开了目录", "toc: true\n", "## 甲\n\n一段。\n\n## 乙\n\n二段。\n\n## 丙\n\n三段。\n",
     "短文开了目录", "should"),
    ("density 写错静默降级", "density: campact\n", "正文一段。\n", "density", "should"),
)


def guard_ok(label, fm, body, kw, level):
    """护栏跑在一个临时目录里，软链 eval/images，保证相对路径与真实一致。"""
    with tempfile.TemporaryDirectory() as d:
        for sub in ("images", "fixtures"):
            os.symlink(os.path.join(EVAL, sub), os.path.join(d, sub))
        md = os.path.join(d, "guard.md")
        open(md, "w", encoding="utf-8").write(HEAD + fm + "---\n\n" + body)
        code, log = run([os.path.join(HERE, "render.py"), md, "-o", os.path.join(d, "out.html")], d)
    hit = (code != 0) if level == "must" else (kw in log)
    return hit, log


# 原语渲染断言：(标签, markdown, 必须出现, 必须不出现)
# 覆盖的是「渲染出来是不是我以为的样子」——只跑 Gate 是看不见这类错的。
RENDER_CHECKS = (
    ("data 的全角/半角分隔符都要拆开",
     "::: data\n3｜甲标签\n11|乙标签\n:::\n", ("甲标签", "乙标签"), ("3｜甲标签",)),
)


def render_check_ok(md, must_have, must_not):
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "r.md")
        open(path, "w", encoding="utf-8").write(HEAD + "---\n\n" + md)
        code, log = run([os.path.join(HERE, "render.py"), path, "-o", os.path.join(d, "o.html")], d)
        html = open(os.path.join(d, "o.html"), encoding="utf-8").read()
    missing = [x for x in must_have if x not in html]
    leaked = [x for x in must_not if x in html]
    return not missing and not leaked, log, missing, leaked


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
               "![](images/01-fig1.png)", "| 列A | 列B |", "|---|---|")


def docx_ok():
    """返回 (是否通过, 说明)。真实读一遍产物，不只看退出码。"""
    import zipfile
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "a.docx")
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("word/document.xml", DOC_XML)
            z.writestr("word/styles.xml", STYLES_XML)
            z.writestr("word/_rels/document.xml.rels", RELS_XML)
            z.write(os.path.join(EVAL, "fixtures", "tiny.png"), "word/media/fig1.png")
        out = os.path.join(d, "a.md")
        code, log = run([os.path.join(HERE, "extract_docx.py"), src, "-o", out], d)
        if code != 0 or not os.path.exists(out):
            return False, f"退出码 {code}\n{log}"
        md = open(out, encoding="utf-8").read()
        missing = [x for x in DOCX_EXPECT if x not in md]
        img = os.path.join(d, "images", "01-fig1.png")
        if not os.path.exists(img):
            missing.append("图片未解包到 images/")
        # 反例：不是 docx 的文件必须失败，不能假装成功
        bad = os.path.join(d, "b.docx")
        open(bad, "w").write("不是 zip")
        code2, _ = run([os.path.join(HERE, "extract_docx.py"), bad, "-o", os.path.join(d, "b.md")], d)
        return (not missing and code2 == 1), f"缺 {missing} · 非 docx 退出码 {code2}"


def shots():
    """把每篇预览真正截成 390px PNG —— Gate 3 通读（人眼或视觉模型）的输入。

    只在预览里排一次版是不够的：字距、折行、图片裁切、首屏密度都必须在像素上看见。
    需要 playwright（skill 本身不需要）；未安装则如实跳过，不假装通过。
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("\n跳过截图：未安装 playwright"
              "（pip install playwright && python3 -m playwright install chromium）")
        return True
    out_dir = os.path.join(ROOT, "shots")
    os.makedirs(out_dir, exist_ok=True)
    made, failed = [], []
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 390, "height": 844}, device_scale_factor=2)
        for name in CASES:
            # 就地渲染：预览里的图片是相对路径，换目录会全部裂开
            html = os.path.join(EVAL, f"_shots_{name}.html")
            code, log = run([os.path.join(HERE, "render.py"), f"{name}.md", "-o", html], EVAL)
            if code != 0:
                failed.append(name)
                continue
            prev = os.path.splitext(html)[0] + "_预览.html"
            png = os.path.join(out_dir, f"{name}.png")
            pg.goto("file://" + prev)
            pg.wait_for_timeout(150)
            pg.screenshot(path=png, full_page=True)
            if "<img" in open(prev, encoding="utf-8").read() and not pg.evaluate(
                    "() => [...document.images].every(i => i.naturalWidth > 0)"):
                failed.append(f"{name}（图片未加载）")
            for f in (html, prev):
                os.remove(f)
            made.append(png)
        b.close()
    print(f"\nGate 3 截图（390px · 2x · 含首屏折线）：{out_dir}")
    for m in made:
        print("   " + os.path.basename(m))
    if failed:
        print("   失败：" + "、".join(failed))
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--shots", action="store_true")
    a = ap.parse_args()
    fails = []

    print("① 用例回归（Gate 1/2 必须全过）")
    for c in CASES:
        ok, log = case_ok(c)
        print(f"   {'PASS' if ok else 'FAIL'} · {c}")
        if not ok:
            fails.append(c)
            print("   " + log.strip().replace("\n", "\n   "))

    # themes.json 是所有人格共用的唯一来源：一个键写坏，选到它的人就整篇渲染不出来。
    print("② 六种人格都要能渲染（themes.json 完整性）")
    sys.path.insert(0, HERE)
    import render as _r
    for key in _r.THEMES:
        try:
            _r.render(_r.SPECIMEN_MD, key)
            print(f"   PASS · {key}（{_r.THEMES[key]['name']}）")
        except Exception as e:  # noqa: BLE001 —— 回归要报告任何一种崩
            fails.append(f"主题 {key}")
            print(f"   FAIL · {key} → {type(e).__name__}: {e}")

    print("③ 护栏回归（负例必须仍被拦住）")
    for label, fm, body, kw, level in GUARDS:
        hit, log = guard_ok(label, fm, body, kw, level)
        print(f"   {'PASS' if hit else 'FAIL'} · {label}（{level} → {kw}）")
        if not hit:
            fails.append(label)
            print("   " + log.strip().replace("\n", "\n   "))

    print("④ 原语渲染（渲染出来是不是我以为的样子）")
    for label, md, must_have, must_not in RENDER_CHECKS:
        ok, log, missing, leaked = render_check_ok(md, must_have, must_not)
        print(f"   {'PASS' if ok else 'FAIL'} · {label}")
        if not ok:
            fails.append(label)
            print(f"   缺 {missing} · 泄漏 {leaked}\n   " + log.strip().replace("\n", "\n   "))

    print("⑤ Word 抽取回归（三条输入路径之一，此前零覆盖）")
    ok, why = docx_ok()
    print(f"   {'PASS' if ok else 'FAIL'} · docx → Markdown（标题/加粗/两种列表/图片/表格）")
    if not ok:
        fails.append("docx 抽取")
        print(f"   {why}")

    if a.shots:
        shot_ok = shots()
        if not shot_ok:
            fails.append("Gate 3 截图")

    print("\n回归：" + ("全部通过" if not fails else f"{len(fails)} 项失败 → {fails}"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
