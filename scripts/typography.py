#!/usr/bin/env python3
"""V12 显示层字符政策：只改装饰性分隔与编辑说明，不改写事实载体。

硬边界：
- 直接引语、URL、行内代码、技术单位（mg/L、km/h）、数字比（1/2）不被斜杠规则改写。
- 中文语境里的装饰性斜杠改为「·」；直角引号归一为中文弯引号，但引语内部文字不动。
- 「编辑说明」一类交代改稿动作的模块不属于文章，渲染时整段移除并在侧车留痕。
"""
import re
from html.parser import HTMLParser

QUOTE_MAP = {"『": "‘", "』": "’", "「": "“", "」": "”"}
_CJK = "\u4e00-\u9fff\u3400-\u4dbf"
DATE_SLASH = re.compile(rf"(?<!\d)((?:19|20)\d{{2}})[/／](\d{{1,2}})[/／](\d{{1,2}})(?!\d)")
DECOR_SLASH = re.compile(rf"(?<=[{_CJK}])\s*[/／]\s*(?=[{_CJK}])")
PROTECTED = re.compile(
    r"https?://[^\s<>，；。！？）\"]+|`[^`]+`|“[^”]*”|‘[^’]*’"
    r"|[A-Za-z0-9]+(?:[/／][A-Za-z0-9]+)+|\d+[/／]\d+"
)
EDITORIAL_LABELS = (
    "编辑说明", "编者说明", "排版说明", "编辑手记", "编辑附记", "制作说明",
    "排版备注", "编辑备注", "修订说明", "改稿说明",
)
_EDITORIAL_HEAD = re.compile(
    r"^[\s#>*_\-─—·0-9.、（）()：:【】\[\]]*(" + "|".join(EDITORIAL_LABELS) + r")(?=$|[\s：:，,。—\-（(])"
)


def _prose(text):
    text = DATE_SLASH.sub(lambda m: f"{m[1]}年{int(m[2])}月{int(m[3])}日", text)
    text = DECOR_SLASH.sub(" · ", text)
    return re.sub(r"(?:\s*·\s*){2,}", " · ", text)


def publish(text):
    """归一装饰性分隔；保护引语、URL、代码、单位与数字比。"""
    if not text:
        return text
    s = text.translate(str.maketrans(QUOTE_MAP))
    out, pos = [], 0
    for m in PROTECTED.finditer(s):
        out.append(_prose(s[pos:m.start()]))
        out.append(m.group())
        pos = m.end()
    out.append(_prose(s[pos:]))
    return "".join(out)


def is_editorial(text):
    """模块标题是否属于「编辑说明」；要求标签后有边界，避免误伤正常句子。"""
    return bool(_EDITORIAL_HEAD.match((text or "").strip()))


class _Sanitizer(HTMLParser):
    """只处理文本节点；等宽代码块内的斜杠、引号与单位原样保留。"""

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out, self.spans = [], []

    def handle_starttag(self, tag, attrs):
        self.out.append(self.get_starttag_text())
        if tag == "span":
            style = dict(attrs).get("style") or ""
            self.spans.append(bool(self.spans and self.spans[-1]) or "monospace" in style)
        elif tag not in ("img", "br"):
            self.spans.append(False)

    def handle_startendtag(self, tag, attrs):
        self.out.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.out.append(f"</{tag}>")
        if self.spans:
            self.spans.pop()

    def handle_data(self, data):
        code = bool(self.spans and self.spans[-1])
        self.out.append(data if code else publish(data))

    def handle_entityref(self, name):
        self.out.append(f"&{name};")

    def handle_charref(self, name):
        self.out.append(f"&#{name};")


def sanitize_html(markup):
    parser = _Sanitizer()
    parser.feed(markup)
    parser.close()
    return "".join(parser.out)

