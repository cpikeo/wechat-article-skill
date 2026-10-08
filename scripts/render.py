#!/usr/bin/env python3
"""Composed Markdown → 公众号 HTML + 390px 预览 + Gate 1/2（一次调用）。

    render.py article.md [--theme paper|letter|ink|frost|bone|folio] [-o out.html]

产出 {stem}_{theme}.html 与 {stem}_{theme}_预览.html。
语法见 SKILL.md。退出码 1 = 存在「必须改」。
设计规则在 SKILL.md / references/decide.md；本文件只执行可确定的子集。
"""
import argparse
import html as H
import json
import math
import os
import re
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
ROLES = {
    "信息", "证据", "氛围", "隐喻", "停顿", "锚点", "数据",
    "information", "evidence", "atmosphere", "metaphor", "pause", "anchor", "data",
}
ATMO = {"氛围", "atmosphere", "隐喻", "metaphor", "停顿", "pause", "锚点", "anchor"}
INFO = {"证据", "evidence", "信息", "information", "数据", "data"}
BR = '<span leaf=""><br></span>'
INLINE = re.compile(r"`([^`]+)`|==(.+?)==|\*\*(.+?)\*\*|<u>(.+?)</u>|~~(.+?)~~|\[([^\]]+)\]\(([^)\s]+)\)")
EMOJI = re.compile(r"[\U0001F300-\U0001FAFF\u2600-\u27BF]")


def typo(s):
    """中文语境：半角标点→全角、直引号→弯引号。代码与链接在外层保护。"""
    if not re.search(f"[{CJK}]", s):
        return s
    s = re.sub(f"(?<=[{CJK}])([,;:!?])|(?<=[A-Za-z0-9])([,;!?])\\s*(?=[{CJK}])",
               lambda m: "，；：！？"[",;:!?".index(m.group(1) or m.group(2))], s)
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
        t, out = self.t, []
        kicker = meta.get("kicker", t["kicker"])
        if t["seal"]:
            out.append(f'<section style="display:flex;align-items:center;gap:10px;">'
                       f'{self.seal(meta.get("seal", t["seal"]))}{self.micro(kicker)}</section>')
        else:
            out.append(self.micro(kicker))
        title = "<br/>".join(self.leaf(typo(x.strip())) for x in meta.get("title", "").split("|"))
        out.append(self.p(title, TITLE, t["text"], f"font-weight:700;line-height:1.45;letter-spacing:1px;"
                                                   f"font-family:{self.font};margin-top:16px;"))
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
        t, rows, items = self.t, [], [x.split("|", 1) for x in lines]
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
        air = role0 in ATMO
        mt = self.g(44 if air else 32)
        if not src or re.match(r"(?i)todo|待补", src):
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
        cap_size = SMALL if role0 in INFO else MICRO
        cap_color = t["sub"] if role0 in INFO else t["muted"]
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
        t, out = self.t, []
        if meta.get("cta"):
            out.append(self.p(self.inline(meta["cta"]), SMALL, t["sub"], "margin-bottom:28px;"))
        if not meta.get("author"):
            return "".join(out) and f'<section style="margin-top:{self.g(52)}px;text-align:center;">{"".join(out)}</section>'
        out.append(f'<section style="text-align:center;">{self.seal(meta.get("seal", t["seal"]))}</section>'
                   if t["seal"] else self.rule(24))
        who = " · ".join(x for x in (meta["author"], meta.get("bio")) if x)
        out.append(self.p(self.leaf(typo(who)), MICRO, t["muted"], "margin-top:16px;letter-spacing:1px;"))
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


def peak_text(b):
    return " ".join(b[1]) or b[0]


def compose_gate(meta, blocks):
    """Gate 2：结构可确定的部分。审美判断留给 Gate 3。"""
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
    for _, (alt, src, role) in imgs:
        if not role:
            must.append(f"图片「{alt or src}」没有声明职责：说不出为什么存在就删除")
        elif role.split()[0] not in ROLES:
            should.append(f"图片职责「{role}」不在标准集合：信息/证据/氛围/隐喻/停顿/锚点/数据")
    chars = sum(visible_len(p) for p in paras)
    real = [x for x in imgs if x[1][1] and not re.match(r"(?i)todo|待补", x[1][1])]
    if len(real) > max(2, chars // 600):
        should.append(f"{len(real)} 张图 / {chars} 字：图片密度偏高，只保留改变阅读体验的那几张")
    for (a, _), (b, _) in zip(imgs, imgs[1:]):
        if sum(visible_len(blocks[k][1]) for k in range(a + 1, b) if blocks[k][0] == "p") < 40:
            should.append("两张图片之间缺少文字承接：合并、删减或补一段过渡")
    if kinds.count("note") > 2:
        should.append(f"{kinds.count('note')} 个 note：旁注过多，优先删除而不是换样式")
    if kinds.count("hr") > 2:
        should.append("转场过多：章节标题已经是停顿，--- 能少则少")
    if kinds.count("quote") > 3:
        should.append(f"{kinds.count('quote')} 处引文：他者声音过多会变成第二个节奏")
    heavy = {"quote", "peak", "note", "data", "table", "code", "img"}
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
    return must, should


PREVIEW = """<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<style>body{{margin:0;background:#EDEDEB;font-family:-apple-system,'PingFang SC',sans-serif}}
.bar{{position:sticky;top:0;display:flex;justify-content:space-between;align-items:center;padding:10px 16px;
background:#fff;border-bottom:1px solid #e5e5e5;font-size:12px;color:#888;z-index:9}}
button{{border:0;background:#1F1F1F;color:#fff;padding:8px 16px;border-radius:6px;font-size:13px;cursor:pointer}}
.phone{{max-width:390px;margin:24px auto 64px;background:#fff;padding:24px 16px 48px;box-sizing:border-box}}</style></head>
<body><div class="bar"><span>{theme} · 390px</span><button onclick="cp(this)">复制到公众号</button></div>
<div class="phone"><div id="c">{body}</div></div>
<script>function cp(b){{var r=document.createRange();r.selectNodeContents(document.getElementById('c'));
var s=getSelection();s.removeAllRanges();s.addRange(r);var ok=document.execCommand('copy');s.removeAllRanges();
b.textContent=ok?'已复制，去编辑器粘贴':'请手动全选复制';setTimeout(function(){{b.textContent='复制到公众号'}},2200)}}</script>
</body></html>"""


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
            sys.exit(f"未知原语 ::: {kind}（可用：peak / note / data）")
    out.append(r.signature(meta))
    t = THEMES[key]
    body = (f'<section style="font-family:{SANS};font-size:{BODY}px;color:{t["text"]};line-height:{t["leading"]};'
            f'letter-spacing:0.5px;line-break:strict;overflow-wrap:break-word;">' + "".join(out) + "</section>")
    return key, meta, blocks, body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md")
    ap.add_argument("--theme", choices=list(THEMES))
    ap.add_argument("-o", "--out")
    a = ap.parse_args()
    key, meta, blocks, body = render(open(a.md, encoding="utf-8").read(), a.theme)
    out = a.out or f"{os.path.splitext(a.md)[0]}_{key}.html"
    open(out, "w", encoding="utf-8").write(body)
    prev = os.path.splitext(out)[0] + "_预览.html"
    open(prev, "w", encoding="utf-8").write(
        PREVIEW.format(title=H.escape(meta.get("title", "")), theme=THEMES[key]["name"], body=body))
    m1, s1 = check(body)
    m2, s2 = compose_gate(meta, blocks)
    holds = sum(1 for b in blocks if b[0] == "img" and (not b[1][1] or re.match(r"(?i)todo|待补", b[1][1])))
    print(f"{THEMES[key]['name']} → {out}\n预览 → {prev}")
    for gate, must, should in (("Gate 1 Platform", m1, s1), ("Gate 2 Composition", m2, s2)):
        print(f"\n{gate}: {'FAIL' if must else 'PASS'}")
        for x in must:
            print("  必须改 ·", x)
        for x in should:
            print("  建议改 ·", x)
    print("\nGate 3 Art Direction：通读 390px 预览。首屏为何往下读？高潮是不是 Core Claim？哪一个元素删掉更好？")
    if holds:
        print(f"待补素材位 {holds} 处（交付时告知用户）")
    if not meta.get("author"):
        print("未提供 author：已省略署名区")
    sys.exit(1 if m1 or m2 else 0)


if __name__ == "__main__":
    main()
