#!/usr/bin/env python3
"""Editorial Intelligence：可定位、可复现的编辑审计层。

边界：
- 本模块不做语义判决、不证实外部事实、不自动改写文字。
- 严格区分三类证据：
    * `mechanical`   —— 形态线索（重复、超长、承诺数量/数值缺位、匿名统计无来源等），只是回看原文的地址。
    * `judgment`     —— 编辑/模型判断入口（论证孤立、类型结构缺环、反例缺失、人物越界揣测等），只定位疑点。
    * `verification` —— 外部事实核真、语义兑现、审美与微信真机验收，本层一律标为 `UNVERIFIED`。
- `compare_facts()` 仅做字面事实单元与引语集合比对，不代表事实核真。
- 文本度量（plain / visible_len / doc_len / peak_text / first_screen）及事实图片职责集合由本模块单一持有。
"""
import difflib
import functools
import re
import statistics
from collections import Counter

# ---------------------------------------------------------------- 共享常量与六类策略

# 事实单元的计量词表：`_fact_matches` 的抽取、`render.PROSE_ATOM` 的防断行与
# `render.NUMERIC` 的“这是不是数值格”判定共用这一份，避免三处各写一版后互相漂移。
NUM_UNITS = (
    "个百分点|万亿美元|亿美元|万美元|万亿元|亿元|万元|千亿|百万|兆瓦|千瓦|公里|千米|小时|分钟|"
    "美元|人民币|欧元|日元|GB|MB|TB|KB|ms|cm|mm|kg|%|％|元|倍|年|月|日|天|人|家|件|台|吨|米|秒|万|亿"
)
FACT_ROLES = {
    "解释", "证据", "对比", "结构", "数据",
    "explain", "evidence", "compare", "structure", "data",
}
PROVENANCE_ROLES = {"资料", "实拍", "archival", "photo"}
# 图片职责只有三类：可核事实（须依据）、出处纪实（须来源与授权）、其余表达性职责。
# 三处代码（图注上版、素材门禁、职责统计）共用这一份词表，新增职责不会只改到一半。
ROLES = FACT_ROLES | PROVENANCE_ROLES | {
    "入口", "锚点", "场景", "叙事", "隐喻", "停顿", "收束",
    "entry", "anchor", "context", "narrative", "metaphor", "rhythm", "ending",
}
EVIDENCE_KINDS = {"note", "table", "data", "bars", "quote", "code"}

TYPES = {
    "news": {
        "label": "新闻报道",
        "reader_question": "发生了什么，何时发生，谁确认的，影响与未知边界在哪",
        "opening": "已确认事实 + 时间与归属来源，先于背景与评论",
        "structure": ["已确认事实", "归属与时间线", "影响范围", "尚未确认/未知项"],
        "evidence": "关键事实须定位到明确机构、当事人、日期或原始通报",
        "title_promise": "事件主体 + 变化量；标题不得把推断或单方说法写成既成事实",
        "risks": ["把单方转述写成已确认事实", "在硬新闻末尾夹带情绪化反问或隐喻", "缺未知边界导致因果错觉"],
        "editorial_work": {
            "protect": "消息来源、引述动词、时间精度、已确认与未知边界",
            "prefer": "删情绪化修辞与动机揣测；按已确认事实→各方回应→未确认事项分层",
            "questions": ["每个核心事实由谁确认？", "单方回应是否保留了归属限定？", "读者能否一眼分清事实与未证实归因？"],
        },
        "semantic_review": ["标题兑现与事实归属", "时间线与消息来源", "事实/推断/未知边界", "逐节信息增量", "原意与引语准确"],
    },
    "analysis": {
        "label": "商业与经济分析",
        "reader_question": "判断凭什么成立，比较口径是什么，反例与适用边界在哪",
        "opening": "核心判断 + 所依赖的证据类型与时效口径",
        "structure": ["核心主张", "同口径证据", "作用机制", "反例与边界", "现实含义"],
        "evidence": "数字须带口径、期间与比较基准；相关、机制与因果分层表述",
        "title_promise": "趋势判断 + 必要限定；不把单一变量写成唯一原因",
        "risks": ["跨口径直接比较", "相关性偷换为单因果定律", "结论段只复述主张无边界收束"],
        "editorial_work": {
            "protect": "指标口径、统计期间、比较基准、相关性限定与反例",
            "prefer": "先对齐比较口径；拆开数据观察→机制解释→适用边界；保留反例",
            "questions": ["证据支持相关、机制还是因果？", "比较对象是否同口径同期间？", "最强反例如何收窄结论边界？"],
        },
        "semantic_review": ["标题兑现与比较口径", "证据→机制→推断链", "最强反例与适用边界", "逐节信息增量", "原意与作者声音"],
    },
    "tutorial": {
        "label": "技术教程",
        "reader_question": "适用版本与前提是什么，按什么顺序执行，失败后如何排查回退",
        "opening": "可验证的完成结果 + 环境/版本前提",
        "structure": ["目标结果", "版本与前提", "最小可执行步骤", "输出校验", "异常边界与回退"],
        "evidence": "命令、参数、版本号与预期输出可逐项复现",
        "title_promise": "具体任务 + 关键规则或完成标准；步骤数与正文一致",
        "risks": ["省略环境前提", "步骤耦合无校验输出", "只写成功路径不写异常与边界"],
        "editorial_work": {
            "protect": "版本、前提、命令、参数、执行顺序、预期输出与风险提示",
            "prefer": "先给最小可运行闭环，再展开参数与常见误区；补齐失败表现与回退",
            "questions": ["读者每一步如何确认执行正确？", "参数越界或环境不符时会出现什么？", "命令与代码是否零歧义？"],
        },
        "semantic_review": ["任务与完成标准", "版本前提与执行顺序", "可观察输出校验", "失败边界与回退", "命令参数保真"],
    },
    "profile": {
        "label": "人物故事",
        "reader_question": "此人在具体处境中做了什么选择，凭什么支撑对他的理解",
        "opening": "可核实的具体场景、时间节点或动作，而非抽象褒贬",
        "structure": ["具体切口/时间点", "处境与选择", "细节与有出处的原话", "有据可依的意义"],
        "evidence": "引语、履历节点与场景细节须有可追溯出处；不补写心理独白",
        "title_promise": "人物主体 + 可兑现的具体路径或选择",
        "risks": ["开篇空泛颂扬代替动作", "无出处补写人物内心活动", "用奖项堆砌代替叙事主线"],
        "editorial_work": {
            "protect": "人物原话、时间线、具体动作、公开履历与作者评价之间的边界",
            "prefer": "以动作、转折与公开记录组织叙事；删空洞拔高；绝不编造心理或场景",
            "questions": ["每句评价能否落回具体动作或公开记录？", "心理描写是否有自述或采访依据？", "时间线是否清晰连贯？"],
        },
        "semantic_review": ["时间线与引语出处", "人物选择与关键转折", "事实/评价/心理边界", "逐节叙事推进", "细节克制与作者声音"],
    },
    "opinion": {
        "label": "观点评论",
        "reader_question": "作者主张什么，代价与前提是什么，如何回应最强反驳",
        "opening": "明确主张及其代价或前提，先于抒情铺垫",
        "structure": ["核心主张", "分点理由", "最强反驳", "正面回应", "结论限定"],
        "evidence": "事实前提与价值判断分开；引述对方观点保留原意不造稻草人",
        "title_promise": "核心立场清晰可定位；设问型标题须给出明确回答",
        "risks": ["情绪姿态代替推理论证", "虚构弱反方打稻草人", "无限定词的全称绝对化断言"],
        "editorial_work": {
            "protect": "作者立场、语气节奏、论证对象、价值前提与时代用字",
            "prefer": "厘清立论→转折→驳论层次；保护作者声音，不改写成千篇一律的公文腔",
            "questions": ["反驳的是对方最强理由还是稻草人？", "事实前提与价值判断是否混淆？", "回应反例后结论范围是否恰当？"],
        },
        "semantic_review": ["主张与价值前提", "理由链与最强反例", "回应力度与结论限定", "事实与观点边界", "作者立场与声音保留"],
    },
    "longform": {
        "label": "深度长文",
        "reader_question": "全文主线如何推进，当前处于哪一幕，每节带来什么新推进",
        "opening": "承载全文张力的具体切口或关键悬念",
        "structure": ["具体切口", "分层展开", "关键转折", "主线回收"],
        "evidence": "中段每节须有新场景、新证据或真转折；结尾回收主线不塞新论据",
        "title_promise": "聚焦单一核心张力或主线关系",
        "risks": ["中段原地复述导致失速", "把连续叙事压碎成清单卡片", "结尾突然抛入未展开的新证据"],
        "editorial_work": {
            "protect": "叙事主线、伏笔回收、时间跨度、节奏留白与作者声音",
            "prefer": "按叙事/论证节点调节疏密；合并中段原地踏步段落；保留有意义的回环",
            "questions": ["每节相对上一节推进了什么？", "关键转折在前文是否有铺垫？", "结尾是否自然回收开篇切口？"],
        },
        "semantic_review": ["主线张力与标题兑现", "伏笔、转折与回收", "中段推进与章节增量", "结尾收束无突兀新证", "叙事呼吸与作者声音"],
    },
}

# 每类文章只检验两个真正决定其成立的结构环节：缺了它，读者按类型预期要找的东西就不在。
# 这不是评分表，而是“到正文里回看哪一环”的定位器。
STRUCTURE_RINGS = {
    "news": [("时间与归属", r"(?:19|20)\d{2}|月\d{1,2}日|昨日|今日|本周|日前"),
             ("影响范围", r"影响|波及|涉及|受此|后果|冲击|意味着")],
    "analysis": [("作用机制", r"机制|原因|因为|取决于|传导|路径|逻辑|为何"),
                 ("现实含义", r"意味着|接下来|未来|或将|对.{0,8}而言|影响|结论")],
    "tutorial": [("目标结果", r"完成|得到|实现|你将|最终|效果|可以做到"),
                 ("步骤序列", r"第[一二三四五六七八九十\d]|步骤|首先|然后|接着|最后")],
    "profile": [("具体切口", r"(?:19|20)\d{2}|月\d{1,2}日|那天|当时|第一次|那年"),
                ("有据意义", r"后来|此后|如今|今天|至今|留下|影响|因此")],
    "opinion": [("理由链", r"因为|理由|首先|其一|第一|由于|说到底"),
                ("结论限定", r"前提|边界|并非|未必|在一定|限于|不适用于|至少")],
    "longform": [("关键转折", r"直到|然而|但|转折|突然|几年后|后来"),
                 ("主线回收", r"回到|再次|最初|开头|终究|最终|那条|那个")],
}

# 开篇入口：每类第一段要交付的东西不同，同一段开场白不可能同时满足六类读者任务。
# 第二项是缺环时的具体改写方向，不复用通用话术。
OPENING_SIGNALS = {
    "news": (r"(?:19|20)\d{2}|月\d{1,2}日|昨日|今日|本周|日前|通报|宣布|发布|确认",
             "首段未见事件时间或发布主体", "把“何时发生、谁确认”写进第一句，再交代背景"),
    "analysis": (r"\d|意味着|判断|问题|取决于|不是.{0,12}(?:而是|是)|真正的",
                 "首段停留在背景铺垫，未见判断或数据", "开篇直接给出判断，以及它依赖的证据类型与口径"),
    "tutorial": (r"完成|得到|实现|你将|最终|做到|结果",
                 "首段未说明读者做完会得到什么", "先写可验证的完成结果，再交代环境与版本前提"),
    "profile": (r"(?:19|20)\d{2}|月\d{1,2}日|那天|第一次|当时|他在|她在|她走进|他走进",
                "首段缺少可核实的时间节点或具体动作", "从一个具体场景、时间或动作切入，不用定语定性人物"),
    "opinion": (r"我认为|应当|必须|不能|问题在于|值得|不该|真正的",
                "首段未亮明主张", "把主张连同它的代价或前提放在开头，先于抒情铺垫"),
    "longform": (r"(?:19|20)\d{2}|[““]|那天|当时|\d",
                 "开篇切口不够具体，读者难以进入场景", "用一个具体场景、动作或细节开场，把全文张力立起来"),
}

# 开篇入口与结构环节指向同一件事时只报一次
OPENING_RING = {"news": "时间与归属", "profile": "具体切口", "tutorial": "目标结果"}

TYPE_ALIASES = {
    "新闻": "news", "报道": "news", "新闻报道": "news",
    "分析": "analysis", "商业分析": "analysis", "经济分析": "analysis", "商业与经济分析": "analysis",
    "教程": "tutorial", "技术教程": "tutorial", "操作指南": "tutorial", "实操": "tutorial",
    "指南": "tutorial", "实务说明": "tutorial", "说明书": "tutorial",
    "人物": "profile", "人物故事": "profile", "特稿": "profile", "特写": "profile", "访谈": "profile",
    "评论": "opinion", "观点": "opinion", "观点评论": "opinion", "社论": "opinion", "专栏": "opinion", "时评": "opinion",
    "长文": "longform", "深度长文": "longform", "深度报道": "longform",
}


def resolve_type(value):
    """返回 (key, 是否精确识别)。空值不报错；复合写法取首个可识别主类型并标记需确认。"""
    if not value:
        return "", True
    raw = value.strip()
    low = raw.lower()
    if low in TYPES:
        return low, True
    if raw in TYPE_ALIASES:
        return TYPE_ALIASES[raw], True
    for part in re.split(r"[+/、,，·\s]+", raw):
        part = part.strip()
        if not part:
            continue
        if part.lower() in TYPES:
            return part.lower(), False
        if part in TYPE_ALIASES:
            return TYPE_ALIASES[part], False
    return "", False


# 结构指纹：只在作者没声明类型时使用。判据分两档——形态证据（代码块、有序列表、日期、数值、
# 引语、篇幅）算两票，用词证据（章节词与正文措辞）算一票：后者太容易误中（一个“但”不能证明是评论）。
# 最高分要 ≥3 且比第二高至少多 1 分才采纳；平局宁可返回未知，也不给文章套错一套编辑策略。
TYPE_FINGERPRINTS = {
    "tutorial": (
        (2, lambda s: s["code"] > 0),
        (2, lambda s: s["ordered"] > 0),
        (1, lambda s: bool(re.search(r"步骤|安装|配置|命令|参数|版本|运行|部署", s["heads"]))),
    ),
    "news": (
        (2, lambda s: s["dates"] >= 2),
        (1, lambda s: bool(re.search(r"通报|宣布|发布|回应|声明|证实", s["heads"] + s["body"]))),
        (1, lambda s: bool(re.search(r"昨日|今日|本周|日前|截至", s["body"]))),
    ),
    "analysis": (
        (2, lambda s: s["numbers"] >= 4),
        (2, lambda s: bool(re.search(r"机制|驱动|取决于|传导|口径|基准|边际", s["body"]))),
        (1, lambda s: bool(re.search(r"意味着|影响", s["heads"]))),
    ),
    "profile": (
        (2, lambda s: s["quotes"] >= 2),
        (1, lambda s: bool(re.search(r"他说|她说|回忆|那一年|第一次|当时", s["body"]))),
        (1, lambda s: bool(re.search(r"(?:19|20)\d{2}年|月", s["body"]))),
    ),
    "opinion": (
        (2, lambda s: bool(re.search(r"我认为|应当|必须|不该|问题在于|真正的", s["body"]))),
        (1, lambda s: bool(re.search(r"但|然而|反过来|有人会|不妨|假设", s["body"]))),
        (1, lambda s: s["numbers"] <= 2),
    ),
    "longform": (
        (2, lambda s: s["chars"] >= 3000),
        (2, lambda s: s["h2"] >= 4),
        (1, lambda s: bool(re.search(r"直到|几年后|后来|多年|回到", s["body"]))),
    ),
}


def infer_type(blocks):
    """按结构形态推断主类型；只用于“作者没写 article_type”的场合。"""
    body = " ".join(block_text(k, b) for k, b in blocks)
    signals = {
        "code": sum(1 for k, _ in blocks if k == "code"),
        "ordered": sum(1 for k, v in blocks if k == "list" and v["ordered"]),
        "h2": sum(1 for k, _ in blocks if k == "h2"),
        "dates": len(re.findall(r"(?:19|20)\d{2}年|\d{1,2}月\d{1,2}日", body)),
        "numbers": len(facts(body)),
        "quotes": len(quoted_spans(body)),
        "chars": doc_len(blocks),
        "heads": " ".join(plain(v) for k, v in blocks if k in ("h2", "h3")),
        "body": body,
    }
    scored = {name: sum(weight for weight, test in tests if test(signals))
              for name, tests in TYPE_FINGERPRINTS.items()}
    ranked = sorted(scored.values(), reverse=True) or [0]
    best = ranked[0]
    runner_up = ranked[1] if len(ranked) > 1 else 0
    winners = [name for name, score in scored.items() if score == best]
    decided = best >= 3 and best - runner_up >= 1 and len(winners) == 1
    return (winners[0] if decided else ""), scored


def effective_type(meta, blocks):
    """返回 (type_key, source)；source ∈ declared / ambiguous / inferred / unknown。"""
    key, exact = resolve_type(meta.get("article_type", ""))
    if key:
        return key, ("declared" if exact else "ambiguous")
    key, _ = infer_type(blocks)
    return key, ("inferred" if key else "unknown")


# ---------------------------------------------------------------- 文本度量（单一事实来源）

_INLINE_MARKUP = re.compile(
    r"\[(\[[^\]\n]*\]|[^\]]+)\]\([^)\s]*\)|`([^`]*)`|==([^=]*)==|\*\*([^*]*)\*\*|<u>([^<]*)</u>"
    r"|~~([^~]*)~~|(?<!\*)\*([^*\n]+)\*(?!\*)"
)


@functools.lru_cache(maxsize=8192)
def plain(s):
    """剥离 Markdown 行内标记（含单层方括号链接文本），供目录与字数度量共用。

    同一条正文在一次审计里会被反复度量十几遍（扫描、增量、判断入口、报告），
    纯函数缓存后这一点开销直接归零。
    """
    for _ in range(16):
        changed = _INLINE_MARKUP.sub(lambda m: next(g for g in m.groups() if g is not None), s)
        if changed == s:
            break
        s = changed
    return re.sub(r"\\([\\`*_\[\]()<>~=\-#!.+|:])", r"\1", s).strip()


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
    """提取块内可读文本，供审计、增量与事实比对使用。"""
    if kind in ("p", "h2", "h3"):
        return value
    if kind in ("lead", "quote"):
        return value[0] + (" " + value[1] if value[1] else "")
    if kind == "peak":
        return peak_text(value)
    if kind in ("note", "unknown", "code", "data", "bars"):
        return " ".join(value[1])
    if kind == "list":
        return " ".join(_list_node_text(value))
    if kind == "table":
        return " ".join(c for row in value for c in row)
    if kind == "img":
        return value[0] or ""
    return ""


def doc_len(blocks):
    return sum(visible_len(block_text(k, b)) for k, b in blocks)


def first_screen(meta, blocks):
    """记录首个正文段落前的入口层；weight 数的是“抢注意力的独立单元”。

    刊头（栏目行 + 摘要行 + 导语）是一件事的三个部分，读者读作一个入口，
    不能算成三个重入口；只有正文图与重点句是真正与之并列的独立单元。
    """
    kinds = [b[0] for b in blocks]
    stop = next((i for i, k in enumerate(kinds) if k == "p"), len(kinds))
    layers = [k for k in kinds[:stop] if k in {"lead", "img", "note", "data", "bars", "table", "quote", "peak"}]
    if meta.get("deck"):
        layers.insert(0, "deck")
    if meta.get("kicker"):
        layers.insert(0, "kicker")
    header = any(k in layers for k in ("kicker", "deck", "lead"))
    weight = (1 if header else 0) + sum(1 for k in layers if k in ("img", "peak"))
    return {"layers": layers, "weight": weight}


# ---------------------------------------------------------------- 事实单元与声音比对

_NUM = re.compile(
    r"(?<![\d.])([+\-−]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[+\-−]?\d+(?:\.\d+)?)\s*(" + NUM_UNITS + r")?"
)
_CN_NUM = re.compile(r"[一二三四五六七八九十百千万两零]{1,7}(?:倍|成|万人|亿元|美元|小时)")
_QUOTED = re.compile(r"\u300c([^\u300d]{2,})\u300d|“([^”]{2,})”|\u300e([^\u300f]{2,})\u300f")
_URL = re.compile(r"https?://[^\s<>，；。！？）\"]+")
_DATE = re.compile(
    r"(?:19|20)\d{2}年(?:\d{1,2}月(?:\d{1,2}日)?)?|"
    r"(?:19|20)\d{2}[-–/]\d{1,2}(?:[-–/]\d{1,2})?|"
    r"\d{1,2}月\d{1,2}日"
)
_QUALIFIER = re.compile(r"大约|约|近|超过|超|不足|少于|多于|不到|至少|至多|预计|估算|初步")
_QUALIFIER_AFTER = re.compile(r"^(?:左右|以上|以下|以内|之外|有余)")
_ATTR_BEFORE = re.compile(r"说|称|问|道|引述|引用|信中|古语|俗语|写道|回答|宣布|表示|坦言|回忆")
_ATTR_AFTER = re.compile(r"^[\s，,：:]*(?:[\u4e00-\u9fff]{1,8})?(?:说|称|问|道|表示|宣布|写道|回答|补充|解释|强调|回忆)")


@functools.lru_cache(maxsize=4096)
def _fact_matches(text):
    out, spans = [], []
    normalized = text.replace("，", ",")
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
        norm_date = year + (f"-{int(month):02d}" if month else "") + (f"-{int(day):02d}" if day else "")
        out.append(("date", norm_date, m.start(), m.end()))
    for m in _NUM.finditer(normalized):
        if any(a <= m.start() < b for a, b in spans):
            continue
        value = re.sub(r"\s+", "", m.group()).replace("％", "%").replace("−", "-")
        out.append(("num", value, m.start(), m.end()))
    for m in _CN_NUM.finditer(normalized):
        if not any(a <= m.start() < b for a, b in spans):
            out.append(("num", m.group(), m.start(), m.end()))
    return tuple(out)


@functools.lru_cache(maxsize=4096)
def facts(text):
    return tuple((kind, raw) for kind, raw, _, _ in _fact_matches(text))


def fact_occurrences(blocks):
    rows = []
    for index, (kind, value) in enumerate(blocks, 1):
        text = block_text(kind, value)
        normalized = text.replace("，", ",")
        matches = _fact_matches(text)
        for pos, (fact_kind, raw, start, end) in enumerate(matches):
            previous_end = matches[pos - 1][3] if pos else 0
            clause = re.split(r"[。！？；;，,]", normalized[previous_end:start])[-1]
            qualifiers = list(_QUALIFIER.finditer(clause[-16:]))
            suffix = _QUALIFIER_AFTER.match(normalized[end:])
            qualifier = (qualifiers[-1].group() if qualifiers else "") + (suffix.group() if suffix else "")
            rows.append({"block": index, "kind": fact_kind, "value": raw,
                         "qualifier": qualifier, "context": text[:180]})
    return rows


def quoted_spans(text):
    """提取带说话/引用归属的直接引语（兼容归属动词在引号前或引号后）。"""
    out = []
    for m in _QUOTED.finditer(text):
        before = text[max(0, m.start() - 14):m.start()]
        after = text[m.end():m.end() + 18]
        if _ATTR_BEFORE.search(before) or _ATTR_AFTER.search(after):
            out.append(next(g for g in m.groups() if g))
    return out


def _unquoted_prose(text):
    """剥离引号内文本，避免把引述对象或反方假想语误判为作者本人的断言。"""
    return _QUOTED.sub(" ", text)


def _fact_key(kind, value):
    v = value.replace("％", "%").replace("．", ".").strip()
    v = re.sub(r"(?<=\d)[,，](?=\d{3})", "", v)
    return kind, v


def compare_facts(original_blocks, edited_blocks, original_meta=None, edited_meta=None):
    original_blocks = list(original_blocks)
    edited_blocks = list(edited_blocks)
    if original_meta:
        original_blocks += [("p", original_meta.get(k, "")) for k in ("title", "deck")]
    if edited_meta:
        edited_blocks += [("p", edited_meta.get(k, "")) for k in ("title", "deck")]
    src, dst = {}, {}
    for blk_list, target in ((original_blocks, src), (edited_blocks, dst)):
        for kind, value in blk_list:
            for fact in facts(block_text(kind, value)):
                target.setdefault(_fact_key(*fact), fact[1])
    matched = {k for k in src if k in dst}
    precision = []
    for key in src:
        if key in matched or key[0] != "date" or not key[1].startswith("????-"):
            continue
        candidates = [c for c in dst if c not in matched and c[0] == "date"
                      and not c[1].startswith("????") and c[1][5:] == key[1][5:]]
        if len(candidates) == 1:
            cand = candidates[0]
            matched.update((key, cand))
            precision.append({"original": src[key], "edited": dst[cand],
                              "status": "UNVERIFIED", "reason": "补全年份需回原始来源确认"})
    src_q = {next(g for g in m.groups() if g) for k, b in original_blocks if k != "code" for m in _QUOTED.finditer(block_text(k, b))}
    dst_q = {next(g for g in m.groups() if g) for k, b in edited_blocks if k != "code" for m in _QUOTED.finditer(block_text(k, b))}
    before, after = fact_occurrences(original_blocks), fact_occurrences(edited_blocks)
    counts_before = Counter(_fact_key(x["kind"], x["value"]) for x in before)
    counts_after = Counter(_fact_key(x["kind"], x["value"]) for x in after)
    qualifiers = []
    for key in matched:
        q1 = {x["qualifier"] for x in before if _fact_key(x["kind"], x["value"]) == key and x["qualifier"]}
        q2 = {x["qualifier"] for x in after if _fact_key(x["kind"], x["value"]) == key and x["qualifier"]}
        if q1 != q2:
            qualifiers.append({"value": src[key], "original": sorted(q1), "edited": sorted(q2), "status": "UNVERIFIED"})
    qualifier_counts = []
    for occurrences in (before, after):
        qualifier_counts.append(Counter((_fact_key(x["kind"], x["value"]), x["qualifier"]) for x in occurrences))
    # 只在事实两侧都还在时比限定词：整体消失/新增已由 occurrence_changes 与 dropped/introduced
    # 报过一次，再报一条“1 → 0 次”就是同一件事的第二种说法。
    shared = {k for k in counts_before if counts_after[k]}
    qualifier_occurrence_changes = [
        {"value": src.get(key, dst.get(key)), "qualifier": qualifier,
         "before": qualifier_counts[0][(key, qualifier)], "after": qualifier_counts[1][(key, qualifier)]}
        for key, qualifier in sorted(set(qualifier_counts[0]) | set(qualifier_counts[1]))
        if key in shared
        and qualifier_counts[0][(key, qualifier)] != qualifier_counts[1][(key, qualifier)]
    ]
    original_code = [v for k, v in original_blocks if k == "code"]
    edited_code = [v for k, v in edited_blocks if k == "code"]
    return {
        "code_changes": [] if original_code == edited_code else {"before": original_code, "after": edited_code},
        "qualifier_occurrence_changes": qualifier_occurrence_changes or (
            [{"scope": "qualifier binding/order",
              "before": [list(x) for x in sorted(qualifier_counts[0].elements()) if x[0] in shared],
              "after": [list(x) for x in sorted(qualifier_counts[1].elements()) if x[0] in shared]}]
            if any(qualifier_counts[0][k] != qualifier_counts[1][k]
                   for k in set(qualifier_counts[0]) | set(qualifier_counts[1]) if k[0] in shared) else []),
        "preserved": [src[k] for k in src if k in matched],
        "dropped": sorted(src[k] for k in src if k not in matched),
        "dropped_quotes": sorted(src_q - dst_q),
        "introduced_quotes": sorted(dst_q - src_q),
        "introduced": sorted(dst[k] for k in dst if k not in matched),
        "source_units": len(src),
        "edited_units": len(dst),
        "precision_changes": precision,
        "qualifier_changes": qualifiers,
        "occurrence_changes": [
            {"value": src.get(k, dst.get(k)), "before": counts_before[k], "after": counts_after[k]}
            for k in sorted(set(counts_before) | set(counts_after)) if counts_before[k] != counts_after[k]
        ],
        "verification": "UNVERIFIED",
    }


def describe_change(change):
    """把比对明细写成编辑读得懂的一句话；不把 Python 字典甩进验收输出。"""
    if "original" in change and "edited" in change:
        head = f"{change['value']} " if change.get("value") else ""
        return f"{head}原稿 {change['original']} → 改稿 {change['edited']}"
    if "qualifier" in change:
        qualifier = f"限定词“{change['qualifier']}”" if change["qualifier"] else "无限定词"
        return f"{change.get('value', '')}（{qualifier}）{change['before']} → {change['after']} 次"
    if "scope" in change:
        return f"{change['scope']}：限定词绑定或顺序前后不一致"
    if "before" in change and "after" in change:
        return f"{change.get('value', '')} {change['before']} → {change['after']} 次"
    return str(change)


VOICE_MARKS = {
    "第一人称": re.compile(r"我(?!们)"),
    "我们": re.compile(r"我们"),
    "第二人称": re.compile(r"你(?!们)"),
    "设问": re.compile(r"[？?]"),
    "破折号": re.compile(r"——"),
    "旁白括号": re.compile(r"（[^）]{2,30}）|\([^)]{2,30}\)"),
    "口语标记": re.compile(r"其实|说到底|大概|反正|偏偏|难免|硬是|倒(?:是|也)"),
    "直引": _QUOTED,
}


def _sentence_list(text):
    return [s.strip() for s in re.split(r"(?<=[。！？!?])", text) if s.strip()]


def voice_profile(blocks):
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


def compare_voice(original_blocks, edited_blocks):
    before, after = voice_profile(original_blocks), voice_profile(edited_blocks)
    changes = []
    for name in before["marks"]:
        b, a = before["marks"][name], after["marks"][name]
        if b != a and (b == 0 or a == 0 or abs(a - b) >= max(2, round(b * 0.5))):
            changes.append({
                "mark": name, "original": b, "edited": a, "status": "UNVERIFIED",
                "note": "整体消失" if a == 0 < b else ("新增" if b == 0 < a else "显著减少/增加"),
            })
    original_paras = Counter(plain(v) for k, v in original_blocks if k == "p" and plain(v))
    edited_paras = Counter(plain(v) for k, v in edited_blocks if k == "p" and plain(v))
    retained = sum((original_paras & edited_paras).values())
    total = sum(original_paras.values())
    return {"original": before, "edited": after, "changes": changes,
            "unchanged_paragraphs": retained, "source_paragraphs": total,
            "unchanged_paragraph_ratio": round(retained / total, 4) if total else None,
            "status": "UNVERIFIED", "scope": "逐字段落保留率与形态计数，不是语义声音相似度评分"}


def classify_fact_change(edited_blocks, kind, value):
    """区分事实单元在改稿中的真丢失（lost）、组件搬家（moved）与日期概括（rounded）。"""
    if kind == "num":
        number = re.match(r"\d[\d,]*(?:\.\d+)?", value)
        for block_kind, block in edited_blocks:
            if block_kind not in ("data", "bars"):
                continue
            unit, body = block if isinstance(block, tuple) else ("", block)
            lines = body if isinstance(body, list) else body.splitlines()
            for raw_line in lines:
                cells = [cell.strip() for cell in raw_line.replace("|", "｜").split("｜")]
                # 兼容“数值｜标签”与“标签｜数值”两种常见顺序
                cand_cells = [c for c in cells[:2] if c]
                for c in cand_cells:
                    if value in {c, c + unit, unit + c}:
                        return "moved", f"数值 {value} 现位于 {block_kind} 块，完整值与单位仍可对应"
                    if number and c == number.group(0):
                        suffix = value[number.end():]
                        if not suffix or suffix in f"{unit} {raw_line}":
                            return "moved", f"数值 {value} 现位于 {block_kind} 块，值与单位分栏保留"
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
                return "rounded", f"改稿把 {value} 退到“年月”，日级信息消失"
            if same.search(body):
                return "rounded", f"{value} 的精确日期仍在正文，另有只到月的表述"
    return "lost", ""


def introduced_without_source(edited_blocks, introduced):
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


# ---------------------------------------------------------------- 修改台账校验

LEDGER_HEAD = ("位置", "问题", "动作", "收益", "保留检查")


def split_row(line):
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith(r"\|"):
        line = line[:-1]
    return [c.strip().replace(r"\|", "|") for c in re.split(r"(?<!\\)\|", line)]



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
                problems.append(f"台账第 {i} 行缺少“{col}”")
    return rows, problems


def locate(needle, blocks):
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


# ---------------------------------------------------------------- 规则模式与审计核心

CAUSAL = re.compile(r"证明(?:了)?|必然|一定会|唯一原因|彻底(?:改变|解决)|直接导致|决定了|根本原因")
HEDGE = re.compile(r"可能|或许|相关|之一|在.{0,8}条件|不等于|未必|有待|尚无|推测|估计|不能|不足以|不宜|无法|并非|不是")
ANON_ATTRIB = re.compile(r"数据显示|研究表明|报告显示|据(?:报道|统计|调查|了解)|有(?:专家|学者|人士)|业内(?:人士|普遍)")
NAMED_SOURCE = re.compile(
    r"(?:援引|引述|向[A-Za-z\u4e00-\u9fff]{2,12}(?:称|表示|透露)|"
    r"[A-Za-z\u4e00-\u9fff]{2,14}(?:宣布|发布|通报|披露|公报|财报|年报|发言人|馆藏|公开履历)|"
    r"原文(?:列举|提到|指出)|Object\s*\d+|馆藏(?:第\s*\d+|号))"
)
CLICHE = re.compile(
    r"随着.{0,12}(?:发展|普及|提升|加快|推进|深入|兴起)|在当今(?:社会|时代|这个)|"
    r"众所周知|不言而喻|毋庸置疑|不可否认|不难发现|值得注意的是|"
    r"总而言之|综上所述|总之[，,]|从某种意义上(?:来)?说"
)
ABSOLUTE = re.compile(
    r"所有人|每个人|所有[^。！？]{0,16}都|无一例外|从来如此|永远|绝对|毫无疑问|显然|"
    r"只要我们[^。]{0,24}就(?:一定|必然)|就一定(?:能|可以|会)"
)
META_DISCOURSE = re.compile(
    r"本文将|本文试图|本文分为|本文将分|接下来我们(?:来看|聊聊)|下面我们(?:来)?看|"
    r"让我们(?:一起)?(?:来看|看看|聊聊)|话不多说|如你所见|感兴趣的朋友|"
    r"如前所述|正如前文(?:所说|提到)"
)
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
ABSTRACT = re.compile(
    r"价值|意义|赋能|抓手|闭环|生态|维度|底层逻辑|顶层设计|颗粒度|方法论|"
    r"认知|链路|势能|心智|锚点|破局|范式|组合拳|护城河|壁垒|动能|闭环思维"
)
RESTATE = re.compile(r"换句话说|也就是说|简单来说|简而言之|一言以蔽之|说到底|归根结底|这意味(?:着)?(?:，|,)?\s*$")
INFER_HEAD = re.compile(r"^(?:因此|所以|可见|由此可见|这说明|足以说明|不难看出|自然|于是|从而)")
PROSE_ORDINAL = re.compile(r"(?:^|[。；！？，\s])(首先|其次|再次|然后|最后|第一|第二|第三)[，,、：]?")
HOLLOW_CALL = re.compile(
    r"让我们|一起(?:努力|成长|进步|见证|期待|迎接)|共同(?:努力|成长|进步|创造)|"
    r"相信(?:未来|明天)|未来可期|迎来更(?:好|美好)的|拭目以待|共勉"
)
SUPERLATIVE = re.compile(
    r"最(?!近|终|后|先|初|多(?:\d|[一二三四五六七八九十百千万]))|"
    r"唯一|首次|没有之一|第一(?!部分|篇|章|节|课|步|阶段|季度|页|天|次|印象|人称|时间|顺位|梯队|期|卷|集|回|代)"
)
_HEAD_STOP = {
    "我们", "他们", "你们", "但是", "因为", "所以", "如果", "虽然", "而且",
    "并且", "同时", "对于", "关于", "其中", "然后", "因此", "可是", "不过",
}


# 只有“类型已声明”时这些才配拿到 should：推断出来的类型可能根本不对，
# 由它派生的检查一律降为提示，免得一篇非教程稿被教程标准追着改。
TYPE_SCOPED = {
    "OPENING-TYPE", "UNKNOWN-MISSING", "NEWS-EDITORIALIZE", "ANALYSIS-NO-BASELINE",
    "MISSING-PREREQ", "MISSING-FAILURE", "MISSING-VERIFY", "PROFILE-EVAL-OPENING",
    "PROFILE-MIND-READ", "NO-COUNTER", "STRAWMAN-CUE", "LONGFORM-LIST-COLLAPSE",
    "LONGFORM-MID-SAG", "SECTION-NO-GAIN", "OPENING-ENTRY", "STRUCTURE-GAP",
}


def _add(issues, code, cls, severity, location, problem, action, benefit, evidence,
         needs="none"):
    issues.append({
        "code": code, "class": cls, "severity": severity, "location": location,
        "problem": problem, "action": action, "benefit": benefit, "evidence": evidence,
        "needs": needs,
    })


def structure_coverage(blocks, type_key):
    """六类的结构环节各在哪：先看章节标题，再看正文；只报位置，不判质量。"""
    rings = STRUCTURE_RINGS.get(type_key) or []
    if not rings:
        return []
    heads = " ".join(plain(v) for k, v in blocks if k in ("h2", "h3"))
    body = " ".join(block_text(k, b) for k, b in blocks)
    out = []
    for name, pattern in rings:
        hit = "标题" if re.search(pattern, heads) else ("正文" if re.search(pattern, body) else "")
        out.append({"ring": name, "located": hit, "status": "located" if hit else "missing"})
    return out


def opening_gap(meta, blocks, type_key):
    """开篇入口是否兑现该类型的读者任务；thesis 已写明主张时不再要求首段重复。"""
    signal = OPENING_SIGNALS.get(type_key)
    if not signal:
        return None
    first = next((plain(block_text(k, b)) for k, b in blocks if k in ("lead", "p") and plain(block_text(k, b))), "")
    if not first:
        return None
    pattern, problem, action = signal
    if re.search(pattern, first[:160]):
        return None
    if type_key in ("opinion", "analysis") and meta.get("thesis"):
        return None
    return {"problem": problem, "action": action, "evidence": f"首段“{first[:32]}…”未见该类入口标记"}


def _head_token(clause):
    for size in (2, 1):
        head = clause[:size]
        if len(head) == size and re.fullmatch(r"[\u4e00-\u9fff]+", head):
            return head
    return ""


def _is_number_token(token):
    return bool(re.fullmatch(r"[一二三四五六七八九十百千万零两0-9]{1,2}", token))


def _shingles(text, n=3):
    compact = re.sub(r"[\s，。；：、！？,.;:!?“”\u300c\u300d\u300e\u300f（）()]+", "", text)
    return {compact[i:i + n] for i in range(max(0, len(compact) - n + 1))}


def _jaccard(a, b):
    return (len(a & b) / len(a | b)) if (a and b) else 0.0


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
            elif kind == "code":
                current["chars"] += sum(len(x.strip()) for x in value[1])
            current["kinds"].append(kind)
    if current:
        sections.append(current)
    return sections


def _affirmative_cues(text, pattern):
    """只把肯定陈述当覆盖证据；“未说明版本”不能证明交代了版本。"""
    hits = []
    for sentence in _sentence_list(text):
        for clause in re.split(r"[，,；;]", sentence):
            if re.search(r"未|没有|不曾|省略|不提供|不说明|不交代|缺(?:少|失|乏)|无论|不能确认|故意不", clause):
                continue
            match = pattern.search(clause)
            if match:
                hits.append(match)
    return hits


def _has_doc_provenance(meta, blocks):
    """全文是否具备可核的出处声明：只有带链接或具名机构/通报的来源才算，年份不算出处。"""
    if re.search(r"https?://\S+", meta.get("source", "")):
        return True
    for k, v in blocks:
        if k == "note":
            joined = (v[0] or "") + " " + " ".join(v[1])
            if re.search(r"https?://\S+", joined) or NAMED_SOURCE.search(joined):
                return True
    return False


def promise_ledger(title, blocks, thesis=""):
    """标题承诺 → 正文兑现位置（结构/字面核对，不代替语义评审）。"""
    text = plain(title)
    heads = [plain(v) for k, v in blocks if k == "h2"]
    body = " ".join(block_text(k, b) for k, b in blocks)
    out = []
    words = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    vague = ("国家", "城市", "公司", "人", "行业", "地区", "时代", "年份", "月", "周", "小时",
             "团队", "部门", "作者", "编辑", "读者", "版本", "文件")
    m = re.search(r"([二两三四五六七八九十]|\d{1,2})\s*(个|项|种|步|条|点|问|招|件事)([\u4e00-\u9fff]{0,4})?", text)
    if m and m.group(2) == "个" and m.group(3) and m.group(3).startswith(vague):
        m = None
    if m:
        raw = m.group(1)
        expected = int(raw) if raw.isdigit() else words[raw]
        noun = m.group(3) or ""                                    # “三种工作”→ 工作
        list_nodes = [v for k, v in blocks if k == "list" and v["ordered"]]
        ordered_lists = [len(node["items"]) for node in list_nodes]
        ordered = max(ordered_lists, default=0)
        list_text = " ".join(t for node in list_nodes for t in _list_node_text(node))
        explicit = [
            h for h in heads
            if re.match(r"^(?:第?[一二三四五六七八九十\d]+[、．.：:]?|[（(][一二三四五六七八九十\d]+[）)]|"
                        r"(?:方法|步骤|原因|问题|建议|误区|原则|技巧|理由|教训)[一二三四五六七八九十\d]+)", h)
        ]
        # 数量相等本身不是兑现证据：三节正文恰好等于“三个”只是巧合。只有当分项标题
        # 或列表项能在字面上锚定到标题承诺的那个名词时，才承认它兑现了。
        heads_anchored = bool(noun) and len(noun) >= 2 and noun in " ".join(heads)
        lists_anchored = heads_anchored or (bool(noun) and len(noun) >= 2 and noun in list_text)
        candidates = (
            ([(len(explicit), "explicit")] if explicit else [])
            + ([(len(heads), "heads")] if heads and heads_anchored else [])
            + [(n, "list") for n in sorted(set(ordered_lists)) if n and lists_anchored]
        )
        hit = next((c for c in candidates if c[0] == expected), None)
        observed = hit[0] if hit else (len(explicit) or len(heads) or ordered)
        if hit:
            status = "fulfilled"
        elif not observed:
            status = "absent"
        elif observed == expected:
            status = "needs-judgment"      # 数量对得上，但没有可定位的分项结构
        else:
            status = "mismatch"
        out.append({
            "kind": "count", "promise": m.group(0), "expected": expected, "observed": observed,
            "status": status,
            "locations": ([f"H2“{h}”" for h in (explicit or heads)] if hit and hit[1] != "list"
                          else ([f"有序列表 {hit[0] if hit else ordered} 项"] if (hit or ordered) else [])),
            "verification": "structural_only",
        })
    for value, unit in re.findall(
            r"([+\-−]?\d[\d.,]*)\s*(%|％|个百分点|亿元|万元|亿美元|美元|小时|分钟|万人|人|倍|年|天)", text):
        raw = re.sub(r"\s+", "", value + unit).replace("％", "%").replace("−", "-")
        candidates = {re.sub(r"\s+", "", v) for _, v in facts(body)}
        normalized = {c.replace(",", "").replace("％", "%") for c in candidates}
        variants = {raw, raw[:-1] if raw.endswith("人") else raw}
        present = bool(variants & candidates) or bool({v.replace(",", "") for v in variants} & normalized)
        out.append({
            "kind": "number", "promise": raw, "expected": 1, "observed": 1 if present else 0,
            "status": "fulfilled" if present else "absent",
            "locations": [f"正文出现 {raw}"] if present else [],
            "verification": "literal_only",
        })
    for term in re.findall(r"[《\u300c]([^》\u300d]{2,20})[》\u300d]", text):
        out.append({
            "kind": "object", "promise": term, "expected": 1,
            "observed": body.count(term),
            "status": "fulfilled" if term in body else "absent",
            "locations": [f"出现 {body.count(term)} 次"] if term in body else [],
        })
    if re.search(r"为什么|为何|如何|怎样|能否|是否|真相|原因", text):
        answer = [h for h in heads if re.search(r"因为|原因|机制|如何|答案|所以|取决于|在于|分清|先|再", h)]
        if not answer and thesis:
            answer = ["frontmatter.thesis（语义兑现仍需评审）"]
        out.append({
            "kind": "question", "promise": "标题提出的问题", "expected": 1,
            "observed": len(answer),
            "status": "needs-judgment" if answer else "unclear",
            "verification": "UNVERIFIED", "locations": answer,
        })
    if SUPERLATIVE.search(text):
        out.append({
            "kind": "superlative", "promise": "最高级或首次断言", "expected": 1,
            "observed": 1 if SUPERLATIVE.search(body) else 0,
            "status": "needs-judgment",
            "locations": ["标题使用最高级或首次断言；正文须给出比较范围、时间与依据"],
        })
    return out


def section_gain(blocks):
    sections = _section_stats(blocks)
    seen_facts, seen_text, out = set(), [], []
    for section in sections:
        start = section["block"]
        end = next((x["block"] for x in sections if x["block"] > start), len(blocks) + 1)
        members = blocks[start - 1:end - 1]
        # 不把章节标题本身混入正文相似度；否则换一个标题即可掩盖整段复制。
        body_members = blocks[start:end - 1]
        text = " ".join(block_text(k, v) for k, v in body_members)
        here = {_fact_key(*f) for f in facts(text)}
        here_facts = {_fact_key(kind, value): value for kind, value in facts(text)}
        new_facts = sorted(value for key, value in here_facts.items() if key not in seen_facts)
        quotes = quoted_spans(text)
        similarity = max((_jaccard(_shingles(text), t) for t in seen_text), default=0.0)
        out.append({
            "heading": section["heading"], "block": start, "chars": section["chars"],
            "new_facts": new_facts, "new_fact_count": len(here - seen_facts),
            "quoted": quotes[:3], "similarity_to_previous": round(similarity, 3),
            "image": any(k == "img" for k, _ in members),
            "evidence_blocks": [i for i, (k, _) in enumerate(body_members, start + 1) if k in ("note", "table", "data", "bars", "code")],
            "verdict": "UNVERIFIED",
        })
        seen_facts |= here
        seen_text.append(_shingles(text))
    return out


def decision_chain(meta, blocks, key=None, type_key=""):
    strategy = TYPES.get(type_key)
    kinds = [k for k, _ in blocks]
    fs = first_screen(meta, blocks)
    images = [(b[0], (b[2] or "").strip()) for k, b in blocks if k == "img"]
    roles = [r.split()[0] for _, r in images if r]
    return {
        "theme": key or meta.get("theme", ""),
        "steps": [
            {"step": "内容类型", "declared": meta.get("article_type", "") or "未声明",
             "derived": (strategy or {}).get("label", ""),
             "evidence": "类型策略已解析" if strategy else "类型未识别，策略未生效",
             "status": "OK" if strategy else "MISSING"},
            {"step": "视觉概念", "declared": meta.get("visual_concept", "") or "未声明",
             "derived": "", "evidence": "一句话说明最重要的关系与第一眼焦点",
             "status": "DECLARED" if meta.get("visual_concept") else "MISSING"},
            {"step": "信息关系", "declared": meta.get("information_shape", "") or "未声明",
             "derived": f"{kinds.count('h2')} 节 · 证据块 {sum(k in ('note', 'table', 'data', 'bars', 'code') for k in kinds)} · 图片 {len(images)}",
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
             "evidence": "主题轴取值已校验（见 theme_profile）",
             "status": "DECLARED" if meta.get("design_rationale") else "MISSING"},
        ],
        "fact_role_images": sum(1 for r in roles if r in FACT_ROLES),
        "note": "DECLARED=作者已写；INFERRED=从结构推出；MISSING=缺这一环。三者都不构成审美结论。",
    }


def _scan_blocks(meta, blocks, sections, type_key):
    """单次扫描生成全部形态线索（mechanical）与段落级判断入口（judgment）。"""
    issues, paragraphs, seen = [], [], {}
    first_prose_idx = next((idx for idx, (k, v) in enumerate(blocks) if k == "p" and plain(v).strip()), -1)
    last_prose_idx = max((idx for idx, (k, v) in enumerate(blocks) if k == "p" and plain(v).strip()), default=-1)
    template_hits = {name: [] for name in TEMPLATES}
    meta_hits, restate_blocks = [], []
    speaker_label = re.compile(r"\*\*[A-Z][A-Z0-9]{0,3}[:：]\*\*")
    emphasis_spans = re.compile(r"\*\*[^*]+?\*\*|==[^=]+?==|<u>[^<]+?</u>")
    emphasis_marks = 0

    for idx, (kind, value) in enumerate(blocks):
        block_no = idx + 1
        loc = f"块 {block_no}"
        raw_text = block_text(kind, value)

        if kind in ("h2", "h3"):
            nxt = blocks[idx + 1][0] if idx + 1 < len(blocks) else ""
            if kind == "h2" and not plain(value).strip():
                _add(issues, "SECTION-EMPTY", "mechanical", "must", loc,
                     "空标题", "补写标题或删除", "保证章节结构有效", "标题为空")
            elif nxt in ("h2", "h3") or not nxt:
                _add(issues, "SECTION-EMPTY", "mechanical", "must", loc,
                     "标题之后没有内容", "补写该节内容或删除空标题", "目录与章节不悬空",
                     f"标题“{plain(value)}”后紧接 {nxt or '文末'}")

        if kind not in ("p", "h2", "h3"):
            continue

        clean = plain(value)
        normalized = re.sub(r"\s+", "", clean)
        if normalized and normalized in seen and normalized not in {"点击这里显示解决方案", "点击此处显示解决方案"}:
            _add(issues, "DUP-EXACT", "mechanical", "note", loc,
                 "与前文出现完全相同的文字；练习说明或控件文案可能需要复用",
                 "确认是否承担重复导航/交互职责；仅合并无功能重复",
                 "消除无信息增量的复制段落", f"与块 {seen[normalized]} 可见文字相同")
        if normalized:
            seen[normalized] = block_no

        if kind != "p" or not clean:
            continue

        paragraphs.append((block_no, normalized, value))
        emphasis_marks += len(emphasis_spans.findall(speaker_label.sub("", raw_text)))

        if len(normalized) > 260:
            _add(issues, "LONG-PARA", "mechanical", "note", loc,
                 "段落较长，可能叠加多个语义任务；长度本身不是缺陷",
                 "仅在论点、证据、转折切换处分段", "适应手机端单屏扫读呼吸",
                 f"该段去标记后 {len(normalized)} 字")

        prose_no_url = re.sub(r"https?://\S+", "", clean)
        sentences = _sentence_list(prose_no_url)
        for sentence in sentences:
            slen = len(re.sub(r"\s", "", sentence))
            if slen > 90:
                _add(issues, "LONG-SENT", "mechanical", "note", loc,
                     "单句较长；完整引语、专名序列或技术定义可保留",
                     "先提炼主谓宾主干；仅在拆分能降低理解负担时断句",
                     "手机窄屏三至四行内读完一个判断", f"“{sentence[:24]}…”{slen} 字")
                break

        # 0-based 邻域窗口：[idx-2, idx+2] 共五块，准确覆盖紧邻的表格、数据与来源注
        window = blocks[max(0, idx - 2):min(len(blocks), idx + 3)]
        local_source = (
            any(k in ("note", "table", "data", "bars") for k, _ in window)
            or bool(re.search(r"https?://", raw_text))
            or bool(NAMED_SOURCE.search(raw_text))
        )
        has_anon_attrib = bool(ANON_ATTRIB.search(raw_text))
        if has_anon_attrib and not local_source:
            _add(issues, "ATTR-NO-SOURCE", "mechanical", "should", loc,
                 "匿名或模糊来源表述（“数据显示/业内人士”等）缺少就近可核依据",
                 "补具体机构与时间出处，或降级为有边界的转述",
                 "读者能分辨可核事实与泛泛转述", "出现匿名归属词且邻近无具体来源",
                 needs="fact-check")

        unquoted = _unquoted_prose(clean)
        causal_sentence = next((sentence for sentence in _sentence_list(unquoted)
                                if CAUSAL.search(sentence) and not HEDGE.search(sentence)
                                and not re.search(r"的证明(?:都|被|可|可以|是)", sentence)), "")
        causal_match = CAUSAL.search(causal_sentence)
        if causal_match:
            _add(issues, "CAUSAL-STRONG", "judgment", "should", loc,
                 "作者叙述中出现强因果/必然性措辞（已排除引语及同句限定）",
                 "核对证据是否足以支撑因果方向；仅支持相关或机制时补限定语",
                 "防止把相关关系或单因素放大为绝对因果",
                 f"候选措辞“{causal_match.group(0)}”且同句无限定词", needs="editor")

        cliche_match = CLICHE.search(unquoted)
        if cliche_match:
            # 套语出现在段首是结构问题（占住了入口），出现在段落中段只是文字问题。
            at_entry = block_no == first_prose_idx + 1 or (idx > 0 and blocks[idx - 1][0] in ("h2", "h3"))
            _add(issues, "CLICHE", "mechanical", "should" if at_entry else "note", loc,
                 "套语占据段首，未提供实质信息" if at_entry else "段中出现套语，多为过渡填空",
                 "删去套语，直接亮出事实、场景或判断",
                 "把首屏和段首留给有效信息", f"命中套语：{cliche_match.group(0)}")

        absolute_sentence = next((sentence for sentence in _sentence_list(unquoted)
                                  if ABSOLUTE.search(sentence) and not HEDGE.search(sentence)
                                  and not re.search(r"显然[，,]?\s*(?:这并不|这不是|这并非)", sentence)), "")
        absolute_match = ABSOLUTE.search(absolute_sentence)
        if absolute_match:
            _add(issues, "GENERALIZE", "judgment", "should", loc,
                 "全称或绝对化措辞可能超出证据边界（已排除引号内反方引述）",
                 "核对适用范围与反例；仅在过度泛化时收窄范围",
                 "让断言力度与证据范围匹配", f"出现“{absolute_match.group(0)}”且句内无限定", needs="editor")

        # 文风形态线索（仅针对正文叙述）
        for m in META_DISCOURSE.finditer(unquoted):
            meta_hits.append((block_no, m.group()))
        for name, pattern in TEMPLATES.items():
            if pattern.search(unquoted):
                template_hits[name].append(block_no)
        restate_blocks.extend((block_no, m.group()) for m in RESTATE.finditer(unquoted))

        for a in range(len(sentences)):
            for b in range(a + 1, len(sentences)):
                s1, s2 = sentences[a], sentences[b]
                if len(s1) >= 14 and len(s2) >= 14 and difflib.SequenceMatcher(None, s1, s2, autojunk=False).ratio() >= 0.72:
                    _add(issues, "CIRCULAR", "mechanical", "note", loc,
                         "同段两句字面高度相似；可能是同义反复，也可能是有意对照或定义",
                         "比较后句是否提供新信息；无推进则合并",
                         "消除原地踏步的句内复述", f"“{s1[:18]}…”与“{s2[:18]}…”相似度 ≥0.72", needs="editor")
                    break

        if len(sentences) >= 3:
            heads = [_head_token(s) if len(s) >= 4 else "" for s in sentences]
            run, best, best_token = 1, 1, ""
            for x, y in zip(heads, heads[1:]):
                if x and x not in _HEAD_STOP and not _is_number_token(x) and x == y:
                    run += 1
                    if run > best:
                        best, best_token = run, x
                else:
                    run = 1
            if best >= 3:
                _add(issues, "REPEAT-SUBJECT", "mechanical", "note", loc,
                     "同段连续多句以同一词开头；可能是排比、步骤或时间线",
                     "逐句核对信息增量；仅在句式重复拖慢阅读时合并主语",
                     "兼顾行文连贯与有意排比", f"连续 {best} 句以“{best_token}…”开头", needs="editor")

        lens = [len(s) for s in sentences if s]
        if len(lens) >= 5 and statistics.pstdev(lens) < 3.5:
            _add(issues, "MONOTONE", "mechanical", "note", loc,
                 "连续五句以上句长几乎一致，缺少长短句节奏变化",
                 "把核心结论凝练为短句，铺垫从句适当归并",
                 "用句长疏密帮读者分辨重点", f"{len(lens)} 句长度 {min(lens)}–{max(lens)} 字，标准差 {statistics.pstdev(lens):.1f}", needs="editor")

        abstract_hits = ABSTRACT.findall(unquoted)
        abstract = sorted(set(abstract_hits))
        if ((len(abstract) >= 3 or (len(abstract) >= 2 and len(abstract_hits) >= 4))
                and not re.search(r"\d", raw_text) and not local_source
                and not quoted_spans(raw_text) and len(clean) >= 60):
            _add(issues, "EMPTY-ABSTRACT", "mechanical", "should", loc,
                 "抽象概念词密集且缺少具体人物、数字、动作或出处支撑",
                 "把抽象黑话替换为可核对的对象、动作、数量或案例",
                 "让段落从空转概念落地为有效信息", f"抽象词 {'、'.join(abstract[:4])}；本段无数字/来源/引语", needs="editor")

        for sentence in sentences:
            if len(sentence) >= 45 and "的" in sentence:
                head = sentence[:sentence.rfind("的")]
                if head.count("的") >= 4 and not re.search(r"[，；。、：！？]", head):
                    _add(issues, "LONG-ATTRIB", "mechanical", "note", loc,
                         "长定语连续套叠无停顿，主语被推迟到句末",
                         "拆成短分句，先立主语和核心动作",
                         "降低手机端长句回读成本", f"“{sentence[:22]}…”连续 {head.count('的')} 个“的”无停顿", needs="editor")
                    break

        ordinals = PROSE_ORDINAL.findall(clean)
        if len(ordinals) >= 3 and len(clean) > 60:
            _add(issues, "PROSE-ORDINAL", "mechanical", "note", loc,
                 f"单段内用“{'/'.join(ordinals[:4])}”连续罗列",
                 "判断各项是否为平级并列：适合扫读时转列表，属时间线则保留段落",
                 "让并列结构清晰且不误拆叙事流", f"单段含 {len(ordinals)} 个顺序标记", needs="editor")

        clauses = [c.strip() for c in re.split(r"[，,；;。！？!?、]", clean) if c.strip()]
        c_heads = [_head_token(c) for c in clauses]
        run, best, best_token = 1, 1, ""
        for x, y in zip(c_heads, c_heads[1:]):
            if x and x == y:
                run += 1
                if run > best:
                    best, best_token = run, x
            else:
                run = 1
        if best >= 3 and best_token not in _HEAD_STOP and not _is_number_token(best_token):
            _add(issues, "PARALLEL-HEAD", "mechanical", "note", loc,
                 f"连续 {best} 个分句以“{best_token}”领起",
                 "比较分句信息差异；保留有意排比，删改空洞凑句",
                 "避免机械排比稀释核心意思", f"“{best_token}…”连续 {best} 次", needs="editor")

        hollow = HOLLOW_CALL.findall(unquoted)
        if idx == last_prose_idx and len(hollow) >= 2 and not re.search(r"\d", raw_text) and not local_source and not quoted_spans(raw_text):
            _add(issues, "HOLLOW-CLOSE", "mechanical", "should", loc,
                 "结尾段依赖空泛口号或愿景收束，无具体动作、事实或主线回收",
                 "直接删去口号段，或换成具体下一步/主线余韵",
                 "让文章停在最有力的信息或余味上", f"命中号召词 {'、'.join(sorted(set(hollow))[:4])}", needs="editor")

    for pos, (i, norm, _) in enumerate(paragraphs):
        if len(norm) < 36:
            continue
        for j, other, _ in paragraphs[:pos]:
            if len(other) >= 36 and norm != other and difflib.SequenceMatcher(None, norm, other, autojunk=False).ratio() >= 0.9:
                _add(issues, "DUP-NEAR", "mechanical", "should", f"块 {i}",
                     "两段文字高度近似，可能在重复同一层意思",
                     "核对两段分工；无新增信息则合并或删除后段",
                     "确保每段只推进一次有效信息", f"与块 {j} 序列相似度 ≥0.90")
                break

    if emphasis_marks > max(6, len(paragraphs)):
        _add(issues, "EMPHASIS-OVERUSE", "mechanical", "note", "全文",
             "正文加粗/高亮过密（已排除采访说话人标签），削弱真正重点",
             "删去修饰性加粗，每屏只保留真正改变读者理解的关键句词",
             "恢复强调层级的稀缺性与扫读锚点", f"强调标记 {emphasis_marks} 处 / 正文 {len(paragraphs)} 段")

    for name, where in template_hits.items():
        if len(where) >= 2:
            _add(issues, "TEMPLATE-REPEAT", "mechanical", "note", f"块 {'、'.join(map(str, where[:5]))}",
                 f"句式模板“{name}”在全文出现 {len(where)} 次",
                 "逐处核对语义功能；仅改写无信息增量的惯性套句",
                 "避免AI式排比惯性掩盖真实逻辑关系", f"模板“{name}”命中 {len(where)} 处", needs="editor")
    if meta_hits:
        _add(issues, "META-DISCOURSE", "mechanical", "note", f"块 {'、'.join(str(i) for i, _ in meta_hits[:4])}",
             "正文出现交代写作过程的元话语（“本文将…”等）",
             "删去过程预告，直接给内容本身",
             "首屏与转场直入主题", "命中：" + "、".join(sorted({m for _, m in meta_hits})[:4]), needs="editor")
    if len(restate_blocks) >= 2:
        _add(issues, "RESTATE-MARKER", "mechanical", "note", f"块 {'、'.join(str(i) for i, _ in restate_blocks[:4])}",
             f"“换句话说/也就是说”类重述标记出现 {len(restate_blocks)} 次",
             "若前句本可写清，直接写清前句并删去二次解释",
             "减少原地解释造成的拖沓", "命中：" + "、".join(sorted({w for _, w in restate_blocks})[:4]), needs="editor")

    total = sum(s["chars"] for s in sections)
    if len(sections) >= 2 and total:
        for section in sections:
            share = section["chars"] / total
            heading = section["heading"]
            expected_short = bool(re.search(r"参见|参考(?:资料|文献)?|总结|结论|结语|大功告成|附", heading))
            expected_core = type_key == "tutorial" and bool(re.search(r"示例|练习|实战|项目|游戏|步骤", heading))
            if (section["chars"] < 45 and not expected_short) or (share > 0.7 and not expected_core):
                _add(issues, "SECTION-SKEW", "mechanical", "note",
                     f"块 {section['block']}（{heading}）",
                     "章节体量与其余章节显著失衡；结语/附录或核心实操章可正常保留",
                     "核对该章功能权重，避免单薄凑章或中段臃肿",
                     "保持全篇章节节奏匀称", f"本章约 {section['chars']} 字（占章节文字 {share:.0%}）")

    return issues


def _judgment_issues(meta, blocks, type_key, sections, gains):
    """六类文章的差异化判断入口（全部 judgment：只定位疑点，不冒充语义判决）。"""
    issues = []
    strategy = TYPES.get(type_key)
    full_body = " ".join(block_text(k, b) for k, b in blocks)

    # 1) 可被证伪的断言有没有依据：全文只有这一处判定，形态扫描不再重复告警。
    #    查的是“这一章（或全文出处声明）有没有任何可核依据”，而不是逐段索要脚注。
    section_backed, current = {}, 0
    for kind, value in blocks:
        if kind == "h2":
            current += 1
        section_backed.setdefault(current, False)
        if kind in ("note", "data", "bars", "table", "code") and block_text(kind, value).strip():
            section_backed[current] = True
        elif kind == "quote" and value[1]:  # 无出处的引文不算证据
            section_backed[current] = True
        elif kind == "p" and (re.search(r"https?://", value) or NAMED_SOURCE.search(value)):
            section_backed[current] = True
    doc_backed = _has_doc_provenance(meta, blocks)

    current = 0
    for idx, (kind, value) in enumerate(blocks):
        if kind == "h2":
            current += 1
        if kind != "p":
            continue
        raw_text = block_text(kind, value)
        unquoted = _unquoted_prose(plain(value))
        if len(unquoted) < 16:
            continue
        # 只追问“可被证伪的断言”：带量化的结论，或明确因果。价值判断与推论不是证据问题。
        quantitative = bool(re.search(
            r"\d+(?:\.\d+)?\s*(?:%|％|个百分点|倍|亿元|万元|亿美元|万人|人|家|年|个月|天|小时)", unquoted))
        causal = bool(CAUSAL.search(unquoted))
        if type_key == "tutorial":
            claim_like = bool(re.search(r"版本|兼容|支持(?:的|率|到)|不支持|报告显示|数据显示|研究表明|据统计", unquoted))
            quantitative, causal = quantitative and claim_like, False
        # 纯因果措辞只在长段里才追问：短句多是承接上文的论证转折，不是新断言
        if not quantitative and not (causal and len(unquoted) > 40):
            continue
        # 明确表达边界、例外或反驳限定的句子本身是在收窄主张，不是无据断言
        if re.search(r"例外|不能|不等于|无法|未必|不足以|尚不能|并非唯一", unquoted):
            continue
        window = blocks[max(0, idx - 2):min(len(blocks), idx + 3)]
        backed = (
            any(k in EVIDENCE_KINDS for k, _ in window)
            or bool(re.search(r"https?://", raw_text))  # 年份不是出处，链接与具名来源才是
            or bool(NAMED_SOURCE.search(raw_text))
            or section_backed.get(current, False) or doc_backed
            or (type_key in ("opinion", "longform") and any(quoted_spans(block_text(k, v)) for k, v in window))
        )
        if not backed:
            severity = "note" if type_key in ("opinion", "tutorial", "longform") else "should"
            infer = next((s for s in _sentence_list(unquoted) if INFER_HEAD.search(s)), "")
            _add(issues, "ORPHAN-CLAIM", "judgment", severity, f"块 {idx + 1}",
                 "量化或因果断言在本章内没有找到可核依据",
                 "确认该结论是否需要出处：需要则补同口径来源，属作者推断则写明依据与边界",
                 "防止关键数字与因果结论悬空",
                 (f"推断连接词“{infer[:10]}…”前未见依据" if infer else "本章未见来源、数据、表格、代码或可归属引语"),
                 needs="fact-check")

    # 2) 章节首段复述 thesis
    thesis = re.sub(r"\s+", "", plain(meta.get("thesis", "")))
    if len(thesis) >= 8:
        for section in sections:
            first = next((block_text(k, v) for k, v in blocks[section["block"]:] if k == "p"), "")
            if first and difflib.SequenceMatcher(None, thesis, re.sub(r"\s+", "", plain(first)), autojunk=False).ratio() > 0.62:
                _add(issues, "RESTATE-THESIS", "judgment", "should",
                     f"块 {section['block']}（{section['heading']}）",
                     "章节首句与全文核心主张高度重合，疑似原地复述",
                     "直接进入该节独有的分论据、机制或反例",
                     "确保每节承担独立推进功能", "与 frontmatter.thesis 相似度 > 0.62", needs="editor")

    # 3) 末段突入全新数字/日期（显式声明例外/边界/反例的收尾小节除外）
    last_head = sections[-1]["heading"] if sections else ""
    if blocks and blocks[-1][0] == "p" and not re.search(r"例外|边界|限制|反例|风险", last_head):
        prior_text = " ".join(block_text(k, v) for k, v in blocks[:-1])
        tail_facts = [f for f in facts(block_text("p", blocks[-1][1])) if f[0] in ("num", "date")]
        fresh = [f for f in tail_facts if f[1] not in prior_text]
        if fresh and len(blocks) >= 5:
            _add(issues, "CONCLUDE-NEW-EVIDENCE", "judgment", "note", f"块 {len(blocks)}",
                 "结尾段首次引入前文未出现的数字或日期；可能是时间线延伸，也可能是迟到论据",
                 "核实该事实仅作收束背景，还是本应前移展开的核心证据",
                 "避免结尾突然抛出未论证的新论据",
                 f"首次出现：{'、'.join(f[1] for f in fresh[:3])}", needs="editor")

    # 4) 六类文章差异化深度策略检查
    if type_key == "news":
        if blocks and blocks[0][0] not in ("lead", "p", "data", "table"):
            _add(issues, "OPENING-TYPE", "judgment", "should", "首屏",
                 "新闻稿首屏未直接给出已确认事实与时间归属",
                 f"首屏先交代：{strategy['opening']}",
                 "满足新闻读者第一眼获知核心事实的任务", "首个正文块为引文或非证据图", needs="editor")
        has_unknown = any(k == "unknown" for k, _ in blocks) or bool(re.search(
            r"尚不清楚|尚不能|尚未|未确认|不能确认|无法确认|未知项|未知|未披露|未公开|未回应|"
            r"没有直接(?:回应|确认)|不得而知|待确认|未经证实|缺乏数据", full_body
        ))
        if not has_unknown:
            _add(issues, "UNKNOWN-MISSING", "judgment", "should", "全文",
                 "新闻报道未标出尚未确认/未知的边界，读者易将背景推断当成既成事实",
                 "用 `::: unknown` 或独立段落写明哪一环尚未获当事人/独立信源确认",
                 "严格守住已确认事实与推断之间的新闻边界", "未见 unknown 块或未确认边界表述", needs="editor")
        for idx, (k, v) in enumerate(blocks):
            if k != "p":
                continue
            unq = _unquoted_prose(plain(v))
            emotive = re.search(r"冰火两重天|撕得明明白白|被裁者的寒冬|令人唏嘘|沦为笑柄|无疑是一记耳光|何其讽刺", unq)
            unquoted_q = next((sentence for sentence in _sentence_list(unq)
                               if re.search(r"难道|岂(?:不|非)|这不正是|(?:？|\?)\s*$", sentence)
                               and not NAMED_SOURCE.search(sentence)), "")
            if emotive or unquoted_q:
                _add(issues, "NEWS-EDITORIALIZE", "judgment", "should", f"块 {idx + 1}",
                     "硬新闻段落出现无归属的情绪化隐喻或评论式反问，混淆报道与评论边界",
                     "删去情绪修辞与反问，或明确转入归属清楚的各方观点与未确认事项",
                     "保持新闻文本的克制与可信度",
                     f"命中：{emotive.group(0) if emotive else unquoted_q[:60]}", needs="editor")

    elif type_key == "analysis":
        has_boundary = any(k == "unknown" for k, _ in blocks) or bool(re.search(
            r"尚不清楚|尚未|未确认|不能确认|未知|缺乏数据|不能单独证明|无法单独证明|"
            r"不等于.{0,8}(?:因果|必然)|不能只归因于|不能把.{0,12}写成唯一|适用边界|例外|样本限制|局限|不确定性|预测存在|"
            r"risks? (?:to the outlook )?(?:are|remain)|could exceed|projections?|not observed outcomes",
            full_body,
        ))
        if not has_boundary:
            _add(issues, "UNKNOWN-MISSING", "judgment", "should", "全文",
                 "分析文章缺少适用边界、反例或未知项说明，相关性易被读成普适因果",
                 "补充反例、样本/时效限制或 `::: unknown` 边界说明",
                 "让分析结论具备可检验的边界条件", "全文未见例外、因果限定或未知表述", needs="editor")
        for idx, (k, v) in enumerate(blocks):
            if k != "p":
                continue
            txt = block_text(k, v)
            if re.search(r"(?:增长|下降|提升|缩水|高出|低了)\s*\d+(?:\.\d+)?\s*(?:%|％|倍)", txt):
                win = " ".join(block_text(wk, wv) for wk, wv in blocks[max(0, idx - 1):min(len(blocks), idx + 2)])
                if not _affirmative_cues(win, re.compile(r"同比|环比|相比|较|高于|低于|从.{1,12}到|(?:19|20)\d{2}|口径|基准|期间")):
                    _add(issues, "ANALYSIS-NO-BASELINE", "judgment", "should", f"块 {idx + 1}",
                         "变化幅度或倍数缺少比较基准与统计期间",
                         "补齐比较对象（同比/环比/跨样本基准）与时间窗口",
                         "没有基准的百分比无法构成有效分析证据", "含变化率数值但邻近未见基准/期间词", needs="fact-check")

    elif type_key == "tutorial":
        prerequisite_heading = any(re.search(r"前提|准备|环境要求|适用版本|依赖", plain(v))
                                   for k, v in blocks if k in ("h2", "h3"))
        concrete_prerequisite = _affirmative_cues(full_body, re.compile(
            r"(?:Python|Node|Java|PHP|Ruby|Go|Rust|iOS|Android)\s*v?\d|无第三方依赖|"
            r"需要先|前提是|适用.{0,12}版本|依赖.{0,12}(?:安装|配置)|安装.{0,12}依赖", re.I))
        if not (prerequisite_heading or concrete_prerequisite):
            _add(issues, "MISSING-PREREQ", "judgment", "should", "全文",
                 "教程未交代运行环境、语言版本或前置条件",
                 "在入口处写明适用版本与前置依赖",
                 "避免读者在不同版本环境下照做失败", "全文未见版本/环境/前提说明", needs="editor")
        if not _affirmative_cues(full_body, re.compile(r"失败|报错|异常|Error|Exception|回退|撤销|如果没有|不适用|边界|错误|"
                                                        r"不起作用|无法运行|重置|不要|不会预先|分清|误区|误当|避免|坑", re.I)):
            _add(issues, "MISSING-FAILURE", "judgment", "should", "全文",
                 "教程只覆盖成功路径，缺少常见误区、异常报错或回退说明",
                 "补充至少一处边界条件、报错表现或回退方法",
                 "读者遇到预期外结果时可自行定位修复", "全文未见失败/异常/误区边界表述", needs="fact-check")
        has_code = any(k == "code" for k, _ in blocks)
        verification_prose = " ".join(block_text(k, v) for k, v in blocks if k != "code")
        if has_code and not _affirmative_cues(verification_prose, re.compile(
                r"预期输出|输出(?:为|校验|检查)|返回(?:值|结果)|预期结果|验证命令|检查.{0,20}是否|校验方式|预期看到|打印出")):
            _add(issues, "MISSING-VERIFY", "judgment", "note", "全文",
                 "教程含代码块但未说明可观察的预期输出或校验方式",
                 "在关键步骤后写出预期输出或验证命令",
                 "读者每步都能确认自己执行无误", "含代码块但未定位到输出校验提示", needs="editor")

    elif type_key == "profile":
        first_p = next((plain(v) for k, v in blocks if k == "p" and plain(v)), "")
        praise = re.search(r"伟大的|传奇一|堪称.{0,6}楷模|巨匠|当之无愧|不朽的|一生奉献给", first_p)
        if praise:
            _add(issues, "PROFILE-EVAL-OPENING", "judgment", "should", "首段",
                 "人物稿开篇先行空泛赞誉或定性标签，晚于具体时间、动作与处境",
                 "删去拔高定语，直接从可核实的时间节点、场景或具体选择切入",
                 "让人物形象立在事实与行动上，而非形容词上", f"首段出现“{praise.group(0)}”", needs="editor")
        for idx, (k, v) in enumerate(blocks):
            if k != "p":
                continue
            txt = _unquoted_prose(plain(v))
            if "我" in txt[:12]:
                continue
            mind_sentence = next((sentence for sentence in _sentence_list(txt)
                                  if re.search(r"(?:他|她)(?:心里想|暗自决定|内心深处明白|在那一刻意识到|默默发誓)", sentence)), "")
            mind = re.search(r"(?:他|她)(?:心里想|暗自决定|内心深处明白|在那一刻意识到|默默发誓)", mind_sentence)
            # 后一句“这些心理活动没有日记依据”是缺陷说明，不是前一句的来源。
            if mind and not _affirmative_cues(mind_sentence, re.compile(r"回忆|自述|采访|信中|日记|坦言|说|写道|据.{1,8}记载")):
                _add(issues, "PROFILE-MIND-READ", "judgment", "should", f"块 {idx + 1}",
                     "第三人称人物叙述出现无出处的心理独白，存在虚构内心活动风险",
                     "核对是否有本人自述/书信/采访依据并写明出处；无依据则改写为可见外部动作",
                     "严守非虚构人物写作的事实边界", f"命中“{mind.group(0)}”且邻近无自述/采访归属", needs="fact-check")

    elif type_key == "opinion":
        if not _affirmative_cues(full_body, re.compile(r"不过|但是|然而|反例|相反|也有人(?:认为|指出|担心)|有人说|另一种|诚然|固然")):
            _add(issues, "NO-COUNTER", "judgment", "should", "全文",
                 "评论未处理反方理由、代价或适用边界",
                 "引入最强反驳并正面回应，或明确主张成立的前提条件",
                 "展现经得起反诘的论证力度", "全文未见转折、反驳或局限表述", needs="editor")
        straw = re.search(r"总有人鼓吹|那些盲目.{0,8}的人|居然有人以为.{0,12}就能解决一切", full_body)
        if straw:
            _add(issues, "STRAWMAN-CUE", "judgment", "note", "全文",
                 "反方立场可能被矮化为极端稻草人表述",
                 "将反方观点还原为其最有说服力的合理形态后再回应",
                 "回应最强反例才能真正增强说服力", f"命中“{straw.group(0)}”", needs="editor")

    elif type_key == "longform":
        narrative_blocks = sum(k in ("p", "list", "table", "quote") for k, _ in blocks)
        if narrative_blocks >= 6:
            list_like = sum(1 for k, _ in blocks if k in ("list", "table"))
            if list_like / narrative_blocks >= 0.5:
                _add(issues, "LONGFORM-LIST-COLLAPSE", "judgment", "note", "全文",
                     "深度长文中列表/表格块占比过高，连续叙事有被压成清单的风险",
                     "仅对真正需要扫读比对的信息保留列表，把人物动作与主线推进还给连续段落",
                     "保持深度长文的阅读沉浸感与叙事张力", f"列表/表格占叙事块 {list_like}/{narrative_blocks}（标题不计）", needs="editor")
        if len(gains) >= 3:
            prior_sentences = set()
            first = gains[0]["block"]
            prior_sentences.update(_sentence_list(" ".join(block_text(k, v) for k, v in blocks[first:gains[1]["block"] - 1])))
            for g in gains[1:-1]:
                end = next((x["block"] for x in gains if x["block"] > g["block"]), len(blocks) + 1)
                here = _sentence_list(" ".join(block_text(k, v) for k, v in blocks[g["block"]:end - 1]))
                repeated = next((sentence for sentence in here if len(sentence) >= 20 and sentence in prior_sentences), "")
                prior_sentences.update(here)
                if repeated or (g["chars"] >= 60 and g["similarity_to_previous"] >= 0.35 and g["new_fact_count"] == 0 and not g["quoted"] and not g["image"]):
                    _add(issues, "LONGFORM-MID-SAG", "judgment", "should",
                         f"块 {g['block']}（{g['heading']}）",
                         "长文中段章节与前文高度重叠，未见新事实、新引语或新场景推进",
                         "合并重复铺垫，或补入推动主线转折的具体细节",
                         "防止长文在中段失速", (f"整句重复：{repeated[:40]}" if repeated else f"与前文相似度 {g['similarity_to_previous']:.2f} 且无新事实/引语"), needs="editor")

    # 5) 证据型文体的逐节信息增量检查
    if type_key in ("analysis", "news", "tutorial", "opinion"):
        for g in gains:
            if g["chars"] >= 80 and g["similarity_to_previous"] >= 0.35 and g["new_fact_count"] == 0 and not g["quoted"] and not g["image"]:
                _add(issues, "SECTION-NO-GAIN", "judgment", "should",
                     f"块 {g['block']}（{g['heading']}）",
                     "该节与前文词汇高度重叠，且未引入新事实单元、引语或图像证据",
                     "合并进相邻章节、补充独立证据，或删去冗余小节",
                     "保证每一节都交付新的信息增量",
                     f"与前文相似度 {g['similarity_to_previous']:.2f}；新事实 0", needs="editor")

    # 6) 六类各有自己的开篇任务与结构承诺：同一段开场白不可能同时满足六类读者
    if strategy:
        gap = opening_gap(meta, blocks, type_key)
        if gap:
            _add(issues, "OPENING-ENTRY", "judgment", "should", "首段",
                 gap["problem"], gap["action"],
                 f"满足{strategy['label']}读者第一眼的判断需求", gap["evidence"], needs="editor")
        missing = [r["ring"] for r in structure_coverage(blocks, type_key) if r["status"] == "missing"]
        # 开篇已就同一件事报过一次，结构层不再重复同一环
        if gap:
            missing = [x for x in missing if x != OPENING_RING.get(type_key)]
        if missing:
            _add(issues, "STRUCTURE-GAP", "judgment", "should", "全文",
                 f"本篇结构缺环：{'、'.join(missing)}",
                 f"按{strategy['label']}的推进结构补齐：{' → '.join(strategy['structure'])}",
                 "让读者按类型预期找到该找的东西",
                 f"章节标题与正文均未定位到{'、'.join(missing)}", needs="editor")

    # 7) 重点句的位置：它是一句判断，不是版面的门框。紧贴章节标题时，读者会把它当小标题扫过去。
    for idx, (kind, _value) in enumerate(blocks):
        if kind != "peak":
            continue
        if idx and blocks[idx - 1][0] == "h2":
            _add(issues, "PEAK-AS-HEADING", "judgment", "should", f"块 {idx + 1}",
                 "重点句紧接章节标题，正在替这一节充当小标题",
                 "把它移入该节中段作为论证的收口，或改写为 H3 明确层级",
                 "避免一句判断被读成版面门框，章节与重点因此可以分辨", "上一块为 H2 标题", needs="editor")

    return issues


def _promise_issues(promises):
    issues = []
    for p in promises:
        if p["kind"] == "number" and p["status"] == "absent":
            _add(issues, "PROMISE-NUMBER", "mechanical", "should", "标题与全文",
                 f"标题承诺的具体数值“{p['promise']}”在正文中未见同值出现",
                 "在正文补齐该数值及其口径，或修改标题数值",
                 "确保标题数字承诺可逐字核对", f"标题含 {p['promise']}，正文未匹配")
        elif p["kind"] == "count" and p["status"] != "fulfilled":
            # 数量相等但找不到分项锚点时，脚本没有资格判“未兑现”——只提示人工核对位置。
            graded = p["status"] in ("absent", "mismatch")
            _add(issues, "PROMISE-COUNT", "judgment", "should" if graded else "note", "标题与全文",
                 "标题的数量承诺未在编号标题或有序列表中直接对齐",
                 "通读正文确认分项是否已在段落内兑现；若缺项则补齐或收窄标题",
                 "防止标题夸大条数或读者难以定位分项",
                 f"标题承诺 {p['expected']} 项；结构可见 {p['observed']} 项"
                 + ("，但没有标题或列表能在字面上对应这些分项" if not graded else ""), needs="editor")
        elif p["kind"] == "object" and p["status"] == "absent":
            _add(issues, "PROMISE-OBJECT", "judgment", "should", "标题与全文",
                 "标题点名的专名对象未以原名在正文出现",
                 "确认正文是否改用简称，或补齐对该对象的实质展开",
                 "确保标题核心对象在正文真正兑现", f"未见原名“{p['promise']}”", needs="editor")
        elif p["kind"] == "question" and p["status"] == "unclear":
            _add(issues, "PROMISE-QUESTION", "judgment", "note", "标题与全文",
                 "设问/如何型标题未在章节标题或 thesis 中定位到显式答复标记",
                 "通读确认正文是否已清晰回答标题之问；必要时让关键章节标题直指答案",
                 "让带着问题点进来的读者快速定位答案", "未声明 thesis 且 H2 无明显答复词", needs="editor")
        elif p["kind"] == "superlative":
            _add(issues, "PROMISE-SUPERLATIVE", "judgment", "note", "标题",
                 "标题含最高级或首次断言，需明确限定范围与证据来源",
                 "在导语或首段写明比较范围、时间窗口与信源依据",
                 "防止无边界最高级损害可信度", "标题含最高级/首次语素", needs="fact-check")
    return issues


def _title_issues(title, blocks):
    """标题的移动端可读性：列表页只露出前十几个字，标题必须自己先立住。"""
    issues = []
    text = plain(title).strip()
    if not text:
        return issues
    if len(text) > 24:
        _add(issues, "TITLE-LONG", "judgment", "should", "标题",
             f"标题 {len(text)} 字，公众号列表与转发卡片会截断前半段",
             "把结论性信息压进前 12 字，其余移到副题或导语",
             "让标题在列表页就完成信息交付", f"“{text[:24]}…”共 {len(text)} 字")
    elif len(text) < 6:
        _add(issues, "TITLE-THIN", "judgment", "note", "标题",
             f"标题仅 {len(text)} 字，读者无法据此判断文章内容",
             "补上对象与判断，而不是加形容词",
             "降低点开才发现不对题的损耗", f"“{text}”")
    first = plain(next((block_text(k, b) for k, b in blocks if k in ("lead", "p")), ""))
    if len(text) >= 6 and text in first:
        _add(issues, "TITLE-RESTATED", "mechanical", "note", "标题与首段",
             "标题原句在首段逐字复述，首屏没有新增信息",
             "首段直接推进到具体事实、场景或代价", "把首屏留给标题之外的内容",
             "首段出现与标题相同的完整句子")
    return issues


def audit(meta, blocks):
    """执行完整编辑审计：形态线索、判断入口、标题承诺、逐节增量、作者声音与设计决策链。"""
    title = meta.get("title", "").replace("|", "｜")
    type_key, type_source = effective_type(meta, blocks)
    strategy = TYPES.get(type_key)
    sections = _section_stats(blocks)
    gains = section_gain(blocks)

    issues = _scan_blocks(meta, blocks, sections, type_key)
    issues.extend(_judgment_issues(meta, blocks, type_key, sections, gains))
    if type_source != "declared":
        for issue in issues:
            if issue["code"] in TYPE_SCOPED:
                issue["severity"] = "note"
                issue["evidence"] += "（类型未声明，策略按推断生效，只作提示）"
    promises = promise_ledger(title, blocks, meta.get("thesis", ""))
    issues.extend(_promise_issues(promises))
    issues.extend(_title_issues(title, blocks))

    brief_keys = ("audience", "reading_context", "purpose", "thesis")
    missing = [k for k in brief_keys if not meta.get(k)]
    if type_source == "inferred":
        _add(issues, "TYPE-INFERRED", "judgment", "note", "frontmatter",
             f"未声明 article_type，按结构推断为“{strategy['label']}”",
             "确认类型后写进 frontmatter；推断错了，下面所有策略都会跟着错",
             "让六类编辑策略真的挂载，而不是静默不生效",
             f"结构指纹命中：代码块/有序列表/时间/数值/引语等形态")
    elif not type_source == "declared":
        declared = (meta.get("article_type") or "").strip()
        _add(issues, "TYPE-UNKNOWN", "mechanical", "should", "frontmatter",
             (f"article_type“{declared}”无法精确识别（或为复合类型）" if declared
              else "未声明 article_type，结构指纹也不足以判定主类型"),
             "改为单一已知主类型以精准启用编辑策略" if declared
             else "在 frontmatter 写一个主类型；推断不出来时不替你猜",
             "确保六类差异化编辑策略准确挂载",
             f"可选：{'、'.join(t['label'] for t in TYPES.values())}")

    severity_rank = {"must": 0, "should": 1, "note": 2}
    issues.sort(key=lambda x: (severity_rank[x["severity"]], x["code"], x["location"]))

    argument_map = []
    for section in sections:
        start = section["block"]
        end = next((x["block"] for x in sections if x["block"] > start), len(blocks) + 1)
        members = list(enumerate(blocks[start - 1:end - 1], start))
        argument_map.append({
            "section": section["heading"], "block": start,
            "claim_candidates": [
                {"block": i, "text": plain(v)[:180]} for i, (k, v) in members
                if k == "p" and re.search(r"应该|必须|意味着|说明|证明|表明|因此|所以|关键|本质", block_text(k, v))
            ],
            "evidence_candidates": [
                {"block": i, "kind": k, "text": block_text(k, v)[:180]}
                for i, (k, v) in members if k in EVIDENCE_KINDS
            ],
            "boundary_candidates": [
                {"block": i, "text": block_text(k, v)[:180]} for i, (k, v) in members
                if k in ("p", "note", "quote", "unknown")
                and re.search(r"但|不过|限制|边界|例外|不能|仅|可能|尚未|未知", block_text(k, v))
            ],
            "inference_relation": "UNVERIFIED",
            "title_contribution": "UNVERIFIED",
            "counterexample_response": "UNVERIFIED",
            "information_gain": "UNVERIFIED",
        })

    return {
        "brief": {k: meta.get(k, "") for k in brief_keys},
        "missing_brief": missing,
        "type": {"key": type_key, "label": strategy["label"] if strategy else "",
                 "source": type_source, "strategy": strategy},
        "decision": {k: meta.get(k, "") for k in
                     ("composition", "visual_concept", "information_shape",
                      "asset_strategy", "mobile_risk", "design_rationale")},
        "claim_map": {
            "title": title,
            "thesis": meta.get("thesis", ""),
            "sections": [s["heading"] for s in sections],
            "evidence_blocks": sum(1 for k, _ in blocks if k in EVIDENCE_KINDS),
            "claim_blocks": sum(1 for k, v in blocks if k == "p" and re.search(
                r"应该|必须|意味着|说明|表明|因此|所以", block_text(k, v))),
        },
        "argument_map": argument_map,
        "semantic_review": {
            "status": "UNVERIFIED",
            "questions": strategy["editorial_work"]["questions"] if strategy else [],
            "required": strategy["semantic_review"] if strategy else ["标题兑现", "信息增量", "事实边界", "原意与作者声音"],
        },
        "promise": promises,
        "issues": issues,
        "summary": {
            "mechanical": sum(1 for i in issues if i["class"] == "mechanical"),
            "judgment": sum(1 for i in issues if i["class"] == "judgment"),
            "must": sum(1 for i in issues if i["severity"] == "must"),
        },
        "evidence_classes": {
            "mechanical": "形态命中线索，附命中依据；是否需要修改须回看原文语境",
            "judgment": "编辑/模型判断入口，只定位疑点与所需核查角色，脚本不下结论",
            "verification": "外部事实核真、语义兑现、审美与真机验收一律标为 UNVERIFIED",
        },
        "section_gain": gains,
        "structure_rings": structure_coverage(blocks, type_key),
        "voice": voice_profile(blocks),
        "decision_chain": decision_chain(meta, blocks, type_key=type_key),
        "fact_verification": "not_performed",
        "visual_acceptance": "pending",
        "wechat_acceptance": "not_tested",
    }


def strategy_notes(meta, blocks):
    key, _ = effective_type(meta, blocks)
    if not key:
        return ["先明确文章主类型与读者核心任务；类型决定入口顺序、证据粒度与边界表达。"]
    t = TYPES[key]
    work = t["editorial_work"]
    notes = [
        f"类型：{t['label']}｜读者问题：{t['reader_question']}",
        f"首屏入口：{t['opening']}",
        f"推进结构：{' → '.join(t['structure'])}",
        f"证据标准：{t['evidence']}",
        f"典型风险：{'；'.join(t['risks'])}",
        f"必须保护：{work['protect']}",
        f"编辑重心：{work['prefer']}",
        f"语义复核：{' / '.join(work['questions'])}",
    ]
    heads = [plain(v) for k, v in blocks if k == "h2"]
    if key == "analysis" and heads and not re.search(r"限制|边界|反例|例外|风险", " ".join(heads)):
        notes.append("建议动作：专设“例外与边界”小节，或在结论段显式收窄适用条件。")
    if key == "news" and not any(re.search(r"\d{4}|\d{1,2}月\d{1,2}日", block_text(k, v)) for k, v in blocks[:4]):
        notes.append("建议动作：首屏补齐事件时间与发布/确认机构。")
    if key == "tutorial" and not any((k == "list" and v["ordered"]) or k == "code" for k, v in blocks):
        notes.append("建议动作：用有序步骤或最小可运行代码块承载操作序列。")
    if key == "profile" and not any(k == "quote" for k, _ in blocks):
        notes.append("建议动作：若有可追溯原话可用独立引文呈现；无出处切勿补造引语。")
    return notes


def render_report(result, facts_diff=None, ledger_problems=None, voice_diff=None):
    lines = ["# 编辑审计", ""]
    t = result["type"]
    mark = {"declared": "", "ambiguous": "（复合或未精确识别，请核对）",
            "inferred": "（未声明，按结构推断，请确认）", "unknown": "（未判断）"}[t["source"]]
    lines.append(f"- 类型：{t['label'] or '未判断'}{mark}")
    s = result["summary"]
    lines.append(f"- 形态线索 {s['mechanical']} 项 · 判断入口 {s['judgment']} 项 · 必须修 {s['must']} 项")
    lines.append(f"- 未填 brief 字段：{'、'.join(result['missing_brief']) or '无'}")
    lines.append("- 语义验收项（均 UNVERIFIED）：" + " / ".join(result["semantic_review"]["required"]))
    if result.get("structure_rings"):
        located = " · ".join(f"{r['ring']}→{r['located'] or '未定位'}" for r in result["structure_rings"])
        lines.append(f"- 结构环节（字面定位，不判质量）：{located}")
    if result["promise"]:
        lines += ["", "## 标题承诺", "", "| 类型 | 承诺 | 期望 | 可见 | 状态 |", "|---|---|---:|---:|---|"]
        for p in result["promise"]:
            lines.append(f"| {p['kind']} | {p['promise']} | {p['expected']} | {p['observed']} | {p['status']} |")
    if result["issues"]:
        lines += ["", "## 机器线索（mechanical）", "",
                  "> 仅代表字面/形态命中，须结合原文语义二次判断。", "",
                  "| 级别 | 位置 | 线索 | 建议动作 | 命中依据 |", "|---|---|---|---|---|"]
        mechanical = [i for i in result["issues"] if i["class"] == "mechanical"]
        for i in mechanical:
            lines.append(f"| {i['severity']} | {i['location']} | {i['problem']} | {i['action']} | {i['evidence']} |")
        if not mechanical:
            lines.append("| — | — | 无形态线索 | — | — |")
        lines += ["", "## 编辑判断入口（judgment）", "",
                  "> 脚本仅定位疑点与所需复核角色，结论须由编辑/模型通读后给出。", "",
                  "| 级别 | 位置 | 疑点 | 建议动作 | 预期收益 | 定位依据 | 复核角色 |", "|---|---|---|---|---|---|---|"]
        judgment = [i for i in result["issues"] if i["class"] == "judgment"]
        for i in judgment:
            lines.append(f"| {i['severity']} | {i['location']} | {i['problem']} | {i['action']} | "
                         f"{i['benefit']} | {i['evidence']} | {i['needs']} |")
        if not judgment:
            lines.append("| — | — | 无判断类疑点 | — | — | — | — |")
    lines += ["", "## 语义评审工作单（UNVERIFIED，须由编辑逐项核实）", "",
              "| 章节/位置 | 主张候选 | 证据候选 | 推导关系 | 反例与边界 | 信息增量 |",
              "|---|---|---|---|---|---|"]
    for section in result.get("argument_map", []):
        claims = "；".join(x["text"] for x in section["claim_candidates"]) or "需通读定位"
        evidence = "；".join(f"块{x['block']} {x['kind']}" for x in section["evidence_candidates"]) or "未见显式证据块"
        bounds = "；".join(x["text"] for x in section["boundary_candidates"]) or "UNVERIFIED"
        lines.append(f"| {section['section']}（块 {section['block']}） | {claims.replace('|', '｜')} | "
                     f"{evidence} | UNVERIFIED | {bounds.replace('|', '｜')} | UNVERIFIED |")
    if result.get("section_gain"):
        lines += ["", "## 逐节信息增量（字面可核项，不替代语义增量判断）", "",
                  "| 章节 | 块 | 字数 | 新事实单元 | 与前文相似度 | 证据块 | 引语/图 |",
                  "|---|---:|---:|---|---:|---|---|"]
        for g in result["section_gain"]:
            new_facts = "、".join(g["new_facts"][:3]) or "0"
            lines.append(f"| {g['heading']} | {g['block']} | {g['chars']} | {new_facts} | "
                         f"{g['similarity_to_previous']:.2f} | {len(g['evidence_blocks'])} | "
                         f"{'是' if (g['quoted'] or g['image']) else '否'} |")
    if result.get("voice"):
        v = result["voice"]
        marks = "、".join(f"{k} {cnt}" for k, cnt in v["marks"].items())
        lines += ["", "## 作者声音画像（形态计数）", "",
                  f"- 标记计数：{marks}",
                  f"- 段落 {v['paragraphs']} · 句 {v['sentences']} · 段均 {v['avg_chars_per_paragraph']} 字"]
    if result.get("decision_chain"):
        lines += ["", "## 设计决策链", "", "| 环节 | 已声明 | 结构推导 | 状态 | 说明 |", "|---|---|---|---|---|"]
        for step in result["decision_chain"]["steps"]:
            lines.append(f"| {step['step']} | {step['declared']} | {step['derived']} | {step['status']} | {step['evidence']} |")
        lines.append(f"\n{result['decision_chain']['note']}")
    if facts_diff is not None:
        lines += ["", "## 事实单元字面比对（机械比对，不等于外部核真）", "",
                  f"- 保留 {len(facts_diff['preserved'])} / 原稿 {facts_diff['source_units']}",
                  f"- 消失：{'、'.join(facts_diff['dropped']) or '无'}",
                  f"- 新增：{'、'.join(facts_diff['introduced']) or '无'}",
                  "- 日期精度变化：" + ("；".join(map(describe_change, facts_diff.get("precision_changes", []))) or "无"),
                  "- 限定词变化：" + ("；".join(map(describe_change, facts_diff.get("qualifier_changes", []))) or "无"),
                  f"- 直接引语变化：删 {'、'.join(facts_diff.get('dropped_quotes', [])) or '无'}；"
                  f"增 {'、'.join(facts_diff.get('introduced_quotes', [])) or '无'}",
                  "- 频次变化：" + ("；".join(map(describe_change, facts_diff.get("occurrence_changes", []))) or "无")]
    if voice_diff is not None:
        lines += ["", "## 作者声音比对（原稿 → 改稿）", "",
                  (f"- 逐字段落保留：{voice_diff['unchanged_paragraphs']}/{voice_diff['source_paragraphs']}"
                   f"（{voice_diff['unchanged_paragraph_ratio']:.1%}）；不代表语义声音评分。"
                   if voice_diff["source_paragraphs"] else "- 原稿无正文段落，保留率不适用。")]
        if voice_diff["changes"]:
            lines += ["| 标记 | 原稿 | 改稿 | 变化形态 |", "|---|---:|---:|---|"]
            lines += [f"| {c['mark']} | {c['original']} | {c['edited']} | {c['note']} |" for c in voice_diff["changes"]]
            lines += ["", "提示：标记归零需确认是删去冗余口头禅，还是误抹平了作者声音。"]
        else:
            lines.append("- 未见显著形态偏移。")
    if ledger_problems:
        lines += ["", "## 修改台账问题", ""] + [f"- {p}" for p in ledger_problems]
    lines += ["", "## 未验证事项（UNVERIFIED）", "",
              "- 外部独立信源逐项事实核真：UNVERIFIED",
              "- 标题语义兑现与审美成品质感：UNVERIFIED（需编辑与五宽度截图通读）",
              "- 微信公众号 API 草稿回读与真机客户端渲染：UNVERIFIED"]
    return "\n".join(lines) + "\n"
