# 公众号排版组件库 —— 静纸（Silent Paper）

> **本 Skill 的第一套内置主题**，此后新增了「暖信笺 Warm Letter」「酌墨 Wine Ink」，三套并列共存，见 [theme-index.md](theme-index.md)。此前 7 套主题（摸鱼绿/红白色系/石墨极简风/留白禅意风/摸鱼票据风/橄榄手记/沙丘橄榄）已全部下线——它们要么是色块堆砌、要么是对已有骨架机械换色，没有真正的克制感。本主题从零设计，直接采用 [editorial-identity.md](editorial-identity.md)「Silent Paper（静纸）」的色板与阅读人格，排版尺寸按该文档「一、二、三节」的 WeChat 安全改编版本执行；设计变量的组织方式借鉴 [design-tokens.md](design-tokens.md) 的 Token 分层习惯（color / background / text / border 分组），但不是拼接，是围绕同一套气质重新设计的一整套组件。

> **阅读人格**：安静、克制、长期阅读。Apple Journal × Kinfolk × Muji。**唯一的设计纪律：少做一件事，永远比多做一件事更接近高级。** 通篇只有一个强调色（鼠尾草绿 `#6A7567`），且只用在真正值得记住的地方；没有渐变、没有阴影卡片、没有多重描边——留白本身就是装饰。

> **使用说明**：所有组件使用**内联样式**，可直接复制粘贴到微信公众号编辑器。

> **公众号平台限制须知**：
> - ❌ 不支持 `<style>`/`<script>`、CSS class/id/`<div>`、`position:fixed/absolute/sticky`、`float`、`@media`/`@keyframes`、`display:grid`、CSS 变量 `var(--x)`、`<svg>`（大概率被粘贴清洗剥离，图标一律用本文档指定的三种安全技术，见 [visual-assets-guide.md](visual-assets-guide.md)）
> - ✅ 支持内联 `style`、有限 `display:flex`、`border-radius`、`box-shadow`（本主题几乎不用，只有极浅阴影会出现 1 次）、`<section>/<p>/<span>/<strong>/<img>` 等基础标签
> - 所有"装饰性空元素"（分割线、留白占位）**必须在内部放 `<span leaf=""><br></span>` 占位**，否则微信会剥掉样式
> - 所有文字节点必须用 `<span leaf="">文字</span>` 包裹
> - **中文大字号标题禁止负字距**（`letter-spacing` 负值）——这是西文压缩大字号的技巧，中文字符不适用，会导致字挤在一起，本主题全篇 `letter-spacing` 只用 0 或极轻的正值
> - **一个组件只用一种强调手法**，不叠加下划线+加粗+变色+背景块四种技巧于一身

---

## 设计变量速查表（Design Token）

```yaml
color:
  primary_text: "#232323"      # 标题、正文主文字
  secondary_text: "#6E6E6E"    # 次要文字、说明、署名
  muted_text: "#9A9995"        # 最弱层级：页码、时间戳、图片说明
  accent: "#6A7567"            # 唯一强调色（鼠尾草绿），全篇 ≤4 处，锚点专用
background:
  page: "#FCFBF9"               # 引用块/提示块背景
  surface: "#FFFFFF"            # 正文主体背景
  highlight: "#EEF3EE"          # 关键词高亮底色（极浅绿，只配合 accent 使用）
border:
  default: "#F0EEE9"            # 分割线、卡片边框
  quote_bg: "#F7F6F3"           # 引用块背景（比 page 略深一阶）
typography:
  h1: "22px / weight 700 / line-height 1.4 / letter-spacing 0"
  h2: "17px / weight 700 / line-height 1.5 / letter-spacing 0"
  quote: "16px / weight 500 / line-height 1.8（仅引用块/金句卡使用，独立于正文字号）"
  body: "15px / weight 400 / line-height 1.9"
  caption: "13px / weight 400 / line-height 1.7（副标题、导读列表、提示旁注）"
  micro: "11px / weight 600 / letter-spacing 1.5px（页眉标签/编号/图片说明/署名/表头，最弱层级统一用这一档，不再额外开 12px）"
spacing:
  section_gap: "40px"           # 章节之间的垂直间距
  image_gap: "32px"             # 图片上下留白
  paragraph_gap: "20px"         # 段落间距
```

**字号阶梯只有 6 级**（11/13/15/16/17/22px），不额外开新字号——这是唯一保留主题相比此前 7 套主题的核心区别之一，此前任意一套随手一算都有 8~11 种字号；**全篇 accent 用量 ≤4 处**，可用 `design_quality_check.py --accent '#6A7567' --accent-quota 4` 自动核查（accent 与 primary_text 色相区分明显，检测可靠）。**结构性重复元素（列表圆点、提示旁注左侧竖线、页眉细线装饰）一律用次要色 `#9A9995`，不占用 accent 配额**——accent 只留给真正稀缺的强调：正文关键词下划线（组件 4）、金句卡（组件 6，全篇 ≤1 次）。

---

## 组件 1：文章头部（标题区）

不用卡片、不用渐变背景、不用阴影——只有一条细线 + 大量留白。**这是本主题和过去所有主题最大的区别：过去用视觉重量吸引注意力，这里用留白吸引注意力。**

```html
<section style="padding:8px 4px 0;margin-bottom:8px;">
  <p style="font-size:11px;font-weight:600;letter-spacing:1.5px;color:#9A9995;margin:0 0 14px;text-transform:uppercase;">
    <span leaf="">{{英文分类标签，如 EDITORIAL}}</span>
  </p>
  <p style="font-size:22px;font-weight:700;color:#232323;line-height:1.4;margin:0 0 12px;letter-spacing:0;">
    <span leaf="">{{文章标题，超过 16 字在语义断点处用 <br/> 分两行，不按字数硬切}}</span>
  </p>
  <p style="font-size:13px;color:#6E6E6E;line-height:1.7;margin:0 0 20px;">
    <span leaf="">{{一句话副标题或摘要，说清楚这篇文章值得读下去的理由，不是标题的重复}}</span>
  </p>
  <section style="display:flex;align-items:center;gap:10px;">
    <span style="width:24px;height:1px;background:#9A9995;display:inline-block;"><span leaf=""><br></span></span>
    <span style="font-size:11px;color:#9A9995;letter-spacing:0.5px;"><span leaf="">{{日期}} · {{阅读时长估计，如"6 分钟"}}</span></span>
  </section>
</section>
<section style="height:1px;background:#F0EEE9;margin:24px 0 0;"><span leaf=""><br></span></section>
```

## 组件 2：导读（可选，仅 3 章节及以上时生成）

不用卡片、不用编号徽章，纯文字列表 + 细线分隔，克制到近乎"看不见设计"的程度。

```html
<section style="margin:32px 0;padding:20px 0;border-top:1px solid #F0EEE9;border-bottom:1px solid #F0EEE9;">
  <p style="font-size:11px;font-weight:600;letter-spacing:1.5px;color:#9A9995;margin:0 0 14px;text-transform:uppercase;">
    <span leaf="">IN THIS ARTICLE</span>
  </p>
  <p style="font-size:13px;color:#232323;line-height:2.1;margin:0;">
    <span leaf="">01 · {{看点一}}</span><br/>
    <span leaf="">02 · {{看点二}}</span><br/>
    <span leaf="">03 · {{看点三}}</span>
  </p>
</section>
```

## 组件 3：章节标题

编号用极小的次要文字，标题本身靠字重和留白建立层级，不靠色块。**全文只有章节标题允许出现"标题+编号"的组合，不要在别处重复这个模式。**

```html
<section style="margin:40px 0 20px;">
  <p style="font-size:11px;font-weight:600;letter-spacing:1.5px;color:#9A9995;margin:0 0 8px;">
    <span leaf="">CHAPTER 01</span>
  </p>
  <p style="font-size:17px;font-weight:700;color:#232323;line-height:1.5;margin:0;">
    <span leaf="">{{章节标题}}</span>
  </p>
</section>
```

小节标题（`###`，不单独编号，字重区分即可）：

```html
<p style="font-size:15px;font-weight:700;color:#232323;line-height:1.6;margin:28px 0 12px;">
  <span leaf="">{{小节标题}}</span>
</p>
```

## 组件 4：正文段落 + 关键词强调

强调手法只有一种：**极细下划线**（1px，accent 色），不用背景高亮块、不用加粗变色叠加。段落长度按 [editorial-identity.md](editorial-identity.md) 第二节控制在 40~70 字，超过在语义断点拆句。

```html
<p style="font-size:15px;color:#232323;line-height:1.9;margin:0 0 20px;text-align:justify;">
  <span leaf="">这里是正文内容，</span><span style="border-bottom:1px solid #6A7567;padding-bottom:1px;"><span leaf="">这几个字是关键词强调</span></span><span leaf="">，一段最多用 1～2 处，不要每句话都强调，强调多了就没有强调的意义。</span>
</p>
```

段落里如果需要"次要说明"（比 accent 更轻的强调，比如专有名词首次出现），用次要文字色加粗，不加下划线：

```html
<p style="font-size:15px;color:#232323;line-height:1.9;margin:0 0 20px;text-align:justify;">
  <span leaf="">这里提到 </span><strong style="color:#6E6E6E;font-weight:600;"><span leaf="">某个专有名词</span></strong><span leaf="">，用字重区分，不占用 accent 的稀缺配额。</span>
</p>
```

## 组件 5：引用块（居中，呼应"引用单独居中"的编辑惯例）

```html
<section style="margin:36px 0;padding:28px 24px;background:#F7F6F3;border-radius:4px;text-align:center;">
  <p style="font-size:16px;color:#232323;line-height:1.8;margin:0;font-weight:500;">
    <span leaf="">{{引用内容，一句话说完，不超过两行}}</span>
  </p>
  <p style="font-size:11px;color:#9A9995;margin:14px 0 0;">
    <span leaf="">—— {{来源/作者，无来源可删除这一行}}</span>
  </p>
</section>
```

## 组件 6：金句强调卡（全文最多用 1 次，比引用块更强的锚点）

这是全篇视觉最重的组件，正因为稀缺才有效——**一篇文章只用一次**，用在最想让读者截图转发的那句话上。

```html
<section style="margin:36px 0;padding:32px 24px;background:linear-gradient(160deg,#232323 0%,#2B2B2B 100%);border-radius:6px;text-align:center;">
  <p style="font-size:17px;color:#FFFFFF;line-height:1.7;margin:0;font-weight:500;">
    <span leaf="">{{全文最核心的一句话}}</span>
  </p>
</section>
```

（此前是纯色实底 `#232323`，这里换成同色系两段式 `linear-gradient`——深浅差只有 8 个色阶，肉眼几乎看不出"渐变"这个动作本身，只会觉得比纯色块多一点材质厚度，这是参考图里深色区块常用的手法，比纯色实底更有质感但不违反"少做一件事"的纪律，因为观感上仍然是"一块深色"，没有增加视觉元素的数量。）

## 组件 7：提示/旁注（左侧细线，不用背景色块）

```html
<section style="margin:0 0 20px;padding:2px 0 2px 16px;border-left:2px solid #9A9995;">
  <p style="font-size:13px;color:#6E6E6E;line-height:1.7;margin:0;">
    <span leaf="">{{提示或补充说明内容}}</span>
  </p>
</section>
```

## 组件 8：代码块（复用通用增量库深色版，仅换语言标签配色）

直接用 [common-components.md](common-components.md) 组件 1a 深色代码块，不改结构；如需浅色版本，把组件 1b 的左侧竖条颜色换成 `#6A7567`。

## 组件 9：图片 + 说明文字

```html
<section style="margin:32px 0;">
  <img src="{{图片URL}}" style="max-width:100%;height:auto;display:block;margin:0 auto;border-radius:4px;" />
  <p style="font-size:11px;color:#9A9995;text-align:center;margin:10px 0 0;line-height:1.6;">
    <span leaf="">{{图片说明，无说明整段删除，不编造}}</span>
  </p>
</section>
```

配图来源与处理规则见 [visual-assets-guide.md](visual-assets-guide.md)——不直接引用图库网站外链，需先下载本地再走上传流程。

## 组件 10：列表

不用色块编号徽章，用极简的小圆点 + 悬挂缩进。

```html
<section style="margin:0 0 20px;">
  <section style="display:flex;margin-bottom:10px;">
    <span style="flex-shrink:0;width:16px;color:#9A9995;font-size:15px;line-height:1.9;"><span leaf="">·</span></span>
    <p style="font-size:15px;color:#232323;line-height:1.9;margin:0;flex:1;"><span leaf="">{{列表项一}}</span></p>
  </section>
  <section style="display:flex;margin-bottom:10px;">
    <span style="flex-shrink:0;width:16px;color:#9A9995;font-size:15px;line-height:1.9;"><span leaf="">·</span></span>
    <p style="font-size:15px;color:#232323;line-height:1.9;margin:0;flex:1;"><span leaf="">{{列表项二}}</span></p>
  </section>
</section>
```

有序列表把 `·` 换成 `01` `02`（次要文字色，11px）。

## 组件 11：表格替代（卡片化，窄屏不挤压）

```html
<section style="margin:0 0 20px;border:1px solid #F0EEE9;border-radius:6px;overflow:hidden;">
  <section style="display:flex;padding:12px 16px;background:#F7F6F3;">
    <p style="flex:1;font-size:11px;font-weight:600;color:#6E6E6E;margin:0;"><span leaf="">{{列名一}}</span></p>
    <p style="flex:1;font-size:11px;font-weight:600;color:#6E6E6E;margin:0;"><span leaf="">{{列名二}}</span></p>
  </section>
  <section style="display:flex;padding:12px 16px;border-top:1px solid #F0EEE9;">
    <p style="flex:1;font-size:13px;color:#232323;margin:0;"><span leaf="">{{值一}}</span></p>
    <p style="flex:1;font-size:13px;color:#232323;margin:0;"><span leaf="">{{值二}}</span></p>
  </section>
</section>
```

## 组件 12：分割线

```html
<section style="margin:36px 0;text-align:center;">
  <span style="font-size:13px;color:#9A9995;letter-spacing:6px;"><span leaf="">· · ·</span></span>
</section>
```

## 组件 13：结尾互动区（图标用 emoji，不用 SVG——见 visual-assets-guide.md）

```html
<section style="margin:48px 0 0;padding:32px 0 0;border-top:1px solid #F0EEE9;text-align:center;">
  <p style="font-size:13px;color:#6E6E6E;line-height:1.7;margin:0 0 20px;">
    <span leaf="">如果这篇文章对你有用，点个赞、留个言，是对写作最好的鼓励。</span>
  </p>
  <section style="display:flex;justify-content:center;gap:32px;">
    <section style="text-align:center;">
      <span style="font-size:17px;line-height:1;"><span leaf="">👍</span></span>
      <p style="font-size:11px;color:#9A9995;margin:6px 0 0;"><span leaf="">点赞</span></p>
    </section>
    <section style="text-align:center;">
      <span style="font-size:17px;line-height:1;"><span leaf="">👀</span></span>
      <p style="font-size:11px;color:#9A9995;margin:6px 0 0;"><span leaf="">在看</span></p>
    </section>
    <section style="text-align:center;">
      <span style="font-size:17px;line-height:1;"><span leaf="">📤</span></span>
      <p style="font-size:11px;color:#9A9995;margin:6px 0 0;"><span leaf="">转发</span></p>
    </section>
  </section>
</section>
```

## 组件 14：作者签名区（末尾仅一处，占位待用户替换）

```html
<section style="margin:32px 0 0;padding:24px 0 0;text-align:center;">
  <p style="font-size:13px;color:#9A9995;line-height:1.8;margin:0;">
    <span leaf="">{{作者名}} · {{一句话简介，占位待替换}}</span>
  </p>
</section>
```

## 组件 15：深色导语封面区块（可选，仅用于需要仪式感开篇的文章类型）

> **默认不用**，组件 1 仍是首选。这是 [common-components.md](common-components.md)「深色导语封面区块」的静纸配色变体，只在文章类型是深度报道/年度总结这类需要"先声夺人"的开篇时才考虑换用，一篇文章只在最开头用一次，不与组件 1 同时出现——用了这个就不再重复组件 1。

```html
<section style="margin:0 0 40px;padding:52px 24px;border-radius:6px;background:linear-gradient(165deg,#1E1E1E 0%,#272727 100%);box-sizing:border-box;">
  <p style="margin:0 0 20px;text-align:center;font-size:11px;font-weight:700;letter-spacing:4px;color:#8FA88A;text-transform:uppercase;">
    <span leaf="">{{小标签，如"深度报道""年度总结"}}</span>
  </p>
  <p style="margin:0 0 24px;text-align:center;font-size:24px;font-weight:700;line-height:1.4;color:#FFFFFF;">
    <span leaf="">{{文章标题，超过 18 字在语义断点处用 <br/> 分两行}}</span>
  </p>
  <p style="margin:0 auto;text-align:center;max-width:80%;font-size:12px;font-weight:500;line-height:1.6;color:#232323;background:#FFFFFF;padding:8px 18px;border-radius:20px;">
    <span leaf="">{{一句话副标题/摘要}}</span>
  </p>
</section>
```

（深色底用比正文更深一阶的纯灰 `#1E1E1E→#272727`，不引入新色相，保持"全篇只有一个强调色"的纪律；小标签用accent 的浅色变体 `#8FA88A`（而不是原色 `#6A7567`）——纯深灰背景上，原色 accent 对比度不够醒目，浅一阶的同色相变体在深色底上更清晰，这一处不计入正文 accent 配额，因为它和组件 1 是互斥关系，不会同时出现在同一篇文章里。）

---

## 完整文章模板骨架

```
组件1 文章头部
[组件2 导读]（3章节以上时生成）
循环：
  组件3 章节标题
  组件4 正文段落（1~2处占据组件7/9/10/11按内容需要插入，组件5引用/组件6金句全篇各只用1次）
组件12 分割线（可选，仅内容天然有大转折时插入）
组件13 结尾互动区
组件14 作者签名区
```

## 文章类型 → 组件组合配方

| 文章类型 | 核心组件 | 点缀组件（按需，不要堆） |
|---|---|---|
| 深度分析/观点 | 组件1+3+4+6 | 组件5 引用（≤2处）、组件7 提示 |
| 教程/操作指南 | 组件1+2+3+4+10 | 组件8 代码块、组件9 图片 |
| 生活方式/随笔 | 组件1+4+5 | 组件6 金句（仅1次）、组件9 图片 |
| 数据/案例复盘 | 组件1+2+3+4+11 | 组件9 图片、组件7 提示 |

## Markdown → 组件映射规则表

| Markdown 元素 | 对应组件 |
|---|---|
| `# 标题` | 组件 1 |
| `## 章节` | 组件 3（大号，编号） |
| `### 子章节` | 组件 3（小节标题变体，不编号） |
| 开头 `> 引用` | 组件 1 副标题（如果是一句话摘要）或组件 5（如果是独立引言） |
| 正文 `> 引用` | 组件 5 |
| `**加粗**` | 组件 4 的"次要说明"变体（`<strong>` 次要色） |
| `==高亮==` / 语义上的核心结论 | 组件 4 的"关键词强调"变体（下划线），全文最重要的一句用组件 6（仅一次） |
| 代码块 | 组件 8 |
| `![]()` | 组件 9 |
| 列表 | 组件 10 |
| 表格 | 组件 11 |
| `---` | 组件 12（仅内容有大转折时用，不逢 `---` 必用） |

---

## Gotchas（本主题设计时刻意规避的坑）

- **不引入负字距**：过去的主题在大字号标题上用 `letter-spacing:-2px` 压缩中文字符，导致视觉拥挤，本主题全篇不用负值。
- **不堆叠强调技巧**：一个组件只用一种强调手法（下划线 或 加粗 或 深色块），不三种一起上。
- **不用虚线框**：过去多套主题滥用 `border:dashed` 做强调框，`design_quality_check.py`/`component_lint.py` 已经把这个模式标为 WARNING 级别的坏味道，本主题不用。
- **不用图标库/SVG**：结尾互动区用 emoji，理由见 [visual-assets-guide.md](visual-assets-guide.md)。
- **accent 色全篇 ≤4 处**：组件 6（金句卡，≤1 次）+ 组件 4 下划线强调（按段落，克制使用）+ 组件 1 的细线装饰，加起来控制在 4 处以内，多了就不稀缺了。
- **字号只用 5 级**：11/12/15/17/22px，不额外开新字号迁就某个组件的"视觉需要"。
