#!/usr/bin/env python3
"""Word .docx → Markdown 提取器（零外部依赖）。

格式归一化层的确定性组件：把 docx 的标题层级 / 粗体 / 列表 / 图片
转成本 skill 排版流程认识的 Markdown。

用法：
    extract_docx.py 文章.docx [-o 输出.md]
    # 内嵌图片解包到 输出.md 同目录的 images/ 下，md 里用相对路径引用

退出码：0 成功；1 失败（文件不存在 / 不是合法 docx）。
普通表格转成 Markdown；合并单元格、文本框等不能保真的结构定位报错，不静默跳过。
抽完只是素材，不是成稿：图片必须补职责（![说明](路径 "职责")），文字还要走一遍 EDIT。
"""

import argparse
import os
import posixpath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

from check import safe_http_url

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"


# Numbering formats with deterministic visible labels. Unknown Word formats fail closed:
# silently converting them to a bullet list changes reading order and hierarchy.
ORDERED_FORMATS = {
    "decimal", "decimalZero", "upperLetter", "lowerLetter", "upperRoman", "lowerRoman",
    "chineseCounting", "chineseCountingThousand", "chineseLegalSimplified", "ordinal", "ordinalText",
}
COMMON_BULLETS = {"•"}


def load_styles(z):
    """styleId → 标题级别（1/2/3…）；非标题样式不入表。"""
    levels = {}
    try:
        root = ET.fromstring(z.read("word/styles.xml"))
    except KeyError:
        return levels
    for st in root.iter(f"{W}style"):
        sid = st.get(f"{W}styleId") or ""
        name_el = st.find(f"{W}name")
        name = (name_el.get(f"{W}val") if name_el is not None else "") or ""
        match = re.search(r"(?:heading|标题)\s*([1-6])", name, re.I) \
            or re.fullmatch(r"([1-6])", sid)
        if match:
            levels[sid] = int(match.group(1))
    return levels


def _word_int(element, label, default=None, attribute="val"):
    """Read a w:val (or named w: attribute) integer with a useful local error."""
    if element is None:
        return default
    raw = element.get(f"{W}{attribute}")
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Word 编号字段 {label} 不是整数：{raw!r}") from error


def _level_definition(level):
    ilvl = _word_int(level, "ilvl", 0, attribute="ilvl")
    if not 0 <= ilvl <= 8:
        raise ValueError(f"Word 列表层级超出 0–8：{ilvl}")
    fmt_el = level.find(f"{W}numFmt")
    text_el = level.find(f"{W}lvlText")
    start_el = level.find(f"{W}start")
    restart_el = level.find(f"{W}lvlRestart")
    restart = _word_int(restart_el, "lvlRestart", None)
    if restart is not None and not 0 <= restart <= 9:
        raise ValueError(f"Word 编号 lvlRestart 超出 0–9：{restart}")
    rpr = level.find(f"{W}rPr")
    fonts = rpr.find(f"{W}rFonts") if rpr is not None else None
    bullet_font = (fonts.get(f"{W}ascii") or fonts.get(f"{W}hAnsi") or "") if fonts is not None else ""
    return {
        "ilvl": ilvl,
        "format": fmt_el.get(f"{W}val") if fmt_el is not None else "",
        "text": text_el.get(f"{W}val") if text_el is not None else "",
        "bullet_font": bullet_font,
        "start": _word_int(start_el, "start", 1),
        "restart": restart,
    }


def load_numbering(z):
    """Load abstractNum/num/lvl and per-num overrides from word/numbering.xml."""
    try:
        root = ET.fromstring(z.read("word/numbering.xml"))
    except KeyError:
        return {"abstract": {}, "nums": {}}
    abstract = {}
    for node in root.findall(f"{W}abstractNum"):
        abstract_id = node.get(f"{W}abstractNumId")
        if abstract_id is None:
            raise ValueError("abstractNum 缺少 abstractNumId")
        if abstract_id in abstract:
            raise ValueError(f"numbering.xml 中 abstractNumId 重复：{abstract_id}")
        if node.find(f"{W}numStyleLink") is not None:
            # Resolving linked numbering styles requires style-linked numbering parts.
            # Fail closed instead of silently treating it as a default decimal list.
            abstract[abstract_id] = {"levels": {}, "style_link": True}
            continue
        levels = {}
        for level in node.findall(f"{W}lvl"):
            definition = _level_definition(level)
            if definition["ilvl"] in levels:
                raise ValueError(f"abstractNum={abstract_id} 的 ilvl={definition['ilvl']} 重复")
            levels[definition["ilvl"]] = definition
        abstract[abstract_id] = {"levels": levels, "style_link": False}
    nums = {}
    for node in root.findall(f"{W}num"):
        num_id = node.get(f"{W}numId")
        abstract_id = node.find(f"{W}abstractNumId")
        if num_id is None or abstract_id is None or abstract_id.get(f"{W}val") is None:
            raise ValueError("num 缺少 numId 或 abstractNumId")
        if num_id in nums:
            raise ValueError(f"numbering.xml 中 numId 重复：{num_id}")
        overrides = {}
        for override in node.findall(f"{W}lvlOverride"):
            ilvl = _word_int(override, "lvlOverride.ilvl", None, attribute="ilvl")
            if ilvl is None or not 0 <= ilvl <= 8:
                raise ValueError(f"lvlOverride 层级无效：{ilvl}")
            if ilvl in overrides:
                raise ValueError(f"numId={num_id} 的 lvlOverride ilvl={ilvl} 重复")
            lvl = override.find(f"{W}lvl")
            start = override.find(f"{W}startOverride")
            overrides[ilvl] = {
                "level": _level_definition(lvl) if lvl is not None else None,
                "start": _word_int(start, "startOverride", None),
            }
        nums[num_id] = {"abstract_id": abstract_id.get(f"{W}val"), "overrides": overrides}
    return {"abstract": abstract, "nums": nums}


def load_style_numpr(z):
    """styleId → basedOn/numId/ilvl; paragraph direct numbering may override either."""
    try:
        root = ET.fromstring(z.read("word/styles.xml"))
    except KeyError:
        return {}
    styles = {}
    for style in root.findall(f"{W}style"):
        style_id = style.get(f"{W}styleId")
        if not style_id:
            continue
        based = style.find(f"{W}basedOn")
        ppr = style.find(f"{W}pPr")
        numpr = ppr.find(f"{W}numPr") if ppr is not None else None
        fields = {}
        if numpr is not None:
            for key, tag in (("num_id", "numId"), ("ilvl", "ilvl")):
                value = numpr.find(f"{W}{tag}")
                if value is not None:
                    fields[key] = _word_int(value, f"style.{style_id}.{tag}", None)
        styles[style_id] = {
            "based_on": based.get(f"{W}val") if based is not None else None,
            "numpr": fields,
        }
    return styles


def _numpr_fields(ppr):
    numpr = ppr.find(f"{W}numPr") if ppr is not None else None
    if numpr is None:
        return {}
    fields = {}
    for key, tag in (("num_id", "numId"), ("ilvl", "ilvl")):
        value = numpr.find(f"{W}{tag}")
        if value is not None:
            fields[key] = _word_int(value, f"numPr.{tag}", None)
    return fields


def resolve_numpr(paragraph, styles):
    """Resolve paragraph/style numbering without discarding either numId or ilvl."""
    ppr = paragraph.find(f"{W}pPr")
    style_el = ppr.find(f"{W}pStyle") if ppr is not None else None
    style_id = style_el.get(f"{W}val") if style_el is not None else ""
    inherited, seen, current = {}, set(), style_id
    while current and current not in seen:
        seen.add(current)
        style = styles.get(current, {})
        for key, value in style.get("numpr", {}).items():
            inherited.setdefault(key, value)
        current = style.get("based_on")
    resolved = {**inherited, **_numpr_fields(ppr)}
    if resolved.get("num_id") == 0:
        return None
    if "num_id" in resolved:
        resolved.setdefault("ilvl", 0)
        return resolved
    if re.search(r"(?i)list|列表", style_id):
        raise ValueError(f"列表样式 {style_id} 没有可解析的 numId，拒绝静默展平")
    if "ilvl" in resolved:
        raise ValueError(f"段落 {style_id or '(默认样式)'} 有 ilvl 但没有 numId")
    return None


def load_rels(z):
    """rId → 媒体文件路径（word/media/...）。"""
    rels = {}
    try:
        root = ET.fromstring(z.read("word/_rels/document.xml.rels"))
    except KeyError:
        return rels
    for rel in root:
        target = rel.get("Target") or ""
        if rel.get("TargetMode") == "External":
            continue
        resolved = posixpath.normpath(posixpath.join("word", target))
        if resolved.startswith("word/media/") and ".." not in resolved.split("/"):
            rels[rel.get("Id")] = resolved
    return rels


def load_links(z):
    """外部超链接 rId → URL；与正文/发布预检共用 URL 安全边界。"""
    try:
        root = ET.fromstring(z.read("word/_rels/document.xml.rels"))
    except KeyError:
        return {}
    links = {}
    for rel in root:
        if not rel.get("Type", "").endswith("/hyperlink"):
            continue
        target = rel.get("Target", "")
        if not safe_http_url(target):
            raise ValueError(f"不支持的超链接：{target}")
        rid = rel.get("Id")
        if not rid:
            raise ValueError("超链接缺少关系 ID")
        links[rid] = target.replace("(", "%28").replace(")", "%29")
    return links


def _alpha_number(value, upper=False):
    out = ""
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        out = chr((65 if upper else 97) + remainder) + out
    return out


def _roman_number(value, upper=False):
    if not 1 <= value <= 3999:
        raise ValueError(f"罗马数字编号超出 1–3999：{value}")
    pairs = ((1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"),
             (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"),
             (5, "V"), (4, "IV"), (1, "I"))
    out = []
    for number, glyph in pairs:
        count, value = divmod(value, number)
        out.append(glyph * count)
    result = "".join(out)
    return result if upper else result.lower()


def _chinese_number(value, formal=False):
    if not 0 <= value <= 9999:
        raise ValueError(f"中文数字编号超出 0–9999：{value}")
    digits = "零壹贰叁肆伍陆柒捌玖" if formal else "零一二三四五六七八九"
    units = ("仟", "佰", "拾") if formal else ("千", "百", "十")
    if value == 0:
        return digits[0]
    parts, zero_pending = [], False
    for power, unit in zip((1000, 100, 10), units):
        digit, value = divmod(value, power)
        if digit:
            if zero_pending and parts:
                parts.append(digits[0])
            # Standard Chinese counting omits 一 in 10–19; legal-form numerals do not.
            if not (power == 10 and digit == 1 and not parts and not formal):
                parts.append(digits[digit])
            parts.append(unit)
            zero_pending = False
        elif parts and value:
            zero_pending = True
    if value:
        if zero_pending:
            parts.append(digits[0])
        parts.append(digits[value])
    return "".join(parts)


def _format_number(fmt, value):
    if fmt == "decimal":
        return str(value)
    if fmt == "decimalZero":
        return f"{value:02d}"
    if fmt == "upperLetter":
        return _alpha_number(value, upper=True)
    if fmt == "lowerLetter":
        return _alpha_number(value)
    if fmt == "upperRoman":
        return _roman_number(value, upper=True)
    if fmt == "lowerRoman":
        return _roman_number(value)
    if fmt in ("chineseCounting", "chineseCountingThousand"):
        return _chinese_number(value)
    if fmt == "chineseLegalSimplified":
        return _chinese_number(value, formal=True)
    if fmt == "ordinal":
        suffix = "th" if 10 <= value % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
        return f"{value}{suffix}"
    if fmt == "ordinalText":
        words = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth",
                 6: "sixth", 7: "seventh", 8: "eighth", 9: "ninth", 10: "tenth"}
        if value not in words:
            raise ValueError(f"当前仅能无歧义还原 1–10 的 ordinalText，遇到 {value}")
        return words[value]
    raise ValueError(f"不支持的 Word 编号格式：{fmt or '(空)'}")


class NumberingState:
    """Per-numId counters with start overrides, nested-level restart, and marker formats."""

    def __init__(self, definitions):
        self.definitions = definitions
        self.states = {}

    def level(self, num_id, ilvl):
        num = self.definitions["nums"].get(str(num_id))
        if num is None:
            raise ValueError(f"numId={num_id} 不存在于 numbering.xml")
        abstract = self.definitions["abstract"].get(num["abstract_id"])
        if abstract is None:
            raise ValueError(f"numId={num_id} 引用缺失 abstractNum={num['abstract_id']}")
        if abstract.get("style_link"):
            raise ValueError(f"numId={num_id} 使用 numStyleLink，当前无法无损展开")
        base = abstract["levels"].get(ilvl)
        override = num["overrides"].get(ilvl, {})
        if override.get("level") is not None:
            base = {**(base or {}), **override["level"]}
        if base is None:
            raise ValueError(f"abstractNum={num['abstract_id']} 缺少 ilvl={ilvl} 定义")
        definition = dict(base)
        if override.get("start") is not None:
            definition["start"] = override["start"]
        fmt = definition.get("format", "")
        if fmt != "bullet" and fmt not in ORDERED_FORMATS:
            raise ValueError(f"numId={num_id} ilvl={ilvl} 使用不支持的 numFmt={fmt!r}，已阻断转换")
        if fmt == "bullet" and not definition.get("text"):
            definition["text"] = "•"
        if fmt != "bullet" and not definition.get("text"):
            definition["text"] = f"%{ilvl + 1}."
        return definition

    def next_item(self, num_id, ilvl):
        num_id = str(num_id)
        definition = self.level(num_id, ilvl)
        state = self.states.setdefault(num_id, {"values": {}})
        values = state["values"]
        fmt = definition["format"]
        # A higher-level item can restart deeper levels even when that parent is a bullet.
        for deeper in list(values):
            if deeper <= ilvl:
                continue
            deeper_def = self.level(num_id, deeper)
            restart = deeper_def["restart"]
            should_restart = (ilvl < deeper) if restart is None else (restart > 0 and ilvl == restart - 1)
            if should_restart:
                values.pop(deeper, None)
        if fmt == "bullet":
            visible = definition["text"]
            if visible == "\uf0b7" and definition.get("bullet_font") in {"Symbol", "Wingdings"}:
                visible = "•"
            if any(0xE000 <= ord(ch) <= 0xF8FF for ch in visible):
                raise ValueError(f"bullet 编号使用未映射私用区字形 {visible!r}；无法保证移动端可见")
            marker = None if visible in COMMON_BULLETS else visible
            return {"num_id": num_id, "ilvl": ilvl, "value": None, "ordered": False,
                    "marker": marker, "markdown_number": None}

        start = definition["start"]
        if not 1 <= start <= 999999:
            raise ValueError(f"Word 编号起始值超出安全范围：{start}")
        value = start if ilvl not in values else values[ilvl] + 1
        values[ilvl] = value

        def label_for_level(level_index):
            level = self.level(num_id, level_index)
            value_at_level = values.get(level_index, level["start"])
            if level["format"] == "bullet":
                visible_bullet = level["text"]
                if visible_bullet == "\uf0b7" and level.get("bullet_font") in {"Symbol", "Wingdings"}:
                    visible_bullet = "•"
                if any(0xE000 <= ord(ch) <= 0xF8FF for ch in visible_bullet):
                    raise ValueError(f"自定义编号模板引用未映射私用区字形 {visible_bullet!r}")
                return visible_bullet
            return _format_number(level["format"], value_at_level)

        pattern = definition["text"]
        visible = re.sub(r"%([1-9])", lambda m: label_for_level(int(m.group(1)) - 1), pattern)
        if "%" in re.sub(r"%[1-9]", "", pattern):
            raise ValueError(f"Word 编号模板无法解析：{pattern!r}")
        if "⟦" in visible or "⟧" in visible or "\n" in visible:
            raise ValueError(f"Word 自定义编号含无法安全保留的字符：{visible!r}")
        standard_decimal = fmt == "decimal" and pattern == f"%{ilvl + 1}."
        custom_marker = None if standard_decimal else visible
        # Standard decimal lists remain ordinary Markdown ordered lists. Other Word formats
        # use a numeric structural marker plus a visible override (e.g. ⟦A.⟧), preserving
        # both list semantics and the original label without inventing renderer behaviour.
        markdown_number = value
        return {"num_id": num_id, "ilvl": ilvl, "value": value, "ordered": True,
                "marker": custom_marker, "markdown_number": markdown_number}


def para_text(p, links=None):
    """段内 run → 行内 Markdown（粗体→**、下划线→<u>）。"""
    links = links or {}
    out = []
    run_links = {id(run): links.get(h.get(f"{R}id"), "")
                 for h in p.iter(f"{W}hyperlink") for run in h.iter(f"{W}r")}
    for r_el in p.iter(f"{W}r"):
        rpr = r_el.find(f"{W}rPr")
        bold = rpr is not None and rpr.find(f"{W}b") is not None \
            and (rpr.find(f"{W}b").get(f"{W}val") or "1") not in ("0", "false")
        underline = rpr is not None and rpr.find(f"{W}u") is not None \
            and rpr.find(f"{W}u").get(f"{W}val") != "none"
        text = "".join(
            (node.text or "") if node.tag == f"{W}t"
            else "\n" if node.tag == f"{W}br"
            else "\t" if node.tag == f"{W}tab" else ""
            for node in r_el
        )
        if not text:
            continue
        if bold:
            text = f"**{text}**"
        if underline:
            text = f"<u>{text}</u>"
        url = run_links.get(id(r_el))
        if url:
            text = f"[{text}]({url})"
        out.append(text)
    return re.sub(r"\*\*\*\*", "", "".join(out))  # 相邻粗体 run 合并的空标记


def image_alt(p, rid):
    """取 rid 对应图片的替换文字（docPr 的 descr / title）。"""
    for tag in ("inline", "anchor"):
        for container in p.iter(f"{WP}{tag}"):
            if not any(blip.get(f"{R}embed") == rid for blip in container.iter(f"{A}blip")):
                continue
            doc_pr = container.find(f"{WP}docPr")
            if doc_pr is not None:
                return (doc_pr.get("descr") or doc_pr.get("title") or "").strip()
    return ""


def validate_body(z, body, links, media_of, style_numpr=None):
    """写出前定位所有不可保真的结构；返回空列表才允许继续。"""
    style_numpr = style_numpr or {}
    unsupported = {"txbxContent", "altChunk", "footnoteReference", "endnoteReference",
                   "gridSpan", "vMerge", "ins", "del", "fldChar", "chart", "diagram",
                   "pict", "object", "oMath", "sdt"}
    names = set(z.namelist())
    problems = []
    for index, el in enumerate(body, 1):
        tags = {node.tag.split("}")[-1] for node in el.iter()}
        bad = sorted(tags & unsupported)
        if el.tag == f"{W}p":
            try:
                numbering_info = resolve_numpr(el, style_numpr)
                if numbering_info is not None:
                    if list(el.iter(f"{A}blip")):
                        bad.append("编号列表项含图片（当前无法保证图片与编号项的顺序）")
                    if not para_text(el, links).strip():
                        bad.append("空编号列表项")
            except ValueError as error:
                bad.append(str(error))
        if el.tag == f"{W}tbl":
            if any(tc.findall(f".//{A}blip") for tc in el.iter(f"{W}tc")):
                bad.append("表格内图片")
            widths = [len(row.findall(f"{W}tc")) for row in el.findall(f"{W}tr")]
            if widths and (not widths[0] or any(width != widths[0] for width in widths)):
                bad.append("表格行列不齐")
            if any(len(tc.findall(f"{W}p")) > 1 for tc in el.iter(f"{W}tc")):
                bad.append("单元格多段落")
            if any(node.tag in (f"{W}br", f"{W}tab")
                   for tc in el.iter(f"{W}tc") for node in tc.iter()):
                bad.append("单元格内换行或制表符")
            try:
                if any(resolve_numpr(p, style_numpr) is not None for p in el.iter(f"{W}p")):
                    bad.append("表格单元格中的编号列表（目前拒绝静默展平）")
            except ValueError as error:
                bad.append(str(error))
        if len(list(el.iter(f"{W}tbl"))) > (1 if el.tag == f"{W}tbl" else 0):
            bad.append("嵌套表格")
        if bad:
            problems.append(f"正文块 {index}：{', '.join(bad)}")
        if el.tag not in {f"{W}p", f"{W}tbl", f"{W}sectPr"}:
            problems.append(f"正文块 {index}：不支持的顶层结构 {el.tag}")
        for hyperlink in el.iter(f"{W}hyperlink"):
            if hyperlink.get(f"{R}id") not in links:
                problems.append(f"正文块 {index}：内部锚点或缺失的链接关系")
        for blip in el.iter(f"{A}blip"):
            src = media_of.get(blip.get(f"{R}embed"))
            if not src or src not in names:
                problems.append(f"正文块 {index}：外链图片或缺失素材关系")
    return problems


def notes_with_text(z):
    """列出含正文的脚注、尾注或批注部件；这些不能被静默丢弃。"""
    found = []
    for name in z.namelist():
        if not re.match(r"word/(?:footnotes|endnotes|comments).*\.xml$", name):
            continue
        try:
            root = ET.fromstring(z.read(name))
        except ET.ParseError as error:
            raise ValueError(f"注释部件 XML 无效：{name}") from error
        if any((node.text or "").strip() for node in root.iter(f"{W}t")):
            found.append(name)
    return found


def plan_images(z, body, img_dir, media_of):
    """先读完并检查全部图片，再允许任何文件写入，避免半成品覆盖。"""
    planned = []
    for paragraph in body.iter(f"{W}p"):
        for blip in paragraph.iter(f"{A}blip"):
            src = media_of.get(blip.get(f"{R}embed"))
            if not src:
                continue
            target = os.path.join(img_dir, f"{len(planned) + 1:02d}-" + os.path.basename(src))
            data = z.read(src)
            if os.path.exists(target):
                with open(target, "rb") as existing:
                    if existing.read() != data:
                        raise ValueError(f"输出图片同名不同内容，拒绝覆盖：{target}")
            planned.append((target, data))
    return planned


def write_images(out_dir, img_dir, planned):
    os.makedirs(out_dir, exist_ok=True)
    if planned:
        os.makedirs(img_dir, exist_ok=True)
    for target, data in planned:
        with open(target, "wb") as output:
            output.write(data)


def table_lines(table, links):
    """普通表格保住行列；复杂表格已在 validate_body 拦截。"""
    source_rows = table.findall(f"{W}tr")
    if not source_rows:
        return []
    rows = []
    for row in source_rows:
        cells = [" / ".join(para_text(p, links) for p in cell.findall(f"{W}p"))
                 .strip().replace("|", "\\|") or " "
                 for cell in row.findall(f"{W}tc")]
        rows.append("| " + " | ".join(cells) + " |")
    columns = len(source_rows[0].findall(f"{W}tc"))
    return [rows[0], "|" + "---|" * columns, *rows[1:], ""]


def paragraph_lines(paragraph, heading_of, media_of, links, image_start, list_info=None):
    """返回 Markdown 行、图片序号、人工核对提示与文字类别。"""
    lines, notices = [], []
    blips = list(paragraph.iter(f"{A}blip"))
    text = para_text(paragraph, links).strip()
    if list_info and blips:
        raise ValueError("Word 列表项含图片；当前无法保证图片与编号项的阅读顺序，已阻断转换")
    if list_info and not text:
        raise ValueError("Word 编号列表项没有可导出的文字；请先核对空列表项")
    if blips and text:
        notices.append("注意：图文混排段归一为图片后接文字，请核对位置")
    image_number = image_start
    for blip in blips:
        rid = blip.get(f"{R}embed")
        src = media_of.get(rid)
        if not src:
            continue
        image_number += 1
        filename = f"{image_number:02d}-" + os.path.basename(src)
        alt = image_alt(paragraph, rid).replace("[", "(").replace("]", ")").replace("\n", " ")
        lines.extend([f"![{alt}](images/{filename})", ""])
        if alt:
            notices.append(f"图注来自 Word 替换文字：{alt[:40]}（仍须补职责与来源）")
    if not text:
        return lines, image_number, notices, None

    ppr = paragraph.find(f"{W}pPr")
    style_el = ppr.find(f"{W}pStyle") if ppr is not None else None
    style_id = style_el.get(f"{W}val") if style_el is not None else ""
    level = heading_of.get(style_id)
    if level and list_info:
        raise ValueError(f"同一段落同时带标题样式和列表编号：{text[:40]}")
    if list_info:
        if not text:
            raise ValueError("Word 编号列表项没有可导出的文字；请先核对空列表项")
        indent = "  " * list_info["ilvl"]
        if list_info["ordered"]:
            marker = f"{list_info['markdown_number']}."
        else:
            marker = "-"
        if list_info["marker"]:
            marker += f" ⟦{list_info['marker']}⟧"
            notices.append(f"自定义编号「{list_info['marker']}」已保留为显式标签；Markdown 仍保留列表层级")
        lines.append(f"{indent}{marker} {text}")
        category = "list"
    elif level:
        clean = re.sub(r"^\*\*(.*)\*\*$", r"\1", text)
        lines.append("#" * min(level, 3) + " " + clean)
        category = "heading"
        if level > 3:
            notices.append(f"注意：标题{level}归一化为三级，请核对层级")
    else:
        lines.append(text)
        category = "paragraph"
    # Do not put blank lines between list items: that would restart the Markdown block.
    if category != "list":
        lines.append("")
    return lines, image_number, notices, category


def extract(docx_path, out_md):
    try:
        archive = zipfile.ZipFile(docx_path)
    except (OSError, zipfile.BadZipFile) as error:
        print(f"✗ 不是合法 docx：{error}", file=sys.stderr)
        return 1

    try:
        with archive as z:
            try:
                if len(z.infolist()) > 10000 or sum(i.file_size for i in z.infolist()) > 100 * 1024 * 1024:
                    raise ValueError("DOCX 解压内容超过 100MB 或 10000 项限制")
                doc = ET.fromstring(z.read("word/document.xml"))
                heading_of = load_styles(z)
                style_numpr = load_style_numpr(z)
                numbering = load_numbering(z)
                media_of = load_rels(z)
                links = load_links(z)
            except (ValueError, KeyError, zipfile.BadZipFile, ET.ParseError) as error:
                print(f"✗ docx 关系或 XML 无效：{error}", file=sys.stderr)
                return 1

            body = doc.find(f"{W}body")
            if body is None:
                print("✗ docx 缺少正文 body", file=sys.stderr)
                return 1
            problems = validate_body(z, body, links, media_of, style_numpr)
            if problems:
                print("✗ 转换会丢失语义，未写出成稿；请先在 Word 展平或另附材料：\n"
                      + "\n".join(problems), file=sys.stderr)
                return 1
            try:
                notes = notes_with_text(z)
            except ValueError as error:
                print(f"✗ {error}，未写出成稿", file=sys.stderr)
                return 1
            if notes:
                print("✗ 文档含脚注／尾注／批注正文，转换会丢失内容；请先在 Word 中把它们并入正文：\n  "
                      + "\n  ".join(notes), file=sys.stderr)
                return 1

            furniture = [name for name in z.namelist()
                         if re.match(r"word/(?:header|footer).*\.xml$", name)]
            if furniture:
                print("  注意：仅提取正文；页眉页脚未转换，请人工核对是否含正文信息："
                      + ", ".join(furniture), file=sys.stderr)

            # Resolve every list before touching output paths. Unsupported custom formats,
            # broken numbering references, and skipped levels therefore cannot leave a
            # half-written Markdown file or extracted images behind.
            numbering_state = NumberingState(numbering)
            list_info_by_para = {}
            previous_list_level = None
            try:
                for element in body:
                    if element.tag != f"{W}p":
                        previous_list_level = None
                        continue
                    resolved = resolve_numpr(element, style_numpr)
                    if resolved is None:
                        previous_list_level = None
                        continue
                    ilvl = resolved["ilvl"]
                    if not 0 <= ilvl <= 8:
                        raise ValueError(f"Word 列表层级超出 0–8：{ilvl}")
                    if previous_list_level is None and ilvl > 0:
                        raise ValueError(f"Word 列表从第 {ilvl + 1} 层开始；缺少父级条目，拒绝静默展平")
                    if previous_list_level is not None and ilvl > previous_list_level + 1:
                        raise ValueError(f"Word 列表从第 {previous_list_level + 1} 层跳到第 {ilvl + 1} 层；"
                                         "缺少父级条目，拒绝静默展平")
                    info = numbering_state.next_item(resolved["num_id"], ilvl)
                    info["ilvl"] = ilvl
                    list_info_by_para[id(element)] = info
                    previous_list_level = ilvl
            except ValueError as error:
                print(f"✗ Word 列表无法无损转换，未写出成稿：{error}", file=sys.stderr)
                return 1

            out_dir = os.path.dirname(os.path.abspath(out_md)) or "."
            img_dir = os.path.join(out_dir, "images")
            try:
                planned = plan_images(z, body, img_dir, media_of)
            except ValueError as error:
                print(f"✗ {error}", file=sys.stderr)
                return 1

            try:
                lines, image_number, tables = [], 0, 0
                counts = {"paragraph": 0, "heading": 0, "list": 0}
                notices_all = []
                previous_list_info = None
                for element in body:
                    if element.tag == f"{W}tbl":
                        if previous_list_info and lines and lines[-1] != "":
                            lines.append("")
                        previous_list_info = None
                        converted = table_lines(element, links)
                        if converted:
                            lines.extend(converted)
                            tables += 1
                        continue
                    if element.tag != f"{W}p":
                        previous_list_info = None
                        continue
                    list_info = list_info_by_para.get(id(element))
                    if previous_list_info and not list_info and lines and lines[-1] != "":
                        lines.append("")

                    converted, image_number, notices, category = paragraph_lines(
                        element, heading_of, media_of, links, image_number, list_info=list_info)
                    lines.extend(converted)
                    notices_all.extend(notices)
                    if category:
                        counts[category] += 1
                    previous_list_info = list_info if category == "list" else None
            except ValueError as error:
                print(f"✗ {error}，未写出成稿", file=sys.stderr)
                return 1

            markdown = "\n".join(lines).rstrip() + "\n"

            # No numbering or structural validation remains after this point. Images and
            # Markdown are written only after the entire source has been converted.
            write_images(out_dir, img_dir, planned)
            with open(out_md, "w", encoding="utf-8") as output:
                output.write(markdown)
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, ET.ParseError) as error:
        print(f"✗ docx 抽取失败：{error}", file=sys.stderr)
        return 1

    for notice in notices_all:
        print(f"  {notice}", file=sys.stderr)
    print(f"✓ {os.path.basename(docx_path)} → {out_md}")
    print(f"  段落 {counts['paragraph']} · 标题 {counts['heading']} · 列表项 {counts['list']} · 图片 {image_number}"
          + (f" · 表格 {tables}（已转 Markdown 表格）" if tables else ""))
    if image_number:
        print(f"  ⚠ 抽出的 {image_number} 张图没有职责：进 render 前先补成 ![说明](路径 \"职责\")，"
              "否则 Gate 2 会判「必须改」", file=sys.stderr)
    return 0

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("docx")
    parser.add_argument("-o", "--out", help="输出 md 路径（默认同名 .md）")
    args = parser.parse_args()
    if not args.docx.lower().endswith(".docx"):
        parser.error("仅支持 .docx，不支持旧版 .doc / PDF")
    if not os.path.isfile(args.docx):
        print(f"✗ 文件不存在: {args.docx}", file=sys.stderr)
        sys.exit(1)
    out = args.out or re.sub(r"\.docx$", "", args.docx, flags=re.I) + ".md"
    sys.exit(extract(args.docx, out))


if __name__ == "__main__":
    main()
