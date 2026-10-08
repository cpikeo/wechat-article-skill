#!/usr/bin/env python3
"""回归：eval/ 用例必须 Gate 1/2 全过；用合成用例守护视觉判断的确定性部分。

    python3 scripts/selftest.py            退出码 1 = 回归失败
    python3 scripts/selftest.py --shots   把每篇预览截成 390px PNG（需 playwright，未装则跳过）

三条铁律：用例必须过；护栏必须仍会在该失败的地方失败；判断一旦确定下来就冻结成测试。
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EVAL = os.path.join(ROOT, "eval")
CASES = ("skills", "portrait", "ink", "visual", "atelier",
         "brief", "longread", "excerpt")
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


# ---- 人格签名：决定一个主题是「编辑语言」还是「换色」----
# 这六个轴直接改变构成（章节标记 / 高潮处理 / 转场 / 引文 / 图片处理 / 字体气质），
# 色值不在其中：只改颜色的新主题不算新人格。
SIGNATURE = ("heading", "peak", "divider", "quote", "image", "display")
COLOR_KEYS = ("text", "sub", "muted", "line", "field", "accent", "dark", "on_dark")


def theme_audit():
    """返回 (错误列表)。人格重复或键缺失都是硬错误：前者是判断退化，后者会静默渲染错。"""
    sys.path.insert(0, HERE)
    import render as _r
    from itertools import combinations
    bad = []
    sig = {}
    for key, t in _r.THEMES.items():
        missing = [k for k in SIGNATURE + COLOR_KEYS + ("name", "leading", "radius") if k not in t]
        if missing:
            bad.append(f"{key} 缺少键 {missing}：新人格必须给全，否则渲染会静默出错")
        sig[key] = tuple(t.get(a) for a in SIGNATURE)
    for a, b in combinations(sorted(sig), 2):
        diff = [x for x, y, z in zip(SIGNATURE, sig[a], sig[b]) if y != z]
        if len(diff) < 2:
            bad.append(f"{a} 与 {b} 只差 {len(diff)} 个编辑语言轴 {diff}："
                       f"只换颜色不算新人格，合并或重新区分")
    return bad


# ---- 同文不同 Decision → 不同 Composition ----
# 判断是否真的改变输出，而不是换了一层皮：把两版 HTML 的色值全部抹掉再比较。
# 若抹掉颜色后仍然不同，说明变的是构成（章节标记 / 高潮处理 / 间距尺度 / 字体气质）。
COMPOSITION_CASE = "skills"
COMPOSITION_LEFT = ("paper", "standard")
COMPOSITION_RIGHT = ("ink", "airy")


# ---- 语料节奏跨度 ----
# 用例若全部把高潮放在结尾，回归就只能证明「一种节奏没坏」。
# 这里冻结语料的节奏多样性：至少要有明显靠前的与靠后的两种。
RHYTHM_SPREAD_MIN = 15          # 百分点


def rhythm_positions():
    """每个用例的高潮位置（%，按块序）。没有 peak 的用例不参与。"""
    sys.path.insert(0, HERE)
    import render as _r
    out = {}
    for name in CASES:
        md = open(os.path.join(EVAL, f"{name}.md"), encoding="utf-8").read()
        try:
            _, _, blocks, _ = _r.render(md)
        except Exception:  # noqa: BLE001
            continue
        kinds = [b[0] for b in blocks]
        if "peak" in kinds:
            out[name] = round(100 * (kinds.index("peak") + 1) / len(kinds))
    return out


# ---- 用例独家覆盖 ----
# eval 不贵（不在常驻 Context 里），但它会不知不觉长大。规则只有一条：
# 每篇用例必须至少独家覆盖一条判断路径；否则它只是别人的重复，应该合并或删除。
# 判据来自「去掉它以后，哪条路径就没人测」——而不是「它看起来写得好不好」。
def coverage():
    """返回 {用例: 独家特征排序列表}；独家为空 = 这篇可以被别人替代。"""
    sys.path.insert(0, HERE)
    import render as _r
    prof = {}
    for name in CASES:
        meta, blocks = _r.parse(open(os.path.join(EVAL, f"{name}.md"), encoding="utf-8").read())
        kinds = [b[0] for b in blocks]
        chars = _r.doc_len(blocks)
        imgs = [b[1] for b in blocks if b[0] == "img"]
        cover = (meta.get("cover") or "").strip()
        f = {
            f"人格:{meta.get('theme')}",
            f"密度:{meta.get('density', 'standard')}",
            "字数档:" + ("≤800" if chars <= 800 else "800-2000" if chars <= 2000 else "≥2000"),
            "封面:" + ("无" if not cover else "待补" if _r.TODO.match(cover) else "真实"),
            "正文图:" + ("无" if not imgs else "待补" if all(
                not b[1][1] or _r.TODO.match(b[1][1]) for b in imgs) else "真实"),
        }
        if meta.get("toc", "").lower() in ("true", "yes", "1") and kinds.count("h2") >= 3:
            f.add("目录")
        if meta.get("deck") and "lead" not in kinds:
            f.add("deck 单独作首屏")
        if "peak" in kinds and 100 * (kinds.index("peak") + 1) / len(kinds) < 70:
            f.add("高潮靠前")
        for k in ("h3", "table", "code", "data", "bars", "note", "hr", "quote"):
            if k in kinds:
                f.add(f"原语:{k}")
        if any(b[0] == "list" and b[1][0] for b in blocks):
            f.add("原语:有序列表")
        if any(b[0] == "list" and not b[1][0] for b in blocks):
            f.add("原语:无序列表")
        prof[name] = f
    return {n: sorted(f - set().union(*[v for m, v in prof.items() if m != n])) for n, f in prof.items()}


def composition_differs(case, left, right):
    """返回 (是否通过, 说明)。"""
    # skills.md：纯文字、无图、有 peak 与 data，最能暴露「换皮不换构成」
    src = open(os.path.join(EVAL, f"{case}.md"), encoding="utf-8").read()
    outs = {}
    for (theme, density), tag in ((left, "L"), (right, "R")):
        md = re.sub(r"(?m)^density:.*$", f"density: {density}", src)
        md = re.sub(r"(?m)^theme:.*$", f"theme: {theme}", md)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "c.md")
            open(path, "w", encoding="utf-8").write(md)
            out = os.path.join(d, "c.html")
            code, log = run([os.path.join(HERE, "render.py"), path, "-o", out], EVAL)
            if code != 0:
                return False, f"{theme}/{density} 渲染失败\n{log}"
            outs[tag] = open(out, encoding="utf-8").read()

    naked = {k: re.sub(r"#[0-9A-Fa-f]{3,8}", "", v) for k, v in outs.items()}
    if naked["L"] == naked["R"]:
        return False, "抹掉颜色后两版完全一致：换的是皮，不是构成"

    # 构成必须真的变了：三个判据都不含颜色——章节标记 / 间距尺度 / 字体气质
    marks = {
        "章节标记": ("border-radius:50%" in naked["R"]) != ("border-radius:50%" in naked["L"]),
        "字体气质": ("Songti" in naked["R"]) != ("Songti" in naked["L"]),
        "间距尺度": (sorted(re.findall(r"margin:\s*(\d+)px", naked["L"])) !=
                     sorted(re.findall(r"margin:\s*(\d+)px", naked["R"]))),
    }
    changed = [k for k, v in marks.items() if v]
    if len(changed) < 2:
        return False, f"只有 {changed} 处构成变化，其余是同一套排版"
    return True, "构成变化：" + "、".join(changed)


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
    print("② 人格系统（themes.json）：可渲染 · 不重复 · 键完整")
    sys.path.insert(0, HERE)
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
        print(f"   不重复 · {len(_r.THEMES)} 个人格两两至少差 2 个编辑语言轴，且键完整")

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

    print("⑤ 同文不同 Decision → 不同 Composition")
    ok, why = composition_differs(COMPOSITION_CASE, COMPOSITION_LEFT, COMPOSITION_RIGHT)
    print(f"   {'PASS' if ok else 'FAIL'} · {COMPOSITION_CASE}："
          f"{COMPOSITION_LEFT[0]}/{COMPOSITION_LEFT[1]} vs {COMPOSITION_RIGHT[0]}/{COMPOSITION_RIGHT[1]}")
    print(f"   {why}")
    if not ok:
        fails.append("composition 差异")

    print("⑥ 语料节奏跨度（回归不能只证明一种节奏）")
    pos = rhythm_positions()
    if len(pos) < 2:
        print(f"   FAIL · 带 peak 的用例不足 2 篇：{pos}")
        fails.append("节奏跨度")
    else:
        spread = max(pos.values()) - min(pos.values())
        line = "、".join(f"{k} {v}%" for k, v in sorted(pos.items(), key=lambda x: x[1]))
        if spread < RHYTHM_SPREAD_MIN:
            fails.append("节奏跨度")
            print(f"   FAIL · 高潮全部落在 {min(pos.values())}–{max(pos.values())}%（跨度 {spread}pp < {RHYTHM_SPREAD_MIN}）："
                  f"用例都是一种节奏\n   {line}")
        else:
            print(f"   PASS · 高潮跨度 {spread}pp\n   {line}")

    print("⑦ 用例独家覆盖（每篇必须至少有一条别人测不到的路径）")
    cov = coverage()
    thin = [n for n, u in cov.items() if not u]
    for n, u in cov.items():
        print(f"   {'PASS' if u else 'FAIL'} · {n}：独家 {len(u)} 项 —— {'、'.join(u) if u else '无（可被其它用例替代）'}")
    if thin:
        fails.extend(thin)

    print("⑧ Word 抽取回归（三条输入路径之一，此前零覆盖）")
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
