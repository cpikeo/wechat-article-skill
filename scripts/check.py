#!/usr/bin/env python3
"""Gate 1：检查发布正文的确定性风险，不证明微信清洗或粘贴兼容。"""
import ipaddress
import os
import re
import sys
from html.parser import HTMLParser
from urllib.parse import urlsplit

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from safety import is_safe_relpath  # noqa: E402

CJK = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")
HALF = re.compile(r"[\u4e00-\u9fff][,;!?:]|\"|[\u4e00-\u9fff]'|'[\u4e00-\u9fff]")
TAGS = {"a", "br", "img", "p", "section", "span", "strong", "table", "td", "th", "tr"}
VOID = {"img", "br"}
ATTRS = {
    "a": {"href", "style"},
    "br": set(),
    "img": {"alt", "src", "style"},
    "p": {"style"},
    "section": {"style"},
    "span": {"leaf", "style"},
    "strong": {"style"},
    "table": {"style"},
    "td": {"style"},
    "th": {"style"},
    "tr": {"style"},
}
REQUIRED = {
    "a": {"href", "style"}, "img": {"alt", "src", "style"},
    "p": {"style"}, "section": {"style"}, "strong": {"style"},
    "table": {"style"}, "td": {"style"}, "th": {"style"},
}
PARENTS = {
    "a": {"p", "span", "strong", "td", "th"},
    "br": {"", "section", "p", "span", "strong", "a", "td", "th"},
    "img": {"section"},
    "p": {"", "section", "td", "th"},
    "section": {"", "section"},
    "span": {"", "section", "p", "span", "strong", "a", "td", "th"},
    "strong": {"p", "span", "strong", "a", "td", "th"},
    "table": {"", "section"},
    "td": {"tr"},
    "th": {"tr"},
    "tr": {"table"},
}

HEX = r"#[0-9a-fA-F]{6}"
SANS = "-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei','Source Han Sans SC','Noto Sans CJK SC',sans-serif"
SERIF = "'Songti SC','STSong','SimSun','Source Han Serif SC','Noto Serif CJK SC',serif"
MONO = "'SF Mono',Menlo,Consolas,monospace"
FONT_FAMILIES = {SANS, SERIF, MONO}


def _length(value, units=("px", "em", "%"), *, negative=False, auto=False,
            max_px=300, max_em=4, max_pct=100):
    if auto and value == "auto":
        return True
    if value == "0":
        return True
    m = re.fullmatch(r"(-?)(\d+(?:\.\d+)?)(px|em|%)", value)
    if not m:
        return False
    sign, number, unit = m.groups()
    n = float(number)
    if sign and not negative:
        return False
    limit = {"px": max_px, "em": max_em, "%": max_pct}.get(unit)
    return unit in units and n <= limit


def _length_list(value, *, auto=False, max_px=300, max_em=4, max_pct=100):
    parts = value.split()
    return (1 <= len(parts) <= 4 and all(
        _length(part, auto=auto, max_px=max_px, max_em=max_em, max_pct=max_pct)
        for part in parts))


def _border(value):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)px\s+(solid|dashed)\s+(" + HEX + r")", value, re.I)
    return bool(m and 0 < float(m.group(1)) <= 8)


def _font_size(value):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)px", value)
    return bool(m and 12 <= float(m.group(1)) <= 64)


def _line_height(value):
    m = re.fullmatch(r"(\d+(?:\.\d+)?)(px)?", value)
    if not m:
        return False
    number = float(m.group(1))
    return (12 <= number <= 100) if m.group(2) else (0.8 <= number <= 3)


def _letter_spacing(value):
    if value == "normal":
        return True
    m = re.fullmatch(r"-?(\d+(?:\.\d+)?)(px|em)", value)
    return bool(m and float(m.group(1)) <= (10 if m.group(2) == "px" else 1))


CSS_RULES = {
    "align-items": lambda v: v in {"baseline", "center", "flex-end", "flex-start"},
    "background": lambda v: bool(re.fullmatch(HEX, v)),
    "border": _border,
    "border-bottom": _border,
    "border-collapse": lambda v: v == "collapse",
    "border-left": _border,
    "border-radius": lambda v: _length(v, ("px", "%"), max_px=100, max_pct=100),
    "border-top": _border,
    "box-sizing": lambda v: v == "border-box",
    "color": lambda v: bool(re.fullmatch(HEX, v)) or v == "inherit",
    "display": lambda v: v in {"block", "flex", "inline-block"},
    "flex": lambda v: v == "1",
    "flex-shrink": lambda v: v == "0",
    "font-family": lambda v: v in FONT_FAMILIES,
    "font-size": _font_size,
    "font-style": lambda v: v in {"italic", "normal"},
    "font-variant-numeric": lambda v: v == "tabular-nums",
    "font-weight": lambda v: v in {"400", "500", "600", "700"},
    "gap": lambda v: bool(re.fullmatch(r"\d+(?:\.\d+)?px", v)) and float(v[:-2]) <= 100,
    "height": lambda v: _length(v, ("px",), auto=True, max_px=1000),
    "justify-content": lambda v: v in {"space-between"},
    "letter-spacing": _letter_spacing,
    "line-break": lambda v: v == "strict",
    "line-height": _line_height,
    "margin": lambda v: _length_list(v, auto=True),
    "margin-bottom": lambda v: _length(v),
    "margin-left": lambda v: _length(v),
    "margin-right": lambda v: _length(v),
    "margin-top": lambda v: _length(v),
    "max-width": lambda v: v == "100%",
    "min-width": lambda v: v == "0",
    "overflow": lambda v: v == "hidden",
    "overflow-wrap": lambda v: v in ("break-word", "anywhere"),
    "padding": lambda v: _length_list(v, max_px=100, max_em=2),
    "padding-bottom": lambda v: _length(v, max_px=100, max_em=2),
    "padding-left": lambda v: _length(v, max_px=100, max_em=2),
    "padding-right": lambda v: _length(v, max_px=100, max_em=2),
    "padding-top": lambda v: _length(v, max_px=100, max_em=2),
    "tab-size": lambda v: bool(re.fullmatch(r"[1-8]", v)),
    "table-layout": lambda v: v == "fixed",
    "text-align": lambda v: v in {"left", "center", "right"},
    "text-decoration": lambda v: v in {"line-through", "underline"},
    "text-indent": lambda v: _length(v, ("px", "em"), negative=True, max_px=100, max_em=3),
    "vertical-align": lambda v: v in {"top", "middle", "bottom", "baseline"} or
        _length(v, ("px", "em"), negative=True, max_px=100, max_em=2),
    "white-space": lambda v: v in {"nowrap", "pre-wrap"},
    "width": lambda v: _length(v, ("px", "%"), max_px=1000, max_pct=100),
    "word-break": lambda v: v == "normal",
}


def _parse_style(style):
    props, issues = {}, []
    if not isinstance(style, str) or not style.strip():
        return props, ["style 为空"]
    declarations = style.split(";")
    for i, declaration in enumerate(declarations):
        if not declaration.strip():
            if i != len(declarations) - 1:
                issues.append("style 含空声明")
            continue
        if ":" not in declaration:
            issues.append(f"style 声明格式错误：{declaration[:24]}")
            continue
        name, value = (part.strip() for part in declaration.split(":", 1))
        name, value = name.lower(), value.strip()
        if name not in CSS_RULES:
            issues.append(f"CSS 属性不在允许列表：{name}")
        elif name in props:
            issues.append(f"CSS 属性重复：{name}")
        elif not value or not CSS_RULES[name](value):
            issues.append(f"CSS 值不在允许范围：{name}: {value[:32]}")
        props[name] = value
    return props, issues


def safe_http_url(value):
    if not isinstance(value, str) or not value or value != value.strip():
        return False
    if any(ord(c) < 0x20 or ord(c) == 0x7f for c in value) or any(c.isspace() for c in value) or "\\" in value:
        return False
    if any(c in value for c in '<>"`'):
        return False
    try:
        parts = urlsplit(value)
        port = parts.port
        host = (parts.hostname or "").lower()
        authority = parts.netloc.rsplit("@", 1)[-1]
        if not (parts.scheme.lower() in {"http", "https"} and host
                and parts.username is None and parts.password is None
                and not authority.endswith(":") and (port is None or 1 <= port <= 65535)):
            return False
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            return False
        try:
            return ipaddress.ip_address(host).is_global
        except ValueError:
            labels = host.split(".")
            return (len(labels) >= 2 and all(
                re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label)
                for label in labels) and not labels[-1].isdigit())
    except ValueError:
        return False


def source_urls(text):
    """Extract syntactically valid links; existence and factual support remain UNVERIFIED."""
    return [url for raw in re.findall(r"https?://[^\s<>，；。！？）\"]+", text)
            if safe_http_url(url := raw.rstrip(".,;:!?)]}"))]


class Leaf(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        # Stack frame: [tag, is_leaf_span, is_mono, has_content]
        self.stack, self.must, self.half, self.images = [], [], [], []
        self.empty_decoration = False

    def _mark_nonempty(self):
        for frame in self.stack:
            frame[3] = True

    def handle_starttag(self, tag, attrs):
        names = [name for name, _ in attrs]
        if len(names) != len(set(names)):
            self.must.append(f"{tag} 含重复属性")
        a = dict(attrs)
        if tag not in TAGS:
            self.must.append(f"标签不在允许列表：{tag}")
        unknown = set(a) - ATTRS.get(tag, set())
        if unknown:
            self.must.append(f"{tag} 属性不在允许列表：{'、'.join(sorted(unknown))}")
        missing = REQUIRED.get(tag, set()) - set(a)
        if missing:
            self.must.append(f"{tag} 缺少必需属性：{'、'.join(sorted(missing))}")
        parent = self.stack[-1][0] if self.stack else ""
        if tag in PARENTS and parent not in PARENTS[tag]:
            self.must.append(f"标签嵌套不在允许结构：{parent or '正文根'} > {tag}")

        if tag == "span" and "leaf" in a and a["leaf"] not in (None, ""):
            self.must.append("span[leaf] 只能为空标记")
        if tag == "span" and not ("leaf" in a or "style" in a):
            self.must.append("span 缺少 leaf 或 style")

        props = {}
        if "style" in a:
            props, problems = _parse_style(a.get("style"))
            self.must.extend(problems)
        if tag == "a" and not safe_http_url(a.get("href")):
            self.must.append("a href 只允许带有效主机名的 HTTP(S) URL")
        if tag == "img":
            src = a.get("src") or ""
            alt = a.get("alt") or ""
            self.images.append(src)
            if not is_safe_relpath(src):
                self.must.append(f"图片必须是安全的相对本地路径：{src}")
            if not alt.strip():
                self.must.append("图片必须有非空 alt 描述")
            if props.get("max-width") != "100%":
                self.must.append("图片缺少 max-width:100%")
            if props.get("height") != "auto":
                self.must.append("图片必须保持 height:auto")
        if tag in VOID:
            self._mark_nonempty()
        else:
            self.stack.append([
                tag,
                tag == "span" and "leaf" in a,
                bool(re.search("monospace", props.get("font-family", ""), re.I)),
                False,
            ])

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag in VOID:
            self.must.append(f"空元素不应有结束标签：{tag}")
            return
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                if i != len(self.stack) - 1:
                    self.must.append(f"标签嵌套顺序错误：{self.stack[-1][0]} 在 {tag} 前未闭合")
                for closed in self.stack[i:]:
                    if closed[0] in ("section", "span") and not closed[3]:
                        self.empty_decoration = True
                del self.stack[i:]
                return
        self.must.append(f"多余结束标签：{tag}")

    def handle_data(self, data):
        if not data:
            return
        # Intentional whitespace inside a `<span leaf="">` separates adjacent inline nodes.
        if self.stack and self.stack[-1][1]:
            self._mark_nonempty()
        t = data.strip()
        if not t:
            return
        self._mark_nonempty()
        if not any(x[1] for x in self.stack):
            self.must.append(f"文字未包 <span leaf>：{t[:20]}")
        if not any(x[2] for x in self.stack) and CJK.search(t) and HALF.search(re.sub(r'https?://[^\s<>，；。！？）"]+', "", t)):
            self.half.append(t[:20])

    def handle_comment(self, data):
        self.must.append("正文不允许 HTML 注释")

    def handle_decl(self, decl):
        self.must.append("正文不允许 HTML 声明")

    def handle_pi(self, data):
        self.must.append("正文不允许处理指令")


def image_sources(html):
    p = Leaf()
    p.feed(html)
    p.close()
    return p.images


def check(html):
    p = Leaf()
    p.feed(html)
    p.close()
    if p.stack:
        p.must.append("标签未闭合：" + " > ".join(x[0] for x in p.stack))
    if p.empty_decoration:
        p.must.append('空装饰元素缺少 <span leaf=""><br></span>')
    should = [f"待人工核对的半角标点/直引号（URL/引文可保留）：{p.half[:3]}"] if p.half else []
    return list(dict.fromkeys(p.must)), should


def main():
    if len(sys.argv) != 2:
        sys.exit("用法：python3 scripts/check.py 正文.html")
    with open(sys.argv[1], encoding="utf-8") as f:
        must, should = check(f.read())
    for level, msgs in (("必须改", must), ("建议改", should)):
        for msg in msgs:
            print(level, "·", msg)
    print("Gate 1 Platform:", "FAIL" if must else "PASS（仅本地静态检查）")
    sys.exit(bool(must))


if __name__ == "__main__":
    main()
