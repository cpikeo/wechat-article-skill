#!/usr/bin/env python3
"""Gate 1：检查发布正文的确定性风险，不证明微信清洗或粘贴兼容。"""
import re
import sys
from html.parser import HTMLParser

CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
HALF = re.compile(r'[\u4e00-\u9fff][,;!?:]|"|[\u4e00-\u9fff]\'|\'[\u4e00-\u9fff]')
VOID = {"img", "br", "hr", "meta", "link", "input", "source", "wbr"}
FORBIDDEN = {"style", "script", "link", "svg", "div", "iframe", "form", "button", "video", "audio", "canvas", "object", "embed"}
CSS_RISKS = (
    (r"position\s*:\s*(fixed|absolute|sticky)", "定位"),
    (r"float\s*:|display\s*:\s*grid", "float/grid"),
    (r"@(media|keyframes|import|font-face)|var\s*\(\s*--", "@规则/CSS变量"),
    (r"white-space\s*:\s*pre(?:\s*;|\s*$)", "white-space:pre"),
    (r"(radial|conic)-gradient|url\s*\(|expression\s*\(", "外部或不支持的CSS资源"),
)


class Leaf(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.must, self.half, self.images, self.sizes = [], [], [], [], set()

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        style = a.get("style") or ""
        if tag in FORBIDDEN:
            self.must.append(f"禁用标签：{tag}")
        if any(k in ("class", "id", "srcset") or k.startswith("on") for k in a):
            self.must.append(f"{tag} 含 class/id/srcset 或事件属性")
        if any((a.get(k) or "").strip().lower().startswith(("javascript:", "data:", "file:")) for k in ("href", "src")):
            self.must.append(f"{tag} 含不允许的资源协议")
        for rx, msg in CSS_RISKS:
            if re.search(rx, style, re.I):
                self.must.append(msg)
        self.sizes.update(re.findall(r"font-size\s*:\s*(\d+)px", style, re.I))
        if tag == "img":
            src = a.get("src") or ""
            self.images.append(src)
            if not src or src.startswith("//") or re.match(r"^[a-z][a-z0-9+.-]*:", src, re.I):
                self.must.append(f"图片必须是本地路径：{src}")
            if not re.search(r"max-width\s*:\s*100%", style, re.I):
                self.must.append("图片缺少 max-width:100%")
        if tag not in VOID:
            self.stack.append((tag, tag == "span" and "leaf" in a, bool(re.search("monospace", style, re.I))))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

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
            self.must.append(f"文字未包 <span leaf>：{t[:20]}")
        if not any(x[2] for x in self.stack) and CJK.search(t) and HALF.search(re.sub(r'https?://[^\s<>，；。！？）"]+', "", t)):
            self.half.append(t[:20])


def image_sources(html):
    p = Leaf()
    p.feed(html)
    return p.images


def check(html):
    p = Leaf()
    p.feed(html)
    should = [f"待人工核对的半角标点/直引号（URL/引文可保留）：{p.half[:3]}"] if p.half else []
    if re.search(r"<(section|span)\b[^>]*>\s*</\1>", html, re.I):
        p.must.append('空装饰元素缺少 <span leaf=""><br></span>')
    return list(dict.fromkeys(p.must)), should


def main():
    if len(sys.argv) != 2:
        sys.exit("用法：python3 scripts/check.py 正文.html")
    must, should = check(open(sys.argv[1], encoding="utf-8").read())
    for level, msgs in (("必须改", must), ("建议改", should)):
        for msg in msgs:
            print(level, "·", msg)
    print("Gate 1 Platform:", "FAIL" if must else "PASS（仅本地静态检查）")
    sys.exit(bool(must))


if __name__ == "__main__":
    main()
