#!/usr/bin/env python3
"""Editorial Intelligence：可定位、可复现的编辑审计层。

边界（必须先读）：

- 本模块**不做**语义判断、不证实事实、不改写文字。它把「能被机器稳定指出的
  线索」摆到编辑面前，并区分两类结论：
    * `mechanical`  —— 只看文字就能确认的形态问题（重复、超长、承诺数量不符、
                       关键数字没有就近来源、强因果措辞没有限定）。
    * `judgment`    —— 需要人或模型判断才能定性的问题（主张缺证据、证据无主张、
                       章节只在复述论点、观点缺少反例）。脚本只负责**指出位置**，
                       不冒充已经判断，也不自动改稿。
- `compare()` 只做「事实单元是否仍在」的集合比对，用于防止改写时凭空新增数字、
  日期或引语。它不是事实核真：事实是否正确，仍须回到原始来源。

单一事实来源：文本度量（plain / visible_len / doc_len / peak_text / first_screen）
由本模块持有，render.py 直接复用，不再复制第二套实现。
"""
import difflib
import re
import statistics
from collections import Counter

# ---------------------------------------------------------------- 文章类型

TYPES = {
    "news": {
        "label": "新闻报道",
        "reader_question": "发生了什么，什么时候，谁说的，对我有什么影响",
        "opening": "已知事实 + 时间/来源，先于背景与评论",
        "structure": ["事实", "时间与来源", "影响", "未知项"],
        "evidence": "每个关键事实可定位到机构、日期或原始文本",
        "title_promise": "事件主体 + 变化量；数量承诺必须逐项出现",
        "risks": ["把转述写成确认", "用观点补事实空缺", "时间线倒置导致因果错觉"],
    },
    "analysis": {
        "label": "商业与经济分析",
        "reader_question": "这个判断凭什么成立，边界在哪，我该据此做什么",
        "opening": "核心判断 + 它依赖的证据类型",
        "structure": ["主张", "证据", "机制", "反例或限制", "含义"],
        "evidence": "数字带口径与期间；相关与因果分开表述",
        "title_promise": "趋势 + 限定；避免把单因素写成唯一原因",
        "risks": ["相关性写成因果", "个例外推", "结论重复主张而没有新增信息"],
    },
    "tutorial": {
        "label": "技术教程",
        "reader_question": "前提是什么，按什么顺序做，失败时怎么办",
        "opening": "读者能得到什么 + 前提与版本",
        "structure": ["问题", "前提", "步骤", "失败条件与回退", "边界"],
        "evidence": "命令、输出、版本号可复现",
        "title_promise": "任务 + 完成标准；步骤数量与正文一致",
        "risks": ["跳过前提", "步骤顺序混乱", "只写成功路径"],
    },
    "profile": {
        "label": "人物故事",
        "reader_question": "这个人做了什么选择，凭什么这样判断",
        "opening": "一个具体场景或动作，而不是评价",
        "structure": ["场景", "冲突或转折", "细节与引语", "意义（有证据支撑）"],
        "evidence": "引语有出处；细节不替代事实",
        "title_promise": "人物 + 一个可兑现的具体性",
        "risks": ["情绪代替事实", "评价先行", "把作者判断排成伪引语"],
    },
    "opinion": {
        "label": "观点评论",
        "reader_question": "作者主张什么，最强的反驳是什么，作者如何回应",
        "opening": "主张与其代价，先于抒情",
        "structure": ["主张", "理由", "最强反例", "回应", "限定"],
        "evidence": "事实与价值判断分开；引用保留真实措辞",
        "title_promise": "立场可被定位；问题型标题必须有明确回答",
        "risks": ["以情绪替代论证", "只打稻草人", "绝对化措辞"],
    },
    "longform": {
        "label": "深度长文",
        "reader_question": "这条主线如何展开，中途我在哪里",
        "opening": "一个能承载全文张力的具体切口",
        "structure": ["切口", "展开", "转折", "收束"],
        "evidence": "长文更容易在中段失去证据，逐段回看",
        "title_promise": "主标题只承诺一个核心关系",
        "risks": ["章节失衡", "中段只复述", "收尾引入未论证的新主张"],
    },
}

EDIT_WORK = {
    "news": {"protect": "消息来源、归属动词、时间、已确认与未知边界", "prefer": "删除情绪性补白；按事实归属分层；不替当事人解释动机", "questions": ["每个事实是谁确认的？", "公司说法是否仍写成公司说法？", "标题的变化量有无同口径依据？"]},
    "analysis": {"protect": "指标口径、期间、比较基准、相关性与例外", "prefer": "先对齐比较对象；把证据→机制→推断拆开；保留反例", "questions": ["证据支持相关、机制还是因果？", "有没有口径不同却直接比较？", "最强反例是否改变结论范围？"]},
    "tutorial": {"protect": "版本、前提、命令、参数、输出、顺序与警告", "prefer": "按执行依赖重排；补可观察完成标准；保留失败与回退", "questions": ["上一步输出是否满足下一步输入？", "读者如何知道执行成功？", "失败时能否恢复原状态？"]},
    "profile": {"protect": "人物原话、时间线、具体动作、事实与作者评价的边界", "prefer": "用已有场景与选择组织叙事；删除空泛赞美；不补心理和采访", "questions": ["评价能否回到具体动作或原话？", "叙事是否倒置了时间或因果？", "场景与引语是否有真实出处？"]},
    "opinion": {"protect": "作者立场、声音、论证对象、价值前提与原有时代用字", "prefer": "优先分段与重排；拆出理由和最强反驳；不为现代口吻重写原文", "questions": ["反驳是否是对方最强版本？", "事实前提与价值判断是否分开？", "回应反例后结论需要缩小吗？"]},
    "longform": {"protect": "主线、伏笔与回收、时间线、各节独有的信息增量", "prefer": "先画章节推进；合并中段复述；保留必要回环，不把长文压成清单", "questions": ["每节相对上一节新增了什么？", "转折是否有前文铺垫？", "结尾是否回收主线而非塞新证据？"]},
}
for key, work in EDIT_WORK.items():
    TYPES[key]["editorial_work"] = work

# 语义验收也按类型分化；这些是需要编辑回答的问题，不是机器评分项。
SEMANTIC_REVIEW = {
    "news": ["标题兑现与事实归属", "时间线和消息来源", "事实/推断/未知边界", "影响与逐节信息增量", "原意、引语与作者声音"],
    "analysis": ["标题兑现与比较口径", "证据→机制→推断链", "最强反例与适用边界", "逐节信息增量", "原意与作者声音"],
    "tutorial": ["任务与完成标准", "版本、前提与执行顺序", "可观察的成功校验", "失败条件与回退", "命令、参数与原意保留"],
    "profile": ["时间线、场景与引语出处", "人物选择与转折", "事实/评价/心理边界", "逐节叙事增量", "细节与作者声音"],
    "opinion": ["主张与价值前提", "理由与最强反例", "回应、代价与结论限定", "事实/推断/观点边界", "作者立场与声音"],
    "longform": ["主线与标题兑现", "伏笔、转折与回收", "时间线与章节信息增量", "结尾不引入未论证新证据", "原意与叙事声音"],
}

# 中文类型别名：frontmatter 允许写中文，解析到同一策略，避免作者被迫记英文键。
TYPE_ALIASES = {
    "新闻": "news", "报道": "news", "新闻报道": "news",
    "分析": "analysis", "商业分析": "analysis", "经济分析": "analysis", "商业与经济分析": "analysis",
    "教程": "tutorial", "技术教程": "tutorial", "操作指南": "tutorial",
    "人物": "profile", "人物故事": "profile", "特稿": "profile",
    "评论": "opinion", "观点": "opinion", "观点评论": "opinion", "社论": "opinion",
    "长文": "longform", "深度长文": "longform", "深度报道": "longform",
    "实操": "tutorial", "指南": "tutorial", "实务说明": "tutorial", "说明书": "tutorial",
    "特写": "profile", "访谈": "profile", "专栏": "opinion", "时评": "opinion",
}


def resolve_type(value):
    """返回 (key, 是否可识别)。空值不算错误：类型判断本应由编辑先做。"""
    if not value:
        return "", True
    key = value.strip().lower()
    if key in TYPES:
        return key, True
    alias = TYPE_ALIASES.get(value.strip())
    if alias:
        return alias, True
    # 允许「新闻 + 分析」这类复合表述：取第一个可识别片段并如实返回
    for part in re.split(r"[+/、,，·\s]+", value):
        part = part.strip()
        low = part.lower()
        if low in TYPES:
            return low, False
        if part in TYPE_ALIASES:
            return TYPE_ALIASES[part], False
    return "", False


# ---------------------------------------------------------------- 文本度量

def plain(s):
    """去掉行内标记只留文字，供目录与度量使用，避免 ** == 原样外露或虚增字数。"""
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)
    return re.sub(r"`([^`]*)`|==([^=]*)==|\*\*([^*]*)\*\*|<u>([^<]*)</u>|~~([^~]*)~~",
                  lambda m: next(g for g in m.groups() if g is not None), s).strip()


def visible_len(s):
    return len(re.sub(r"</?u>|https?://\S+|[`*=~\[\]()]", "", s))


def peak_text(b):
    return " ".join(b[1]) or b[0]


def _list_node_text(node):
    parts = []
    for item in node.get("items", []):
        parts.append(item.get("text", ""))
        for child in item.get("children", []):
            parts.extend(_list_node_text(child))
    return parts


def block_text(kind, value):
    """块的可读文字，用于审计与事实比对；不含标签与图注之外的元信息。"""
    if kind in ("p", "h2", "h3"):
        return value
    if kind in ("lead", "quote"):
        return value[0]
    if kind == "peak":
        return peak_text(value)
    if kind in ("note", "unknown"):
        return " ".join(value[1])
    if kind == "list":
        return " ".join(_list_node_text(value))
    if kind == "table":
        return " ".join(c for row in value for c in row)
    if kind == "code":
        return " ".join(value[1])
    if kind in ("data", "bars"):
        return " ".join(value[1])
    if kind == "img":
        return value[0] or ""
    return ""


def doc_len(blocks):
    """全文可见字数（正文 + 标题 + 列表 + 表格 + 代码 + 旁注）。

    只用段落字数会低估数据型 / 技术型文章：一篇 400 字正文 + 500 行代码的文章
    并不是一篇 400 字的短文，图片预算与节奏判断都跟着错。
    """
    return sum(visible_len(block_text(k, b)) for k, b in blocks)


def first_screen(meta, blocks):
    """记录首个正文段落之前的块，不推测像素首屏。

    `weight` 统计「同时抢首屏」的重元素：副题、导语、首图、核心主张。
    超过一个就说明首屏没有唯一入口——这是建议级判断，不阻断渲染。
    """
    kinds = [b[0] for b in blocks]
    stop = next((i for i, k in enumerate(kinds) if k == "p"), len(kinds))
    layers = [k for k in kinds[:stop] if k in {"lead", "img", "note", "data", "bars", "table", "quote", "peak"}]
    if meta.get("deck"):
        layers.insert(0, "deck")
    if meta.get("kicker"):
        layers.insert(0, "kicker")
    weight = sum(1 for k in layers if k in ("deck", "lead", "img", "peak"))
    return {"layers": layers, "weight": weight}


# ---------------------------------------------------------------- 事实单元

_NUM = re.compile(
    r"(?<![\d.])([+\-−]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[+\-−]?\d+(?:\.\d+)?)\s*"
    r"(个百分点|万亿美元|亿美元|万美元|万亿元|亿元|万元|千亿|百万|兆瓦|千瓦|公里|千米|小时|分钟|"
    r"美元|人民币|欧元|日元|GB|MB|TB|ms|%|％|元|倍|年|月|日|天|人|家|件|台|吨|米|秒|万|亿)?"
)
_CN_NUM = re.compile(r"[一二三四五六七八九十百千万两零]{1,7}(?:倍|成|万人|亿元|美元|小时)")
_QUOTED = re.compile(r"「([^」]{2,})」|“([^”]{2,})”")
_URL = re.compile(r"https?://[^\s<>，；。！？）\"]+")
_DATE = re.compile(r"(?:19|20)\d{2}年(?:\d{1,2}月(?:\d{1,2}日)?)?|"
                   r"(?:19|20)\d{2}[-–/]\d{1,2}(?:[-–/]\d{1,2})?|"
                   r"\d{1,2}月\d{1,2}日")
_QUALIFIER = re.compile(r"大约|约|近|超过|超|不足|少于|多于|不到|至少|至多|预计|估算|初步")


def _fact_matches(text):
    """(kind, raw, start, end)；位置用于逐次限定检查，不靠第一次出现代表整段。"""
    out, spans = [], []
    normalized = text.replace("，", ",")
    # URL 是单一事实单元；路径/百分号编码里的数字不拆成统计数值。
    for m in _URL.finditer(text):
        raw = m.group().rstrip("。，；）")
        spans.append((m.start(), m.start() + len(raw)))
        out.append(("url", raw, m.start(), m.start() + len(raw)))
    for m in _DATE.finditer(normalized):
        if any(a <= m.start() < b for a, b in spans):
            continue
        spans.append(m.span())
        raw = re.sub(r"\s+", "", m.group())
        nums = re.findall(r"\d+", raw)
        if len(nums[0]) == 4:
            year, month, day = nums[0], nums[1] if len(nums) > 1 else "", nums[2] if len(nums) > 2 else ""
        else:
            year, month, day = "????", nums[0], nums[1] if len(nums) > 1 else ""
        out.append(("date", year + (f"-{int(month):02d}" if month else "") + (f"-{int(day):02d}" if day else ""), m.start(), m.end()))
    for m in _NUM.finditer(normalized):
        if any(a <= m.start() < b for a, b in spans):
            continue
        if m.group(2):
            value = re.sub(r"\s+", "", m.group()).replace("％", "%").replace("−", "-")
            out.append(("num", value, m.start(), m.end()))
    for m in _CN_NUM.finditer(normalized):
        if not any(a <= m.start() < b for a, b in spans):
            out.append(("num", m.group(), m.start(), m.end()))
    return out


def facts(text):
    """字面事实候选，不是真实性判断；保留正负号、单位、日期精度。"""
    return [(kind, raw) for kind, raw, _, _ in _fact_matches(text)]


def fact_occurrences(blocks):
    """给编辑回查的上下文；近似/预测等限定与事实值分开记录。"""
    rows = []
    for index, (kind, value) in enumerate(blocks, 1):
        text = block_text(kind, value)
        normalized = text.replace("，", ",")
        for fact_kind, raw, start, _ in _fact_matches(text):
            clause = re.split(r"[。！？；;，,]", normalized[:start])[-1]
            qualifiers = list(_QUALIFIER.finditer(clause[-16:]))
            rows.append({"block": index, "kind": fact_kind, "value": raw,
                         "qualifier": qualifiers[-1].group() if qualifiers else "", "context": text[:180]})
    return rows


def quoted_spans(text):
    """只把有说话/引用归属的引号当直接引语；强调性引号不冒充引语。

    中文既常写「他说：“……”」，也常写「“……”他说」。归属动词在引号后时
    同样是直接引语，不能在改稿比对中被误报为新增或删除。
    """
    out = []
    attribution_after = re.compile(
        r"^[\s，,：:]*(?:[\u4e00-\u9fff]{1,8})?(?:说|称|问|道|表示|宣布|写道|回答|补充|解释|强调|回忆)"
    )
    for m in _QUOTED.finditer(text):
        before = text[max(0, m.start() - 14):m.start()]
        after = text[m.end():m.end() + 18]
        if (re.search(r"说|称|问|道|引述|引用|信中|古语|俗语|写道|回答|宣布|表示", before)
                or attribution_after.search(after)):
            out.append(next(g for g in m.groups() if g))
    return out


def _fact_key(kind, value):
    v = value.replace("％", "%").replace("．", ".").strip()
    v = re.sub(r"(?<=\d)[,，](?=\d{3})", "", v)
    return kind, v


def compare_facts(original_blocks, edited_blocks, original_meta=None, edited_meta=None):
    """集合保留 + 出现次数/限定/日期精度变化；不把补年份或删「约」当作无损改写。"""
    original_blocks = list(original_blocks)
    edited_blocks = list(edited_blocks)
    if original_meta:
        original_blocks += [("p", original_meta.get(k, "")) for k in ("title", "deck")]
    if edited_meta:
        edited_blocks += [("p", edited_meta.get(k, "")) for k in ("title", "deck")]
    src, dst = {}, {}
    for blocks, target in ((original_blocks, src), (edited_blocks, dst)):
        for kind, value in blocks:
            for fact in facts(block_text(kind, value)):
                target.setdefault(_fact_key(*fact), fact[1])
    matched = {k for k in src if k in dst}
    precision = []
    # 仅识别可能的日期补全，不自动认证；同年不同日期、不同年份绝不匹配。
    for key in src:
        if key in matched or key[0] != "date" or not key[1].startswith("????-"):
            continue
        candidates = [c for c in dst if c not in matched and c[0] == "date"
                      and not c[1].startswith("????") and c[1][5:] == key[1][5:]]
        if len(candidates) == 1:
            cand = candidates[0]
            matched.update((key, cand))
            precision.append({"original": src[key], "edited": dst[cand], "status": "UNVERIFIED", "reason": "补全年份需回原始来源确认"})
    src_q = {q for k, b in original_blocks for q in quoted_spans(block_text(k, b))}
    dst_q = {q for k, b in edited_blocks for q in quoted_spans(block_text(k, b))}
    before, after = fact_occurrences(original_blocks), fact_occurrences(edited_blocks)
    counts_before, counts_after = Counter((_fact_key(x['kind'], x['value'])) for x in before), Counter((_fact_key(x['kind'], x['value'])) for x in after)
    qualifiers = []
    for key in matched:
        q1 = {x['qualifier'] for x in before if _fact_key(x['kind'], x['value']) == key and x['qualifier']}
        q2 = {x['qualifier'] for x in after if _fact_key(x['kind'], x['value']) == key and x['qualifier']}
        if q1 != q2:
            qualifiers.append({"value": src[key], "original": sorted(q1), "edited": sorted(q2), "status": "UNVERIFIED"})
    return {
        "preserved": [src[k] for k in src if k in matched],
        "dropped": sorted(src[k] for k in src if k not in matched),
        "dropped_quotes": sorted(src_q - dst_q), "introduced_quotes": sorted(dst_q - src_q),
        "introduced": sorted(dst[k] for k in dst if k not in matched),
        "source_units": len(src), "edited_units": len(dst),
        "precision_changes": precision, "qualifier_changes": qualifiers,
        "occurrence_changes": [{"value": src.get(k, dst.get(k)), "before": counts_before[k], "after": counts_after[k]}
                               for k in sorted(set(counts_before) | set(counts_after)) if counts_before[k] != counts_after[k]],
        "verification": "UNVERIFIED",
    }


def compare_voice(original_blocks, edited_blocks):
    """改稿是否把作者声音抹平：同一口径计数原稿与改稿，只报差异，不给好坏结论。

    第一人称、设问、破折号、旁白括号、口语标记整体归零，是「声音被改掉」的形态信号；
    是否该保留由编辑判断（有些确实是冗余口语）。
    """
    before, after = voice_profile(original_blocks), voice_profile(edited_blocks)
    changes = []
    for name in before["marks"]:
        b, a = before["marks"][name], after["marks"][name]
        if b != a and (b == 0 or a == 0 or abs(a - b) >= max(2, round(b * 0.5))):
            changes.append({"mark": name, "original": b, "edited": a,
                            "status": "UNVERIFIED",
                            "note": "整体消失" if a == 0 < b else ("新增" if b == 0 < a else "显著减少/增加")})
    return {"original": before, "edited": after, "changes": changes,
            "status": "UNVERIFIED", "scope": "形态计数，不是声音相似度评分"}


def classify_fact_change(edited_blocks, kind, value):
    """一条事实「消失/新增」的性质：真丢失、结构性搬家，还是精度概括。

    - `moved`：数值被搬进 data / bars 块（值在行里、单位写在块标题），字面不再相邻。
      这是排版决定，不是删事实；但口径仍需人确认，所以降级为「建议改」。
    - `rounded`：只出现在导语/标题的年份概括，而同一年的精确日期仍在正文别处。
    - `lost` / `added`：其余情况——默认保守处理，必须人工回查。
    """
    if kind == "num":
        number = re.match(r"\d[\d,]*(?:\.\d+)?", value)
        for block_kind, block in edited_blocks:
            if block_kind not in ("data", "bars"):
                continue
            unit, body = block if isinstance(block, tuple) else ("", block)
            lines = body if isinstance(body, list) else body.splitlines()
            for raw_line in lines:
                cells = [cell.strip() for cell in raw_line.replace("|", "｜").split("｜")]
                # data 是「值｜标签」，bars 是「标签｜值｜满分」。
                cell = cells[0] if block_kind == "data" else (cells[1] if len(cells) > 1 else "")
                if not cell:
                    continue
                if value in {cell, cell + unit, unit + cell}:
                    return "moved", f"数值 {value} 现在位于 {block_kind} 块，完整值与单位仍可对应"
                if number and cell == number.group(0):
                    suffix = value[number.end():]
                    if not suffix or suffix in f"{unit} {raw_line}":
                        return "moved", f"数值 {value} 现在位于 {block_kind} 块，值与单位分栏保留"
    if kind == "date":
        year = re.match(r"(\d{4})", value)
        precise = re.compile(rf"{year.group(1)}年\d{{1,2}}月\d{{1,2}}日") if year else None
        body = " ".join(block_text(k, b) for k, b in edited_blocks)
        if year and value.rstrip("年月日") == year.group(1) and precise and precise.search(body):
            return "rounded", f"{value} 是只到年的概括，同年精确日期仍在正文"
        partial = re.match(r"(\d{4})-(\d{2})$", value)
        if year and partial:
            same = re.compile(rf"{partial.group(1)}年{int(partial.group(2))}月")
            if same.search(body) and not re.search(rf"{int(partial.group(2))}月\d{{1,2}}日", body):
                return "rounded", f"改稿把 {value} 退到「年月」，日级信息消失"
            if same.search(body):
                return "rounded", f"{value} 的精确日期仍在正文，另有只到月的表述"
    return "lost", ""


def introduced_without_source(edited_blocks, introduced):
    """新增事实是否就近可核：相邻 note 或同段链接视为已给出依据。"""
    if not introduced:
        return []
    haystack = []
    for i, (kind, value) in enumerate(edited_blocks):
        text = block_text(kind, value)
        near = " ".join(block_text(k, v) for k, v in edited_blocks[max(0, i - 1):i + 2])
        if re.search(r"https?://\S+", near) or kind == "note":
            haystack.append(text + " " + near)
    joined = " ".join(haystack)
    nearby_keys = {_fact_key(*fact) for fact in facts(joined)}
    return [f for f in introduced
            if f not in joined and not any(key[1] == _fact_key("num", f)[1] for key in nearby_keys)]


# ---------------------------------------------------------------- 台账

LEDGER_HEAD = ("位置", "问题", "动作", "收益", "保留检查")


def split_row(line):
    return [c.strip().replace(r"\|", "|") for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def parse_ledger(text):
    rows, problems, header, separator = [], [], False, False
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = split_row(line)
        if tuple(cells) == LEDGER_HEAD:
            header = True
            continue
        if cells and all(re.fullmatch(r":?-+:?", c) for c in cells):
            separator = len(cells) == 5
            continue
        if len(cells) != 5:
            problems.append(f"台账第 {number} 行必须为五列，实际 {len(cells)} 列")
            continue
        rows.append(dict(zip(LEDGER_HEAD, cells)))
    if not header or not separator:
        problems.append("台账缺少五列表头或分隔行")
    for i, row in enumerate(rows, 1):
        for col in LEDGER_HEAD:
            if not row[col] or row[col] in ("—", "-", "无", "略"):
                problems.append(f"台账第 {i} 行缺少「{col}」")
    return rows, problems


def locate(needle, blocks):
    """台账「位置」能否回到正文：短句命中即算，标题/导语等入口可写定性位置。"""
    if not needle:
        return False
    key = re.sub(r"\s+", "", plain(needle))
    if len(key) < 2:
        return False
    body = re.sub(r"\s+", "", " ".join(block_text(k, b) for k, b in blocks))
    if key in body:
        return True
    entry = {"标题", "导语", "全文", "首段", "结尾", "封面", "副题"}
    return all(part.strip() in entry for part in re.split(r"[与和、，,]", needle) if part.strip())


# ---------------------------------------------------------------- 审计

CAUSAL = re.compile(r"证明(?:了)?|必然|一定会|唯一原因|彻底(?:改变|解决)|直接导致|决定了|根本原因")
HEDGE = re.compile(r"可能|或许|相关|之一|在.{0,8}条件|不等于|未必|有待|尚无|推测|估计|不能|不足以|不宜|无法")
ATTRIB = re.compile(r"数据显示|研究表明|报告显示|据(?:报道|统计|调查|了解)|有(?:专家|学者|人士)|业内(?:人士|普遍)")
CLICHE = re.compile(r"随着.{0,12}(?:发展|普及|提升|加快|推进|深入|兴起)|在当今(?:社会|时代|这个)|"
                    r"众所周知|不言而喻|毋庸置疑|不可否认|不难发现|值得注意的是|"
                    r"总而言之|综上所述|总之[，,]|从某种意义上(?:来)?说")
ABSOLUTE = re.compile(r"所有人|每个人|无一例外|从来如此|永远|绝对|毫无疑问|显然|"
                       r"只要我们[^。]{0,24}就(?:一定|必然)|就一定(?:能|可以|会)")
# ---- 文风线索（mechanical）：全部只报「形态」，不下「写得差」的结论 --------------
# 元话语：把写作过程写进正文，占掉首屏却不给信息。
META_DISCOURSE = re.compile(r"本文将|本文试图|本文分为|本文将分|接下来我们(?:来看|聊聊)|下面我们(?:来)?看|"
                            r"让我们(?:一起)?(?:来看|看看|聊聊)|话不多说|如你所见|感兴趣的朋友|"
                            r"如前所述|正如前文(?:所说|提到)")
# 模板排比：同一句式反复出现，才说明它在替代思考，单次使用不算。
TEMPLATES = {
    "既是…也是…更是": re.compile(r"既[是][^。]{0,24}也[是][^。]{0,24}更[是]"),
    "不仅…而且…更": re.compile(r"不仅[^。]{0,24}而且[^。]{0,24}更"),
    "不是…而是": re.compile(r"不是[^。]{0,20}而是"),
    "越…越…": re.compile(r"越[^。，]{1,8}越[^。，]{1,8}[，。]"),
    "只有…才…": re.compile(r"只有[^。]{0,24}才(?:能|可以|会)"),
    "从…到…": re.compile(r"从[^。，]{1,10}到[^。，]{1,10}[，。]"),
    "让…更…": re.compile(r"让[^。，]{1,10}更[^。，]{1,10}"),
    "与其…不如": re.compile(r"与其[^。]{0,20}不如"),
    "既…又…": re.compile(r"既[^。]{0,16}又[^。]{0,16}[，。]"),
}
# 抽象名词空转：名词本身不承载可核信息，密集出现且无数字/来源/引语时才是线索。
ABSTRACT = re.compile(r"价值|意义|赋能|抓手|闭环|生态|维度|底层逻辑|顶层设计|颗粒度|方法论|"
                      r"认知|链路|势能|心智|锚点|破局|范式|组合拳|护城河|壁垒|动能|闭环思维")
RESTATE = re.compile(r"换句话说|也就是说|简单来说|简而言之|一言以蔽之|说到底|归根结底|"
                     r"这意味(?:着)?(?:，|,)?\s*$")
# 句首推断标记：句子靠连接词承接，但同段没有可见依据时，推断容易跳步。
INFER_HEAD = re.compile(r"^(?:因此|所以|可见|由此可见|这说明|足以说明|不难看出|自然|于是|从而)")
# 口语序号：正文用「首先/其次/最后」推进，却没有真的成为列表项。
PROSE_ORDINAL = re.compile(r"(?:^|[。；！？，])(首先|其次|再次|然后|最后|第一|第二|第三)[，,、：]")
# 空洞呼吁：结尾靠号召、祝愿、共同愿景收束，没有给出具体的下一步。
HOLLOW_CALL = re.compile(r"让我们|一起(?:努力|成长|进步|见证|期待|迎接)|共同(?:努力|成长|进步|创造)|"
                        r"相信(?:未来|明天)|未来可期|迎来更(?:好|美好)的|拭目以待|共勉")
# 呼吁类词在结尾段里出现多少次才算「靠口号收束」：一次可能只是正常的引用或过渡。
HOLLOW_CALL_MIN = 2
# 作者声音画像：用于 --against 比对「改稿是否抹平了作者」，只数形态，不判断好坏。
VOICE_MARKS = {
    "第一人称": re.compile(r"我(?!们)"),
    "我们": re.compile(r"我们"),
    "第二人称": re.compile(r"你(?!们)"),
    "设问": re.compile(r"[？?]"),
    "破折号": re.compile(r"——"),
    "旁白括号": re.compile(r"（[^）]{2,30}）|\([^)]{2,30}\)"),
    "口语标记": re.compile(r"其实|说到底|大概|反正|偏偏|难免|硬是|偏偏|倒(?:是|也)"),
    "直引": _QUOTED,
}


def _add(issues, code, cls, severity, location, problem, action, benefit, evidence,
         preservation="保留原意、事实、语气与限定条件", needs="none"):
    issues.append({
        "code": code, "class": cls, "severity": severity, "location": location,
        "problem": problem, "action": action, "benefit": benefit, "evidence": evidence,
        "preservation": preservation, "needs": needs,
        # 兼容旧台账：reason 曾是唯一说明字段。
        "reason": evidence,
    })


SUPERLATIVE = re.compile(
    r"最(?!近|终|后|先|初|多(?:\d|[一二三四五六七八九十百千万]))|"
    r"唯一|首次|没有之一|第一(?!部分|篇|章|节|课|步|阶段|季度|页|天|次|印象|人称|时间|顺位|梯队|期|卷|集|回|代)"
)


def promise_ledger(title, blocks, thesis=""):
    """标题承诺 → 正文兑现位置。只核对可数、可指的承诺，不评价标题好坏。"""
    text = plain(title)
    heads = [plain(v) for k, v in blocks if k == "h2"]
    body = " ".join(block_text(k, b) for k, b in blocks)
    out = []
    words = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    # “一个”是量词而不是承诺；“两个国家”“三年”也不承诺分项。只有可枚举、且≥2 的数量才进台账，
    # 否则每条正常标题都会被判成“承诺未兑现”，规则就失去了可信度。
    vague = ("国家", "城市", "公司", "人", "行业", "地区", "时代", "年份", "月", "周", "小时",
             "团队", "部门", "作者", "编辑", "读者", "版本", "文件")
    m = re.search(r"([二两三四五六七八九十]|\d{1,2})\s*(个|项|种|步|条|点|问|招|件事)([^，。！？、\s]{0,2})?", text)
    if m and m.group(2) == "个" and m.group(3) and m.group(3).startswith(vague):
        m = None
    if m:
        raw = m.group(1)
        expected = int(raw) if raw.isdigit() else words[raw]
        # 所有有序列表的长度都要参与核对：作者可能把「三个参数」写在某一节里，
        # 而全文最长的有序列表可能是另一节的自查步骤。
        ordered_lists = [len(v["items"]) for k, v in blocks if k == "list" and v["ordered"]]
        ordered = max(ordered_lists, default=0)
        noun = re.search(r"方法|步骤|原因|问题|建议|误区|原则|技巧|理由|教训", m.group(0) + text[m.end():m.end()+4])
        explicit = [h for h in heads if re.match(r"^(?:第?[一二三四五六七八九十\d]+[、．.：:]?|[（(][一二三四五六七八九十\d]+[）)]|(?:方法|步骤|原因|问题|建议|误区|原则|技巧|理由|教训)[一二三四五六七八九十\d]+)", h)
                    or (noun and noun.group() in h and re.search(r"[一二三四五六七八九十\d]", h))]
        # 三处信号任一对得上就算兑现：显式编号标题、全部 H2、最长有序列表。
        # 旧实现固定取「explicit → heads → ordered」的先后顺序，会把「三个参数」这种
        # 由有序列表兑现、但章节数不同的标题不能因此判成未兑现。
        candidates = ([(len(explicit), "explicit")] if explicit else []) \
            + ([(len(heads), "heads")] if heads else []) \
            + [(n, "list") for n in sorted(set(ordered_lists)) if n]
        hit = next((c for c in candidates if c[0] == expected), None)
        observed = hit[0] if hit else (len(explicit) or len(heads) or ordered)
        out.append({"kind": "count", "promise": m.group(0), "expected": expected, "observed": observed,
                    "status": "fulfilled" if hit else ("absent" if not observed else "mismatch"),
                    "locations": ([f"H2「{h}」" for h in (explicit or heads)] if hit and hit[1] != "list"
                                  else ([f"有序列表 {hit[0] if hit else ordered} 项"] if (hit or ordered) else [])),
                    "verification": "structural_only"})
    # 标题里的**带单位数值**是硬承诺：「37%」「9000 人」「200 小时」必须能在正文找到同值。
    # 只认带单位/百分号/货币的数值，裸数字（「3 个方法」）交给上面的数量词规则。
    for value, unit in re.findall(
            r"([+\-−]?\d[\d.,]*)\s*(%|％|个百分点|亿元|万元|亿美元|美元|小时|分钟|万人|人|倍|年|天)", text):
        raw = re.sub(r"\s+", "", value + unit).replace("％", "%").replace("−", "-")
        candidates = {re.sub(r"\s+", "", v) for _, v in facts(body)}
        normalized = {c.replace(",", "").replace("％", "%") for c in candidates}
        # 量词写法会不一致：标题写「1.5万人」，正文写「超过1.5万」。
        # 事实单元把「万」当单位、把人当量词，所以比较时允许去掉末尾的「人」。
        variants = {raw, raw[:-1] if raw.endswith("人") else raw}
        present = bool(variants & candidates) or bool({v.replace(",", "") for v in variants} & normalized)
        out.append({"kind": "number", "promise": raw, "expected": 1, "observed": 1 if present else 0,
                    "status": "fulfilled" if present else ("absent" if not present else "mismatch"),
                    "locations": [f"正文出现 {raw}"] if present else [],
                    "verification": "literal_only"})
    for term in re.findall(r"[《「]([^》」]{2,20})[》」]", text):
        out.append({"kind": "object", "promise": term, "expected": 1,
                    "observed": body.count(term),
                    "status": "fulfilled" if term in body else "absent",
                    "locations": [f"出现 {body.count(term)} 次"] if term in body else []})
    if re.search(r"为什么|为何|如何|怎样|能否|是否|真相|原因", text):
        answer = [h for h in heads if re.search(r"因为|原因|机制|如何|答案|所以|取决于|在于", h)]
        if not answer and thesis:
            answer = ["frontmatter.thesis（语义兑现仍需评审）"]
        out.append({"kind": "question", "promise": "标题提出的问题", "expected": 1,
                    "observed": len(answer),
                    "status": "needs-judgment" if answer else "unclear",
                    "verification": "UNVERIFIED", "locations": answer})
    if SUPERLATIVE.search(text):
        out.append({"kind": "superlative", "promise": "最高级或首次断言", "expected": 1,
                    "observed": 1 if SUPERLATIVE.search(body) else 0,
                    "status": "needs-judgment",
                    "locations": ["标题使用最高级或首次断言；正文须给出比较范围、时间与依据"]})
    return out


# 分句首词复读的停用词：这些词本身是连接或指代，重复不代表排比。
_HEAD_STOP = {"我们", "他们", "你们", "但是", "因为", "所以", "如果", "虽然", "而且",
              "并且", "同时", "对于", "关于", "其中", "然后", "因此", "可是", "不过"}


def _head_token(clause):
    """取分句开头两个汉字；不足两字或不是汉字则返回空串。"""
    for size in (2, 1):
        head = clause[:size]
        if len(head) == size and re.fullmatch(r"[\u4e00-\u9fff]+", head):
            return head
    return ""


def _is_number_token(token):
    return bool(re.fullmatch(r"[一二三四五六七八九十百千万零两0-9]{1,2}", token))


def _sentence_list(text):
    """按句末标点切句，保留标点；用于句长节奏与逐句线索。"""
    return [s.strip() for s in re.split(r"(?<=[。！？!?])", text) if s.strip()]


def _shingles(text, n=3):
    compact = re.sub(r"[\s，。；：、！？,.;:!?“”「」『』（）()]+", "", text)
    return {compact[i:i + n] for i in range(max(0, len(compact) - n + 1))}


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def voice_profile(blocks):
    """作者声音的可核对形态：人称、设问、破折号、旁白、口语标记、直引次数。

    只做计数。它不能证明“读起来像同一个人”，但能证明改稿是否把某类标记整体抹掉。
    """
    body = " ".join(block_text(k, b) for k, b in blocks)
    counts = {name: len(pattern.findall(body)) for name, pattern in VOICE_MARKS.items()}
    paras = [plain(v) for k, v in blocks if k == "p"]
    lengths = [len(_sentence_list(p)) for p in paras if p]
    return {
        "marks": counts,
        "sentences": sum(lengths),
        "paragraphs": len(paras),
        "avg_chars_per_paragraph": round(sum(len(p) for p in paras) / len(paras), 1) if paras else 0,
        "status": "structural_only",
    }


def prose_clues(blocks):
    """文风与机械扩写的**形态线索**（全部 mechanical）。

    每条都附「为什么它可能是问题」与「先确认什么」，因为命中本身不是判决：
    同义反复在必要复现里是合理的，模板排比在强调时也可能成立。判断留给编辑。
    """
    out = []

    def add(code, severity, location, problem, action, benefit, evidence, needs="editor"):
        _add(out, code, "mechanical", severity, location, problem, action, benefit, evidence, needs=needs)

    paragraphs = [(i, k, plain(v) if k in ("p", "h2", "h3") else block_text(k, v))
                  for i, (k, v) in enumerate(blocks, 1)]
    last_prose = max((i for i, kind, text in paragraphs if kind == "p" and text.strip()), default=-1)
    template_hits = {name: [] for name in TEMPLATES}
    meta_hits, restate_blocks = [], []

    for index, kind, text in paragraphs:
        # 逐句文风线索只看作者正文；不能把引语、代码、表格、列表或标题中的
        # 必要复现当成正文同义反复/排比。需要审计那些块时应使用对应的结构规则。
        if kind != "p" or not text.strip():
            continue
        sentences = _sentence_list(text)
        # 1) 元话语：写作过程写进正文
        for m in META_DISCOURSE.finditer(text):
            meta_hits.append((index, m.group()))
        # 2) 模板排比：同类句式在全文反复出现
        for name, pattern in TEMPLATES.items():
            if pattern.search(text):
                template_hits[name].append(index)
        # 3) 同义反复：同段两句相似度过高，第二句没有新增信息
        for a in range(len(sentences)):
            for b in range(a + 1, len(sentences)):
                s1, s2 = plain(sentences[a]), plain(sentences[b])
                if len(s1) < 14 or len(s2) < 14:
                    continue
                if difflib.SequenceMatcher(None, s1, s2, autojunk=False).ratio() >= 0.72:
                    add("CIRCULAR", "note", f"块 {index}",
                        "同段两句字面相似；可能是冗余，也可能是对照、术语定义或必要复现",
                        "先核对两句的语义任务；只有后句没有新增信息时才合并/删除",
                        "保留有用的重复，避免机械删掉引用、定义或对照项",
                        f"「{s1[:18]}…」与「{s2[:18]}…」相似度 ≥0.72")
                    break
        # 4) 主语复读：只比较有效中文开头；数字时间线不是主语复读。
        if len(sentences) >= 3:
            heads = [_head_token(plain(s)) if len(plain(s)) >= 4 else "" for s in sentences]
            run, best, best_token = 1, 1, ""
            for x, y in zip(heads, heads[1:]):
                eligible = x and x not in _HEAD_STOP and not _is_number_token(x)
                if eligible and x == y:
                    run += 1
                    if run > best:
                        best, best_token = run, x
                else:
                    run = 1
            if best >= 3:
                add("REPEAT-SUBJECT", "note", f"块 {index}",
                    "同段连续多句以相同两字开头；可能是节奏、时间线或教学步骤的有意复现",
                    "先确认每句是否增加新信息；只有重复妨碍推进时才合并或换主语",
                    "保留有用的排比、时间线与步骤提示",
                    f"连续 {best} 句同一开头「{best_token}…」")
        # 5) 句长过齐：五句以上且长度几乎相同，节奏失去疏密
        lens = [len(plain(s)) for s in sentences if plain(s)]
        if len(lens) >= 5 and statistics.pstdev(lens) < 3.5:
            add("MONOTONE", "note", f"块 {index}",
                "句长几乎相等，长句短句没有交替",
                "把结论句单独成句，把铺垫合并；只在语义需要处变化",
                "读者能靠节奏分出主张与支撑",
                f"{len(lens)} 句长度 {min(lens)}–{max(lens)} 字，标准差 {statistics.pstdev(lens):.1f}")
        # 6) 抽象名词空转 + 无数字/来源/引语
        abstract_hits = ABSTRACT.findall(text)
        abstract = sorted(set(abstract_hits))
        # 三个以上不同抽象词，或两个不同词反复出现：都说明这一段靠名词在支撑。
        if (len(abstract) >= 3 or (len(abstract) >= 2 and len(abstract_hits) >= 4)) \
                and not re.search(r"\d", text) \
                and not ATTRIB.search(text) and not quoted_spans(text) and len(text) >= 60:
            add("EMPTY-ABSTRACT", "should", f"块 {index}",
                "抽象名词密集且没有数字、来源或引语，读者拿不到可核内容",
                "把其中一个抽象名词换成一个具体的人、数、动作或时间",
                "段落从口号变成可核对的信息",
                f"抽象词 {'、'.join(abstract[:4])}；本段无数字/来源/引语")
        # 7) 定语过长：一句话里「的」层层相扣且中途没有停顿，主语被推到最后。
        #    只在没有任何句读的连续修饰链里报——排比句与术语串里的「的」不算。
        for sentence in sentences:
            line = plain(sentence)
            if len(line) < 45 or "的" not in line:
                continue
            head = line[:line.rfind("的")]
            if head.count("的") >= 4 and not re.search(r"[，；。、：！？]", head):
                add("LONG-ATTRIB", "note", f"块 {index}",
                    "一句话里连续堆叠多层定语，读到句末才知道主语是谁",
                    "拆成两到三句；先给主语和动作，再补限定",
                    "读者不必读到句末才知道在说谁",
                    f"「{line[:22]}…」连续 {head.count('的')} 个「的」{len(line)} 字无停顿")
                break
        # 8) 句首推断跳步：连接词承接，但同段无依据
        for sentence in sentences:
            s = plain(sentence)
            if not INFER_HEAD.search(s) or len(s) < 12:
                continue
            window = " ".join(block_text(k, b) for k, b in blocks[max(0, index - 2):index + 1])
            backed = bool(re.search(r"\d", window) or ATTRIB.search(window)
                          or quoted_spans(window) or re.search(r"https?://", window)
                          or any(k in ("note", "table", "data", "bars", "code", "quote")
                                 for k, _ in blocks[max(0, index - 3):index + 1]))
            if not backed:
                out_window = s
                add("WEAK-INFERENCE", "note", f"块 {index}",
                    "句首以推断连接词承接，附近未定位到显式依据；上下文/修辞可能提供隐含依据",
                    "核对推断链；只有读者无法还原依据时才补证据或限定语",
                    "避免把逻辑提示误当事实证明义务",
                    f"「{out_window[:26]}…」；相邻块未定位到数字、来源、引语或证据块", needs="editor")
            break
        restate_blocks.extend((index, m.group()) for m in RESTATE.finditer(text))
        # 9) 口语序号推进：一段里三个以上序号词，说明并列关系没有变成任何结构
        ordinals = PROSE_ORDINAL.findall(text)
        if len(ordinals) >= 3:
            add("PROSE-ORDINAL", "note", f"块 {index}",
                f"段落用「{'/'.join(ordinals[:4])}」推进；可能需要列表，也可能是清楚的时间线",
                "核对顺序与并列关系；只有列表能提升扫读且不扭曲时间关系时才转换",
                "保留原有时间线与语义层级，避免为排版而排版",
                f"单段出现 {len(ordinals)} 个序号词：{'、'.join(ordinals[:5])}")
        # 10) 分句首词复读：同一两字连续领起三个以上分句（「一起努力，一起成长…」）
        clauses = [plain(c) for c in re.split(r"[，,；;。！？!?、]", text) if plain(c)]
        heads = [_head_token(c) for c in clauses]
        run, best, best_token = 1, 1, ""
        for x, y in zip(heads, heads[1:]):
            if x and x == y:
                run += 1
                if run > best:
                    best, best_token = run, x
            else:
                run = 1
        if best >= 3 and best_token not in _HEAD_STOP and not _is_number_token(best_token):
            add("PARALLEL-HEAD", "note", f"块 {index}",
                f"连续 {best} 个分句以「{best_token}」开头；可能是有意排比或必要选项清单",
                "比较每个分句带来的信息差异；只有重复替代了内容时才改写",
                "保留排比强调与必要选项，不把句式相同误当作信息重复",
                f"本段「{best_token}…」连续 {best} 次")
        # 11) 空洞呼吁收尾：结尾段靠号召与愿景收束，没有可执行动作
        hollow = HOLLOW_CALL.findall(text)
        if index == last_prose and hollow and len(hollow) >= HOLLOW_CALL_MIN and not re.search(r"\d", text) \
                and not ATTRIB.search(text) and not quoted_spans(text):
            add("HOLLOW-CLOSE", "should", f"块 {index}",
                "段落以号召/愿景收束，但没有具体动作、对象或时间",
                "换成下一步可执行的具体动作、一个可核对的数字，或直接删掉这段",
                "读者离开时带走一个能做的事，而不是一句口号",
                f"命中号召词 {'、'.join(sorted(set(hollow))[:4])}；本段无数字/来源/引语")

    for name, where in template_hits.items():
        if len(where) >= 2:
            add("TEMPLATE-REPEAT", "note", f"块 {'、'.join(map(str, where[:5]))}",
                f"「{name}」句式在全文出现 {len(where)} 次；相同句式可能承担不同语义任务",
                "逐处比较其论证/叙事功能；仅在复述且无信息增量时改写",
                "不把正常的对比、递进或时间表达误判为模板",
                f"模板「{name}」命中 {len(where)} 处")
    if meta_hits:
        add("META-DISCOURSE", "note", f"块 {'、'.join(str(i) for i, _ in meta_hits[:4])}",
            "正文出现讲述写作过程的话（元话语）",
            "逐条看：能删就删；只有帮助定位时保留一处",
            "首屏与段落交还给内容",
            "命中：" + "、".join(sorted({m for _, m in meta_hits})[:4]))
    if len(restate_blocks) >= 2:
        add("RESTATE-MARKER", "note", f"块 {'、'.join(str(i) for i, _ in restate_blocks[:4])}",
            f"「换句话说/也就是说」类自我解释出现 {len(restate_blocks)} 次",
            "检查每次换说是否真的更清楚；若只是复述，删掉后一次",
            "解释只在不清楚之处出现",
            "命中：" + "、".join(sorted({w for _, w in restate_blocks})[:4]))
    return out


def section_gain(blocks):
    """逐节信息增量（可核对版）：新事实单元、与前文的相似度、篇幅占比。

    “新事实为零 + 与前节高度相似”才提示复述；纯叙事文章没有数字也不该被误报，
    因此只对证据敏感的类型（见 audit）使用该线索。
    """
    sections = _section_stats(blocks)
    seen_facts, seen_text, out = set(), [], []
    for section in sections:
        start = section["block"]
        end = next((x["block"] for x in sections if x["block"] > start), len(blocks) + 1)
        members = blocks[start - 1:end - 1]
        text = " ".join(block_text(k, v) for k, v in members)
        here = {_fact_key(*f) for f in facts(text)}
        here_facts = {(_fact_key(kind, value)): value for kind, value in facts(text)}
        new_facts = sorted(value for key, value in here_facts.items() if key not in seen_facts)
        quotes = quoted_spans(text)
        similarity = max((_jaccard(_shingles(text), t) for t in seen_text), default=0.0)
        out.append({
            "heading": section["heading"], "block": start, "chars": section["chars"],
            "new_facts": new_facts, "new_fact_count": len(here - seen_facts),
            "quoted": quotes[:3], "similarity_to_previous": round(similarity, 3),
            "image": any(k == "img" for k, _ in members),
            "evidence_blocks": [i for i, (k, _) in enumerate(members, start) if k in ("note", "table", "data", "bars", "code")],
            "verdict": "UNVERIFIED",
        })
        seen_facts |= here
        seen_text.append(_shingles(text))
    return out


def decision_chain(meta, blocks, key=None):
    """内容类型 → 视觉概念 → 信息关系 → 构图 → 排版：把已声明的决策摆成一条可核对的链。

    `declared` 只表示「作者写了」，`evidence` 只表示「文章结构支持这种说法」。
    两者都不等于「这个决定是对的」——审美结论仍须 Gate 3 人工判断。
    """
    type_key, type_ok = resolve_type(meta.get("article_type", ""))
    strategy = TYPES.get(type_key)
    kinds = [k for k, _ in blocks]
    fs = first_screen(meta, blocks)
    images = [(b[0], (b[2] or "").strip()) for k, b in blocks if k == "img"]
    roles = [r.split()[0] for _, r in images if r]
    fact_roles = {"证据", "数据", "explain", "evidence", "data", "structure", "结构", "对比", "compare"}
    return {
        "theme": key or meta.get("theme", ""),
        "steps": [
            {"step": "内容类型", "declared": meta.get("article_type", "") or "未声明",
             "derived": (strategy or {}).get("label", ""),
             "evidence": "类型策略已解析" if type_ok and strategy else "类型未识别，策略未生效",
             "status": "OK" if type_ok and strategy else "MISSING"},
            {"step": "视觉概念", "declared": meta.get("visual_concept", "") or "未声明",
             "derived": "", "evidence": "一句话说明最重要的关系与第一眼焦点",
             "status": "DECLARED" if meta.get("visual_concept") else "MISSING"},
            {"step": "信息关系", "declared": meta.get("information_shape", "") or "未声明",
             "derived": f"{kinds.count('h2')} 节 · 证据块 {sum(k in ('note','table','data','bars','code') for k in kinds)} · "
                        f"图片 {len(images)}",
             "evidence": "章节数、证据块数与图片职责构成实际的信息形状",
             "status": "DECLARED" if meta.get("information_shape") else "INFERRED"},
            {"step": "构图", "declared": meta.get("composition", "") or "未声明",
             "derived": f"首屏 {' > '.join(fs['layers']) or '空'}（重元素 {fs['weight']}）",
             "evidence": "首屏只应有一个入口；证据图须紧邻其解释文字",
             "status": "DECLARED" if meta.get("composition") else "INFERRED"},
            {"step": "素材策略", "declared": meta.get("asset_strategy", "") or "未声明",
             "derived": "、".join(sorted(set(roles))) or "无正文图片",
             "evidence": "图片职责分布；事实类职责需可核来源",
             "status": "DECLARED" if meta.get("asset_strategy") else ("NONE" if not images else "INFERRED")},
            {"step": "排版", "declared": meta.get("design_rationale", "") or "未声明",
             "derived": f"主题 {key or meta.get('theme', '')}",
             "evidence": "主题轴取值已校验（见 theme_axes）",
             "status": "DECLARED" if meta.get("design_rationale") else "MISSING"},
        ],
        "fact_role_images": sum(1 for r in roles if r in fact_roles),
        "note": "DECLARED=作者已写；INFERRED=从结构推出；MISSING=缺这一环。三者都不构成审美结论。",
    }


def _section_stats(blocks):
    sections, current = [], None
    for index, (kind, value) in enumerate(blocks, 1):
        if kind == "h2":
            if current:
                sections.append(current)
            current = {"heading": plain(value), "block": index, "chars": 0, "kinds": []}
        elif current:
            if kind in ("p", "list", "table", "data", "bars"):
                current["chars"] += visible_len(block_text(kind, value))
            current["kinds"].append(kind)
    if current:
        sections.append(current)
    return sections


EVIDENCE_KINDS = {"note", "table", "data", "bars", "quote", "code"}


def _text_issues(blocks, sections=None, article_type=""):
    """逐段文字与整体结构线索；每条自己的 class 决定它是形态还是判断入口。"""
    issues, paragraphs, seen = [], [], {}
    # --- 形态检查（mechanical） ---
    for index, (kind, value) in enumerate(blocks, 1):
        text = block_text(kind, value)
        if kind in ("p", "h2", "h3"):
            normalized = re.sub(r"\s+", "", plain(value))
            if kind == "p":
                paragraphs.append((index, normalized, value))
            if normalized and normalized in seen and normalized not in {"点击这里显示解决方案", "点击此处显示解决方案"}:
                _add(issues, "DUP-EXACT", "mechanical", "note", f"块 {index}",
                     "发现与前文完全相同的文字；跨练习说明或控件文案可能需要复用",
                     "确认是否面对同一读者/同一任务；只有无功能的重复才合并",
                     "避免删除练习所需的就地说明或交互标签",
                     f"与块 {seen[normalized]} 的可见文字完全相同")
            seen[normalized] = index
            if kind == "p" and len(normalized) > 260:
                _add(issues, "LONG-PARA", "mechanical", "note", f"块 {index}",
                     "段落篇幅较长，可能包含多个语义任务；长度本身不构成缺陷",
                     "只在出现论点/证据/限制的语义断点时拆分",
                     "让结构服务语义，不按字符数机械切段",
                     f"该段去标记后为 {len(normalized)} 字；须人工判断")
            prose_for_length = re.sub(r"https?://\S+", "", plain(value))
            for sentence in re.split(r"(?<=[。！？])", prose_for_length):
                sentence_length = len(re.sub(r"\s", "", sentence))
                if sentence_length > 90:
                    _add(issues, "LONG-SENT", "mechanical", "note", f"块 {index}",
                         "可见句子较长；引语、专名清单、术语定义与时间线可能应保持原样",
                         "先找主干和语义停顿；只有拆分能提升理解时才改",
                         "读者能一遍读完一个判断，同时保留引文和术语完整性",
                         f"「{sentence.strip()[:24]}…」{sentence_length} 字")
                    break
            nearby = blocks[max(0, index - 2):min(len(blocks), index + 1)]
            has_source = any(k == "note" for k, _ in nearby) or bool(re.search(r"https?://", text))
            # 日历日期本身不是统计证据需求；人物叙事中的「1990年」不应与「37%」同规则。
            if kind == "p" and re.search(r"\d+(?:\.\d+)?(?:%|％|亿元|万元|万人|倍|小时|美元)", text) and not has_source:
                _add(issues, "NUM-NO-SOURCE", "mechanical", "should", f"块 {index}",
                     "关键数字附近未见可核对依据", "核查数字并就近补口径",
                     "读者可判断时间、口径与结论力度", "相邻块未见来源 note 或 HTTP(S) 链接",
                     "不补写无法确认的来源；必要时限定、删除或标未核", needs="fact-check")
            if kind == "p" and ATTRIB.search(text) and not has_source:
                _add(issues, "ATTR-NO-SOURCE", "mechanical", "should", f"块 {index}",
                     "来源型表述没有就近指向依据", "补原始出处或降级表述",
                     "区分可核事实与作者转述", "出现“数据显示/研究表明/据…”而相邻块无来源", needs="fact-check")
            causal_match = CAUSAL.search(text) if kind == "p" else None
            nominal_proof = bool(causal_match and causal_match.group(0).startswith("证明")
                                 and re.search(r"的证明(?:都|被|可|可以|是)", text[max(0, causal_match.start()-4):causal_match.end()+4]))
            quoted_causal = bool(causal_match and any(causal_match.group(0) in quote for quote in quoted_spans(text)))
            if causal_match and not nominal_proof and not quoted_causal and not HEDGE.search(text):
                _add(issues, "CAUSAL-STRONG", "judgment", "should", f"块 {index}",
                     "可能存在因果/确定性措辞；引用中的原话和名词‘证明’不等于作者的因果断言",
                     "核对作者自己的推断链；只有断言强于证据时才补限定",
                     "不把引用或名词误读为因果结论",
                     f"候选措辞「{causal_match.group(0)}」；句内未见限制词", needs="editor")
            if kind == "p" and CLICHE.search(text):
                _add(issues, "OPENING-CLICHE", "mechanical", "should", f"块 {index}",
                     "套语开头占据入口，没有给出信息", "删除套语，直接给事实或判断",
                     "首屏留在有效信息上", f"命中套语：{CLICHE.search(text).group(0)}")
            absolute_match = ABSOLUTE.search(text) if kind == "p" else None
            local_example_observation = bool(absolute_match and absolute_match.group(0) == "显然"
                                             and re.search(r"显然[，,]?\s*(?:这|这并不|这不是|这并非)", text))
            if absolute_match and not local_example_observation and not HEDGE.search(text):
                _add(issues, "GENERALIZE", "judgment", "should", f"块 {index}",
                     "绝对化措辞可能把局部经验写成普遍规律；对当前示例的评价不等于泛化",
                     "核对断言范围与证据；只在声称普遍规律时补范围或反例",
                     "区分经验判断与对当前示例的即时评价",
                     f"出现“{absolute_match.group(0)}”且句内无限定", needs="editor")
            ordinal_count = len(PROSE_ORDINAL.findall(plain(value)))
            if kind == "p" and ordinal_count < 3 and len(re.findall(r"首先|其次|再次|最后|第一|第二|第三", text)) >= 3 and len(text) > 80:
                _add(issues, "PROSE-LIST", "mechanical", "note", f"块 {index}",
                     "段内出现多个顺序连接词；可能是时间线，也可能适合列表",
                     "确认项目是否可独立列举且顺序有意义；避免与序号线索重复提示",
                     "并列关系清楚，同时不破坏时间线",
                     "存在顺序连接词；列表与否需编辑判断")
        if kind in ("h2", "h3"):
            nxt = blocks[index][0] if index < len(blocks) else ""
            if nxt in ("h2", "h3") or not nxt:
                _add(issues, "SECTION-EMPTY", "mechanical", "must", f"块 {index}",
                     "标题之后没有内容", "补写该节或删除标题", "目录不与空章节对应",
                     f"标题「{plain(value)}」后紧接 {nxt or '文末'}")
        if kind == "h2" and not plain(value).strip():
            _add(issues, "SECTION-EMPTY", "mechanical", "must", f"块 {index}", "空标题", "补写或删除", "结构可读", "标题为空")

    for pos, (i, norm, _) in enumerate(paragraphs):
        if len(norm) < 36:
            continue
        for j, other, _ in paragraphs[:pos]:
            if len(other) >= 36 and norm != other:
                if difflib.SequenceMatcher(None, norm, other, autojunk=False).ratio() >= 0.9:
                    _add(issues, "DUP-NEAR", "mechanical", "should", f"块 {i}",
                         "两段高度相似，可能重复推进同一信息", "比较后合并、分工或保留",
                         "每段承担不同论证任务",
                         f"与块 {j} 的字符序列相似度 ≥0.90；须人工判断是否为必要复现")
                    break

    emphasis_spans = re.compile(r"\*\*[^*]+?\*\*|==[^=]+?==|<u>[^<]+?</u>")
    speaker_label = re.compile(r"\*\*[A-Z][A-Z0-9]{0,3}[:：]\*\*")
    marks = 0
    for k, v in blocks:
        if k != "p":
            continue
        raw = speaker_label.sub("", block_text(k, v))
        marks += len(emphasis_spans.findall(raw))
    if marks > max(6, len(paragraphs)):
        _add(issues, "EMPHASIS-OVERUSE", "mechanical", "note", "全文",
             "强调样式出现较密；问答说话人标签等格式不计作正文强调",
             "只检查真正强调的词句是否都改变理解；不因格式标签删改采访结构",
             "让视觉强调承担语义，而不破坏问答导航",
             f"正文强调跨度 {marks} 处 / 段落 {len(paragraphs)} 个")

    # --- 台账与整体结构 ---
    sections = _section_stats(blocks) if sections is None else sections
    total = sum(s["chars"] for s in sections)
    if len(sections) >= 2 and total:
        for section in sections:
            share = section["chars"] / total
            heading = section["heading"]
            expected_short = bool(re.search(r"参见|参考(?:资料|文献)?|总结|结论|结语|大功告成", heading))
            expected_tutorial_core = article_type == "tutorial" and bool(re.search(r"示例|练习|实战|项目|游戏", heading))
            if (section["chars"] < 45 and not expected_short) or (share > 0.7 and not expected_tutorial_core):
                _add(issues, "SECTION-SKEW", "mechanical", "note",
                     f"块 {section['block']}（{heading}）", "章节篇幅与其他章节差异较大；短参见/总结或核心教程案例本来就可能如此",
                     "核对章节功能与信息重量；比例只定位疑点，不单独触发拆分或扩写",
                     "保留正常的结尾、参考链接与核心案例章节",
                     f"本章约 {section['chars']} 字，占有标题章节文字 {share:.0%}；比例仅作定位")

    if blocks and blocks[-1][0] == "p":
        head = " ".join(block_text(k, v) for k, v in blocks[:3])
        tail_facts = [f for f in facts(block_text("p", blocks[-1][1])) if f[0] in ("num", "date")]
        fresh = [f for f in tail_facts if f[1] not in head and f[1] not in " ".join(
            block_text(k, v) for k, v in blocks[:-1])]
        if fresh:
            _add(issues, "CONCLUDE-NEW-EVIDENCE", "judgment", "note", f"块 {len(blocks)}",
                 "末段首次出现数字/日期；可能是新证据，也可能是相关背景或时间线",
                 "确认该事实的来源和收束作用；只有实质新证据才需前移并展开",
                 "保留有效历史背景与时间线，避免以位置代替论证判断",
                 f"字面上首次出现：{'、'.join(f[1] for f in fresh[:3])}", needs="editor")

    issues.extend(prose_clues(blocks))
    return issues


def _judgment_issues(meta, blocks, type_key, sections=None):
    """只为编辑/模型定位论证与类型疑点；严重级别不得高于其证据。"""
    issues = []
    sections = _section_stats(blocks) if sections is None else sections
    strategy = TYPES.get(type_key)
    evidence_kinds = EVIDENCE_KINDS
    # --- 论证层（judgment）：只定位，不判决 ---
    for index, (kind, value) in enumerate(blocks, 1):
        if kind != "p":
            continue
        raw_text = block_text(kind, value)
        text = plain(value)
        if type_key == "tutorial":
            # 教程中的操作指令和概念解释通常由步骤/代码示例承担证明责任；只把
            # 可核的版本、数值、兼容性等事实送入来源复核，避免给每句讲解强加引文。
            claim_like = bool(re.search(r"版本|兼容|支持(?:的|率|到)|不支持|报告显示|数据显示|研究表明|据统计", text))
        else:
            claim_like = bool(re.search(r"应该|必须|意味着|说明|证明|表明|因此|所以|结论|关键|本质", text))
        # index 为 1-based；当前块在数组 index-1。覆盖前两块、当前块与后两块。
        window = blocks[max(0, index - 3):min(len(blocks), index + 2)]
        # plain() 会去掉 Markdown 链接目标；在原始块上判来源，否则有链接的段落会被误报。
        backed = any(k in evidence_kinds for k, _ in window) or bool(re.search(r"https?://|\d{4}", raw_text))
        # 句末为设问、且没有独立事实/数字时，连接词“所以”不应自动变成无依据断言。
        rhetorical_question = text.rstrip().endswith(("?", "？")) and not re.search(r"\d|必须|应该|证明|表明", text)
        if claim_like and not backed and not rhetorical_question and len(text) > 40:
            severity = "note" if type_key in ("opinion", "tutorial") else "should"
            _add(issues, "ORPHAN-CLAIM", "judgment", severity, f"块 {index}",
                 "判断性句子附近未定位到依据；价值立场、教程解释或直接引语可能无需外部引用",
                 "先判断是否为可核事实/推断；仅在来源缺失且结论需证据时补证据或限定",
                 "区分事实、观点、示例与引述，不把价值判断一律变成引文任务",
                 "相邻块未定位到来源、表格、引文或代码",
                 needs="fact-check")
    # 章节是否只在复述主张：比较 thesis 与每个 H2 之后的第一段
    thesis = re.sub(r"\s+", "", plain(meta.get("thesis", "")))
    if thesis and len(thesis) >= 8:
        for section in sections:
            start = section["block"]            # H2 在 blocks 里是 1-based 位置
            first = next((block_text(k, v) for k, v in blocks[start:] if k == "p"), "")
            if not first:
                continue
            if difflib.SequenceMatcher(None, thesis,
                                       re.sub(r"\s+", "", plain(first)), autojunk=False).ratio() > 0.62:
                _add(issues, "RESTATE-THESIS", "judgment", "should",
                     f"块 {section['block']}（{section['heading']}）",
                     "该节首句与核心主张高度重合，可能只是复述", "推进新证据或删去该节",
                     "每节都带来新信息", "与 thesis 的相似度 > 0.62", needs="editor")

    # 观点类：是否出现反例或限制
    if type_key == "opinion":
        body = " ".join(block_text(k, b) for k, b in blocks)
        if not re.search(r"不过|但是|然而|反例|相反|也有人|另一种|代价|局限|例外", body):
            _add(issues, "NO-COUNTER", "judgment", "should", "全文",
                 "评论没有处理最强反例", "写出反例并回应，或缩小主张范围",
                 "读者能判断作者是否考虑过相反证据", "全文未见转折/反例/局限表述", needs="editor")
    if type_key == "news":
        if blocks and blocks[0][0] not in ("lead", "p", "data", "table"):
            _add(issues, "OPENING-TYPE", "judgment", "should", "首屏",
                 "新闻稿首屏没有先给事实", f"先给：{strategy['opening']}",
                 "读者在首屏拿到可核对的事实", "首个正文块为引文或图片", needs="editor")
    if type_key == "tutorial":
        body = " ".join(block_text(k, b) for k, b in blocks)
        if not re.search(r"版本|前提|要求|需要先|环境|依赖", body):
            _add(issues, "MISSING-PREREQ", "judgment", "should", "全文",
                 "教程未写前提或版本", "补读者进入步骤前必须满足的条件",
                 "失败可归因，读者不会在错误前提下照着做", "全文未见前提/版本表述", needs="editor")
        if not re.search(r"失败|报错|回退|撤销|如果没有|不适用|边界|错误|不起作用|不工作|不能正常|无法正常|无法运行|重置|清除|卡住|解决方案", body):
            _add(issues, "MISSING-FAILURE", "judgment", "should", "全文",
                 "教程只写成功路径", "补失败条件与回退方式",
                 "读者在出问题时能自行判断", "全文未见失败/回退表述", needs="fact-check")

    return issues


def _promise_issues(promises):
    """把标题结构候选转成复核事项；语义兑现不由关键词或 H2 数量认证。"""
    issues = []
    for p in promises:
        if p["kind"] == "number" and p["status"] == "absent":
            _add(issues, "PROMISE-NUMBER", "mechanical", "should", "标题与全文",
                 f"标题里的数值「{p['promise']}」在正文没有同值出现",
                 "正文补出该数值（含口径与期间），或改标题",
                 "标题的数字承诺能被逐字核对",
                 f"标题承诺 {p['promise']}；正文未见同值")
        if p["kind"] == "count" and p["status"] != "fulfilled":
            _add(issues, "PROMISE-COUNT", "judgment", "should", "标题与全文",
                 "标题数量承诺尚未在可见结构中逐项对齐", "通读正文确认分项；需要时补定位或收窄标题",
                 "避免把普通段落中的真实回答误判为未兑现，也避免漏掉缺失分项",
                 f"标题承诺 {p['expected']} 项；H2/有序列表可见 {p['observed']} 项；普通段落未由机器计数",
                 needs="editor")
        if p["kind"] == "object" and p["status"] == "absent":
            _add(issues, "PROMISE-OBJECT", "judgment", "should", "标题与全文",
                 "标题中的明确对象未以同一名称在正文出现", "确认是否使用简称或已实际兑现；必要时补定位或收窄标题",
                 "让标题对象能被读者定位，同时允许合理的名称变化",
                 f"标题对象“{p['promise']}”未以同一名称出现；语义等价需编辑确认", needs="editor")
        if p["kind"] == "question" and p["status"] == "unclear":
            _add(issues, "PROMISE-QUESTION", "judgment", "note", "标题与全文",
                 "问题/‘如何’型标题中，机器未定位到回答标题或 thesis；不等于文章没有回答",
                 "人工判断叙事、正文或结尾是否已经兑现；仅在读者难以定位时补答复结构",
                 "避免把叙事型‘如何’标题误判为未兑现，也保留真正缺答的提醒",
                 "未提供 thesis，且 H2 未见显式回答性表述；语义兑现必须人工确认", needs="editor")
        if p["kind"] == "superlative":
            _add(issues, "PROMISE-SUPERLATIVE", "judgment", "note", "标题",
                 "最高级断言需要比较范围与依据", "写明比较范围、时间与来源",
                 "读者能核对最高级或首次断言是否成立", "标题含明确的最高级/首次断言语素；最近、最终等普通词不计", needs="fact-check")

    return issues


def audit(meta, blocks):
    """返回完整审计结果：brief / strategy / claim_map / promise / issues / ledger。"""
    title = meta.get("title", "").replace("|", "｜")
    type_key, type_ok = resolve_type(meta.get("article_type", ""))
    strategy = TYPES.get(type_key)

    sections = _section_stats(blocks)
    issues = _text_issues(blocks, sections, type_key)
    issues.extend(_judgment_issues(meta, blocks, type_key, sections))
    evidence_kinds = EVIDENCE_KINDS

    # --- 未知项：新闻/分析必须给「还不知道什么」，否则读者会把推断当已确认 ---
    if type_key in ("news", "analysis"):
        has_unknown = any(k == "unknown" for k, _ in blocks) \
            or bool(re.search(r"尚不清楚|尚不能|尚未|未确认|不能确认|无法确认|未知项|未知|"
                              r"未披露|未公开|不得而知|待确认|未经证实|没有(?:公开|披露)|缺乏数据", " ".join(
                block_text(k, b) for k, b in blocks)))
        if not has_unknown:
            _add(issues, "UNKNOWN-MISSING", "judgment", "should", "全文",
                 "全文没有标出未知项，事实与推断之间缺一道边界",
                 "补一段「尚不清楚/未确认」：写清缺哪一环、由谁才能确认",
                 "读者不会把作者的推断读成已确认的事实",
                 "未见 unknown 块或未知类表述", needs="editor")

    # --- 逐节信息增量（mechanical 线索 + judgment 判断入口） ---
    gains = section_gain(blocks)
    if type_key in ("analysis", "news", "tutorial", "opinion"):
        for gain in gains:
            repeat = gain["similarity_to_previous"] >= 0.35
            empty = gain["new_fact_count"] == 0 and not gain["quoted"] and not gain["image"]
            if gain["chars"] >= 80 and repeat and empty:
                _add(issues, "SECTION-NO-GAIN", "judgment", "should",
                     f"块 {gain['block']}（{gain['heading']}）",
                     "该节与前文高度相似，且没有新事实、引语或图像",
                     "合并到相邻节、补该节独有的证据，或删去这一节",
                     "每一节都带来读者此前没有的信息",
                     f"与前文相似度 {gain['similarity_to_previous']:.2f}；新事实 0", needs="editor")

    # --- 标题承诺 ---
    promises = promise_ledger(title, blocks, meta.get("thesis", ""))
    issues.extend(_promise_issues(promises))

    # --- brief ---
    brief_keys = ("audience", "reading_context", "purpose", "thesis")
    missing = [k for k in brief_keys if not meta.get(k)]
    if not type_ok:
        _add(issues, "TYPE-UNKNOWN", "mechanical", "should", "frontmatter",
             f"article_type「{meta.get('article_type')}」未识别", "改用已知类型或删去",
             "类型策略能被真实应用", f"可选：{'、'.join(t['label'] for t in TYPES.values())}")

    severity_rank = {"must": 0, "should": 1, "note": 2}
    issues.sort(key=lambda x: (severity_rank[x["severity"]], x["code"], x["location"]))

    argument_map = []
    for section in sections:
        start = section["block"]
        end = next((x["block"] for x in sections if x["block"] > start), len(blocks) + 1)
        members = list(enumerate(blocks[start - 1:end - 1], start))
        argument_map.append({
            "section": section["heading"], "block": start,
            "claim_candidates": [{"block": i, "text": plain(v)[:180]} for i, (k, v) in members
                                 if k == "p" and re.search(r"应该|必须|意味着|说明|证明|表明|因此|所以|关键|本质", block_text(k, v))],
            "evidence_candidates": [{"block": i, "kind": k, "text": block_text(k, v)[:180]} for i, (k, v) in members if k in evidence_kinds],
            "boundary_candidates": [{"block": i, "text": block_text(k, v)[:180]} for i, (k, v) in members
                                    if k in ("p", "note", "quote") and re.search(r"但|不过|限制|边界|例外|不能|仅|可能|尚未|未知", block_text(k, v))],
            "inference_relation": "UNVERIFIED", "title_contribution": "UNVERIFIED",
            "counterexample_response": "UNVERIFIED", "information_gain": "UNVERIFIED",
        })
    claim_map = {
        "title": title,
        "thesis": meta.get("thesis", ""),
        "sections": [s["heading"] for s in sections],
        "evidence_blocks": sum(1 for k, _ in blocks if k in evidence_kinds),
        "claim_blocks": sum(1 for k, v in blocks if k == "p" and re.search(r"应该|必须|意味着|说明|表明|因此|所以", block_text(k, v))),
    }
    summary = {
        "mechanical": sum(1 for i in issues if i["class"] == "mechanical"),
        "judgment": sum(1 for i in issues if i["class"] == "judgment"),
        "must": sum(1 for i in issues if i["severity"] == "must"),
    }
    return {
        "brief": {k: meta.get(k, "") for k in brief_keys},
        "missing_brief": missing,
        "type": {"key": type_key, "label": strategy["label"] if strategy else "", "recognized": type_ok,
                 "strategy": strategy},
        "decision": {k: meta.get(k, "") for k in
                     ("composition", "visual_concept", "information_shape", "asset_strategy",
                      "mobile_risk", "design_rationale")},
        "claim_map": claim_map,
        "argument_map": argument_map,
        "semantic_review": {"status": "UNVERIFIED", "questions": strategy["editorial_work"]["questions"] if strategy else [],
                            "required": SEMANTIC_REVIEW.get(type_key, ["标题兑现", "信息增量", "事实边界", "原意与作者声音"])},
        "promise": promises,
        "issues": issues,
        "summary": summary,
        # 分歧必须显式分开——机器线索 / 编辑判断 / 未验证的语义结论。
        "evidence_classes": {
            "mechanical": "只表示形态命中，不表示写得好或坏；每条的 evidence 字段给出命中依据",
            "judgment": "只定位疑点并写明「需要谁判断」，结论由编辑或模型给出，脚本不下结论",
            "verification": "事实核真、语义兑现、审美与真机验收在本层一律 UNVERIFIED",
        },
        "section_gain": gains,
        "voice": voice_profile(blocks),
        "decision_chain": decision_chain(meta, blocks),
        "fact_verification": "not_performed",
        "visual_acceptance": "pending",
        "wechat_acceptance": "not_tested",
    }


def strategy_notes(meta, blocks):
    """按内容类型给编辑的下一步动作。只给动作，不代写正文。"""
    key, _ = resolve_type(meta.get("article_type", ""))
    if not key:
        return ["先判断文章类型与读者任务；类型决定入口、证据密度与标题承诺的兑现方式。"]
    t = TYPES[key]
    work = t["editorial_work"]
    notes = [f"类型：{t['label']}｜读者问题：{t['reader_question']}",
             f"入口应先给：{t['opening']}",
             f"结构参考：{' → '.join(t['structure'])}",
             f"证据要求：{t['evidence']}",
             f"常见失败：{'；'.join(t['risks'])}",
             f"优先保护：{work['protect']}", f"编辑顺序：{work['prefer']}",
             f"语义复核：{' / '.join(work['questions'])}"]
    heads = [plain(v) for k, v in blocks if k == "h2"]
    if key == "analysis" and heads and not re.search(r"限制|边界|反例|例外|风险", " ".join(heads)):
        notes.append("动作：补一节「限制与反例」，或把限定写进结论句。")
    if key == "news" and not any(re.search(r"\d{4}", block_text(k, v)) for k, v in blocks[:4]):
        notes.append("动作：首屏补时间与来源，读者需要先知道这是什么时候的事。")
    if key == "tutorial" and not any(k == "list" and v["ordered"] for k, v in blocks):
        notes.append("动作：把操作序列改为有序列表，顺序本身就是信息。")
    if key == "profile" and not any(k == "quote" for k, _ in blocks):
        notes.append("动作：若有人物原话，用带出处的引文；没有就不要编写。")
    return notes


def render_report(result, facts_diff=None, ledger_problems=None, voice_diff=None):
    """把审计结果排成可交付的「修改记录 / 验收」文本。"""
    lines = ["# 编辑审计", ""]
    t = result["type"]
    lines.append(f"- 类型：{t['label'] or '未判断'}" + ("" if t["recognized"] else "（未识别，需修正）"))
    s = result["summary"]
    lines.append(f"- 形态问题 {s['mechanical']} 项 · 判断类问题 {s['judgment']} 项 · 必须修 {s['must']} 项")
    lines.append(f"- 缺 brief 字段：{'、'.join(result['missing_brief']) or '无'}")
    lines.append("- 本类语义验收（均 UNVERIFIED）：" + " / ".join(result["semantic_review"]["required"]))
    if result["promise"]:
        lines += ["", "## 标题承诺", "", "| 类型 | 承诺 | 期望 | 可见 | 状态 |", "|---|---|---:|---:|---|"]
        for p in result["promise"]:
            lines.append(f"| {p['kind']} | {p['promise']} | {p['expected']} | {p['observed']} | {p['status']} |")
    if result["issues"]:
        # 机械线索与编辑判断分表呈现：混在一起时，读者会把「命中关键词」读成「质量结论」。
        lines += ["", "## 问题：机器线索（mechanical）", "",
                  "> 只表示形态命中，不表示写得好或坏；每条都给出命中依据，判断请回到原文。", "",
                  "| 级别 | 位置 | 问题 | 动作 | 依据 |", "|---|---|---|---|---|"]
        mechanical = [i for i in result["issues"] if i["class"] == "mechanical"]
        for i in mechanical:
            lines.append(f"| {i['severity']} | {i['location']} | {i['problem']} | {i['action']} | {i['evidence']} |")
        if not mechanical:
            lines.append("| — | — | 无形态线索 | — | — |")
        lines += ["", "## 问题：编辑判断（judgment）", "",
                  "> 脚本只定位疑点并写明需要谁判断；结论由编辑或模型给出，不在此处。", "",
                  "| 级别 | 位置 | 疑点 | 动作 | 收益 | 依据 | 需要 |", "|---|---|---|---|---|---|---|"]
        judgment = [i for i in result["issues"] if i["class"] == "judgment"]
        for i in judgment:
            lines.append(f"| {i['severity']} | {i['location']} | {i['problem']} | {i['action']} | "
                         f"{i['benefit']} | {i['evidence']} | {i['needs']} |")
        if not judgment:
            lines.append("| — | — | 无判断类疑点 | — | — | — | — |")
    lines += ["", "## 语义评审工作单（UNVERIFIED，须由编辑逐项填写）", "",
              "| 章节/位置 | 主张候选 | 证据候选 | 推导关系 | 反例与边界 | 信息增量 |",
              "|---|---|---|---|---|---|"]
    for section in result.get("argument_map", []):
        claims = "；".join(x["text"] for x in section["claim_candidates"]) or "未定位，需通读"
        evidence = "；".join(f"块{x['block']} {x['kind']}" for x in section["evidence_candidates"]) or "未定位，不等于不存在"
        bounds = "；".join(x["text"] for x in section["boundary_candidates"]) or "UNVERIFIED"
        lines.append(f"| {section['section']}（块 {section['block']}） | {claims.replace('|', '｜')} | {evidence} | UNVERIFIED | {bounds.replace('|', '｜')} | UNVERIFIED |")
    if result.get("section_gain"):
        lines += ["", "## 逐节信息增量（可核对，不评好坏）", "",
                  "| 章节 | 块 | 字数 | 新事实单元 | 与前文相似度 | 证据块 | 引语/图 |",
                  "|---|---:|---:|---|---:|---|---|"]
        for g in result["section_gain"]:
            new_facts = "、".join(g["new_facts"][:3]) or "0"
            lines.append(f"| {g['heading']} | {g['block']} | {g['chars']} | {new_facts} | "
                         f"{g['similarity_to_previous']:.2f} | {len(g['evidence_blocks'])} | "
                         f"{'是' if (g['quoted'] or g['image']) else '否'} |")
        lines += ["", "「新事实单元」只统计数字/日期/链接等字面单元；**没有数字的叙事节不等于没有增量**，"
                      "语义增量仍须人工判断。"]
    if result.get("voice"):
        v = result["voice"]
        marks = "、".join(f"{k} {v}" for k, v in v["marks"].items())
        lines += ["", "## 作者声音画像（形态）", "",
                  f"- 标记计数：{marks}",
                  f"- 段落 {v['paragraphs']} · 句 {v['sentences']} · 段均 {v['avg_chars_per_paragraph']} 字",
                  "- 这是可核对的形态，不证明「读起来像同一个人」；`--against` 会用同一口径比对原稿与改稿。"]
    if result.get("decision_chain"):
        lines += ["", "## 设计决策链", "", "| 环节 | 声明的 | 结构推出的 | 状态 | 说明 |", "|---|---|---|---|---|"]
        for step in result["decision_chain"]["steps"]:
            lines.append(f"| {step['step']} | {step['declared']} | {step['derived']} | "
                         f"{step['status']} | {step['evidence']} |")
        lines.append(f"\n{result['decision_chain']['note']}")
    if facts_diff is not None:
        lines += ["", "## 事实单元比对（机械，不等于核真）", "",
                  f"- 保留 {len(facts_diff['preserved'])} / 原稿 {facts_diff['source_units']}",
                  f"- 删除：{'、'.join(facts_diff['dropped']) or '无'}",
                  f"- 新增：{'、'.join(facts_diff['introduced']) or '无'}",
                  f"- 日期精度变化：{facts_diff.get('precision_changes', [])}",
                  f"- 限定变化：{facts_diff.get('qualifier_changes', [])}",
                  f"- 引语变化：删除 {facts_diff.get('dropped_quotes', [])}；新增 {facts_diff.get('introduced_quotes', [])}",
                  "- 出现次数变化：" + str(facts_diff.get('occurrence_changes', []))]
    if voice_diff is not None:
        lines += ["", "## 声音比对（原稿 → 改稿，形态计数）", ""]
        if voice_diff["changes"]:
            lines += ["| 标记 | 原稿 | 改稿 | 形态 |", "|---|---:|---:|---|"]
            lines += [f"| {c['mark']} | {c['original']} | {c['edited']} | {c['note']} |"
                      for c in voice_diff["changes"]]
            lines += ["", "整体归零不等于更好：确认是删掉冗余口语，还是把作者的声音改掉了。"]
        else:
            lines.append("- 未见显著变化（阈值：归零或变动超过较大者的一半）。")
        lines.append(f"- 状态：{voice_diff['status']}（{voice_diff['scope']}）")
    if ledger_problems:
        lines += ["", "## 台账问题", ""] + [f"- {p}" for p in ledger_problems]
    lines += ["", "## 未验证", "",
                  "- 独立外部读者盲选：未执行（脚本不产生偏好结论）",
                  "- 逐项第二来源事实核真：未执行",
                  "- 真实微信草稿 / 手机端：未执行"]
    return "\n".join(lines) + "\n"
