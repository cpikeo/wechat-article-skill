#!/usr/bin/env python3
"""Composed Markdown → 公众号正文 HTML + 独立移动预览 + Gate 1/2（V19.1）。

    render.py article.md [--theme paper|letter|ink|frost|bone|folio] [-o out.html]
    render.py article.md --against 原稿.md [--ledger 台账.md]
    render.py article.md --deliver 交付目录/
"""
import argparse
import base64
import functools
import hashlib
import html as H
import json
import math
import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check import MONO, SANS, SERIF, check, safe_http_url, source_urls  # noqa: E402
from editorial import (  # noqa: E402
    FACT_ROLES, NUM_UNITS, PROVENANCE_ROLES, ROLES, audit, block_text, classify_fact_change,
    compare_facts, compare_voice, describe_change, doc_len, first_screen, introduced_without_source,
    LEDGER_HEAD, locate, parse_ledger, peak_text, plain, render_report, split_row, strategy_notes,
)
from safety import atomic_write, contrast, local_path, output_path, sha256  # noqa: E402
import typography  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_VERSION = "19.1.0"
THEMES_PATH = os.path.join(HERE, "..", "assets", "themes.json")
with open(THEMES_PATH, "rb") as _theme_file:
    THEME_CONFIG_BYTES = _theme_file.read()
THEME_CONFIG_SHA256 = hashlib.sha256(THEME_CONFIG_BYTES).hexdigest()
THEMES = json.loads(THEME_CONFIG_BYTES.decode("utf-8"))

THEME_AXES = {
    "header": {"rule", "lede", "seal", "band", "plate", "feature"},
    "lead": {"brief", "deck", "ink", "report", "plate", "feature"},
    "heading": {"gutter", "rail", "seal", "brief", "atelier", "folio"},
    "heading_num": {"above", "inline"},
    "h3": {"label", "soft", "serif", "report", "atelier", "folio"},
    "peak": {"rule", "bar", "line", "plate", "quiet", "compact"},
    "divider": {"short-rule", "pause", "seal", "hairline", "double", "dot"},
    "quote": {"rule", "inset", "serif", "report", "atelier", "folio"},
    "image": {"flush", "soft", "inkline", "report", "mat", "folio"},
    "initial": {"none", "raised"},
    "data": {"columns", "stack", "ledger", "ticker", "specimen", "folio"},
    "table": {"open", "warm", "ink", "report", "atelier", "feature"},
    "list": {"index", "dash", "chinese", "report", "atelier", "folio"},
    "code": {"rule", "flush", "ink", "signal", "plate", "folio"},
}
TYPE_KEYS = ("deck_size", "heading_size", "heading_weight", "heading_leading", "peak_size", "lead_size",
             "lead_weight", "lead_leading", "quote_size", "h3_size", "data_size")
TRACKING_KEYS = ("display", "heading", "label", "caption")
COLOR_ROLES = ("page", "text", "sub", "muted", "line", "accent")
TEXT_ROLES = ("text", "sub", "muted", "accent")
# 版面只有一种背景：页底。浅底（field）作为“块”的区分手段已整体取消，
# 代码、数据、记录卡改由字体、留白与细线承担，因此不再存在第二个背景角色。
BACKGROUND_ROLES = ("page",)
PAGE_HEX = "#FFFFFF"
GRID_KEYS = ("indent", "chapter_gap", "paragraph_gap", "body", "caption")
# 纵向节奏的硬区间：正文行高、标题行高、段距都不允许落到区间外。
# 这些数字不是审美偏好，是中文手机正文的可读区间——行高靠加宽制造的“高级感”，
# 读者只在翻页时付出代价。
LEADING_BAND = (1.65, 1.78)
HEADING_LEADING_BAND = (1.20, 1.35)
PARAGRAPH_GAP_BAND = (12, 16)
MARGIN_BAND = (16, 20)
# 重点句的字重由主题气质决定，但必须低于同级章节标题：两者字号接近时，字重是唯一还能
# 把“作者的一句判断”和“版面的一个门框”区分开的东西。
PEAK_WEIGHT = {"rule": 500, "bar": 500, "quiet": 600, "line": 600, "plate": 400, "compact": 700}
# 三级标题轴：字重 + 字族 + 字距 + 上下间距 + 前置记号。六档必须真的不同——
# 若四种取值落到同一组参数，这条轴就只是 themes.json 里的一个装饰性字段。
H3_AXIS = {
    "label": (600, "sans", "heading", 30, 10, ""),
    "soft": (600, "serif", "caption", 30, 8, ""),
    "serif": (600, "serif", "heading", 34, 10, "seal"),
    "report": (700, "sans", "heading", 24, 6, ""),
    "atelier": (600, "serif", "heading", 32, 10, "hair"),
    "folio": (700, "sans", "display", 24, 8, ""),
}


def contrast_pairs(t):
    """所有实际文字色 × 实际背景色；载入与侧车共用同一真源。"""
    return [(role, bg) for bg in BACKGROUND_ROLES for role in TEXT_ROLES]


def side_px(t):
    """页边按 390 设计宽给定像素：微信正文容器宽度随机型变化，比例页边会在窄屏挤掉字。"""
    return t.get("margin", 0)


def content_px(t, viewport=320):
    """指定视口下的可用正文宽度。"""
    return viewport - 2 * side_px(t)


def validate_themes(themes):
    """校验主题配置完整性与字号层级硬约束（H2 > 导语 > 正文 ≥ 图注 ≥ 12px，H2 > H3 ≥ 正文）。"""
    problems = []
    for name, t in themes.items():
        before = len(problems)
        for axis, allowed in THEME_AXES.items():
            value = t.get(axis)
            if value not in allowed:
                problems.append(f"{name}.{axis}={value!r} 未登记（可用：{'、'.join(sorted(allowed))}）")
        for role in COLOR_ROLES + ("display", "toc_label", "body_font", "initial"):
            if role not in t:
                problems.append(f"{name} 缺少 {role}")
        if not (t.get("stance") or "").strip():
            problems.append(f"{name} 缺少 stance：每套主题必须先说清它是哪一种世界，配色与版式才有判断依据")
        for key in GRID_KEYS:
            if key not in t.get("grid", {}):
                problems.append(f"{name}.grid 缺少 {key}")
        for key in TYPE_KEYS:
            if key not in t.get("type", {}):
                problems.append(f"{name}.type 缺少 {key}")
        for key in TRACKING_KEYS:
            if key not in t.get("tracking", {}):
                problems.append(f"{name}.tracking 缺少 {key}")
        if not 0 <= t.get("margin", -1) <= 40:
            problems.append(f"{name}.margin 须为 0–40px（当前 {t.get('margin')!r}）")
        if t.get("rhythm") not in (6, 8, 9, 10, 12):
            problems.append(f"{name}.rhythm 须为 6/8/9/10/12（当前 {t.get('rhythm')!r}）")
        if t.get("page") != PAGE_HEX:
            problems.append(f"{name}.page={t.get('page')!r}：全部主题只有一种版面背景 {PAGE_HEX}；"
                            "底色不能用来区分主题，区分靠字体、构图与节奏")
        if "field" in t:
            problems.append(f"{name} 仍有 field：浅底角色已取消，块的分界改用细线与留白；请删除这一项")
        if "side_left" in t or "side_right" in t:
            problems.append(f"{name} 仍有 side_left/side_right：左右页边默认对称，非对称必须在正文里说明构图理由，"
                            "不能用主题参数随手偏移")
        if len(problems) > before:
            continue
        ty, grid = t["type"], t["grid"]
        # 纵向节奏：行高与段距落在中文字手机正文的可读区间内，六套主题只在这个区间里微调。
        if not LEADING_BAND[0] <= t["leading"] <= LEADING_BAND[1]:
            problems.append(f"{name}：正文行高 {t['leading']} 超出 {LEADING_BAND[0]}–{LEADING_BAND[1]}"
                            "（过宽会把紧凑的论证读成松散的散文）")
        if not HEADING_LEADING_BAND[0] <= ty["heading_leading"] <= HEADING_LEADING_BAND[1]:
            problems.append(f"{name}：标题行高 {ty['heading_leading']} 超出 "
                            f"{HEADING_LEADING_BAND[0]}–{HEADING_LEADING_BAND[1]}（标题两行之间不许松开）")
        if not LEADING_BAND[0] <= ty["lead_leading"] <= LEADING_BAND[1]:
            problems.append(f"{name}：导语行高 {ty['lead_leading']} 超出 {LEADING_BAND[0]}–{LEADING_BAND[1]}")
        if not PARAGRAPH_GAP_BAND[0] <= grid["paragraph_gap"] <= PARAGRAPH_GAP_BAND[1]:
            problems.append(f"{name}：段距 {grid['paragraph_gap']}px 超出 "
                            f"{PARAGRAPH_GAP_BAND[0]}–{PARAGRAPH_GAP_BAND[1]}px")
        if not 24 <= grid["chapter_gap"] <= 56:
            problems.append(f"{name}：章节间距 {grid['chapter_gap']}px 超出 24–56px（过大就是空白在假装层级）")
        if not MARGIN_BAND[0] <= t["margin"] <= MARGIN_BAND[1]:
            problems.append(f"{name}：左右页边 {t['margin']}px 超出 {MARGIN_BAND[0]}–{MARGIN_BAND[1]}px"
                            "（320–430px 屏幕共用的安全区间）")
        if not ty["heading_size"] > ty["lead_size"]:
            problems.append(f"{name}：章节标题 {ty['heading_size']}px 未大于导语 {ty['lead_size']}px")
        if not ty["lead_size"] > grid["body"]:
            problems.append(f"{name}：导语 {ty['lead_size']}px 未大于正文 {grid['body']}px")
        if not ty["heading_size"] > ty["h3_size"]:
            problems.append(f"{name}：H2 {ty['heading_size']}px 未大于 H3 {ty['h3_size']}px")
        if ty["h3_size"] < grid["body"]:
            problems.append(f"{name}：H3 {ty['h3_size']}px 小于正文 {grid['body']}px，层级倒置")
        if ty["heading_size"] - grid["body"] < 5:
            problems.append(f"{name}：H2 与正文仅差 {ty['heading_size'] - grid['body']}px，章节层级立不住")
        # 重点句夹在导语与章节标题之间：既不能低于导语（否则“重点”让位于“导语”），
        # 也不能贴到章节标题的高度（否则读者会把一句判断扫成一个小标题）。
        if ty["peak_size"] <= ty["lead_size"]:
            problems.append(f"{name}：重点句 {ty['peak_size']}px 未高于导语 {ty['lead_size']}px")
        if ty["peak_size"] >= ty["heading_size"]:
            problems.append(f"{name}：重点句 {ty['peak_size']}px 不低于章节标题 {ty['heading_size']}px")
        elif (ty["heading_size"] - ty["peak_size"] < 4
              and PEAK_WEIGHT.get(t["peak"], 600) >= ty["heading_weight"]):
            problems.append(f"{name}：重点句 {ty['peak_size']}px 与章节标题 {ty['heading_size']}px 仅差 "
                            f"{ty['heading_size'] - ty['peak_size']}px 且字重不低，两者会被读成同级")
        if not grid["body"] >= grid["caption"]:
            problems.append(f"{name}：正文 {grid['body']}px 小于图注 {grid['caption']}px")
        if not 15 <= grid["body"] <= 17:
            problems.append(f"{name}：正文字号 {grid['body']}px 超出 15–17px 手机阅读区间")
        if not 12 <= grid["caption"] <= 15:
            problems.append(f"{name}：图注字号 {grid['caption']}px 超出 12–15px")
        if not 12 <= ty["deck_size"] <= 20:
            problems.append(f"{name}：摘要行 {ty['deck_size']}px 超出 12–20px")
        if not 12 <= ty["data_size"] <= 40:
            problems.append(f"{name}：数据值 {ty['data_size']}px 超出 12–40px")
        if not -0.03 <= t["tracking"]["display"] <= 0.08:
            problems.append(f"{name}：标题字距 {t['tracking']['display']}em 超出 -0.03–0.08em")
        if not 0 <= t["tracking"]["label"] <= 0.20:
            problems.append(f"{name}：标签字距 {t['tracking']['label']}em 超出 0–0.20em")
        # 分隔线是这套版面的骨架：章节印记、表格边框、柱图轨道、目录栏位全靠它。
        # 1.45:1 以下在手机屏上等于不存在，3.2:1 以上会抢过正文；两个边界都是实测口径。
        rule = contrast(t["line"], t["page"])
        if not 1.45 <= rule <= 3.2:
            problems.append(f"{name}：分隔线 {t['line']} 在底色 {t['page']} 上 {rule:.2f}:1，"
                            + ("低于 1.45:1 会在手机上消失" if rule < 1.45 else "高于 3.2:1 会抢过正文"))
        for role, bg in contrast_pairs(t):
            ratio = contrast(t[role], t[bg])
            if ratio < 4.5:
                problems.append(f"{name}：{role} {t[role]} 在 {bg} {t[bg]} 上对比 {ratio:.2f}，低于 WCAG AA 4.5:1")
    return problems



_THEME_PROBLEMS = validate_themes(THEMES)
if _THEME_PROBLEMS:
    raise ValueError("主题配置不合格：\n  " + "\n  ".join(_THEME_PROBLEMS))

CJK = "\u4e00-\u9fff\u3400-\u4dbf"
# 行首标点悬挂：中文正文的起笔线是一条直线，引号与书名号退进页边半个字。
HANGING = "“‘「『（《【"
# 笔画过少、放大后会被读成一条线的字：首字放大要跳过它们。
SPARSE_GLYPHS = set("一二三十丁厂丨川")

MICRO, SMALL, BODY = 13, 14, 16


@functools.lru_cache(maxsize=1)
def renderer_fingerprint():
    root = os.path.dirname(HERE)
    paths = [os.path.join(root, "assets", "themes.json"),
             os.path.join(root, "assets", "preview.template.html")] + [
        os.path.join(HERE, name + ".py") for name in ("render", "editorial", "check", "safety", "typography")]
    h = hashlib.sha256()
    for path in sorted(paths):
        with open(path, "rb") as stream:
            h.update(os.path.relpath(path, root).encode() + b"\0" + stream.read() + b"\0")
    return h.hexdigest()

IMAGE_MODES = {"hero", "full-width", "bleed", "inset", "plate", "sequence", "comparison", "detail", "macro", "evidence", "editorial", "explainer", "data"}
TODO = re.compile(r"(?i)^(todo|待补)")
# 图注是作者写给读者看的说明；只有看起来像制作标签的短文本才不印，而不是按职责一刀切丢掉。
CAPTION_LABEL = re.compile(
    r"^(?:封面|配图|插图|图片|示意图|素材|生成图|待补|todo)\b|^(?:AI\s*生成|生成式|人工智能生成)"
    r"|(?:素材说明|待补素材|来源[：:]|授权[：:])", re.I)


def _caption_text(alt, role0):
    """决定图注是否上版：事实类职责必须印；其余职责保留作者写的说明，但挡掉制作标签。"""
    text = (alt or "").strip()
    if not text:
        return ""
    if role0 in FACT_ROLES:
        return text
    if len(plain(text)) < 6 or CAPTION_LABEL.search(text):
        return ""
    return text
COVER_RATIO = 2.35
COVER_BAND = (1.6, 3.0)
COVER_MIN_W = 900

BR = '<span leaf=""><br></span>'
# 由专门语法产生的块名。`::: name` 只能写原语，撞上这些名字会落进错误分支。
STRUCTURAL_KINDS = ("lead", "quote", "p", "h2", "h3", "img", "code", "table", "list", "hr")
INLINE = re.compile(
    r"\\(?P<escape>[\\`*_\[\]()<>~=\-#!.+|:])"
    r"|`(?P<code>[^`]+)`|==(?P<mark>.+?)==|\*\*\*(?P<bolditalic>.+?)\*\*\*|\*\*(?P<bold>.+?)\*\*"
    r"|<u>(?P<underline>.+?)</u>|~~(?P<strike>.+?)~~"
    r"|(?<!\*)\*(?P<italic>[^*\n]+?)\*(?!\*)"
    r"|\[(?P<link>(?:\[[^\]\n]*\]|[^\[\]])+)\]\((?P<url>[^)\s]+)\)"
)

CN_NUM = "一二三四五六七八九十百零〇两"
# 章节序号只在“标题开头 + 紧跟分隔符或章节量词”时才算数。这条边界是整个编号机制的地基：
# 放宽一格，`3.5 倍`、`12 月`、`一小时` 就会被当成序号从标题里剥掉——那是删数据，不是排版。
_SEP = r"(?:[、．。，:：]|[.,](?!\d))"
ORDINAL_HEAD = re.compile(
    r"^[（(]\s*(?P<paren>[" + CN_NUM + r"]{1,3}|\d{1,2})\s*[）)]\s*"
    r"|^(?P<cn>[" + CN_NUM + r"]{1,3})\s*" + _SEP + r"\s*"
    r"|^(?P<arabic>\d{1,2})\s*" + _SEP + r"\s*"
    r"|^(?P<zero>0\d)[\s　]+"
    r"|^(?P<chap>第\s*(?:[" + CN_NUM + r"]{1,4}|\d{1,3})\s*[章节回讲部篇期段条则辑卷问日])"
    r"\s*[、．。，:：.]?\s*"
    r"|^(?P<circ>[①-⑳⑴-⒇])"
)


def split_ordinal(text):
    """剥离标题开头的章节序号，返回去掉序号后的标题。

    全文只此一处识别章节序号：渲染、目录、门禁共用它，因此不可能出现
    “左侧自动编号 + 标题里手写序号”同时上版。标题若只剩序号本身（例如整行就是“二、”），
    原样返回——宁可留一个重复的编号，也不能把标题清空。
    """
    raw = (text or "").strip()
    m = ORDINAL_HEAD.match(raw)
    if not m:
        return raw
    rest = raw[m.end():].strip()
    return rest or raw


def has_ordinal(text):
    """标题是否自带序号：只有自带时才需要决定“保留原序号”还是“改由渲染器编号”。"""
    raw = (text or "").strip()
    return bool(ORDINAL_HEAD.match(raw)) and split_ordinal(raw) != raw

PROSE_ATOM = re.compile(
    r"(?:19|20)\d{2}年(?:\d{1,2}月(?:\d{1,2}日)?)?"
    r"|\d{1,2}月\d{1,2}日"
    r"|[+\-−]?\d[\d.,，]*(?:\s*[×x–—-]\s*[\d.,，]*)*(?::1|" + NUM_UNITS + r")?"
)


def typo(s):
    """中文语境半角标点归一；保护行内代码、链接与 URL。

    只做“源码级”改写：引号转形与装饰斜杠归一是文本节点的排版政策，统一在
    `typography.sanitize_html()` 里对最终文本节点执行一次。两处都做等于每个
    字都被 publish 两遍，而第二遍从未产出不同的结果。
    """
    def prose(text):
        return re.sub(
            f"(?<=[{CJK}])([,;:!?])|(?<=[A-Za-z0-9])([,;!?])\\s*(?=[{CJK}])",
            lambda m: dict(zip(",;:!?", "，；：！？"))[m[1] or m[2]],
            text,
        )
    return "".join(
        part if i % 2 else prose(part)
        for i, part in enumerate(re.split(r"(`[^`]+`|“[^”]*”|\u300c[^\u300d]*\u300d|\u300e[^\u300f]*\u300f|\[(?:\[[^\]\n]*\]|[^\]]+)\]\([^)\s]+\)|https?://[^\s<>\u3000，；。！？）\"]+)", s))
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
    "cover", "cover_note", "cover_focal", "kicker", "deck", "author", "date", "toc", "source", "removed_facts", "digest", "bio", "cta",
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


def parse(md, plain_text=False):
    if plain_text:
        text = md.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
        paragraphs = re.split(r"\n\s*\n", text.strip())
        escape = lambda value: re.sub(r"([\\`*_\[\]()<>~=#!.+|])", r"\\\1", value)
        return {}, [("p", escape(p.replace("\n", " "))) for p in paragraphs if p.strip()]
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
            if v.startswith(('"', "'")) and not re.fullmatch(r"([\"\'])([^\"\']*)\1(?:\s+#.*)?", v):
                raise ValueError(f"frontmatter 第 {line_no} 行引号未闭合")
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
        fence = re.match(r"^(`{3,}|~{3,})(.*)$", s)
        if fence:
            flush()
            marker, lang = fence.groups()
            if marker[0] == "`" and "`" in lang:
                raise ValueError(f"第 {i + 1} 行：反引号代码语言不能含反引号")
            body, i = [], i + 1
            closing = re.compile(r"^" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}\s*$")
            while i < len(lines) and not closing.fullmatch(lines[i].strip()):
                if lines[i].strip().startswith(marker[0] * len(marker)):
                    raise ValueError(f"第 {i + 1} 行：代码结束围栏不能附带文字")
                body.append(lines[i])
                i += 1
            if i >= len(lines):
                raise ValueError("代码围栏未闭合")
            blocks.append(("code", (lang.strip(), body)))
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
            if kind in STRUCTURAL_KINDS:
                # ::: 只产生原语。lead/quote/img 等结构性块有自己的语法，同名会撞进
                # 渲染分支并把内容错位（导语变成署名、正文消失），所以在这里拒掉。
                hint = "`> ` 引用块（全文首个即导语）" if kind in ("lead", "quote") else "对应的 Markdown 语法"
                raise ValueError(f"第 {i + 1} 行：::: {kind} 不是原语，请用 {hint}"
                                 f"（原语限：peak / note / unknown / data / bars / timeline）")
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
                q.append(re.sub(r"^\s*> ?", "", lines[i]))
                i += 1
            i -= 1
            src = q.pop()[1:].lstrip("—-– ").strip() if len(q) > 1 and re.match(r"[—–-]", q[-1]) else ""
            # 仅全文首个块作为导语，防止多个连续 > 块叠加成双导语
            kind = "lead" if not blocks else "quote"
            blocks.append((kind, ("\n".join(q).strip(), src)))
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
            rows, sep_cols, table_header_count = [], None, 0
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = split_row(lines[i])
                if cells and all(re.fullmatch(r":?-+:?", c) for c in cells):
                    sep_cols = len(cells)
                    table_header_count += 1
                    if table_header_count > 1 or len(rows) != 1:
                        raise ValueError(f"第 {i + 1} 行：表格分隔行只能出现一次且紧跟表头")
                else:
                    rows.append(cells)
                i += 1
            i -= 1
            if sep_cols is None or table_header_count != 1 or not rows:
                raise ValueError(f"第 {i + 1} 行：表格必须有表头，且第二行是唯一的列分隔行")
            if any(len(row) != sep_cols for row in rows):
                raise ValueError(f"第 {i + 1} 行：表格列数不一致，不能静默补齐或丢弃单元格")
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


def image_info(data):
    """从字节头一次性取 (MIME, (宽, 高))：PNG / JPEG / GIF / WebP。

    尺寸、MIME 与哈希都从同一份字节得到：图片只读一次，也不去问平台 MIME 注册表
    （Windows 上那次注册表读取比解码图片本身还慢）。
    """
    try:
        if data[:8] == b"\x89PNG\r\n\x1a\n":
            return "image/png", struct.unpack(">II", data[16:24])
        if data[:6] in (b"GIF87a", b"GIF89a"):
            return "image/gif", struct.unpack("<HH", data[6:10])
        if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
            tag, chunk = data[12:16], data[20:32]
            if tag == b"VP8X":
                return "image/webp", (1 + int.from_bytes(chunk[4:7], "little"),
                                      1 + int.from_bytes(chunk[7:10], "little"))
            if tag == b"VP8L":
                bits = int.from_bytes(chunk[1:5], "little")
                return "image/webp", ((bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1)
            if tag == b"VP8 ":
                return "image/webp", (int.from_bytes(chunk[6:8], "little") & 0x3FFF,
                                      int.from_bytes(chunk[8:10], "little") & 0x3FFF)
        if data[:2] == b"\xff\xd8":
            i = 2
            while i + 9 < len(data):
                if data[i] != 0xFF:
                    i += 1
                    continue
                marker = data[i + 1]
                if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                    height, width = struct.unpack(">HH", data[i + 5:i + 9])
                    return "image/jpeg", (width, height)
                if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                    i += 2
                    continue
                i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    except (struct.error, IndexError):
        return None, None
    return None, None


def file_image_info(path):
    try:
        with open(path, "rb") as stream:
            return image_info(stream.read())
    except OSError:
        return None, None


NUMERIC = re.compile(
    r"(?:约|近|超过|超|不足|少于|多于|不到)?[+\-−]?[\d.,，]+(?:\s*[–—-]\s*[\d.,，]+)?\s*"
    r"(?:" + NUM_UNITS + r")?"
)
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


def line_px(s, size, tracking=0.0):
    """含字距的单行宽度。CSS 的 letter-spacing 加在每个字符之后，末字也算一次。"""
    return text_px(s, size) + len(s) * tracking * size


def _greedy_wrap(text, size, width, tracking=0.0):
    """模拟不可控的自动折行：逐字贪心，用于判断末行是否会剩孤字。"""
    lines, cur = [], ""
    for ch in text:
        if not cur or line_px(cur + ch, size, tracking) <= width:
            cur += ch
        else:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    return lines


# 设计基准宽度：排版在 375–430 上必须成立，320 由标题长度把关而不是靠机械断行。
DESIGN_WIDTH = 375


def balance_title(text, size, width, tracking=0.0, narrow=None):
    """标题只在自动折行留下孤字/寡行时重排，且重排结果必须在最窄屏仍然成立。

    返回 None 表示“不要插手”：正常断行不硬换行——硬换行会在大屏把一行拆成两行，
    也会在窄屏把已经断好的行再拆一次，反而造出两字孤行。只有版面真的失败时才付这个代价。
    """
    if not text:
        return None
    natural = _greedy_wrap(text, size, width, tracking)
    if len(natural) == 1:
        return None
    tail, head = len(natural[-1]), max(len(x) for x in natural[:-1])
    if tail >= 4 and tail >= head * 0.3:
        return None
    n = len(natural)
    target = len(text) / n
    lines, rest = [], text
    while rest and len(lines) < n - 1:
        lo, hi = int(target * 0.7), min(len(rest) - 1, int(target * 1.3) + 1)
        cut = next((i for i in range(hi, lo - 1, -1) if rest[i - 1] in "，。、：；·！？—）】》”"), 0)
        if not cut:
            cut = max(1, min(len(rest) - 1, round(target)))
        lines.append(rest[:cut])
        rest = rest[cut:]
    lines.append(rest)
    lines = [x for x in lines if x]
    if narrow and any(line_px(x, size, tracking) > narrow for x in lines):
        return None
    return lines


def orphan_cells(rows, widths, avail, pad, size=SMALL):
    """单元格折行后只剩一两个字，就是孤字行——这张表在手机上已经读不成了。
    列数不足三列时不判：两列表的列本来就宽，尾行两个字读得下去。"""
    if not rows or len(rows[0]) < 3:
        return False
    for row in rows:
        for j, cell in enumerate(row):
            room = widths[j] / 100 * avail - pad
            if room <= 0:
                return True
            lines = _greedy_wrap(plain(str(cell)).strip(), size, room)
            if len(lines) > 1 and len(lines[-1]) <= 2:
                return True
    return False


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


def table_fits(rows, pad=12, margin=0):
    """320px 视口下所有列的最小可读宽度能否同时成立；放不下则转记录卡。"""
    avail = 320 - 2 * margin
    if not rows or not rows[0]:
        return True
    return sum(_column_floors(rows, pad)) <= avail


def col_widths(rows, avail, pad=12):
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
    """六主题共享排版引擎：视觉差异由彩色关系、架构比例、字体与网格驱动，而非换一套色。"""

    def __init__(self, t, density):
        self.t = t
        self.type = t["type"]
        self.grid = t.get("grid", {})
        self.k = {"dense": 0.82, "airy": 1.18}.get(density, 1.0)
        self.body = self.grid.get("body", BODY)
        self.cap = self.grid.get("caption", MICRO)
        self.margin = t.get("margin", 0)
        # 左右页边一律对称：非对称会同时打破标题、正文、图注共用的那条起笔线，
        # 而这条线是整套版面的骨相。出血图需要的只是“页边是多少”，不关心两边是否相等。
        self.pad_left = self.pad_right = self.margin
        self.rhythm = t.get("rhythm", 8)
        self.tracking = t.get("tracking", {})
        self.font = SERIF if t["display"] == "serif" else SANS
        self.reading_font = SERIF if t.get("body_font") == "serif" else SANS
        self.image_axis = t["image"]
        self.divider_axis = t["divider"]
        self.initial = t["initial"]
        # 编号由渲染器统一生成，六套主题只差它放在哪里：inline 与标题同基线，
        # above 自成一行。标题里的手写序号一律剥掉——全文只能有一个编号来源。
        self.number_place = t.get("heading_num", "above")

    def g(self, px):
        """纵向间距一律落到主题的模数网格：26/30/34 这种随手值会让全篇节奏散掉。"""
        return max(self.rhythm, round(px * self.k / self.rhythm) * self.rhythm)

    def tr(self, role):
        value = self.tracking.get(role, 0)
        return f"letter-spacing:{value:g}em;" if value else "letter-spacing:normal;"

    def heading_lines(self, text, size, reserve=0.0):
        """标题断行：只在会留下孤字时重排，且只在纯文本标题上动手。

        reserve 是本行已被占掉的宽度（行内章节号）：不扣掉它，重排后的首行会顶出屏幕。
        """
        if re.search(r"[*`\[\]=<>~]", text):
            return None
        room = content_px(self.t, DESIGN_WIDTH) - reserve
        return balance_title(text, size, room, self.tracking.get("display", 0), room)


    def leaf(self, s):
        return BR if not s else BR.join(f'<span leaf="">{H.escape(part, quote=False)}</span>' for part in s.split("\n"))

    def prose_leaf(self, s):
        # Escape processing happens in inline(); here only keep numeric atoms intact.
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
        for m in INLINE.finditer(s):
            if m.start() > pos:
                out.append(self.prose_leaf(s[pos:m.start()]))
            g = m.groupdict()
            if g["escape"] is not None:
                out.append(self.leaf(g["escape"]))
            elif g["code"] is not None:
                # 行内代码不铺底色：等宽字族本身就是“这不是正文”的信号，
                # 再加一块灰底就成了卡片，而卡片会打断一行话的节奏。
                out.append(f'<span style="font-family:{MONO};font-size:{SMALL}px;color:{t["text"]};">'
                           f'{self.leaf(g["code"])}</span>')
            elif g["mark"] is not None or g["underline"] is not None:
                inner = self.inline(g["mark"] if g["mark"] is not None else g["underline"], normalize=False)
                out.append(f'<span style="border-bottom:1px solid {t["accent"]};padding-bottom:1px;">{inner}</span>')
            elif g["bolditalic"] is not None:
                out.append(f'<strong style="font-weight:700;color:inherit;"><span style="font-style:italic;">{self.inline(g["bolditalic"], normalize=False)}</span></strong>')
            elif g["bold"] is not None:
                out.append(f'<strong style="font-weight:700;color:inherit;">{self.inline(g["bold"], normalize=False)}</strong>')
            elif g["italic"] is not None:
                out.append(f'<span style="font-style:italic;">{self.inline(g["italic"], normalize=False)}</span>')
            elif g["strike"] is not None:
                out.append(f'<span style="text-decoration:line-through;color:{t["muted"]};">{self.inline(g["strike"], normalize=False)}</span>')
            else:
                url = g["url"]
                if not safe_http_url(url):
                    raise ValueError(f"链接不合法或协议不支持：{url}；仅允许带有效主机名的 HTTP(S) URL")
                out.append(f'<a href="{H.escape(url, quote=True)}" style="color:{t["text"]};text-decoration:underline;">{self.inline(g["link"], normalize=False)}</a>')
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

    def title_rows(self, text, size, extra, align=""):
        """标题正文：默认交给浏览器自然折行；只有在会留下孤字且重排安全时才显式分行。"""
        lines = self.heading_lines(text, size)
        if not lines:
            return self.p(self.inline(text), size, extra=extra + align)
        return "".join(self.p(self.leaf(line), size, extra=extra + align) for line in lines)

    def h2(self, text, n, weight="normal"):
        """章节标题：编号只是辅助信息，视觉重心永远在标题本身。

        n 由 render() 按章节出现顺序给出，标题里原有的手写序号已在 render() 剥掉，
        所以全文只有一个编号来源。主题之间只差编号**放在哪里**（`heading_num`）：
        `inline` 与标题同处一条起笔线，`above` 自成一行压在上方。
        """
        t, mode, place = self.t, self.t["heading"], self.number_place
        hs = self.type["heading_size"]
        # 字距是主题的排版语言，不随单条标题变动；断行只在真出孤字时由 balance_title 接管
        style = (f"font-weight:{self.type['heading_weight']};line-height:{self.type['heading_leading']};"
                 f"font-family:{self.font};{self.tr('display')}")
        # 章节间距不是常数：开篇第一章要立起整篇的门框，两段就翻过去的短章只是一次停顿——
        # 把它收近上文，读者才不会把一个停顿读成一个新部次。距离就是关系。
        lead_in = {"open": 1.34, "beat": 0.72}.get(weight, 1.0)
        gap = f'margin:{self.g(self.grid["chapter_gap"] * lead_in)}px 0 {self.g(12)}px;'
        accent_num = mode in ("rail", "brief", "folio")
        num_color = t["accent"] if accent_num else t["muted"]
        label = f"{n:02d}"

        def number_row():
            return self.p(self.leaf(label), 12, num_color,
                          f"margin-bottom:{self.g(6)}px;font-weight:600;"
                          f"font-variant-numeric:tabular-nums;{self.tr('label')}")

        def inline_prefix():
            """行内编号：12px 与标题同基线，后面留 8px。返回（HTML, 占位宽度）。"""
            width = text_px(label, 12) + len(label) * self.tracking.get("label", 0) * 12 + 8
            html = (f'<span style="font-size:12px;color:{num_color};font-weight:600;'
                    f'margin-right:8px;font-variant-numeric:tabular-nums;{self.tr("label")}">'
                    f'<span leaf="">{label}</span></span>')
            return html, width

        if mode == "rail":
            # 信笺：编号与一道短线并排贴在左栏，标题从同一条起笔线出发。
            # 线只做一件事——把标题从上一节的余韵里划出来，不用来包住标题。
            mark = (f'<section style="display:flex;align-items:center;gap:{self.g(9)}px;'
                    f'margin-bottom:{self.g(10)}px;">'
                    + self.p(self.leaf(label), 12, num_color,
                             f"font-weight:600;{self.tr('label')}font-variant-numeric:tabular-nums;")
                    + f'<section style="flex:1;height:1px;background:{t["line"]};">{BR}</section>'
                    "</section>")
            return f'<section style="{gap}">{mark}{self.title_rows(text, hs, style)}</section>'
        if mode == "brief":
            # 简报：编号在上，标题之下压一道通栏细线，把每节做成一条独立的电讯
            head = number_row() + self.title_rows(text, hs, style)
            rule = f'<section style="height:1px;background:{t["line"]};margin-top:{self.g(10)}px;">{BR}</section>'
            return f'<section style="{gap}">{head}{rule}</section>'
        # 其余模式：先画章节印记（韵墨的朱砂印、素作的展签线），再落标题
        mark = ""
        if mode == "seal":
            mark = (f'<section style="width:12px;height:2px;background:{t["accent"]};'
                    f'margin-bottom:{self.g(10)}px;">{BR}</section>')
        elif mode == "atelier":
            mark = (f'<section style="width:16px;height:1px;background:{t["line"]};'
                    f'margin-bottom:{self.g(10)}px;">{BR}</section>')
        if place == "inline":
            # 编号与标题同处一条起笔线：读者先读到标题，再回头发现“这里有个编号”。
            # 编号不能挂到页边外——18px 的页边放不下两位数，数字会贴到屏幕边缘。
            pre, reserve = inline_prefix()
            lines = self.heading_lines(text, hs, reserve)
            if not lines:
                body = self.p(pre + self.inline(text), hs, extra=style)
            else:
                body = self.p(pre + self.leaf(lines[0]), hs, extra=style) + "".join(
                    self.p(self.leaf(x), hs, extra=style) for x in lines[1:])
            return f'<section style="{gap}">{mark}{body}</section>'
        return (f'<section style="{gap}">{mark}' + number_row()
                + self.title_rows(text, hs, style, "") + "</section>")

    def masthead(self, meta):
        """刊头：只有摘要行。六主题各有一套起印语法——这是正文之前唯一的版面单元。

        刊头不放栏目行、期号或分类串：那些信息读者不需要，公众号也已有栏目体系，
        印在正文顶部只是装饰。一块版面从“这篇文章说什么”开始，不从刊名装饰开始。
        """
        t, mode = self.t, self.t["header"]
        deck = meta.get("deck", "")
        if not deck:
            return ""
        size = self.type["deck_size"]
        deck_style = f"font-family:{self.font};line-height:1.72;{self.tr('caption')}"

        def deck_p(color, weight=500, extra=""):
            return self.p(self.inline(deck), size, color,
                          deck_style + f"font-weight:{weight};" + extra)

        if mode == "lede":
            # 信笺：摘要与导语同一收进量，右端参差即版心——起笔线上不加任何横线
            return (f'<section style="margin-bottom:{self.g(22)}px;padding-right:8%;">'
                    f'{deck_p(t["sub"])}</section>')
        if mode == "seal":
            # 酌墨：摘要之前一道朱砂短印，与章节印记同一笔
            seal = (f'<section style="width:12px;height:2px;background:{t["accent"]};'
                    f'margin-bottom:{self.g(10)}px;">{BR}</section>')
            return f'<section style="margin-bottom:{self.g(24)}px;">{seal}{deck_p(t["sub"])}</section>'
        if mode == "band":
            # 北霜：电讯头——摘要收在一道 2px 通栏实线之下，字重压住信息密度
            return (f'<section style="border-top:2px solid {t["text"]};padding-top:{self.g(9)}px;'
                    f'margin-bottom:{self.g(20)}px;">{deck_p(t["sub"], 600)}</section>')
        if mode == "plate":
            # 素作：16px 发丝线起印，摘要左右各收 6%，像展签的说明栏
            hair = (f'<section style="width:16px;height:1px;background:{t["line"]};'
                    f'margin-bottom:{self.g(10)}px;">{BR}</section>')
            return (f'<section style="margin-bottom:{self.g(26)}px;">{hair}'
                    f'<section style="margin:0 6%;">{deck_p(t["sub"])}</section></section>')
        if mode == "feature":
            # 特稿：摘要紧贴标题压下来，接近导语的重量，先声夺人。
            # 压缩靠上间距与字重，不靠压行高——行高取主题自己的 lead_leading，
            # 低于 1.65 会把摘要挤成一块铅字，读者在手机上分不清行从哪里开始。
            tight = f"line-height:{self.type['lead_leading']};"
            return (f'<section style="margin-bottom:{self.g(22)}px;">'
                    f'{deck_p(t["text"], 600, tight)}</section>')
        # 静纸：一道通栏发丝线起印，摘要右端收进 22%——留白是版面的第一件工具。
        # 收进 32% 会让 390px 上的摘要只剩四个字宽，折成四行、尾行掉一个字，
        # 那就不再是留白，是版面被咬掉一口。
        rule = (f'<section style="height:1px;background:{t["line"]};'
                f'margin-bottom:{self.g(12)}px;">{BR}</section>')
        return (f'<section style="margin-bottom:{self.g(24)}px;">{rule}'
                f'<section style="padding-right:22%;">{deck_p(t["sub"])}</section></section>')

    def h3(self, text):
        """三级标题：字重、字族、字距、上下间距与前置记号全部由 H3_AXIS 单一决定。

        三级标题不低于正文字号——层级靠字重、字距与间距建立，不靠缩小字号。
        """
        t = self.t
        weight, family, track, top, bottom, mark = H3_AXIS[t["h3"]]
        size = max(self.type["h3_size"], self.body)
        font = SERIF if family == "serif" else SANS
        lead = ""
        if mark == "seal":
            # 与章节印记同族的小朱点：只在二级标题下面复用一次，读者立刻认出这是同一套编号语言
            lead = (f'<span style="display:inline-block;width:5px;height:5px;background:{t["accent"]};'
                    f'margin-right:0.45em;vertical-align:middle;">{BR}</span>')
        elif mark == "hair":
            # 发丝记号是块级对象，必须落在段落之外：微信只接受 p 内的行内内容，
            # 把 section 塞进 p 会被 Gate 1 直接判非法结构。
            lead = (f'<section style="width:16px;height:1px;background:{t["line"]};'
                    f'margin-bottom:{self.g(6)}px;">{BR}</section>')
        heading = self.p((lead if mark == "seal" else "") + self.inline(text), size, t["text"],
                         f"font-weight:{weight};font-family:{font};{self.tr(track)}")
        if mark == "hair":
            heading = lead + heading
        return f'<section style="margin:{self.g(top)}px 0 {self.g(bottom)}px;">{heading}</section>'

    def para(self, text, next_kind="", initial=False):
        indent = self.grid.get("indent", 0)
        extra = "text-align:left;"
        if indent:
            extra += f"text-indent:{indent:g}em;"
        elif text.lstrip()[:1] in HANGING:
            # 悬挂标点只做在无缩进主题上：段首是引号时把它退进页边半个字，
            # 十行正文的起笔线才是一条直线；缩进主题的起笔线本来分两段，再悬挂就乱了。
            extra += "text-indent:-0.5em;"
        # 段距是全篇最容易被放大的数字：12–16px 的区间之外，读者读到的是“被拆散的句子”，
        # 不是“舒展的版面”。density 只在这个区间内挪动，不许把它推出边界。
        gap = self.grid["paragraph_gap"]
        if indent and next_kind != "p":
            gap += 4
        gap = min(PARAGRAPH_GAP_BAND[1], max(PARAGRAPH_GAP_BAND[0], round(gap * self.k)))
        inner = self.opening(text) if initial else self.inline(text)
        # 段距直接落在 p 上：少一层 section 包裹，微信清洗后结构更稳
        return self.p(inner, extra=extra + f"margin:0 0 {gap}px;")

    def opening(self, text):
        """开篇首字放大：只在无导语的正文开篇使用一次，是书页的起笔，不是每段装饰。

        “一、二、三、十”这类笔画稀少的字放大到 30px 就是一道横线或两条横线，
        读者会把它读成一个破折号——首字放大的前提是这个字放大之后仍然认得出是这个字。
        """
        head = text[:1]
        if self.initial != "raised" or not re.fullmatch(f"[{CJK}]", head) or head in SPARSE_GLYPHS:
            return self.inline(text)
        size = min(64, round(self.body * 1.9))
        lead = (f'<span style="font-size:{size}px;line-height:1.1;font-weight:600;">'
                f'<span leaf="">{H.escape(head)}</span></span>')
        return lead + self.inline(text[1:])

    def lead(self, text, src):
        t, mode = self.t, self.t["lead"]
        inner = self.inline(text, normalize=False)
        lead_size = min(self.type["lead_size"], 21) if len(plain(text)) > 48 else self.type["lead_size"]
        lead_style = (f'line-height:{self.type["lead_leading"]};font-weight:{self.type["lead_weight"]};'
                      f'{self.tr("caption")}')
        cite = self.p(self.leaf("—— " + src), self.cap, t["muted"], "margin-top:8px;") if src else ""
        if mode == "brief":
            return (f'<section style="margin:{self.g(4)}px 0 {self.g(24)}px;">'
                    + self.p(inner, lead_size, t["text"], lead_style + f"font-family:{self.font};") + cite + "</section>")
        if mode == "deck":
            # 信笺：导语从左侧起笔线出发，右端收进 8%——行尾参差是版面张力，
            # 不是没对齐；署名留在左下，与导语同一轴线，不做居中落款。
            return (f'<section style="margin:{self.g(4)}px 0 {self.g(27)}px;">'
                    + f'<section style="padding-right:8%;">'
                    + self.p(inner, lead_size, t["text"], lead_style + f"font-family:{self.font};")
                    + "</section>" + cite + "</section>")
        if mode == "ink":
            return (f'<section style="margin:{self.g(4)}px 0 {self.g(30)}px;">'
                    + self.p(inner, lead_size, t["text"], lead_style + f"font-family:{SERIF};") + cite + "</section>")
        if mode == "report":
            return (f'<section style="margin:{self.g(4)}px 0 {self.g(20)}px;">'
                    + self.p(inner, lead_size, t["text"], lead_style) + cite + "</section>")
        if mode == "plate":
            return (f'<section style="margin:{self.g(9)}px 0 {self.g(27)}px;">'
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
            return (f'<section style="margin:{self.g(4)}px 0 {self.g(24)}px;">'
                    + rows + cite + "</section>")
        raise ValueError(f"导语轴取值未实现：{mode}")

    def quote(self, text, src):
        t, mode = self.t, self.t["quote"]
        cite = self.p(self.leaf(f"—— {src}"), self.cap, t["muted"], "margin-top:8px;") if src else ""
        body = self.inline(text, normalize=False)
        qsize = self.type["quote_size"]
        if mode == "inset":
            # 信笺：引语缩进一栏、左侧只留一道发丝线；署名右对齐，与居中的金句彻底分开——
            # 别人的话往纸里退一格，说话人落在右下角，读者一眼看得出这是谁在说。
            hang = "text-indent:-0.55em;padding-left:0.55em;" if text.lstrip()[:1] in "\u300c\u300e“‘" else ""
            cite = (self.p(self.leaf(f"—— {src}"), self.cap, t["muted"], "margin-top:10px;text-align:right;")
                    if src else "")
            return (f'<section style="margin:{self.g(24)}px 0;padding:2px 0 2px 18px;'
                    f'border-left:1px solid {t["line"]};">'
                    + self.p(body, qsize, t["sub"], f"font-weight:500;line-height:1.76;font-family:{self.font};{hang}")
                    + cite + "</section>")
        if mode == "serif":
            return (f'<section style="margin:{self.g(24)}px 0;padding:2px 0;">'
                    + self.p(body, qsize, t["sub"], f"font-weight:400;line-height:1.78;font-family:{SERIF};")
                    + cite + "</section>")
        if mode == "report":
            # 简报引文：收窄行宽 + 次级色，靠版心而不是边框区别于正文
            return (f'<section style="margin:{self.g(20)}px 8%;padding:2px 0;">'
                    + self.p(body, qsize, t["sub"], "font-weight:500;line-height:1.70;") + cite + "</section>")
        if mode == "atelier":
            return (f'<section style="margin:{self.g(26)}px 6%;padding:2px 0;">'
                    + self.p(body, qsize, t["sub"], f"font-weight:400;line-height:1.78;font-family:{SERIF};letter-spacing:0.02em;")
                    + cite + "</section>")
        if mode == "folio":
            # 特稿的引语不退栏、不换色，只靠字号与字重的克制台阶把它从正文里拎出来：
            # 20px 已是正文之上的第二档，字重再加到 600 就会与小标题抢位。
            return (f'<section style="margin:{self.g(26)}px 0;padding:2px 0;">'
                    + self.p(body, qsize, t["text"], f"font-weight:500;line-height:1.68;font-family:{self.font};")
                    + cite + "</section>")
        if mode == "rule":
            return (f'<section style="margin:{self.g(24)}px 0;padding:0 4px;">'
                    + self.p(body, qsize, t["sub"], "font-weight:500;line-height:1.72;") + cite + "</section>")
        raise ValueError(f"引文轴取值未实现：{mode}")

    def peak(self, text):
        """重点句：全文最重的一句判断。字号由主题阶梯给出，各主题以字重、缩进与行距区分气质；
        字重一律低于同级章节标题，避免一句判断被扫成一个小标题。

        断行规则与章节标题一致：一句 22px 的话落在 280px 版心上只剩两行，尾行掉下一两个字
        就是排版事故——那句话读起来会像是被截断的。"""
        t, style = self.t, self.t["peak"]
        fam = f"font-family:{self.font};{self.tr('display')}"
        size = self.type["peak_size"]
        weight = PEAK_WEIGHT.get(style, 600)

        def rows(extra):
            lines = self.heading_lines(text, size)
            if not lines:
                return self.p(self.inline(text, normalize=False), size, t["text"], extra)
            return "".join(self.p(self.leaf(line), size, t["text"], extra) for line in lines)

        if style in ("quiet", "compact"):
            lh = 1.66 if style == "quiet" else 1.54
            pad = "0 2px" if style == "quiet" else "0"
            return (f'<section style="margin:{self.g(30)}px 0;padding:{pad};">'
                    + rows(f"font-weight:{weight};line-height:{lh};{fam}") + "</section>")
        if style == "rule":
            # 静纸：一句判断前留一道 20px 细线，作为版面里唯一的图形标记
            mark = f'<section style="width:20px;height:1px;background:{t["line"]};margin-bottom:12px;">{BR}</section>'
            return (f'<section style="margin:{self.g(30)}px 0;">{mark}'
                    + rows(f"font-weight:{weight};line-height:1.66;{fam}") + "</section>")
        if style == "bar":
            # 信笺：重点句靠“栏宽”而不是图形立住——上方一道发丝线把这段话从正文里划出来，
            # 右端收进 12%，行比正文短、字比正文大一号；不加大面积底色，也不做成居中金句。
            # 线只画到文字结束的地方：线的长度就是这句话的栏宽，多一寸都会读成章节分隔
            return (f'<section style="margin:{self.g(28)}px 0;">'
                    f'<section style="width:88%;padding-top:14px;border-top:1px solid {t["line"]};">'
                    + rows(f"font-weight:{weight};line-height:1.70;{fam}")
                    + "</section></section>")
        if style == "line":
            # 简报：加粗夹注，上下内边距收紧，读作一条被拎出来的电讯行而不是章节
            return (f'<section style="margin:{self.g(26)}px 0;padding:8px 0;">'
                    + rows(f"font-weight:{weight};line-height:1.60;{fam}") + "</section>")
        if style == "plate":
            # 器物牌：衬线常规字重、左右收进 6%，像展签上的说明
            return (f'<section style="margin:{self.g(30)}px 6%;padding:0;">'
                    + rows(f"font-weight:{weight};line-height:1.72;{fam}") + "</section>")
        raise ValueError(f"重点轴取值未实现：{style}")

    def unknown(self, label, lines):
        t = self.t
        head = self.micro(label or "未确认", extra="margin-bottom:6px;")
        body = "".join(self.p(self.inline(x), self.body - 1, t["sub"], "line-height:1.72;") for x in lines)
        return f'<section style="margin:{self.g(24)}px 0;">{head}{body}</section>' 

    def note(self, label, lines, tight=False):
        t = self.t
        body = "".join(self.p(self.inline(x), self.cap, t["sub"], "line-height:1.68;overflow-wrap:anywhere;") for x in lines)
        return f'<section style="margin:{self.g(8) if tight else self.g(16)}px 0 {self.g(16)}px;">{body}</section>'

    def data(self, lines, below=None):
        """离散关键数值：先验证 320px 可用宽度，再按各主题独有的设计语法呈现，绝不同质化降级。"""
        t = self.t
        items = [(v.strip(), lab.strip()) for v, _, lab in (ln.replace("|", "｜").partition("｜") for ln in lines)]
        mode, size = t["data"], self.type["data_size"]
        avail = content_px(t, 320)
        margin = f'margin:{self.g(28)}px 0 {below if below is not None else self.g(28)}px;'

        def values_fit(width):
            return all(text_px(value, size) + DATA_VALUE_SLACK <= width for value, _ in items)

        def value_label(v, lab, label_size):
            return (self.p(self.leaf(v), size, t["text"],
                           f"font-weight:600;line-height:1.25;font-family:{self.font};"
                           "font-variant-numeric:tabular-nums;white-space:nowrap;")
                    + self.p(self.inline(lab), label_size, t["sub"], "margin-top:6px;line-height:1.65;"))

        if mode in ("columns", "specimen"):
            gap = 16 if mode == "columns" else 12
            if mode != "columns":
                prefs = [2]
            elif len(items) == 2:
                prefs = [2]
            elif len(items) % 3 == 0:
                prefs = [3]
            elif len(items) % 3 == 2:
                prefs = [3, 2]
            else:
                prefs = [2]
            # 末行只落一项时，分栏就散了：四项排 2+2，绝不排 3+1。
            per = next((p for p in prefs if values_fit((avail - gap * (p - 1)) / p)), 1)
            if per >= 2:
                edge = t["text"] if mode == "columns" else t["line"]
                rows = []
                for i in range(0, len(items), per):
                    chunk = items[i:i + per]
                    cells = "".join('<section style="flex:1;min-width:0;padding:12px 0 0;'
                                    f'border-top:1px solid {edge};">'
                                    + value_label(v, lab, self.cap if mode == "specimen" else SMALL)
                                    + "</section>" for v, lab in chunk)
                    # 末行不满时留空位，而不是让最后一个数值撑满通栏：分栏要共享同一条网格。
                    cells += f'<section style="flex:1;min-width:0;">{BR}</section>' * (per - len(chunk))
                    rows.append(f'<section style="display:flex;gap:{gap}px;margin-top:{gap if i else 0}px;">{cells}</section>')
                return f'<section style="{margin}">{"".join(rows)}</section>'
            rows = [
                '<section style="'
                + (f"padding:13px 0 11px;border-top:1px solid {t['line']};margin-top:{8 if idx else 0}px;"
                   if mode == "specimen" else f"padding:11px 0;border-top:1px solid {t['text' if idx == 0 else 'line']};")
                + '">'
                + self.p(self.leaf(v), size, t["text"],
                         f"font-weight:600;line-height:1.28;font-family:{SERIF if mode == 'specimen' else self.font};"
                         "font-variant-numeric:tabular-nums;")
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

        spec = {
            # 信笺不设底色卡片：数值与标签靠一道发丝线与缩进分开，像信纸上的一栏小账
            "stack": (0.38, t["accent"], f"font-weight:600;line-height:1.3;font-family:{self.font};",
                      f"border-top:1px solid {t['line']};"),
            "ticker": (0.40, t["text"], "font-weight:700;line-height:1.25;",
                       f"border-top:2px solid {t['text']};border-bottom:1px solid {t['text']};"),
            "folio": (0.42, t["accent"], f"font-weight:700;line-height:1.18;font-family:{self.font};letter-spacing:-0.02em;",
                      f"border-top:3px solid {t['text']};"),
        }.get(mode)
        if not spec:
            raise ValueError(f"数据轴取值未实现：{mode}")
        ratio, v_col, v_ext, outer = spec
        side_fits = values_fit(avail * ratio)
        row_pad = {"stack": "padding:11px 0;", "ticker": "padding:9px 0;", "folio": "padding:12px 0;"}[mode]
        rows = []
        for idx, (v, lab) in enumerate(items):
            sep = f"border-top:1px solid {t['line']};" if idx and mode != "stack" else ""
            if side_fits:
                rows.append(
                    f'<section style="display:flex;align-items:baseline;gap:12px;{sep}{row_pad}">'
                    + self.p(self.leaf(v), size, v_col, f"width:{int(ratio * 100)}%;box-sizing:border-box;flex-shrink:0;{v_ext}font-variant-numeric:tabular-nums;white-space:nowrap;")
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


    def bars(self, lines, label="", below=None):
        """同单位分量比较。形态由数据形状决定，不由主题决定：
        三四项、标签短的离散量是一张图（竖柱，看得见高低差），
        项多或标签长的一串是一张表（横条，读得完标签）。"""
        t, rows, items = self.t, [], []
        for ln in lines:
            val, _, lab = ln.replace("|", "｜").partition("｜")
            items.append((val.strip(), lab.strip()))
        if any(not re.fullmatch(r"\d+(\.\d+)?", v) for v, _ in items):
            raise ValueError("bars 只接受非负十进制数值；负值请改用有符号轴的图表或文字，不能画成零")
        nums = [float(v) for v, _ in items]
        nums = [v if math.isfinite(v) else 0 for v in nums]
        mx = max(nums, default=0)
        gap = 14
        slot = (content_px(t, 320) - gap * (len(items) - 1)) / max(len(items), 1)
        column = (2 <= len(items) <= 4
                  and all(text_px(lab, SMALL) <= slot * 0.94 for _, lab in items)
                  and all(text_px(v, self.body) <= slot for v, _ in items))
        if label:
            rows.append(self.p(self.inline(label), SMALL, t["text"], f"font-weight:600;{self.tr('caption')}"))
        if column:
            cells, labels = [], []
            for (val, lab), num in zip(items, nums):
                height = (8 + round(num / mx * 88)) if mx else 8
                cells.append('<section style="flex:1;min-width:0;">'
                             + self.p(self.leaf(val), self.body, t["text"],
                                      f"font-weight:600;text-align:center;line-height:1.3;font-family:{self.font};"
                                      "font-variant-numeric:tabular-nums;white-space:nowrap;")
                             + f'<section style="height:{height}px;background:{t["accent"]};margin-top:{self.g(6)}px;">{BR}</section>'
                             + "</section>")
                labels.append('<section style="flex:1;min-width:0;">'
                              + self.p(self.inline(lab), self.cap, t["sub"], "text-align:center;line-height:1.55;")
                              + "</section>")
            # 基线就是零起点：竖柱一旦画在轴上，读者不必再被告知“从零开始”
            return (f'<section style="margin:{self.g(28)}px 0 {below if below is not None else self.g(28)}px;">'
                    + "".join(rows)
                    + f'<section style="display:flex;align-items:flex-end;gap:{gap}px;">{"".join(cells)}</section>'
                    + f'<section style="height:1px;background:{t["text"]};">{BR}</section>'
                    + f'<section style="display:flex;gap:{gap}px;margin-top:{self.g(8)}px;">{"".join(labels)}</section>'
                    + "</section>")
        # 零基线是读图前提，用一行小字交代；“最长条代表最大值”属于方法说明，留在侧车不印在版面
        rows.append(self.p(self.leaf("零起点"), 12, t["muted"], f"margin-top:2px;{self.tr('label')}"))
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

    def timeline(self, label, lines, below=None):
        """时间关系：日期挂在左侧栏、事件贴着一条竖轴往下走。
        这不是“带日期的列表”——日期必须能竖着扫读，事件必须在同一条轴上排队，
        读者才看得见间隔（两个月还是三年）本身就是信息。"""
        t = self.t
        rows, baseline = [], f"line-height:{self.body * self.t['leading']:.0f}px;"
        for idx, ln in enumerate(lines):
            when, _, what = ln.replace("|", "｜").partition("｜")
            last = idx == len(lines) - 1
            rows.append(
                '<section style="display:flex;gap:12px;">'
                + self.p(self.leaf(when.strip()), 12, t["muted"],
                         f"width:62px;flex-shrink:0;text-align:right;{baseline}font-weight:600;"
                         f"font-variant-numeric:tabular-nums;{self.tr('label')}")
                + f'<section style="flex:1;min-width:0;border-left:1px solid {t["line"]};'
                + f'padding-left:14px;' + ("" if last else f"padding-bottom:{self.g(16)}px;") + '">'
                + self.p(self.inline(what.strip()), self.body, t["text"], baseline)
                + "</section></section>"
            )
        head = self.p(self.inline(label), SMALL, t["text"], f"font-weight:600;margin-bottom:{self.g(14)}px;{self.tr('caption')}") if label else ""
        return (f'<section style="margin:{self.g(28)}px 0 {below if below is not None else self.g(28)}px;">'
                + head + "".join(rows) + "</section>")

    def table(self, rows, below=None):
        """语义表格：320px 下所有列均满足最小可读宽度才维持表格，否则自动降级为记录卡。"""
        t, out, mode = self.t, [], self.t["table"]
        if not rows or any(len(row) != len(rows[0]) for row in rows):
            raise ValueError("表格行列数不一致，不能对齐数据")
        hpad = table_pad(t) // 2
        table_avail = content_px(t, 320)
        if not table_fits(rows, 2 * hpad, self.margin):
            return self.table_stack(rows, below)
        widths = col_widths(rows, table_avail, 2 * hpad)
        if orphan_cells(rows, widths, table_avail, 2 * hpad):
            # 能放下不等于读得成：三列以上出现孤字行时，记录卡比一张挤扁的表清楚得多
            return self.table_stack(rows, below)
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
                    bg = ""
                    border = t["accent"] if i == 0 else t["line"]
                elif mode == "report":
                    pad = "8px 6px"
                    bg = ""
                    color = t["text"]
                elif mode == "atelier":
                    pad = "11px 7px"
                elif mode == "feature" and i == 0:
                    color, border = t["text"], t["text"]
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
        if len(rows) == 1:
            return f'<section style="margin:{self.g(24)}px 0;">' + "".join(self.p(self.inline(label), SMALL, t["sub"], "padding:6px 0;") for label in head) + "</section>"
        for n, row in enumerate(rows[1:], 1):
            # 若首列是名称，直接把它作为卡片标题；否则不写任何标号——“记录 01”只对编辑器有意义
            lead_key = plain(row[0]).strip() if row else ""
            use_first_as_title = bool(lead_key and len(lead_key) <= 18 and len(head) >= 3)
            pairs = list(zip(head[1:], row[1:])) if use_first_as_title else list(zip(head, row))
            card_title = (self.inline(head[0]) + self.leaf(" · ") + self.inline(row[0])) if use_first_as_title else ""
            cells = [
                '<section style="display:flex;gap:12px;padding:4px 0;">'
                + self.p(self.inline(label), self.cap, t["muted"], "width:32%;flex-shrink:0;min-width:0;line-height:1.65;")
                + self.p(self.inline(value), SMALL, t["text"],
                         "flex:1;min-width:0;line-height:1.65;font-variant-numeric:tabular-nums;")
                + "</section>"
                for label, value in pairs
            ]
            card_style = (
                # 记录卡不再铺底色：一条顶线与 12px 内陷足以分开两条记录，
                # 铺一片浅底反而让同一页出现第二块“背景”。
                f"padding:12px 0 10px;border-top:1px solid {t['line']};margin-top:{10 if n > 1 else 0}px;"
                if mode in ("warm", "atelier") else
                f"padding:11px 0 9px;border-top:1px solid {t['text' if n == 1 and mode in ('report', 'feature', 'ink') else 'line']};"
            )
            blocks.append(
                f'<section style="{card_style}">'
                + (self.p(card_title, SMALL, t["accent"] if mode == "feature" else t["text"],
                          f"margin-bottom:6px;font-weight:600;font-family:{self.font};") if card_title else "")
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
                    "folio": f"{number:02d}",
                }[mode]
            else:
                marker = {"index": "·", "dash": "—", "chinese": "·", "report": "—",
                          "atelier": "◇", "folio": "▪"}[mode]
            marker_color = t["accent"] if item.get("marker") or mode in ("dash", "folio") else t["muted"]
            marker_family = SERIF if mode in ("chinese", "atelier") else self.font
            marker_size = SMALL if (ordered or item.get("marker")) else self.body
            marker_html = self.p(
                self.leaf(marker),
                marker_size,
                marker_color,
                f"font-weight:{600 if ordered or item.get('marker') else 500};font-family:{marker_family};",
            )
            # 无序列表的记号按正文字号排，所以栏位必须按记号的真实宽度给：
            # 给 18px 的固定栏位，“—”会顶到正文上，读起来像一个错字而不是一个条目。
            width = (max(26, min(64, round(text_px(marker, SMALL) + 8))) if item.get("marker")
                     else 32 if mode in ("chinese", "atelier", "folio")
                     else 26 if ordered
                     else round(text_px(marker, marker_size)) + 12)

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
        """代码块不用灰底卡片：六个主题各自决定它如何与正文分开（细线的位置、粗细与缩进）。

        代码的身份由等宽字族承担，边界由细线承担；底色一加，页面上就多了一块“背景”，
        而白底排版里最贵的东西正是这块空白。
        """
        t, axis = self.t, self.t["code"]
        # break-word 只在长标识符真的放不下时才断词；anywhere 会把每一行都切碎
        line = (f"margin:0;font-family:{MONO};font-size:{SMALL}px;line-height:1.68;white-space:pre-wrap;"
                f"overflow-wrap:break-word;word-break:normal;tab-size:4;color:{t['text']};")
        rows = "".join(
            f'<p style="{line}">' + (self.leaf(ln) if ln.strip() else BR) + "</p>" for ln in body
        )
        label = self.micro(lang.upper(), extra=f"margin-bottom:8px;font-family:{MONO};") if lang else ""
        if axis == "flush":
            # 信笺：只用缩进与一道顶线起印，像信纸上抄下的一段
            box = f"padding:12px 0 0;border-top:1px solid {t['line']};"
        elif axis == "ink":
            box = f"padding:2px 0 2px 12px;border-left:2px solid {t['accent']};"
        elif axis == "signal":
            # 北霜：2px 信号色压顶，电讯式的块首，靠粗细而非底色划出层级
            box = f"padding:12px 0 0;border-top:2px solid {t['accent']};"
        elif axis == "plate":
            # 素作：展签的上下双线，像一张贴在卡纸上的说明
            box = f"padding:16px 4%;border-top:1px solid {t['line']};border-bottom:1px solid {t['line']};"
        elif axis == "folio":
            box = f"padding:14px 0;border-top:3px solid {t['text']};border-bottom:1px solid {t['line']};"
        else:
            box = f"padding:14px 2px;border-top:1px solid {t['line']};border-bottom:1px solid {t['line']};"
        return f'<section style="margin:{self.g(22)}px 0;{box}">{label}{rows}</section>'

    def img(self, alt, src, role, below=None, above=None):
        """图片只做构图与间距；职责/来源留在 Markdown 与侧车，不在版面印制作标签。"""
        t = self.t
        parts = (role or "").split()
        role0 = parts[0] if parts else ""
        mode = parts[1].lower() if len(parts) > 1 else ""
        mt = self.g(28) if above is None else above
        mb = below if below is not None else mt
        if not src or TODO.match(src):
            return ""
        img_extra, side = "max-width:100%;height:auto;display:block;", 0
        if mode in ("hero", "full-width", "bleed"):
            img_extra += "width:100%;"
        elif mode == "inset":
            side = 8
        elif mode == "detail":
            side = 4
        elif mode == "macro":
            side = 12
        # 收进版心的图也要撑满自己的框：否则窄图会缩在左边，与正文轴线断开
        if side:
            img_extra += "width:100%;"
        # 版心语法：主题决定图片宽度、图注对齐与字号，而不是给图片加衬底或描边
        cap_size, cap_extra, cap_align = self.cap, "margin-top:10px;line-height:1.7;", "left"
        axis = self.image_axis
        if axis == "soft":
            # 信笺：图片与图注都贴正文那条起笔线，连 8px 的内缩都不留——单轴版面里，
            # 图比文字窄一点就是错位，读者说不出哪里不对，只会觉得版面松了。
            side = 0
            cap_size, cap_extra, cap_align = self.cap, "margin-top:12px;line-height:1.72;", "left"
        elif axis == "mat":
            side = max(side, 4)
            cap_size, cap_extra, cap_align = self.cap, "margin-top:14px;line-height:1.70;", "center"
        elif axis == "inkline":
            cap_extra = "margin-top:9px;line-height:1.7;"
        elif axis == "report":
            cap_size, cap_extra = max(12, self.cap - 0.5), "margin-top:8px;line-height:1.6;"
        elif axis == "folio":
            # 特稿图注悬挂：首行顶格，续行与正文对齐，图与注读作一块
            cap_extra = "margin-top:10px;line-height:1.66;padding-left:1.1em;text-indent:-1.1em;"
        cap_style = f"{cap_extra}text-align:{cap_align};{self.tr('caption')}"
        cap = _caption_text(alt, role0)
        if mode == "bleed":
            # 出血：图反推到屏幕两缘，页边在图上取消；图注退回到正文起笔线。
            # 全篇只有少数几张图值得吃掉页边——尺寸的阶跃本身就是一次呼吸，
            # 每张都出血等于没有出血。
            caption = (f'<section style="padding:0 {self.pad_left}px;">'
                       + self.p(self.leaf(typo(cap)), cap_size, t["sub"], cap_style) + "</section>") if cap else ""
            return (f'<section style="margin:{mt}px -{self.pad_right}px {mb}px -{self.pad_left}px;">'
                    f'<img src="{H.escape(src)}" alt="{H.escape(alt or "")}" style="{img_extra}" />'
                    + caption + "</section>")
        box = f"margin:{mt}px {side}% {mb}px;" if side else f"margin:{mt}px 0 {mb}px;"
        return (
            f'<section style="{box}">'
            f'<img src="{H.escape(src)}" alt="{H.escape(alt or "")}" style="{img_extra}" />'
            + (self.p(self.leaf(typo(cap)), cap_size, t["sub"], cap_style) if cap else "")
            + "</section>"
        )

    def hr(self):
        """分节符：换场靠留白与一个极小的记号，不靠装饰线堆叠。"""
        t, axis = self.t, self.divider_axis
        box = f"margin:{self.g(30)}px 0;"
        if axis == "pause":
            # 暖信笺：只留一段呼吸，画任何记号都属于多余的排版动作
            return f'<section style="{box}">{BR}</section>'
        mark = {
            "short-rule": (24, 1, t["line"]),
            "hairline": ("100%", 1, t["line"]),
            "double": (18, 1, t["line"]),
            "seal": (6, 6, t["accent"]),
            "dot": (36, 2, t["accent"]),
        }[axis]
        width, height, color = mark
        unit = "" if isinstance(width, str) else "px"
        rule = (f'<section style="width:{width}{unit};height:{height}px;background:{color};margin:0 auto;">{BR}</section>')
        if axis == "double":
            rule += (f'<section style="width:10px;height:1px;background:{color};'
                     f'margin:4px auto 0;">{BR}</section>')
        return f'<section style="{box}text-align:center;">{rule}</section>'

    def signature(self, meta):
        t, out = self.t, []
        if meta.get("cta"):
            out.append(self.p(self.inline(meta["cta"]), SMALL, t["sub"]))
        if meta.get("bio"):
            out.append(self.p(self.leaf(typo(meta["bio"])), self.cap, t["muted"], "margin-top:10px;"))
        return (f'<section style="margin-top:{self.g(32)}px;">'
                + "".join(out) + "</section>") if out else ""

    def toc(self, heads):
        """目录即版面索引：目录与章节开门说同一种语言，读者看目录就知道这是哪种刊物。

        heads 是已经剥掉手写序号的标题；编号与正文共用 render() 给出的同一个序号，
        因此目录与章节页不可能出现两套数字。
        """
        t, mode = self.t, self.t["heading"]
        # 目录与正文共用同一个序号来源：正文怎么编号，目录就怎么编号。
        num_w = 22
        rows = []
        for n, h in enumerate(heads, 1):
            label = plain(h)
            top = self.g(8) if n > 1 else 0
            rows.append(
                f'<section style="display:flex;align-items:baseline;gap:10px;margin-top:{top}px;">'
                + self.p(self.leaf(f"{n:02d}"), 12, t["accent"] if mode in ("rail", "brief", "folio") else t["muted"],
                         f"width:{num_w}px;flex-shrink:0;font-weight:600;{self.tr('label')}"
                         "font-variant-numeric:tabular-nums;")
                + self.p(self.leaf(label), SMALL, t["text"],
                         f"flex:1;min-width:0;line-height:1.66;font-family:{self.font};"
                         + ("font-weight:600;" if mode == "folio" else ""))
                + "</section>"
            )
        if mode == "rail":
            # 信笺：目录贴着正文起笔线排，标签用一道短线起头；不加框线，靠行距与编号分栏
            box = f"margin:{self.g(9)}px 0 {self.g(27)}px;padding:0;"
            align = ""
        elif mode == "seal":
            # 卷目：无框线，靠行距与衬线成篇——框线会把书页变成表单
            box = f"margin:{self.g(10)}px 0 {self.g(30)}px;padding:{self.g(4)}px 0;"
            align = ""
        elif mode == "atelier":
            # 素作：上下双线夹住目录，像一张展签
            box = (f"margin:{self.g(9)}px 0 {self.g(27)}px;padding:{self.g(12)}px 0;"
                   f"border-top:1px solid {t['line']};border-bottom:1px solid {t['line']};")
            align = ""
        elif mode == "brief":
            # 北霜：顶部一道 2px 实线收口，与章节开门下方那道通栏细线首尾呼应
            box = (f"margin:{self.g(8)}px 0 {self.g(24)}px;padding:{self.g(12)}px 0;"
                   f"border-top:2px solid {t['text']};")
            align = ""
        elif mode == "folio":
            # 特稿：无框线，让加粗条目与 accent 编号自己撑起层级
            box = f"margin:{self.g(8)}px 0 {self.g(28)}px;padding:0;"
            align = ""
        else:
            # 静纸：左发丝线做栏位，编号挂在线上——与章节标题的悬挂编号同一套网格
            box = (f"margin:{self.g(6)}px 0 {self.g(30)}px;padding:{self.g(12)}px 0 "
                   f"{self.g(12)}px {self.g(14)}px;border-left:1px solid {t['line']};")
            align = ""
        if mode == "rail":
            # 标签在左、发丝线向右跑到底：一条静默的索引线，同时给出“从这里开始读”的方向
            head = (f'<section style="display:flex;align-items:center;gap:{self.g(9)}px;'
                    f'margin-bottom:{self.g(12)}px;">'
                    + self.p(self.leaf(t["toc_label"]), 12, t["muted"], f"font-weight:600;{self.tr('label')}")
                    + f'<section style="flex:1;height:1px;background:{t["line"]};">{BR}</section>'
                    "</section>")
        else:
            head = self.p(self.leaf(t["toc_label"]), 12, t["muted"],
                          f"margin-bottom:{self.g(12)}px;font-weight:600;{self.tr('label')}{align}")
        return f'<section style="{box}">{head}{"".join(rows)}</section>'


def api_title(t):
    return typography.publish(t.replace("|", "｜")).strip()


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


def _near_text(blocks, idx):
    """相邻散文/注释文本：供来源与证据门禁读取，不要求版面出现模板标签。"""
    out = []
    for j in (idx - 1, idx + 1):
        if 0 <= j < len(blocks):
            k, b = blocks[j]
            if k == "note":
                out += list(b[1])
            elif k == "p":
                out.append(b)
    return " ".join(out)


def _asset_gate(meta, blocks, base, key=None):
    must, should = [], []
    th = THEMES.get(key or meta.get("theme", "paper"), THEMES["paper"])
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
        mods = {x.lower() for x in tokens[2:]}
        unknown_mods = mods - {"ai", "generated", "parallel"}
        if unknown_mods:
            must.append(f"图片修饰词未识别：{'、'.join(sorted(unknown_mods))}")
        if "parallel" in mods:
            must.append("parallel 只用于 comparison；窄屏按单列纵向呈现，已无此声明的作用")
        if role0 in FACT_ROLES and not (alt or "").strip():
            must.append("证据类图必须写清出处 / 口径 / 时间；解释图也需说明")
        if role0 in FACT_ROLES and not _has_adjacent_explanation(blocks, idx):
            should.append(f"图片 {src}（{role0}）未紧邻解释文字：说明/证据类图片须靠近其解释对象")
        shown = _caption_text(alt, role0)
        if shown:
            # 图注会被印出来，就同样不许掉孤字：尾行只剩一两个字时，读到的是半句话。
            folded = _greedy_wrap(shown, th["grid"]["caption"], content_px(th, 320),
                                  th["tracking"]["caption"])
            if len(folded) > 1 and len(folded[-1]) <= 2:
                should.append(f"图注在 320px 下折出孤字行（尾行“……{folded[-1]}”）："
                              f"压到 {len(folded[0]) * (len(folded) - 1)} 字以内，或把定语删掉")
        if role0 in PROVENANCE_ROLES and re.search(r"(?:^|\s)(?:ai|generated)(?:\s|$)", role, re.I):
            must.append(f"图片 {src}：AI 生成图不能承担资料/实拍职责；请改用真实来源或改为隐喻/场景示意")
        if role0 in PROVENANCE_ROLES:
            caption = " ".join([alt or "", role or "", _near_text(blocks, idx)])
            has_source = re.search(r"来源|馆藏|摄影|摄于|拍摄|archive|collection|commons|wikimedia|https?://", caption, re.I)
            has_rights = re.search(r"授权|许可|版权|CC0|CC BY|©|rights|license|公有领域|public domain", caption, re.I)
            placeholder = re.search(r"(?:来源|授权|许可)[：:]\s*(?:未知|待补|无)|(?:TODO|TBD)", caption, re.I)
            if not (has_source and has_rights) or placeholder:
                must.append(f"图片 {src}：资料图/实拍须分别写明实际来源与授权；关键词或“未知/待补”不构成验收")
        if role0 in {"证据", "数据", "evidence", "data"}:
            context = " ".join([alt or "", role or "", _near_text(blocks, idx)])
            if re.search(r"(?:^|\s)(?:ai|generated)(?:\s|$)|AI\s*生成|生成式|人工智能生成", context, re.I):
                must.append("生成示意图不能承担证据/数据职责")
            elif not source_urls(context):
                must.append("证据/数据图片缺少有效、可核对的 HTTP(S) 来源链接")
        if not src or TODO.match(src):
            must.append(f"图片待补，不能进入发布：{src or '(空路径)'}")
            continue
        p = local_path(src, base)
        if not os.path.isfile(p):
            must.append(f"图片不存在：{src}（本地化后再交付，或写成 todo）")
            continue
        wh, kb = file_image_info(p)[1], os.path.getsize(p) // 1024
        if not wh or not all(wh):
            must.append(f"图片不是可识别格式：{src}")
        elif wh[0] < 600:
            should.append(f"{os.path.basename(src)} 分辨率偏低，核对手机端显示清晰度（{wh[0]}×{wh[1]}）")
        if kb > 1024:
            should.append(f"{os.path.basename(src)} 体积 {kb}KB：建议压到 1MB 以内再发布")

    modes = [_img_mode(b) for _, b in imgs if _img_mode(b)]
    if len(modes) >= 3 and len(set(modes)) == 1 and modes[0] not in ("sequence", "comparison"):
        should.append(f"全文 {len(modes)} 张图均为同一表达方式 {modes[0]}：视觉叙事同质化，请按封面/场景/概念/解释/收束差异化景别与构图")
    focal = (meta.get("cover_focal") or "").strip()
    if focal and not re.fullmatch(r"(?:100|[0-9]{1,2})% (?:100|[0-9]{1,2})%", focal):
        must.append("cover_focal 格式应为“x% y%”（0–100），例如 30% 45%")
    cover = (meta.get("cover") or "").strip()
    if not cover:
        should.append(f"没有封面：公众号草稿需要一张 {COVER_RATIO}:1 封面（见 references/direction.md）")
    elif not TODO.match(cover):
        if not (meta.get("cover_note") or "").strip():
            must.append("封面缺少 cover_note：写明来源、授权与是否 AI 生成")
        p = local_path(cover, base)
        if not os.path.isfile(p):
            must.append(f"封面文件不存在：{cover}")
        else:
            wh = file_image_info(p)[1]
            if not wh or not all(wh):
                must.append("封面不是可识别图片")
            else:
                w, h = wh
                ratio = w / h
                if w < COVER_MIN_W:
                    should.append(f"封面 {w}×{h}：宽度低于建议基线 {COVER_MIN_W}px，复核缩略清晰度")
                if not COVER_BAND[0] <= ratio <= COVER_BAND[1]:
                    should.append(f"封面 {w}×{h}（{ratio:.2f}:1）：超出微信 {COVER_RATIO}:1 常见区间，确认主体位于中央安全区")
    # 同一张图出现两次，读者第二次什么也没多知道：路径重复与字节完全相同都算重复
    paths = [b[1] for _, b in imgs if b[1] and not TODO.match(b[1])]
    counts = {}
    for src in paths:
        counts[src] = counts.get(src, 0) + 1
    for src, count in counts.items():
        if count > 1:
            must.append(f"图片 {src} 在正文出现 {count} 次：重复图不提供信息增量，删掉多余的一张")
    digests = {}
    for src in dict.fromkeys(paths):
        if counts[src] > 1:
            continue
        path = local_path(src, base)
        if not os.path.isfile(path):
            continue
        digest = sha256(path)
        if digest in digests:
            must.append(f"图片 {digests[digest]} 与 {src} 内容完全相同：两张一样的图占两份版面，不占两份信息")
        else:
            digests[digest] = src
    if cover and not TODO.match(cover) and cover in counts:
        should.append("封面同时被用作正文插图：读者已经见过这一张，正文首图应建立新的场景或证据")
    chars = doc_len(blocks)
    budget = 1 if chars <= 800 else 3 if chars <= 2000 else 4
    if len(imgs) > budget:
        should.append(f"正文 {len(imgs)} 张图超出本文 {chars} 字的图片预算（{budget} 张）："
                      "多出来的图在稀释节奏，逐张问它替哪一句说话，说不出就删")
    return must, should


def _data_gate(meta, blocks, key):
    must, should = [], []
    th = THEMES.get(key or meta.get("theme", "paper"), THEMES["paper"])
    for i, (k, b) in enumerate(blocks):
        if k not in ("bars", "data"):
            continue
        note = blocks[i + 1][1] if i + 1 < len(blocks) and blocks[i + 1][0] == "note" else ("", [])
        # 来源行接受链接、年份（含“（2025）”全角括号）、季度/半年/全年口径、标准号，或明写假设/演示
        source = " ".join(note[1])
        if not re.search(r"https?://\S+|\d{4}\s*(?:年|[-–/]\s*\d{1,2}|[)）]|$)"
                         r"|Q[1-4]|[1-4一二三四]\s*季度|上半年|下半年|全年"
                         r"|(?:EN|DIN|ISO|GB|ANSI|JIS)\s?/?\s?[A-Z]?\s?\d{2,5}"
                         r"|假设|演示|非统计|推算|测算|常见值|通行值", source):
            must.append(f"{k} 缺少紧邻来源 note：写清主体与日期（或一行地址），或明写假设/演示")
        if k == "data":
            if not b[1]:
                must.append("data 不能为空")
            room = content_px(th, 320)
            for line in b[1]:
                val, _, lab = line.replace("|", "｜").partition("｜")
                if not val.strip() or not lab.strip():
                    must.append("data 必须有数值与标签")
                elif text_px(val.strip(), th["type"]["data_size"]) + DATA_VALUE_SLACK > room:
                    must.append(f"data 数值在 320px 无法单行完整显示：{val.strip()[:24]}；请精简口径或改用文字")
            continue
        if not re.search(r"单位[：:]\s*\S+", b[0]):
            must.append("bars 必须声明单一单位，格式为“说明（单位：项）”。不同单位不能共轴")
        items = [(v.strip(), lab.strip()) for v, _, lab in (x.replace("|", "｜").partition("｜") for x in b[1])]
        for v, lab in items:
            if not re.fullmatch(r"\d+(\.\d+)?", v):
                must.append(f"bars 的值必须是非负十进制数字：{v or '（空）'}；负值不能为零起点柱图")
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
    for i, (k, b) in enumerate(blocks):
        if k == "h2":
            # 章节标题是版面的门框：超过两行就不再是标题，而是段落；宽度按 375 设计基准算
            size = th["type"]["heading_size"]
            lines = _greedy_wrap(plain(b), size, content_px(th, DESIGN_WIDTH), th["tracking"]["display"])
            if len(lines) > 2:
                should.append(f"章节标题“{plain(b)[:16]}”在 375px 下折成 {len(lines)} 行：压到 "
                              f"{len(lines[0]) * 2} 字以内，或把定语拆进正文")
            # 编号重复是唯一会让读者当场出戏的错误：左边一个 02、标题又以“二、”开头。
            # 渲染器已统一剥离，这两条门禁守的是“剥离失败”的情形，而不是正常稿件。
            if has_ordinal(b):
                core = split_ordinal(b)
                if core == plain(b).strip():
                    must.append(f"章节标题“{plain(b)[:16]}”只有序号没有标题正文：补上标题，否则编号会重复出现")
                elif has_ordinal(core):
                    must.append(f"章节标题“{core[:16]}”剥掉一层序号后仍以序号开头：全文编号会重复，请人工确认层级")
        if k == "hr":
            prev_k = blocks[i - 1][0] if i > 0 else ""
            next_k = blocks[i + 1][0] if i + 1 < len(blocks) else ""
            if prev_k == "h2" or next_k == "h2":
                should.append("分隔线紧邻 H2 标题：章节标题已承担转场，渲染时已合并冗余分隔线")
        if k == "table":
            if not b or any(len(row) != len(b[0]) for row in b):
                must.append("表格行列数不一致，不能对齐数据")
            elif not table_fits(b, table_pad(th), th.get("margin", 0)):
                should.append(f"表格 {len(b[0])} 列在 320px 无法维持可读列宽，已自动降级为记录卡堆叠")
            elif orphan_cells(b, col_widths(b, content_px(th, 320), table_pad(th)),
                              content_px(th, 320), table_pad(th)):
                should.append(f"表格在 320px 下 {len(b[0])} 列会折出孤字行，已自动降级为记录卡——"
                              "想保住表格就减一列或把单元格压短")
        if k == "timeline":
            rows = [ln for ln in b[1] if ln.strip()]
            if len(rows) < 2:
                must.append("timeline 至少两行：只有一个时间点就没有间隔可读，改用一句正文")
            for ln in rows:
                when, _, what = ln.replace("|", "｜").partition("｜")
                if not when.strip() or not what.strip():
                    must.append(f"timeline 每行须为“日期｜事件”：{ln[:24]}")
                    break
                if text_px(when.strip(), 12) > 60:
                    must.append(f"timeline 日期列放不下“{when.strip()[:12]}”：压到 6 字以内（如 2024.06）")
                    break
        if k == "note":
            label, lines = b[0] or "", b[1]
            text = [ln for ln in lines if not re.fullmatch(r"\s*https?://\S+\s*", ln)]
            if re.search(r"来源|口径", label) and len(text) > 2:
                must.append("数据来源与口径过长：控制在两行内（来源一行、口径一行），URL 单独成行不计")
            for ln in text:
                if len(ln) > 64:
                    should.append(f"注释行偏长（{len(ln)} 字）：来源短写“主体（日期）”，口径一句话")
                    break
    title = meta.get("title", "")
    if meta.get("kicker"):
        should.append("kicker 不再输出：栏目行、期号与分类串是装饰性信息，读者版面已取消；"
                      "请删除 frontmatter 里的这一行")
    if not api_title(title):
        must.append("缺少标题")
    deck = meta.get("deck", "")
    if deck:
        # 摘要行是全篇第一句被印出来的话，同样不许掉孤字
        folded = _greedy_wrap(plain(deck), th["type"]["deck_size"],
                              content_px(th, 320) * (0.78 if th["header"] == "rule" else 1),
                              th["tracking"]["caption"])
        if len(folded) > 1 and len(folded[-1]) <= 2:
            should.append(f"摘要行在 320px 下折出孤字行（尾行“……{folded[-1]}”）："
                          f"压到 {len(folded[0]) * (len(folded) - 1)} 字以内")

    for field, value, cap in (("title", api_title(title), 32), ("author", meta.get("author", ""), 16), ("digest", meta.get("digest", ""), 120)):
        if len(value) > cap:
            must.append(f"{field} 超过发布上限 {cap}：请编辑收窄，不静默截断")
    if meta.get("density", "standard") not in ("dense", "standard", "airy"):
        must.append(f"density“{meta['density']}”不存在：仅支持 dense / standard / airy")
    return must, should


def compose_gate(meta, blocks, base=".", key=None, review=None):
    must, should = [], []
    for m, s in (_asset_gate(meta, blocks, base, key), _data_gate(meta, blocks, key), _structure_gate(meta, blocks, key)):
        must.extend(m)
        should.extend(s)
    review = review or audit(meta, blocks)
    for issue in review["issues"]:
        if issue["severity"] == "must":
            must.append(f"编辑必须修 · {issue['code']} · {issue['location']}：{issue['problem']} → {issue['action']}")
    return list(dict.fromkeys(must)), list(dict.fromkeys(should))


PREVIEW_TEMPLATE = os.path.join(HERE, "..", "assets", "preview.template.html")
VIEWPORTS = (320, 360, 375, 390, 430)
ANDROID_SANS = "'Roboto','HarmonyOS Sans SC','MiSans','Noto Sans CJK SC','Source Han Sans SC',sans-serif"
ANDROID_SERIF = "'Noto Serif CJK SC','Noto Serif SC','Source Han Serif SC','Source Han Serif CN',serif"
ANDROID_MONO = "'Roboto Mono','Droid Sans Mono','Noto Sans Mono',monospace"


def preview_page(meta, theme_name, native, body, base=".", cover=None):
    """移动预览：五宽度、双字体栈、微信界面模拟；只呈现读者可见内容，复制只含正文。"""
    with open(PREVIEW_TEMPLATE, encoding="utf-8") as stream:
        html = stream.read()
    viewports = "".join(
        f'<button type="button" data-w="{w}" aria-pressed="{"true" if w == 375 else "false"}">{w}</button>'
        for w in VIEWPORTS)
    fontmap = json.dumps({"pairs": [[SANS, ANDROID_SANS], [SERIF, ANDROID_SERIF], [MONO, ANDROID_MONO]]},
                         ensure_ascii=False)
    cover_js = json.dumps(cover or {}, ensure_ascii=False).replace("</", "<\\/")
    for token, value in (
        ("__TITLE__", H.escape(api_title(meta.get("title", "")))),
        ("__THEME__", H.escape(theme_name)),
        ("__NATIVE__", native),
        ("__BODY__", body),
        ("__VIEWPORTS__", viewports),
        ("__FONTMAP__", fontmap),
        ("__COVER__", cover_js),
    ):
        html = html.replace(token, value)
    return html


def preview_image(src, base):
    """预览内嵌图：读一次字节，同时得到 MIME 与是否可内嵌；不查平台 MIME 注册表。"""
    if re.match(r"^(?:[a-z][a-z0-9+.-]*:|//)", src, re.I):
        return ""
    path = local_path(src, base)
    if not os.path.isfile(path):
        return src
    with open(path, "rb") as stream:
        data = stream.read()
    mime, size = image_info(data)
    if not mime or not size:
        return src
    return f"data:{mime};base64," + base64.b64encode(data).decode("ascii")


def strip_editorial(blocks):
    """摘掉交代改稿动作的模块（编辑说明一类），并在侧车留痕；不改写成正文。"""
    kept, dropped, skipping = [], [], False
    for kind, b in blocks:
        text = block_text(kind, b)
        if kind in ("h2", "h3"):
            if typography.is_editorial(text):
                skipping, _ = True, dropped.append(text.strip())
                continue
            skipping = False
        elif skipping:
            dropped.append(text.strip()[:40])
            continue
        if kind in ("note", "p", "unknown") and typography.is_editorial(text):
            dropped.append(text.strip()[:40])
            continue
        kept.append((kind, b))
    return kept, dropped


def render(md, theme=None, plain_text=False):
    meta, blocks = parse(md, plain_text=plain_text)
    blocks, removed_editorial = strip_editorial(blocks)
    key = theme or meta.get("theme", "paper")
    if key not in THEMES:
        raise ValueError(f"未知主题 {key}，可选：{', '.join(THEMES)}")
    r = R(THEMES[key], meta.get("density", "standard"))
    # 章节编号在这里一次性决定：标题里手写的「二、」「02、」「第三章」一律剥掉，
    # 由渲染器按出现顺序统一给出 01…nn；标题与目录读的是同一份结果。
    # 渲染层任何地方都不再自己判断“这个标题有没有序号”。
    h2_display, seq = {}, 0
    for i, (kind, text) in enumerate(blocks):
        if kind != "h2":
            continue
        seq += 1
        h2_display[i] = (split_ordinal(text), seq)
    out = [r.masthead(meta)]
    heads = [h2_display[i][0] for i, (kind, _) in enumerate(blocks) if kind == "h2"]
    # 目录是刊头与正文之间的版面索引：插在第一个章节标题之前。
    # 早先按“第一段之后”插入，一旦正文没有引言段，目录就会落进第一章内部，
    # 读者读第一章时被一张全篇目录横断——位置错了，再好看的目录也是错的。
    toc_on = meta.get("toc", "").lower() in ("true", "yes", "1") and len(heads) >= 3
    toc_at = next((i for i, (k, _) in enumerate(blocks) if k == "h2"), None) if toc_on else None
    has_lead = any(k == "lead" for k, _ in blocks)
    attach = ("bars", "data", "table", "img", "timeline")
    consumed = set()
    seen_para = False
    # 章节的分量由它在全文里的位置与长度决定：开篇一章立门框，两段就过去的短章只是一次停顿。
    h2_at = [i for i, (k, _) in enumerate(blocks) if k == "h2"]
    section_weight = {}
    for order, idx in enumerate(h2_at):
        end = h2_at[order + 1] if order + 1 < len(h2_at) else len(blocks)
        opens_image = idx + 1 < len(blocks) and blocks[idx + 1][0] == "img"
        section_weight[idx] = ("open" if order == 0
                               else "beat" if (end - idx - 1 <= 2 and not opens_image) else "normal")

    for i, (kind, b) in enumerate(blocks):
        if i in consumed:
            continue
        nxt = blocks[i + 1][0] if i + 1 < len(blocks) else ""
        prev = blocks[i - 1][0] if i > 0 else ""
        below = 8 if nxt == "note" else None

        if toc_at is not None and i == toc_at:
            out.append(r.toc(heads))
            toc_at = None

        if kind == "h2":
            text, number = h2_display.get(i, (b, None))
            out.append(r.h2(text, number, section_weight.get(i, "normal")))
        elif kind == "h3":
            out.append(r.h3(b))
        elif kind == "p":
            out.append(r.para(b, next_kind=nxt, initial=not seen_para and not has_lead))
            seen_para = True
        elif kind == "lead":
            out.append(r.lead(b[0], " ".join(b[1])))
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
        elif kind == "timeline":
            out.append(r.timeline(b[0], b[1], below=below))
        elif kind == "table":
            out.append(r.table(b, below=below))
        elif kind == "list":
            out.append(r.lst(b))
        elif kind == "code":
            out.append(r.code(*b))
        elif kind == "img":
            parts = (b[2] or "").split()
            mode = parts[1].lower() if len(parts) > 1 else ""
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
                if _img_mode(other) == "comparison":
                    after_pair = blocks[i + 2][0] if i + 2 < len(blocks) else ""
                    mb = 8 if after_pair == "note" else r.g(24)
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
            raise ValueError(f"未知原语 ::: {kind}（可用：peak / note / unknown / data / bars / timeline）")

    sig = r.signature(meta)
    if sig:
        out.append(sig)
    t = THEMES[key]
    # 页边左右对称，全篇共用一条起笔线：标题、导语、正文、引语、图注、图表都从这里出发。
    body = (f'<section style="background:{t["page"]};font-family:{r.reading_font};font-size:{r.body}px;color:{t["text"]};'
            f'line-height:{t["leading"]};letter-spacing:normal;text-align:left;line-break:strict;overflow-wrap:break-word;'
            f'padding:{r.g(2)}px {r.pad_right}px {r.g(6)}px {r.pad_left}px;">'
            + typography.sanitize_html("".join(out)) + "</section>")
    return key, meta, blocks, body, removed_editorial


def contrast_checks(theme):
    t = THEMES[theme]
    return [{"foreground_role": role, "foreground": t[role], "background": t[bg],
             "background_role": bg, "ratio": round(contrast(t[role], t[bg]), 3),
             "required": 4.5, "pass": contrast(t[role], t[bg]) >= 4.5}
            for role, bg in contrast_pairs(t)]


def safety_read(path):
    with open(path, "rb") as stream:
        return stream.read()


def build(md_path, theme=None, out=None, against=None, ledger=None, delivery=False):
    """Read → validate → stage → commit. Manifest is written last, never a false PASS."""
    base = os.path.dirname(os.path.abspath(md_path))
    with open(md_path, "rb") as stream:
        source_bytes = stream.read()
    source_text = source_bytes.decode("utf-8")
    source_digest = hashlib.sha256(source_bytes).hexdigest()
    key, meta, blocks, body, removed_editorial = render(
        source_text, theme, plain_text=os.path.splitext(md_path)[1].lower() == ".txt")
    out = os.path.abspath(out or f"{os.path.splitext(md_path)[0]}_{key}.html")
    if os.path.splitext(out)[1].lower() != ".html":
        raise ValueError("正文输出必须使用 .html 扩展名，拒绝覆盖源稿或其他文件")
    out = output_path(out)
    out_base = os.path.dirname(out)
    prev = output_path(os.path.splitext(out)[0] + "_预览.html")
    meta_path = output_path(os.path.splitext(out)[0] + ".meta.json")
    protected = {os.path.realpath(md_path)}
    for optional in (against, ledger):
        if optional:
            protected.add(os.path.realpath(optional))
    if {os.path.realpath(p) for p in (out, prev, meta_path)} & protected or len({out, prev, meta_path}) != 3:
        raise ValueError("输出路径与源稿/原稿/台账冲突，或正文、预览、侧车彼此重名")
    os.makedirs(out_base, exist_ok=True)
    deliver = out_base if delivery else ""
    if delivery and os.path.basename(out) != "正文.html":
        raise ValueError("交付目录的正文必须命名为 正文.html")
    previous_manifest = None
    if deliver and os.path.exists(deliver):
        if not os.path.isdir(deliver) or os.path.islink(deliver):
            raise ValueError("交付目标必须是真实目录")
        if os.listdir(deliver):
            manifest_path = os.path.join(deliver, "交付清单.json")
            if not os.path.isfile(manifest_path):
                raise ValueError("交付目录非空且没有本工具清单；拒绝混入或覆盖用户文件，请使用空目录")
            with open(manifest_path, encoding="utf-8") as stream:
                previous_manifest = json.load(stream)
            for name, digest in previous_manifest.get("files", {}).items():
                path = local_path(name, deliver)
                if not os.path.isfile(path) or sha256(path) != digest:
                    raise ValueError(f"既有交付已手工改动或缺失，拒绝覆盖：{name}；请使用新目录")
            actual = {os.path.relpath(os.path.join(root, name), deliver).replace(os.sep, "/")
                      for root, _, names in os.walk(deliver) for name in names} - {"交付清单.json"}
            if actual != set(previous_manifest.get("files", {})):
                raise ValueError("交付目录存在清单外文件；拒绝混入，请使用空目录")

    asset_sources = [b[1] for k, b in blocks if k == "img" and b[1] and not TODO.match(b[1])]
    cover = (meta.get("cover") or "").strip()
    if cover and not TODO.match(cover):
        asset_sources.append(cover)
    originals = {}
    for src in dict.fromkeys(asset_sources):
        path = local_path(src, base)
        if os.path.realpath(path) in protected or os.path.realpath(path) in {out, prev, meta_path}:
            raise ValueError(f"素材与输入或输出文件冲突：{src}")
        if not os.path.isfile(path):
            continue
        with open(path, "rb") as stream:
            originals[src] = stream.read()
        target = local_path(src, out_base)
        if os.path.islink(os.path.join(out_base, src)):
            raise ValueError(f"素材输出不能是符号链接：{src}")
        if os.path.isfile(target) and target != os.path.realpath(path) and safety_read(target) != originals[src]:
            raise ValueError(f"输出素材冲突，拒绝覆盖：{src}")

    review = audit(meta, blocks)
    m1, s1 = check(body)
    m2, s2 = compose_gate(meta, blocks, base, key, review)
    s2 = [f"平台层建议：{x}" for x in s1] + s2
    facts_diff = voice_diff = None
    ledger_rows, ledger_problems = [], []
    if against:
        original_meta, original_blocks = parse(open(against, encoding="utf-8").read())
        facts_diff = compare_facts(original_blocks, blocks, original_meta, meta)
        declared = {x.strip() for x in (meta.get("removed_facts") or "").replace("，", ",").split(",") if x.strip()}
        for item in facts_diff["dropped"]:
            if item in declared:
                continue
            change, why = classify_fact_change(blocks, "num", item) if re.search(r"\d", item) else ("lost", "")
            if change == "lost":
                change, why = classify_fact_change(blocks, "date", item)
            message = f"原稿事实单元消失：{item}" + (f"；{why}" if why else "")
            (s2 if change in ("moved", "rounded") else m2).append(message + "；须回源确认，有意删除须声明 removed_facts")
        for item in introduced_without_source(blocks, facts_diff["introduced"]):
            m2.append(f"改稿新增事实单元“{item}”附近缺少可核对来源")
        for change in facts_diff["precision_changes"] + facts_diff["qualifier_changes"] + facts_diff["qualifier_occurrence_changes"]:
            m2.append(f"事实精度或限定词变化需回源确认：{describe_change(change)}")
        for quote in facts_diff["dropped_quotes"] + facts_diff["introduced_quotes"]:
            m2.append(f"直接引语变化需逐字回源：{quote[:40]}")
        if facts_diff["code_changes"]:
            m2.append("代码语言、内容、顺序或空行发生变化；教程须逐项验证，不能视作润色")
        voice_diff = compare_voice(original_blocks, blocks)
        s2.extend(f"作者声音形态变化：{x['mark']} {x['original']} → {x['edited']}" for x in voice_diff["changes"])
    if ledger:
        ledger_rows, ledger_problems = parse_ledger(open(ledger, encoding="utf-8").read())
        ledger_problems.extend(f"台账位置“{row['位置']}”无法在成稿定位" for row in ledger_rows if not locate(row["位置"], blocks))
        m2.extend(f"修改台账不合格：{x}" for x in ledger_problems)
    contrasts = contrast_checks(key)
    m2.extend(f"色彩对比不足：{x['foreground_role']} 在 {x['background']} 上 "
              f"{x['ratio']}:1，低于 WCAG AA" for x in contrasts if not x["pass"])

    fs = first_screen(meta, blocks)
    if fs["weight"] > 1:
        s2.append(f"首屏含 {fs['weight']} 个重入口：建议只保留一个主入口")
    m1, m2, s2 = list(dict.fromkeys(m1)), list(dict.fromkeys(m2)), list(dict.fromkeys(s2))

    source_name = "源稿.md" if delivery else os.path.abspath(md_path)
    cover_uri = preview_image(cover, base) if cover and not TODO.match(cover) else ""
    cover_panel = ({"src": cover_uri, "focal": meta.get("cover_focal") or "50% 50%",
                    "note": meta.get("cover_note", "")} if cover_uri.startswith("data:") else None)
    preview = preview_page(meta, THEMES[key]["name"], native_header(meta), body, cover=cover_panel)
    preview = re.sub(r'(<img\b[^>]*src=")([^"]+)(")',
                     lambda m: m[1] + H.escape(preview_image(H.unescape(m[2]), base)) + m[3]
                     + ' data-local="' + m[2] + '"', preview)
    asset_records = []
    img_meta = {b[1]: (b[0], b[2]) for k, b in blocks if k == "img"}
    for src, data in sorted(originals.items()):
        # 字节已经在手：尺寸与哈希都从这份字节算，不再二次读盘、不重复算同一份 sha256
        digest = hashlib.sha256(data).hexdigest()
        _mime, wh = image_info(data)
        alt, role = img_meta.get(src, ("", "cover"))
        asset_records.append({"path": src, "sha256": digest,
                              "dimensions": list(wh) if wh else None,
                              "role": role or ("cover" if src == cover else ""),
                              "caption": alt, "provenance": meta.get("cover_note", "") if src == cover else "",
                              "focal": meta.get("cover_focal", "50% 50%") if src == cover else "",
                              "subject_visibility": "UNVERIFIED", "safe_zone": "UNVERIFIED"})
    side = {
        "title": meta.get("title", ""), "api_title": api_title(meta.get("title", "")),
        "author": meta.get("author", ""), "digest": meta.get("digest") or auto_digest(meta, blocks),
        "cover": cover if cover and not TODO.match(cover) else "", "source_url": meta.get("source", ""),
        "theme": key, "skill_version": SKILL_VERSION, "theme_config_sha256": THEME_CONFIG_SHA256,
        "renderer_sha256": renderer_fingerprint(),
        "typography": {"policy": "装饰性分隔归一为“·”；引语、URL、代码、单位比与数字比不改写；编辑说明整段移除",
                       "removed_editorial": removed_editorial,
                       "preview_viewports": list(VIEWPORTS),
                       "preview_fonts": ["ios", "android"]},
        "theme_profile": dict({axis: THEMES[key][axis] for axis in THEME_AXES},
                              stance=THEMES[key].get("stance", "")),
        "grid": dict(THEMES[key]["grid"]), "contrast_checks": contrasts,
        "decision": review["decision"], "article_type": review["type"]["key"],
        "composition_evidence": {"first_screen_layers": fs["layers"], "first_screen_weight": fs["weight"],
                                 "h2_count": sum(k == "h2" for k, _ in blocks), "body_characters": doc_len(blocks),
                                 "scope": "源稿结构统计，不是首屏像素测量"},
        "integrity_version": 4,
        "source": {"path": source_name, "sha256": source_digest}, "assets": asset_records,
        "body_sha256": hashlib.sha256(body.encode()).hexdigest(),
        "preview_sha256": hashlib.sha256(preview.encode()).hexdigest(),
        "render_status": "FAIL" if m1 or m2 else "PASS", "render_errors": m1 + m2,
        "pending_assets": any(not b[1] or TODO.match(b[1]) for k, b in blocks if k == "img"),
        "verification_gates": {"local_static": "FAIL" if m1 or m2 else "PASS",
                               "browser_multi_width": "UNVERIFIED", "semantic_editorial": "UNVERIFIED",
                               "wechat_api_readback": "UNVERIFIED", "wechat_real_device": "UNVERIFIED"},
    }
    if facts_diff is not None:
        side.update(fact_diff=facts_diff, voice_diff=voice_diff)
    if ledger:
        side["ledger"] = {"rows": ledger_rows, "problems": ledger_problems}

    # 交付字节全部在内存里组装：每个文件只写一次、只算一次哈希，不经过中转目录。
    payloads = {"正文.html": body.encode(), "预览.html": preview.encode(),
                "正文.meta.json": (json.dumps(side, ensure_ascii=False, indent=2) + "\n").encode()}
    payloads.update(originals)
    if delivery:
        report = render_report(review, facts_diff, ledger_problems, voice_diff)
        report += "\n## 类型策略\n\n" + "\n".join(f"- {x}" for x in strategy_notes(meta, blocks)) + "\n"
        report += "\n## 修改边界\n\n仅记录已输入的原稿比对与修改台账；未提供原稿时，不声称已完成改前/改后编辑审计。\n"
        if ledger_rows:
            report += "\n## 修改台账\n\n| 位置 | 问题 | 动作 | 收益 | 保留检查 |\n|---|---|---|---|---|\n"
            report += "\n".join("| " + " | ".join(row[c].replace("|", "｜").replace("\n", " ") for c in LEDGER_HEAD) + " |" for row in ledger_rows) + "\n"
        acceptance = ["# 验收结果", "", f"- Skill：{SKILL_VERSION}；主题：{key}",
                      f"- 本地静态 Gate：{'FAIL' if m1 or m2 else 'PASS'}"]
        acceptance += [f"- FAIL：{x}" for x in m1 + m2]
        acceptance += [f"- 复核建议：{x}" for x in s2]
        acceptance += ["", "| 验证项 | 状态 | 证据边界 |", "|---|---|---|",
                       "| 五宽度浏览器 | UNVERIFIED | 本命令不启动浏览器；须另附 320/360/375/390/430px 实测 |",
                       "| 语义编辑与外部核真 | UNVERIFIED | 机器线索不是事实核真或审美评分 |",
                       "| 微信 API 回读 | UNVERIFIED | 须真实账号创建草稿并回读 |",
                       "| 微信 iOS/Android 真机 | UNVERIFIED | 浏览器与 API 均不能代替 |",
                       "| 图片主体与安全区 | UNVERIFIED | 须实际核看原图与客户端裁切 |"]
        payloads["源稿.md"] = source_bytes
        payloads["修改记录.md"] = report.encode()
        payloads["验收.md"] = ("\n".join(acceptance) + "\n").encode()
    targets = {}
    for relative in payloads:
        name = os.path.basename(prev) if relative == "预览.html" else relative
        if not delivery and relative in ("正文.html", "正文.meta.json"):
            name = os.path.basename(out if relative == "正文.html" else meta_path)
        targets[relative] = os.path.join(out_base, name)
    # 先整体校验目标路径与冲突，再落盘：任一条不合格时一个字都不写
    collisions = [path for path in targets.values() if os.path.realpath(path) in protected]
    if collisions:
        raise ValueError(f"交付将覆盖受保护输入：{collisions}")
    for path in targets.values():
        output_path(path)
    for relative, path in targets.items():
        atomic_write(path, payloads[relative])
    if delivery:
        # 清单键必须是交付目录内的相对路径：只写文件名会让 images/ 下的素材一起撞名，
        # 也会让下次交付时的“清单内文件全等”校验永远找不到文件。
        manifest = {"schema": 1, "skill_version": SKILL_VERSION, "source_sha256": source_digest,
                    "body_sha256": side["body_sha256"], "render_status": side["render_status"],
                    "files": {os.path.relpath(path, out_base).replace(os.sep, "/"):
                              hashlib.sha256(payloads[relative]).hexdigest()
                              for relative, path in sorted(targets.items())}}
        atomic_write(os.path.join(deliver, "交付清单.json"), json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return {"key": key, "meta": meta, "blocks": blocks, "body": body, "side": side, "review": review,
            "out": out, "preview": prev, "meta_path": meta_path, "facts_diff": facts_diff,
            "voice_diff": voice_diff, "ledger_rows": ledger_rows, "ledger_problems": ledger_problems,
            "gates": (("Gate 1 Platform", m1, s1), ("Gate 2 Composition", m2, s2))}


def native_header(meta):
    title = H.escape(api_title(meta.get("title", "")))
    author = H.escape(meta.get("author", ""))
    date = H.escape(meta.get("date", ""))
    credit = (f'<b>{author}</b>' if author else "") + date
    return (f'<div class="nt"><h1>{title}</h1>' + (f'<p class="au">{credit}</p>' if credit else "") + "</div>") if title else ""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("md")
    ap.add_argument("--theme", choices=list(THEMES))
    ap.add_argument("-o", "--out")
    ap.add_argument("--against", help="原稿：事实、引语、代码、限定词与作者声音比对")
    ap.add_argument("--ledger", help="五列修改台账")
    ap.add_argument("--deliver", help="完整交付到空目录或未被手改的本工具交付目录")
    args = ap.parse_args()
    if os.path.splitext(args.md)[1].lower() not in (".md", ".markdown", ".txt"):
        ap.error("仅支持 UTF-8 Markdown/纯文本；DOCX 请先用 extract_docx.py 转换")
    if args.out and args.deliver:
        ap.error("--out 与 --deliver 二选一")
    out = os.path.join(os.path.abspath(args.deliver), "正文.html") if args.deliver else args.out
    result = build(args.md, args.theme, out, args.against, args.ledger, bool(args.deliver))
    review = result["review"]
    for issue in review["issues"]:
        print(f"编辑提示 · {issue['severity']} · {issue['location']} · {issue['code']}：{issue['problem']} → {issue['action']}")
    print(f"{THEMES[result['key']]['name']} — {THEMES[result['key']].get('stance', '')}")
    print(f"→ {result['out']}\n预览 → {result['preview']}\n侧车 → {result['meta_path']}")
    failed = False
    for gate, must, should in result["gates"]:
        failed |= bool(must)
        print(f"\n{gate}: {'FAIL' if must else 'PASS'}")
        for message in must:
            print("  必须改 ·", message)
        for message in should:
            print("  建议改 ·", message)
    print("\n浏览器、语义编辑、微信 API 与真机：UNVERIFIED；静态 PASS 不能代替。")
    if args.deliver:
        print(f"交付包 → {args.deliver}（清单最后写入）")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError) as error:
        sys.exit(f"输入错误：{error}")
