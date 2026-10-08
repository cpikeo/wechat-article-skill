#!/usr/bin/env python3
"""Composed Markdown → 公众号 HTML + 390px 预览 + Gate 1/2（一次调用）。

    render.py article.md [--theme paper|letter|ink|frost|bone|folio] [-o out.html]
    render.py --specimen [-o shots/themes.html]       六格气候对照板（生成物，不进公众号）

产出 {stem}_{theme}.html 与 {stem}_{theme}_预览.html（预览另含封面两种裁切与首屏线）。
语法见 SKILL.md。退出码 1 = 存在「必须改」。
设计规则在 SKILL.md / references/*；本文件只执行可确定的子集。
"""
import argparse
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
SANS = "-apple-system,BlinkMacSystemFont,'PingFang SC','Hiragino Sans GB','Microsoft YaHei',sans-serif"
SERIF = "'Songti SC','STSong','SimSun',serif"
MONO = "'SF Mono',Menlo,Consolas,monospace"
CJK = "\u4e00-\u9fff\u3400-\u4dbf"
# 6 级字号，主题不得再发明
MICRO, SMALL, BODY, LEAD, DISPLAY, TITLE = 11, 13, 15, 17, 20, 24

# 正文视觉职责（封面单独由 frontmatter 承担）。说不出职责 → 删。
ROLES = {"锚点", "解释", "证据", "对比", "结构", "场景", "隐喻", "停顿", "数据",
         "anchor", "explain", "evidence", "compare", "structure", "context", "metaphor", "rhythm", "data"}
QUIET = {"停顿", "隐喻", "rhythm", "metaphor"}                       # 图片前后留白更大
FACT = {"解释", "证据", "对比", "结构", "数据",
        "explain", "evidence", "compare", "structure", "data"}       # 说明用正文色、字号大一级
TODO = re.compile(r"(?i)^(todo|待补)")
COVER_RATIO = 2.35                    # 封面目标比例（微信首图）
COVER_BAND = (1.6, 3.0)               # 可接受区间；超出说明这不是一张封面
COVER_MIN_W = 900                     # 下方会被裁，再窄就糊

BR = '<span leaf=""><br></span>'
INLINE = re.compile(r"`([^`]+)`|==(.+?)==|\*\*(.+?)\*\*|<u>(.+?)</u>|~~(.+?)~~|\[([^\]]+)\]\(([^)\s]+)\)")
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def typo(s):
    """中文语境：半角标点→全角、直引号→弯引号。代码与链接在外层保护。"""
    if not re.search(f"[{CJK}]", s):
        return s
    s = re.sub(f"(?<=[{CJK}])([,;:!?])|(?<=[A-Za-z0-9])([,;!?])\\s*(?=[{CJK}])",
               lambda m: "，；：！？"[";,;:!?".index(m.group(1) or m.group(2))], s)
    s = s.replace("...", "……")
    q = iter(["“", "”"] * 200)
    return re.sub(r'"', lambda m: next(q), s)


def parse(md):
    meta, blocks = {}, []
    m = re.match(r"^---\n(.*?)\n---\n", md, re.S)
    if m:
        for ln in m.group(1).splitlines():
            if ":" in ln:
                k, v = ln.split(":", 1)
                # 行内注释（# 前须有空白，不伤 URL fragment）；文档样张带注释，照抄不能炸
                v = re.sub(r"\s+#.*$", "", v)
                meta[k.strip()] = v.strip()
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
            blocks.append(("code", (lang, body)))
        elif s.startswith(":::") and len(s) > 3:
            flush()
            kind, _, arg = s[3:].strip().partition(" ")
            body = []
            i += 1
            while i < len(lines) and lines[i].strip() != ":::":
                body.append(lines[i].strip())
                i += 1
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
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
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

    def inline(self, s):
        t, out, pos = self.t, [], 0
        keep = {}

        def protect(m):
            keep[f"\x00{len(keep)}\x00"] = m.group(0)
            return f"\x00{len(keep) - 1}\x00"
        s = typo(re.sub(r"`[^`]+`|\[[^\]]+\]\([^)\s]+\)", protect, s))
        for k, v in keep.items():
            s = s.replace(k, v)
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
                out.append(f'<strong style="font-weight:600;color:{t["text"]};">{self.leaf(bold)}</strong>')
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
        ls = "" if "letter-spacing" in extra else "letter-spacing:0.5px;"
        return (f'<p style="margin:0;font-size:{size}px;{lh}color:{color or self.t["text"]};'
                f'{ls}{extra}">{inner}</p>')

    def micro(self, s, color=None, extra=""):
        return self.p(self.leaf(s), MICRO, color or self.t["muted"], f"letter-spacing:2px;font-weight:600;{extra}")

    def rule(self, w=24, h=1, color=None, center=True, below=0):
        pos = f"margin:0 auto {below}px;" if center else "flex-shrink:0;"
        return f'<section style="width:{w}px;height:{h}px;background:{color or self.t["line"]};{pos}">{BR}</section>'

    def seal(self, glyph, size=24, color=None):
        return (f'<span style="display:inline-block;width:{size}px;height:{size}px;line-height:{size - 2}px;'
                f'border:1px solid {self.t["muted"]};border-radius:50%;text-align:center;font-size:{MICRO}px;'
                f'font-weight:600;color:{color or self.t["text"]};box-sizing:border-box;">{self.leaf(glyph)}</span>')

    def masthead(self, meta, minutes):
        """正文开头只放 kicker / deck / 日期行。title 是平台原生字段（草稿标题栏），
        正文里再印一遍 = 读者看到两个标题；断行标记 | 只服务原生标题的排版意图。"""
        t, out = self.t, []
        kicker = meta.get("kicker", t["kicker"])
        if t["seal"]:
            out.append(f'<section style="display:flex;align-items:center;gap:10px;">'
                       f'{self.seal(meta.get("seal", t["seal"]))}{self.micro(kicker)}</section>')
        else:
            out.append(self.micro(kicker))
        if meta.get("deck"):
            out.append(self.p(self.inline(meta["deck"]), BODY, t["sub"], "margin-top:12px;"))
        info = " · ".join(x for x in (meta.get("date"), f"约 {minutes} 分钟阅读") if x)
        out.append(f'<section style="display:flex;align-items:center;gap:10px;margin-top:18px;">'
                   f'{self.rule(20, 1, t["muted"], False)}{self.p(self.leaf(info), MICRO, t["muted"])}</section>')
        return f'<section style="padding-top:4px;">{"".join(out)}</section>' + \
            f'<section style="height:1px;background:{t["line"]};margin-top:{self.g(24)}px;">{BR}</section>'

    def h2(self, text, n):
        t, ending = self.t, re.search(r"结语|尾声|写在最后|后记", text)
        title = self.p(self.inline(text), DISPLAY, t["text"],
                       f"font-weight:700;line-height:1.5;letter-spacing:1px;font-family:{self.font};")
        if t["heading"] == "dot":
            mark = (f'<section style="width:6px;height:6px;border-radius:50%;background:{t["muted"]};'
                    f'margin-bottom:14px;">{BR}</section>')
        elif ending:
            mark = self.micro("—", extra="margin-bottom:10px;")
        elif t["heading"] == "seal":
            mark = f'<section style="margin-bottom:12px;">{self.seal(f"{n:02d}", 26)}</section>'
        elif t["heading"] == "blank":
            mark = ""
        else:
            mark = self.micro(f"{n:02d}", extra="margin-bottom:10px;")
        return f'<section style="margin:{self.g(56)}px 0 {self.g(20)}px;">{mark}{title}</section>'

    def h3(self, text):
        return f'<section style="margin:{self.g(28)}px 0 {self.g(12)}px;">' + \
            self.p(self.inline(text), BODY, self.t["text"], "font-weight:700;") + "</section>"

    def para(self, text):
        return f'<section style="margin:0 0 {self.g(20)}px;">' + \
            self.p(self.inline(text), extra=f"text-align:{align(text)};") + "</section>"

    def quote(self, text, src, weight):
        """lead / quote / peak 同一原语，三种重量。只有 Peak 居中——避免两个高潮互抢。"""
        t = self.t
        serif = t["quote"] == "serif"
        if serif and weight != "lead" and not text.startswith("「"):
            text = f"「{text}」"
        if weight == "lead":
            return f'<section style="margin:{self.g(28)}px 0 {self.g(36)}px;">' + \
                self.p(self.inline(text), LEAD, t["text"],
                       f"line-height:1.85;letter-spacing:0.8px;font-family:{self.font};") + "</section>"
        fam = f"font-family:{SERIF};" if serif else ""
        if weight == "quote":
            cite = self.p(self.leaf(f"—— {src}"), MICRO, t["muted"],
                          "margin-top:12px;letter-spacing:1px;") if src else ""
            return (f'<section style="margin:{self.g(36)}px 0;padding:0 4px 0 12px;'
                    f'border-left:1px solid {t["line"]};">'
                    + self.p(self.inline(text), LEAD, t["sub"], f"font-weight:500;line-height:1.8;{fam}")
                    + cite + "</section>")
        style = t["peak"]
        body_color = t["on_dark"] if style == "dark" else t["text"]
        claim = self.p(self.inline(text), DISPLAY, body_color,
                       f"font-weight:600;line-height:1.65;letter-spacing:1px;{fam}")
        top = self.rule(24, 2, t["accent"], below=20)
        if style == "rule":
            box = f"padding:{self.g(8)}px 8px;"
        elif style == "field":
            box = f"padding:{self.g(32)}px 20px;background:{t['field']};border-radius:{t['radius']}px;"
        else:
            box, top = f"padding:{self.g(40)}px 20px;background:{t['dark']};border-radius:{t['radius']}px;", ""
        return f'<section style="margin:{self.g(52)}px 0;text-align:center;{box}">{top}{claim}</section>'

    def note(self, label, lines):
        t = self.t
        head = self.micro(label, extra="margin-bottom:6px;") if label else ""
        body = "".join(self.p(self.inline(x), SMALL, t["sub"], "line-height:1.8;") for x in lines)
        return (f'<section style="margin:{self.g(24)}px 0;padding:2px 0 2px 14px;'
                f'border-left:2px solid {t["line"]};">{head}{body}</section>')

    def data(self, lines):
        # 全角「｜」与半角「|」都要能拆：中文输入法默认给的是全角，
        # 只按半角拆会把「3｜标签」整条当成数值，标签消失、大字号里挤进一整句。
        t, rows, items = self.t, [], [x.replace("|", "｜").split("｜", 1) for x in lines]
        per = len(items) if 0 < len(items) <= 3 else 2
        for i in range(0, len(items), per):
            cells = "".join(
                f'<section style="flex:1;padding-top:12px;border-top:1px solid {t["text"]};">'
                + self.p(self.leaf(v.strip()), TITLE, t["text"],
                         f"font-weight:600;line-height:1.3;font-family:{self.font};")
                + self.p(self.inline(lab.strip() if lab else ""), MICRO, t["muted"],
                         "margin-top:6px;letter-spacing:1px;")
                + "</section>" for v, *rest in items[i:i + per] for lab in [rest[0] if rest else ""])
            rows.append(f'<section style="display:flex;gap:16px;margin-top:{16 if i else 0}px;">{cells}</section>')
        return f'<section style="margin:{self.g(36)}px 0;">{"".join(rows)}</section>'

    def bars(self, lines):
        """数量对比图：值｜标签。数值同时以文字给出——即使长度表达失效，信息也不丢。"""
        t, rows, items = self.t, [], []
        for ln in lines:
            val, _, lab = ln.replace("|", "｜").partition("｜")
            items.append((val.strip(), lab.strip()))
        try:
            mx = max(float(v) for v, _ in items)
        except ValueError:
            mx = 0
        for val, lab in items:
            w = max(2, round(float(val) / mx * 100)) if mx else 0
            rows.append(
                f'<section style="display:flex;align-items:flex-end;gap:10px;margin-top:{self.g(16)}px;">'
                + self.p(self.inline(lab), SMALL, t["sub"], "flex:1;")
                + self.p(self.leaf(val), BODY, t["text"], f"font-weight:600;font-family:{self.font};")
                + "</section>"
                + f'<section style="height:5px;background:{t["line"]};margin-top:6px;">'
                + f'<section style="width:{w}%;height:5px;background:{t["accent"]};">{BR}</section></section>')
        return f'<section style="margin:{self.g(32)}px 0;">{"".join(rows)}</section>'

    def table(self, rows):
        t, out = self.t, []
        for r, cells in enumerate(rows):
            head = r == 0
            line = t["sub"] if head else t["line"]
            out.append(f'<section style="display:flex;gap:12px;padding:{8 if head else 12}px 0;border-bottom:1px solid {line};">'
                       + "".join(f'<section style="flex:1;">' + (
                           self.micro(c) if head else self.p(self.inline(c), SMALL, t["text"], "line-height:1.7;"))
                           + "</section>" for c in cells) + "</section>")
        return f'<section style="margin:{self.g(28)}px 0;">{"".join(out)}</section>'

    def lst(self, ordered, items):
        t, out = self.t, []
        for n, it in enumerate(items, 1):
            mk = (self.p(self.leaf(f"{n:02d}"), SMALL, t["muted"], "font-weight:600;") if ordered
                  else self.p(self.leaf("·"), BODY, t["muted"], "font-weight:700;"))
            out.append(f'<section style="display:flex;margin-bottom:{self.g(10)}px;">'
                       f'<section style="width:{28 if ordered else 18}px;flex-shrink:0;padding-top:{2 if ordered else 0}px;">{mk}</section>'
                       f'<section style="flex:1;">{self.p(self.inline(it))}</section></section>')
        return f'<section style="margin:{self.g(8)}px 0 {self.g(22)}px;">{"".join(out)}</section>'

    def code(self, lang, body):
        t = self.t
        rows = "".join(
            f'<p style="margin:0;font-family:{MONO};font-size:{SMALL}px;line-height:1.7;color:{t["text"]};">'
            + (self.leaf(re.sub(r"^( +)", lambda m: "\u3000" * math.ceil(len(m.group(1)) / 2), ln)) if ln.strip() else BR)
            + "</p>" for ln in body)
        label = self.micro(lang.upper(), extra=f"margin-bottom:10px;font-family:{MONO};") if lang else ""
        return (f'<section style="margin:{self.g(24)}px 0;padding:16px 18px;background:{t["field"]};'
                f'border-radius:{t["radius"]}px;">{label}{rows}</section>')

    def img(self, alt, src, role):
        t = self.t
        role0 = (role or "").split()[0]
        mt = self.g(44 if role0 in QUIET else 32)
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
                f'<img src="{H.escape(src)}" style="max-width:100%;height:auto;display:block;margin:0 auto;{extra}" />'
                + (self.p(self.leaf(typo(cap)), cap_size, cap_color, "margin-top:10px;letter-spacing:1px;") if cap else "")
                + "</section>")

    def hr(self):
        t, kind = self.t, self.t["divider"]
        inner = (self.seal("·", 20, t["muted"]) if kind == "seal" else self.rule(32) if kind == "rule"
                 else self.p(self.leaf("· · ·"), SMALL, t["muted"], "letter-spacing:8px;"))
        return f'<section style="margin:{self.g(44)}px 0;text-align:center;">{inner}</section>'

    def signature(self, meta):
        """收束只留 cta + bio。author 与 title 一样是平台原生字段（标题下作者栏），
        文末再印一遍作者名 = 草稿里上下各出现一次（线上事故实测）。bio 不是原生字段，可以留。"""
        t, out = self.t, []
        if meta.get("cta"):
            out.append(self.p(self.inline(meta["cta"]), SMALL, t["sub"], "margin-bottom:28px;"))
        if meta.get("bio"):
            out.append(f'<section style="text-align:center;">{self.seal(meta.get("seal", t["seal"]))}</section>'
                       if t["seal"] else self.rule(24))
            out.append(self.p(self.leaf(typo(meta["bio"])), MICRO, t["muted"], "margin-top:16px;letter-spacing:1px;"))
        if not out:
            return ""
        return f'<section style="margin-top:{self.g(56)}px;text-align:center;">{"".join(out)}</section>'

    def toc(self, heads):
        t = self.t
        rows = "".join(self.p(self.leaf(f"{n:02d}　{h}"), SMALL, t["text"], "line-height:2.1;")
                       for n, h in enumerate(heads, 1))
        return (f'<section style="margin:0 0 {self.g(36)}px;padding:16px 0;border-top:1px solid {t["line"]};'
                f'border-bottom:1px solid {t["line"]};">{self.micro(t["toc_label"], extra="margin-bottom:10px;")}{rows}</section>')


def align(s):
    """两端对齐只用于纯中文；中西混排改左对齐，避免字距河流。"""
    return "left" if len(re.findall(r"[A-Za-z]{2,}", s)) >= 2 else "justify"


def visible_len(s):
    return len(re.sub(r"</?u>|https?://\S+|[`*=~\[\]()]", "", s))


def api_title(t):
    """平台原生标题栏用的标题：frontmatter 的 | 是正文断行标记，
    原生标题栏里必须转成全角｜，否则半角管道会原样挤进标题（草稿标题与正文各印一遍标题的根因之一）。"""
    return t.replace("|", "｜").strip()


def plain(s):
    """剥掉行内语法，得到读者可见的纯文本（供摘要等原生字段复用）。"""
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)          # 链接留文字
    s = re.sub(r"`([^`]*)`|==([^=]*)==|\*\*([^*]*)\*\*|<u>([^<]*)</u>|~~([^~]*)~~",
               lambda m: next(g for g in m.groups() if g is not None), s)
    return s.strip()


def auto_digest(meta, blocks, limit=120):
    """摘要兜底：lead > deck > 首段。官方上限 120 字（2026-07-14 对齐 mp 端）。
    不能让微信自己抓正文前 54 字——正文开头是 kicker / 日期行，抓出来不是摘要。"""
    src = next((b[0] for k, b in blocks if k == "lead"), "") \
        or meta.get("deck", "") \
        or next((b for k, b in blocks if k == "p"), "")
    return plain(src)[:limit]


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


def asset_budget(chars):
    """Image Budget：先定上限，再取素材。封面单列，不占这张预算。"""
    return 1 if chars <= 800 else 3 if chars <= 2000 else 4


def first_screen(meta, blocks):
    """首屏实际压了几层：读者第一屏看到的是钩子，还是目录与素材。"""
    kinds = [b[0] for b in blocks]
    stop = next((i for i, k in enumerate(kinds) if k == "p"), len(kinds))
    layers = [k for k in kinds[:stop] if k in {"lead", "img", "note", "data", "bars", "table", "quote"}]
    if meta.get("deck"):
        layers.insert(0, "deck")
    if meta.get("toc", "").lower() in ("true", "yes", "1") and len([b for b in blocks if b[0] == "h2"]) >= 3:
        layers.append("toc")
    return layers


def compose_gate(meta, blocks, base="."):
    """Gate 2：可确定的结构与资产检查。审美判断留给 Gate 3。"""
    must, should = [], []
    kinds = [b[0] for b in blocks]
    peaks = kinds.count("peak")
    if peaks > 1:
        must.append(f"Visual Peak 出现 {peaks} 次：高潮只能有一个")
    if peaks == 0:
        should.append("没有 ::: peak —— 确认全文确实不存在值得成为高潮的 Core Claim")
    for k, b in blocks:
        if k == "peak" and visible_len(peak_text(b)) > 48:
            should.append("Peak 超过一句：高潮应是 Claim，不是段落")
    paras = [b[1] for b in blocks if b[0] == "p"]
    marks = sum(len(re.findall(r"==.+?==|<u>.+?</u>", p)) for p in paras)
    emph = sum(1 for p in paras if re.search(r"==|\*\*|<u>", p))
    if marks > 3:
        should.append(f"==标记== {marks} 处（>3）：强调稀缺才有价值，降级为字重或删除")
    if paras and emph / len(paras) > 0.35:
        should.append(f"{emph}/{len(paras)} 段带强调：已接近机械装饰，多数段落应完全不强调")
    imgs = [(i, b[1]) for i, b in enumerate(blocks) if b[0] == "img"]
    roles = []
    for _, (alt, src, role) in imgs:
        if not role:
            must.append(f"图片「{alt or src}」没有声明职责：说不出为什么存在就删除")
            continue
        # 证据 / 解释 / 对比 / 结构 / 数据 这几类图没有说明，读者无法核对 → 等于装饰。
        if role.split()[0] in FACT and not (alt or "").strip():
            should.append(f"图片「{src or 'todo'}」职责是「{role}」却没有说明：证据类图必须写清出处 / 口径 / 时间")
        if role.split()[0] not in ROLES:
            should.append(f"图片职责「{role}」不在标准集合：锚点/解释/证据/对比/结构/场景/隐喻/停顿/数据")
        roles.append(role.split()[0])
    for r in sorted(set(roles)):
        if roles.count(r) >= 3:
            should.append(f"「{r}」职责出现 {roles.count(r)} 次：同一职责最多两次，否则是在凑数")
    # 预算算的是「计划」而不是「已存在」：todo 也是要花预算的图位，不是免费位。
    chars = doc_len(blocks)
    cap = asset_budget(chars)
    if len(imgs) > cap:
        should.append(f"{len(imgs)} 张正文图 > 本文字数档位的预算 {cap}：删到只剩改变阅读体验的那几张")
    for _, (alt, src, role) in imgs:
        if not src or TODO.match(src):
            continue
        p = resolve(src, base)
        if not os.path.exists(p):
            must.append(f"图片不存在：{src}（本地化后再交付，或写成 todo）")
            continue
        wh, kb = img_size(p), os.path.getsize(p) // 1024
        if wh:
            w, h = wh
            name = os.path.basename(src)
            for bad, level, why in ((min(w, h) < 600, must, "分辨率过低，手机上一定糊"),
                                    (min(w, h) < 800, should, "短边 <800px，压缩或重出"),
                                    (w >= h and w < 1200, should, "正文图宽建议 ≥1200px")):
                if bad:
                    level.append(f"{name} {w}×{h}：{why}")
                    break
        if kb > 1024:
            should.append(f"{os.path.basename(src)} 体积 {kb}KB：压到 1MB 以内再发布")
    cover = (meta.get("cover") or "").strip()
    if not cover:
        should.append(f"没有封面：公众号需要一张 {COVER_RATIO}:1 封面（方向见 references/direction.md「封面工艺」）")
    elif not TODO.match(cover):
        p = resolve(cover, base)
        if not os.path.exists(p):
            must.append(f"封面文件不存在：{cover}")
        else:
            wh = img_size(p)
            if wh:
                w, h = wh
                ratio = w / h
                if w < COVER_MIN_W:
                    should.append(f"封面 {w}×{h}：首图会糊，宽度至少 {COVER_MIN_W}px")
                if not COVER_BAND[0] <= ratio <= COVER_BAND[1]:
                    should.append(f"封面 {w}×{h}（{ratio:.2f}:1）：微信会裁成 {COVER_RATIO}:1，确认主体在中央安全区，"
                                  f"不要靠烧字补意思")
    for k, b in blocks:
        if k != "bars":
            continue
        items = [(v.strip(), lab.strip()) for v, _, lab in (x.replace("|", "｜").partition("｜") for x in b[1])]
        nums = []
        for v, lab in items:
            if not re.fullmatch(r"\d+(\.\d+)?", v):
                must.append(f"bars 的值必须是数字：{v or '（空）'}")
            else:
                nums.append(float(v))
            if not lab:
                should.append(f"bars 的 {v} 缺少标签：数值没有口径等于没有信息")
        if len(items) < 2:
            must.append("bars 至少 2 项：单项对比不成立，直接用文字")
        elif len(items) > 6:
            should.append(f"bars {len(items)} 项：手机上超过 6 行就失去对比意义")
        elif nums and max(nums) / (min(nums) or 1) < 1.3:
            should.append("bars 各项数值接近：长度表达不出差异，改回文字或表格")
    # 同一件事的三条阈值集中成一张表：数一数就够，不必各写一段话。
    for k, cap, why in (("note", 2, "旁注过多，优先删除而不是换样式"),
                        ("hr", 2, "章节标题已经是停顿，--- 能少则少"),
                        ("quote", 3, "他者声音过多会变成第二个节奏")):
        if kinds.count(k) > cap:
            should.append(f"{kinds.count(k)} 处 {k}：{why}")
    heavy = {"quote", "peak", "note", "data", "bars", "table", "code", "img"}
    run = 0
    for i, k in enumerate(kinds):
        run = run + 1 if k in heavy else 0
        if run == 3:
            should.append(f"第 {i - 1}-{i + 1} 块连续三个非正文原语：至少让一段文字回来呼吸")
        if k in ("h2", "h3") and i + 1 < len(kinds) and kinds[i + 1] in ("h2", "h3"):
            should.append("标题后紧跟标题：中间缺少正文")
        if k == "peak" and {kinds[j] for j in (i - 1, i + 1) if 0 <= j < len(kinds)} & {"quote", "data"}:
            should.append("Peak 紧邻 quote/data：两个停顿叠在一起会稀释高潮")
        if k == "h2" and EMOJI.search(blocks[i][1]):
            should.append("标题含 emoji：结构图标只用文字/数字/几何")
        if k == "table" and blocks[i][1] and len(blocks[i][1][0]) > 3:
            should.append("表格超过 3 列：手机上会碎，拆表或改成 data")
    for (a, _), (b, _) in zip(imgs, imgs[1:]):
        if sum(visible_len(blocks[k][1]) for k in range(a + 1, b) if blocks[k][0] == "p") < 40:
            should.append("两张图片之间缺少文字承接：合并、删减或补一段过渡")
    heavies = sum(1 for k in kinds if k in heavy)
    if heavies > 6:
        should.append("非正文原语偏多：先问哪一个可以消失，再考虑增加")
    run = 0
    for k, b in blocks:
        run = run + visible_len(b) if k == "p" else 0
        if run > 1400:
            should.append("连续 1400+ 字纯正文：确认是刻意的沉浸段，否则考虑一次停顿")
            run = -10 ** 9
    for p in paras:
        if visible_len(p) > 180:
            should.append(f"段落 {visible_len(p)} 字：「{p[:14]}…」手机上超过 8 行，在语义断点拆开")
    title = meta.get("title", "")
    if not title:
        must.append("缺少标题")
    elif len(title) > 15 and "|" not in title:
        should.append("标题 >15 字且未指定断行：用 | 在语义处断开，避免由屏宽决定断点")
    if "lead" not in kinds and not meta.get("deck"):
        should.append("首屏没有 lead / deck：读者凭什么继续往下读？")
    if meta.get("deck") and "lead" in kinds:
        should.append("deck 与 lead 同时出现：首屏两个钩子，留一个")
    if meta.get("density", "standard") not in ("dense", "standard", "airy"):
        should.append(f"density「{meta['density']}」不存在：dense / standard / airy（写错会静默按 standard 执行）")

    # 证据类图片没有说明 = 无法核对 = 装饰。
    # 封面顺手用正文图：封面要讲主张，不是配图。
    if cover and not TODO.match(cover) and any(
            os.path.basename(b[1][1]) == os.path.basename(cover) for b in blocks if b[0] == "img" and b[1][1]):
        should.append("封面与正文图是同一张：封面必须独立做 art direction")
    # 图示把正文数字又画一遍 = 信息增量 ≈ 0。
    for i, (k, b) in enumerate(blocks):
        if k != "bars":
            continue
        near = " ".join(p for kk, p in blocks[max(0, i - 2):i + 3] if kk == "p")
        dup = sorted(v for v, _, _ in (x.replace("|", "｜").partition("｜") for x in b[1])
                     if v and re.search(rf"(?<!\d){re.escape(v.strip())}(?!\d)", near))
        if dup:
            should.append(f"图示数字与正文重复（{'、'.join(dup)}）：正文只留关系，数字交给图示")
    # 首屏：短文开目录，第一屏就只剩目录。
    heads = [b[1] for b in blocks if b[0] == "h2"]
    if meta.get("toc", "").lower() in ("true", "yes", "1") and len(heads) >= 3:
        if chars < 1600 or len(heads) < 4:
            should.append(f"{chars} 字 / {len(heads)} 节的短文开了目录：首屏被目录占掉，正文被推到折线以下")
    layers = first_screen(meta, blocks)
    if len(layers) >= 3:
        should.append(f"首屏压了 {len(layers)} 层（{'/'.join(layers)}）：第一屏只留钩子，其余下移")
    return must, should


def evidence(meta, blocks, base="."):
    """Gate 3 的证据：能核对的数字与条目。艺术判断交给通读的人 / 视觉模型。"""
    kinds = [b[0] for b in blocks]
    paras = [b[1] for b in blocks if b[0] == "p"]
    imgs = [b[1] for b in blocks if b[0] == "img"]
    chars = doc_len(blocks)
    heads = [b[1] for b in blocks if b[0] == "h2"]
    out = []
    cover = (meta.get("cover") or "").strip()
    wh = None if (not cover or TODO.match(cover)) else img_size(resolve(cover, base))
    cover_txt = "无" if not cover else (f"{wh[0]}×{wh[1]}（{wh[0] / wh[1]:.2f}:1）" if wh else "待补")
    roles = [b[1][2].split()[0] for b in blocks if b[0] == "img" and b[1][2]]
    holds = sum(1 for b in imgs if not b[1] or TODO.match(b[1]))
    out.append(f"资产 · 全文 {chars} 字 · 封面 {cover_txt} · 正文图 {len(imgs)}/{asset_budget(chars)}（预算）"
               + (f"：{'、'.join(roles)}" if roles else "") + (f" · 待补位 {holds}" if holds else ""))
    layers = first_screen(meta, blocks)
    stop = next((i for i, k in enumerate(kinds) if k == "p"), len(kinds))
    out.append(f"首屏 · 标题 + {'/'.join(layers) if layers else '无附加层'}；首段落在第 {stop + 1} 块")
    idx = [i for i, k in enumerate(kinds) if k == "img"]
    gaps = [sum(visible_len(blocks[j][1]) for j in range(a + 1, b) if blocks[j][0] == "p")
            for a, b in zip(idx, idx[1:])]
    longest = max((visible_len(p) for p in paras), default=0)
    out.append(f"节奏 · 非正文块 {sum(1 for k in kinds if k != 'p')}/{len(kinds)}"
               + (f" · 图间承接最少 {min(gaps)} 字" if gaps else "") + f" · 最长段落 {longest} 字")
    strong = sum(len(re.findall(r"==.+?==|<u>.+?</u>", p)) for p in paras)
    weak = sum(len(re.findall(r"\*\*.+?\*\*", p)) for p in paras)
    out.append(f"结构 · H2 {len(heads)} · 转场 {kinds.count('hr')} · Peak {kinds.count('peak')}"
               f" · 强调 =={strong} / **{weak}")
    if "peak" in kinds:
        i = kinds.index("peak")
        after = kinds[i + 1] if i + 1 < len(kinds) else "（结尾）"
        out.append(f"节奏线 · 首屏 → 高潮在第 {i + 1}/{len(kinds)} 块（{round(100 * (i + 1) / len(kinds))}%）"
                   f" · 高潮后是 {after} · 收束：{kinds[-1]}{' + cta' if meta.get('cta') else '（无 cta）'}")
    else:
        out.append("节奏线 · 没有 peak：确认全文真的不存在值得记住的一句")
    out.append(f"封面 · {COVER_RATIO}:1 与 1:1 中央裁切见预览顶部（主语在正方形里还站得住吗）")
    return out


PREVIEW = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{margin:0;background:#EDEDEB;font-family:-apple-system,'PingFang SC',sans-serif}}
.bar{{position:sticky;top:0;display:flex;justify-content:space-between;align-items:center;padding:10px 16px;
background:#fff;border-bottom:1px solid #e5e5e5;font-size:12px;color:#888;z-index:9}}
button{{border:0;background:#1F1F1F;color:#fff;padding:8px 16px;border-radius:6px;font-size:13px;cursor:pointer}}
.phone{{position:relative;max-width:390px;margin:24px auto 64px;background:#fff;padding:24px 16px 48px;box-sizing:border-box}}
.nt{{padding:2px 2px 16px;margin-bottom:22px;border-bottom:1px solid #EDEDEB}}
.nt h1{{margin:0 0 8px;font-size:22px;line-height:1.4;font-weight:700;color:#191919}}
.nt .au{{margin:0;font-size:13px;color:#888}}
.fold{{position:absolute;left:0;right:0;top:780px;border-top:1px dashed #C6C1B8}}
.fold b{{position:absolute;right:6px;top:-17px;font-size:10px;font-weight:500;letter-spacing:1px;color:#A8A29A;
background:#fff;padding:0 5px}}
.cv{{max-width:390px;margin:24px auto 0;background:#fff;padding:16px;box-sizing:border-box}}
.cv h4{{margin:0 0 8px;font-size:11px;letter-spacing:1.6px;color:#8A847A;font-weight:600}}
.cv img{{display:block;width:100%;background:#F0EEE9}}
.hint{{margin:16px 0 0;font-size:11px;line-height:1.7;color:#A8A29A}}</style></head>
<body><div class="bar"><span>{theme} · 390px</span><button onclick="cp(this)">复制到公众号</button></div>
{cover}<div class="phone">{native}<div id="c">{body}</div><div class="fold"><b>首屏 ≈780px</b></div></div>
<script>function cp(b){{var r=document.createRange();r.selectNodeContents(document.getElementById('c'));
var s=getSelection();s.removeAllRanges();s.addRange(r);var ok=document.execCommand('copy');s.removeAllRanges();
b.textContent=ok?'已复制，去编辑器粘贴':'请手动全选复制';setTimeout(function(){{b.textContent='复制到公众号'}},2200)}}</script>
</body></html>"""


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
            f'<img src="{H.escape(src)}" style="aspect-ratio:2.35/1;object-fit:cover">'
            f'<h4 style="margin:16px 0 8px">1:1 缩略（信息流 / 会话卡片）</h4>'
            f'<img src="{H.escape(src)}" style="width:132px;height:132px;object-fit:cover">'
            f'<p class="hint">默认不放文字。{warn}</p></div>')


def render(md, theme=None):
    meta, blocks = parse(md)
    key = theme or meta.get("theme", "paper")
    if key not in THEMES:
        sys.exit(f"未知主题 {key}，可选：{', '.join(THEMES)}")
    r = R(THEMES[key], meta.get("density", "standard"))
    chars = sum(visible_len(b[1]) for b in blocks if b[0] == "p")
    out, n = [r.masthead(meta, max(1, math.ceil(chars / 400)))], 0
    heads = [b[1] for b in blocks if b[0] == "h2"]
    toc_done = meta.get("toc", "").lower() not in ("true", "yes", "1") or len(heads) < 3
    for kind, b in blocks:
        if not toc_done and kind != "lead":
            out.append(r.toc(heads))
            toc_done = True
        if kind == "h2":
            n += 1
            out.append(r.h2(b, n))
        elif kind == "h3":
            out.append(r.h3(b))
        elif kind == "p":
            out.append(r.para(b))
        elif kind in ("lead", "quote"):
            out.append(r.quote(b[0], b[1], kind))
        elif kind == "peak":
            out.append(r.quote(peak_text(b), "", "peak"))
        elif kind == "note":
            out.append(r.note(*b))
        elif kind == "data":
            out.append(r.data(b[1]))
        elif kind == "bars":
            out.append(r.bars(b[1]))
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
            f'letter-spacing:0.5px;line-break:strict;overflow-wrap:break-word;">' + "".join(out) + "</section>")
    return key, meta, blocks, body


SPECIMEN_MD = """---
title: 留下的东西|比发出去的更重要
kicker: SPECIMEN
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
.phone{{background:#fff;padding:28px 18px 48px;box-shadow:0 24px 48px rgba(40,30,20,.14)}}</style>
</head><body>
<header><div class="k">EDITORIAL MODES · 生成物，勿手改（render.py --specimen）</div>
<h1>六种编辑人格，不是六套配色</h1>
<p class="lede">同一篇样张，六种气候。用途与判断见 references/decide.md；此板用来目视对照与主题回归。</p></header>
<div class="board">
{cols}
</div></body></html>
"""


def specimen(path):
    """六格对照板由真实渲染器生成，避免与人手维护的样本漂移。写到 shots/（生成物目录）。"""
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
        specimen(a.out or os.path.join(HERE, "..", "shots", "themes.html"))
        return
    if not a.md:
        ap.error("需要一个 markdown 文件，或使用 --specimen")
    base = os.path.dirname(os.path.abspath(a.md))
    key, meta, blocks, body = render(open(a.md, encoding="utf-8").read(), a.theme)
    out = a.out or f"{os.path.splitext(a.md)[0]}_{key}.html"
    open(out, "w", encoding="utf-8").write(body)
    prev = os.path.splitext(out)[0] + "_预览.html"
    # 预览模拟平台原生标题栏 / 作者行：title、author 只进原生字段，正文不再重印。
    # 复制按钮只复制 #c，模拟标题栏不会被带进编辑器。
    nt = H.escape(api_title(meta.get("title", "")))
    au = H.escape(meta.get("author", ""))
    native = (f'<div class="nt"><h1>{nt}</h1>' + (f'<p class="au">{au}</p>' if au else "") + "</div>") if nt else ""
    open(prev, "w", encoding="utf-8").write(
        PREVIEW.format(title=H.escape(meta.get("title", "")), theme=THEMES[key]["name"],
                       cover=cover_block(meta, base), native=native, body=body))
    # 发布字段 sidecar：publish.py --meta 直接消费，保证草稿原生字段与预览所见一致。
    cover = (meta.get("cover") or "").strip()
    side = {
        "title": meta.get("title", ""),
        "api_title": api_title(meta.get("title", ""))[:32],
        "author": (meta.get("author") or "")[:16],
        "digest": auto_digest(meta, blocks),
        "cover": "" if (not cover or TODO.match(cover)) else cover,
        "source_url": meta.get("source", ""),
        "theme": key,
    }
    meta_path = os.path.splitext(out)[0] + ".meta.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(side, f, ensure_ascii=False, indent=2)
    print(f"{THEMES[key]['name']} → {out}\n预览 → {prev}\n发布字段 → {meta_path}（publish.py --meta 直接消费）\n")
    m1, s1 = check(body)
    m2, s2 = compose_gate(meta, blocks, base)
    print(f"{THEMES[key]['name']} → {out}\n预览 → {prev}\n")
    print("Gate 3 证据（可核对的都摆在这里；结论与艺术判断由通读的人 / 视觉模型给）")
    for line in evidence(meta, blocks, base):
        print("  " + line)
    for gate, must, should in (("Gate 1 Platform", m1, s1), ("Gate 2 Composition", m2, s2)):
        print(f"\n{gate}: {'FAIL' if must else 'PASS'}")
        for x in must:
            print("  必须改 ·", x)
        for x in should:
            print("  建议改 ·", x)
    print("\nGate 3 Art Direction：对照上面证据通读 390px 预览。"
          "CONTENT / EDITORIAL / VISUAL / MOBILE / FINAL JUDGMENT —— 只写 KEEP / REVISE / DELETE，"
          "回答 **Which element should disappear?**，并给每张留下的资产一句「为什么是这张」。")
    if not meta.get("author"):
        print("未提供 author：草稿作者栏将留空（作者名只走原生字段，正文不印）")
    sys.exit(1 if m1 or m2 else 0)


if __name__ == "__main__":
    main()
