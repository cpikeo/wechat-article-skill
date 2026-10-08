#!/usr/bin/env python3
"""公众号 HTML 设计质量启发式检测器。

validate_gzh_html.py 只管"平台会不会吃掉这段 HTML"（合规），
本脚本管"这段 HTML 排出来像不像专业设计师做的"（质量）——
这两件事是独立的正交检查，都要跑，互不替代。

检查的都是可量化、可复现的启发式信号，不是审美判断本身：
1. 强调色滥用：某个高饱和强调色出现次数是否超出"全篇克制配额"
   （主题库里一般写"全篇 ≤3~5 处"，本脚本按传入的 --accent 检测出现频次）。
2. 字号体系混乱：正文区出现的不同 font-size 取值种类是否过多
   （专业排版的字号级数通常是一套 4~6 级的克制阶梯，不是随手取值）。
3. 连续重复区块：连续 3 个及以上 <section>/<p> 使用完全相同的 style
   字符串，视觉上会显得单调、缺乏节奏变化。
4. 段落过长：单个文本节点长度超过阈值且中间没有任何标点/换行断句，
   在手机屏幕上会形成大段无呼吸感的文字墙。
5. 空标题/空容器：组件骨架里常见的 {{占位符}} 残留未替换。
6. 图片过密：相邻两张图片之间是否几乎没有正文文字，导致读者连续
   下滑却全是图，没有文字承接（"发布模拟器"式检查里"图片是否跳跃"
   的可量化版本——只测"图片间正文字数"，不测审美本身）。

用法:
    design_quality_check.py <file.html> [--accent '#F97316'] [--accent-quota 5]
    design_quality_check.py --stdin < file.html

退出码: 1 = 有 ERROR 级别问题；0 = 通过（可能仍有 WARNING，建议人工过一遍）。
"""

import argparse
import re
import sys
from collections import Counter
from html.parser import HTMLParser

PLACEHOLDER = re.compile(r"\{\{[^}]+\}\}")
FONT_SIZE = re.compile(r"font-size\s*:\s*(\d+(?:\.\d+)?)px", re.I)
LONG_TEXT_THRESHOLD = 220  # 单个文本节点的字符数阈值（含中文标点计数）
BREAK_PUNCT = re.compile(r"[，。！？；、,.!?;]")


class StyleCollector(HTMLParser):
    """收集顶层 section/p 的 style 签名，以及每个文本节点的长度。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.block_styles = []   # 按出现顺序记录 (tag, style)
        self.text_lengths = []   # 每个独立文本节点的 (长度, 摘要, 是否含断句标点)
        self._cur_text = []

    def handle_starttag(self, tag, attrs):
        ad = dict(attrs)
        if tag in ("section", "p"):
            self.block_styles.append((tag, ad.get("style", "").strip()))

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return
        has_break = bool(BREAK_PUNCT.search(text))
        self.text_lengths.append((len(text), text[:30] + ("…" if len(text) > 30 else ""), has_break))


def check_accent_overuse(html, accent, quota):
    if not accent:
        return None
    count = html.count(accent)
    if count > quota:
        return (
            "WARNING",
            f"强调色 {accent} 出现 {count} 次，超过建议配额（≤{quota} 处）——"
            "锚点层的价值在于稀缺，到处用等于没有重点，考虑改回主色或下划线标记。",
        )
    return None


def check_font_size_variety(html, max_levels=6):
    sizes = Counter(FONT_SIZE.findall(html))
    n = len(sizes)
    if n > max_levels:
        top = ", ".join(f"{k}px×{v}" for k, v in sorted(sizes.items(), key=lambda x: -x[1])[:10])
        return (
            "WARNING",
            f"正文出现 {n} 种不同字号，超过专业排版常见的 4~6 级阶梯（{top} ...）——"
            "字号越杂，层级感越弱，建议归并到主题设计变量表规定的几档字号。",
        )
    return None


def check_repeated_blocks(block_styles, min_repeat=3):
    issues = []
    i = 0
    n = len(block_styles)
    while i < n:
        j = i
        while j < n and block_styles[j] == block_styles[i]:
            j += 1
        run_len = j - i
        if run_len >= min_repeat and block_styles[i][1]:
            tag, style = block_styles[i]
            issues.append(
                f"连续 {run_len} 个 <{tag}> 使用完全相同的 style（{style[:50]}...），"
                "视觉节奏单调，建议在其中穿插不同的组件类型或强调层级。"
            )
        i = j
    return issues


def check_long_paragraphs(text_lengths, threshold=LONG_TEXT_THRESHOLD):
    issues = []
    for length, snippet, has_break in text_lengths:
        if length > threshold and not has_break:
            issues.append(
                f"发现 {length} 字的文本节点且中间无任何标点断句："
                f"「{snippet}」——手机端会变成一堵文字墙，建议拆句或拆段。"
            )
    return issues


def check_placeholders(html):
    hits = PLACEHOLDER.findall(html)
    if hits:
        uniq = sorted(set(hits))
        return [f"发现未替换的占位符 {', '.join(uniq)}——交付前必须替换或删除对应整行（见 SKILL.md 占位图/占位署名规则）。"]
    return []


IMG_TAG = re.compile(r"<img\b[^>]*>", re.I)
ANY_TAG = re.compile(r"<[^>]+>")


def check_image_density(html, min_text_between=12):
    """检测相邻两张图片之间的正文字数是否过少（图片过密/连续刷图）。

    做法：把每个 <img> 替换成一个分隔符，去掉其余所有标签只留纯文本，
    再看分隔符之间的文字量——这只测"字数"这个可复现信号，不判断图片
    本身好不好看，也不判断"是否跳跃"这种主观感受。
    """
    marked = IMG_TAG.sub("\x00", html)
    stripped = re.sub(r"\s+", "", ANY_TAG.sub("", marked))
    segments = stripped.split("\x00")
    n_images = len(segments) - 1
    issues = []
    if n_images < 2:
        return issues
    for idx in range(1, n_images):  # 第 idx 张和第 idx+1 张之间
        gap_len = len(segments[idx])
        if gap_len < min_text_between:
            issues.append(
                f"第 {idx} 张和第 {idx + 1} 张图片之间只有约 {gap_len} 个字的正文"
                f"（少于 {min_text_between} 字）——连续图片间缺少文字承接，"
                "读者感觉是在连续刷图而不是读文章，建议补一段过渡文字，"
                "或者两张图确实是同一组素材的话直接合并/删减其中一张。"
            )
    return issues


def run(html, accent=None, accent_quota=5):
    errors, warnings = [], []

    collector = StyleCollector()
    try:
        collector.feed(html)
    except Exception as e:
        warnings.append(f"HTML 解析中断，以下检查可能不完整: {e}")

    r = check_accent_overuse(html, accent, accent_quota)
    if r:
        (errors if r[0] == "ERROR" else warnings).append(r[1])

    r = check_font_size_variety(html)
    if r:
        (errors if r[0] == "ERROR" else warnings).append(r[1])

    for msg in check_repeated_blocks(collector.block_styles):
        warnings.append(msg)

    for msg in check_long_paragraphs(collector.text_lengths):
        warnings.append(msg)

    ph = check_placeholders(html)
    errors.extend(ph)  # 占位符残留视为 ERROR：这是"忘了填"的硬伤，不是审美问题

    for msg in check_image_density(html):
        warnings.append(msg)

    return errors, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("file", nargs="?", help="HTML 文件路径")
    ap.add_argument("--stdin", action="store_true", help="从标准输入读取")
    ap.add_argument("--accent", default=None, help="要监控用量的强调色 hex，如 #F97316")
    ap.add_argument("--accent-quota", type=int, default=5, help="强调色全篇建议上限次数，默认 5")
    args = ap.parse_args()

    if args.stdin or not args.file:
        html = sys.stdin.read()
        name = "<stdin>"
    else:
        with open(args.file, encoding="utf-8", errors="replace") as f:
            html = f.read()
        name = args.file

    errors, warnings = run(html, accent=args.accent, accent_quota=args.accent_quota)

    print(f"🎨 设计质量启发式检测: {name}")
    if errors:
        print(f"\n❌ ERROR ×{len(errors)}（交付前必须处理）:")
        for e in errors:
            print(f"   • {e}")
    if warnings:
        print(f"\n⚠️  WARNING ×{len(warnings)}（建议人工过一遍，不一定要全改）:")
        for w in warnings:
            print(f"   • {w}")
    if not errors and not warnings:
        print("\n✅ 未发现启发式问题（这不代表审美一定过关，仍建议交付前通读一遍）")
    elif not errors:
        print("\n✅ 无硬伤，warning 请按需取舍")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
