#!/usr/bin/env python3
"""Composed Markdown → 公众号 HTML + 390px 预览 + Gate 1/2（一次调用）。

    render.py article.md [--theme paper|letter|ink|frost|bone|folio] [-o out.html]
    render.py article.md --against 原稿.md     改写前后的事实单元与台账比对
    render.py article.md --deliver 交付目录     一次产出源稿/正文/预览/meta/修改记录/验收

产出 {stem}_{theme}.html 与 {stem}_{theme}_预览.html（预览另含封面两种裁切）。
语法见 SKILL.md。退出码 1 = 存在「必须改」。
判断在 SKILL.md 与 editorial.py 的边界内；本文件只执行可确定的排版与检查。
"""
import argparse
import base64
import hashlib
import mimetypes
import html as H
import json
import math
import os
import re
import struct
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check import check  # noqa: E402
from safety import local_path, sha256, contrast
from editorial import (audit, block_text, classify_fact_change, compare_facts,  # noqa: E402
                       compare_voice, doc_len,
                       first_screen, introduced_without_source, locate, parse_ledger,
                       plain, peak_text, render_report, strategy_notes)

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_VERSION = "7.0.0"
THEMES_PATH = os.path.join(HERE, "..", "assets", "themes.json")
with open(THEMES_PATH, "rb") as _theme_file:
    THEME_CONFIG_BYTES = _theme_file.read()
THEME_CONFIG_SHA256 = hashlib.sha256(THEME_CONFIG_BYTES).hexdigest()
THEMES = json.loads(THEME_CONFIG_BYTES.decode("utf-8"))

# 每个主题轴的**取值全集**必须在这里登记，且 renderer 有对应分支。
# 没有登记的取值会在载入时直接报错：主题配置写错一个词不会再静默落回默认样式。
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
    """主题配置的结构、取值与字号层级：不合格就拒绝运行，而不是渲染出一份错版式。

    字号层级是这里的硬约束：导语必须弱于章节标题，正文字号必须小于两者，
    图注不大于正文。它们不是审美偏好，而是「读者能否一眼分出层级」的前提。
    """
    problems = []
    for name, t in themes.items():
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
        if problems:
            continue
        ty, grid = t["type"], t["grid"]
        if not ty["heading_size"] > ty["lead_size"]:
            problems.append(f"{name}：章节标题 {ty['heading_size']}px 未大于导语 {ty['lead_size']}px，"
                            f"首屏会出现两个同级入口")
        if not ty["lead_size"] > grid["body"]:
            problems.append(f"{name}：导语 {ty['lead_size']}px 未大于正文 {grid['body']}px，导语失去入口作用")
        if not ty["heading_size"] > ty["h3_size"]:
            problems.append(f"{name}：H2 {ty['heading_size']}px 未大于 H3 {ty['h3_size']}px")
        if not grid["body"] >= grid["caption"]:
            problems.append(f"{name}：正文 {grid['body']}px 小于图注 {grid['caption']}px")
        if not 15 <= grid["body"] <= 17:
            problems.append(f"{name}：正文字号 {grid['body']}px 超出 15–17px 的手机阅读区间")
        if not 12 <= grid["caption"] <= 15:
            problems.append(f"{name}：图注字号 {grid['caption']}px 超出 12–15px")
    return problems


_THEME_PROBLEMS = validate_themes(THEMES)
if _THEME_PROBLEMS:
    raise ValueError("主题配置不合格：\n  " + "\n  ".join(_THEME_PROBLEMS))
SANS = "-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei','Noto Sans CJK SC',sans-serif"
SERIF = "'Songti SC','STSong','SimSun','Noto Serif CJK SC',serif"
MONO = "'SF Mono',Menlo,Consolas,monospace"
CJK = "\u4e00-\u9fff\u3400-\u4dbf"
# 默认阅读字号，非必须遵守的审美配额
MICRO, SMALL, BODY, DISPLAY, TITLE = 13, 14, 16, 20, 24

# 正文视觉职责（封面单独由 frontmatter 承担）。说不出职责 → 删。
ROLES = {"锚点", "解释", "证据", "对比", "结构", "场景", "隐喻", "停顿", "数据", "资料", "实拍",
         "anchor", "explain", "evidence", "compare", "structure", "context", "metaphor", "rhythm",
         "data", "archival", "photo"}
# 资料图（馆藏扫描、档案、截图）与实拍照片：读者会默认它们「拍到了现场」，
# 所以图注必须写明来源与授权状态，而不只是写内容。
PROVENANCE_ROLES = {"资料", "实拍", "archival", "photo"}
FACT = {"解释", "证据", "对比", "结构", "数据",
        "explain", "evidence", "compare", "structure", "data"}       # 说明用正文色、字号大一级
TODO = re.compile(r"(?i)^(todo|待补)")
COVER_RATIO = 2.35                    # 封面目标比例（微信首图）
COVER_BAND = (1.6, 3.0)               # 可接受区间；超出说明这不是一张封面
COVER_MIN_W = 900                     # 下方会被裁，再窄就糊

BR = '<span leaf=""><br></span>'
INLINE = re.compile(r"`([^`]+)`|==(.+?)==|\*\*(.+?)\*\*|<u>(.+?)</u>|~~(.+?)~~|\[([^\]]+)\]\(([^)\s]+)\)")
# 标题自带序号（一、/（二）/第三章/1. /01 …）：章标是构成不是内容，不叠加第二套编号。
ORDINAL = re.compile(r"^(?:[一二三四五六七八九十]{1,3}[、．.．]|[（(][一二三四五六七八九十0-9]{1,3}[）)]"
                     r"|第[一二三四五六七八九十0-9]{1,3}[章节回讲部篇期段条则辑卷问日]"
                     r"|[0-9]{1,2}[、．.]\s|[0-9]{1,2}\s"
                     r"|[①-⑳⑴-⒇]|[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩⅪⅫ]+[、．.\s]?)")


def typo(s):
    """仅归一中文语境标点；不改引用引号、数字、代码或资源地址。"""
    def prose(text):
        return re.sub(f"(?<=[{CJK}])([,;:!?])|(?<=[A-Za-z0-9])([,;!?])\\s*(?=[{CJK}])",
                      lambda m: dict(zip(",;:!?", "，；：！？"))[m[1] or m[2]], text)
    return "".join(part if i % 2 else prose(part) for i, part in enumerate(
        re.split(r"(`[^`]+`|\[[^\]]+\]\([^)\s]+\)|https?://[^\s<>\u3000，；。！？）\"]+)", s)))


def unique_style(style):
    """Merge renderer-owned CSS declarations; later values replace earlier ones."""
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
            kind = "lead" if not any(b[0] in ("p", "h2", "img") for b in blocks) else "quote"
            blocks.append((kind, ("".join(x for x in q if x), src)))
        elif re.match(r"!\[[^\]]*\]\([^)]*\)\s*$", s):
            flush()
            mm = re.match(r'!\[([^\]]*)\]\(\s*([^)\s]*)\s*(?:"([^"]*)")?\s*\)', s)
            if not mm:
                raise ValueError("图片语法错误：使用 ![说明](路径 \"职责\")，带空格路径请重命名")
            blocks.append(("img", mm.groups()))
        elif re.match(r"([-*]|\d+[.、])\s", s):
            if ln != ln.lstrip():
                raise ValueError(f"第 {i + 1} 行：嵌套或缩进列表不支持，请显式展平并核对层级")
            flush()
            ordered, items = bool(re.match(r"\d", s)), []
            while i < len(lines) and re.match(r"\s*([-*]|\d+[.、])\s", lines[i]):
                raw = lines[i]
                marker = re.match(r"\s*([-*]|\d+[.、])\s+", raw).group(1)
                if raw != raw.lstrip():
                    raise ValueError(f"第 {i + 1} 行：嵌套或缩进列表不支持，请显式展平并核对层级")
                if bool(re.match(r"\d", marker)) != ordered:
                    raise ValueError(f"第 {i + 1} 行：混合列表类型，请用空行分开")
                if ordered and int(marker[:-1]) != len(items) + 1:
                    raise ValueError(f"第 {i + 1} 行：有序列表必须从 1 连续编号，避免改变原顺序")
                items.append(re.sub(r"^\s*([-*]|\d+[.、])\s+", "", raw))
                i += 1
            i -= 1
            blocks.append(("list", (ordered, items)))
        elif s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip().replace(r"\|", "|") for c in re.split(r"(?<!\\)\|", lines[i].strip().strip("|"))]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            i -= 1
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
    """读文件头取 (宽, 高)：PNG / JPEG / GIF / WebP。取不到返回 None（不误报）。"""
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
            if head[:2] == b"\xff\xd8":                       # JPEG：扫 SOF 段
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


class R:
    """六人格共用一个渲染器，差异来自配置轴，而不是散落的 if 分支。

    网格（grid）、字号（type）、组件语言（lead/heading/...）都从 themes.json 读取；
    这里只负责把「关系」翻译成微信允许的内联样式。
    """

    def __init__(self, t, density):
        self.t = t
        self.type = t["type"]
        self.grid = t.get("grid", {})
        self.k = {"dense": 0.8, "airy": 1.2}.get(density, 1.0)
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
        atoms = re.compile(r"(?:(?:19|20)\d{2}年)?(?:\d{1,2}月)?(?:\d{1,2}日)?|[+\-−]?\d[\d.,，]*(?:%|％|个百分点|亿元|万元|亿美元|美元|小时|分钟|万人|元|倍|年|天|人|家|件|台|公里|千米|米)?")
        out, pos = [], 0
        for m in atoms.finditer(s):
            token = m.group()
            if not re.search(r"\d", token) or text_px(token, self.body) > 240:
                continue
            # URL/资源地址不是 prose 数值；整段保护，避免把 query 数字包成不可断行原子。
            if re.search(r"https?://[^\s<>]*$", s[:m.start()]):
                continue
            if m.start() > pos:
                out.append(self.leaf(s[pos:m.start()]))
            out.append(f'<span leaf="" style="white-space:nowrap;">{H.escape(token)}</span>')
            pos = m.end()
        out.append(self.leaf(s[pos:]))
        return "".join(out)

    def inline(self, s, normalize=True):
        t, out, pos = self.t, [], 0
        s = typo(s) if normalize else s
        for m in INLINE.finditer(s):
            if m.start() > pos:
                out.append(self.prose_leaf(s[pos:m.start()]))
            code, mark, bold, u, strike, ltext, url = m.groups()
            if code:
                out.append(f'<span style="font-family:{MONO};font-size:{SMALL}px;background:{t["field"]};'
                           f'padding:1px 5px;border-radius:3px;color:{t["text"]};">{self.leaf(code)}</span>')
            elif mark or u:
                # 强调用字重与内描线，不用第二套颜色；颜色差在小屏与反色块里会消失。
                out.append(f'<span style="border-bottom:1px solid {t["accent"]};padding-bottom:1px;">'
                           f'{self.leaf(mark or u)}</span>')
            elif bold:
                out.append(f'<strong style="font-weight:600;color:inherit;">{self.leaf(bold)}</strong>')
            elif strike:
                out.append(f'<span style="text-decoration:line-through;color:{t["muted"]};">{self.leaf(strike)}</span>')
            else:
                # Preserve semantic links; client clickability is a separate acceptance gate.
                if not re.match(r"^https?://[^\s]+$", url, re.I):
                    raise ValueError(f"链接协议不支持：{url}；仅允许 http/https")
                out.append(f'<a href="{H.escape(url, quote=True)}" style="color:{t["text"]};text-decoration:underline;">{self.leaf(ltext)}</a>')
            pos = m.end()
        if pos < len(s):
            out.append(self.prose_leaf(s[pos:]))
        return "".join(out)

    def p(self, inner, size=None, color=None, extra=""):
        size = self.body if size is None else size
        lh = "" if "line-height" in extra else f'line-height:{self.t["leading"] if size == self.body else 1.75};'
        ls = "" if "letter-spacing" in extra else "letter-spacing:normal;"
        style = unique_style(f'margin:0;font-size:{size:g}px;{lh}color:{color or self.t["text"]};{ls}{extra}')
        return f'<p style="{style}">{inner}</p>'

    def micro(self, s, color=None, extra="", size=None):
        return self.p(self.leaf(s), size or self.cap, color or self.t["muted"], f"font-weight:500;{extra}")

    def rule(self, w=24, h=1, color=None, center=True, below=0):
        pos = f"margin:0 auto {below}px;" if center else "flex-shrink:0;"
        return f'<section style="width:{w}px;height:{h}px;background:{color or self.t["line"]};{pos}">{BR}</section>'

    def seal(self, glyph, size=24, color=None):
        return (f'<span style="display:inline-block;width:{size}px;height:{size}px;line-height:{size - 2}px;'
                f'border:1px solid {self.t["muted"]};border-radius:50%;text-align:center;font-size:{MICRO}px;'
                f'font-weight:600;color:{color or self.t["text"]};box-sizing:border-box;">{self.leaf(glyph)}</span>')

    # ---- 章节：六种转场语言 ----
    def h2(self, text, n):
        t, mode = self.t, self.t["heading"]
        numbered = not ORDINAL.match(text.strip())
        title = self.inline(text)
        hs = self.type["heading_size"]
        style = (f"font-weight:{self.type['heading_weight']};line-height:{self.type['heading_leading']};"
                 f"font-family:{self.font};")
        gap = f'margin:{self.g(self.grid["chapter_gap"])}px 0 {self.g(14)}px;'
        if mode == "index" and numbered:
            # 工作纸索引：小号编号与标题同基线，不做装饰线。
            head = (f'<span style="font-size:{SMALL}px;color:{t["muted"]};font-weight:500;'
                    f'font-variant-numeric:tabular-nums;">{self.leaf(f"{n:02d}　")}</span>')
            return (f'<section style="{gap}">' + self.p(head + title, hs, extra=style) + "</section>")
        if mode == "plain":
            # 信笺：无编号，标题下压一条短署名线，作为章节的“结束句”。
            return (f'<section style="{gap}">' + self.p(title, hs, extra=style)
                    + f'<section style="width:28px;height:1px;background:{t["accent"]};margin-top:12px;">{BR}</section>'
                    + "</section>")
        if mode == "seal" and numbered:
            title = self.seal(f"{n:02d}", 24) + "　" + title
        elif mode == "report":
            marker = self.micro(f"{n:02d} /", extra="margin-bottom:7px;font-variant-numeric:tabular-nums;") if numbered else ""
            return (f'<section style="{gap}padding-top:10px;border-top:1px solid {t["text"]};">{marker}'
                    + self.p(title, hs, extra=style) + "</section>")
        elif mode == "atelier":
            # 素作：只留一条发丝线与足够留白；不再每节印同一个英文装饰标签
            # （那既不是内容，也会在三个以上章节里变成机械重复）。
            return (f'<section style="{gap}padding-top:18px;border-top:1px solid {t["line"]};">'
                    + self.p(title, hs, extra=style + "letter-spacing:0.04em;") + "</section>")
        elif mode == "folio":
            marker = (self.p(self.leaf(f"{n:02d}"), 40, t["accent"],
                             f"font-weight:700;line-height:1;font-family:{self.font};"
                             f"margin-bottom:10px;letter-spacing:-0.02em;font-variant-numeric:tabular-nums;")
                      if numbered else "")
            return (f'<section style="{gap}">{marker}'
                    + self.p(title, hs, extra=style) + "</section>")
        return (f'<section style="{gap}">' + self.p(title, hs, extra=style) + "</section>")

    def h3(self, text):
        t, mode = self.t, self.t["h3"]
        size, weight, extra = self.type["h3_size"], 700, f"font-family:{self.font};"
        if mode == "label":
            # 工作纸式小节标签：小一号、加字距、压成弱色，靠位置与字距而不是线来分层。
            size = max(self.cap, size - 2)
            weight = 600
            extra = f"font-family:{self.font};color:{t['sub']};letter-spacing:0.06em;"
        elif mode == "soft":
            weight, extra = 500, f"font-family:{self.font};color:{t['sub']};"
        elif mode == "serif":
            weight = 600
        elif mode == "report":
            extra += f"padding-bottom:6px;border-bottom:1px solid {t['line']};"
        elif mode == "atelier":
            weight = 500
            extra += "letter-spacing:0.04em;"
        elif mode == "folio":
            weight = 700
            extra += f"padding-left:10px;border-left:3px solid {t['accent']};"
        return (f'<section style="margin:{self.g(26)}px 0 {self.g(10)}px;">'
                + self.p(self.inline(text), size, t["text"], f"font-weight:{weight};{extra}") + "</section>")

    def para(self, text):
        indent = self.grid.get("indent", 0)
        extra = "text-align:left;"
        if indent:
            # 段首缩进是「文本流」的人格：段间不再用空行切开，靠缩进与行距分句。
            extra += f"text-indent:{indent:g}em;"
        gap = self.grid["paragraph_gap"]
        return (f'<section style="margin:0 0 {self.g(gap)}px;">'
                + self.p(self.inline(text), extra=extra) + "</section>")

    def _lead_lines(self, s, size):
        """把导语的每一句渲染成一行：中文长句在手机上最容易“读到一半换行”。

        只有标了些句号级句末标点才分行；用块级 span 而不是 <br>，微信清洗后两种都成立。
        """
        parts = [p for p in re.split(r"(?<=[。！？；])", s) if p.strip()]
        if len(parts) < 2:
            return self.inline(s, normalize=False)
        return "".join(
            f'<span style="display:block;">{self.inline(p.strip(), normalize=False)}</span>' for p in parts)

    def _dropcap(self, s):
        """首字下沉：不靠 float，用一个行内大字撑开首行，微信清洗后仍成立。

        输入是原始 Markdown 文本（不是已渲染 HTML），首字之后再走 inline，
        这样加粗/代码不会被二次转义。
        """
        s = s.lstrip()
        # 单笔画汉字（一/二/十）放大后会被读成一条误入的横线或装饰线，不做下沉。
        if not s or s[0] in "「“『（《一二三十壹贰叁拾":
            return self.inline(s, normalize=False)
        return (f'<span style="display:inline-block;font-size:{round(self.body * 1.9)}px;'
                f'line-height:1;font-family:{SERIF};font-weight:600;color:{self.t["accent"]};'
                f'vertical-align:-0.08em;margin-right:2px;">{self.leaf(s[0])}</span>'
                + self.inline(s[1:], normalize=False))

    def quote(self, text, src, weight):
        """导语、引文、主张分权重；引文保留原标点，主题只改变构图关系。"""
        t = self.t
        if weight == "lead":
            inner = self.inline(text, normalize=False)
            lead_size = self.type["lead_size"]
            if len(plain(text)) > 48:
                lead_size = min(lead_size, 22)
            lead_style = f'line-height:{self.type["lead_leading"]};font-weight:{self.type["lead_weight"]};'
            cite = (self.p(self.leaf("—— " + src), self.cap, t["muted"], "margin-top:10px;")
                    if src else "")
            mode = t["lead"]
            if mode == "brief":
                return (f'<section style="margin:{self.g(8)}px 0 {self.g(26)}px;padding-top:14px;'
                        f'border-top:2px solid {t["accent"]};">'
                        + self.p(inner, lead_size, t["text"], lead_style + f"font-family:{self.font};")
                        + cite + "</section>")
            if mode == "letter":
                return (f'<section style="margin:{self.g(4)}px 0 {self.g(30)}px;padding:0 2px;">'
                        f'<section style="width:22px;height:1px;background:{t["accent"]};margin-bottom:12px;">{BR}</section>'
                        + self.p(inner, lead_size, t["text"], lead_style + f"font-family:{self.font};font-weight:500;")
                        + cite + "</section>")
            if mode == "ink":
                return (f'<section style="margin:{self.g(8)}px 0 {self.g(30)}px;padding:16px 0;'
                        f'border-top:1px solid {t["line"]};border-bottom:1px solid {t["line"]};">'
                        + self.p(self._dropcap(text), lead_size, t["text"], lead_style + f"font-family:{SERIF};")
                        + cite + "</section>")
            if mode == "report":
                return (f'<section style="margin:{self.g(8)}px 0 {self.g(22)}px;padding-bottom:14px;'
                        f'border-bottom:1px solid {t["text"]};">'
                        + self.p(inner, lead_size, t["text"], lead_style) + cite + "</section>")
            if mode == "plate":
                return (f'<section style="margin:{self.g(8)}px 0 {self.g(30)}px;padding:18px 16px;'
                        f'background:{t["field"]};">'
                        + self.p(inner, lead_size, t["text"], lead_style + f"font-family:{SERIF};") + cite + "</section>")
            return (f'<section style="margin:{self.g(6)}px 0 {self.g(30)}px;">'
                    f'<section style="width:56px;height:4px;background:{t["accent"]};margin-bottom:16px;">{BR}</section>'
                    + self.p(self._lead_lines(text, lead_size), lead_size, t["text"],
                             lead_style + f"font-family:{self.font};"
                             f"letter-spacing:-0.01em;") + cite + "</section>")
        if weight == "quote":
            cite = (self.p(self.leaf(f"—— {src}"), self.cap, t["muted"], "margin-top:10px;")
                    if src else "")
            mode = t["quote"]
            body = self.inline(text, normalize=False)
            if mode == "voice":
                return (f'<section style="margin:{self.g(28)}px 0;padding:0 4px;">'
                        + self.p(body, self.type["quote_size"], t["text"], "font-weight:500;line-height:1.95;"
                                                     "text-indent:-1em;padding-left:1em;") + cite + "</section>")
            if mode == "serif":
                return (f'<section style="margin:{self.g(28)}px 0;padding:4px 2px 4px 16px;'
                        f'border-left:2px solid {t["accent"]};">'
                        + self.p(body, self.type["quote_size"], t["sub"], f"font-weight:500;line-height:2;font-family:{SERIF};")
                        + cite + "</section>")
            if mode == "report":
                return (f'<section style="margin:{self.g(24)}px 0;padding:12px 0;'
                        f'border-top:1px solid {t["line"]};border-bottom:1px solid {t["line"]};">'
                        + self.p(body, self.type["quote_size"], t["text"], "font-weight:600;line-height:1.8;") + cite + "</section>")
            if mode == "atelier":
                return (f'<section style="margin:{self.g(30)}px 8%;padding:14px 0;'
                        f'border-top:1px solid {t["line"]};">'
                        + self.p(body, self.type["quote_size"], t["sub"], f"font-weight:500;line-height:2;font-family:{SERIF};"
                                                     f"letter-spacing:0.02em;") + cite + "</section>")
            if mode == "folio":
                return (f'<section style="margin:{self.g(30)}px 0;padding-top:14px;'
                        f'border-top:4px solid {t["text"]};">'
                        + self.p(body, self.type["quote_size"], t["text"], f"font-weight:700;line-height:1.6;font-family:{self.font};")
                        + cite + "</section>")
            if mode == "rule":
                return (f'<section style="margin:{self.g(26)}px 0;padding:0 4px 0 14px;'
                        f'border-left:2px solid {t["accent"]};">'
                        + self.p(body, self.type["quote_size"], t["sub"], "font-weight:500;line-height:1.9;") + cite + "</section>")
            raise ValueError(f"引文轴取值未实现：{mode}")
        style, fam = t["peak"], f"font-family:{self.font};"
        if style in ("dark", "compact"):
            inner = self.p(self.inline(text, normalize=False), DISPLAY, t["on_dark"],
                           f"font-weight:600;line-height:{'1.7' if style == 'dark' else '1.55'};{fam}")
            pad = f"{self.g(22)}px 18px" if style == "dark" else "13px 15px"
            return f'<section style="margin:{self.g(34)}px 0;text-align:left;padding:{pad};background:{t["dark"]};">{inner}</section>'
        claim = self.p(self.inline(text, normalize=False), DISPLAY, t["text"],
                       f"font-weight:600;line-height:1.65;{fam}")
        if style == "field":
            return f'<section style="margin:{self.g(34)}px 0;text-align:left;padding:{self.g(20)}px 16px;background:{t["field"]};border-radius:{t["radius"]}px;">{claim}</section>'
        if style == "line":
            return (f'<section style="margin:{self.g(32)}px 0;text-align:left;padding:0 4px 0 14px;'
                    f'border-left:3px solid {t["accent"]};">{claim}</section>')
        if style == "plate":
            return (f'<section style="margin:{self.g(34)}px 0;text-align:left;padding:16px 0;'
                    f'border-top:1px solid {t["line"]};border-bottom:1px solid {t["line"]};">{claim}</section>')
        if style == "rule":
            return (f'<section style="margin:{self.g(34)}px 0;text-align:left;">'
                    f'<section style="width:28px;height:2px;background:{t["accent"]};margin:0 0 14px;">{BR}</section>'
                    f'{claim}</section>')
        raise ValueError(f"重点轴取值未实现：{style}")

    def unknown(self, label, lines):
        """未知项：事实、推断、观点之外的第四类内容，必须与已确认事实在形式上分开。

        虚线框 + 明写标签，是最轻的「边界」表达：不是警告，也不抢正文。
        它同时是机器可核对的信号——audit 见到 unknown 块就不再提示「缺未知项」。
        """
        t = self.t
        head = self.micro(label or "未知 / 待确认", extra="margin-bottom:6px;")
        body = "".join(self.p(self.inline(x), self.body - 1, t["sub"], "line-height:1.85;") for x in lines)
        return (f'<section style="margin:{self.g(24)}px 0;padding:13px 14px;'
                f'border:1px dashed {t["line"]};border-radius:{t["radius"]}px;">{head}{body}</section>')

    def note(self, label, lines, tight=False):
        t = self.t
        head = self.micro(label, extra="margin-bottom:6px;") if label else ""
        # 标签已点明「来源／口径」，正文同词前缀就是同一处说两遍：剥掉前缀，一词一处
        body_lines = []
        for x in lines:
            for word in ("来源", "口径"):
                if word in (label or ""):
                    x = re.sub(rf"^{word}[：:]\s*", "", x)
            body_lines.append(x)
        body = "".join(self.p(self.inline(x), self.cap, t["sub"], "line-height:1.8;") for x in body_lines)
        # tight 只收顶边：来源紧贴上面的证据，下面仍按正常节奏离开。
        return f'<section style="margin:{self.g(10) if tight else self.g(16)}px 0 {self.g(16)}px;">{head}{body}</section>'

    def data(self, lines, below=None):
        """离散数值组。关系不变，六人格通过值/标签次序和基线组织信息。"""
        t = self.t
        items = []
        for line in lines:
            value, _, label = line.replace("|", "｜").partition("｜")
            items.append((value.strip(), label.strip()))
        mode, chunks = t["data"], []
        size = self.type["data_size"]
        avail = MOBILE_TABLE_PX - 2 * self.inset
        per = len(items) if 0 < len(items) <= 3 else 2
        column_room = (avail - 16 * (per - 1)) / per
        wide_value = any(text_px(v, size) + 4 > avail * 0.34 for v, _ in items)
        if mode in ("columns", "specimen") and any(text_px(v, size) + 4 > column_room for v, _ in items):
            mode = "stack"
            for i in range(0, len(items), per):
                cells = "".join(
                    f'<section style="flex:1;min-width:0;padding-top:12px;border-top:1px solid {t["text"]};">'
                    + self.p(self.leaf(value), TITLE, t["text"],
                             f"font-weight:600;line-height:1.3;font-family:{self.font};font-variant-numeric:tabular-nums;")
                    + self.p(self.inline(label), self.cap, t["muted"], "margin-top:6px;") + "</section>"
                    for value, label in items[i:i + per])
                chunks.append(f'<section style="display:flex;gap:16px;margin-top:{16 if i else 0}px;">{cells}</section>')
        elif mode == "stack":
            for value, label in items:
                chunks.append(f'<section style="display:flex;gap:14px;align-items:baseline;padding:13px 0;'
                              f'border-top:1px solid {t["line"]};">'
                              + self.p(self.leaf(value), size, t["accent"],
                                       f"width:34%;flex-shrink:0;font-weight:600;line-height:1.35;font-family:{self.font};font-variant-numeric:tabular-nums;")
                              + self.p(self.inline(label), SMALL, t["sub"], "flex:1;min-width:0;line-height:1.8;") + "</section>")
        elif mode == "ledger":
            for value, label in items:
                chunks.append(f'<section style="display:flex;gap:16px;align-items:baseline;padding:12px 0;'
                              f'border-bottom:1px solid {t["line"]};">'
                              + self.p(self.inline(label), SMALL, t["sub"], "flex:1;min-width:0;")
                              + self.p(self.leaf(value), size, t["text"],
                                       f"flex-shrink:0;font-weight:600;line-height:1.3;font-family:{SERIF};font-variant-numeric:tabular-nums;") + "</section>")
        elif mode == "ticker":
            for value, label in items:
                chunks.append(f'<section style="display:flex;gap:12px;align-items:center;padding:10px 0;'
                              f'border-top:1px solid {t["text"]};">'
                              + self.p(self.leaf(value), size, t["text"],
                                       f"width:38%;flex-shrink:0;font-weight:700;line-height:1.2;font-family:{self.font};font-variant-numeric:tabular-nums;")
                              + self.p(self.inline(label), SMALL, t["sub"], "flex:1;min-width:0;line-height:1.7;") + "</section>")
        elif mode == "specimen":
            per = 2
            for i in range(0, len(items), per):
                cells = "".join(
                    f'<section style="flex:1;min-width:0;padding:16px 10px 14px;'
                    f'border-top:1px solid {t["line"]};border-bottom:1px solid {t["line"]};">'
                    + self.p(self.leaf(value), size, t["text"],
                             f"font-weight:500;line-height:1.3;font-family:{SERIF};font-variant-numeric:tabular-nums;")
                    + self.p(self.inline(label), self.cap, t["muted"], "margin-top:8px;") + "</section>"
                    for value, label in items[i:i + per])
                chunks.append(f'<section style="display:flex;gap:12px;margin-top:{12 if i else 0}px;">{cells}</section>')
        elif mode == "columns":
            # 工作纸式数值栏：等宽分栏，值在上、标签在下，与 specimen 的差别在留白与分隔线。
            per = len(items) if 0 < len(items) <= 3 else 2
            for i in range(0, len(items), per):
                cells = "".join(
                    f'<section style="flex:1;min-width:0;padding-top:12px;border-top:1px solid {t["text"]};">'
                    + self.p(self.leaf(value), size, t["text"],
                             f"font-weight:600;line-height:1.25;font-family:{self.font};font-variant-numeric:tabular-nums;")
                    + self.p(self.inline(label), SMALL, t["sub"], "margin-top:6px;") + "</section>"
                    for value, label in items[i:i + per])
                chunks.append(f'<section style="display:flex;gap:18px;margin-top:{18 if i else 0}px;">{cells}</section>')
        elif mode == "folio":
            for value, label in items:
                chunks.append(f'<section style="display:flex;gap:16px;align-items:flex-end;padding:14px 0;'
                              f'border-top:3px solid {t["text"]};">'
                              + self.p(self.leaf(value), size, t["accent"],
                                       f"width:42%;flex-shrink:0;font-weight:700;line-height:1;font-family:{self.font};font-variant-numeric:tabular-nums;letter-spacing:-0.02em;")
                              + self.p(self.inline(label), SMALL, t["text"], "flex:1;min-width:0;font-weight:600;line-height:1.65;") + "</section>")
        if wide_value:
            chunks = []
            for value, label in items:
                border = f"border-top:{3 if mode == 'folio' else 1}px solid {t['text' if mode in ('ticker', 'folio') else 'line']};"
                chunks.append(f'<section style="padding:12px 0;{border}">'
                    + self.p(self.leaf(value), size, t["accent"] if mode in ("stack", "folio") else t["text"],
                             f"font-weight:{self.type['lead_weight']};line-height:1.35;font-family:{self.font};font-variant-numeric:tabular-nums;white-space:nowrap;")
                    + self.p(self.inline(label), SMALL, t["sub"], "margin-top:6px;line-height:1.7;") + "</section>")
        return (f'<section style="margin:{self.g(36)}px 0 '
                f'{below if below is not None else self.g(36)}px;">{"".join(chunks)}</section>')

    def bars(self, lines, label="", below=None):
        """数量对比图：值｜标签。数值同时以文字给出——即使长度表达失效，信息也不丢。"""
        t, rows, items = self.t, [], []
        for ln in lines:
            val, _, lab = ln.replace("|", "｜").partition("｜")
            items.append((val.strip(), lab.strip()))
        nums = [float(v) if re.fullmatch(r"\d+(\.\d+)?", v) else 0 for v, _ in items]
        nums = [v if math.isfinite(v) else 0 for v in nums]
        mx = max(nums, default=0)
        if label:
            rows.append(self.p(self.inline(label), SMALL, t["sub"]))
        rows.append(self.p(self.leaf("零起点 · 最长条代表本组最大值"), self.cap, t["muted"], "margin-top:4px;"))
        for (val, lab), num in zip(items, nums):
            w = f"{num / mx * 100:.6g}" if mx else "0"
            rows.append(
                f'<section style="display:flex;align-items:flex-end;gap:10px;margin-top:{self.g(16)}px;">'
                + self.p(self.inline(lab), SMALL, t["sub"], "flex:1;min-width:0;")
                + self.p(self.leaf(val), self.body, t["text"], f"font-weight:600;font-family:{self.font};"
                                                               f"font-variant-numeric:tabular-nums;white-space:nowrap;flex-shrink:0;")
                + "</section>"
                + f'<section style="height:5px;background:{t["line"]};margin-top:6px;">'
                + f'<section style="width:{w}%;height:5px;background:{t["accent"]};">{BR}</section></section>')
        return f'<section style="margin:{self.g(32)}px 0 {below if below is not None else self.g(32)}px;">{"".join(rows)}</section>'

    def table(self, rows, below=None):
        """语义表格；人格改变表头、基线和首列权重，不靠缩小字号塞列。

        320px 下确实放不下时改为“记录卡”堆叠：标签与数值仍成对出现，
        信息不丢、字号不缩。删列是编辑决定，渲染器只保证不靠牺牲可读性硬塞。
        微信会剥离媒体查询，所以判定只按最窄的 320px 做一次，六宽度共用同一形态。
        """
        t, out, mode = self.t, [], self.t["table"]
        if not rows or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError("表格行列数不一致，不能对齐数据")
        hpad = table_pad(t) // 2                     # 单侧内距，与下面 pad 字符串同源
        table_avail = MOBILE_TABLE_PX - 2 * self.inset
        if not table_fits(rows, self.inset, 2 * hpad):
            return self.table_stack(rows, below)
        widths = col_widths(rows, table_avail, 2 * hpad)
        # 表框只由三轴决定，其余轴（open/warm/report）的差异在单元格内距与表头底色里。
        # 取值合法性已在载入时由 validate_themes 校验，这里不再用 if/else 兜底。
        table_extra = {
            "ink": f"border-top:2px solid {t['text']};border-bottom:1px solid {t['text']};",
            "atelier": f"border-top:1px solid {t['text']};border-bottom:1px solid {t['text']};",
            "feature": f"border-top:4px solid {t['text']};",
        }.get(mode, "")
        for i, cells in enumerate(rows):
            tag = "th" if i == 0 else "td"
            rendered = []
            for j, cell in enumerate(cells):
                pad = "10px 6px"
                bg, color = "", t["sub"] if i == 0 else t["text"]
                border = t["muted"] if i == 0 else t["line"]
                weight = 600 if i == 0 or (j == 0 and mode in ("report", "feature")) else 400
                family = f"font-family:{self.font};" if i == 0 and mode in ("ink", "atelier") else ""
                if mode == "warm":
                    pad = "12px 7px"
                    bg = f"background:{t['field']};" if i == 0 else ""
                    border = t["accent"] if i == 0 else t["line"]
                elif mode == "report":
                    pad = "9px 6px"
                    bg = f"background:{t['field']};" if i == 0 else ""
                    border = t["text"] if i == 0 else t["line"]
                    color = t["text"]
                elif mode == "atelier":
                    pad = "13px 7px"
                elif mode == "feature" and i == 0:
                    bg, color, border = f"background:{t['dark']};", t["on_dark"], t["dark"]
                extra = "line-height:1.75;" + family
                # 数字只在分配宽度真的够时禁止折行：现在每条分支都先算过可用像素，
                # 所以既不会把 8 位数字拆成两行，也不会让 nowrap 撑破单元格。
                if NUMERIC.fullmatch(cell):
                    extra += "font-variant-numeric:tabular-nums;"
                    room = widths[j] / 100 * table_avail - 2 * (7 if mode in ("warm", "atelier") else 6)
                    if text_px(cell) <= room + 1:
                        extra += "white-space:nowrap;"
                rendered.append(
                    f'<{tag} style="width:{widths[j]:.6g}%;padding:{pad};vertical-align:top;'
                    f'overflow-wrap:anywhere;word-break:normal;text-align:left;'
                    f'font-weight:{weight};{bg}">'
                    + self.p(self.inline(cell), SMALL, color, extra) + f"</{tag}>")
            # 行线画在 tr 上：一 px 的线只出现一次，不会因为单元格内距变成双线。
            row_border = "" if i == len(rows) - 1 and mode in ("ink", "atelier", "feature", "report", "warm") else (
                f"border-bottom:1px solid {border if i == 0 else t['line']};")
            row_attr = f' style="{row_border}"' if row_border else ""
            out.append(f'<tr{row_attr}>' + "".join(rendered) + "</tr>")
        return (f'<table style="width:100%;table-layout:fixed;border-collapse:collapse;{table_extra}'
                f'margin:{self.g(24)}px 0 {below if below is not None else self.g(24)}px;">'
                + "".join(out) + "</table>")

    def table_stack(self, rows, below=None):
        """窄屏记录卡：一行一条记录，字段名与值成对，顺序与表格一致。"""
        t, head = self.t, rows[0]
        mode = t["table"]
        record_label = {"open": "条目", "warm": "第", "ink": "项", "report": "记录", "atelier": "规格", "feature": "焦点"}.get(mode, "记录")
        blocks = []
        for n, row in enumerate(rows[1:], 1):
            cells = []
            for label, value in zip(head, row):
                cells.append(
                    f'<section style="display:flex;gap:12px;padding:{8 if mode == 'atelier' else 5}px 0;">'
                    + self.p(self.leaf(label), self.cap, t["muted"], "width:30%;flex-shrink:0;min-width:0;line-height:1.7;")
                    + self.p(self.inline(value), SMALL, t["text"],
                             "flex:1;min-width:0;line-height:1.7;font-variant-numeric:tabular-nums;") + "</section>")
            blocks.append(f'<section style="padding:12px 0 10px;border-top:1px solid {t["line"]};">'
                          + self.p(self.leaf(f"{record_label} {n:02d}" + (" 则" if mode == "warm" else "")), self.cap, t["accent"] if mode == "feature" else t["muted"],
                                  f"margin-bottom:6px;font-weight:{700 if mode == 'feature' else 500};font-family:{self.font};") + "".join(cells) + "</section>")
        return (f'<section style="margin:{self.g(24)}px 0 {below if below is not None else self.g(24)}px;">'
                + "".join(blocks) + "</section>")

    def lst(self, ordered, items):
        t, out, mode = self.t, [], self.t["list"]
        chinese = "一二三四五六七八九十"
        for n, item in enumerate(items, 1):
            if ordered:
                marker = {
                    "index": f"{n:02d}",
                    "dash": f"{n}.",
                    "chinese": (chinese[n - 1] + "、") if n <= len(chinese) else f"{n}、",
                    "report": f"{n:02d}",
                    "atelier": (chinese[n - 1] + "　") if n <= len(chinese) else f"{n}　",
                    "folio": f"{n:02d}/",
                }[mode]
            else:
                marker = {"index": "·", "dash": "—", "chinese": "〇", "report": "—",
                          "atelier": "◇", "folio": "▪"}[mode]
            marker_color = t["accent"] if mode in ("dash", "folio") else t["muted"]
            marker_family = SERIF if mode in ("chinese", "atelier") else self.font
            marker_html = self.p(self.leaf(marker), SMALL if ordered else self.body, marker_color,
                                 f"font-weight:{600 if mode in ('report', 'folio') else 500};font-family:{marker_family};")
            width = 34 if mode in ("chinese", "atelier", "folio") else 28 if ordered else 20
            rule = f"border-top:1px solid {t['line']};padding-top:10px;" if mode == "report" else ""
            out.append(f'<section style="display:flex;margin-bottom:{self.g(10)}px;{rule}">'
                       f'<section style="width:{width}px;flex-shrink:0;padding-top:2px;">{marker_html}</section>'
                       f'<section style="flex:1;min-width:0;">{self.p(self.inline(item))}</section></section>')
        return f'<section style="margin:{self.g(8)}px 0 {self.g(22)}px;">{"".join(out)}</section>'

    def code(self, lang, body):
        t = self.t
        rows = "".join(
            f'<p style="margin:0;font-family:{MONO};font-size:{SMALL}px;line-height:1.7;white-space:pre-wrap;overflow-wrap:anywhere;word-break:normal;tab-size:4;color:{t["text"]};">'
            + (self.leaf(ln) if ln.strip() else BR)
            + "</p>" for ln in body)
        label = self.micro(lang.upper(), extra=f"margin-bottom:10px;font-family:{MONO};") if lang else ""
        return (f'<section style="margin:{self.g(24)}px 0;padding:16px 18px;background:{t["field"]};'
                f'border-radius:{t["radius"]}px;">{label}{rows}</section>')

    def img(self, alt, src, role, below=None, above=None):
        """图片版式：人格给默认处理，表达方式覆盖它；只排列，不裁切、不合成、不推测内容。

        每条边只声明一次：人格的底线与 hero 的强调线不会叠加成双线。
        """
        t = self.t
        role0 = next(iter((role or "").split()), "")   # 无职责的图不该崩：Gate 2 会判「必须改」
        mt = self.g(26) if above is None else above
        mb = below if below is not None else mt
        if not src or TODO.match(src):
            return (f'<section style="margin:{mt}px 0 {mb}px;padding:36px 16px;border:1px dashed {t["muted"]};'
                    f'text-align:center;">{self.micro("待补素材")}'
                    + self.p(self.leaf(alt or "此处插入图片"), SMALL, t["sub"], "margin-top:8px;")
                    + (self.p(self.leaf(f"职责：{role}"), self.cap, t["muted"], "margin-top:4px;") if role else "")
                    + "</section>")
        parts = (role or "").split()
        mode = parts[1].lower() if len(parts) > 1 else ""
        treat = t.get("image", "flush")
        img_extra, outer, pad, rule = "", [], [], None
        if treat == "soft":
            img_extra = f"border-radius:{t['radius']}px;"
            outer = ["margin-left:2%", "margin-right:2%"]
        elif treat == "inkline":
            pad, rule = ["10px 0"], (1, t["line"])
            outer.append(f"border-top:1px solid {t['text']}")
        elif treat == "report":
            pad, rule = ["8px 0 10px"], (2, t["text"])
            outer.append(f"border-top:2px solid {t['text']}")
        elif treat == "mat":
            pad = ["14px 14px 12px"]
            outer.append(f"background:{t['field']}")
        elif treat == "folio":
            pad, rule = ["0 0 10px"], (4, t["text"])
        if mode == "hero":
            img_extra += "width:100%;"
            pad, rule = ["0 0 14px"], (2, t["accent"])
        elif mode == "full-width":
            img_extra += "width:100%;"
        elif mode == "inset":
            outer += ["margin-left:10%", "margin-right:10%"]
        elif mode == "plate":
            pad = ["12px"]
            outer.append(f"background:{t['field']}")
        elif mode == "detail":
            outer += ["margin-left:5%", "margin-right:5%"]
        elif mode in ("sequence", "comparison"):
            pad = ["8px 0 0"]
        elif mode in ("evidence", "explainer", "data"):
            pad = ["0 0 0 12px"]
            outer.append(f"border-left:2px solid {t['accent']}")
        wrap = unique_style(";".join(outer) + ";") if outer else ""
        if pad:
            wrap += f"padding:{' '.join(pad)};"
        if rule:
            wrap += f"border-bottom:{rule[0]}px solid {rule[1]};"
        ai = bool(set(x.lower() for x in parts[2:]) & {"ai", "generated"})
        cap = ("AI 生成示意 · " if ai and "AI" not in (alt or "") else "") + ("GIF · " if src.lower().endswith(".gif") else "") + (alt or "")
        cap_size = SMALL if role0 in FACT else self.cap
        cap_color = t["sub"] if role0 in FACT else t["muted"]
        cap_extra = "margin-top:9px;"
        if treat in ("report", "folio"):
            cap_extra += "font-weight:600;letter-spacing:0.01em;"
        elif treat in ("inkline", "mat"):
            cap_extra += f"font-family:{self.font};letter-spacing:0.04em;"
        elif treat == "soft":
            cap_extra += "padding:0 2px;"
        return (f'<section style="margin:{mt}px 0 {mb}px;{wrap}">'
                f'<img src="{H.escape(src)}" alt="{H.escape(alt or "")}" style="max-width:100%;height:auto;display:block;margin:0 auto;{img_extra}" />'
                + (self.p(self.leaf(typo(cap)), cap_size, cap_color, cap_extra) if cap else "")
                + "</section>")

    def hr(self):
        t, kind = self.t, self.t["divider"]
        if kind == "seal":
            inner = self.seal("·", 20, t["muted"])
        elif kind == "short-rule":
            inner = self.rule(36, 2, t["accent"])
        elif kind == "pause":
            inner = f'<section style="height:1px;overflow:hidden;">{BR}</section>'
        elif kind == "hairline":
            inner = f'<section style="width:100%;height:1px;background:{t["line"]};margin:0;">{BR}</section>'
        elif kind == "double":
            inner = (f'<section style="width:48px;height:1px;background:{t["text"]};margin:0 auto 5px;">{BR}</section>'
                     f'<section style="width:24px;height:1px;background:{t["line"]};margin:0 auto;">{BR}</section>')
        elif kind == "slash":
            inner = self.p(self.leaf("／"), DISPLAY, t["accent"], "font-weight:700;line-height:1;")
        else:
            raise ValueError(f"分隔轴取值未实现：{kind}")
        return f'<section style="margin:{self.g(44)}px 0;text-align:center;">{inner}</section>'

    def signature(self, meta):
        t, out = self.t, []
        if meta.get("cta"):
            out.append(self.p(self.inline(meta["cta"]), SMALL, t["sub"]))
        if meta.get("bio"):
            out.append(self.p(self.leaf(typo(meta["bio"])), self.cap, t["muted"], "margin-top:12px;"))
        return (f'<section style="margin-top:{self.g(34)}px;padding-top:18px;border-top:1px solid {t["line"]};">'
                + "".join(out) + "</section>") if out else ""

    def toc(self, heads):
        t, mode = self.t, self.t["heading"]
        def marker(n, heading):
            if ORDINAL.match(heading.strip()) or mode in ("plain", "atelier"):
                return ""
            return {"index": f"{n:02d}　", "seal": f"{n:02d} · ",
                    "report": f"{n:02d} / ", "folio": f"{n:02d} — "}.get(mode, "")
        rows = "".join(
            self.p(self.leaf(marker(n, h) + plain(h)), SMALL, t["text"],
                   f"line-height:{'1.9' if mode == 'report' else '2.1'};font-family:{self.font};"
                   + ("font-weight:600;" if mode == "folio" else ""))
            for n, h in enumerate(heads, 1))
        top = t["text"] if mode in ("report", "folio") else t["line"]
        return (f'<section style="margin:0 0 {self.g(38)}px;padding:16px 0;border-top:1px solid {top};'
                f'border-bottom:1px solid {t["line"]};">{self.micro(t["toc_label"], extra="margin-bottom:10px;")}{rows}</section>')


def table_fits(rows, inset=0, pad=12):
    """320px 视口下，所有“不可拆”单元格的最小宽度能否同时兑现。

    可用宽度是视口减正文内边距、再减人格自己的左右留白（inset）：窄版面的人格
    更容易放不下，不能按同一套宽度模型判断。
    """
    avail = MOBILE_TABLE_PX - 2 * inset
    if not rows or not rows[0]:
        return True
    n = len(rows[0])
    floor = [0.0] * n
    for row in rows:
        for j, cell in enumerate(row):
            text = re.sub(r"[`*=~]", "", str(cell)).strip()
            if NUMERIC.fullmatch(text) or (len(text) <= 4 and not re.search(r"\s", text)):
                floor[j] = max(floor[j], col_floor(text, pad))
    return sum(px / avail * 100 for px in floor) < 100


NUMERIC = re.compile(
    r"(?:约|近|超过|超|不足|少于|多于|不到)?"
    r"[+\-−]?[\d.,，]+(?:\s*[–—-]\s*[\d.,，]+)?\s*"
    r"(?:个百分点|小时|分钟|美元|亿元|万元|%|％|元|万|亿|年|天|人|家|件|倍)?"
)
MOBILE_TABLE_PX = 288  # 320px 视口减正文左右各 16px


def text_px(s, size=14):
    """14px 表格字下的单行文字宽：ASCII≈0.556em、CJK≈1em、空格≈0.28em。

    常数来自 Chromium 实测（Noto Sans CJK：数字 7.78px、汉字 14px、字号 14px）。
    早期版本按 0.5em 估算并统一加 20px 内距，把「其实放得下」的四列数值表误判成记录卡。
    """
    return sum(0.28 if ch == " " else 0.556 if ord(ch) < 128 else 1.0 for ch in s) * size


def cell_min_px(s, pad=12):
    """单行单元格所需宽度：文字宽 + 该人格表格的左右内距（默认 2×6px）。"""
    return text_px(s) + pad


# 列宽下限比量到的文字宽再多 4px：Chromium 在 table-layout:fixed 下会把小数百分比
# 向下取整，正好卡在文字宽度的列会出现「一季 / 度」这种孤字断行。
TABLE_SLACK = 2


def col_floor(s, pad=12):
    return cell_min_px(s, pad) + TABLE_SLACK


def table_pad(t):
    """表格左右内距：warm/atelier 为 2×7px，其余 2×6px（与 table() 的 padding 同源）。"""
    return 14 if t.get("table") in ("warm", "atelier") else 12


def col_widths(rows, avail=MOBILE_TABLE_PX, pad=12):
    """按内容分配列宽，并先兑现 320px 下的不可拆宽度。

    数值/单位必须同线；四字以内的短表头也不该折成“三字＋孤字”。先为这些单元格保留
    最小像素份额，再把余量给长文本列。若最小份额总和已超过 100%，返回归一化结果，
    compose_gate 会把放不下的数值列明确拦下，而不是缩字号硬塞。
    """
    if not rows or not rows[0]:
        return []
    n = len(rows[0])
    weights, floor_px = [], [0.0] * n
    for j in range(n):
        best = 1.0
        for i, row in enumerate(rows):
            if j >= len(row):
                continue
            text = re.sub(r"[`*=~]", "", str(row[j])).strip()
            w = sum(0.5 if ord(ch) < 128 else 1.0 for ch in text)
            best = max(best, min(w, 12.0))
            if NUMERIC.fullmatch(text):
                floor_px[j] = max(floor_px[j], col_floor(text, pad))
            # 短标签（≤4 字、无空格）在任何一行都要求不折行：表头的「观察对象」和
            # 正文的「一季度」是同一种断行风险，只保护表头会把 3 字标签折成「一季 / 度」。
            if 0 < len(text) <= 4 and not re.search(r"\s", text):
                floor_px[j] = max(floor_px[j], col_floor(text, pad))
        weights.append(max(best, 3.0))

    floors = [px / avail * 100 for px in floor_px]
    floor_total = sum(floors)
    if floor_total >= 100:
        return [f / floor_total * 100 for f in floors]

    # 已由 floor 兑现的内容不再争抢余量；长文本列获得剩余空间并自然换行。
    residual = [max(0.0, w - px / 14) for w, px in zip(weights, floor_px)]
    residual_total = sum(residual)
    if not residual_total:
        residual, residual_total = weights, sum(weights)
    remain = 100 - floor_total
    return [f + remain * r / residual_total for f, r in zip(floors, residual)]


def api_title(t):
    """兼容旧源的 |：转为原生标题全角分隔符，不控制断行。"""
    return t.replace("|", "｜").strip()


def auto_digest(meta, blocks, limit=120):
    """摘要兜底：lead > deck > 首段。摘要上限120字（官方文档，见 references/publish.md）。
    不能让微信自己抓正文前 54 字——抓到的开头不稳定（副题等），不是摘要。"""
    src = next((b[0] for k, b in blocks if k == "lead"), "") \
        or meta.get("deck", "") \
        or next((b for k, b in blocks if k == "p"), "")
    src = plain(src)        # 与目录/度量共用一套行内标记剥离，不再维护第二份正则
    if len(src) <= limit:
        return src
    cut = src[:limit]
    end = max(cut.rfind(ch) for ch in "。！？")          # 优先在句末收口
    if end >= 0:
        return cut[:end + 1]
    end = max(cut.rfind(ch) for ch in "，；、：")          # 其次在停顿处收口并标省略
    return (cut[:end] + "…") if end > 0 else cut + "…"


def resolve(src, base):
    return local_path(src, base)


def compose_gate(meta, blocks, base=".", key=None):
    """Gate 2：可确定的结构与资产检查。审美判断留给 Gate 3。"""
    must, should = [], []
    kinds = [b[0] for b in blocks]
    imgs = [(i, b[1]) for i, b in enumerate(blocks) if b[0] == "img"]
    for idx, (alt, src, role) in imgs:
        tokens0 = (role or "").split()
        if len(tokens0) > 1 and tokens0[1].lower() == "comparison":
            def is_comparison(j):
                if not 0 <= j < len(blocks) or blocks[j][0] != "img":
                    return False
                parts = (blocks[j][1][2] or "").split()
                return len(parts) > 1 and parts[1].lower() == "comparison"
            if not is_comparison(idx - 1):
                end = idx
                while is_comparison(end):
                    end += 1
                if end - idx != 2:
                    must.append("comparison 必须恰好两张相邻图片；多组之间用文字分隔")
        role = (role or "").strip()
        role0 = next(iter(role.split()), "")
        if not role0:
            must.append("图片没有声明职责")
        elif role0 not in ROLES:
            must.append(f"图片职责未识别：{role0}")
        if len(role.split()) > 1 and role.split()[1].lower() in ("sequence", "comparison"):
            mode = role.split()[1].lower()
            neighbors = [blocks[j][1] for j in (idx - 1, idx + 1)
                         if 0 <= j < len(blocks) and blocks[j][0] == "img"]
            if not any(mode in [x.lower() for x in (b[2] or "").split()[1:]] for b in neighbors):
                must.append(f"图片 {src}：{mode} 需要相邻同组图片；单图请改表达方式")
            if not alt:
                must.append(f"图片 {src}：{mode} 必须在图注写明顺序或比较对象与口径")
        tokens = role.split()
        if len(tokens) > 1 and tokens[1].lower() not in {"hero", "full-width", "inset", "plate", "sequence", "comparison", "detail", "evidence", "editorial", "explainer", "data"}:
            should.append(f"图片表达方式未识别：{tokens[1]}；按主题默认处理")
        unknown_mods = set(x.lower() for x in tokens[2:]) - {"ai", "generated", "parallel"}
        if unknown_mods:
            must.append(f"图片修饰词未识别：{'、'.join(sorted(unknown_mods))}")
        if "parallel" in tokens[2:] and (len(tokens) < 2 or tokens[1] != "comparison"):
            must.append("parallel 只用于 comparison；默认纵向同宽对照")
        if role0 in FACT and not (alt or "").strip():
            must.append("证据类图必须写清出处 / 口径 / 时间；解释图也需说明")
        if not src or TODO.match(src):
            continue
        # 说明/证据类图片必须紧邻它的解释对象：孤零零一张图不承担信息职责。
        if role0 in FACT and not TODO.match(src or ""):
            neighbours = [blocks[j] for j in (idx - 1, idx + 1) if 0 <= j < len(blocks)]
            explained = any(k in ("p", "note", "quote", "table", "data", "bars") and block_text(k, v).strip()
                            for k, v in neighbours)
            if not explained:
                should.append(f"图片 {src}（{role0}）上下都是图片或标题：说明/证据类图片需要紧邻它的解释文字")
        # 资料图 / 实拍：图注须交代来源与授权，避免读者把扫描件当成现场照片。
        if role0 in PROVENANCE_ROLES:
            # 出处可以写在图注（alt），也可以写在紧邻的来源行；两处都认，避免逼作者改语序。
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
        p = resolve(src, base)
        if not os.path.isfile(p):
            must.append(f"图片不存在：{src}（本地化后再交付，或写成 todo）")
            continue
        wh, kb = img_size(p), os.path.getsize(p) // 1024
        if not wh or not all(wh):
            must.append(f"图片不是可识别格式：{src}")
        if wh and all(wh):
            w, h = wh
            name = os.path.basename(src)
            if w < 600:
                should.append(f"{name} 分辨率过低，核对显示宽度与细节（{w}×{h}）")
        if kb > 1024:
            should.append(f"{os.path.basename(src)} 体积 {kb}KB：压到 1MB 以内再发布")
    cover = (meta.get("cover") or "").strip()
    if not cover:
        should.append(f"没有封面：公众号需要一张 {COVER_RATIO}:1 封面（方向见 references/direction.md「封面工艺」）")
    elif not TODO.match(cover):
        p = resolve(cover, base)
        if not os.path.isfile(p):
            must.append(f"封面文件不存在：{cover}")
        else:
            wh = img_size(p)
            if not wh or not all(wh):
                must.append("封面不是可识别图片")
            if wh and all(wh):
                w, h = wh
                ratio = w / h
                if w < COVER_MIN_W:
                    should.append(f"封面 {w}×{h}：复核缩略清晰度，宽度至少 {COVER_MIN_W}px")
                if not COVER_BAND[0] <= ratio <= COVER_BAND[1]:
                    should.append(f"封面 {w}×{h}（{ratio:.2f}:1）：微信会裁成 {COVER_RATIO}:1，确认主体在中央安全区，"
                                  f"不要靠烧字补意思")
    for i, (k, b) in enumerate(blocks):
        if k not in ("bars", "data"):
            continue
        note = blocks[i + 1][1] if i + 1 < len(blocks) and blocks[i + 1][0] == "note" else ("", [])
        source = " ".join(note[1])
        # 来源短写到可核对为止：主体＋日期即可，或一行地址，或明确假设/演示（机器不核真）
        if not re.search(r"https?://\S+|\d{4}\s*(?:年|[-–/]\d{1,2}|\))|假设|演示|非统计", source):
            must.append(f"{k} 缺少紧邻来源 note：写清主体与日期（或一行地址），或明确假设/演示（机器不核真）")
        if k == "data":
            for line in b[1]:
                val, _, lab = line.replace("|", "｜").partition("｜")
                if not val.strip() or not lab.strip():
                    must.append("data 必须有数值与标签")
            if not b[1]:
                must.append("data 不能为空")
            th = THEMES.get(key or meta.get("theme", "paper"), THEMES["paper"])
            room = MOBILE_TABLE_PX - 2 * th["grid"]["inset"]
            for line in b[1]:
                value = line.replace("|", "｜").partition("｜")[0].strip()
                if text_px(value, th["type"]["data_size"]) + 4 > room:
                    must.append(f"data 数值在 320px 无法完整显示：{value[:24]}；改用文字或重新组织口径，不缩字号")
            continue
        if not b[0]:
            must.append("bars 必须声明单一单位/口径：写在 ::: bars 后")
        items = [(v.strip(), lab.strip()) for v, _, lab in (x.replace("|", "｜").partition("｜") for x in b[1])]
        nums = []
        for v, lab in items:
            if not re.fullmatch(r"\d+(\.\d+)?", v):
                must.append(f"bars 的值必须是数字：{v or '（空）'}")
            else:
                num = float(v)
                if not math.isfinite(num):
                    must.append("bars 的值必须是有限数字")
                else:
                    nums.append(num)
                    if text_px(v, THEMES.get(key or meta.get("theme", "paper"), THEMES["paper"])["grid"]["body"]) > 110:
                        must.append(f"bars 数值过长：{v[:24]}；改用开放表格或文字，避免挤压标签")
            if not lab:
                must.append(f"bars 的 {v} 缺少标签：数值没有口径等于没有信息")
        if len(items) < 2:
            must.append("bars 至少 2 项：单项对比不成立，直接用文字")
    for i, (k, b) in enumerate(blocks):
        if k in ("h2", "h3") and (i + 1 == len(kinds) or kinds[i + 1] in ("h2", "h3")):
            must.append("标题后缺少内容")
        if k == "table" and (not b or any(len(row) != len(b[0]) for row in b)):
            must.append("表格行列数不一致，不能对齐数据")
        th = THEMES.get(key or meta.get("theme", "paper"), THEMES["paper"])
        inset = th.get("grid", {}).get("inset", 0)
        if k == "table" and b and not table_fits(b, inset, table_pad(th)):
            # V4：不再以「必须改」阻断。窄屏确实放不下时渲染为记录卡（标签与值成对、字号不缩），
            # 让读者仍能取到全部信息；是否应删列仍是编辑决定。
            should.append(f"表格 {len(b[0])} 列在 320px 放不下，已改为记录卡堆叠；"
                          f"若这些列本可省略，请删低价值列")
        if k == "table" and b and len(b[0]) >= 5:
            should.append(f"表格 {len(b[0])} 列：390px 下每列过窄，改成更少列或拆成两张表（不要缩小字号硬塞）")
        if k == "note":
            label, lines = b[0] or "", b[1]
            # 来源与口径两行内：一行来源、一行口径；单独的地址行不计，单位写在图表头不进注
            text = [ln for ln in lines if not re.fullmatch(r"\s*https?://\S+\s*", ln)]
            if re.search(r"来源|口径", label) and len(text) > 2:
                must.append("数据来源与口径过长：两行内（来源一行、口径一行；标签点明的词不写前缀），地址单独一行不计")
            for ln in text:
                if len(ln) > 60:
                    should.append(f"注释行过长（{len(ln)} 字）：来源短写「主体（日期）」，口径一句话")
                    break
    title = meta.get("title", "")
    if not api_title(title):
        must.append("缺少标题")
    for field, value, cap in (("title", api_title(title), 32), ("author", meta.get("author", ""), 16), ("digest", meta.get("digest", ""), 120)):
        if len(value) > cap:
            must.append(f"{field} 超过发布上限 {cap}：请编辑，不静默截断")
    if meta.get("density", "standard") not in ("dense", "standard", "airy"):
        must.append(f"density「{meta['density']}」不存在：dense / standard / airy（必须修正）")
    for issue in audit(meta, blocks)["issues"]:
        if issue["severity"] == "must":
            must.append(f"编辑必须修 · {issue['code']} · {issue['location']}：{issue['problem']} → {issue['action']}")
    return must, should


def evidence(meta, blocks, base="."):
    """只报告需对照的结构/资产与数据状态，不推测阅读质量。"""
    kinds = [k for k, _ in blocks]
    imgs = [b for k, b in blocks if k == "img"]
    fs = first_screen(meta, blocks)
    out = [f"结构 · {doc_len(blocks)}字 · H2 {kinds.count('h2')} · 引文 {kinds.count('quote')} · peak {kinds.count('peak')}"]
    out.append(f"首屏 · {' > '.join(fs['layers']) or '空'} · 重元素 {fs['weight']}"
               + ("（两个入口抢重心，请只留一个）" if fs["weight"] > 1 else ""))
    for alt, src, role in imgs:
        out.append(f"资产 · {src or 'todo'} · {(role or '').strip() or '职责缺失'} · {alt}")
    for i, (k, b) in enumerate(blocks):
        if k in ("bars", "data"):
            note = blocks[i + 1][1] if i + 1 < len(blocks) and blocks[i + 1][0] == "note" else ("", [])
            out.append(f"图示 · {k} · {b[0]} · {len(b[1])}项 · {note[0] or '来源待补'}（声明不等于核真）")
        th = THEMES.get(meta.get("theme", "paper"), THEMES["paper"])
        inset = th.get("grid", {}).get("inset", 0)
        if k == "table" and not table_fits(b, inset, table_pad(th)):
            out.append(f"表格 · {len(b)}行×{len(b[0])}列 · 320px 放不下 → 已按记录卡堆叠")
    out.append("复核 · 正文、图注与来源的阅读连续性；封面两裁切与素材授权见预览")
    return out


PREVIEW = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{margin:0;background:#EDEDEB;font-family:-apple-system,'PingFang SC',sans-serif}}
.bar{{display:flex;justify-content:space-between;align-items:center;gap:10px 12px;flex-wrap:wrap;padding:10px 16px;
background:#fff;border-bottom:1px solid #e5e5e5;font-size:12px;color:#888;}}
button{{border:0;background:#1F1F1F;color:#fff;padding:8px 16px;border-radius:6px;font-size:13px;cursor:pointer;white-space:nowrap;flex-shrink:0}}
.phone{{position:relative;max-width:430px;margin:24px auto 64px;background:#fff;padding:24px 16px 48px;box-sizing:border-box}}
.nt{{padding:2px 2px 16px;margin-bottom:22px;border-bottom:1px solid #EDEDEB}}
.nt h1{{margin:0 0 8px;font-size:22px;line-height:1.42;font-weight:700;color:#191919;letter-spacing:-.02em;font-family:-apple-system,BlinkMacSystemFont,'PingFang SC','Microsoft YaHei',sans-serif;line-break:strict;overflow-wrap:anywhere;word-break:normal}}
.nt .au{{margin:0;font-size:13px;line-height:1.6;color:#6B6762}}
.cv{{max-width:430px;margin:24px auto 0;background:#fff;padding:16px;box-sizing:border-box}}
.cv h4{{margin:0 0 8px;font-size:12px;color:#746F66;font-weight:600}}
.cv img{{display:block;width:100%;background:#F0EEE9}}
.as{{margin-top:14px;padding-top:12px;border-top:1px solid #EFEDE9}}
.as img{{display:block;width:100%;background:#F0EEE9}}
.hint{{margin:16px 0 0;font-size:12px;line-height:1.7;color:#746F66}}</style></head>
<body><div class="bar"><span>{theme} · 移动预览</span><button onclick="cp(this)">复制正文（图片另传）</button></div>
<div class="phone">{native}<div id="c">{body}</div></div>{cover}{assets}
<script>function cp(b){{var c=document.getElementById('c'), r=document.createRange();r.selectNodeContents(c);
var s=getSelection();s.removeAllRanges();s.addRange(r);
function copy(e){{var n=c.cloneNode(true);n.querySelectorAll('img').forEach(function(i){{i.setAttribute('src',i.dataset.local||i.getAttribute('src'));i.removeAttribute('data-local')}});e.clipboardData.setData('text/html',n.innerHTML);e.clipboardData.setData('text/plain',c.innerText);e.preventDefault()}}
document.addEventListener('copy',copy);var ok=false;try{{ok=document.execCommand('copy')}}finally{{document.removeEventListener('copy',copy)}}
if(ok)s.removeAllRanges();b.textContent=ok?'正文已复制；本地图片须另传':'请手动复制正文，图片另传';setTimeout(function(){{b.textContent='复制正文（图片另传）'}},2200)}}</script>
</body></html>"""


def preview_image(src, base):
    """仅预览嵌图；正文路径与上传职责不变，不加载外部资源。"""
    if re.match(r"^(?:[a-z][a-z0-9+.-]*:|//)", src, re.I):
        return ""
    path = resolve(src, base)
    if not os.path.isfile(path):
        return src
    mime = mimetypes.guess_type(path)[0] or "application/octet-stream"
    if mime not in ("image/jpeg", "image/png", "image/gif", "image/webp"):
        return src
    return f"data:{mime};base64," + base64.b64encode(open(path, "rb").read()).decode("ascii")


def cover_block(meta, base):
    """预览里的封面检查：2.35:1 首图裁切 + 1:1 信息流缩略。封面不参与正文粘贴。"""
    src = (meta.get("cover") or "").strip()
    if not src or TODO.match(src):
        return ('<div class="cv"><h4>封面</h4><p class="hint" style="margin:0">未设置封面。'
                f'公众号需要一张 {COVER_RATIO}:1 的封面：方向见 references/direction.md「封面工艺」。</p></div>')
    p = resolve(src, base)
    wh = img_size(p) if os.path.exists(p) else None
    info = f"{wh[0]}×{wh[1]}（{wh[0] / wh[1]:.2f}:1）" if wh else "尺寸未知"
    warn = "" if wh and COVER_BAND[0] <= wh[0] / wh[1] <= COVER_BAND[1] else " 主体必须落在中央安全区——微信会裁。"
    return (f'<div class="cv"><h4>封面 · {info}</h4>'
            f'<img src="{H.escape(src)}" alt="封面裁切预览" style="aspect-ratio:2.35/1;object-fit:cover">'
            f'<h4 style="margin:16px 0 8px">1:1 缩略（信息流 / 会话卡片）</h4>'
            f'<img src="{H.escape(src)}" alt="封面缩略预览" style="width:132px;height:132px;object-fit:cover">'
            f'<p class="hint">默认不放文字。{warn}</p></div>')


def asset_sheet(blocks, base="."):
    """预览末尾的资产对照表：附路径／职责／说明／尺寸／体积，不重复展示正文图片。

    配图闭环的最后一段：视觉决策 → 取资产 → 这里逐张过目（留下 / 重做 / 删除）→ 渲染进正文。
    只出现在预览里，不进正文、不会被复制进编辑器。
    """
    imgs = [b for k, b in blocks if k == "img"]
    if not imgs:
        return ""
    rows = []
    for alt, src, role in imgs:
        tag = H.escape(role or "（未声明职责）")
        if not src or TODO.match(src):
            rows.append(f'<div class="as"><p class="hint">待补 · {tag}<br>{H.escape(alt or "（无说明）")}</p></div>')
            continue
        fp = resolve(src, base)
        if not os.path.isfile(fp):
            rows.append(f'<div class="as"><p class="hint">{tag} · 文件不存在：{H.escape(src)}</p></div>')
            continue
        wh, kb = img_size(fp), os.path.getsize(fp) // 1024
        info = f"{wh[0]}×{wh[1]}（{wh[0] / wh[1]:.2f}:1）· {kb}KB" if wh else f"{kb}KB"
        rows.append(f'<div class="as"><p class="hint">{H.escape(src)} · {tag} · {info}<br>{H.escape(alt or "（无说明）")}</p></div>')
    return (f'<div class="cv"><h4>正文资产 · {len(imgs)} 张（图片见正文上下文）</h4>'
            + "".join(rows)
            + '<p class="hint">逐张只问三句：合这套语法吗？比正文多给什么？390px 上主语还站得住吗？'
              '→ 留下 / 重做 / 删除。留下的要能说出「为什么是这张」。</p></div>')


def render(md, theme=None):
    meta, blocks = parse(md)
    key = theme or meta.get("theme", "paper")
    if key not in THEMES:
        raise ValueError(f"未知主题 {key}，可选：{', '.join(THEMES)}")
    r = R(THEMES[key], meta.get("density", "standard"))
    out, n = [], 0
    if meta.get("kicker"):
        out.append(f'<section style="margin-bottom:{r.g(12)}px;">'
                   + r.micro(typo(meta["kicker"]), extra="letter-spacing:0.12em;font-weight:600;") + "</section>")
    if meta.get("deck"):
        # 副题与导语同处首屏：副题只做一句限定，字号低于导语，避免两个入口打架。
        out.append(f'<section style="margin-bottom:{r.g(20)}px;">{r.p(r.inline(meta["deck"]), r.body, r.t["sub"], f"font-family:{r.font};")}</section>')
    heads = [b[1] for b in blocks if b[0] == "h2"]
    toc_done = meta.get("toc", "").lower() not in ("true", "yes", "1") or len(heads) < 3
    # 目录只在首段后，顺序由源稿决定。
    toc_after_p, seen_p = any(k == "p" for k, _ in blocks), False
    attach = ("bars", "data", "table", "img")     # 来源/口径紧贴其证据，不做悬空脚注
    consumed = set()
    for i, (kind, b) in enumerate(blocks):
        if i in consumed:
            continue
        nxt = blocks[i + 1][0] if i + 1 < len(blocks) else ""
        below = 10 if nxt == "note" else None
        if not toc_done and kind != "lead" and (seen_p or not toc_after_p):
            out.append(r.toc(heads))
            toc_done = True
        if kind == "h2":
            n += 1
            out.append(r.h2(b, n))
        elif kind == "h3":
            out.append(r.h3(b))
        elif kind == "p":
            out.append(r.para(b))
            seen_p = True
        elif kind in ("lead", "quote"):
            out.append(r.quote(b[0], b[1], kind))
        elif kind == "peak":
            out.append(r.quote(peak_text(b), "", "peak"))
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
            out.append(r.lst(*b))
        elif kind == "code":
            out.append(r.code(*b))
        elif kind == "img":
            parts = (b[2] or "").split()
            mode = parts[1].lower() if len(parts) > 1 else ""
            if mode == "sequence":
                end = i
                group = []
                while end < len(blocks) and blocks[end][0] == "img":
                    image = blocks[end][1]
                    op = (image[2] or "").split()
                    if len(op) < 2 or op[1].lower() != "sequence":
                        break
                    group.append(image)
                    end += 1
                if len(group) >= 2:
                    out.append(f'<section style="margin:{r.g(24)}px 0;">' + ''.join(
                        r.img(f"{n:02d} · {image[0]}", image[1], image[2], below=18, above=0 if n == 1 else 18)
                        for n, image in enumerate(group, 1)) + '</section>')
                    consumed.update(range(i + 1, end))
                    continue
            if mode == "comparison" and "parallel" in parts[2:] and i + 1 < len(blocks) and blocks[i + 1][0] == "img":
                other = blocks[i + 1][1]
                op = (other[2] or "").split()
                if len(op) > 1 and op[1].lower() == "comparison" and "parallel" in op[2:]:
                    cells = [r.img(f"对照 {n} · {image[0]}", image[1], image[2], below=0)
                             for n, image in enumerate((b, other), 1)]
                    out.append('<table style="width:100%;table-layout:fixed;border-collapse:collapse;">'
                               '<tr>' + ''.join('<td style="width:50%;vertical-align:top;padding:0 4px;overflow-wrap:anywhere;">' + cell + '</td>' for cell in cells) + '</tr></table>')
                    consumed.add(i + 1)
                    continue
            out.append(r.img(*b, below=below))
        elif kind == "hr":
            out.append(r.hr())
        else:
            sys.exit(f"未知原语 ::: {kind}（可用：peak / note / unknown / data / bars）")
    out.append(r.signature(meta))
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
    """一次渲染的全部产物，供 CLI 与 --deliver 共用（避免两套路径各写一遍）。"""
    base = os.path.dirname(os.path.abspath(md_path))
    with open(md_path, encoding="utf-8") as f:
        source_text = f.read()
    key, meta, blocks, body = render(source_text, theme)
    # Reject escapes before any preview, copying or generated output is written.
    for src in [meta.get("cover", "")] + [b[1] for k, b in blocks if k == "img"]:
        if src and not TODO.match(src):
            local_path(src, base)
    out = out or f"{os.path.splitext(md_path)[0]}_{key}.html"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    out_base = os.path.dirname(os.path.abspath(out))

    def output_src(src):
        if not src or TODO.match(src) or re.match(r"^(?:[a-z][a-z0-9+.-]*:|//)", src, re.I):
            return src
        original = resolve(src, base)
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
    open(out, "w", encoding="utf-8").write(body)
    prev = os.path.splitext(out)[0] + "_预览.html"
    # 预览模拟平台原生标题栏 / 作者行：title、author 只进原生字段，正文不再重印。
    # 复制按钮只复制 #c，模拟标题栏不会被带进编辑器。
    nt = H.escape(api_title(meta.get("title", "")))
    # 平台原生元信息行自带发布日期；预览用「作者 + frontmatter 日期」模拟，
    # 与正文对看：日期应只在这一行出现一次。
    au_line = H.escape("  ".join(x for x in (meta.get("author", ""), meta.get("date", "")) if x))
    native = (f'<div class="nt"><h1>{nt}</h1>' + (f'<p class="au">{au_line}</p>' if au_line else "") + "</div>") if nt else ""
    preview = PREVIEW.format(title=H.escape(meta.get("title", "")), theme=THEMES[key]["name"],
                             cover=cover_block(dict(meta, cover=output_src(meta.get("cover", ""))), out_base),
                             assets=asset_sheet([(k, (b[0], output_src(b[1]), b[2])) if k == "img" else (k, b)
                                                 for k, b in blocks], out_base),
                             native=native, body=body)
    preview = re.sub(r'(<img\b[^>]*src=")([^"]+)(")',
                     lambda m: m[1] + H.escape(preview_image(H.unescape(m[2]), out_base)) + m[3]
                     + ' data-local="' + m[2] + '"', preview)
    open(prev, "w", encoding="utf-8").write(preview)

    # 发布字段 sidecar：publish.py --meta 直接消费，保证草稿原生字段与预览所见一致。
    cover = (meta.get("cover") or "").strip()
    m1, s1 = check(body)
    m2, s2 = compose_gate(meta, blocks, base, key)
    # Gate 1 的建议级结论过去算完就丢；并进 Gate 2 的建议里，读者才看得到。
    s2 = [f"平台层建议：{x}" for x in s1] + s2
    contrasts = contrast_checks(key)
    for pair in contrasts:
        if not pair["pass"]:
            m2.append(f"色彩对比不足：{pair['foreground_role']} / {pair['background']} 为 {pair['ratio']:.2f}:1，要求 ≥4.5")
    fs = first_screen(meta, blocks)
    if fs["weight"] > 1:
        s2.append(f"首屏有 {fs['weight']} 个重元素（{'、'.join(fs['layers'])}）：只保留一个入口，"
                  f"其余降级为限定或证据")
    review = audit(meta, blocks)
    side = {
        "title": meta.get("title", ""),
        "api_title": api_title(meta.get("title", "")),
        "author": (meta.get("author") or ""),
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
        "composition_evidence": {"first_screen_layers": fs["layers"], "first_screen_weight": fs["weight"],
                                 "h2_count": sum(k == "h2" for k, _ in blocks), "body_characters": doc_len(blocks),
                                 "scope": "源文开篇结构，不是像素首屏；实际首屏见浏览器测量"},
        "editorial_review": review,
        "integrity_version": 2,
        "source": {"path": os.path.abspath(md_path), "sha256": sha256(md_path)},
        "assets": [{"path": src, "sha256": sha256(local_path(src, out_base)), "source_path": src,
                    "source_sha256": sha256(local_path(src, base))}
                   for src in sorted(set([output_src(b[1]) for k, b in blocks
                                          if k == "img" and b[1] and not TODO.match(b[1])]
                                         + ([output_src(cover)] if cover and not TODO.match(cover) else [])))
                   if os.path.isfile(local_path(src, out_base))],
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "render_errors": m1 + m2,
        "pending_assets": any(not b[1] or TODO.match(b[1]) for k, b in blocks if k == "img"),
    }
    meta_path = os.path.splitext(out)[0] + ".meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(side, f, ensure_ascii=False, indent=2)
    return {"key": key, "meta": meta, "blocks": blocks, "body": body, "side": side,
            "out": out, "preview": prev, "meta_path": meta_path,
            "gates": (("Gate 1 Platform", m1, s1), ("Gate 2 Composition", m2, s2))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md", nargs="?")
    ap.add_argument("--theme", choices=list(THEMES))
    ap.add_argument("-o", "--out")
    ap.add_argument("--against", help="原稿 .md：比对改写前后的事实单元（不改稿，只报告）")
    ap.add_argument("--ledger", help="修改台账 .md：五列表格，逐行校验收益与位置")
    ap.add_argument("--deliver", help="交付目录：一次产出源稿/正文/预览/meta/修改记录/验收")
    a = ap.parse_args()
    if not a.md:
        ap.error("需要一个 markdown 文件")
    if os.path.splitext(a.md)[1].lower() not in (".md", ".markdown", ".txt"):
        ap.error("仅支持 UTF-8 Markdown/纯文本；DOCX 请先用 extract_docx.py 转换")

    deliver = os.path.abspath(a.deliver) if a.deliver else ""
    if deliver:
        os.makedirs(os.path.join(deliver, "images"), exist_ok=True)
    out = os.path.join(deliver, "正文.html") if deliver else a.out
    res = build(a.md, a.theme, out)
    key, meta, blocks, side = res["key"], res["meta"], res["blocks"], res["side"]
    g1, g2 = res["gates"]
    m1, m2, s2 = g1[1], g2[1], g2[2]      # Gate 1 的建议级结论已并入 g2[2]
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
            change, why = classify_fact_change(original_blocks, blocks, "num", item) \
                if re.search(r"\d", item) else ("lost", "")
            if change == "lost":
                change, why = classify_fact_change(original_blocks, blocks, "date", item)
            message = f"原稿事实单元在改稿中消失：{item}"
            if change in ("moved", "rounded"):
                s2.append(f"{message}；{why}（结构性搬家/概括不等于删除，但口径需确认）")
            else:
                m2.append(f"{message}；确认是删除还是改写，确属删除请写入 frontmatter removed_facts")
        for item in loose:
            change, why = classify_fact_change(original_blocks, blocks, "date", item) \
                if not re.search(r"[^\d\-\s]", item) else ("added", "")
            if change == "rounded":
                s2.append(f"改稿新增「{item}」；{why}（概括式表述，确认没有替代精确值）")
            else:
                m2.append(f"改稿新增事实单元「{item}」附近没有可核对来源：补出处，或说明它来自何处")
        for change in facts_diff["precision_changes"] + facts_diff["qualifier_changes"]:
            m2.append(f"事实精度或限定变化需回源确认：{change}（有链接不等于已核真）")
        for quote in facts_diff["dropped_quotes"] + facts_diff["introduced_quotes"]:
            m2.append(f"直接引语变化需逐字回源：{quote[:40]}；恢复原话或明确改为间接转述")
        voice_diff = compare_voice(original_blocks, blocks)
        side["fact_diff"] = facts_diff
        side["voice_diff"] = voice_diff
        if voice_diff["changes"]:
            for change in voice_diff["changes"]:
                # 声音变化是「需要人确认」的事，不阻断渲染：声音该不该保留由编辑判断。
                s2.append(f"作者声音形态变化（需确认是有意删改）：{change['mark']} "
                          f"{change['original']} → {change['edited']}（{change['note']}）")
        side["render_errors"] = m1 + m2

    ledger_rows, ledger_problems = [], []
    if a.ledger:
        with open(a.ledger, encoding="utf-8") as f:
            ledger_rows, ledger_problems = parse_ledger(f.read())
        for row in ledger_rows:
            if not locate(row["位置"], blocks):
                ledger_problems.append(f"台账位置「{row['位置']}」在正文找不到：位置必须能回到原文")
        side["ledger"] = {"rows": ledger_rows, "problems": ledger_problems}
    if ledger_problems or facts_diff:
        with open(res["meta_path"], "w", encoding="utf-8") as f:
            json.dump(side, f, ensure_ascii=False, indent=2)

    for issue in review["issues"]:
        print(f"编辑提示 · {issue['severity']:<6} · {issue['location']} · {issue['problem']} → "
              f"{issue['action']}；收益：{issue['benefit']}（{issue['class']}，需要：{issue['needs']}）")
    print(f"{THEMES[key]['name']} → {res['out']}\n预览 → {res['preview']}\n"
          f"发布字段 → {res['meta_path']}（publish.py --meta 直接消费）\n")
    print("\nGate 3 证据（可核对的都摆在这里；结论与艺术判断由通读的人 / 视觉模型给）")
    for line in evidence(meta, blocks, os.path.dirname(os.path.abspath(a.md))):
        print("  " + line)
    for gate, must, should in res["gates"]:
        print(f"\n{gate}: {'FAIL' if must else 'PASS'}")
        for x in must:
            print("  必须改 ·", x)
        for x in should:
            print("  建议改 ·", x)
    if facts_diff is not None:
        print(f"\n事实单元比对：保留 {len(facts_diff['preserved'])}/{facts_diff['source_units']} · "
              f"消失 {len(facts_diff['dropped'])} · 新增 {len(facts_diff['introduced'])}（不等于核真）")
    if ledger_problems:
        print("\n修改台账：" + "；".join(ledger_problems))

    if deliver:
        report = render_report(review, facts_diff, ledger_problems, voice_diff)
        report += "\n## 类型策略\n\n" + "\n".join(f"- {x}" for x in strategy_notes(meta, blocks)) + "\n"
        if ledger_rows:
            report += "\n## 修改台账（已校验）\n\n| 位置 | 问题 | 动作 | 收益 | 保留检查 |\n|---|---|---|---|---|\n"
            report += "\n".join(f"| {r['位置']} | {r['问题']} | {r['动作']} | {r['收益']} | {r['保留检查']} |"
                                for r in ledger_rows) + "\n"
        open(os.path.join(deliver, "修改记录.md"), "w", encoding="utf-8").write(report)
        acceptance = ["# 验收结果", "",
                      f"- 生成时间：本机运行 `render.py --deliver`（{SKILL_VERSION}）",
                      f"- 主题：`{key}`（{THEMES[key]['name']}）", ""]
        for gate, must, should in res["gates"]:
            acceptance.append(f"## {gate}：{'FAIL' if must else 'PASS'}")
            acceptance.append("")
            acceptance += [f"- 必须改：{x}" for x in must] or ["- 必须改：无"]
            acceptance += [f"- 建议改：{x}" for x in should] or ["- 建议改：无"]
            acceptance.append("")
        acceptance += ["## 微信验收：三级必须分开记录", "",
                       "| 级别 | 能证明什么 | 本轮状态 |", "|---|---|---|",
                       "| 浏览器 PASS | 本地 320/360/390/430px 无溢出、无数值拆行、最小字号达标 | UNVERIFIED（需四宽度实跑截图作为证据） |",
                       "| API 回读 PASS | 草稿字段与本地正文逐字一致（title/content/thumb_media_id） | UNVERIFIED（需授权账号执行 `publish.py`）|",
                       "| 微信真机 PASS | 客户端清洗后的样式、后台重开、iOS/Android 阅读、封面 2.35:1 与 1:1 裁切 | UNVERIFIED（需真机，脚本无法代劳） |",
                       "",
                       "## UNVERIFIED（不得计作通过）", "",
                       "- Gate 3 人工视觉判断：需通读 320/360/390/430px 截图后填写",
                       "- Gate 4 真实微信：见上表；三者互不替代",
                       "- 事实逐项第二来源核真：本地脚本不做核真",
                       "- 独立外部读者 A/B 盲选：未执行"]
        open(os.path.join(deliver, "验收.md"), "w", encoding="utf-8").write("\n".join(acceptance) + "\n")
        shutil.copyfile(a.md, os.path.join(deliver, "源稿.md"))
        print(f"\n交付包 → {deliver}（源稿/正文/预览/meta/修改记录/验收/素材）")

    print("\nGate 3 Art Direction：对照上面证据通读 390px 预览。"
          "CONTENT / EDITORIAL / VISUAL / MOBILE / FINAL JUDGMENT —— 保留 / 修改 / 删除并说明理由，可以无需修改。")
    if not meta.get("author"):
        print("未提供 author：草稿作者栏将留空（作者名只走原生字段，正文不印）")
    sys.exit(1 if m1 or m2 else 0)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as e:
        sys.exit(f"输入错误：{e}")
