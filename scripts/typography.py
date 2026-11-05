#!/usr/bin/env python3
"""V11.1 显示层字符与署名政策（运行时唯一真源，仅标准库）。

两条硬规则，作用于「发布正文里读者能看见的字」：

1. 不用斜杠，不用直角引号。读者可见文本中不出现 `/` `／` `「` `」` `『` `』`。
   分隔语义用「·」，引述语义用中文弯引号 “ ”。
2. 不出现编辑说明。「编辑说明 / 编者说明 / 排版说明 / 编辑手记 / 制作说明」一类
   交代改稿动作的模块不属于文章，渲染时整段移除并在侧车留痕，不改写成正文。

注意：只处理文本节点，不触碰 HTML 属性，因此链接 href、资源路径与样式值不受影响。
"""
import re

# 直角引号 → 中文弯引号（单层与双层）
QUOTE_MAP = {"『": "‘", "』": "’", "「": "“", "」": "”"}

# 斜杠：半角与全角，前后空白一并收编为「·」
SLASH = re.compile(r"[ \t\u00a0\u3000]*[/／][ \t\u00a0\u3000]*")
DATE_SLASH = re.compile(r"(?<!\d)((?:19|20)\d{2})[/／](\d{1,2})[/／](\d{1,2})(?!\d)")
# 数字比：1/2、3/4 类；中文里改写成「比」更自然，其余数字斜杠退为「·」
DIGIT_RATIO = re.compile(r"(?<![\d.])(\d{1,4})/(\d{1,4})(?![\d.])")

BANNED_CHARS = ("/", "／", "「", "」", "『", "』")
BANNED_IN_TITLE = ("/", "／")

# 交代改稿动作的模块：不属于文章内容
EDITORIAL_LABELS = (
    "编辑说明", "编者说明", "排版说明", "编辑手记", "编辑附记", "制作说明",
    "排版备注", "编辑备注", "修订说明", "改稿说明",
)


def publish(text):
    """把一段读者可见纯文本归一为出版口径。行内代码与 URL 由调用方另行保护。"""
    if not text:
        return text
    s = DATE_SLASH.sub(lambda m: f"{m[1]}年{int(m[2])}月{int(m[3])}日", text)
    s = s.translate(str.maketrans(QUOTE_MAP))
    s = DIGIT_RATIO.sub(lambda m: m[1] + "比" + m[2], s)
    s = SLASH.sub(" · ", s)
    s = re.sub(r"(?:\s*·\s*){2,}", " · ", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    trimmed = re.sub(r"^\s*·\s*|\s*·\s*$", "", s)
    if trimmed.strip():
        s = trimmed
    return s.strip() if s != text else s


def is_editorial(text):
    """模块标题是否属于「编辑说明」一类需要移除的内容。"""
    head = re.sub(r"^[\s#>*_\-─—·0-9.、（）()：:【】\[\]]+", "", (text or "").strip())
    return any(head.startswith(label) for label in EDITORIAL_LABELS)


def sanitize_html(markup):
    """对 HTML 片段中的文本节点执行 publish()，属性一律不动。"""
    out, pos = [], 0
    for m in re.finditer(r"<[^>]*>", markup):
        if m.start() > pos:
            out.append(publish(markup[pos:m.start()]))
        out.append(m.group())
        pos = m.end()
    if pos < len(markup):
        out.append(publish(markup[pos:]))
    return "".join(out)


def visible_text(markup):
    """粗略可见文本：去掉标签、注释与常见实体。用于审计，不用于渲染。"""
    text = re.sub(r"<!--.*?-->", "", markup, flags=re.S)
    text = re.sub(r"<[^>]*>", "", text)
    return (text.replace("&nbsp;", " ").replace("&amp;", "&")
                .replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"'))


def violations(markup, limit=12):
    """返回可见文本中残留的禁用字符位置与上下文，供门禁与测试断言。"""
    text = visible_text(markup)
    found = []
    for i, ch in enumerate(text):
        if ch in BANNED_CHARS:
            found.append({"char": ch, "index": i, "context": text[max(0, i - 12):i + 13].replace("\n", " ")})
            if len(found) >= limit:
                break
    return found


def slash_hints(markup, limit=8):
    """斜杠改写后可读性存疑的场合（数字比），提示编辑改写成中文计量表达。"""
    hints = []
    for m in re.finditer(r"\d{1,4}比\d{1,4}", visible_text(markup)):
        hints.append(m.group())
        if len(hints) >= limit:
            break
    return hints
