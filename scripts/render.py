#!/usr/bin/env python3
"""Composed Markdown → 公众号 HTML + 390px 预览 + Gate 1/2（一次调用）。

    render.py article.md [--theme paper|letter|ink|frost|bone|folio] [-o out.html]
    render.py --specimen [-o assets/themes.html]      六格气候对照板（入库，--specimen 重新生成）

产出 {stem}_{theme}.html 与 {stem}_{theme}_预览.html（预览另含封面两种裁切）。
语法见 SKILL.md。退出码 1 = 存在「必须改」。
设计判断只在 SKILL.md；本文件只执行可确定的子集。
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
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check import check  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
THEMES = json.load(open(os.path.join(HERE, "..", "assets", "themes.json"), encoding="utf-8"))
SANS = "-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei','Noto Sans CJK SC',sans-serif"
SERIF = "'Songti SC','STSong','SimSun','Noto Serif CJK SC',serif"
MONO = "'SF Mono',Menlo,Consolas,monospace"
CJK = "\u4e00-\u9fff\u3400-\u4dbf"
# 默认阅读字号，非必须遵守的审美配额
MICRO, SMALL, BODY, LEAD, DISPLAY, TITLE = 12, 14, 16, 18, 20, 24

# 正文视觉职责（封面单独由 frontmatter 承担）。说不出职责 → 删。
ROLES = {"锚点", "解释", "证据", "对比", "结构", "场景", "隐喻", "停顿", "数据",
         "anchor", "explain", "evidence", "compare", "structure", "context", "metaphor", "rhythm", "data"}
FACT = {"解释", "证据", "对比", "结构", "数据",
        "explain", "evidence", "compare", "structure", "data"}       # 说明用正文色、字号大一级
TODO = re.compile(r"(?i)^(todo|待补)")
COVER_RATIO = 2.35                    # 封面目标比例（微信首图）
COVER_BAND = (1.6, 3.0)               # 可接受区间；超出说明这不是一张封面
COVER_MIN_W = 900                     # 下方会被裁，再窄就糊

BR = '<span leaf=""><br></span>'
INLINE = re.compile(r"`([^`]+)`|==(.+?)==|\*\*(.+?)\*\*|<u>(.+?)</u>|~~(.+?)~~|\[([^\]]+)\]\(([^)\s]+)\)")


def typo(s):
    """仅归一中文语境标点；不改引用引号、数字、代码或资源地址。"""
    def prose(text):
        return re.sub(f"(?<=[{CJK}])([,;:!?])|(?<=[A-Za-z0-9])([,;!?])\\s*(?=[{CJK}])",
                      lambda m: dict(zip(",;:!?", "，；：！？"))[m[1] or m[2]], text)
    return "".join(part if i % 2 else prose(part) for i, part in enumerate(
        re.split(r"(`[^`]+`|\[[^\]]+\]\([^)\s]+\)|https?://[^\s<>\u3000，；。！？）\"]+)", s)))


def parse(md):
    md = md.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    meta, blocks = {}, []
    m = re.match(r"^---\n(.*?)\n---\n", md, re.S)
    if m:
        for ln in m.group(1).splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                # 行内注释（# 前须有空白，不伤 URL fragment）；文档样张带注释，照抄不能炸
                v = v.strip()
                quoted = re.fullmatch(r"([\"'])(.*?)\1(?:\s+#.*)?", v)
                v = quoted[2] if quoted else re.sub(r"\s+#.*$", "", v).strip()
                meta[k.strip()] = v
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
            flush()
            ordered, items = bool(re.match(r"\d", s)), []
            while i < len(lines) and re.match(r"\s*([-*]|\d+[.、])\s", lines[i]):
                items.append(re.sub(r"^\s*([-*]|\d+[.、])\s+", "", lines[i]))
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
    def __init__(self, t, density):
        self.t = t
        self.k = {"dense": 0.8, "airy": 1.2}.get(density, 1.0)
        self.font = SERIF if t["display"] == "serif" else SANS

    def g(self, px):
        return round(px * self.k)

    def leaf(self, s):
        return BR if not s else f'<span leaf="">{H.escape(s, quote=False)}</span>'

    def inline(self, s, normalize=True):
        t, out, pos = self.t, [], 0
        s = typo(s) if normalize else s
        for m in INLINE.finditer(s):
            if m.start() > pos:
                out.append(self.leaf(s[pos:m.start()]))
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
                out.append(f'<span style="border-bottom:1px solid {t["line"]};">{self.leaf(ltext)}</span>'
                           + (f'<span style="color:{t["muted"]};font-size:{SMALL}px;">{self.leaf(" " + url)}</span>'
                              if url.startswith("http") else ""))
            pos = m.end()
        if pos < len(s):
            out.append(self.leaf(s[pos:]))
        return "".join(out)

    def p(self, inner, size=None, color=None, extra=""):
        size = BODY if size is None else size
        lh = "" if "line-height" in extra else f'line-height:{self.t["leading"] if size == BODY else 1.75};'
        ls = "" if "letter-spacing" in extra else "letter-spacing:normal;"
        return (f'<p style="margin:0;font-size:{size}px;{lh}color:{color or self.t["text"]};'
                f'{ls}{extra}">{inner}</p>')

    def micro(self, s, color=None, extra=""):
        return self.p(self.leaf(s), MICRO, color or self.t["muted"], f"font-weight:500;{extra}")

    def rule(self, w=24, h=1, color=None, center=True, below=0):
        pos = f"margin:0 auto {below}px;" if center else "flex-shrink:0;"
        return f'<section style="width:{w}px;height:{h}px;background:{color or self.t["line"]};{pos}">{BR}</section>'

    def seal(self, glyph, size=24, color=None):
        return (f'<span style="display:inline-block;width:{size}px;height:{size}px;line-height:{size - 2}px;'
                f'border:1px solid {self.t["muted"]};border-radius:50%;text-align:center;font-size:{MICRO}px;'
                f'font-weight:600;color:{color or self.t["text"]};box-sizing:border-box;">{self.leaf(glyph)}</span>')

    def h2(self, text, n):
        t = self.t
        if t["heading"] == "seal":
            mark = self.seal(f"{n:02d}", 24) + " "
        elif t["heading"] == "number":
            mark = f'<span style="font-size:{SMALL}px;color:{t["muted"]};font-weight:500;">{self.leaf(f"{n:02d}　")}</span>'
        else:
            mark = ""
        return f'<section style="margin:{self.g(32)}px 0 {self.g(14)}px;">' + self.p(
            mark + self.inline(text), DISPLAY, extra=f"font-weight:600;line-height:1.5;font-family:{self.font};") + "</section>"

    def h3(self, text):
        return f'<section style="margin:{self.g(24)}px 0 {self.g(10)}px;">' + \
            self.p(self.inline(text), BODY, self.t["text"], "font-weight:700;") + "</section>"

    def para(self, text):
        return f'<section style="margin:0 0 {self.g(20)}px;">' + \
            self.p(self.inline(text), extra="text-align:left;") + "</section>"

    def quote(self, text, src, weight):
        """lead / quote / peak 同一原语，三种重量。引用不改原句；重点可用文字、侧线或少量反色。"""
        t = self.t
        serif = t["quote"] == "serif"
        if weight == "lead":
            return f'<section style="margin:{self.g(8)}px 0 {self.g(24)}px;">' + \
                self.p(self.inline(text, normalize=False), LEAD, t["text"],
                       f"line-height:1.85;font-family:{self.font};") + (self.p(self.leaf("—— " + src), MICRO, t["muted"], "margin-top:12px;") if src else "") + "</section>"
        fam = f"font-family:{SERIF};" if serif else ""
        if weight == "quote":
            cite = self.p(self.leaf(f"—— {src}"), MICRO, t["muted"],
                          "margin-top:8px;") if src else ""
            return (f'<section style="margin:{self.g(24)}px 0;padding:0 4px 0 12px;'
                    f'border-left:1px solid {t["line"]};">'
                    + self.p(self.inline(text, normalize=False), LEAD, t["sub"], f"font-weight:500;line-height:1.8;{fam}")
                    + cite + "</section>")
        style = t["peak"]
        body_color = t["on_dark"] if style == "dark" else t["text"]
        claim = self.p(self.inline(text, normalize=False), DISPLAY, body_color,
                       f"font-weight:600;line-height:1.65;{fam}")
        box = ""
        if style == "field":
            box = f"padding:0 0 0 16px;border-left:2px solid {t['accent']};"
        elif style == "dark":
            box = f"padding:{self.g(20)}px 18px;background:{t['dark']};"
        return f'<section style="margin:{self.g(32)}px 0;text-align:left;{box}">{claim}</section>'

    def note(self, label, lines):
        t = self.t
        head = self.micro(label, extra="margin-bottom:6px;") if label else ""
        body = "".join(self.p(self.inline(x), SMALL, t["sub"], "line-height:1.8;") for x in lines)
        return f'<section style="margin:{self.g(16)}px 0;">{head}{body}</section>'

    def data(self, lines):
        # 全角「｜」与半角「|」都要能拆：中文输入法默认给的是全角，
        # 只按半角拆会把「3｜标签」整条当成数值，标签消失、大字号里挤进一整句。
        t, rows, items = self.t, [], [x.replace("|", "｜").split("｜", 1) for x in lines]
        per = len(items) if 0 < len(items) <= 3 else 2
        for i in range(0, len(items), per):
            cells = "".join(
                f'<section style="flex:1;min-width:0;padding-top:12px;border-top:1px solid {t["text"]};">'
                + self.p(self.leaf(v.strip()), TITLE, t["text"],
                         f"font-weight:600;line-height:1.3;font-family:{self.font};font-variant-numeric:tabular-nums;")
                + self.p(self.inline(lab.strip() if lab else ""), MICRO, t["muted"],
                         "margin-top:6px;")
                + "</section>" for v, *rest in items[i:i + per] for lab in [rest[0] if rest else ""])
            rows.append(f'<section style="display:flex;gap:16px;margin-top:{16 if i else 0}px;">{cells}</section>')
        return f'<section style="margin:{self.g(36)}px 0;">{"".join(rows)}</section>'

    def bars(self, lines, label=""):
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
        rows.append(self.p(self.leaf("零起点 · 最长条代表本组最大值"), MICRO, t["muted"], "margin-top:4px;"))
        for (val, lab), num in zip(items, nums):
            w = f"{num / mx * 100:.6g}" if mx else "0"
            rows.append(
                f'<section style="display:flex;align-items:flex-end;gap:10px;margin-top:{self.g(16)}px;">'
                + self.p(self.inline(lab), SMALL, t["sub"], "flex:1;min-width:0;")
                + self.p(self.leaf(val), BODY, t["text"], f"font-weight:600;font-family:{self.font};font-variant-numeric:tabular-nums;white-space:nowrap;flex-shrink:0;")
                + "</section>"
                + f'<section style="height:5px;background:{t["line"]};margin-top:6px;">'
                + f'<section style="width:{w}%;height:5px;background:{t["accent"]};">{BR}</section></section>')
        return f'<section style="margin:{self.g(32)}px 0;">{"".join(rows)}</section>'

    def table(self, rows):
        t, out = self.t, []
        for i, cells in enumerate(rows):
            tag = "th" if i == 0 else "td"
            out.append("<tr>" + "".join(
                f'<{tag} style="width:{100 / len(cells):.6g}%;padding:10px 6px;vertical-align:top;'
                f'text-align:left;border-bottom:1px solid {t["line"]};font-weight:{600 if i == 0 else 400};">'
                + self.p(self.inline(c), SMALL, t["sub"] if i == 0 else t["text"], "line-height:1.75;")
                + f'</{tag}>' for c in cells) + "</tr>")
        return f'<table style="width:100%;table-layout:fixed;border-collapse:collapse;margin:{self.g(24)}px 0;">' + "".join(out) + "</table>"

    def lst(self, ordered, items):
        t, out = self.t, []
        for n, it in enumerate(items, 1):
            mk = (self.p(self.leaf(f"{n:02d}"), SMALL, t["muted"], "font-weight:500;") if ordered
                  else self.p(self.leaf("·"), BODY, t["muted"], "font-weight:700;"))
            out.append(f'<section style="display:flex;margin-bottom:{self.g(10)}px;">'
                       f'<section style="width:{28 if ordered else 18}px;flex-shrink:0;padding-top:{2 if ordered else 0}px;">{mk}</section>'
                       f'<section style="flex:1;min-width:0;">{self.p(self.inline(it))}</section></section>')
        return f'<section style="margin:{self.g(8)}px 0 {self.g(22)}px;">{"".join(out)}</section>'

    def code(self, lang, body):
        t = self.t
        rows = "".join(
            f'<p style="margin:0;font-family:{MONO};font-size:{SMALL}px;line-height:1.7;white-space:pre-wrap;tab-size:4;color:{t["text"]};">'
            + (self.leaf(ln) if ln.strip() else BR)
            + "</p>" for ln in body)
        label = self.micro(lang.upper(), extra=f"margin-bottom:10px;font-family:{MONO};") if lang else ""
        return (f'<section style="margin:{self.g(24)}px 0;padding:16px 18px;background:{t["field"]};'
                f'border-radius:{t["radius"]}px;">{label}{rows}</section>')

    def img(self, alt, src, role):
        t = self.t
        role0 = next(iter((role or "").split()), "")   # 无职责的图不该崩：Gate 2 会判「必须改」
        mt = self.g(24)
        if not src or TODO.match(src):
            return (f'<section style="margin:{mt}px 0;padding:36px 16px;border:1px dashed {t["muted"]};'
                    f'text-align:center;">{self.micro("待补素材")}'
                    + self.p(self.leaf(alt or "此处插入图片"), SMALL, t["sub"], "margin-top:8px;")
                    + (self.p(self.leaf(f"职责：{role}"), MICRO, t["muted"], "margin-top:4px;") if role else "")
                    + "</section>")
        treat = t.get("image", "flush")
        extra = ""
        if treat == "soft":
            extra = f"border-radius:{t['radius']}px;"
        elif treat == "line":
            extra = f"border:1px solid {t['line']};"
        cap = ("GIF · " if src.lower().endswith(".gif") else "") + (alt or "")
        cap_size = SMALL if role0 in FACT else MICRO
        cap_color = t["sub"] if role0 in FACT else t["muted"]
        return (f'<section style="margin:{mt}px 0;">'
                f'<img src="{H.escape(src)}" alt="{H.escape(alt or "")}" style="max-width:100%;height:auto;display:block;margin:0 auto;{extra}" />'
                + (self.p(self.leaf(typo(cap)), cap_size, cap_color, "margin-top:8px;") if cap else "")
                + "</section>")

    def hr(self):
        t, kind = self.t, self.t["divider"]
        inner = (self.seal("·", 20, t["muted"]) if kind == "seal" else self.rule(32) if kind == "rule"
                 else self.p(self.leaf("· · ·"), SMALL, t["muted"], "letter-spacing:8px;"))
        return f'<section style="margin:{self.g(44)}px 0;text-align:center;">{inner}</section>'

    def signature(self, meta):
        t, out = self.t, []
        if meta.get("cta"):
            out.append(self.p(self.inline(meta["cta"]), SMALL, t["sub"]))
        if meta.get("bio"):
            out.append(self.p(self.leaf(typo(meta["bio"])), MICRO, t["muted"], "margin-top:12px;"))
        return (f'<section style="margin-top:{self.g(32)}px;padding-top:16px;border-top:1px solid {t["line"]};">'
                + "".join(out) + "</section>") if out else ""

    def toc(self, heads):
        t = self.t
        rows = "".join(self.p(self.leaf(f"{n:02d}　{h}"), SMALL, t["text"], "line-height:2.1;")
                       for n, h in enumerate(heads, 1))
        return (f'<section style="margin:0 0 {self.g(36)}px;padding:16px 0;border-top:1px solid {t["line"]};'
                f'border-bottom:1px solid {t["line"]};">{self.micro(t["toc_label"], extra="margin-bottom:10px;")}{rows}</section>')


def visible_len(s):
    return len(re.sub(r"</?u>|https?://\S+|[`*=~\[\]()]", "", s))


def api_title(t):
    """兼容旧源的 |：转为原生标题全角分隔符，不控制断行。"""
    return t.replace("|", "｜").strip()


def auto_digest(meta, blocks, limit=120):
    """摘要兜底：lead > deck > 首段。摘要上限120字（官方文档，见 references/publish.md）。
    不能让微信自己抓正文前 54 字——抓到的开头不稳定（副题等），不是摘要。"""
    src = next((b[0] for k, b in blocks if k == "lead"), "") \
        or meta.get("deck", "") \
        or next((b for k, b in blocks if k == "p"), "")
    src = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", src)      # 链接留文字
    src = re.sub(r"`([^`]*)`|==([^=]*)==|\*\*([^*]*)\*\*|<u>([^<]*)</u>|~~([^~]*)~~",
                 lambda m: next(g for g in m.groups() if g is not None), src)
    return src.strip()[:limit]


def doc_len(blocks):
    """全文可见字数（正文 + 标题 + 列表 + 表格 + 代码 + 旁注）。

    只用段落字数会低估数据型 / 技术型文章：一篇 400 字正文 + 500 行代码的文章
    并不是一篇 400 字的短文，图片预算与节奏判断都跟着错。
    """
    total = 0
    for k, b in blocks:
        if k == "p" or k in ("h2", "h3"):
            total += visible_len(b)
        elif k in ("lead", "quote"):
            total += visible_len(b[0])
        elif k == "peak":
            total += visible_len(peak_text(b))
        elif k == "note":
            total += sum(visible_len(x) for x in b[1])
        elif k == "list":
            total += sum(visible_len(i) for i in b[1])
        elif k == "table":
            total += sum(visible_len(c) for r in b for c in r)
        elif k == "code":
            total += sum(len(x) for x in b[1])
        elif k in ("data", "bars"):
            total += sum(visible_len(x) for x in b[1])
    return total


def peak_text(b):
    return " ".join(b[1]) or b[0]


def resolve(src, base):
    return src if os.path.isabs(src) else os.path.join(base, src)


def first_screen(meta, blocks):
    """仅记录首个正文段落之前的块，不推测像素首屏。"""
    kinds = [b[0] for b in blocks]
    stop = next((i for i, k in enumerate(kinds) if k == "p"), len(kinds))
    layers = [k for k in kinds[:stop] if k in {"lead", "img", "note", "data", "bars", "table", "quote"}]
    if meta.get("deck"):
        layers.insert(0, "deck")
    return layers


def compose_gate(meta, blocks, base="."):
    """Gate 2：可确定的结构与资产检查。审美判断留给 Gate 3。"""
    must, should = [], []
    kinds = [b[0] for b in blocks]
    imgs = [(i, b[1]) for i, b in enumerate(blocks) if b[0] == "img"]
    for idx, (alt, src, role) in imgs:
        role = (role or "").strip()
        role0 = next(iter(role.split()), "")
        if not role0:
            must.append("图片没有声明职责")
        if role0 in FACT and not (alt or "").strip():
            must.append("证据类图必须写清出处 / 口径 / 时间；解释图也需说明")
        if not src or TODO.match(src):
            continue
        if role0 in {"证据", "数据", "evidence", "data"}:
            context = (alt or "") + " " + (" ".join(blocks[idx + 1][1][1]) if idx + 1 < len(blocks) and blocks[idx + 1][0] == "note" else "")
            if re.search(r"AI.*示意|生成.*示意", context):
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
        if not re.search(r"https?://\S+|假设|演示|非统计", source):
            must.append(f"{k} 缺少紧邻来源 note：提供链接与口径，或明确假设/演示（机器不核真）")
        if k == "data":
            for line in b[1]:
                val, _, lab = line.replace("|", "｜").partition("｜")
                if not val.strip() or not lab.strip():
                    must.append("data 必须有数值与标签")
            if not b[1]:
                must.append("data 不能为空")
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
            if not lab:
                must.append(f"bars 的 {v} 缺少标签：数值没有口径等于没有信息")
        if len(items) < 2:
            must.append("bars 至少 2 项：单项对比不成立，直接用文字")
    for i, (k, b) in enumerate(blocks):
        if k in ("h2", "h3") and (i + 1 == len(kinds) or kinds[i + 1] in ("h2", "h3")):
            must.append("标题后缺少内容")
        if k == "table" and (not b or any(len(row) != len(b[0]) for row in b)):
            must.append("表格行列数不一致，不能对齐数据")
    title = meta.get("title", "")
    if not api_title(title):
        must.append("缺少标题")
    for field, value, cap in (("title", api_title(title), 32), ("author", meta.get("author", ""), 16), ("digest", meta.get("digest", ""), 120)):
        if len(value) > cap:
            must.append(f"{field} 超过发布上限 {cap}：请编辑，不静默截断")
    if meta.get("density", "standard") not in ("dense", "standard", "airy"):
        must.append(f"density「{meta['density']}」不存在：dense / standard / airy（必须修正）")

    return must, should


def evidence(meta, blocks, base="."):
    """只报告需对照的结构/资产与数据状态，不推测阅读质量。"""
    kinds = [k for k, _ in blocks]
    imgs = [b for k, b in blocks if k == "img"]
    out = [f"结构 · {doc_len(blocks)}字 · H2 {kinds.count('h2')} · 引文 {kinds.count('quote')} · peak {kinds.count('peak')}"]
    for alt, src, role in imgs:
        out.append(f"资产 · {src or 'todo'} · {(role or '').strip() or '职责缺失'} · {alt}")
    for i, (k, b) in enumerate(blocks):
        if k in ("bars", "data"):
            note = blocks[i + 1][1] if i + 1 < len(blocks) and blocks[i + 1][0] == "note" else ("", [])
            out.append(f"图示 · {k} · {b[0]} · {len(b[1])}项 · {note[0] or '来源待补'}（声明不等于核真）")
    out.append("复核 · 正文、图注与来源的阅读连续性；封面两裁切与素材授权见预览")
    return out


PREVIEW = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{margin:0;background:#EDEDEB;font-family:-apple-system,'PingFang SC',sans-serif}}
.bar{{display:flex;justify-content:space-between;align-items:center;padding:10px 16px;
background:#fff;border-bottom:1px solid #e5e5e5;font-size:12px;color:#888;}}
button{{border:0;background:#1F1F1F;color:#fff;padding:8px 16px;border-radius:6px;font-size:13px;cursor:pointer}}
.phone{{position:relative;max-width:390px;margin:24px auto 64px;background:#fff;padding:24px 16px 48px;box-sizing:border-box}}
.nt{{padding:2px 2px 16px;margin-bottom:22px;border-bottom:1px solid #EDEDEB}}
.nt h1{{margin:0 0 8px;font-size:22px;line-height:1.4;font-weight:700;color:#191919}}
.nt .au{{margin:0;font-size:13px;color:#6B6762}}
.cv{{max-width:390px;margin:24px auto 0;background:#fff;padding:16px;box-sizing:border-box}}
.cv h4{{margin:0 0 8px;font-size:12px;color:#746F66;font-weight:600}}
.cv img{{display:block;width:100%;background:#F0EEE9}}
.as{{margin-top:14px;padding-top:12px;border-top:1px solid #EFEDE9}}
.as img{{display:block;width:100%;background:#F0EEE9}}
.hint{{margin:16px 0 0;font-size:12px;line-height:1.7;color:#746F66}}</style></head>
<body><div class="bar"><span>{theme} · 390px</span><button onclick="cp(this)">复制正文（图片另传）</button></div>
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
        sys.exit(f"未知主题 {key}，可选：{', '.join(THEMES)}")
    r = R(THEMES[key], meta.get("density", "standard"))
    out, n = [], 0
    if meta.get("deck"):
        out.append(f'<section style="margin-bottom:{r.g(24)}px;">{r.p(r.inline(meta["deck"]), BODY, r.t["sub"])}</section>')
    heads = [b[1] for b in blocks if b[0] == "h2"]
    toc_done = meta.get("toc", "").lower() not in ("true", "yes", "1") or len(heads) < 3
    # 目录只在首段后，顺序由源稿决定。
    toc_after_p, seen_p = any(k == "p" for k, _ in blocks), False
    for kind, b in blocks:
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
            out.append(r.note(*b))
        elif kind == "data":
            out.append(r.data(b[1]))
        elif kind == "bars":
            out.append(r.bars(b[1], b[0]))
        elif kind == "table":
            out.append(r.table(b))
        elif kind == "list":
            out.append(r.lst(*b))
        elif kind == "code":
            out.append(r.code(*b))
        elif kind == "img":
            out.append(r.img(*b))
        elif kind == "hr":
            out.append(r.hr())
        else:
            sys.exit(f"未知原语 ::: {kind}（可用：peak / note / data / bars）")
    out.append(r.signature(meta))
    t = THEMES[key]
    body = (f'<section style="font-family:{SANS};font-size:{BODY}px;color:{t["text"]};line-height:{t["leading"]};'
            f'letter-spacing:normal;text-align:left;line-break:strict;overflow-wrap:anywhere;">' + "".join(out) + "</section>")
    return key, meta, blocks, body


SPECIMEN_MD = """---
title: 留下的东西|比发出去的更重要
author: 甲木
bio: 气候对照用样张
---

> 一篇文章的气质，不在配色，而在什么被允许发出声音。

## 判断在主题之前

主题是人格，不是皮肤。同一段文字，换人格，节奏应跟着变；若只换了色，判断没有发生。

> 能不用就不用，能弱化就弱化。

## 视觉权重服从信息权重

正文永远是最安静的一层，标记只留给真正需要停顿的地方。

::: data
01｜可删元素
01｜可弱化层级
01｜可取消装饰
:::

::: note 演示
样张计数仅演示data原语，非统计。
:::

::: peak
克制不是少，是每一处都有职责。
:::
"""

SPECIMEN_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Six Editorial Modes</title>
<style>*{{box-sizing:border-box}}
body{{margin:0;background:#D8D3CA;color:#2B2824;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC","Hiragino Sans GB",sans-serif}}
header{{padding:56px 40px 12px}}
.k{{font-size:11px;letter-spacing:2.4px;font-weight:600;color:#8A847A}}
h1{{font-size:28px;font-weight:600;letter-spacing:.4px;margin:10px 0 8px;line-height:1.3}}
.lede{{font-size:14px;color:#6E6860;line-height:1.7;max-width:560px;margin:0}}
.board{{display:flex;gap:32px;overflow-x:auto;padding:28px 40px 88px;align-items:flex-start}}
.col{{flex:0 0 390px}}
.name{{font-size:13px;font-weight:600;letter-spacing:.3px}}
.swatches{{display:flex;gap:7px;margin:12px 0 16px}}
.sw{{display:block;width:16px;height:16px;border-radius:50%;box-shadow:inset 0 0 0 1px rgba(40,30,20,.12)}}
.phone{{background:#fff;padding:28px 18px 48px;border:1px solid #D6D0C5}}</style>
</head><body>
<header><div class="k">EDITORIAL MODES · 生成物，勿手改（render.py --specimen）</div>
<h1>六种编辑人格，不是六套配色</h1>
<p class="lede">同一篇样张，六种气候。用途与判断见 SKILL.md；此板用来目视对照与主题回归。</p></header>
<div class="board">
{cols}
</div></body></html>
"""


def specimen(path):
    """六格对照板由真实渲染器生成，避免与人手维护的样本漂移。入库 assets/themes.html，--specimen 重新生成。"""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    cols = []
    for key, t in THEMES.items():
        _, _, _, body = render(SPECIMEN_MD, key)
        sw = "".join(f'<i class="sw" style="background:{t[k]}"></i>' for k in ("text", "field", "accent", "line", "dark"))
        cols.append(f'<div class="col"><div class="name">{t["name"]}</div>'
                    f'<div class="swatches">{sw}</div><div class="phone">{body}</div></div>')
    open(path, "w", encoding="utf-8").write(SPECIMEN_HTML.format(cols="".join(cols)))
    print(f"气候对照板 → {path}（对照用，不进公众号）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md", nargs="?")
    ap.add_argument("--theme", choices=list(THEMES))
    ap.add_argument("-o", "--out")
    ap.add_argument("--specimen", action="store_true", help="生成六格气候对照板")
    a = ap.parse_args()
    if a.specimen:
        specimen(a.out or os.path.join(HERE, "..", "assets", "themes.html"))
        return
    if not a.md:
        ap.error("需要一个 markdown 文件，或使用 --specimen")
    base = os.path.dirname(os.path.abspath(a.md))
    key, meta, blocks, body = render(open(a.md, encoding="utf-8").read(), a.theme)
    out = a.out or f"{os.path.splitext(a.md)[0]}_{key}.html"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    out_base = os.path.dirname(os.path.abspath(out))
    def output_src(src):
        if not src or TODO.match(src) or re.match(r"^(?:[a-z][a-z0-9+.-]*:|//)", src, re.I):
            return src
        return os.path.relpath(resolve(src, base), out_base).replace(os.sep, "/")
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
                       assets=asset_sheet([(k, (b[0], output_src(b[1]), b[2])) if k == "img" else (k, b) for k, b in blocks], out_base),
                       native=native, body=body)
    preview = re.sub(r'(<img\b[^>]*src=")([^"]+)(")',
                     lambda m: m[1] + H.escape(preview_image(H.unescape(m[2]), out_base)) + m[3]
                     + ' data-local="' + m[2] + '"', preview)
    open(prev, "w", encoding="utf-8").write(preview)
    # 发布字段 sidecar：publish.py --meta 直接消费，保证草稿原生字段与预览所见一致。
    cover = (meta.get("cover") or "").strip()
    m1, s1 = check(body)
    m2, s2 = compose_gate(meta, blocks, base)
    side = {
        "title": meta.get("title", ""),
        "api_title": api_title(meta.get("title", "")),
        "author": (meta.get("author") or ""),
        "digest": meta.get("digest") or auto_digest(meta, blocks),
        "cover": "" if (not cover or TODO.match(cover)) else output_src(cover),
        "source_url": meta.get("source", ""),
        "theme": key,
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "render_errors": m1 + m2,
        "pending_assets": any(not b[1] or TODO.match(b[1]) for k, b in blocks if k == "img"),
    }
    meta_path = os.path.splitext(out)[0] + ".meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(side, f, ensure_ascii=False, indent=2)
    print(f"{THEMES[key]['name']} → {out}\n预览 → {prev}\n发布字段 → {meta_path}（publish.py --meta 直接消费）\n")
    print("\nGate 3 证据（可核对的都摆在这里；结论与艺术判断由通读的人 / 视觉模型给）")
    for line in evidence(meta, blocks, base):
        print("  " + line)
    for gate, must, should in (("Gate 1 Platform", m1, s1), ("Gate 2 Composition", m2, s2)):
        print(f"\n{gate}: {'FAIL' if must else 'PASS'}")
        for x in must:
            print("  必须改 ·", x)
        for x in should:
            print("  建议改 ·", x)
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
