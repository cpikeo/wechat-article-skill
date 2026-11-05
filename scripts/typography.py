#!/usr/bin/env python3
"""显示层字符政策：只改装饰性分隔，不改写事实载体，也不改写作者的标点风格。

硬边界：
- 直接引语、URL、行内代码、技术单位（mg/L、km/h、次/日）、数字比（1/2）不被斜杠规则改写。
- 引号风格属于作者：直角引号「」『』原样保留，弯引号“”‘’原样保留。把「」统一改成“”
  看似规范，实则是对作者排版习惯的机械改写——这篇文档里的引语必须逐字可核。
- 中文语境里的装饰性斜杠改为「·」。
- 「编辑说明」一类交代改稿动作的模块不属于文章，渲染时整段移除并在侧车留痕。
"""
import re
from html.parser import HTMLParser

_CJK = "\u4e00-\u9fff\u3400-\u4dbf"
DECOR_SLASH = re.compile(rf"(?<=[{_CJK}])\s*[/／]\s*(?=[{_CJK}])")
PROTECTED = re.compile(
    r"https?://[^\s<>，；。！？）\"]+|`[^`]+`|“[^”]*”|‘[^’]*’|「[^」]*」|『[^』]*』"
    r"|[A-Za-z0-9]+(?:[/／][A-Za-z0-9]+)+|\d+[/／]\d+"
)

# 单位比：两侧都是计量单位时，斜杠是比值而不是版式分隔，必须原样保留。
# 「次/日」「吨/小时」「元/度」这类写法一旦被改成分隔点，就是把技术定义写成修辞。
UNITS = {
    "次", "日", "年", "月", "周", "天", "时", "小时", "分钟", "秒", "昼夜",
    "人", "户", "家", "台", "件", "套", "吨", "公斤", "千克", "克", "斤", "担",
    "元", "角", "分", "度", "度电", "瓦", "千瓦", "兆瓦", "千瓦时", "万千瓦时",
    "米", "公里", "千米", "厘米", "毫米", "平方米", "立方米", "亩", "公顷",
    "升", "毫升", "页", "份", "项", "条", "张", "座", "班", "课时", "学分",
    "位", "只", "支", "头", "辆", "艘", "架", "门", "篇", "章", "节", "期", "卷", "本", "册", "批",
    "Wh", "kWh", "MWh", "W", "kW", "MW", "GW", "V", "A", "mAh", "Ah",
    "GB", "TB", "MB", "KB", "ms", "s", "min", "h", "km", "m", "cm", "mm", "kg", "g", "t",
    "L", "mL", "ppm", "dpi", "Hz", "rpm", "bps", "°C", "℃",
}
# 逻辑连词不是比值也不是装饰，改写会改变语义。
LOGIC_PAIRS = {"与/或", "和/或", "或/及"}
UNIT_RATIO = re.compile(r"(?<![A-Za-z0-9])([A-Za-z\u4e00-\u9fff]{1,6})\s*[/／]\s*([A-Za-z\u4e00-\u9fff]{1,6})(?![A-Za-z0-9])")

EDITORIAL_LABELS = (
    "编辑说明", "编者说明", "排版说明", "编辑手记", "编辑附记", "制作说明",
    "排版备注", "编辑备注", "修订说明", "改稿说明",
)
_EDITORIAL_HEAD = re.compile(
    r"^[\s#>*_\-─—·0-9.、（）()：:【】\[\]]*(" + "|".join(EDITORIAL_LABELS) + r")(?=$|[\s：:，,。—\-（(])"
)


def _prose(text):
    text = DECOR_SLASH.sub(" · ", text)
    return re.sub(r"(?:\s*·\s*){2,}", " · ", text)


def _spans(s):
    """所有必须原样保留的片段：URL、代码、引语、单位比、逻辑连词、数值比。"""
    spans = [m.span() for m in PROTECTED.finditer(s)]
    for m in UNIT_RATIO.finditer(s):
        left, right = m.group(1), m.group(2)
        if (left in UNITS and right in UNITS) or f"{left}/{right}" in LOGIC_PAIRS:
            spans.append(m.span())
    spans.sort()
    merged = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def publish(text):
    """归一装饰性分隔；保护引语（含直角引号）、URL、代码、单位比与数字比。"""
    if not text:
        return text
    s = text
    out, pos = [], 0
    for start, end in _spans(s):
        out.append(_prose(s[pos:start]))
        out.append(s[start:end])
        pos = end
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
