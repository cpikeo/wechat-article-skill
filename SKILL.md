---
name: wechat-article
description: 把 Markdown/Word/纯文本做成可直接粘贴进公众号编辑器的编辑设计水准 HTML，并做视觉导演与资产选择（Visual Thesis / 封面 / 配图 / CSS 图示 / 该留哪张）。判断驱动：先写 Decision，再决定视觉资产值不值得存在，再 Compose，一次渲染出正文 HTML + 390px 预览 + Gate 1/2 + Gate 3 证据。可选官方 API 建草稿/发布。触发：公众号排版/微信排版/gzh/一键排版/自动发布/新主题/封面/配图/这张图要不要留。不用于普通网页/落地页/PPT。
---

# WeChat Article · Editorial Intelligence

把一篇文章变成值得读完、值得记住的公众号成品。
代码是执行器，主题是材料，图片是工具。**判断是最高层。**
宪法只有一句：**每个元素都必须有职责；说不出职责的，删。**

## 流水线

`UNDERSTAND → JUDGE → EDIT → DIRECT → VISUALIZE → SELECT → COMPOSE → RENDER → VERIFY → REFINE`

| 步 | 做什么 |
|---|---|
| UNDERSTAND | 只读一次原文：谁在读、为什么读、读完记住哪一句 |
| JUDGE | 写 Decision（见下） |
| EDIT | 按 Decision 改文字（不改事实）：先删，再合并，最后顺句子。**原稿已经成立就不改** |
| DIRECT / VISUALIZE / SELECT | 先定语法再取资产：现有素材 > CSS 图示 > 生成 > 无图；逐张 留下/重做/删除 |
| COMPOSE | 输出 Composed Markdown（全流程唯一可交付源） |
| RENDER | `python3 scripts/render.py 文章.md` → 正文 HTML + 390px 预览（模拟原生标题/作者栏 · 封面两种裁切 · 正文资产表）+ `*.meta.json` + Gate 1/2 + Gate 3 证据 |
| VERIFY / REFINE | 对照证据通读预览，Gate 3 只写 KEEP/REVISE/DELETE；只改 Markdown；「必须改」或 REVISE 才允许二次渲染 |

默认全自动。交付：Decision + 三关结论 + 用户待办（署名 / 补素材 / 粘贴）。

## 只加载需要的知识

| 何时 | 读什么 |
|---|---|
| 每次 | 本文件 |
| JUDGE / EDIT | `references/decide.md`（判断与人格） |
| 要图景时（有图 / 要做封面 / 要写生成描述 / 要筛资产） | `references/direction.md`（视觉） |
| Gate 1 FAIL、手改 HTML | `references/platform.md` |
| 发布 / 草稿 / 凭证 / 素材 | `references/publish.md`（凭证与默认字段来自 `config.json`） |
| 回归 | `python3 scripts/selftest.py` |
| `eval/` 语料 | 只由回归脚本读取，**不加载进 Context** |

全文无图、且封面已由用户给定（不是 `todo`）时**不读 `direction.md`**——它是本文件之外最大的一块 Context，只在真的要做视觉决定时才付。
同一任务内 references 读一次即可，不重复加载。
脚本不是设计规则来源；只执行**可确定**的那部分判断，并把 Gate 3 要用的证据摆出来。

## Decision（导演 brief，不是 JSON；不确定写「未知，按默认」，不编造）

五行一组。**每个字段都必须有落点**，写不出落点的字段，删。

```
READ     Audience · Purpose · Core Claim · Hierarchy · Elements To Remove
EDIT     Tone（→ theme） · Density · Rhythm · Composition · Mobile
TYPE     Typography（标题断行 · 强调预算 · 衬线位置 · 字号 6 级不新增）
VISUAL   Thesis · Grammar · Visual Anchor · Image Role · Budget · Cover
REVIEW   保留 · 弱化 · 删除 · 最大视觉风险 · 最终验证重点
```

落点：Core Claim→`::: peak`；Tone→`theme`；Density/Typography→`density`、`|` 断行、`==` 预算；
Hierarchy/Remove→Compose 里真实发生的删减；Rhythm/Composition/Mobile→首屏层数、停顿、视觉重量、封面裁切与 390px；
Anchor/Role/Budget→`![说明](路径 "职责")` 位置与预算；Thesis/Grammar/Cover→Gate 3 VISUAL 逐条对。
REVIEW 是先承诺；通读后落 KEEP/REVISE/DELETE + **Which element should disappear?**

## 视觉判断（核心）

- **Thesis**：先答「这篇看起来像什么」。一句 + 气质 / 隐喻（只选一个）/ 重量 / 克制点；自检能否同时否掉三张不该出现的图（校准见 `direction.md`）。
- **Grammar**：全篇一套光源·材质·色盘·镜头·画幅·裁切·图形语言；并排像同一位 AD 的同一次创作，不一致就重做或删后来那张。
- **Weight**：视觉重量服从信息权重；允许全文只强调一处。
- **Role**：先问职能再问要不要图：锚点/解释/证据/对比/结构/场景/隐喻/停顿/数据/封面；一图一主职责，说不出 → 删。
- **Information Gain**：图给的信息必须多于正文；Text ≈ Image → 删；CSS/表格/`::: bars` 更准 → 不用图。
- **Budget**：≤800 字 0–1 张；800–2000 1–3 张；2000+ 2–4 张；`todo` 占预算；封面单列且必须有；同一职责最多两次。
- **SELECT**：留下/重做/删除；留下的写一句「为什么是这张」；优先删，而不是重生成。
- **事实安全**：视觉不得制造事实；事实性生成图标注「示意」，宁可留 `todo`。
- **封面**：独立 art direction，讲主张不讲话题；2.35:1，主体在中央安全区（1:1 裁切仍成立），默认不放文字。
- **节奏**：按 Rhythm 分配，不按篇幅均摊；长段后停顿，高潮前留空。

## Compose = 视觉层级词汇

Core Claim > Section Claim > Evidence > Explanation > Metadata > Decoration；能用纯文字就不用原语；层级越靠后允许出现越少。

| 层级 | 写法 | 职责 |
|---|---|---|
| Core Claim | `::: peak` | 全文唯一高潮 |
| Section Claim | `## / ###` | 章节主张；标题后必须接正文 |
| Evidence | `![说明](路径 "职责")` · `::: data` · `::: bars` · 表格 · 代码 | 数字交给图示，正文不重复 |
| Explanation | 正文 · `- 列表` · `> 引文` | `> 开头` = 首屏钩子 |
| Metadata | `date` · `::: note` · `toc` · `bio` · `cta` | title/author/发布日期走原生字段，正文不重印 |
| Decoration | —— | 空 |

行内与节奏：`==` ≤3 · `**` 少用 · `---` 少于 H2 数。frontmatter 是 Decision 落点，不是调参面板；没写＝默认。

```yaml
---
title: 主标题|断行后半    # | 是断行标记：原生标题栏自动转｜；正文不重印标题
theme: letter            # paper / letter / ink / frost / bone / folio
density: airy            # dense / standard / airy
deck: 一句副题           # 可选；与 lead 不要叠两个钩子
date: 2026年10月8日      # 原生元信息行自带发布时间；正文不重印，仅预览模拟
toc: true                # ≥3 个 H2 才生效，长文才用；渲染时排在第一段之后（首屏先给钩子）
author: 甲木             # 平台原生作者栏；正文不重印
bio: 一句话简介          # 文末刊尾落款
cta: 结尾一句话          # 文末刊尾细线框内
cover: images/cover.jpg  # 独立 art direction；写 todo = 待补
source: https://…        # 可选；原文链接 → 草稿底部「阅读原文」
---
```

## QA

- **Gate 1 Platform**（脚本）：微信 HTML 硬约束。FAIL 不交付。
- **Gate 2 Composition**（脚本）：只拦**缺陷**——坏了的、无法核对的、违反本文件已写明规则的（图不存在 / 无职责 / 分辨率 / 预算、bars 非法、封面缺失、字段超上限……）。「必须改」修完；「建议改」逐条给理由。
- **Gate 3 Art Direction**：对照证据通读 390px 预览（含资产表）——CONTENT / EDITORIAL / VISUAL / MOBILE / FINAL JUDGMENT；只写 KEEP/REVISE/DELETE，强制回答 **Which element should disappear?** 与每张图的「为什么是这张」。不打分。
- **发布前**：`python3 scripts/publish.py --html … --meta … --preflight`（不联网）把将要上行的字段 / 封面 / 待传图片摆出来对一遍，再真发。

**机器只验可确定的缺陷。** 密度、节奏、强调多少、裁切好不好看是判断，一律交给 Gate 3 通读——不写成阈值。
**「建议改」不是待办清单**：先问「改了读者多得到什么」，答不出 → 不改，并在交付里写明为什么不改。

## 硬规则

1. 不手写 HTML，不改渲染器输出——要改就改 Composed Markdown。
2. 不编造引言、数据、出处、图片说明。
3. 图片本地化；说不出职责的删除；生成图标注示意。
4. 为「看起来丰富」加的元素，全部进 Cut。
5. Gate 1/2 有「必须改」就不交付。
