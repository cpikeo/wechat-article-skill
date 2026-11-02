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


def block_text(kind, value):
    """块的可读文字，用于审计与事实比对；不含标签与图注之外的元信息。"""
    if kind in ("p", "h2", "h3"):
        return value
    if kind in ("lead", "quote"):
        return value[0]
    if kind == "peak":
        return peak_text(value)
    if kind == "note":
        return " ".join(value[1])
    if kind == "list":
        return " ".join(value[1])
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
    """只把有说话/引用归属的引号当直接引语；强调性引号不冒充引语。"""
    out = []
    for m in _QUOTED.finditer(text):
        before = text[max(0, m.start() - 14):m.start()]
        if re.search(r"说|称|问|道|引述|引用|信中|古语|俗语|写道|回答|宣布|表示", before):
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
CLICHE = re.compile(r"随着.{0,12}(?:发展|普及|提升|加快)|在当今(?:社会|时代)|众所周知|不言而喻|众所周知的是")
ABSOLUTE = re.compile(r"所有人|每个人|无一例外|从来如此|永远|绝对|毫无疑问|显然")
EMPH = re.compile(r"==|</?u>|\*\*")


def _add(issues, code, cls, severity, location, problem, action, benefit, evidence,
         preservation="保留原意、事实、语气与限定条件", needs="none"):
    issues.append({
        "code": code, "class": cls, "severity": severity, "location": location,
        "problem": problem, "action": action, "benefit": benefit, "evidence": evidence,
        "preservation": preservation, "needs": needs,
        # V2/V3 消费者兼容：reason 曾是唯一说明字段。
        "reason": evidence,
    })


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
        ordered = max((len(v[1]) for k, v in blocks if k == "list" and v[0]), default=0)
        noun = re.search(r"方法|步骤|原因|问题|建议|误区|原则|技巧|理由|教训", m.group(0) + text[m.end():m.end()+4])
        explicit = [h for h in heads if re.match(r"^(?:第?[一二三四五六七八九十\d]+[、．.：:]?|[（(][一二三四五六七八九十\d]+[）)]|(?:方法|步骤|原因|问题|建议|误区|原则|技巧|理由|教训)[一二三四五六七八九十\d]+)", h)
                    or (noun and noun.group() in h and re.search(r"[一二三四五六七八九十\d]", h))]
        observed = len(explicit) or len(heads) or ordered
        out.append({"kind": "count", "promise": m.group(0), "expected": expected, "observed": observed,
                    "status": "fulfilled" if observed == expected else ("absent" if not observed else "mismatch"),
                    "locations": [f"H2「{h}」" for h in (explicit or heads)] if heads else ([f"有序列表 {ordered} 项"] if ordered else []),
                    "verification": "structural_only"})
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
    if re.search(r"最|唯一|第一|首次|没有之一", text):
        out.append({"kind": "superlative", "promise": "最高级断言", "expected": 1,
                    "observed": 1 if re.search(r"最|唯一|第一|首次", body) else 0,
                    "status": "needs-judgment",
                    "locations": ["标题使用最高级；正文须给出比较范围与依据"]})
    return out


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


def audit(meta, blocks):
    """返回完整审计结果：brief / strategy / claim_map / promise / issues / ledger。"""
    issues, paragraphs, seen = [], [], {}
    title = meta.get("title", "").replace("|", "｜")
    type_key, type_ok = resolve_type(meta.get("article_type", ""))
    strategy = TYPES.get(type_key)

    # --- 形态检查（mechanical） ---
    for index, (kind, value) in enumerate(blocks, 1):
        text = block_text(kind, value)
        if kind in ("p", "h2", "h3"):
            normalized = re.sub(r"\s+", "", plain(value))
            if kind == "p":
                paragraphs.append((index, normalized, value))
            if normalized and normalized in seen:
                _add(issues, "DUP-EXACT", "mechanical", "should", f"块 {index}", "信息完全重复",
                     "合并或删除", "减少重复阅读，不改变论证",
                     f"与块 {seen[normalized]} 的可见文字完全相同")
            seen[normalized] = index
            if kind == "p" and len(normalized) > 260:
                _add(issues, "LONG-PARA", "mechanical", "should", f"块 {index}",
                     "移动端长段掩盖语义转折", "按语义断点拆分", "让论点、证据与限制更容易被扫读",
                     f"该段去标记后为 {len(normalized)} 字；不按字数机械拆分")
            for sentence in re.split(r"(?<=[。！？])", plain(value)):
                if len(re.sub(r"\s", "", sentence)) > 90:
                    _add(issues, "LONG-SENT", "mechanical", "should", f"块 {index}",
                         "单句超过 90 字，移动端容易读丢主语", "在连接词处断句或改列表",
                         "读者能一遍读完一个判断", f"「{sentence.strip()[:24]}…」{len(sentence)} 字")
                    break
            nearby = blocks[max(0, index - 2):min(len(blocks), index + 1)]
            has_source = any(k == "note" for k, _ in nearby) or bool(re.search(r"https?://", text))
            if kind == "p" and re.search(r"\d+(?:\.\d+)?(?:%|％|亿元|万元|万人|倍|年|月|日|小时|美元)", text) and not has_source:
                _add(issues, "NUM-NO-SOURCE", "mechanical", "should", f"块 {index}",
                     "关键数字附近未见可核对依据", "核查数字并就近补口径",
                     "读者可判断时间、口径与结论力度", "相邻块未见来源 note 或 HTTP(S) 链接",
                     "不补写无法确认的来源；必要时限定、删除或标未核", needs="fact-check")
            if kind == "p" and ATTRIB.search(text) and not has_source:
                _add(issues, "ATTR-NO-SOURCE", "mechanical", "should", f"块 {index}",
                     "来源型表述没有就近指向依据", "补原始出处或降级表述",
                     "区分可核事实与作者转述", "出现“数据显示/研究表明/据…”而相邻块无来源", needs="fact-check")
            if kind == "p" and CAUSAL.search(text) and not HEDGE.search(text):
                _add(issues, "CAUSAL-STRONG", "judgment", "should", f"块 {index}",
                     "因果或确定性措辞可能强于可见证据", "核对推断链并补限定",
                     "避免把相关、估算或观点写成确定事实", "出现强因果/绝对措辞，句内未见限制词", needs="editor")
            if kind == "p" and CLICHE.search(text):
                _add(issues, "OPENING-CLICHE", "mechanical", "should", f"块 {index}",
                     "套语开头占据入口，没有给出信息", "删除套语，直接给事实或判断",
                     "首屏留在有效信息上", f"命中套语：{CLICHE.search(text).group(0)}")
            if kind == "p" and ABSOLUTE.search(text) and not HEDGE.search(text):
                _add(issues, "GENERALIZE", "judgment", "should", f"块 {index}",
                     "绝对化措辞可能把局部经验写成普遍规律", "补范围与反例，或改为限定表述",
                     "结论力度与证据范围一致", f"出现“{ABSOLUTE.search(text).group(0)}”且句内无限定",
                     needs="editor")
            if kind == "p" and len(re.findall(r"首先|其次|再次|最后|第一|第二|第三", text)) >= 3 and len(text) > 80:
                _add(issues, "PROSE-LIST", "mechanical", "should", f"块 {index}",
                     "段内并列超过三项，扫读成本高", "改为有序列表并保留原有编号语义",
                     "并列关系一眼可见，顺序不被改写", "同段出现 3 个以上顺序连接词")
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

    marks = sum(len(EMPH.findall(block_text(k, v))) for k, v in blocks if k == "p")
    if marks > max(6, len(paragraphs)):
        _add(issues, "EMPHASIS-OVERUSE", "mechanical", "should", "全文",
             "强调标记密度过高，强调等于没有强调", "只保留改变理解的字句",
             "重点重新变得可辨", f"段落内强调标记 {marks} 处 / 段落 {len(paragraphs)} 个")

    # --- 台账与整体结构 ---
    sections = _section_stats(blocks)
    total = sum(s["chars"] for s in sections)
    if len(sections) >= 2 and total:
        for section in sections:
            share = section["chars"] / total
            if section["chars"] < 45 or share > 0.7:
                _add(issues, "SECTION-SKEW", "mechanical", "should",
                     f"块 {section['block']}（{section['heading']}）", "章节篇幅与其他章节明显失衡",
                     "检查是否缺证据、应并入相邻章或需要拆分", "让章节推进与信息重量一致",
                     f"本章约 {section['chars']} 字，占有标题章节文字 {share:.0%}；比例仅作定位，不自动改稿")

    if blocks and blocks[-1][0] == "p":
        head = " ".join(block_text(k, v) for k, v in blocks[:3])
        tail_facts = [f for f in facts(block_text("p", blocks[-1][1])) if f[0] in ("num", "date")]
        fresh = [f for f in tail_facts if f[1] not in head and f[1] not in " ".join(
            block_text(k, v) for k, v in blocks[:-1])]
        if fresh:
            _add(issues, "CONCLUDE-NEW-EVIDENCE", "judgment", "should", f"块 {len(blocks)}",
                 "结尾出现前文未论证的新数字", "把该证据移到对应章节，或删去", "结尾只收束已论证的内容",
                 f"新出现：{'、'.join(f[1] for f in fresh[:3])}", needs="editor")

    # --- 论证层（judgment）：只定位，不判决 ---
    evidence_kinds = {"note", "table", "data", "bars", "quote", "code"}
    for index, (kind, value) in enumerate(blocks, 1):
        if kind != "p":
            continue
        text = plain(value)
        claim_like = bool(re.search(r"应该|必须|意味着|说明|证明|表明|因此|所以|结论|关键|本质", text))
        window = blocks[max(0, index - 2):min(len(blocks), index + 2)]
        backed = any(k in evidence_kinds for k, _ in window) or bool(re.search(r"https?://|\d{4}", text))
        if claim_like and not backed and len(text) > 40:
            _add(issues, "ORPHAN-CLAIM", "judgment", "should", f"块 {index}",
                 "判断性句子附近没有可见证据", "补证据、降级为推测或改为提问",
                 "读者能区分结论与依据", "相邻两块无来源、表格、引文或代码",
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
        head = blocks[:2]
        if head and head[0][0] not in ("lead", "p", "data", "table"):
            _add(issues, "OPENING-TYPE", "judgment", "should", "首屏",
                 "新闻稿首屏没有先给事实", f"先给：{strategy['opening']}",
                 "读者在首屏拿到可核对的事实", "首个正文块为引文或图片", needs="editor")
    if type_key == "tutorial":
        body = " ".join(block_text(k, b) for k, b in blocks)
        if not re.search(r"版本|前提|要求|需要先|环境|依赖", body):
            _add(issues, "MISSING-PREREQ", "judgment", "should", "全文",
                 "教程未写前提或版本", "补读者进入步骤前必须满足的条件",
                 "失败可归因，读者不会在错误前提下照着做", "全文未见前提/版本表述", needs="editor")
        if not re.search(r"失败|报错|回退|撤销|如果没有|不适用|边界", body):
            _add(issues, "MISSING-FAILURE", "judgment", "should", "全文",
                 "教程只写成功路径", "补失败条件与回退方式",
                 "读者在出问题时能自行判断", "全文未见失败/回退表述", needs="fact-check")

    # --- 标题承诺 ---
    promises = promise_ledger(title, blocks, meta.get("thesis", ""))
    for p in promises:
        if p["kind"] == "count" and p["status"] != "fulfilled" and p["observed"]:
            _add(issues, "PROMISE-COUNT", "mechanical", "must", "标题与全文",
                 "标题的数量承诺与可见结构不一致", "逐项核对标题承诺",
                 "避免点击后发现正文没有兑现标题",
                 f"标题承诺 {p['expected']} 项；可见 {p['observed']} 项")
        if p["kind"] == "count" and p["status"] == "absent":
            _add(issues, "PROMISE-COUNT", "judgment", "must", "标题与全文",
                 "标题承诺的分项在正文没有可定位结构", "补分项标题或收窄标题",
                 "标题与目录能对上", "标题含数量承诺，正文无 H2 或有序列表", needs="editor")
        if p["kind"] == "object" and p["status"] == "absent":
            _add(issues, "PROMISE-OBJECT", "mechanical", "must", "标题与全文",
                 "标题中的明确对象未在正文出现", "补兑现位置或收窄标题",
                 "让标题对象能在正文被定位", f"标题对象“{p['promise']}”未出现在正文")
        if p["kind"] == "question" and p["status"] == "unclear":
            _add(issues, "PROMISE-QUESTION", "judgment", "should", "标题与全文",
                 "问题型标题缺少可定位的回答结构", "标出核心回答与推导步骤",
                 "读者能确认标题问题在何处被回答", "未提供 thesis，且 H2 未见回答性表述；关键词命中也不等于回答成立", needs="editor")
        if p["kind"] == "superlative":
            _add(issues, "PROMISE-SUPERLATIVE", "judgment", "note", "标题",
                 "最高级断言需要比较范围与依据", "写明比较范围、时间与来源",
                 "读者能核对最高级是否成立", "标题含“最/唯一/第一”", needs="fact-check")

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
                            "required": ["标题兑现", "逐节信息增量", "证据到结论的推导", "最强反例", "结论适用范围", "原意与声音保留"]},
        "promise": promises,
        "issues": issues,
        "summary": summary,
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
    if key == "tutorial" and not any(k == "list" and v[0] for k, v in blocks):
        notes.append("动作：把操作序列改为有序列表，顺序本身就是信息。")
    if key == "profile" and not any(k == "quote" for k, _ in blocks):
        notes.append("动作：若有人物原话，用带出处的引文；没有就不要编写。")
    return notes


def render_report(result, facts_diff=None, ledger_problems=None):
    """把审计结果排成可交付的「修改记录 / 验收」文本。"""
    lines = ["# 编辑审计", ""]
    t = result["type"]
    lines.append(f"- 类型：{t['label'] or '未判断'}" + ("" if t["recognized"] else "（未识别，需修正）"))
    s = result["summary"]
    lines.append(f"- 形态问题 {s['mechanical']} 项 · 判断类问题 {s['judgment']} 项 · 必须修 {s['must']} 项")
    lines.append(f"- 缺 brief 字段：{'、'.join(result['missing_brief']) or '无'}")
    if result["promise"]:
        lines += ["", "## 标题承诺", "", "| 类型 | 承诺 | 期望 | 可见 | 状态 |", "|---|---|---:|---:|---|"]
        for p in result["promise"]:
            lines.append(f"| {p['kind']} | {p['promise']} | {p['expected']} | {p['observed']} | {p['status']} |")
    if result["issues"]:
        lines += ["", "## 问题（按严重度）", "", "| 级别 | 类别 | 位置 | 问题 | 动作 | 收益 | 证据 | 需要 |",
                  "|---|---|---|---|---|---|---|---|"]
        for i in result["issues"]:
            lines.append(f"| {i['severity']} | {i['class']} | {i['location']} | {i['problem']} | "
                         f"{i['action']} | {i['benefit']} | {i['evidence']} | {i['needs']} |")
    lines += ["", "## 语义评审工作单（UNVERIFIED，须由编辑逐项填写）", "",
              "| 章节/位置 | 主张候选 | 证据候选 | 推导关系 | 反例与边界 | 信息增量 |",
              "|---|---|---|---|---|---|"]
    for section in result.get("argument_map", []):
        claims = "；".join(x["text"] for x in section["claim_candidates"]) or "未定位，需通读"
        evidence = "；".join(f"块{x['block']} {x['kind']}" for x in section["evidence_candidates"]) or "未定位，不等于不存在"
        bounds = "；".join(x["text"] for x in section["boundary_candidates"]) or "UNVERIFIED"
        lines.append(f"| {section['section']}（块 {section['block']}） | {claims.replace('|', '｜')} | {evidence} | UNVERIFIED | {bounds.replace('|', '｜')} | UNVERIFIED |")
    if facts_diff is not None:
        lines += ["", "## 事实单元比对（机械，不等于核真）", "",
                  f"- 保留 {len(facts_diff['preserved'])} / 原稿 {facts_diff['source_units']}",
                  f"- 删除：{'、'.join(facts_diff['dropped']) or '无'}",
                  f"- 新增：{'、'.join(facts_diff['introduced']) or '无'}",
                  f"- 日期精度变化：{facts_diff.get('precision_changes', [])}",
                  f"- 限定变化：{facts_diff.get('qualifier_changes', [])}",
                  f"- 引语变化：删除 {facts_diff.get('dropped_quotes', [])}；新增 {facts_diff.get('introduced_quotes', [])}",
                  "- 出现次数变化：" + str(facts_diff.get('occurrence_changes', []))]
    if ledger_problems:
        lines += ["", "## 台账问题", ""] + [f"- {p}" for p in ledger_problems]
    lines += ["", "## 未验证", "",
                  "- 独立外部读者盲选：未执行（脚本不产生偏好结论）",
                  "- 逐项第二来源事实核真：未执行",
                  "- 真实微信草稿 / 手机端：未执行"]
    return "\n".join(lines) + "\n"
