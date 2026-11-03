#!/usr/bin/env python3
"""Composed Markdown → 公众号正文 HTML + 独立移动预览 + Gate 1/2（V10）。

    render.py article.md [--theme paper|letter|ink|frost|bone|folio] [-o out.html]
    render.py article.md --against 原稿.md [--ledger 台账.md]
    render.py article.md --deliver 交付目录/
"""
import argparse
import base64
import hashlib
import html as H
import json
import math
import mimetypes
import os
import re
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check import MONO, SANS, SERIF, check, safe_http_url  # noqa: E402
from editorial import (  # noqa: E402
    FACT_ROLES, audit, block_text, classify_fact_change, compare_facts,
    compare_voice, doc_len, first_screen, introduced_without_source,
    locate, parse_ledger, peak_text, plain, render_report, strategy_notes,
)
from safety import contrast, local_path, sha256  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_VERSION = "10.0.0"
THEMES_PATH = os.path.join(HERE, "..", "assets", "themes.json")
with open(THEMES_PATH, "rb") as _theme_file:
    THEME_CONFIG_BYTES = _theme_file.read()
THEME_CONFIG_SHA256 = hashlib.sha256(THEME_CONFIG_BYTES).hexdigest()
THEMES = json.loads(THEME_CONFIG_BYTES.decode("utf-8"))

THEME_AXES = {
    "lead": {"brief", "letter", "ink", "report", "plate", "feature"},
    "heading": {"index", "plain", "seal", "report", "atelier", "folio"},
    "h3": {"label", "soft", "serif", "report", "atelier", "folio"},
    "peak": {"rule", "field", "line", "plate", "dark", "compact"},
    "divider": {"short-rule", "pause", "seal", "hairline", "double", "slash"},
    "quote": {"rule", "voice", "serif", "report", "atelier", "folio"},
    "image": {"flush", "soft", "inkline", "report", "mat", "folio"},
    "data": {"columns", "stack", "ledger", "ticker", "specimen", "folio"},
    "table": {"open", "warm", "ink", "report", "atelier", "feature"},
    "list": {"index", "dash", "chinese", "report", "atelier", "folio"},
}
TYPE_KEYS = ("heading_size", "heading_weight", "heading_leading", "lead_size", "lead_weight",
             "lead_leading", "quote_size", "h3_size", "data_size")
COLOR_ROLES = ("text", "sub", "muted", "line", "field", "accent", "dark", "on_dark")
GRID_KEYS = ("inset", "indent", "chapter_gap", "paragraph_gap", "body", "caption")


def validate_themes(themes):
    """校验主题配置完整性与字号层级硬约束（H2 > 导语 > 正文 >= 图注 >= 12px，H2 > H3）。"""
    problems = []
    for name, t in themes.items():
        before = len(problems)
        for axis, allowed in THEME_AXES.items():
            value = t.get(axis)
            if value not in allowed:
                problems.append(f"{name}.{axis}={value!r} 未登记（可用：{'、'.join(sorted(allowed))}）")
        for role in COLOR_ROLES + ("display", "toc_label", "body_font"):
            if role not in t:
                problems.append(f"{name} 缺少 {role}")
        for key in GRID_KEYS:
            if key not in t.get("grid", {}):
                problems.append(f"{name}.grid 缺少 {key}")
        for key in TYPE_KEYS:
            if key not in t.get("type", {}):
                problems.append(f"{name}.type 缺少 {key}")
        if len(problems) > before:
            continue
        ty, grid = t["type"], t["grid"]
        if not ty["heading_size"] > ty["lead_size"]:
            problems.append(f"{name}：章节标题 {ty['heading_size']}px 未大于导语 {ty['lead_size']}px")
        if not ty["lead_size"] > grid["body"]:
            problems.append(f"{name}：导语 {ty['lead_size']}px 未大于正文 {grid['body']}px")
        if not ty["heading_size"] > ty["h3_size"]:
            problems.append(f"{name}：H2 {ty['heading_size']}px 未大于 H3 {ty['h3_size']}px")
        if not grid["body"] >= grid["caption"]:
            problems.append(f"{name}：正文 {grid['body']}px 小于图注 {grid['caption']}px")
        if not 15 <= grid["body"] <= 17:
            problems.append(f"{name}：正文字号 {grid['body']}px 超出 15–17px 手机阅读区间")
        if not 12 <= grid["caption"] <= 15:
            problems.append(f"{name}：图注字号 {grid['caption']}px 超出 12–15px")
    return problems


_THEME_PROBLEMS = validate_themes(THEMES)
if _THEME_PROBLEMS:
    raise ValueError("主题配置不合格：\n  " + "\n  ".join(_THEME_PROBLEMS))

CJK = "\u4e00-\u9fff\u3400-\u4dbf"
MICRO, SMALL, BODY, DISPLAY = 13, 14, 16, 20

ROLES = {
    "入口", "锚点", "解释", "证据", "对比", "结构", "场景", "叙事", "隐喻", "停顿", "数据", "资料", "实拍",
    "entry", "anchor", "explain", "evidence", "compare", "structure", "context", "narrative", "metaphor", "rhythm",
    "data", "archival", "photo",
}
PROVENANCE_ROLES = {"资料", "实拍", "archival", "photo"}
IMAGE_MODES = {"hero", "full-width", "inset", "plate", "sequence", "comparison", "detail", "evidence", "editorial", "explainer", "data"}
TODO = re.compile(r"(?i)^(todo|待补)")
COVER_RATIO = 2.35
COVER_BAND = (1.6, 3.0)
COVER_MIN_W = 900

BR = '<span leaf=""><br></span>'
INLINE = re.compile(r"`([^`]+)`|==(.+?)==|\*\*(.+?)\*\*|<u>(.+?)</u>|~~(.+?)~~|\[([^\]]+)\]\(([^)\s]+)\)")
INLINE_BRACKET_LINK = re.compile(r"\[(\[[^\]\n]*\])\]\(([^)\s]+)\)")
ORDINAL = re.compile(
    r"^(?:[一二三四五六七八九十]{1,3}[、．.]|[（(][一二三四五六七八九十0-9]{1,3}[）)]"
    r"|第[一二三四五六七八九十0-9]{1,3}[章节回讲部篇期段条则辑卷问日]"
    r"|[0-9]{1,2}[、．.]\s|[0-9]{1,2}\s"
    r"|[①-⑳⑴-⒇]|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+[、．.\s]?)"
)
PROSE_ATOM = re.compile(
    r"(?:19|20)\d{2}年(?:\d{1,2}月(?:\d{1,2}日)?)?"
    r"|\d{1,2}月\d{1,2}日"
    r"|[+\-−]?\d[\d.,，]*(?:\s*[×x–—-]\s*\d[\d.,，]*)*(?::1|%|％|个百分点|万亿美元|亿美元|万美元|万亿元|亿元|万元|万人|"
    r"美元|人民币|欧元|日元|小时|分钟|公里|千米|GB|MB|TB|KB|ms|cm|mm|kg|px|Hz|元|倍|年|月|日|天|人|家|件|台|吨|米|秒|艘|幅|万|亿)?"
)


def typo(s):
    """归一中文语境半角标点；保护行内代码、链接与 URL。"""
    def prose(text):
        return re.sub(
            f"(?<=[{CJK}])([,;:!?])|(?<=[A-Za-z0-9])([,;!?])\\s*(?=[{CJK}])",
            lambda m: dict(zip(",;:!?", "，；：！？"))[m[1] or m[2]],
            text,
        )
    return "".join(
        part if i % 2 else prose(part)
        for i, part in enumerate(re.split(r"(`[^`]+`|\[(?:\[[^\]\n]*\]|[^\]]+)\]\([^)\s]+\)|https?://[^\s<>\u3000，；。！？）\"]+)", s))
    )


def unique_style(style):
    props = {}
    for declaration in style.split(";"):
        if not declaration.strip():
            continue
        name, sep, value = declaration.partition(":")
        if not sep:
            raise ValueError(f"内部 CSS 声明无效：{declaration}")
        props[name.strip()] = value.strip()
    return "".join(f"{name}:{value};" for name, value in props.items())


FRONTMATTER_FIELDS = {
    "title", "theme", "density", "article_type", "audience", "reading_context", "purpose", "thesis",
    "composition", "visual_concept", "information_shape", "asset_strategy", "mobile_risk", "design_rationale",
    "cover", "kicker", "deck", "author", "date", "toc", "source", "removed_facts", "digest", "bio", "cta",
}
_LIST_LINE = re.compile(r"^( *)([-*]|[0-9]{1,9}[.、])\s+(.+?)\s*$")


def _new_list_node(ordered, start=1):
    return {"ordered": ordered, "start": start if ordered else 1, "items": []}


def _list_node_accepts(node, ordered, number):
    if node["ordered"] != ordered:
        return False
    return True if not ordered else (number == node["start"] + len(node["items"]))


def parse_list(lines, start_index):
    roots, stack, owners = [], [], []
    previous_level = -1
    i = start_index
    while i < len(lines):
        raw = lines[i].rstrip()
        match = _LIST_LINE.match(raw)
        if not match:
            break
        indent, marker, content = match.groups()
        if "\t" in indent or len(indent) % 2:
            raise ValueError(f"第 {i + 1} 行：列表缩进须为 2 个空格的整数倍")
        level = len(indent) // 2
        if level > 8:
            raise ValueError(f"第 {i + 1} 行：嵌套列表层级超过 8")
        if level > previous_level + 1:
            raise ValueError(f"第 {i + 1} 行：嵌套列表跳过父级条目")
        ordered = bool(marker[0].isdigit())
        number = int(marker[:-1]) if ordered else 1
        if ordered and not 0 <= number <= 999999:
            raise ValueError(f"第 {i + 1} 行：有序列表起始编号超出范围")
        custom = re.match(r"^⟦([^⟧]{1,64})⟧(?:\s+|$)", content)
        custom_marker = custom.group(1) if custom else None
        if custom:
            content = content[custom.end():]
        if not content.strip():
            raise ValueError(f"第 {i + 1} 行：列表项不能为空")

        if level == 0:
            if not roots or not _list_node_accepts(roots[-1], ordered, number):
                roots.append(_new_list_node(ordered, number))
            node = roots[-1]
            stack, owners = [node], [None]
        else:
            if len(stack) < level or not stack[level - 1]["items"]:
                raise ValueError(f"第 {i + 1} 行：嵌套列表没有对应的父项")
            parent_item = stack[level - 1]["items"][-1]
            owner = id(parent_item)
            node = stack[level] if len(stack) > level and owners[level] == owner else None
            if node is None or not _list_node_accepts(node, ordered, number):
                node = _new_list_node(ordered, number)
                parent_item["children"].append(node)
            stack = stack[:level] + [node]
            owners = owners[:level] + [owner]

        node["items"].append({"text": content.strip(), "marker": custom_marker, "children": []})
        previous_level = level
        i += 1
    return roots, i


def parse(md):
    md = md.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    meta, blocks = {}, []
    if md.startswith("---\n"):
        m = re.match(r"^---\n(.*?)\n---(?:\n|$)", md, re.S)
        if not m:
            raise ValueError("frontmatter 未闭合")
        for line_no, ln in enumerate(m.group(1).splitlines(), 2):
            if not ln.strip() or ln.lstrip().startswith("#"):
                continue
            if ln[:1].isspace() or not re.match(r"^[a-z_]+:", ln):
                raise ValueError(f"frontmatter 第 {line_no} 行只支持顶格 key: 单行值；不支持嵌套 YAML")
            k, v = ln.split(":", 1)
            if k not in FRONTMATTER_FIELDS:
                raise ValueError(f"frontmatter 第 {line_no} 行非法字段：{k}")
            if k in meta:
                raise ValueError(f"frontmatter 第 {line_no} 行重复字段：{k}")
            v = v.strip()
            quoted = re.fullmatch(r"([\"'])(.*?)\1(?:\s+#.*)?", v)
            if quoted:
                v = quoted[2]
            else:
                if v.startswith(("[", "{", "|", ">")):
                    raise ValueError(f"frontmatter 字段 {k} 不支持数组、对象或多行 YAML；请使用单行文本")
                v = re.sub(r"\s+#.*$", "", v).strip()
            meta[k] = v
        if "toc" in meta and meta["toc"].lower() not in ("true", "false", "yes", "no", "1", "0"):
            raise ValueError("frontmatter toc 只接受 true/false/yes/no/1/0")
        md = md[m.end():]
    lines, i, para = md.splitlines(), 0, []

    def flush():
        if para:
            txt = ""
            for seg in para:
                txt += (" " if txt and re.match(r"[\x00-\x7f]", seg[0]) and re.search(r"[\x00-\x7f]$", txt) else "") + seg
            blocks.append(("p", txt))
            para.clear()

    while i < len(lines):
        ln = lines[i].rstrip()
        s = ln.strip()
        if s.startswith("```"):
            flush()
            lang, body = s[3:].strip(), []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                body.append(lines[i])
                i += 1
            if i >= len(lines):
                raise ValueError("代码围栏未闭合")
            blocks.append(("code", (lang, body)))
        elif s.startswith(":::") and len(s) > 3:
            flush()
            kind, _, arg = s[3:].strip().partition(" ")
            body = []
            i += 1
            while i < len(lines) and lines[i].strip() != ":::":
                body.append(lines[i].strip())
                i += 1
            if i >= len(lines):
                raise ValueError(f"::: {kind} 未闭合")
            blocks.append((kind, (arg.strip(), [b for b in body if b])))
        elif re.match(r"#{1,3} ", s):
            flush()
            lvl, text = len(s.split(" ")[0]), s.split(" ", 1)[1].strip()
            if lvl == 1:
                if meta.get("title") and meta["title"] != text:
                    raise ValueError(f"第 {i + 1} 行：H1 与 frontmatter title 不一致，不能静默丢弃标题")
                meta.setdefault("title", text)
            else:
                blocks.append(("h2" if lvl == 2 else "h3", text))
        elif re.fullmatch(r"(-{3,}|\*{3,})", s):
            flush()
            blocks.append(("hr", None))
        elif s.startswith(">"):
            flush()
            q = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(lines[i].strip().lstrip(">").strip())
                i += 1
            i -= 1
            src = q.pop()[1:].lstrip("—-– ").strip() if len(q) > 1 and re.match(r"[—–-]", q[-1]) else ""
            # 仅全文首个块作为导语，防止多个连续 > 块叠加成双导语
            kind = "lead" if not blocks else "quote"
            blocks.append((kind, ("".join(x for x in q if x), src)))
        elif re.match(r"!\[[^\]]*\]\([^)]*\)\s*$", s):
            flush()
            mm = re.match(r'!\[([^\]]*)\]\(\s*([^)\s]*)\s*(?:"([^"]*)")?\s*\)', s)
            if not mm:
                raise ValueError("图片语法错误：使用 ![说明](路径 \"职责\")，带空格路径请重命名")
            blocks.append(("img", mm.groups()))
        elif _LIST_LINE.match(ln):
            flush()
            nodes, next_i = parse_list(lines, i)
            blocks.extend(("list", node) for node in nodes)
            i = next_i - 1
        elif s.startswith("|"):
            flush()
            rows, sep_cols = [], None
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip().replace(r"\|", "|") for c in re.split(r"(?<!\\)\|", lines[i].strip().strip("|"))]
                if cells and all(re.fullmatch(r":?-+:?", c) for c in cells):
                    sep_cols = len(cells)
                else:
                    rows.append(cells)
                i += 1
            i -= 1
            if sep_cols is not None and rows and sep_cols != len(rows[0]):
                raise ValueError(f"第 {i + 1} 行：表格分隔行列数（{sep_cols}）与表头列数（{len(rows[0])}）不一致")
            blocks.append(("table", rows))
        elif not s:
            flush()
        elif ln != ln.lstrip() and blocks and blocks[-1][0] == "list":
            raise ValueError(f"第 {i + 1} 行：列表续行或缩进块不支持，请显式改写后核对")
        elif re.match(r"#{4,6} ", s):
            raise ValueError(f"第 {i + 1} 行：仅支持三级标题；请显式重组层级")
        elif re.search(r"!\[.*?\]\(", s):
            raise ValueError(f"第 {i + 1} 行：图片必须独占一行，不能静默转为文字")
        else:
            para.append(s)
        i += 1
    flush()
    return meta, blocks


def img_size(path):
    """读文件头取 (宽, 高)：PNG / JPEG / GIF / WebP。"""
    try:
        with open(path, "rb") as f:
            head = f.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                return struct.unpack(">II", head[16:24])
            if head[:6] in (b"GIF87a", b"GIF89a"):
                return struct.unpack("<HH", head[6:10])
            if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
                tag, chunk = head[12:16], head[20:32]
                if tag == b"VP8X":
                    w = 1 + int.from_bytes(chunk[4:7], "little")
                    return w, 1 + int.from_bytes(chunk[7:10], "little")
                if tag == b"VP8L":
                    bits = int.from_bytes(chunk[1:5], "little")
                    return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
                if tag == b"VP8 ":
                    return (int.from_bytes(chunk[6:8], "little") & 0x3FFF,
                            int.from_bytes(chunk[8:10], "little") & 0x3FFF)
            if head[:2] == b"\xff\xd8":
                data = head + f.read()
                i = 2
                while i + 9 < len(data):
                    if data[i] != 0xFF:
                        i += 1
                        continue
                    mk = data[i + 1]
                    if mk in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                        h, w = struct.unpack(">HH", data[i + 5:i + 9])
                        return w, h
                    if mk in (0xD8, 0x01) or 0xD0 <= mk <= 0xD7:
                        i += 2
                        continue
                    i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    except (OSError, struct.error, IndexError):
        return None
    return None


NUMERIC = re.compile(
    r"(?:约|近|超过|超|不足|少于|多于|不到)?"
    r"[+\-−]?[\d.,，]+(?:\s*[–—-]\s*[\d.,，]+)?\s*"
    r"(?:个百分点|小时|分钟|美元|亿元|万元|%|％|元|万|亿|年|天|人|家|件|倍)?"
)
MOBILE_TABLE_PX = 288  # 320px 视口减正文左右各 16px
DATA_VALUE_SLACK = 8
TABLE_SLACK = 2


def text_px(s, size=14):
    """估算单行渲染像素宽：ASCII≈0.556em，半宽符号≈0.68em，CJK≈1.0em。"""
    def char_em(ch):
        if ch == " ":
            return 0.28
        if ord(ch) < 128:
            return 0.556
        if ch in "×–—·…“”‘’":
            return 0.68
        return 1.0
    return sum(char_em(ch) for ch in s) * size


def cell_min_px(s, pad=12):
    return text_px(s) + pad


def col_floor(s, pad=12):
    return cell_min_px(s, pad) + TABLE_SLACK


def table_pad(t):
    return 14 if t.get("table") in ("warm", "atelier") else 12


def _column_floors(rows, pad=12):
    """计算每列最小可读宽度：数值列不拆断、短标签不孤字折行、叙述列至少保留 4 个汉字可读宽。"""
    n = len(rows[0])
    floor = [0.0] * n
    prose_min = 4 * SMALL + pad + TABLE_SLACK
    for row in rows:
        for j, cell in enumerate(row):
            if j >= n:
                continue
            text = re.sub(r"[`*=~]", "", plain(str(cell))).strip()
            if not text:
                continue
            px = text_px(text, SMALL)
            if NUMERIC.fullmatch(text):
                floor[j] = max(floor[j], px + pad + TABLE_SLACK)
            elif px <= 4.5 * SMALL:
                floor[j] = max(floor[j], px + pad + TABLE_SLACK)
            else:
                floor[j] = max(floor[j], min(px + pad + TABLE_SLACK, prose_min))
    return floor


def table_fits(rows, inset=0, pad=12):
    """320px 视口下所有列的最小可读宽度能否同时成立；放不下则转记录卡。"""
    avail = MOBILE_TABLE_PX - 2 * inset
    if not rows or not rows[0]:
        return True
    return sum(_column_floors(rows, pad)) <= avail


def col_widths(rows, avail=MOBILE_TABLE_PX, pad=12):
    """先兑现每列最小可读像素，若短词列整列可单行容纳则优先给足，再按体量分配长文本列。"""
    if not rows or not rows[0]:
        return []
    n = len(rows[0])
    floor_px = _column_floors(rows, pad)
    col_max = [0.0] * n
    weights = []
    for j in range(n):
        best = 1.0
        for row in rows:
            if j < len(row):
                text = re.sub(r"[`*=~]", "", plain(str(row[j]))).strip()
                px = text_px(text, SMALL)
                col_max[j] = max(col_max[j], px)
                best = max(best, min(px / SMALL, 12.0))
        weights.append(max(best, 3.0))
    for j in range(n):
        want = col_max[j] + pad + TABLE_SLACK + 4
        if col_max[j] <= 6.8 * SMALL and want > floor_px[j] and sum(floor_px) - floor_px[j] + want <= avail:
            floor_px[j] = want

    floors = [px / avail * 100 for px in floor_px]
    floor_total = sum(floors)
    if floor_total >= 100:
        return [f / floor_total * 100 for f in floors]

    residual = [max(0.0, w - px / SMALL) for w, px in zip(weights, floor_px)]
    residual_total = sum(residual)
    if not residual_total:
        residual, residual_total = weights, sum(weights)
    remain = 100 - floor_total
    return [f + remain * r / residual_total for f, r in zip(floors, residual)]


class R:
    """六主题共享排版引擎：一切视觉差异由架构比例、字体、网格与组件语法驱动，而非换色。"""

    def __init__(self, t, density):
        self.t = t
        self.type = t["type"]
        self.grid = t.get("grid", {})
        self.k = {"dense": 0.82, "airy": 1.18}.get(density, 1.0)
        self.body = self.grid.get("body", BODY)
        self.cap = self.grid.get("caption", MICRO)
        self.inset = self.grid.get("inset", 0)
        self.font = SERIF if t["display"] == "serif" else SANS
        self.reading_font = SERIF if t.get("body_font") == "serif" else SANS

    def g(self, px):
        return round(px * self.k)

    def leaf(self, s):
        return BR if not s else f'<span leaf="">{H.escape(s, quote=False)}</span>'

    def prose_leaf(self, s):
        out, pos = [], 0
        for m in PROSE_ATOM.finditer(s):
            token = m.group()
            if not re.search(r"\d", token) or text_px(token, self.body) > 220:
                continue
            if re.search(r"https?://[^\s<>]*$", s[:m.start()]):
                continue
            if m.start() > pos:
                out.append(self.leaf(s[pos:m.start()]))
            out.append(f'<span leaf="" style="white-space:nowrap;">{H.escape(token)}</span>')
            pos = m.end()
        if pos < len(s) or not out:
            out.append(self.leaf(s[pos:]))
        return "".join(out)

    def inline(self, s, normalize=True):
        t, out, pos = self.t, [], 0
        s = typo(s) if normalize else s
        matches = [(m, False) for m in INLINE.finditer(s)]
        matches.extend((m, True) for m in INLINE_BRACKET_LINK.finditer(s))
        matches.sort(key=lambda item: item[0].start())
        for m, bracket_link in matches:
            if m.start() < pos:
                continue
            if m.start() > pos:
                out.append(self.prose_leaf(s[pos:m.start()]))
            if bracket_link:
                code = mark = bold = u = strike = None
                ltext, url = m.groups()
            else:
                code, mark, bold, u, strike, ltext, url = m.groups()
            if code:
                out.append(f'<span style="font-family:{MONO};font-size:{SMALL}px;background:{t["field"]};'
                           f'padding:1px 5px;border-radius:3px;color:{t["text"]};">{self.leaf(code)}</span>')
            elif mark or u:
                out.append(f'<span style="border-bottom:1px solid {t["accent"]};padding-bottom:1px;">'
                           f'{self.leaf(mark or u)}</span>')
            elif bold:
                out.append(f'<strong style="font-weight:600;color:inherit;">{self.leaf(bold)}</strong>')
            elif strike:
                out.append(f'<span style="text-decoration:line-through;color:{t["muted"]};">{self.leaf(strike)}</span>')
            else:
                if not safe_http_url(url):
                    raise ValueError(f"链接不合法或协议不支持：{url}；仅允许带有效主机名的 HTTP(S) URL")
                out.append(f'<a href="{H.escape(url, quote=True)}" style="color:{t["text"]};text-decoration:underline;">{self.leaf(ltext)}</a>')
            pos = m.end()
        if pos < len(s) or not out:
            out.append(self.prose_leaf(s[pos:]))
        return "".join(out)

    def p(self, inner, size=None, color=None, extra=""):
        size = self.body if size is None else size
        lh = "" if "line-height" in extra else f'line-height:{self.t["leading"] if size == self.body else 1.72};'
        ls = "" if "letter-spacing" in extra else "letter-spacing:normal;"
        style = unique_style(f'margin:0;font-size:{size:g}px;{lh}color:{color or self.t["text"]};{ls}{extra}')
        return f'<p style="{style}">{inner}</p>'

    def micro(self, s, color=None, extra="", size=None):
        return self.p(self.leaf(s), size or self.cap, color or self.t["muted"], f"font-weight:500;{extra}")

    def rule(self, w=24, h=1, color=None, center=True, below=0):
        pos = f"margin:0 auto {below}px;" if center else "flex-shrink:0;"
        return f'<section style="width:{w}px;height:{h}px;background:{color or self.t["line"]};{pos}">{BR}</section>'

    def h2(self, text, n):
        t, mode = self.t, self.t["heading"]
        numbered = not ORDINAL.match(text.strip())
        title = self.inline(text)
        hs = self.type["heading_size"]
        style = (f"font-weight:{self.type['heading_weight']};line-height:{self.type['heading_leading']};"
                 f"font-family:{self.font};")
        gap = f'margin:{self.g(self.grid["chapter_gap"])}px 0 {self.g(14)}px;'
        if mode == "index":
            if numbered:
                idx_col = self.p(self.leaf(f"{n:02d}"), SMALL, t["muted"],
                                 "width:26px;flex-shrink:0;font-weight:600;font-variant-numeric:tabular-nums;")
                return (f'<section style="{gap}display:flex;align-items:baseline;gap:8px;">'
                        f'{idx_col}' + self.p(title, hs, extra=style + "flex:1;min-width:0;") + "</section>")
            return f'<section style="{gap}">' + self.p(title, hs, extra=style) + "</section>"
        if mode == "plain":
            return (f'<section style="{gap}text-align:center;">'
                    + self.p(title, hs, extra=style + "text-align:center;")
                    + f'<section style="width:24px;height:1px;background:{t["accent"]};margin:11px auto 0;">{BR}</section>'
                    + "</section>")
        if mode == "seal":
            if numbered:
                seal_box = (f'<section style="flex-shrink:0;padding-top:3px;">'
                            f'<span style="display:inline-block;padding:1px 6px;border:1px solid {t["accent"]};'
                            f'font-size:{MICRO}px;line-height:1.4;font-weight:600;font-family:{SERIF};'
                            f'color:{t["accent"]};">{self.leaf(f"{n:02d}")}</span></section>')
                return (f'<section style="{gap}display:flex;align-items:flex-start;gap:10px;">'
                        f'{seal_box}' + self.p(title, hs, extra=style + "flex:1;min-width:0;") + "</section>")
            return f'<section style="{gap}">' + self.p(title, hs, extra=style) + "</section>"
        if mode == "report":
            marker = self.micro(f"{n:02d} /", color=t["accent"], extra="margin-bottom:5px;font-weight:700;font-variant-numeric:tabular-nums;") if numbered else ""
            return (f'<section style="{gap}padding-top:10px;border-top:1px solid {t["text"]};">{marker}'
                    + self.p(title, hs, extra=style) + "</section>")
        if mode == "atelier":
            return (f'<section style="{gap}padding-top:16px;border-top:1px solid {t["line"]};">'
                    + self.p(title, hs, extra=style + "letter-spacing:0.03em;") + "</section>")
        if mode == "folio":
            bar = (f'<section style="display:flex;align-items:center;gap:8px;margin-bottom:7px;">'
                   + self.p(self.leaf(f"{n:02d}"), SMALL, t["accent"],
                            f"font-weight:700;line-height:1;font-family:{self.font};font-variant-numeric:tabular-nums;flex-shrink:0;")
                   + f'<section style="width:20px;height:2px;background:{t["accent"]};flex-shrink:0;">{BR}</section></section>'
                   if numbered else "")
            return f'<section style="{gap}">{bar}' + self.p(title, hs, extra=style) + "</section>"
        raise ValueError(f"章节轴取值未实现：{mode}")

    def h3(self, text):
        t, mode = self.t, self.t["h3"]
        size, weight, extra = self.type["h3_size"], 600, f"font-family:{self.font};"
        if mode == "label":
            size = max(self.cap, size - 1)
            extra = f"font-family:{self.font};color:{t['sub']};letter-spacing:0.05em;"
        elif mode == "soft":
            extra = f"font-family:{self.font};color:{t['sub']};"
        elif mode == "serif":
            weight = 600
        elif mode == "report":
            weight = 700
            extra += f"padding-bottom:5px;border-bottom:1px solid {t['line']};"
        elif mode == "atelier":
            extra += "letter-spacing:0.03em;"
        elif mode == "folio":
            weight = 700
            extra += f"padding-left:10px;border-left:3px solid {t['accent']};"
        return (f'<section style="margin:{self.g(24)}px 0 {self.g(10)}px;">'
                + self.p(self.inline(text), size, t["text"], f"font-weight:{weight};{extra}") + "</section>")

    def para(self, text, next_kind=""):
        indent = self.grid.get("indent", 0)
        extra = "text-align:left;"
        if indent:
            extra += f"text-indent:{indent:g}em;"
        # 段首缩进主题在连续正文段之间保持紧凑流，但在进入其他结构组件前留出完整呼吸间距
        gap = self.grid["paragraph_gap"] if (not indent or next_kind == "p") else max(20, self.grid["paragraph_gap"] * 2)
        return f'<section style="margin:0 0 {self.g(gap)}px;">' + self.p(self.inline(text), extra=extra) + "</section>"

    def _dropcap(self, s):
        s = s.lstrip()
        if not s or s[0] in "「“『（《一二三十壹贰叁拾":
            return self.inline(s, normalize=False)
        return (f'<span style="display:inline-block;font-size:{round(self.body * 1.75)}px;'
                f'line-height:1;font-family:{SERIF};font-weight:700;color:{self.t["accent"]};'
                f'vertical-align:-2px;margin-right:4px;">{self.leaf(s[0])}</span>'
                + self.inline(s[1:], normalize=False))

    def lead(self, text, src):
        t, mode = self.t, self.t["lead"]
        inner = self.inline(text, normalize=False)
        lead_size = min(self.type["lead_size"], 21) if len(plain(text)) > 48 else self.type["lead_size"]
        lead_style = f'line-height:{self.type["lead_leading"]};font-weight:{self.type["lead_weight"]};'
        cite = self.p(self.leaf("—— " + src), self.cap, t["muted"], "margin-top:8px;") if src else ""
        if mode == "brief":
            return (f'<section style="margin:{self.g(4)}px 0 {self.g(24)}px;padding-top:12px;'
                    f'border-top:2px solid {t["accent"]};">'
                    + self.p(inner, lead_size, t["text"], lead_style + f"font-family:{self.font};") + cite + "</section>")
        if mode == "letter":
            return (f'<section style="margin:{self.g(4)}px 0 {self.g(26)}px;padding:0 4px;">'
                    f'<section style="width:24px;height:1px;background:{t["accent"]};margin-bottom:12px;">{BR}</section>'
                    + self.p(inner, lead_size, t["text"], lead_style + f"font-family:{self.font};") + cite + "</section>")
        if mode == "ink":
            return (f'<section style="margin:{self.g(4)}px 0 {self.g(26)}px;padding:2px 0 16px;'
                    f'border-bottom:1px solid {t["line"]};">'
                    + self.p(self._dropcap(text), lead_size, t["text"], lead_style + f"font-family:{SERIF};") + cite + "</section>")
        if mode == "report":
            return (f'<section style="margin:{self.g(4)}px 0 {self.g(20)}px;padding:11px 14px;'
                    f'background:{t["field"]};border-left:3px solid {t["accent"]};">'
                    + self.p(inner, lead_size, t["text"], lead_style) + cite + "</section>")
        if mode == "plate":
            return (f'<section style="margin:{self.g(4)}px 0 {self.g(26)}px;padding:16px 16px;'
                    f'background:{t["field"]};border-top:1px solid {t["line"]};border-bottom:1px solid {t["line"]};">'
                    + self.p(inner, lead_size, t["text"], lead_style + f"font-family:{SERIF};") + cite + "</section>")
        if mode == "feature":
            parts = [p.strip() for p in re.split(r"(?<=[。！？；])", text) if p.strip()]
            if len(parts) >= 2:
                rows = "".join(
                    self.p(self.inline(part, normalize=False), lead_size, t["text"],
                           lead_style + f"font-family:{self.font};letter-spacing:-0.01em;"
                           + ("margin-top:6px;" if idx else ""))
                    for idx, part in enumerate(parts)
                )
            else:
                rows = self.p(inner, lead_size, t["text"], lead_style + f"font-family:{self.font};letter-spacing:-0.01em;")
            return (f'<section style="margin:{self.g(4)}px 0 {self.g(26)}px;">'
                    f'<section style="width:44px;height:3px;background:{t["accent"]};margin-bottom:14px;">{BR}</section>'
                    + rows + cite + "</section>")
        raise ValueError(f"导语轴取值未实现：{mode}")

    def quote(self, text, src):
        t, mode = self.t, self.t["quote"]
        cite = self.p(self.leaf(f"—— {src}"), self.cap, t["muted"], "margin-top:8px;") if src else ""
        body = self.inline(text, normalize=False)
        qsize = self.type["quote_size"]
        if mode == "voice":
            hang = "text-indent:-0.55em;padding-left:0.55em;" if text.lstrip()[:1] in "「『“‘" else ""
            return (f'<section style="margin:{self.g(24)}px 0;padding:2px 12px;">'
                    + self.p(body, qsize, t["sub"], f"font-weight:500;line-height:1.9;font-family:{self.font};{hang}")
                    + cite + "</section>")
        if mode == "serif":
            return (f'<section style="margin:{self.g(24)}px 0;padding:2px 2px 2px 14px;border-left:2px solid {t["accent"]};">'
                    + self.p(body, qsize, t["sub"], f"font-weight:400;line-height:1.95;font-family:{SERIF};")
                    + cite + "</section>")
        if mode == "report":
            return (f'<section style="margin:{self.g(20)}px 0;padding:10px 12px;background:{t["field"]};">'
                    + self.p(body, qsize, t["text"], "font-weight:500;line-height:1.78;") + cite + "</section>")
        if mode == "atelier":
            return (f'<section style="margin:{self.g(26)}px 6%;padding:12px 0;border-top:1px solid {t["line"]};border-bottom:1px solid {t["line"]};">'
                    + self.p(body, qsize, t["sub"], f"font-weight:400;line-height:1.95;font-family:{SERIF};letter-spacing:0.02em;")
                    + cite + "</section>")
        if mode == "folio":
            return (f'<section style="margin:{self.g(26)}px 0;padding:2px 0 2px 14px;border-left:3px solid {t["accent"]};">'
                    + self.p(body, qsize, t["text"], f"font-weight:600;line-height:1.65;font-family:{self.font};")
                    + cite + "</section>")
        if mode == "rule":
            return (f'<section style="margin:{self.g(24)}px 0;padding:0 4px 0 14px;border-left:2px solid {t["accent"]};">'
                    + self.p(body, qsize, t["sub"], "font-weight:500;line-height:1.85;") + cite + "</section>")
        raise ValueError(f"引文轴取值未实现：{mode}")

    def peak(self, text):
        t, style = self.t, self.t["peak"]
        fam = f"font-family:{self.font};"
        if style in ("dark", "compact"):
            inner = self.p(self.inline(text, normalize=False), DISPLAY - 1, t["on_dark"],
                           f"font-weight:600;line-height:{'1.68' if style == 'dark' else '1.56'};{fam}")
            pad = f"{self.g(20)}px 18px" if style == "dark" else "14px 16px"
            return f'<section style="margin:{self.g(30)}px 0;padding:{pad};background:{t["dark"]};">{inner}</section>'
        claim = self.p(self.inline(text, normalize=False), DISPLAY - 1, t["text"], f"font-weight:600;line-height:1.65;{fam}")
        if style == "field":
            return f'<section style="margin:{self.g(28)}px 0;padding:{self.g(18)}px 16px;background:{t["field"]};border-radius:{t["radius"]}px;">{claim}</section>'
        if style == "line":
            return f'<section style="margin:{self.g(26)}px 0;padding:2px 4px 2px 14px;border-left:3px solid {t["accent"]};">{claim}</section>'
        if style == "plate":
            return f'<section style="margin:{self.g(30)}px 0;padding:15px 0;border-top:1px solid {t["text"]};border-bottom:1px solid {t["line"]};">{claim}</section>'
        if style == "rule":
            return (f'<section style="margin:{self.g(30)}px 0;">'
                    f'<section style="width:28px;height:2px;background:{t["accent"]};margin:0 0 12px;">{BR}</section>'
                    f'{claim}</section>')
        raise ValueError(f"重点轴取值未实现：{style}")

    def unknown(self, label, lines):
        t = self.t
        head = self.micro(label or "未知 / 待确认", extra="margin-bottom:6px;")
        body = "".join(self.p(self.inline(x), self.body - 1, t["sub"], "line-height:1.82;") for x in lines)
        return (f'<section style="margin:{self.g(22)}px 0;padding:13px 14px;'
                f'border:1px dashed {t["muted"]};border-radius:{t["radius"]}px;">{head}{body}</section>')

    def note(self, label, lines, tight=False):
        t = self.t
        head = self.micro(label, extra="margin-bottom:5px;") if label else ""
        body_lines = []
        for x in lines:
            for word in ("来源", "口径"):
                if word in (label or ""):
                    x = re.sub(rf"^{word}[：:]\s*", "", x)
            body_lines.append(x)
        body = "".join(self.p(self.inline(x), self.cap, t["sub"], "line-height:1.75;overflow-wrap:anywhere;") for x in body_lines)
        return f'<section style="margin:{self.g(8) if tight else self.g(16)}px 0 {self.g(16)}px;">{head}{body}</section>'

    def data(self, lines, below=None):
        """离散关键数值：先验证 320px 可用宽度，再按各主题独有的设计语法呈现，绝不同质化降级。"""
        t = self.t
        items = [(v.strip(), lab.strip()) for v, _, lab in (ln.replace("|", "｜").partition("｜") for ln in lines)]
        mode, size = t["data"], self.type["data_size"]
        avail = MOBILE_TABLE_PX - 2 * self.inset
        margin = f'margin:{self.g(28)}px 0 {below if below is not None else self.g(28)}px;'

        def values_fit(width):
            return all(text_px(value, size) + DATA_VALUE_SLACK <= width for value, _ in items)

        if mode in ("columns", "specimen"):
            gap = 16 if mode == "columns" else 12
            candidates = ([3, 2] if len(items) >= 3 and mode == "columns" else [2]) if len(items) >= 2 else [1]
            per = next((p for p in candidates if values_fit((avail - gap * (p - 1)) / p)), 1)
            if per >= 2:
                rows = []
                for i in range(0, len(items), per):
                    cells = "".join(
                        f'<section style="flex:1;min-width:0;'
                        + (f"padding:12px 0 0;border-top:1px solid {t['text']};" if mode == "columns"
                           else f"padding:14px 12px;background:{t['field']};border-top:1px solid {t['line']};")
                        + '">'
                        + self.p(self.leaf(v), size, t["text"],
                                 f"font-weight:600;line-height:1.25;font-family:{self.font};font-variant-numeric:tabular-nums;white-space:nowrap;")
                        + self.p(self.inline(lab), self.cap if mode == "specimen" else SMALL, t["sub"], "margin-top:6px;line-height:1.65;")
                        + "</section>"
                        for v, lab in items[i:i + per]
                    )
                    rows.append(f'<section style="display:flex;gap:{gap}px;margin-top:{gap if i else 0}px;">{cells}</section>')
                return f'<section style="{margin}">{"".join(rows)}</section>'
            rows = [
                f'<section style="'
                + (f"padding:13px 14px;background:{t['field']};border-top:1px solid {t['line']};margin-top:{8 if idx else 0}px;"
                   if mode == "specimen" else f"padding:11px 0;border-top:1px solid {t['text' if idx == 0 else 'line']};")
                + '">'
                + self.p(self.leaf(v), size, t["text"],
                         f"font-weight:600;line-height:1.28;font-family:{SERIF if mode == 'specimen' else self.font};font-variant-numeric:tabular-nums;")
                + self.p(self.inline(lab), self.cap if mode == "specimen" else SMALL, t["sub"], "margin-top:5px;line-height:1.65;")
                + "</section>"
                for idx, (v, lab) in enumerate(items)
            ]
            return f'<section style="{margin}">{"".join(rows)}</section>'

        if mode == "ledger":
            rows = [
                (f'<section style="display:flex;justify-content:space-between;align-items:baseline;gap:14px;padding:11px 0;border-bottom:1px solid {t["line"]};">'
                 + self.p(self.inline(lab), SMALL, t["sub"], "flex:1;min-width:0;line-height:1.68;")
                 + self.p(self.leaf(v), size, t["text"], f"flex-shrink:0;font-weight:700;line-height:1.25;font-family:{SERIF};font-variant-numeric:tabular-nums;white-space:nowrap;")
                 + "</section>")
                if text_px(v, size) + DATA_VALUE_SLACK <= avail * 0.58 else
                (f'<section style="padding:11px 0;border-bottom:1px solid {t["line"]};">'
                 + self.p(self.inline(lab), SMALL, t["sub"], "line-height:1.65;")
                 + self.p(self.leaf(v), size, t["text"], f"margin-top:4px;text-align:right;font-weight:700;line-height:1.25;font-family:{SERIF};font-variant-numeric:tabular-nums;")
                 + "</section>")
                for v, lab in items
            ]
            return f'<section style="{margin}border-top:1px solid {t["text"]};">{"".join(rows)}</section>'

        if mode in ("stack", "ticker", "folio"):
            spec = {
                "stack": (0.38, 16, t["accent"], f"font-weight:600;line-height:1.3;font-family:{self.font};",
                          f"padding:14px 16px;background:{t['field']};border-radius:{t['radius']}px;"),
                "ticker": (0.40, 0, t["text"], "font-weight:700;line-height:1.25;",
                           f"border-top:2px solid {t['text']};border-bottom:1px solid {t['text']};"),
                "folio": (0.42, 0, t["accent"], f"font-weight:700;line-height:1.18;font-family:{self.font};letter-spacing:-0.02em;",
                          f"border-top:3px solid {t['text']};"),
            }[mode]
            ratio, pad_x, v_col, v_ext, outer = spec
            side_fits = values_fit(avail * ratio - pad_x)
            rows = []
            for idx, (v, lab) in enumerate(items):
                row_pad = ("padding-top:10px;margin-top:10px;" if idx else "margin:0;") if mode == "stack" else ("padding:9px 0;" if mode == "ticker" else "padding:12px 0;")
                sep = f"border-top:1px solid {t['line']};" if idx else ""
                if side_fits:
                    rows.append(
                        f'<section style="display:flex;align-items:baseline;gap:12px;{sep}{row_pad}">'
                        + self.p(self.leaf(v), size, v_col, f"width:{int(ratio * 100)}%;flex-shrink:0;{v_ext}font-variant-numeric:tabular-nums;white-space:nowrap;")
                        + self.p(self.inline(lab), SMALL, t["text" if mode != "ticker" else "sub"], "flex:1;min-width:0;line-height:1.65;")
                        + "</section>"
                    )
                else:
                    rows.append(
                        f'<section style="{sep}{row_pad}">'
                        + self.p(self.leaf(v), size, v_col, f"{v_ext}font-variant-numeric:tabular-nums;")
                        + self.p(self.inline(lab), SMALL, t["sub" if mode != "folio" else "text"], "margin-top:4px;line-height:1.65;")
                        + "</section>"
                    )
            return f'<section style="{margin}{outer}">{"".join(rows)}</section>'

        raise ValueError(f"数据轴取值未实现：{mode}")

    def bars(self, lines, label="", below=None):
        t, rows, items = self.t, [], []
        for ln in lines:
            val, _, lab = ln.replace("|", "｜").partition("｜")
            items.append((val.strip(), lab.strip()))
        nums = [float(v) if re.fullmatch(r"\d+(\.\d+)?", v) else 0 for v, _ in items]
        nums = [v if math.isfinite(v) else 0 for v in nums]
        mx = max(nums, default=0)
        if label:
            rows.append(self.p(self.inline(label), SMALL, t["text"], "font-weight:600;"))
        rows.append(self.p(self.leaf("零起点 · 最长条代表本组最大值"), self.cap, t["muted"], "margin-top:2px;"))
        for (val, lab), num in zip(items, nums):
            w = f"{num / mx * 100:.6g}" if mx else "0"
            rows.append(
                f'<section style="display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-top:{self.g(14)}px;">'
                + self.p(self.inline(lab), SMALL, t["sub"], "flex:1;min-width:0;")
                + self.p(self.leaf(val), self.body, t["text"],
                         f"font-weight:600;font-family:{self.font};font-variant-numeric:tabular-nums;white-space:nowrap;flex-shrink:0;")
                + "</section>"
                + f'<section style="height:5px;background:{t["line"]};margin-top:5px;">'
                + f'<section style="width:{w}%;height:5px;background:{t["accent"]};">{BR}</section></section>'
            )
        return f'<section style="margin:{self.g(28)}px 0 {below if below is not None else self.g(28)}px;">{"".join(rows)}</section>'

    def table(self, rows, below=None):
        """语义表格：320px 下所有列均满足最小可读宽度才维持表格，否则自动降级为记录卡。"""
        t, out, mode = self.t, [], self.t["table"]
        if not rows or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError("表格行列数不一致，不能对齐数据")
        hpad = table_pad(t) // 2
        table_avail = MOBILE_TABLE_PX - 2 * self.inset
        if not table_fits(rows, self.inset, 2 * hpad):
            return self.table_stack(rows, below)
        widths = col_widths(rows, table_avail, 2 * hpad)
        table_extra = {
            "open": f"border-top:1px solid {t['text']};border-bottom:1px solid {t['line']};",
            "ink": f"border-top:2px solid {t['text']};border-bottom:1px solid {t['text']};",
            "atelier": f"border-top:1px solid {t['text']};border-bottom:1px solid {t['text']};",
            "feature": f"border-top:2px solid {t['text']};border-bottom:1px solid {t['text']};",
        }.get(mode, "")
        for i, cells in enumerate(rows):
            tag = "th" if i == 0 else "td"
            rendered = []
            for j, cell in enumerate(cells):
                pad = "9px 6px"
                bg, color = "", t["sub"] if i == 0 else t["text"]
                border = t["text"] if i == 0 and mode in ("open", "ink", "report", "feature") else t["line"]
                weight = 600 if i == 0 or (j == 0 and mode in ("report", "feature")) else 400
                family = f"font-family:{self.font};" if i == 0 and mode in ("ink", "atelier") else ""
                if mode == "warm":
                    pad = "11px 7px"
                    bg = f"background:{t['field']};" if i == 0 else ""
                    border = t["accent"] if i == 0 else t["line"]
                elif mode == "report":
                    pad = "8px 6px"
                    bg = f"background:{t['field']};" if i == 0 else ""
                    color = t["text"]
                elif mode == "atelier":
                    pad = "11px 7px"
                elif mode == "feature" and i == 0:
                    bg, color, border = f"background:{t['field']};", t["text"], t["text"]
                extra = "line-height:1.68;" + family
                if NUMERIC.fullmatch(cell):
                    extra += "font-variant-numeric:tabular-nums;"
                    room = widths[j] / 100 * table_avail - 2 * hpad
                    if text_px(cell) <= room + 1:
                        extra += "white-space:nowrap;"
                rendered.append(
                    f'<{tag} style="width:{widths[j]:.6g}%;padding:{pad};vertical-align:top;'
                    f'overflow-wrap:anywhere;word-break:normal;text-align:left;font-weight:{weight};{bg}">'
                    + self.p(self.inline(cell), SMALL, color, extra) + f"</{tag}>"
                )
            row_border = "" if i == len(rows) - 1 else f"border-bottom:1px solid {border};"
            row_attr = f' style="{row_border}"' if row_border else ""
            out.append(f"<tr{row_attr}>" + "".join(rendered) + "</tr>")
        return (f'<table style="width:100%;table-layout:fixed;border-collapse:collapse;{table_extra}'
                f'margin:{self.g(24)}px 0 {below if below is not None else self.g(24)}px;">'
                + "".join(out) + "</table>")

    def table_stack(self, rows, below=None):
        """窄屏记录卡降级：保留全部字段与顺序，字号不缩、长词不断裂。"""
        t, head = self.t, rows[0]
        mode = t["table"]
        blocks = []
        for n, row in enumerate(rows[1:], 1):
            # 若首列为短名称（≤8字），直接把首列作为卡片小标题，省去机械的“记录 01”冗余头
            lead_key = plain(row[0]).strip() if row else ""
            use_first_as_title = bool(lead_key and len(lead_key) <= 10 and len(head) >= 3)
            pairs = list(zip(head[1:], row[1:])) if use_first_as_title else list(zip(head, row))
            card_title = f"{plain(head[0])} · {lead_key}" if use_first_as_title else f"记录 {n:02d}"
            cells = [
                f'<section style="display:flex;gap:12px;padding:4px 0;">'
                + self.p(self.leaf(label), self.cap, t["muted"], "width:32%;flex-shrink:0;min-width:0;line-height:1.65;")
                + self.p(self.inline(value), SMALL, t["text"],
                         "flex:1;min-width:0;line-height:1.65;font-variant-numeric:tabular-nums;")
                + "</section>"
                for label, value in pairs
            ]
            card_style = (
                f"padding:12px 14px;background:{t['field']};border-radius:{t['radius']}px;margin-top:{10 if n > 1 else 0}px;"
                if mode in ("warm", "atelier") else
                f"padding:11px 0 9px;border-top:1px solid {t['text' if n == 1 and mode in ('report', 'feature', 'ink') else 'line']};"
            )
            blocks.append(
                f'<section style="{card_style}">'
                + self.p(self.leaf(card_title), SMALL, t["accent"] if mode == "feature" else t["text"],
                         f"margin-bottom:6px;font-weight:600;font-family:{self.font};")
                + "".join(cells) + "</section>"
            )
        return (f'<section style="margin:{self.g(24)}px 0 {below if below is not None else self.g(24)}px;">'
                + "".join(blocks) + "</section>")

    def lst(self, node, depth=0):
        t, mode = self.t, self.t["list"]
        ordered = node["ordered"]
        items = node["items"]
        start = node.get("start", 1)
        chinese = "一二三四五六七八九十"
        out = []
        for index, item in enumerate(items):
            number = start + index
            if item.get("marker"):
                marker = item["marker"]
            elif ordered:
                marker = {
                    "index": f"{number:02d}",
                    "dash": f"{number}.",
                    "chinese": (chinese[number - 1] + "、") if number <= len(chinese) else f"{number}、",
                    "report": f"{number:02d}",
                    "atelier": (chinese[number - 1] + "　") if number <= len(chinese) else f"{number}　",
                    "folio": f"{number:02d}/",
                }[mode]
            else:
                marker = {"index": "·", "dash": "—", "chinese": "·", "report": "—",
                          "atelier": "◇", "folio": "▪"}[mode]
            marker_color = t["accent"] if item.get("marker") or mode in ("dash", "folio") else t["muted"]
            marker_family = SERIF if mode in ("chinese", "atelier") else self.font
            marker_html = self.p(
                self.leaf(marker),
                SMALL if ordered or item.get("marker") else self.body,
                marker_color,
                f"font-weight:{600 if ordered or item.get('marker') else 500};font-family:{marker_family};",
            )
            width = (max(26, min(64, round(text_px(marker, SMALL) + 8))) if item.get("marker")
                     else 32 if mode in ("chinese", "atelier", "folio")
                     else 26 if ordered else 18)
            # 仅顶层条目可使用报表分隔线，嵌套子列表不重复画横线
            rule = f"border-top:1px solid {t['line']};padding-top:9px;" if (mode == "report" and depth == 0 and index > 0) else ""
            children = "".join(self.lst(child, depth + 1) for child in item.get("children", []))
            body = self.p(self.inline(item["text"])) + children
            out.append(
                f'<section style="display:flex;margin-bottom:{self.g(8 if depth else 10)}px;{rule}">'
                f'<section style="width:{width}px;flex-shrink:0;padding-top:1px;">{marker_html}</section>'
                f'<section style="flex:1;min-width:0;">{body}</section></section>'
            )
        if depth:
            return f'<section style="margin:6px 0 0 {min(depth * 12, 36)}px;">{"".join(out)}</section>'
        return f'<section style="margin:{self.g(8)}px 0 {self.g(22)}px;">{"".join(out)}</section>'

    def code(self, lang, body):
        t = self.t
        rows = "".join(
            f'<p style="margin:0;font-family:{MONO};font-size:{SMALL}px;line-height:1.68;white-space:pre-wrap;'
            f'overflow-wrap:anywhere;word-break:normal;tab-size:4;color:{t["text"]};">'
            + (self.leaf(ln) if ln.strip() else BR)
            + "</p>" for ln in body
        )
        label = self.micro(lang.upper(), extra=f"margin-bottom:8px;font-family:{MONO};") if lang else ""
        return (f'<section style="margin:{self.g(22)}px 0;padding:14px 16px;background:{t["field"]};'
                f'border-radius:{t["radius"]}px;">{label}{rows}</section>')

    def img(self, alt, src, role, below=None, above=None):
        t = self.t
        role0 = next(iter((role or "").split()), "")
        mt = self.g(24) if above is None else above
        mb = below if below is not None else mt
        if not src or TODO.match(src):
            return (
                f'<section style="margin:{mt}px 0 {mb}px;padding:32px 16px;border:1px dashed {t["muted"]};text-align:center;">'
                + self.micro("待补素材")
                + self.p(self.leaf(alt or "此处插入图片"), SMALL, t["sub"], "margin-top:8px;text-align:center;")
                + (self.p(self.leaf(f"职责：{role}"), self.cap, t["muted"], "margin-top:4px;text-align:center;") if role else "")
                + "</section>"
            )
        parts = (role or "").split()
        mode = parts[1].lower() if len(parts) > 1 else ""
        treat = t.get("image", "flush")
        img_extra, outer, pad, rule = "", [], [], None
        if treat == "soft":
            img_extra = f"border-radius:{t['radius']}px;"
        elif treat == "inkline":
            pad, rule = ["8px 0"], (1, t["line"])
        elif treat == "report":
            pad, rule = ["0 0 8px"], (1, t["line"])
        elif treat == "mat":
            pad = ["12px 12px 10px"]
            outer.append(f"background:{t['field']}")
        elif treat == "folio":
            pad, rule = ["0 0 8px"], (2, t["text"])
        if mode == "hero":
            img_extra += "width:100%;"
            pad, rule = ["0 0 12px"], (2, t["accent"])
        elif mode == "full-width":
            img_extra += "width:100%;"
        elif mode == "inset":
            outer += ["margin-left:8%", "margin-right:8%"]
        elif mode == "plate":
            pad = ["12px"]
            outer = [x for x in outer if not x.startswith("background:")] + [f"background:{t['field']}"]
        elif mode == "detail":
            outer += ["margin-left:4%", "margin-right:4%"]
        elif mode in ("sequence", "comparison"):
            pad, rule = [], None
        elif mode in ("evidence", "explainer", "data"):
            pad = ["0 0 0 12px"]
            outer.append(f"border-left:2px solid {t['accent']}")
        wrap = unique_style(";".join(outer) + ";") if outer else ""
        if pad:
            wrap += f"padding:{' '.join(pad)};"
        if rule:
            wrap += f"border-bottom:{rule[0]}px solid {rule[1]};"
        ai = bool(set(x.lower() for x in parts[2:]) & {"ai", "generated"})
        cap = (("AI 生成示意 · " if ai and "AI" not in (alt or "") else "")
               + ("GIF · " if src.lower().endswith(".gif") else "")
               + (alt or ""))
        cap_size = SMALL if role0 in FACT_ROLES else self.cap
        cap_color = t["sub"] if role0 in FACT_ROLES else t["muted"]
        cap_extra = "margin-top:8px;line-height:1.65;"
        if treat in ("inkline", "mat"):
            cap_extra += f"font-family:{self.font};"
        return (
            f'<section style="margin:{mt}px 0 {mb}px;{wrap}">'
            f'<img src="{H.escape(src)}" alt="{H.escape(alt or "")}" '
            f'style="max-width:100%;height:auto;display:block;margin:0 auto;{img_extra}" />'
            + (self.p(self.leaf(typo(cap)), cap_size, cap_color, cap_extra) if cap else "")
            + "</section>"
        )

    def hr(self):
        t, kind = self.t, self.t["divider"]
        if kind == "seal":
            inner = (f'<span style="display:inline-block;padding:1px 7px;border:1px solid {t["line"]};'
                     f'font-size:{MICRO}px;color:{t["muted"]};font-family:{SERIF};">{self.leaf("·")}</span>')
        elif kind == "short-rule":
            inner = self.rule(32, 2, t["accent"])
        elif kind == "pause":
            inner = self.rule(18, 1, t["line"])
        elif kind == "hairline":
            inner = f'<section style="width:100%;height:1px;background:{t["line"]};margin:0;">{BR}</section>'
        elif kind == "double":
            inner = (f'<section style="width:44px;height:1px;background:{t["text"]};margin:0 auto 4px;">{BR}</section>'
                     f'<section style="width:22px;height:1px;background:{t["line"]};margin:0 auto;">{BR}</section>')
        elif kind == "slash":
            inner = self.p(self.leaf("／"), DISPLAY - 2, t["accent"], "font-weight:700;line-height:1;text-align:center;")
        else:
            raise ValueError(f"分隔轴取值未实现：{kind}")
        return f'<section style="margin:{self.g(36)}px 0;text-align:center;">{inner}</section>'

    def signature(self, meta):
        t, out = self.t, []
        if meta.get("cta"):
            out.append(self.p(self.inline(meta["cta"]), SMALL, t["sub"]))
        if meta.get("bio"):
            out.append(self.p(self.leaf(typo(meta["bio"])), self.cap, t["muted"], "margin-top:10px;"))
        return (f'<section style="margin-top:{self.g(32)}px;padding-top:16px;border-top:1px solid {t["line"]};">'
                + "".join(out) + "</section>") if out else ""

    def toc(self, heads):
        t, mode = self.t, self.t["heading"]
        numbered = mode not in ("plain", "atelier")
        rows = []
        for n, h in enumerate(heads, 1):
            label = plain(h)
            if numbered and not ORDINAL.match(h.strip()):
                prefix = {"index": f"{n:02d}", "seal": f"{n:02d}", "report": f"{n:02d}/", "folio": f"{n:02d}"}[mode]
                rows.append(
                    f'<section style="display:flex;align-items:baseline;gap:8px;margin-top:{6 if n > 1 else 0}px;">'
                    + self.p(self.leaf(prefix), self.cap, t["accent"] if mode == "folio" else t["muted"],
                             "width:24px;flex-shrink:0;font-weight:600;font-variant-numeric:tabular-nums;")
                    + self.p(self.leaf(label), SMALL, t["text"],
                             f"flex:1;min-width:0;line-height:1.65;font-family:{self.font};"
                             + ("font-weight:600;" if mode == "folio" else ""))
                    + "</section>"
                )
            else:
                rows.append(
                    self.p(self.leaf(label), SMALL, t["text"],
                           f"margin-top:{6 if n > 1 else 0}px;line-height:1.68;font-family:{self.font};")
                )
        box_style = (
            f"margin:{self.g(6)}px 0 {self.g(30)}px;padding:13px 15px;background:{t['field']};border-radius:{t['radius']}px;"
            if mode in ("plain", "atelier") else
            f"margin:{self.g(6)}px 0 {self.g(30)}px;padding:12px 0 12px 12px;border-left:2px solid {t['line']};"
        )
        return f'<section style="{box_style}">{self.micro(t["toc_label"], extra="margin-bottom:8px;")}{"".join(rows)}</section>'


def api_title(t):
    return t.replace("|", "｜").strip()


def auto_digest(meta, blocks, limit=120):
    src = (next((b[0] for k, b in blocks if k == "lead"), "")
           or meta.get("deck", "")
           or next((b for k, b in blocks if k == "p"), ""))
    src = plain(src)
    if len(src) <= limit:
        return src
    cut = src[:limit]
    end = max(cut.rfind(ch) for ch in "。！？")
    if end >= 0:
        return cut[:end + 1]
    end = max(cut.rfind(ch) for ch in "，；、：")
    return (cut[:end] + "…") if end > 0 else src[:limit - 1] + "…"


def _img_mode(block_val):
    parts = (block_val[2] or "").split()
    return parts[1].lower() if len(parts) > 1 else ""


def _has_adjacent_explanation(blocks, idx):
    """检查事实/解释类图片（或同组 sequence/comparison）是否紧邻解释性正文或小节首段。"""
    mode = _img_mode(blocks[idx][1])
    start, end = idx, idx
    if mode in ("sequence", "comparison"):
        while start > 0 and blocks[start - 1][0] == "img" and _img_mode(blocks[start - 1][1]) == mode:
            start -= 1
        while end + 1 < len(blocks) and blocks[end + 1][0] == "img" and _img_mode(blocks[end + 1][1]) == mode:
            end += 1
    prose_kinds = ("p", "note", "quote", "table", "data", "bars")
    if start > 0 and blocks[start - 1][0] in prose_kinds and block_text(*blocks[start - 1]).strip():
        return True
    if end + 1 < len(blocks):
        nxt_k, nxt_v = blocks[end + 1]
        if nxt_k in prose_kinds and block_text(nxt_k, nxt_v).strip():
            return True
        if nxt_k in ("h2", "h3") and end + 2 < len(blocks):
            after_k, after_v = blocks[end + 2]
            if after_k in prose_kinds and block_text(after_k, after_v).strip():
                return True
    return False


def _asset_gate(meta, blocks, base):
    must, should = [], []
    imgs = [(i, b[1]) for i, b in enumerate(blocks) if b[0] == "img"]
    consecutive_standalone = 0
    prev_img_idx = -2

    for idx, (alt, src, role) in imgs:
        role = (role or "").strip()
        tokens = role.split()
        role0 = next(iter(tokens), "")
        mode = tokens[1].lower() if len(tokens) > 1 else ""

        if mode not in ("sequence", "comparison"):
            consecutive_standalone = (consecutive_standalone + 1) if idx == prev_img_idx + 1 else 1
            prev_img_idx = idx
            if consecutive_standalone == 3:
                should.append("连续出现 3 张以上独立图片且无正文间隔：请改为 sequence 叙事组、精选对比或删除无增量图片")
        else:
            consecutive_standalone = 0

        if mode == "comparison":
            def is_comparison(j):
                return 0 <= j < len(blocks) and blocks[j][0] == "img" and _img_mode(blocks[j][1]) == "comparison"
            if not is_comparison(idx - 1):
                end = idx
                while is_comparison(end):
                    end += 1
                if end - idx != 2:
                    must.append("comparison 必须恰好两张相邻图片；多组之间用文字分隔")
        if not role0:
            must.append("图片没有声明职责")
        elif role0 not in ROLES:
            must.append(f"图片职责未识别：{role0}")
        if mode in ("sequence", "comparison"):
            neighbors = [blocks[j][1] for j in (idx - 1, idx + 1) if 0 <= j < len(blocks) and blocks[j][0] == "img"]
            if not any(_img_mode(b) == mode for b in neighbors):
                must.append(f"图片 {src}：{mode} 需要相邻同组图片；单图请改表达方式")
            if not alt:
                must.append(f"图片 {src}：{mode} 必须在图注写明顺序或比较对象与口径")
        if mode and mode not in IMAGE_MODES:
            should.append(f"图片表达方式未识别：{tokens[1]}；按主题默认处理")
        unknown_mods = set(x.lower() for x in tokens[2:]) - {"ai", "generated", "parallel"}
        if unknown_mods:
            must.append(f"图片修饰词未识别：{'、'.join(sorted(unknown_mods))}")
        if "parallel" in [x.lower() for x in tokens[2:]] and mode != "comparison":
            must.append("parallel 只用于 comparison；默认纵向同宽对照")
        if role0 in FACT_ROLES and not (alt or "").strip():
            must.append("证据类图必须写清出处 / 口径 / 时间；解释图也需说明")
        if not src or TODO.match(src):
            continue
        if role0 in FACT_ROLES and not _has_adjacent_explanation(blocks, idx):
            should.append(f"图片 {src}（{role0}）未紧邻解释文字：说明/证据类图片须靠近其解释对象")
        if role0 in PROVENANCE_ROLES:
            note_near = blocks[idx + 1][1][1] if idx + 1 < len(blocks) and blocks[idx + 1][0] == "note" else []
            caption = " ".join([alt or "", role or ""] + list(note_near))
            if not re.search(r"来源|馆藏|授权|许可|版权|CC0|CC BY|©|摄影|摄于|截图|扫描|archive|collection", caption, re.I):
                must.append(f"图片 {src}：资料图/实拍必须在图注写明来源与授权（馆藏、CC BY、摄影者或档案编号）")
        if role0 in {"证据", "数据", "evidence", "data"}:
            context = (alt or "") + " " + role + " " + (" ".join(blocks[idx + 1][1][1]) if idx + 1 < len(blocks) and blocks[idx + 1][0] == "note" else "")
            if re.search(r"AI.*示意|生成.*示意|(?:^|\s)(?:ai|generated)(?:\s|$)", context, re.I):
                must.append("生成示意图不能承担证据/数据职责")
            elif not re.search(r"https?://\S+", context):
                must.append("证据/数据图片缺少可核对来源链接")
        p = local_path(src, base)
        if not os.path.isfile(p):
            must.append(f"图片不存在：{src}（本地化后再交付，或写成 todo）")
            continue
        wh, kb = img_size(p), os.path.getsize(p) // 1024
        if not wh or not all(wh):
            must.append(f"图片不是可识别格式：{src}")
        elif wh[0] < 600:
            should.append(f"{os.path.basename(src)} 分辨率偏低，核对手机端显示清晰度（{wh[0]}×{wh[1]}）")
        if kb > 1024:
            should.append(f"{os.path.basename(src)} 体积 {kb}KB：建议压到 1MB 以内再发布")

    cover = (meta.get("cover") or "").strip()
    if not cover:
        should.append(f"没有封面：公众号草稿需要一张 {COVER_RATIO}:1 封面（见 references/direction.md）")
    elif not TODO.match(cover):
        p = local_path(cover, base)
        if not os.path.isfile(p):
            must.append(f"封面文件不存在：{cover}")
        else:
            wh = img_size(p)
            if not wh or not all(wh):
                must.append("封面不是可识别图片")
            else:
                w, h = wh
                ratio = w / h
                if w < COVER_MIN_W:
                    should.append(f"封面 {w}×{h}：宽度低于建议基线 {COVER_MIN_W}px，复核缩略清晰度")
                if not COVER_BAND[0] <= ratio <= COVER_BAND[1]:
                    should.append(f"封面 {w}×{h}（{ratio:.2f}:1）：超出微信 {COVER_RATIO}:1 常见区间，确认主体位于中央安全区")
    return must, should


def _data_gate(meta, blocks, key):
    must, should = [], []
    th = THEMES.get(key or meta.get("theme", "paper"), THEMES["paper"])
    for i, (k, b) in enumerate(blocks):
        if k not in ("bars", "data"):
            continue
        note = blocks[i + 1][1] if i + 1 < len(blocks) and blocks[i + 1][0] == "note" else ("", [])
        source = " ".join(note[1])
        if not re.search(r"https?://\S+|\d{4}\s*(?:年|[-–/]\d{1,2}|\))|假设|演示|非统计", source):
            must.append(f"{k} 缺少紧邻来源 note：写清主体与日期（或一行地址），或明写假设/演示")
        if k == "data":
            if not b[1]:
                must.append("data 不能为空")
            room = MOBILE_TABLE_PX - 2 * th["grid"]["inset"]
            for line in b[1]:
                val, _, lab = line.replace("|", "｜").partition("｜")
                if not val.strip() or not lab.strip():
                    must.append("data 必须有数值与标签")
                elif text_px(val.strip(), th["type"]["data_size"]) + DATA_VALUE_SLACK > room:
                    must.append(f"data 数值在 320px 无法单行完整显示：{val.strip()[:24]}；请精简口径或改用文字")
            continue
        if not b[0]:
            must.append("bars 必须声明单一单位/口径：写在 ::: bars 后")
        items = [(v.strip(), lab.strip()) for v, _, lab in (x.replace("|", "｜").partition("｜") for x in b[1])]
        for v, lab in items:
            if not re.fullmatch(r"\d+(\.\d+)?", v):
                must.append(f"bars 的值必须是数字：{v or '（空）'}")
            else:
                num = float(v)
                if not math.isfinite(num):
                    must.append("bars 的值必须是有限数字")
                elif text_px(v, th["grid"]["body"]) > 110:
                    must.append(f"bars 数值过长：{v[:24]}；改用表格或文字")
            if not lab:
                must.append(f"bars 的 {v} 缺少标签")
        if len(items) < 2:
            must.append("bars 至少 2 项：单项对比不成立，直接用文字")
    return must, should


def _structure_gate(meta, blocks, key):
    must, should = [], []
    th = THEMES.get(key or meta.get("theme", "paper"), THEMES["paper"])
    inset = th.get("grid", {}).get("inset", 0)
    for i, (k, b) in enumerate(blocks):
        if k == "hr":
            prev_k = blocks[i - 1][0] if i > 0 else ""
            next_k = blocks[i + 1][0] if i + 1 < len(blocks) else ""
            if prev_k == "h2" or next_k == "h2":
                should.append("分隔线紧邻 H2 标题：章节标题已承担转场，渲染时已合并冗余分隔线")
        if k == "table":
            if not b or any(len(row) != len(b[0]) for row in b):
                must.append("表格行列数不一致，不能对齐数据")
            elif not table_fits(b, inset, table_pad(th)):
                should.append(f"表格 {len(b[0])} 列在 320px 无法维持可读列宽，已自动降级为记录卡堆叠")
        if k == "note":
            label, lines = b[0] or "", b[1]
            text = [ln for ln in lines if not re.fullmatch(r"\s*https?://\S+\s*", ln)]
            if re.search(r"来源|口径", label) and len(text) > 2:
                must.append("数据来源与口径过长：控制在两行内（来源一行、口径一行），URL 单独成行不计")
            for ln in text:
                if len(ln) > 64:
                    should.append(f"注释行偏长（{len(ln)} 字）：来源短写「主体（日期）」，口径一句话")
                    break
    title = meta.get("title", "")
    if not api_title(title):
        must.append("缺少标题")
    for field, value, cap in (("title", api_title(title), 32), ("author", meta.get("author", ""), 16), ("digest", meta.get("digest", ""), 120)):
        if len(value) > cap:
            must.append(f"{field} 超过发布上限 {cap}：请编辑收窄，不静默截断")
    if meta.get("density", "standard") not in ("dense", "standard", "airy"):
        must.append(f"density「{meta['density']}」不存在：仅支持 dense / standard / airy")
    return must, should


def compose_gate(meta, blocks, base=".", key=None, review=None):
    must, should = [], []
    for m, s in (_asset_gate(meta, blocks, base), _data_gate(meta, blocks, key), _structure_gate(meta, blocks, key)):
        must.extend(m)
        should.extend(s)
    review = review or audit(meta, blocks)
    for issue in review["issues"]:
        if issue["severity"] == "must":
            must.append(f"编辑必须修 · {issue['code']} · {issue['location']}：{issue['problem']} → {issue['action']}")
    return list(dict.fromkeys(must)), list(dict.fromkeys(should))


def evidence(meta, blocks, key=None):
    kinds = [k for k, _ in blocks]
    imgs = [b for k, b in blocks if k == "img"]
    fs = first_screen(meta, blocks)
    out = [f"结构 · {doc_len(blocks)}字 · H2 {kinds.count('h2')} · 引文 {kinds.count('quote')} · peak {kinds.count('peak')}"]
    out.append(f"首屏 · {' > '.join(fs['layers']) or '正文直入'} · 重元素 {fs['weight']}"
               + ("（多个重入口抢夺首屏，建议只留一个）" if fs["weight"] > 1 else ""))
    for alt, src, role in imgs:
        out.append(f"资产 · {src or 'todo'} · {(role or '').strip() or '职责缺失'} · {alt}")
    th = THEMES.get(key or meta.get("theme", "paper"), THEMES["paper"])
    inset = th.get("grid", {}).get("inset", 0)
    for i, (k, b) in enumerate(blocks):
        if k in ("bars", "data"):
            note = blocks[i + 1][1] if i + 1 < len(blocks) and blocks[i + 1][0] == "note" else ("", [])
            out.append(f"图示 · {k} · {b[0]} · {len(b[1])}项 · {note[0] or '来源待补'}（字面存在不等于已核真）")
        if k == "table" and b and not table_fits(b, inset, table_pad(th)):
            out.append(f"表格 · {len(b)}行×{len(b[0])}列 · 320px 下已自动降级为记录卡")
    out.append("复核 · 对照 320/360/390/430px 检查断行、溢出与图文关系；封面双裁切见独立预览")
    return out


PREVIEW = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{margin:0;background:#ECEAE5;font-family:-apple-system,'PingFang SC','Noto Sans CJK SC',sans-serif}}
.bar{{display:flex;justify-content:space-between;align-items:center;gap:10px 12px;flex-wrap:wrap;padding:10px 16px;
background:#fff;border-bottom:1px solid #E5E3DD;font-size:12px;color:#6E6A63}}
button{{border:0;background:#1F1D1A;color:#fff;padding:7px 14px;border-radius:5px;font-size:12px;cursor:pointer;white-space:nowrap;flex-shrink:0}}
.phone{{position:relative;max-width:430px;margin:20px auto 48px;background:#fff;padding:24px 16px 44px;box-sizing:border-box}}
.nt{{margin-bottom:20px}}
.nt h1{{margin:0 0 10px;font-size:22px;line-height:1.4;font-weight:700;color:#191919;letter-spacing:-.01em;
font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Noto Sans CJK SC',sans-serif;line-break:strict;overflow-wrap:anywhere;word-break:normal;text-wrap:pretty}}
.nt .au{{margin:0;font-size:14px;line-height:1.5;color:#888888}}
.nt .au b{{font-weight:500;color:#576B95;margin-right:8px}}
.cv{{max-width:430px;margin:20px auto 0;background:#fff;padding:16px;box-sizing:border-box}}
.cv h4{{margin:0 0 8px;font-size:12px;color:#746F66;font-weight:600}}
.cv img{{display:block;width:100%;background:#F0EEE9}}
.as{{margin-top:12px;padding-top:10px;border-top:1px solid #EFEDE9}}
.hint{{margin:14px 0 0;font-size:12px;line-height:1.7;color:#746F66}}</style></head>
<body><div class="bar"><span>{theme} · 移动预览（原生标题栏仅为模拟）</span><button onclick="cp(this)">复制正文（图片另传）</button></div>
<div class="phone">{native}<div id="c">{body}</div></div>{cover}{assets}
<script>function cp(b){{var c=document.getElementById('c'), r=document.createRange();r.selectNodeContents(c);
var s=getSelection();s.removeAllRanges();s.addRange(r);
function copy(e){{var n=c.cloneNode(true);n.querySelectorAll('img').forEach(function(i){{i.setAttribute('src',i.dataset.local||i.getAttribute('src'));i.removeAttribute('data-local')}});e.clipboardData.setData('text/html',n.innerHTML);e.clipboardData.setData('text/plain',c.innerText);e.preventDefault()}}
document.addEventListener('copy',copy);var ok=false;try{{ok=document.execCommand('copy')}}finally{{document.removeEventListener('copy',copy)}}
if(ok)s.removeAllRanges();b.textContent=ok?'正文已复制；本地图片须另传':'请手动复制正文，图片另传';setTimeout(function(){{b.textContent='复制正文（图片另传）'}},2200)}}</script>
</body></html>"""


def preview_image(src, base):
    if re.match(r"^(?:[a-z][a-z0-9+.-]*:|//)", src, re.I):
        return ""
    path = local_path(src, base)
    if not os.path.isfile(path):
        return src
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        return src
    with open(path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("ascii")
    return f"data:{mime};base64," + encoded


def cover_block(meta, base):
    src = (meta.get("cover") or "").strip()
    if not src or TODO.match(src):
        return ('<div class="cv"><h4>封面</h4><p class="hint" style="margin:0">未设置封面。'
                f'公众号草稿需提供 {COVER_RATIO}:1 首图封面（见 references/direction.md）。</p></div>')
    p = local_path(src, base)
    wh = img_size(p) if os.path.exists(p) else None
    info = f"{wh[0]}×{wh[1]}（{wh[0] / wh[1]:.2f}:1）" if wh else "尺寸未知"
    warn = "" if wh and COVER_BAND[0] <= wh[0] / wh[1] <= COVER_BAND[1] else " 主体须位于中央安全区。"
    return (f'<div class="cv"><h4>封面模拟裁切 · {info}</h4>'
            f'<img src="{H.escape(src)}" alt="封面 2.35:1 模拟" style="aspect-ratio:2.35/1;object-fit:cover">'
            f'<h4 style="margin:14px 0 8px">1:1 信息流/转发卡片缩略</h4>'
            f'<img src="{H.escape(src)}" alt="封面 1:1 模拟" style="width:128px;height:128px;object-fit:cover">'
            f'<p class="hint">封面默认不压字。{warn} 本地仅为几何模拟；主体可见性与微信客户端真实裁切均为 UNVERIFIED。</p></div>')


def asset_sheet(blocks, base="."):
    imgs = [b for k, b in blocks if k == "img"]
    if not imgs:
        return ""
    rows = []
    for alt, src, role in imgs:
        tag = H.escape(role or "（未声明职责）")
        if not src or TODO.match(src):
            rows.append(f'<div class="as"><p class="hint" style="margin:0">待补 · {tag}<br>{H.escape(alt or "（无说明）")}</p></div>')
            continue
        fp = local_path(src, base)
        if not os.path.isfile(fp):
            rows.append(f'<div class="as"><p class="hint" style="margin:0">{tag} · 文件不存在：{H.escape(src)}</p></div>')
            continue
        wh, kb = img_size(fp), os.path.getsize(fp) // 1024
        info = f"{wh[0]}×{wh[1]}（{wh[0] / wh[1]:.2f}:1）· {kb}KB" if wh else f"{kb}KB"
        rows.append(f'<div class="as"><p class="hint" style="margin:0">{H.escape(src)} · {tag} · {info}<br>{H.escape(alt or "（无说明）")}</p></div>')
    return (f'<div class="cv"><h4>正文资产卡 · {len(imgs)} 张</h4>'
            + "".join(rows)
            + '<p class="hint">未亲眼核验原图前，可见主体、景别、安全区一律记为 UNVERIFIED，不得凭文件名或 alt 推断。</p></div>')


def render(md, theme=None):
    meta, blocks = parse(md)
    key = theme or meta.get("theme", "paper")
    if key not in THEMES:
        raise ValueError(f"未知主题 {key}，可选：{', '.join(THEMES)}")
    r = R(THEMES[key], meta.get("density", "standard"))
    out, n = [], 0
    if meta.get("kicker"):
        out.append(f'<section style="margin-bottom:{r.g(10)}px;">'
                   + r.micro(typo(meta["kicker"]), color=r.t["accent"], extra="letter-spacing:0.1em;font-weight:600;")
                   + "</section>")
    if meta.get("deck"):
        out.append(f'<section style="margin-bottom:{r.g(18)}px;">'
                   + r.p(r.inline(meta["deck"]), r.body, r.t["sub"], f"font-family:{r.font};") + "</section>")

    heads = [b[1] for b in blocks if b[0] == "h2"]
    toc_done = meta.get("toc", "").lower() not in ("true", "yes", "1") or len(heads) < 3
    toc_after_p, seen_p = any(k == "p" for k, _ in blocks), False
    attach = ("bars", "data", "table", "img")
    consumed = set()

    for i, (kind, b) in enumerate(blocks):
        if i in consumed:
            continue
        nxt = blocks[i + 1][0] if i + 1 < len(blocks) else ""
        prev = blocks[i - 1][0] if i > 0 else ""
        below = 8 if nxt == "note" else None
        will_insert_toc_after = (kind == "p" and not seen_p and not toc_done and nxt != "lead")

        if not toc_done and kind != "lead" and (seen_p or not toc_after_p):
            out.append(r.toc(heads))
            toc_done = True

        if kind == "h2":
            n += 1
            out.append(r.h2(b, n))
        elif kind == "h3":
            out.append(r.h3(b))
        elif kind == "p":
            effective_next = "toc" if will_insert_toc_after else nxt
            out.append(r.para(b, next_kind=effective_next))
            seen_p = True
        elif kind == "lead":
            out.append(r.lead(b[0], b[1]))
        elif kind == "quote":
            out.append(r.quote(b[0], b[1]))
        elif kind == "peak":
            out.append(r.peak(peak_text(b)))
        elif kind == "note":
            out.append(r.note(*b, tight=i > 0 and blocks[i - 1][0] in attach))
        elif kind == "unknown":
            out.append(r.unknown(*b))
        elif kind == "data":
            out.append(r.data(b[1], below=below))
        elif kind == "bars":
            out.append(r.bars(b[1], b[0], below=below))
        elif kind == "table":
            out.append(r.table(b, below=below))
        elif kind == "list":
            out.append(r.lst(b))
        elif kind == "code":
            out.append(r.code(*b))
        elif kind == "img":
            parts = (b[2] or "").split()
            mode = parts[1].lower() if len(parts) > 1 else ""
            mods = {x.lower() for x in parts[2:]}
            if mode == "sequence":
                end, group = i, []
                while end < len(blocks) and blocks[end][0] == "img" and _img_mode(blocks[end][1]) == "sequence":
                    group.append(blocks[end][1])
                    end += 1
                if len(group) >= 2:
                    after_group = blocks[end][0] if end < len(blocks) else ""
                    mb = 8 if after_group == "note" else r.g(24)
                    out.append(
                        f'<section style="margin:{r.g(24)}px 0 {mb}px;">'
                        + "".join(r.img(f"{idx_g:02d} · {im[0]}", im[1], im[2],
                                        below=0 if idx_g == len(group) else 14, above=0 if idx_g == 1 else 14)
                                  for idx_g, im in enumerate(group, 1))
                        + "</section>"
                    )
                    consumed.update(range(i + 1, end))
                    continue
            if mode == "comparison" and i + 1 < len(blocks) and blocks[i + 1][0] == "img":
                other = blocks[i + 1][1]
                other_parts = (other[2] or "").split()
                if _img_mode(other) == "comparison":
                    after_pair = blocks[i + 2][0] if i + 2 < len(blocks) else ""
                    mb = 8 if after_pair == "note" else r.g(24)
                    if "parallel" in mods and "parallel" in {x.lower() for x in other_parts[2:]}:
                        cells = [r.img(f"对照 {idx_c} · {im[0]}", im[1], im[2], below=0, above=0)
                                 for idx_c, im in enumerate((b, other), 1)]
                        out.append(
                            f'<table style="width:100%;table-layout:fixed;border-collapse:collapse;margin:{r.g(24)}px 0 {mb}px;">'
                            "<tr>" + "".join(
                                '<td style="width:50%;vertical-align:top;padding:0 4px;overflow-wrap:anywhere;">' + cell + "</td>"
                                for cell in cells
                            ) + "</tr></table>"
                        )
                    else:
                        # 纵向同宽成组对照：收紧组内间距，使两图在同一阅读视野内形成清晰比较关系
                        def _cmp_cap(idx_c, text):
                            return text if re.match(r"^(?:对照|近景|远景|图\s*[AB12])", text.strip()) else f"对照 {idx_c:02d} · {text}"
                        out.append(
                            f'<section style="margin:{r.g(24)}px 0 {mb}px;">'
                            + r.img(_cmp_cap(1, b[0]), b[1], b[2], below=12, above=0)
                            + r.img(_cmp_cap(2, other[0]), other[1], other[2], below=0, above=12)
                            + "</section>"
                        )
                    consumed.add(i + 1)
                    continue
            out.append(r.img(*b, below=below))
        elif kind == "hr":
            # 紧邻 H2 的水平分隔线冗余（H2 已建立章节转场），静默合并避免双线叠加
            if prev == "h2" or nxt == "h2":
                continue
            out.append(r.hr())
        else:
            raise ValueError(f"未知原语 ::: {kind}（可用：peak / note / unknown / data / bars）")

    sig = r.signature(meta)
    if sig:
        out.append(sig)
    t = THEMES[key]
    pad = f"padding-left:{r.inset}px;padding-right:{r.inset}px;" if r.inset else ""
    body = (f'<section style="font-family:{r.reading_font};font-size:{r.body:g}px;color:{t["text"]};line-height:{t["leading"]};'
            f'letter-spacing:normal;text-align:left;line-break:strict;overflow-wrap:break-word;{pad}">'
            + "".join(out) + "</section>")
    return key, meta, blocks, body


def contrast_checks(theme):
    t = THEMES[theme]
    pairs = [(role, "#FFFFFF") for role in ("text", "sub", "muted", "accent")]
    pairs += [(role, t["field"]) for role in ("text", "sub", "muted")]
    pairs.append(("on_dark", t["dark"]))
    return [{"foreground_role": role, "foreground": t[role], "background": bg,
             "ratio": round(contrast(t[role], bg), 3), "required": 4.5,
             "pass": contrast(t[role], bg) >= 4.5} for role, bg in pairs]


def build(md_path, theme=None, out=None):
    base = os.path.dirname(os.path.abspath(md_path))
    with open(md_path, encoding="utf-8") as f:
        source_text = f.read()
    key, meta, blocks, body = render(source_text, theme)
    for src in [meta.get("cover", "")] + [b[1] for k, b in blocks if k == "img"]:
        if src and not TODO.match(src):
            local_path(src, base)
    out = out or f"{os.path.splitext(md_path)[0]}_{key}.html"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    out_base = os.path.dirname(os.path.abspath(out))

    def output_src(src):
        if not src or TODO.match(src) or re.match(r"^(?:[a-z][a-z0-9+.-]*:|//)", src, re.I):
            return src
        original = local_path(src, base)
        target = local_path(src, out_base)
        if os.path.isfile(original) and os.path.realpath(original) != os.path.realpath(target):
            os.makedirs(os.path.dirname(target), exist_ok=True)
            if os.path.exists(target) and sha256(target) != sha256(original):
                raise ValueError(f"输出素材冲突，拒绝覆盖：{src}")
            if not os.path.exists(target):
                shutil.copyfile(original, target)
        return src

    body = re.sub(r'(<img\b[^>]*src=")([^"]+)(")',
                  lambda m: m[1] + H.escape(output_src(H.unescape(m[2]))) + m[3], body)
    with open(out, "w", encoding="utf-8") as f:
        f.write(body)
    prev = os.path.splitext(out)[0] + "_预览.html"
    nt = H.escape(api_title(meta.get("title", "")))
    au_parts = []
    if meta.get("author"):
        au_parts.append(f"<b>{H.escape(meta['author'])}</b>")
    if meta.get("date"):
        au_parts.append(H.escape(meta["date"]))
    native = (f'<div class="nt"><h1>{nt}</h1>' + (f'<p class="au">{"".join(au_parts)}</p>' if au_parts else "") + "</div>") if nt else ""
    preview = PREVIEW.format(
        title=H.escape(meta.get("title", "")),
        theme=THEMES[key]["name"],
        cover=cover_block(dict(meta, cover=output_src(meta.get("cover", ""))), out_base),
        assets=asset_sheet([(k, (b[0], output_src(b[1]), b[2])) if k == "img" else (k, b) for k, b in blocks], out_base),
        native=native,
        body=body,
    )
    preview = re.sub(
        r'(<img\b[^>]*src=")([^"]+)(")',
        lambda m: m[1] + H.escape(preview_image(H.unescape(m[2]), out_base)) + m[3] + ' data-local="' + m[2] + '"',
        preview,
    )
    with open(prev, "w", encoding="utf-8") as f:
        f.write(preview)

    cover = (meta.get("cover") or "").strip()
    m1, s1 = check(body)
    review = audit(meta, blocks)
    m2, s2 = compose_gate(meta, blocks, base, key, review)
    s2 = [f"平台层建议：{x}" for x in s1] + s2
    contrasts = contrast_checks(key)
    for pair in contrasts:
        if not pair["pass"]:
            m2.append(f"色彩对比不足：{pair['foreground_role']} / {pair['background']} 为 {pair['ratio']:.2f}:1，要求 ≥4.5")
    fs = first_screen(meta, blocks)
    if fs["weight"] > 1:
        s2.append(f"首屏含 {fs['weight']} 个重入口（{'、'.join(fs['layers'])}）：建议只保留一个主入口")

    asset_records = []
    for src in sorted(set([output_src(b[1]) for k, b in blocks if k == "img" and b[1] and not TODO.match(b[1])]
                          + ([output_src(cover)] if cover and not TODO.match(cover) else []))):
        resolved_out = local_path(src, out_base)
        if os.path.isfile(resolved_out):
            wh = img_size(resolved_out)
            asset_records.append({
                "path": src,
                "sha256": sha256(resolved_out),
                "source_path": src,
                "source_sha256": sha256(local_path(src, base)),
                "dimensions": list(wh) if wh else None,
                "subject_visibility": "UNVERIFIED",
                "safe_zone": "UNVERIFIED",
            })

    side = {
        "title": meta.get("title", ""),
        "api_title": api_title(meta.get("title", "")),
        "author": meta.get("author") or "",
        "digest": meta.get("digest") or auto_digest(meta, blocks),
        "cover": "" if (not cover or TODO.match(cover)) else output_src(cover),
        "source_url": meta.get("source", ""),
        "theme": key,
        "skill_version": SKILL_VERSION,
        "theme_config_sha256": THEME_CONFIG_SHA256,
        "theme_profile": {axis: THEMES[key][axis] for axis in
                          ("lead", "heading", "h3", "quote", "peak", "divider", "image", "data", "table", "list")},
        "grid": dict(THEMES[key].get("grid", {})),
        "contrast_checks": contrasts,
        "decision": review["decision"],
        "article_type": review["type"]["key"],
        "composition_evidence": {
            "first_screen_layers": fs["layers"],
            "first_screen_weight": fs["weight"],
            "h2_count": sum(k == "h2" for k, _ in blocks),
            "body_characters": doc_len(blocks),
            "scope": "源稿开篇结构统计；真实首屏像素高度须在 320/360/390/430px 浏览器验证",
        },
        "editorial_review": review,
        "integrity_version": 2,
        "source": {"path": os.path.abspath(md_path), "sha256": sha256(md_path)},
        "assets": asset_records,
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "render_errors": m1 + m2,
        "pending_assets": any(not b[1] or TODO.match(b[1]) for k, b in blocks if k == "img"),
        "verification_gates": {
            "browser_multi_width": "UNVERIFIED",
            "wechat_api_readback": "UNVERIFIED",
            "wechat_real_device": "UNVERIFIED",
        },
    }
    meta_path = os.path.splitext(out)[0] + ".meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(side, f, ensure_ascii=False, indent=2)
    return {
        "key": key, "meta": meta, "blocks": blocks, "body": body, "side": side,
        "out": out, "preview": prev, "meta_path": meta_path,
        "gates": (("Gate 1 Platform", m1, s1), ("Gate 2 Composition", m2, s2)),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md", nargs="?")
    ap.add_argument("--theme", choices=list(THEMES))
    ap.add_argument("-o", "--out")
    ap.add_argument("--against", help="原稿 .md：比对改写前后的事实单元与作者声音")
    ap.add_argument("--ledger", help="修改台账 .md：五列表格，逐行校验收益与原文定位")
    ap.add_argument("--deliver", help="交付目录：一次产出源稿/正文/预览/meta/修改记录/验收与本地素材")
    a = ap.parse_args()
    if not a.md:
        ap.error("需要一个 markdown 文件")
    if os.path.splitext(a.md)[1].lower() not in (".md", ".markdown", ".txt"):
        ap.error("仅支持 UTF-8 Markdown/纯文本；DOCX 请先用 extract_docx.py 转换")

    deliver = os.path.abspath(a.deliver) if a.deliver else ""
    if deliver:
        os.makedirs(deliver, exist_ok=True)
    out = os.path.join(deliver, "正文.html") if deliver else a.out
    res = build(a.md, a.theme, out)
    key, meta, blocks, side = res["key"], res["meta"], res["blocks"], res["side"]
    g1, g2 = res["gates"]
    m1, m2, s2 = g1[1], g2[1], g2[2]
    review = side["editorial_review"]

    facts_diff, voice_diff = None, None
    if a.against:
        with open(a.against, encoding="utf-8") as f:
            original_meta, original_blocks = parse(f.read())
        facts_diff = compare_facts(original_blocks, blocks, original_meta, meta)
        loose = introduced_without_source(blocks, facts_diff["introduced"])
        declared = {x.strip() for x in (meta.get("removed_facts") or "").replace("，", ",").split(",") if x.strip()}
        for item in facts_diff["dropped"]:
            if item in declared:
                continue
            change, why = classify_fact_change(blocks, "num", item) if re.search(r"\d", item) else ("lost", "")
            if change == "lost":
                change, why = classify_fact_change(blocks, "date", item)
            message = f"原稿事实单元在改稿中消失：{item}"
            if change in ("moved", "rounded"):
                s2.append(f"{message}；{why}（结构搬家/概括不等于删除，口径仍须人工确认）")
            else:
                m2.append(f"{message}；确认是删除还是改写，确属有意删除请声明 removed_facts")
        for item in loose:
            change, why = classify_fact_change(blocks, "date", item) if not re.search(r"[^\d\-\s]", item) else ("added", "")
            if change == "rounded":
                s2.append(f"改稿新增「{item}」；{why}（确认未替代精确值）")
            else:
                m2.append(f"改稿新增事实单元「{item}」附近缺少可核对来源")
        for change in facts_diff["precision_changes"] + facts_diff["qualifier_changes"]:
            m2.append(f"事实精度或限定词变化需回源确认：{change}")
        for quote in facts_diff["dropped_quotes"] + facts_diff["introduced_quotes"]:
            m2.append(f"直接引语变化需逐字回源：{quote[:40]}")
        voice_diff = compare_voice(original_blocks, blocks)
        side["fact_diff"] = facts_diff
        side["voice_diff"] = voice_diff
        for change in voice_diff["changes"]:
            s2.append(f"作者声音形态变化：{change['mark']} {change['original']} → {change['edited']}（{change['note']}）")
        side["render_errors"] = m1 + m2

    ledger_rows, ledger_problems = [], []
    if a.ledger:
        with open(a.ledger, encoding="utf-8") as f:
            ledger_rows, ledger_problems = parse_ledger(f.read())
        for row in ledger_rows:
            if not locate(row["位置"], blocks):
                ledger_problems.append(f"台账位置「{row['位置']}」无法在成稿定位")
        if ledger_problems:
            m2.extend(f"修改台账不合格：{p}" for p in ledger_problems)
            side["render_errors"] = m1 + m2
        side["ledger"] = {"rows": ledger_rows, "problems": ledger_problems}
    if ledger_problems or facts_diff is not None:
        with open(res["meta_path"], "w", encoding="utf-8") as f:
            json.dump(side, f, ensure_ascii=False, indent=2)

    for issue in review["issues"]:
        print(f"编辑提示 · {issue['severity']:<6} · {issue['location']} · {issue['problem']} → "
              f"{issue['action']}；收益：{issue['benefit']}（{issue['class']}，需要：{issue['needs']}）")
    print(f"{THEMES[key]['name']} → {res['out']}\n预览 → {res['preview']}\n"
          f"发布字段 → {res['meta_path']}\n")
    print("Gate 3 客观结构证据")
    for line in evidence(meta, blocks, key):
        print("  " + line)
    for gate, must, should in res["gates"]:
        print(f"\n{gate}: {'FAIL' if must else 'PASS'}")
        for x in must:
            print("  必须改 ·", x)
        for x in should:
            print("  建议改 ·", x)
    if facts_diff is not None:
        print(f"\n事实单元比对：保留 {len(facts_diff['preserved'])}/{facts_diff['source_units']} · "
              f"消失 {len(facts_diff['dropped'])} · 新增 {len(facts_diff['introduced'])}（仅字面比对）")
    if ledger_problems:
        print("\n修改台账：" + "；".join(ledger_problems))

    if deliver:
        report = render_report(review, facts_diff, ledger_problems, voice_diff)
        report += "\n## 类型策略\n\n" + "\n".join(f"- {x}" for x in strategy_notes(meta, blocks)) + "\n"
        if ledger_rows:
            report += "\n## 修改台账（已校验）\n\n| 位置 | 问题 | 动作 | 收益 | 保留检查 |\n|---|---|---|---|---|\n"
            report += "\n".join(f"| {r['位置']} | {r['问题']} | {r['动作']} | {r['收益']} | {r['保留检查']} |"
                                for r in ledger_rows) + "\n"
        with open(os.path.join(deliver, "修改记录.md"), "w", encoding="utf-8") as f:
            f.write(report)
        acceptance = [
            "# 验收结果", "",
            f"- 渲染版本：`{SKILL_VERSION}`",
            f"- 主题：`{key}`（{THEMES[key]['name']}）", "",
        ]
        for gate, must, should in res["gates"]:
            acceptance.append(f"## {gate}：{'FAIL' if must else 'PASS'}")
            acceptance.append("")
            acceptance += [f"- 必须改：{x}" for x in must] or ["- 必须改：无"]
            acceptance += [f"- 建议改：{x}" for x in should] or ["- 建议改：无"]
            acceptance.append("")
        acceptance += [
            "## 三级验收状态（严禁互相冒充）", "",
            "| 级别 | 能证明 | 当前状态 |", "|---|---|---|",
            "| 浏览器验证 | 本地 320/360/390/430px 无溢出、最小字号≥12px、数值不拆断 | UNVERIFIED（须附四宽度实测截图） |",
            "| 微信 API 回读 | 草稿 title/content/thumb_media_id 与本地逐字一致 | UNVERIFIED（须授权账号执行 `publish.py`） |",
            "| 微信真机验收 | 客户端清洗后样式、后台重开、iOS/Android 阅读与双入口封面裁切 | UNVERIFIED（须真机实测） |",
            "",
            "## 未验证清单（UNVERIFIED）", "",
            "- 图像可见主体、景别与裁切安全区：未人工核看原图前一律为 UNVERIFIED",
            "- 外部独立第二信源逐项事实核真：UNVERIFIED",
            "- 微信真机粘贴/草稿保存重开与多端渲染：UNVERIFIED",
        ]
        with open(os.path.join(deliver, "验收.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(acceptance) + "\n")
        shutil.copyfile(a.md, os.path.join(deliver, "源稿.md"))
        print(f"\n交付包 → {deliver}（源稿/正文/预览/meta/修改记录/验收" + ("/素材" if side["assets"] else "") + "）")

    if not meta.get("author"):
        print("提示：未填写 author，草稿原生作者栏将留空。")
    sys.exit(1 if m1 or m2 else 0)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as e:
        sys.exit(f"输入错误：{e}")
