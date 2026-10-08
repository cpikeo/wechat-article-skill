#!/usr/bin/env python3
"""Gate 1 · Platform —— 微信公众号 HTML 确定性合规检查。

独立于渲染器：render.py 产物自动经过本检查；手改过的 HTML 也可单独跑。
    check.py <section.html>      退出码 1 = 存在「必须改」
"""
import re
import sys
from collections import Counter
from html.parser import HTMLParser

MUST = [  # 粘贴后会被清洗或导致样式丢失
    (r"<(style|script|link|svg|div|iframe|form|button|video|audio|canvas)[\s>]", "禁用标签"),
    (r"\s(class|id)\s*=", "class/id 会被剥离"),
    (r"position\s*:\s*(fixed|absolute|sticky)", "position 定位不被支持"),
    (r"float\s*:", "float 不被支持"),
    (r"@(media|keyframes|import|font-face)", "@ 规则不被支持"),
    (r"display\s*:\s*grid", "grid 不被支持"),
    (r"var\s*\(\s*--", "CSS 变量不被支持"),
    (r"white-space\s*:\s*pre", "white-space:pre 会把源码换行渲染成空行"),
    (r"(radial|conic)-gradient", "只允许 linear-gradient"),
    (r"src\s*=\s*['\"]https?://[^'\"]*(unsplash|pexels|pixabay|unpkg|jsdelivr)", "图库/CDN 外链图片"),
    (r"\{\{[^}]*\}\}", "占位符残留"),
]
CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
HALF = re.compile(r"[\u4e00-\u9fff][,;!?:]|\"|[\u4e00-\u9fff]'|'[\u4e00-\u9fff]")
CODE = re.compile(r"monospace", re.I)


class Leaf(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.unwrapped, self.half, self.empty = [], [], [], 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        self.stack.append((tag, tag == "span" and "leaf" in a, bool(CODE.search(a.get("style") or ""))))

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        t = data.strip()
        if not t:
            return
        if not any(x[1] for x in self.stack):
            self.unwrapped.append(t[:20])
        if not any(x[2] for x in self.stack) and CJK.search(t) and HALF.search(t):
            self.half.append(t[:20])


def check(html):
    must, should = [], []
    for rx, msg in MUST:
        n = len(re.findall(rx, html, re.I))
        if n:
            must.append(f"{msg}（{n} 处）")
    p = Leaf()
    p.feed(html)
    if p.unwrapped:
        must.append(f"{len(p.unwrapped)} 处文字未包 <span leaf>，例：{p.unwrapped[:3]}")
    if p.half:
        should.append(f"{len(p.half)} 处正文半角标点/直引号，例：{p.half[:3]}")
    # 空装饰元素必须含 <span leaf><br></span>，否则会被整体剥掉
    bare = len(re.findall(r"<(section|span)\s[^>]*>\s*</\1>", html))
    if bare:
        must.append(f"{bare} 个空装饰元素缺少 <span leaf=\"\"><br></span> 占位")
    sizes = Counter(re.findall(r"font-size:\s*(\d+)px", html))
    if len(sizes) > 6:
        should.append(f"字号 {len(sizes)} 级（>6），层级被稀释：{sorted(map(int, sizes))}")
    if re.search(r"<img(?![^>]*max-width:100%)", html):
        must.append("图片缺少 max-width:100%，手机端可能溢出")
    return must, should


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    must, should = check(open(sys.argv[1], encoding="utf-8").read())
    for m in must:
        print("必须改 ·", m)
    for s in should:
        print("建议改 ·", s)
    print("Gate 1 Platform:", "FAIL" if must else "PASS")
    sys.exit(1 if must else 0)


if __name__ == "__main__":
    main()
