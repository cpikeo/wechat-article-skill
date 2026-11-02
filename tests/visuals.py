#!/usr/bin/env python3
"""Browser evidence: six editorial samples, one source-traceable image fixture, four widths, six themes.

Requires optional development tools: playwright, Pillow, Chromium and Noto CJK fonts.
Generated screenshots are review inputs, not an aesthetic score or proof of WeChat compatibility.
"""
import argparse
import itertools
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evaluation"
RENDER = ROOT / "scripts" / "render.py"
WIDTHS = (320, 360, 390, 430)
# One deterministic editorial case per retained theme, plus a human-authored CC0 image fixture.
# The image fixture is rendered unchanged under every theme for visual comparison.
THEME_SAMPLES = {
    "paper": "business",
    "letter": "longform",
    "ink": "opinion",
    "frost": "news",
    "bone": "tutorial",
    "folio": "profile",
}
SAME_DRAFT = "visual-sample"
VISUAL_SAMPLE = EVAL / "visual-sample.md"

NEUTRALIZE_COLOR = """
#c, .cv { background:#fff !important; color:#111 !important; }
#c *, .cv * {
  color:#111 !important;
  background-color:transparent !important;
  background-image:none !important;
  border-color:#666 !important;
  box-shadow:none !important;
  text-shadow:none !important;
  outline-color:#666 !important;
}
#c img, .cv img { filter:grayscale(1) !important; }
"""


def dependency_check():
    try:
        # 只探测可用性；真正使用时在函数内部按需导入，模块顶层不留未用引用。
        __import__("PIL.Image"); __import__("PIL.ImageChops"); __import__("PIL.ImageStat")
        __import__("playwright.sync_api")
    except ImportError as exc:
        return False, f"BLOCKED: optional screenshot dependency unavailable: {exc}"
    font = subprocess.run(["fc-match", "-f", "%{family}", "Noto Sans CJK SC"],
                          capture_output=True, text=True)
    if font.returncode or "Noto Sans CJK" not in font.stdout:
        return False, "BLOCKED: Noto Sans CJK SC is not installed; refusing missing-glyph evidence"
    return True, ""


def build_preview(source, output, theme):
    cmd = [sys.executable, str(RENDER), str(source), "--theme", theme, "-o", str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"render failed for {source.name}/{theme}:\n{result.stdout}\n{result.stderr}")
    preview = output.with_name(output.stem + "_预览.html")
    if not preview.is_file():
        raise RuntimeError(f"renderer did not create preview: {preview}")
    return preview


def inspect_page(page, width):
    return page.evaluate("""(width) => {
      const content = document.querySelector('#c');
      const title = document.querySelector('.nt h1');
      const nonempty = [...content.querySelectorAll('p')].filter(p => p.textContent.trim());
      const sourceSections = nonempty.filter(p => p.textContent.trim() === '来源与口径')
        .map(p => p.parentElement);
      const imageSections = [...content.querySelectorAll('img')]
        .map(img => img.parentElement).filter(el => el && el.tagName === 'SECTION');
      const noteSections = [...new Set([...sourceSections, ...imageSections])];
      const inNote = p => noteSections.some(section => section.contains(p));
      const bodyPs = nonempty.filter(p => {
        const parentStyle = p.parentElement.getAttribute('style') || '';
        return !p.closest('table') && !inNote(p) && /^margin:0 0/.test(parentStyle);
      });
      const tablePs = nonempty.filter(p => p.closest('table'));
      const notePs = nonempty.filter(inNote);
      const minSize = list => list.length ? Math.min(...list.map(p => parseFloat(getComputedStyle(p).fontSize))) : null;
      const ranges = [];
      if (title) {
        const range = document.createRange();
        range.selectNodeContents(title);
        ranges.push(...range.getClientRects());
      }
      const right = content.getBoundingClientRect().right;
      const overflow = [...content.querySelectorAll('p,img,table,th,td')].filter(el =>
        el.scrollWidth > el.clientWidth + 1 || el.getBoundingClientRect().right > right + 1
      ).map(el => ({tag:el.tagName, text:el.textContent.trim().slice(0,32)}));
      const splitAtoms = [...content.querySelectorAll('span[style*="white-space:nowrap"]')]
        .filter(el => el.getClientRects().length > 1).map(el => el.textContent);
      // 排版层级：导语、H2、正文的相对字号是「第一眼能否分出主次」的可测前提。
      // 导语 = 第一个章节标题之前、字号最大的正文段落（不含图注/来源），
      // 这样 kicker（14px 小字）不会被误当成导语。
      // 章节标记：每个 H2 之前紧邻的 section 里的短文字（如 01 /、SECTION、— 、编号）。
      // 章节标题 = 字号大于正文、字重≥500、且确实是文字（短于 6 字的多半是 01 / 之类标记）。
      const chapters = [...content.querySelectorAll('p')].filter(p => {
        const s = getComputedStyle(p);
        const text = p.textContent.trim();
        return parseFloat(s.fontSize) >= 17 && parseFloat(s.fontWeight) >= 500 && text.length >= 6
          && !p.closest('table') && !inNote(p) && !/^margin:0 0/.test(p.parentElement.getAttribute('style') || '');
      });
      const firstChapter = chapters.length ? chapters[0] : null;
      // 导语候选：首个章节标题之前、字数≥6、且不小于正文的段落。
      // 图注/来源（本来就比正文小）与 01 这类纯标记（不足 6 字）都不参选。
      const bodySize = minSize(bodyPs);
      const leadCandidates = nonempty.filter(p => {
        const size = parseFloat(getComputedStyle(p).fontSize);
        return !p.closest('table') && !inNote(p) && p.textContent.trim().length >= 6
          && (bodySize === null || size >= bodySize)
          && (!firstChapter || (firstChapter.compareDocumentPosition(p) & Node.DOCUMENT_POSITION_PRECEDING));
      });
      const leadSize = leadCandidates.length
        ? Math.max(...leadCandidates.map(p => parseFloat(getComputedStyle(p).fontSize))) : null;
      const markers = chapters.map(h => {
        let el = h.closest('section');
        let prev = el && el.previousElementSibling;
        while (prev && !prev.textContent.trim()) prev = prev.previousElementSibling;
        const t = prev ? prev.textContent.trim() : '';
        return t.length <= 12 ? t : '';
      });
      return {
        width,
        leadSize,
        chapterHeadingSizes: chapters.map(p => parseFloat(getComputedStyle(p).fontSize)),
        chapterMarkers: markers,
        viewportOverflow: document.documentElement.scrollWidth > innerWidth + 1,
        elementOverflow: overflow,
        splitAtoms,
        titleLines: ranges.length,
        titleHeight: title ? Math.round(title.getBoundingClientRect().height) : 0,
        minBodySize: minSize(bodyPs),
        minTableSize: minSize(tablePs),
        minNoteSize: minSize(notePs),
        contentWidth: Math.round(content.getBoundingClientRect().width),
        bodyImageCount: content.querySelectorAll('img').length,
        imagesLoaded: [...document.images].every(img => img.complete && (!img.currentSrc || img.naturalWidth > 0))
      };
    }""", width)


# 本脚本会写入的输出文件名；清理旧输出时只删这些形态。
GENERATED_PATTERNS = ("sample_*.png", "same-draft_*.jpg", "same-draft_*_neutral.png", "REPORT.md")


def prune_stale(out, written):
    """删除上一轮留下、本轮没有写过的截图。

    输出目录只放生成物，但清理必须放在**跑完之后**：中途失败时上一轮的证据仍然在。
    只删本脚本自己的命名形态，`--out` 指向别的目录也不会误删别人的文件。
    """
    keep = {Path(p).resolve() for p in written}
    removed = []
    for pattern in GENERATED_PATTERNS:
        for path in out.glob(pattern):
            if path.is_file() and path.resolve() not in keep:
                path.unlink()
                removed.append(path.name)
    return sorted(removed)


def declares_lead(source):
    """源稿是否真有导语（frontmatter 之后第一个正文块是 `>`）。没有导语就不该量导语字号。"""
    text = source.read_text(encoding="utf-8")
    body = text.split("---\n", 2)[-1]
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        return line.startswith(">")
    return False


def hierarchy_issues(theme, metrics, has_lead=True):
    """可机检的排版层级缺陷：导语压过章节标题、正文字号反超导语、章节标记机械复读。

    这些不是审美判断，而是「层级链断掉」的几何证据：读者在小屏上靠字号与标记分辨主次，
    一旦导语 ≥ 章节标题，首屏就出现两个同级入口（V7 审计发现 paper/folio 曾如此）。
    """
    issues = []
    sizes = metrics.get("chapterHeadingSizes") or []
    lead = metrics.get("leadSize") if has_lead else None
    if lead and sizes and lead >= min(sizes):
        issues.append(f"lead {lead:.1f}px ≥ 章节标题 {min(sizes):.1f}px（首屏出现同级入口）")
    if lead and metrics.get("minBodySize") and lead <= metrics["minBodySize"]:
        issues.append(f"lead {lead:.1f}px ≤ 正文 {metrics['minBodySize']:.1f}px（导语失去入口作用）")
    markers = [m for m in (metrics.get("chapterMarkers") or []) if m]
    run, best = 1, 1
    for a, b in zip(markers, markers[1:]):
        run = run + 1 if a == b else 1
        best = max(best, run)
    if best >= 3:
        issues.append(f"同一章节标记「{markers[0]}」连续出现 {best} 次（机械复读）")
    return issues


def open_page(browser, preview, width, height=844):
    page = browser.new_page(viewport={"width": width, "height": height}, device_scale_factor=1)
    page.goto(preview.as_uri())
    page.evaluate("() => document.fonts.ready")
    page.wait_for_function("() => [...document.images].every(img => img.complete)")
    return page


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(ROOT / "evaluation" / "visual-review"),
                    help="ignored review-output directory (default: evaluation/visual-review)")
    args = ap.parse_args()
    ok, reason = dependency_check()
    if not ok:
        print(reason)
        return 2

    from PIL import Image, ImageChops, ImageStat
    from playwright.sync_api import sync_playwright

    out = Path(args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    cases_dir = EVAL / "cases"
    for case_id in set(THEME_SAMPLES.values()):
        if not (cases_dir / f"{case_id}.edited.md").is_file():
            print(f"FAIL: missing evaluation case {case_id}")
            return 1
    if not VISUAL_SAMPLE.is_file():
        print(f"FAIL: missing real-image visual fixture {VISUAL_SAMPLE}")
        return 1

    failures, neutral_paths, written = [], {}, []
    with tempfile.TemporaryDirectory(prefix="wechat-theme-study-") as temp_dir, sync_playwright() as p:
        try:
            browser = p.chromium.launch()
        except Exception as exc:
            print(f"BLOCKED: Chromium could not launch in this environment: {exc}")
            return 2
        temp = Path(temp_dir)

        # Six real-source samples at all four requested widths.
        for theme, case_id in THEME_SAMPLES.items():
            source = cases_dir / f"{case_id}.edited.md"
            preview = build_preview(source, temp / f"sample_{case_id}_{theme}.html", theme)
            for width in WIDTHS:
                page = open_page(browser, preview, width)
                metrics = inspect_page(page, width)
                png = out / f"sample_{theme}_{case_id}_{width}.png"
                page.screenshot(path=str(png), full_page=True)
                written.append(png)
                issues = []
                if metrics["viewportOverflow"] or metrics["elementOverflow"]:
                    issues.append("horizontal overflow")
                if metrics["splitAtoms"]:
                    issues.append("nowrap number/date split")
                if not metrics["imagesLoaded"]:
                    issues.append("image failed to load")
                if metrics["minBodySize"] is not None and metrics["minBodySize"] < 15:
                    issues.append(f"body below 15px ({metrics['minBodySize']:.1f}px)")
                if metrics["minTableSize"] is not None and metrics["minTableSize"] < 12:
                    issues.append(f"table text below 12px ({metrics['minTableSize']:.1f}px)")
                if metrics["minNoteSize"] is not None and metrics["minNoteSize"] < 12:
                    issues.append(f"note/caption below 12px ({metrics['minNoteSize']:.1f}px)")
                if not metrics["titleLines"]:
                    issues.append("native title is absent or not measurable")
                issues.extend(hierarchy_issues(theme, metrics, declares_lead(source)))
                if issues:
                    failures.append(f"{theme}/{case_id}/{width}px: {', '.join(issues)}")
                page.close()

        # The same source-traceable image article under all six themes. Check four widths,
        # preserve colored full-page captures, and neutralize all themed content for comparison.
        for theme in THEME_SAMPLES:
            preview = build_preview(VISUAL_SAMPLE, temp / f"same_{SAME_DRAFT}_{theme}.html", theme)
            for width in WIDTHS:
                page = open_page(browser, preview, width)
                metrics = inspect_page(page, width)
                if metrics["viewportOverflow"] or metrics["elementOverflow"] or metrics["splitAtoms"]:
                    failures.append(f"image fixture/{theme}/{width}px: overflow or split nowrap atom")
                if metrics["minBodySize"] is not None and metrics["minBodySize"] < 15:
                    failures.append(f"image fixture/{theme}/{width}px: body below 15px")
                if metrics["minTableSize"] is not None and metrics["minTableSize"] < 12:
                    failures.append(f"image fixture/{theme}/{width}px: table text below 12px")
                if metrics["minNoteSize"] is not None and metrics["minNoteSize"] < 12:
                    failures.append(f"image fixture/{theme}/{width}px: note/caption below 12px")
                if not metrics["imagesLoaded"]:
                    failures.append(f"image fixture/{theme}/{width}px: image failed to load")
                hierarchy = hierarchy_issues(theme, metrics, declares_lead(VISUAL_SAMPLE))
                if hierarchy:
                    failures.append(f"image fixture/{theme}/{width}px: {'; '.join(hierarchy)}")
                if metrics["bodyImageCount"] != 4:
                    failures.append(f"image fixture/{theme}/{width}px: expected 4 body image instances, found {metrics['bodyImageCount']}")
                same_draft = out / f"same-draft_{theme}_{width}.jpg"
                page.screenshot(path=str(same_draft), full_page=True, type="jpeg", quality=90)
                written.append(same_draft)
                if width == 390:
                    # The toolbar contains a theme name, which is not a design difference.
                    page.evaluate("() => { const label=document.querySelector('.bar span'); if(label) label.textContent='同稿同题'; }")
                    page.add_style_tag(content=NEUTRALIZE_COLOR)
                    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                    shot = out / f"same-draft_{theme}_390_neutral.png"
                    page.screenshot(path=str(shot), full_page=True)
                    written.append(shot)
                    neutral_paths[theme] = shot
                page.close()

        browser.close()

    # Compare neutralized browser captures. This does not rank designs; it catches the concrete
    # failure mode where themes differ only by color and collapse to the same structure.
    pair_rows = []
    for left, right in itertools.combinations(THEME_SAMPLES, 2):
        a = Image.open(neutral_paths[left]).convert("L")
        b = Image.open(neutral_paths[right]).convert("L")
        canvas_size = (max(a.width, b.width), max(a.height, b.height))
        # Align full-page captures at the top-left; pad the shorter page with preview gray.
        pa, pb = Image.new("L", canvas_size, 237), Image.new("L", canvas_size, 237)
        pa.paste(a, (0, 0))
        pb.paste(b, (0, 0))
        difference = ImageChops.difference(pa, pb)
        mean_delta = ImageStat.Stat(difference).mean[0] / 255
        changed = sum(1 for px in difference.tobytes() if px > 8) / (pa.width * pa.height)
        pair_rows.append((left, right, mean_delta, changed))
        if mean_delta < 0.001:
            failures.append(f"{left}/{right}: near-identical after color neutralization ({mean_delta:.5f})")

    report = [
        "# Browser Visual Review · V7",
        "",
        "Screenshots are browser evidence and review inputs, not a design score or proof of WeChat compatibility.",
        "",
        "## Editorial source samples at four widths",
        "",
        "| Theme | Source sample | Widths | Status |",
        "|---|---|---|---|",
    ]
    for theme, case_id in THEME_SAMPLES.items():
        issue = any(row.startswith(f"{theme}/{case_id}/") for row in failures)
        report.append(f"| {theme} | `{case_id}` | 320 / 360 / 390 / 430px | {'FAIL' if issue else 'PASS'} |")
    image_failures = [row for row in failures if row.startswith("image fixture/")]
    report += ["", "## Source-traceable image fixture", "",
               "- `evaluation/visual-sample.md`: a human-authored reading sample using The Met's public-domain *Under the Wave off Kanagawa*; the museum API marks the image `isPublicDomain=true`, and the Open Access policy applies CC0.",
               "- Six themes × 320 / 360 / 390 / 430px. Four body image placements (full scan, explanatory detail, adjacent comparison pair) and a declared cover crop are checked for successful local loading.",
               f"- Browser/image-load status: {'FAIL' if image_failures else 'PASS'}; interpretive quality, asset-role suitability and crop preference still require human editorial judgment.",
               "- The original six editorial cases contain no body images; their image-load checks are intentionally not counted as image evidence.",
               "", "## Same image article under six themes, color neutralized", "",
               "The theme-name label is replaced with a common label; article and cover colors are neutralized and images are grayscale. Pairwise pixel deltas detect collapse to near-identical structure only; they do not rank aesthetics.",
               "", "| Pair | Mean pixel delta (0–1) | Changed pixels |", "|---|---:|---:|"]
    for left, right, mean_delta, changed in pair_rows:
        report.append(f"| {left} / {right} | {mean_delta:.5f} | {changed:.1%} |")
    report += ["", "## Issues", ""] + ([f"- {item}" for item in failures] or ["- No browser-geometry, image-load or minimum-text issues."])
    report += ["", "## Not tested", "",
               "- Semantic title promise, editorial logic, factual truth and author-voice preference require model/editor review.",
               "- Independent external blind review is UNVERIFIED.",
               "- Real WeChat account, editor sanitization, iOS/Android reading and in-client cover crops are UNVERIFIED.",
               "", "## Reproduction", "", "```bash", "python3 tests/visuals.py", "```", ""]
    report_path = out / "REPORT.md"
    report_path.write_text("\n".join(report), encoding="utf-8")
    written.append(report_path)
    removed = prune_stale(out, written)
    if removed:
        print(f"清理上一轮遗留输出 {len(removed)} 个：{'、'.join(removed[:6])}"
              + ("…" if len(removed) > 6 else ""))
    print(f"Browser visual review: {'PASS' if not failures else 'FAIL'}")
    print(f"Real-source samples: {len(THEME_SAMPLES)} × {len(WIDTHS)} widths; same draft: 6 themes × {len(WIDTHS)} widths")
    print(f"Neutralized pair comparisons: {len(pair_rows)}")
    print(f"Review evidence: {out}")
    if failures:
        for item in failures:
            print("FAIL ·", item)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
