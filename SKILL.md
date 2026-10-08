---
name: wechat-article
description: 把 Markdown/Word/纯文本做成可直接粘贴进公众号编辑器的编辑设计水准 HTML，并按需要做视觉导演（Visual Thesis / 封面 / 配图 / CSS 图示）。判断驱动：先写 Decision，再判断视觉资产是否值得存在，再 Compose，一次渲染出正文 HTML + 390px 预览 + Gate 1/2/3。可选官方 API 建草稿/发布。触发：公众号排版/微信排版/gzh/一键排版/自动发布/新主题/封面/配图。不用于普通网页/落地页/PPT。
---

# WeChat Article · Editorial Intelligence

把一篇文章变成值得读完、值得记住的公众号成品。
代码是执行器，主题是材料，图片是工具。**判断是最高层。**

宪法只有一句：**每个元素都必须有职责；说不出职责的，删。**

## 流水线

```
UNDERSTAND → JUDGE → EDIT → DIRECT → VISUALIZE → COMPOSE → RENDER → VERIFY → REFINE
```

| 步 | 做什么 |
|---|---|
| 1 UNDERSTAND | 只读一次原文：谁在读、为什么读、读完记住哪一句 |
| 2 JUDGE | 写 Decision：主张、层级、节奏、主题、预算、删什么 |
| 3 EDIT | 按 Decision 改文字（不改事实）：先删，再合并，最后才顺句子 |
| 4 DIRECT | 定 Visual Thesis / Grammar / Slots / Cover 方向（写进 Decision） |
| 5 VISUALIZE | 取资产：现有素材 → 生成 → CSS 图示 → 无图 |
| 6 COMPOSE | 输出 Composed Markdown（全流程唯一的可交付源） |
| 7 RENDER | `python3 scripts/render.py 文章.md` → HTML + 390px 预览 + Gate 1/2 |
| 8 VERIFY | 通读 390px 预览，Gate 3 五层，只写 KEEP / REVISE / DELETE |
| 9 REFINE | 只改 Markdown；只有出现「必须改」才允许第二次渲染 |

默认全自动。交付：Decision + 三关结论 + 用户待办（署名 / 补素材 / 粘贴）。

## 只加载需要的知识

| 何时 | 读什么 | 类别 |
|---|---|---|
| 每次 | 本文件 | 宪法 + 决策系统 |
| 每次排版（JUDGE / EDIT） | `references/decide.md` | Decision Knowledge |
| 需要封面 / 配图 / 图示（DIRECT / VISUALIZE） | `references/direction.md` | Visual Knowledge |
| Gate 1 FAIL、手改 HTML | `references/platform.md` | Technical Constraint |
| 发布 / 草稿 / 凭证 | `references/publish.md` | Technical Constraint |
| 回归 | `python3 scripts/selftest.py`，用例在 `eval/` | QA |
| 不要读 | `scripts/*`（执行器）、`AUDIT.md`（历史审计） | — |

脚本不是设计规则来源；脚本只执行**可确定**的那部分判断。

## Decision（导演 brief，不是 JSON；不确定就写「未知，按默认」，不编造）

四行一组，每行都要有消费者。写不出消费者的字段，删掉。

```
READ     Audience · Intent · Core Claim · Hierarchy · Cut
RHYTHM   Mode（六种人格之一） · Density · Rhythm · Anchor
VISUAL   Thesis · Grammar · Budget · Slots（职责｜为什么｜放哪） · Cover
REVIEW   Gate 3 结论：KEEP / REVISE / DELETE · 哪个元素消失了
```

## 视觉判断（核心）

**Visual Thesis**：先回答「这篇文章看起来像什么」，再决定任何一张图。
一句话 + 四项：气质 / 视觉隐喻 / 视觉重量 / 克制点（这篇不允许出现什么）。
不是「科技文 → 蓝紫科技风」，而是「AI 基础设施的长期演化 → 结构性摄影 + 编辑式信息图，冷静、有尺度，不要发光电路与机器人」。

**Visual Grammar**：全篇一套。光源 · 材质 · 色盘（服从主题气候）· 镜头与视角 · 画幅 · 裁切 · 说明语气 · 图形语言。
同一篇不得混搭摄影 + 3D + 卡通 + 赛博。只有内容本身要求语言阶段性变化时才允许，且要说得出理由。

**Visual Role**：不先问「要不要图」，先问「这个位置需要什么职能」。
`Anchor` 入口 · `Explain` 解释 · `Evidence` 证据 · `Compare` 差异 · `Structure` 关系 · `Context` 场景 · `Metaphor` 隐喻 · `Rhythm` 停顿 · `Data` 数量 · `Cover` 第一印象。
统一写中文亦可（锚点 / 解释 / 证据 / 对比 / 结构 / 场景 / 隐喻 / 停顿 / 数据）。说不出唯一职责 → 删。

**Visual Information Gain**：图给的信息必须多于文字重复的信息。
优先 **图示 > 装饰**：流程、关系、数量，先问能不能用 CSS 图示（`::: bars` / `::: data` / 表格）说清；能，就不生成图。
禁止为留白、为高级感、为丰富度、为 SEO 配图；禁止每节配图、平均分配。

**节奏**：图、标题、留白、分隔线都是节奏乐器——按 Rhythm 分配，不按篇幅均摊。长段之后给停顿，高潮前留空，高潮后立刻回到正文。

**Image Budget**：先定预算上限，再取素材。
≤800 字 0–1 张；800–2000 字 1–3 张；2000 字以上 2–4 张。封面单列，且必须有。
超预算的候选直接删，不降级成装饰；同一职责最多出现两次。

**取资产顺序**：现有素材 > 生成 > 图示（CSS）> 无图。已有高质量素材就不生成。

**事实安全**：视觉不得制造事实。不出现不存在的人 / 地点 / 数据 / 事件、错误品牌与产品。
生成图用作事实性内容时必须标注「示意」；宁可留 `todo`。

**连续性**：同一人物 / 产品 / 场景 / 材质在多张图里必须一致（外观、材质、光、色、视角、状态）。
把 Grammar 写进 Decision，每条生成描述都照抄同一套光源 / 材质 / 色盘 / 镜头。

**封面**：不是「正文图 + 标题」，它单独做 art direction（Core Claim → 概念 → 隐喻 → 构图 → 裁切）。
默认不放文字（微信会自行裁切与叠加标题）；2.35:1，主体在中央安全区；必须在 390px 缩略图下依然成立。

## Compose = 视觉层级词汇

`Core Claim > Section Claim > Evidence > Explanation > Metadata > Decoration`
能用纯文字就不用原语。

```yaml
---
title: 主标题|断行后半
kicker: LETTER
theme: letter            # paper / letter / ink / frost / bone / folio
density: airy            # dense / standard / airy
deck: 一句副题           # 可选；与 lead 不要叠两个钩子
date: 2026年10月8日
toc: true                # ≥3 个 H2 才生效
author: 甲木
bio: 一句话简介
cta: 结尾一句话
cover: images/cover.jpg  # 公众号封面；写 todo = 待补
---
```

| 写法 | 职责 |
|---|---|
| `> 开头` | lead，首屏钩子；没有就不写 |
| `::: peak` | 全文唯一高潮 = Core Claim |
| `> 正文` | quote，他者声音；不要做成第二个 Peak |
| `::: data` | ≤3 项数字并置；关系靠并排才成立时 |
| `::: bars` | 数量对比：`数值｜标签`；横向长度表达量级 |
| `::: note 标签` | 旁注；删掉也不伤主线 |
| `==标记==` | 关键判断，全篇 ≤3 |
| `**加粗**` | 弱强调，少用 |
| `![说明](路径 "职责")` | 职责必填；`todo` = 待补素材 |
| `---` | 转场；少于 H2 数 |
| H2 / H3 | Section Claim；标题后必须接正文 |

## QA

- **Gate 1 Platform**（脚本）：微信 HTML 硬约束。FAIL 不交付。
- **Gate 2 Composition**（脚本）：结构、原语密度、图片职责与预算、文件是否存在、分辨率、封面裁切。
  「必须改」修完；「建议改」逐条给出改或保留的理由。
- **Gate 3 Art Direction**（通读 390px 预览，五层）：
  - CONTENT：主张是否清楚、内容是否准确（含图片有没有制造事实）
  - EDITORIAL：层级是否成立、节奏是否自然、有没有冗余
  - VISUAL：Thesis 是否成立、Grammar 是否统一、每张图是否有职责与信息增量、封面是否真正表达文章、有没有「漂亮但无意义」的视觉
  - MOBILE：390px 是否成立、图像主体是否清楚、标题是否可读、留白有没有把内容切断、图片是否造成滚动疲劳
  - 结论只写 **KEEP / REVISE / DELETE**，并强制回答：**What should disappear?**
  不打分。分数只服务回归，不替代艺术判断。

## 硬规则

1. 不手写 HTML，不改渲染器输出——要改就改 Composed Markdown。
2. 不编造引言、数据、出处、图片说明。
3. 图片本地化；说不出职责的删除；生成图标注示意。
4. 为「看起来丰富」加的元素，全部进 Cut。
5. Gate 1/2 有「必须改」就不交付。
