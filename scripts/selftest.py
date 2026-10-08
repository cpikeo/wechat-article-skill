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
CASES = ("skills", "letter", "ink", "visual")
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

    print("② 护栏回归（负例必须仍被拦住）")
    for label, fm, body, kw, level in GUARDS:
        hit, log = guard_ok(label, fm, body, kw, level)
        print(f"   {'PASS' if hit else 'FAIL'} · {label}（{level} → {kw}）")
        if not hit:
            fails.append(label)
            print("   " + log.strip().replace("\n", "\n   "))

    if a.shots:
        try:
            import playwright  # noqa: F401
            from PIL import Image  # noqa: F401
        except ImportError:
            print("\n跳过截图源：未安装 playwright / Pillow（skill 本身不需要它们）")
        else:
            d = os.path.join(tempfile.gettempdir(), "selftest_shots")
            os.makedirs(d, exist_ok=True)
            for n in CASES:
                run([os.path.join(HERE, "render.py"), f"{n}.md", "-o", os.path.join(d, f"{n}.html")], EVAL)
            print(f"\n截图源就绪：{d}（在 390px 无头浏览器里打开，做 Gate 3 通读）")

    print("\n回归：" + ("全部通过" if not fails else f"{len(fails)} 项失败 → {fails}"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
