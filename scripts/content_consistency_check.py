#!/usr/bin/env python3
"""文章术语/日期/数字/单位一致性检测器（配套 references/content-editing-guide.md 第三节）。

只做**检测和定位**，不自动改——同一概念该用哪种写法（比如"AI"还是"人工智能"）
由用户的行文习惯决定，脚本没有权限替用户做这个选择。

检测项：
1. 同一概念的中英文/全称简称混用（如 "AI" / "人工智能" 交替出现）。
2. 日期格式不统一（"2026年7月17日" 和 "2026-07-17" 同时出现）。
3. 数字全角半角混用（"３个方法" 和 "3个方法" 同时出现）。
4. 常见计量单位书写不统一（"km" 和 "公里"、"%" 和 "百分之" 同时出现）。

用法:
    content_consistency_check.py <文章.md 或 .html>
    content_consistency_check.py --stdin < 文章.md

退出码: 始终为 0——本脚本只报告、不拦截，不影响 SKILL.md 第 5/5.5 步的强制校验。
"""

import argparse
import re
import sys

# 同一概念的常见中英/全称简称对照组：出现两种及以上写法即提示，不判断哪种"对"
TERM_GROUPS = [
    ["AI", "人工智能"],
    ["公众号", "official account", "微信公众号"],
    ["GZH", "公众号"],
    ["LLM", "大语言模型", "大模型"],
    ["API", "接口"],
    ["UI", "界面"],
    ["UX", "用户体验"],
    ["ROI", "投资回报率"],
    ["KOL", "意见领袖"],
    ["SaaS", "软件即服务"],
]

DATE_PATTERNS = {
    "中文长日期（2026年7月17日）": re.compile(r"\d{4}年\d{1,2}月\d{1,2}日"),
    "短横线日期（2026-07-17）": re.compile(r"\d{4}-\d{1,2}-\d{1,2}"),
    "斜杠日期（2026/07/17）": re.compile(r"\d{4}/\d{1,2}/\d{1,2}"),
    "点分日期（2026.07.17）": re.compile(r"\d{4}\.\d{1,2}\.\d{1,2}"),
}

FULLWIDTH_DIGIT = re.compile(r"[０-９]")
HALFWIDTH_DIGIT = re.compile(r"[0-9]")

UNIT_GROUPS = [
    ["km", "公里", "千米"],
    ["kg", "公斤", "千克"],
    ["%", "百分之"],
    ["min", "分钟"],
    ["h", "小时"],
    ["m", "米"],
]


def check_term_consistency(text):
    warnings = []
    for group in TERM_GROUPS:
        found = [t for t in group if re.search(re.escape(t), text, re.I)]
        if len(found) >= 2:
            warnings.append(
                f"术语混用：{' / '.join(found)} 在同一篇文章里同时出现——"
                "确认是否指同一概念，是的话统一成一种写法（用哪种由行文习惯定，本脚本不代改）。"
            )
    return warnings


def check_date_format(text):
    hit_formats = [name for name, pat in DATE_PATTERNS.items() if pat.search(text)]
    if len(hit_formats) >= 2:
        return [
            f"日期格式不统一：同时出现 {' 、 '.join(hit_formats)}——建议统一成一种格式。"
        ]
    return []


def check_digit_width(text):
    has_full = bool(FULLWIDTH_DIGIT.search(text))
    has_half = bool(HALFWIDTH_DIGIT.search(text))
    if has_full and has_half:
        fulls = sorted(set(FULLWIDTH_DIGIT.findall(text)))
        return [
            f"数字全角/半角混用：正文中同时出现全角数字（如 {''.join(fulls[:5])}）和半角数字——"
            "全角数字在公众号排版里少见且容易显得不专业，建议统一成半角，代码块/命令行内容除外。"
        ]
    return []


def check_unit_consistency(text):
    warnings = []
    for group in UNIT_GROUPS:
        found = [u for u in group if re.search(re.escape(u), text)]
        has_ascii = any(u.isascii() for u in found)
        has_chinese = any(not u.isascii() for u in found)
        # 只在"英文缩写"和"中文写法"同时出现时才提示，避免单字母缩写（h/m）在正文里的高误报率
        if has_ascii and has_chinese:
            warnings.append(f"计量单位写法不统一：{' / '.join(found)} 同时出现——建议统一成一种写法。")
    return warnings


def run(text):
    warnings = []
    warnings.extend(check_term_consistency(text))
    warnings.extend(check_date_format(text))
    warnings.extend(check_digit_width(text))
    warnings.extend(check_unit_consistency(text))
    return warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", help="文章文件路径（.md 或 .html）")
    ap.add_argument("--stdin", action="store_true", help="从标准输入读取")
    args = ap.parse_args()

    if args.stdin or not args.file:
        text = sys.stdin.read()
        name = "<stdin>"
    else:
        with open(args.file, encoding="utf-8", errors="replace") as f:
            text = f.read()
        name = args.file

    warnings = run(text)

    print(f"📝 内容一致性检测: {name}")
    if warnings:
        print(f"\n⚠️  发现 {len(warnings)} 处可能的不一致（仅提示，不自动修改）:")
        for w in warnings:
            print(f"   • {w}")
    else:
        print("\n✅ 未发现术语/日期/数字/单位层面的明显不一致")

    print("\n提示：本脚本只检测、不代改；统一成哪种写法由用户的行文习惯决定，不是本脚本判断对错。")
    sys.exit(0)


if __name__ == "__main__":
    main()
