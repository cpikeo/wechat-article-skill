# Direction：视觉导演

DIRECT / VISUALIZE 两步读这份。**判据在 SKILL.md，这里只讲怎么做到。**

## 1 Visual Thesis

一句话回答「这篇看起来像什么」，再补四项。写完自检：它能不能同时否掉三张不该出现的图？

```
Thesis: 结构性的冷静 —— 用基础设施摄影的尺度感 + 编辑式信息图，呈现系统的秩序与约束
气质   冷静 / 低饱和 / 有重量
隐喻   电网、走廊、尺度（只选一个，不要三个一起上）
重量   中偏重：大画幅开场，正文克制
禁止   人物特写、霓虹、发光电路、机器人、3D 渲染感
```

三种可校准的气质（不要照抄，用来对齐）：

| 类型 | 常见题材 | 语言 | 反例 |
|---|---|---|---|
| 分析型 | 行业、技术、评论 | 结构摄影 + 信息图，冷、平视、无人物 | 蓝紫科技插画 |
| 叙事型 | 人物、城市、回忆 | 自然光纪实，暖、有颗粒、近景与细节交替 | 过曝滤镜、摆拍笑 |
| 材质型 | 品牌、工艺、产品 | 物体与材质特写，高精度、浅景深、留白大 | 拼贴、贴纸感图标 |

## 2 Visual Grammar 十项

色盘（从主题气候推导，不另造色）· 光源与方向 · 材质 · 镜头与视角 · 画幅比例 · 裁切 · 主体位置 · 说明语气 · 图形语言（线 / 点 / 编号）· 允许的例外。

判据只有一个：**把全篇图并排放在一起，像不像同一次拍摄、同一位插画师。**
不一致时的正确做法是把后来那张重做或删掉，不是再加一张折中风格。

## 3 Role 对应

| 职责 | 通常放在 | 画幅 | 说明语气 |
|---|---|---|---|
| Anchor 入口 | 首屏之后第一处停顿 | 大（通栏） | 一句，不解释 |
| Explain 解释 | 概念第一次出现处 | 中 | 讲清怎么读这张图 |
| Evidence 证据 | 论点之后紧跟 | 中 | 出处 / 时间 / 地点 |
| Compare 对比 | 两个对象各说完之后 | 中，可并置 | 说清差异维度 |
| Structure 关系 | 流程、层级、依赖出现处 | 中 | 只用必要的节点词 |
| Context 场景 | 换场景 / 换时间点 | 大 | 交代地点与状态 |
| Metaphor 隐喻 | 抽象判断处，全文 ≤1 | 中 | 点破隐喻，不铺陈 |
| Rhythm 停顿 | 长段之后 | 小或极窄 | 可以只有一句 |
| Data 数量 | 数字第一次出现处 | 中 | 必带口径与出处 |
| Cover 第一印象 | 文章之外（frontmatter） | 2.35:1 | 不放文字 |

## 4 Information Gain 三问

1. 文字已经说过的，图是不是在重复？
2. 难解释的一句话，图有没有变成一眼能懂？
3. 390px 上主体与关系还看得清吗？

两问不过 → 删。能改用 CSS 图示 → 改。
改写的典型：**「排队的容量比电网本身还大」** 不需要配图，用 `::: data` 并排两个数字就成立；
**「密度三年翻四倍」** 不需要插画，用 `::: bars` 的表达比任何渲染图都准确。

## 5 Prompt 编译（不维护模板库）

描述永远由 Decision 派生，链条固定：

```
Intent → Role → Concept → Subject → Composition → Camera → Light → Material
→ Palette(服从主题) → Safe area → Crop → Mobile(390px)
```

- 同篇所有描述里，`Light / Material / Palette / Camera` 子句**逐字一致**（这就是连续性）。
- 负面清单固定，缺一项就是风险：`no text, no logo, no watermark, no people（除非叙事需要）, no neon, no HDR sheen, no lens flare, no collage`。
- 不写「4K、超高清、masterpiece」这类无方向的词；写可被验证的物理事实（阴天散射光、淬火铜的划痕、混凝土的麻面）。

示例（封面，从 §1 的 Thesis 派生）：

> Editorial architectural photograph, wide 2.35:1: high-voltage transmission corridor at dusk from a high vantage point, steel lattice pylons receding into cold blue-grey haze; low saturation graphite/concrete/pale sky with a faint amber horizon; soft overcast light, long shadows, fine grain, 35mm, deep depth of field; subject mass slightly left of centre, right third quiet as text-safe area. No people, no text, no logo, no neon, not futuristic.

示例（正文 Context，同一套光照与色盘）：

> Editorial still-life, 3:2: extreme close-up of heavy copper busbars and bolted lugs inside grey-painted industrial switchgear; oxidised copper, machined surface, fine dust; soft overcast top light with gentle falloff, cool desaturated copper/graphite/steel-blue palette, 50mm, shallow depth of field. No people, no text, no logo, no sparks, no HDR sheen.

生成图用于事实性内容时，图注必须写明「示意」。**宁可留 `todo`，也不塞低质量或不诚实的图。**

## 6 封面工艺

- 比例 **2.35:1**（首图 1080×460 起，最小 900×383）。
- **真正的硬约束是 1:1 中央裁切**：信息流与会话卡片会把封面从中间裁成正方形。所以主体必须落在**画面正中**，
  而不是「左边压一条、右边留白」——那种构图在 2.35:1 上成立，在 1:1 上会把主体切掉一半。
  问自己：把这张图从中间裁成正方形，还剩不剩得下主语？
- **默认不放文字**：标题由微信排版，图上烧字会被裁、被判违规、且缩略后不可读。必须放字时，字要在中央 60% 内且 390px 缩略仍可读。
- 三问：读者第一眼看到什么？视觉焦点在哪？1:1 中央裁切后它还成立吗？
- 预览顶部同时给出 2.35:1 首图与 1:1 信息流两种裁切，就是用来回答第三个问题的。
- 常见错误：把正文图顺手当封面（横竖比例不对）、封面讲的是话题而不是主张、为了「高级」做成纯色渐变 + 小字、主体偏在一侧导致 1:1 裁切缺角。
- `render.py` 会在预览顶部给出 2.35:1 与 1:1 两种裁切，用来检查主体是否被切。

## 7 数据与图示

优先级：**表格 > `::: bars` > `::: data` > 配图**。
能用文字说清的数字，什么图都不要做。

- `::: data`：≤3 项，且必须靠并排才成立（对比、跨度、量级）。
- `::: bars`：2–6 项、同一口径、有明确最大值；数值必须是数字，标签写口径与时间。
- 数字必须有出处；预测必须标「预测」；不同口径的数字不要放进同一张图。

## 8 失败样例（黑名单）

蓝紫科技插画 · 机器人握手 · 发光电路板 · 抽象粒子与光斑 · 多风格拼贴 · 图上烧字 · AI 生成的「用户头像」当真实人物 · 假历史照片 · 编造的品牌 / 产品 / 数据 · 为空白处补的装饰图 · 每节一张的「氛围图」。

## 9 素材落地

- 命名语义化：`images/cover.jpg`、`images/fig-busbar.jpg`；不要 `image1.png`。
- 尺寸下限：正文图宽 ≥1200px（竖图短边 ≥800）；封面 ≥900×383。压缩后单张 <1MB 为宜。
- 引用必须本地路径（外链一律 Gate 1 FAIL）；暂缺就写 `![说明](todo "职责")`。
- 生成或下载后**先看**：主体是否清楚、有没有多余文字 / 水印、与文章事实是否冲突；不合格就重做或删。
