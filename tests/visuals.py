#!/usr/bin/env python3
"""Browser evidence: six licensed real-source samples, four widths, and one same-draft theme study.

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
# One real-source case per retained theme. The same business-analysis draft is also rendered
# under every theme so the visual language can be compared without changing the words.
THEME_SAMPLES = {
    "paper": "business",
    "letter": "longform",
    "ink": "opinion",
    "frost": "news",
    "bone": "tutorial",
    "folio": "profile",
}
SAME_DRAFT = "business"

NEUTRALIZE_COLOR = """
#c { background:#fff !important; color:#111 !important; }
#c, #c * {
  color:#111 !important;
  background-color:transparent !important;
  background-image:none !important;
  border-color:#666 !important;
  box-shadow:none !important;
  text-shadow:none !important;
  outline-color:#666 !important;
}
#c img { filter:grayscale(1) !important; }
"""


def dependency_check():
    try:
        from PIL import Image, ImageChops, ImageStat  # noqa: F401
        from playwright.sync_api import sync_playwright  # noqa: F401
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
      return {
        width,
        viewportOverflow: document.documentElement.scrollWidth > innerWidth + 1,
        elementOverflow: overflow,
        splitAtoms,
        titleLines: ranges.length,
        titleHeight: title ? Math.round(title.getBoundingClientRect().height) : 0,
        minBodySize: minSize(bodyPs),
        minTableSize: minSize(tablePs),
        minNoteSize: minSize(notePs),
        contentWidth: Math.round(content.getBoundingClientRect().width),
        imagesLoaded: [...document.images].every(img => img.complete && (!img.currentSrc || img.naturalWidth > 0))
      };
    }""", width)


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
    for case_id in set(THEME_SAMPLES.values()) | {SAME_DRAFT}:
        if not (cases_dir / f"{case_id}.edited.md").is_file():
            print(f"FAIL: missing evaluation case {case_id}")
            return 1

    failures, neutral_paths = [], {}
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
                if issues:
                    failures.append(f"{theme}/{case_id}/{width}px: {', '.join(issues)}")
                page.close()

        # Same words under all six themes. Check all widths; save a neutralized 390px viewport
        # capture for structural comparison, after removing foreground/background color cues.
        for theme in THEME_SAMPLES:
            source = cases_dir / f"{SAME_DRAFT}.edited.md"
            preview = build_preview(source, temp / f"same_{SAME_DRAFT}_{theme}.html", theme)
            for width in WIDTHS:
                page = open_page(browser, preview, width)
                metrics = inspect_page(page, width)
                if metrics["viewportOverflow"] or metrics["elementOverflow"] or metrics["splitAtoms"]:
                    failures.append(f"same draft/{theme}/{width}px: overflow or split nowrap atom")
                if metrics["minBodySize"] is not None and metrics["minBodySize"] < 15:
                    failures.append(f"same draft/{theme}/{width}px: body below 15px")
                if metrics["minTableSize"] is not None and metrics["minTableSize"] < 12:
                    failures.append(f"same draft/{theme}/{width}px: table text below 12px")
                if metrics["minNoteSize"] is not None and metrics["minNoteSize"] < 12:
                    failures.append(f"same draft/{theme}/{width}px: note/caption below 12px")
                if width == 390:
                    page.add_style_tag(content=NEUTRALIZE_COLOR)
                    page.evaluate("() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))")
                    shot = out / f"same-draft_{theme}_390_neutral.png"
                    page.screenshot(path=str(shot), clip={"x": 0, "y": 0, "width": width, "height": 844})
                    neutral_paths[theme] = shot
                page.close()

        browser.close()

    # Compare neutralized browser captures. This does not rank designs; it catches the concrete
    # failure mode where themes differ only by color and collapse to the same structure.
    pair_rows = []
    for left, right in itertools.combinations(THEME_SAMPLES, 2):
        a = Image.open(neutral_paths[left]).convert("L")
        b = Image.open(neutral_paths[right]).convert("L")
        if a.size != b.size:
            failures.append(f"neutralized captures have different sizes: {left}/{right}")
            continue
        difference = ImageChops.difference(a, b)
        mean_delta = ImageStat.Stat(difference).mean[0] / 255
        changed = sum(1 for px in difference.tobytes() if px > 8) / (a.width * a.height)
        pair_rows.append((left, right, mean_delta, changed))
        if mean_delta < 0.001:
            failures.append(f"{left}/{right}: near-identical after color neutralization ({mean_delta:.5f})")

    report = [
        "# Browser Visual Review · V6",
        "",
        "Screenshots are browser evidence and review inputs, not a design score or proof of WeChat compatibility.",
        "",
        "## Real-source samples at four widths",
        "",
        "| Theme | Source sample | Widths | Status |",
        "|---|---|---|---|",
    ]
    for theme, case_id in THEME_SAMPLES.items():
        issue = any(row.startswith(f"{theme}/{case_id}/") for row in failures)
        report.append(f"| {theme} | `{case_id}` | 320 / 360 / 390 / 430px | {'FAIL' if issue else 'PASS'} |")
    report += ["", "## Same draft under six themes, color neutralized", "",
               "| Pair | Mean pixel delta (0–1) | Changed pixels |", "|---|---:|---:|"]
    for left, right, mean_delta, changed in pair_rows:
        report.append(f"| {left} / {right} | {mean_delta:.5f} | {changed:.1%} |")
    report += ["", "## Issues", ""] + ([f"- {item}" for item in failures] or ["- No browser-geometry or minimum-text issues."])
    report += ["", "## Not tested", "",
               "- All six evaluation samples contain no body images; image-load assertions were vacuous. Asset path/upload regressions are covered separately.",
               "- Semantic title promise, editorial logic, factual truth and author-voice preference require model/editor review.",
               "- Independent external blind review is UNVERIFIED.",
               "- Real WeChat account, editor sanitization, iOS/Android reading and cover entry-point crops are UNVERIFIED.",
               "", "## Reproduction", "", "```bash", "python3 tests/visuals.py", "```", ""]
    (out / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
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
