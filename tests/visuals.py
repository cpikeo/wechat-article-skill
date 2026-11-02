#!/usr/bin/env python3
"""开发证据：六类真实来源原稿/优化稿的 320/390px 截图与并排对照。不进入运行时。"""
import argparse, json, os, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
import editorial_eval as ev

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "assets" / "shots" / "editorial"))
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright
    from PIL import Image, ImageDraw
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    data = ev.load_dataset()
    with tempfile.TemporaryDirectory() as td, sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        for case in data["cases"]:
            images = {}
            for side in ("original", "edited"):
                src = ev.safe_case_file(case[side])
                html = Path(td) / f"{case['id']}_{side}.html"
                subprocess.run([sys.executable, str(ROOT/"scripts"/"render.py"), str(src), "-o", str(html)], check=True, capture_output=True)
                prev = html.with_name(html.stem + "_预览.html")
                for width in (320, 390):
                    pg = b.new_page(viewport={"width": width, "height": 844}, device_scale_factor=2)
                    pg.goto(prev.as_uri()); pg.wait_for_function("() => [...document.images].every(i=>i.complete)")
                    pg.evaluate("() => document.fonts.ready")
                    name = f"{case['id']}_{side}_{width}.png"
                    pg.screenshot(path=str(out/name), full_page=True)
                    pg.screenshot(path=str(out/f"{case['id']}_{side}_{width}_首屏.png"), clip={"x":0,"y":0,"width":width,"height":844})
                    images[(side,width)] = out/name
                    pg.close()
            for width in (320,390):
                a = Image.open(images[("original",width)]); c = Image.open(images[("edited",width)])
                h = max(a.height,c.height); w = a.width+c.width+24
                sheet = Image.new("RGB",(w,h+56),"white"); d=ImageDraw.Draw(sheet)
                d.text((8,8),f"{case['id']} · original · {width}px",fill="black"); d.text((a.width+32,8),f"{case['id']} · edited · {width}px",fill="black")
                sheet.paste(a,(0,56)); sheet.paste(c,(a.width+24,56))
                sheet.save(out/f"{case['id']}_before_after_{width}.png")
        b.close()
    print(f"编辑前后视觉证据 → {out}")
if __name__ == "__main__":
    main()
