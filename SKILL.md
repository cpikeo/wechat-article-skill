---
name: wechat-article
description: 把 Markdown/Word/纯文本做成可直接粘贴进公众号编辑器的编辑设计水准 HTML，并做视觉导演与资产选择（Visual Thesis / 封面 / 配图 / CSS 图示 / 该留哪张）。判断驱动：先写 Decision，再决定视觉资产值不值得存在，再 Compose，一次渲染出正文 HTML + 390px 预览 + Gate 1/2 + Gate 3 证据。可选官方 API 建草稿/发布。触发：公众号排版/微信排版/gzh/一键排版/自动发布/新主题/封面/配图/这张图要不要留。不用于普通网页/落地页/PPT。
---

# WeChat Article · Editorial Intelligence

把一篇文章变成值得读完、值得记住的公众号成品。
代码是执行器，主题是材料，图片是工具。**判断是最高层。**

宪法只有一句：**每个元素都必须有职责；说不出职责的，删。**

## 流水线

```
UNDERSTAND → JUDGE → EDIT → DIRECT → VISUALIZE → SELECT → COMPOSE → RENDER → VERIFY → REFINE
```

| 步 | 做什么 |
|---|---|
| 1 UNDERSTAND | 只读一次原文：谁在读、为什么读、读完记住哪一句 |
| 2 JUDGE | 写 Decision：主张、层级、节奏、人格、视觉、复核（含 REVIEW 预登记） |
| 3 EDIT | 按 Decision 改文字（不改事实）：先删，再合并，最后才顺句子 |
| 4 DIRECT | 先定语法再谈素材：Thesis / Grammar / Weight / Budget / Slots / Cover |
| 5 VISUALIZE | 取资产：现有素材 → CSS 图示 → 生成 → 无图 |
| 6 SELECT | 逐张过：留下 / 重做 / 删除，并写明「为什么是这张」 |
| 7 COMPOSE | 输出 Composed Markdown（全流程唯一的可交付源） |
| 8 RENDER | `python3 scripts/render.py 文章.md` → HTML + 390px 预览（模拟原生标题/作者栏）+ 发布字段 `*.meta.json` + Gate 1/2 + Gate 3 证据 |
| 9 VERIFY | 对照证据通读 390px 预览，Gate 3 五层，只写 KEEP / REVISE / DELETE |
| 10 REFINE | 只改 Markdown；只有出现「必须改」或 Gate 3 判 REVISE 才允许第二次渲染 |

默认全自动。交付：Decision + 三关结论 + 用户待办（署名 / 补素材 / 粘贴）。

## 只加载需要的知识

| 何时 | 读什么 |
|---|---|
| 每次 | 本文件：宪法 + 决策系统 |
| JUDGE / EDIT | `references/decide.md` |
| DIRECT / VISUALIZE / SELECT | `references/direction.md` |
| Gate 1 FAIL、手改 HTML | `references/platform.md` |
| 发布 / 草稿 / 凭证 | `references/publish.md` |
| 回归 | `python3 scripts/selftest.py`，用例在 `eval/` |
| 不要读 | `scripts/*`（执行器）、`AUDIT.md`（历史审计） |

脚本不是设计规则来源；脚本只执行**可确定**的那部分判断，并把 Gate 3 要用的证据摆出来。

## Decision（导演 brief，不是 JSON；不确定就写「未知，按默认」，不编造）

五行一组。**每个字段都必须有落点**，写不出落点的字段，删掉。

```
READ     Audience · Purpose · Core Claim · Hierarchy · Elements To Remove
EDIT     Tone（→ theme） · Density · Rhythm · Composition · Mobile
TYPE     Typography（标题断行 · 强调预算 · 衬线位置 · 字号层级不新增）
VISUAL   Thesis · Grammar · Visual Anchor · Image Role · Budget · Cover
REVIEW   保留 · 弱化 · 删除 · 最大视觉风险 · 最终验证重点
```

**落点**（这就是「可执行」的意思）：Core Claim → `::: peak`；Tone → `theme`；
Density · Typography → `density`、标题 `\|` 断行、`==` 预算；Hierarchy · Elements To Remove → Compose 里真实发生的删减；
Rhythm · Composition · Mobile → 首屏层数、停顿位置、视觉重量、封面裁切与 390px；
Visual Anchor · Image Role · Budget → `![说明](路径 "职责")` 的位置与预算；Thesis · Grammar · Cover → Gate 3 VISUAL 逐条对。

REVIEW 是**先承诺**：这篇最大的视觉风险是什么、最后必须查哪一条。
Gate 3 通读后再落结论：**KEEP / REVISE / DELETE** + **Which element should disappear?**

## 视觉判断（核心）

**Visual Thesis**：先回答「这篇文章看起来像什么」，再决定任何一张图。
一句话 + 四项：气质 / 视觉隐喻（只选一个） / 视觉重量 / 克制点（这篇不允许出现什么）。
自检：这句话能不能同时否掉三张不该出现的图？（校准例句与三种气质见 `direction.md`）

**Visual Grammar**：全篇一套光源 · 材质 · 色盘 · 镜头 · 画幅 · 裁切 · 图形语言。
不得混搭摄影 + 3D + 卡通 + 赛博。判据：并排放在一起，像不像**同一位 Art Director 在同一次创作里**完成；不一致就重做或删掉后来那张。

**Visual Weight**：视觉重量服从信息权重，允许全文只强调一处——不是让页面看起来丰富，而是让信息拥有正确的重量。

**Visual Role**：不先问「要不要图」，先问「这个位置需要什么职能」。
职责：`Anchor` 入口 · `Explain` 解释 · `Evidence` 证据 · `Compare` 差异 · `Structure` 关系 · `Context` 场景 · `Metaphor` 隐喻 · `Rhythm` 停顿 · `Data` 数量 · `Cover` 封面（可写中文）。
一张图一个主职责（最多一个辅助）；说不出唯一职责 → 删。

**Information Gain**：图给的信息必须多于文字已经给的信息（五问见 `direction.md`）。
Text ≈ Image → 删。**CSS / 表格 / `::: bars` 说得更准 → 不用图。**

**取资产顺序**：现有素材（且真的好） > CSS 图示（关系、数量、流程） > 生成（场景、材质、尺度、情绪） > 无图。
**图示 > 插画；证据 > 装饰；意义 > 丰富度。** 禁止为留白 / 高级感 / 丰富度配图，禁止按篇幅平均分配。

**Image Budget**：先定预算上限，再取素材。≤800 字 0–1 张；800–2000 字 1–3 张；2000 字以上 2–4 张。
`todo` 图位同样占预算；封面单列且必须有。超预算的候选直接删，不降级成装饰；同一职责最多两次。

**SELECT（生成之后、进入文章之前）**：候选资产一律 **留下 / 重做 / 删除**（三问见 `direction.md`）。
留下的每张写一句 **「为什么是这张」**，写不出 → 删。**优先删，而不是重生成。**

**事实安全**：视觉不得制造事实（不存在的人 / 地点 / 数据 / 事件、错误品牌）；生成图用于事实性内容必须标注「示意」，宁可留 `todo`。

**连续性**：多条生成描述**逐字照抄**同一套光源 / 材质 / 色盘 / 镜头——一致性不靠「请保持一致」祈求。

**封面 = 独立 art direction**：Core Claim → 概念 → 隐喻 → 构图 → 裁切 → 390px 缩略。
封面讲的是**文章的主张**，不是「这是一篇关于 AI / 商业 / 科技的文章」。
2.35:1，主体落在中央安全区（微信会再裁成 1:1），默认不放文字；在 390px 缩略下必须依然成立。

**节奏**：图、标题、留白、分隔线都是节奏乐器——按 Rhythm 分配，不按篇幅均摊。长段之后给停顿，高潮前留空，高潮后立刻回到正文。

## Compose = 视觉层级词汇

`Core Claim > Section Claim > Evidence > Explanation > Metadata > Decoration`；能用纯文字就不用原语。
**每个原语属于一个层级；层级越靠后，允许出现的次数越少。**

| 层级 | 写法 | 职责 |
|---|---|---|
| Core Claim | `::: peak` | 全文唯一高潮；渲染器保证只有一个 |
| Section Claim | `## / ###` | 章节主张；标题后必须接正文 |
| Evidence | `![说明](路径 "职责")` · `::: data` · `::: bars` · `表格` · `代码` | 证据、数量、关系；数字交给图示，正文不重复写 |
| Explanation | 正文 · `- 列表` · `> 引文` | 解释与展开；`> 开头` = 首屏钩子，没有就不写 |
| Metadata | `kicker` · `date` · `::: note 标签` · `toc` · `bio` · `cta` | 元信息；不抢正文。title/author/发布日期都走原生字段，正文不重印；masthead 单行左右布局：左 kicker 右阅读时长 |
| Decoration | —— | **空。说不出职责的元素不允许存在** |

行内与节奏：`==关键判断==`（全篇 ≤3）· `**弱强调**`（少用）· `---` 转场（少于 H2 数）。

frontmatter 是 Decision 的落点，不是调参面板；没写＝用默认。

```yaml
---
title: 主标题|断行后半    # | 是断行标记：原生标题栏自动转｜；正文不重印标题
kicker: LETTER
theme: letter            # paper / letter / ink / frost / bone / folio
density: airy            # dense / standard / airy
deck: 一句副题           # 可选；与 lead 不要叠两个钩子
date: 2026年10月8日      # 原生元信息行自带发布时间；正文不重印，仅预览模拟
toc: true                # ≥3 个 H2 才生效，且长文才用
author: 甲木             # 平台原生作者栏；正文不重印（草稿里出现两次是事故）
bio: 一句话简介          # 文末收束区只保留 bio + cta
cta: 结尾一句话
cover: images/cover.jpg  # 独立 art direction；写 todo = 待补
source: https://…        # 可选；原文链接 → 草稿底部「阅读原文」
---
```


## QA

- **Gate 1 Platform**（脚本）：微信 HTML 硬约束。FAIL 不交付。
- **Gate 2 Composition**（脚本）：结构、原语密度、首屏、图片职责与预算、文件存在性、分辨率、封面裁切、图示与正文是否重复。
  「必须改」修完；「建议改」逐条给出改或保留的理由。
- **Gate 3 Art Direction**（对照渲染输出的证据，通读 390px 预览）：
  - CONTENT：主张是否清楚、事实是否可靠（含图片有没有制造事实）
  - EDITORIAL：删减是否有效、层级是否成立、节奏是否自然
  - VISUAL：Thesis 是否成立、Grammar 是否统一、每张图是否真有信息增量、封面是否表达主张、有没有「漂亮但无意义」的视觉
  - MOBILE：390px 下信息是否清楚、主体是否被裁、视觉重量是否失衡、是否产生滚动疲劳、留白是否真正服务阅读
  - FINAL JUDGMENT：只写 **KEEP / REVISE / DELETE**，强制回答 **Which element should disappear?**，并对每张留下的资产给出「为什么是这张」
  不打总分。分数只能服务回归，不替代 Art Direction。

## 硬规则

1. 不手写 HTML，不改渲染器输出——要改就改 Composed Markdown。
2. 不编造引言、数据、出处、图片说明。
3. 图片本地化；说不出职责的删除；生成图标注示意。
4. 为「看起来丰富」加的元素，全部进 Cut。
5. Gate 1/2 有「必须改」就不交付。

---

**Understand before Create. Judge before Compose. Meaning before Decoration.**
**Select before Generate more. Delete before Add. Quality before Feature Count.**
**Less System. More Judgment.**
