# 公众号排版组件库 —— 酌墨（Wine Ink）

> **新增主题**，与「静纸 Silent Paper」「暖信笺 Warm Letter」并列，不替代二者。设计动机：静纸走"极致留白、近乎看不见设计"的路线，暖信笺走"温暖叙事"的路线，但两者都刻意回避"视觉重量"——对偏好**更有文人气、更像一本正式出版物**而不是"笔记感"的内容（深度评论、行业观察、书评影评、访谈实录、年度总结），需要一套**更笃定、更有印刷质感**的表达。酌墨要做的不是"更花哨"，而是"更像一本装帧讲究的书"。

> **阅读人格**：笃定、克制而不寡淡、有文人分量。像一本装帧考究的评论集或独立书店的选书笔记，不是手记也不是备忘录。**唯一的设计纪律：用一种颜色把话说重，而不是用很多颜色把话说满。** 全篇只有一个强调色（深绛红 `#7A2E2E`），但比静纸多一层"印刷质感"——衬线大标题、图章式收尾符号、卡片用极细描边而不是纯留白分隔。

> **和现有两套主题的关键区别**（决定它何时该被选用）：
> - 静纸：无衬线全篇统一字体，标题靠字号/字重区分，气质是"安静到没有存在感"。
> - 暖信笺：温暖橙色叙事，圆角卡片较多，气质是"像收到一封信"。
> - **酌墨：标题用系统衬线字体（宋体），正文用无衬线，两者对比制造"编辑刊物"的层级感；收尾/强调符号用「图章式圆环 + 字符」而不是 emoji，全篇色彩比静纸更笃定（强调色只有一处但用得更重）。**

> **使用说明**：所有组件使用**内联样式**，可直接复制粘贴到微信公众号编辑器。

> **公众号平台限制须知**（与其余主题共通，完整清单见 SKILL.md「平台红线」）：
> - ❌ 不支持 `<style>`/`<script>`、CSS class/id/`<div>`、`position:fixed/absolute/sticky`、`float`、`@media`/`@keyframes`、`display:grid`、CSS 变量、`<svg>`
> - ✅ 支持内联 `style`、有限 `display:flex`、`border-radius`、`box-shadow`、`linear-gradient`、`<section>/<p>/<span>/<strong>/<img>`
> - **本主题的"图标"全部由「细描边圆环 + 排版符号（✓ ◎ → 等 Unicode 字符，非 emoji）」构成**，不使用任何彩色 emoji（🔴🟡🟢👍👀📤 这类），理由见 [visual-assets-guide.md](visual-assets-guide.md)——emoji 自带独立配色，和本主题"全篇仅一处强调色"的纪律冲突，观感上也是最容易让整体设计显得廉价、拼凑的来源之一；圆环+字符方案用主题色统一渲染，是**本主题相比其余两套主题的核心改进点**，其余两套主题沿用 emoji 是历史遗留，不建议迁就。
> - **系统衬线字体（`"Songti SC","STSong",serif`）用于大标题**：这是系统预装字体（iOS/macOS/Windows 中文系统均自带宋体族），不是外部字体文件，不触发"外部字体不被支持"的红线，也不需要 `@font-face`——只是在 `font-family` 里多写一个系统已有的字体名，公众号编辑器不会剥离这条声明。若某些安卓机型缺少对应宋体、会自动回退到系统默认无衬线字体，不影响内容完整性，只是标题的"衬线感"在少数设备上会打折扣，这是已知的、可接受的兜底行为。
> - 所有"装饰性空元素"内部必须放 `<span leaf=""><br></span>` 占位；所有文字节点必须用 `<span leaf="">文字</span>` 包裹；一个组件只用一种强调手法，不叠加。

---

## 设计变量速查表（Design Token）

```yaml
color:
  primary_text: "#1C1A1A"      # 标题、正文主文字（暖近黑，比纯黑#000柔和）
  secondary_text: "#6E6764"    # 次要文字、说明、署名
  muted_text: "#A39C98"        # 最弱层级：页码、时间戳、图片说明、图章标签
  accent: "#7A2E2E"            # 唯一强调色（深绛红），全篇 ≤4 处，锚点专用
background:
  page: "#FBF8F6"               # 引用块/图章区背景（暖白，略偏米粉）
  surface: "#FFFFFF"            # 正文主体背景
  highlight: "#F6EFEC"          # 关键词高亮底色（极浅绛红，只配合 accent 使用）
border:
  default: "#ECE4E1"            # 分割线、卡片边框
  ring: "#D8CFC9"                # 图章圆环描边（比 border.default 略深，保证描边可见）
  quote_bg: "#F2E7E3"            # 引用块背景（比 highlight 深一阶，块级容器和内联高亮拉开层次，不是同一个色值）
typography:
  h1: "22px / weight 700 / line-height 1.45 / letter-spacing 0.5px / font-family 衬线（宋体族）"
  h2: "17px / weight 700 / line-height 1.5 / letter-spacing 0 / font-family 无衬线"
  quote: "16px / weight 500 / line-height 1.85 / font-family 衬线（宋体族）——引用/金句区专用衬线，制造'摘录感'"
  body: "15px / weight 400 / line-height 1.9 / font-family 无衬线"
  caption: "13px / weight 400 / line-height 1.7（副标题、导读列表、提示旁注）"
  micro: "11px / weight 600 / letter-spacing 1.5px（页眉标签/编号/图片说明/署名/图章标签）"
spacing:
  section_gap: "40px"
  image_gap: "32px"
  paragraph_gap: "20px"
```

**字号阶梯只有 6 级**（11/13/15/16/17/22px），与静纸一致，不迁就任何组件额外开新字号。**全篇 accent 用量 ≤4 处**，可用 `design_quality_check.py --accent '#7A2E2E' --accent-quota 4` 自动核查（accent 与 primary_text 色相区分明显，检测可靠）。**结构性重复元素（列表圆点、图章圆环描边、页眉细线）一律用 `border.ring`/`muted_text` 这类中性色，不占 accent 配额**——accent 只留给正文关键词下划线（组件 5）和金句卡（组件 6，全篇 ≤1 次）。

**关于"衬线标题"的字体声明写法**：本主题所有需要衬线的元素统一写 `font-family:"Songti SC","STSong","SimSun",serif;`，四个候选值按"macOS/iOS 优先→Windows 备选→通用宋体名→最终回退到系统衬线"排列，确保绝大多数设备都能命中一个宋体字重，实在没有宋体的设备回退到系统默认 serif，不会缺字或报错。

---

## 组件 1：文章头部（标题区，衬线大标题 + 图章式期号）

不用卡片、不用渐变——用**衬线标题**建立"这是一本正式出版物"的第一印象，配一个类似期刊"卷期号"的图章式小标记。

```html
<section style="padding:8px 4px 0;margin-bottom:8px;">
  <section style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
    <span style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;border:1px solid #7A2E2E;color:#7A2E2E;font-size:11px;font-weight:700;"><span leaf="">酌</span></span>
    <span style="font-size:11px;font-weight:600;letter-spacing:1.5px;color:#A39C98;text-transform:uppercase;"><span leaf="">{{英文分类标签，如 REVIEW / ESSAY}}</span></span>
  </section>
  <p style="font-size:22px;font-weight:700;color:#1C1A1A;line-height:1.45;margin:0 0 12px;letter-spacing:0.5px;font-family:&quot;Songti SC&quot;,&quot;STSong&quot;,&quot;SimSun&quot;,serif;">
    <span leaf="">{{文章标题，超过 16 字在语义断点处用 &lt;br/&gt; 分两行，不按字数硬切}}</span>
  </p>
  <p style="font-size:13px;color:#6E6764;line-height:1.7;margin:0 0 20px;">
    <span leaf="">{{一句话副标题，说清楚这篇值得读下去的理由，不是标题的重复}}</span>
  </p>
  <section style="display:flex;align-items:center;gap:10px;">
    <span style="width:24px;height:1px;background:#D8CFC9;display:inline-block;"><span leaf=""><br></span></span>
    <span style="font-size:11px;color:#A39C98;letter-spacing:0.5px;"><span leaf="">{{日期}} · {{阅读时长估计，如"6 分钟"}}</span></span>
  </section>
</section>
<section style="height:1px;background:#ECE4E1;margin:24px 0 0;"><span leaf=""><br></span></section>
```

**"酌"字图章**：默认放一个和主题名呼应的单字（如"酌"），也可以按文章系列/专栏名换成任意单字或双字缩写（如专栏名"评"/"记"），起到"期刊 Logo 角标"的作用，不是随便选的装饰。

## 组件 2：导读（仅 3 章节及以上时生成）

```html
<section style="margin:32px 0;padding:20px 0;border-top:1px solid #ECE4E1;border-bottom:1px solid #ECE4E1;">
  <p style="font-size:11px;font-weight:600;letter-spacing:1.5px;color:#A39C98;margin:0 0 14px;text-transform:uppercase;">
    <span leaf="">IN THIS ISSUE</span>
  </p>
  <p style="font-size:13px;color:#1C1A1A;line-height:2.1;margin:0;">
    <span leaf="">01 · {{看点一}}</span><br/>
    <span leaf="">02 · {{看点二}}</span><br/>
    <span leaf="">03 · {{看点三}}</span>
  </p>
</section>
```

## 组件 3：章节标题（无衬线，与衬线大标题形成对比层级）

```html
<section style="margin:40px 0 20px;">
  <p style="font-size:11px;font-weight:600;letter-spacing:1.5px;color:#A39C98;margin:0 0 8px;">
    <span leaf="">CHAPTER 01</span>
  </p>
  <p style="font-size:17px;font-weight:700;color:#1C1A1A;line-height:1.5;margin:0;">
    <span leaf="">{{章节标题}}</span>
  </p>
</section>
```

小节标题（`###`，不单独编号）：

```html
<p style="font-size:15px;font-weight:700;color:#1C1A1A;line-height:1.6;margin:28px 0 12px;">
  <span leaf="">{{小节标题}}</span>
</p>
```

## 组件 4：正文段落 + 关键词强调

```html
<p style="font-size:15px;color:#1C1A1A;line-height:1.9;margin:0 0 20px;text-align:justify;">
  <span leaf="">这里是正文内容，</span><span style="border-bottom:1px solid #7A2E2E;padding-bottom:1px;"><span leaf="">这几个字是关键词强调</span></span><span leaf="">，一段最多用 1～2 处。</span>
</p>
```

次要说明（专有名词首次出现，不占 accent 配额）：

```html
<p style="font-size:15px;color:#1C1A1A;line-height:1.9;margin:0 0 20px;text-align:justify;">
  <span leaf="">这里提到 </span><strong style="color:#6E6764;font-weight:600;"><span leaf="">某个专有名词</span></strong><span leaf="">，用字重区分。</span>
</p>
```

## 组件 5：引用块（衬线摘录体，制造"引文"的印刷感）

静纸的引用块用无衬线居中，酌墨改用**衬线字体**呈现引用文字本身——这是本主题区别于其余两套主题最直接的细节：引用在视觉上真的"像被摘录出来的一段文字"，而不是同一套字体换了颜色。

```html
<section style="margin:36px 0;padding:28px 24px;background:#F2E7E3;border-radius:2px;text-align:center;">
  <p style="font-size:16px;color:#1C1A1A;line-height:1.85;margin:0;font-weight:500;font-family:&quot;Songti SC&quot;,&quot;STSong&quot;,&quot;SimSun&quot;,serif;">
    <span leaf="">「{{引用内容，一句话说完，不超过两行}}」</span>
  </p>
  <p style="font-size:11px;color:#A39C98;margin:14px 0 0;">
    <span leaf="">—— {{来源/作者，无来源可删除这一行}}</span>
  </p>
</section>
```

## 组件 6：金句强调卡（全文最多用 1 次）

```html
<section style="margin:36px 0;padding:32px 24px;background:linear-gradient(160deg,#1C1A1A 0%,#272322 100%);border-radius:3px;text-align:center;">
  <p style="font-size:17px;color:#FBF8F6;line-height:1.75;margin:0;font-weight:500;font-family:&quot;Songti SC&quot;,&quot;STSong&quot;,&quot;SimSun&quot;,serif;">
    <span leaf="">「{{全文最核心的一句话}}」</span>
  </p>
</section>
```

（和静纸/暖信笺的处理一致：纯色实底换成同色系微渐变，增加材质厚度感，不增加视觉元素数量。）

## 组件 7：提示/旁注（左侧细线）

```html
<section style="margin:0 0 20px;padding:2px 0 2px 16px;border-left:2px solid #A39C98;">
  <p style="font-size:13px;color:#6E6764;line-height:1.7;margin:0;">
    <span leaf="">{{提示或补充说明内容}}</span>
  </p>
</section>
```

## 组件 8：代码块

直接用 [common-components.md](common-components.md) 组件 1a 深色代码块，**但删除顶栏三色圆点（🔴🟡🟢 macOS 窗口按钮那套），只保留语言标签文字**——这三个彩色圆点是本组件库审查时发现的另一处"廉价感"来源：三个高饱和红黄绿圆点和酌墨/静纸的克制配色体系完全脱节，是抄袭终端截图的装饰性模仿，没有信息量。改法：

```html
<section style="margin:0 0 20px;border-radius:6px;overflow:hidden;background:#1E1B1A;">
  <section style="display:flex;align-items:center;padding:9px 14px;background:#141211;">
    <span style="font-size:11px;font-weight:600;color:#8A8580;font-family:Consolas,Monaco,monospace;letter-spacing:1.5px;text-transform:uppercase;"><span leaf="">python</span></span>
  </section>
  <section style="padding:11px 14px;">
    <p style="margin:0;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:13px;line-height:1.6;color:#EDE8E5;"><span leaf="">{{代码行}}</span></p>
  </section>
</section>
```

浅色代码块同理，去掉顶栏图形装饰，左竖条换成 `#7A2E2E`。

## 组件 9：图片 + 说明文字

```html
<section style="margin:32px 0;">
  <img src="{{图片URL}}" style="max-width:100%;height:auto;display:block;margin:0 auto;border-radius:2px;" />
  <p style="font-size:11px;color:#A39C98;text-align:center;margin:10px 0 0;line-height:1.6;">
    <span leaf="">{{图片说明，无说明整段删除，不编造}}</span>
  </p>
</section>
```

## 组件 10：列表

```html
<section style="margin:0 0 20px;">
  <section style="display:flex;margin-bottom:10px;">
    <span style="flex-shrink:0;width:16px;color:#A39C98;font-size:15px;line-height:1.9;"><span leaf="">·</span></span>
    <p style="font-size:15px;color:#1C1A1A;line-height:1.9;margin:0;flex:1;"><span leaf="">{{列表项}}</span></p>
  </section>
</section>
```

有序列表把 `·` 换成 `01` `02`（muted_text，11px）。

## 组件 11：表格替代（卡片化）

```html
<section style="margin:0 0 20px;border:1px solid #ECE4E1;border-radius:4px;overflow:hidden;">
  <section style="display:flex;padding:12px 16px;background:#F6EFEC;">
    <p style="flex:1;font-size:11px;font-weight:600;color:#6E6764;margin:0;"><span leaf="">{{列名一}}</span></p>
    <p style="flex:1;font-size:11px;font-weight:600;color:#6E6764;margin:0;"><span leaf="">{{列名二}}</span></p>
  </section>
  <section style="display:flex;padding:12px 16px;border-top:1px solid #ECE4E1;">
    <p style="flex:1;font-size:13px;color:#1C1A1A;margin:0;"><span leaf="">{{值一}}</span></p>
    <p style="flex:1;font-size:13px;color:#1C1A1A;margin:0;"><span leaf="">{{值二}}</span></p>
  </section>
</section>
```

## 组件 12：分割线（图章式，替代静纸的"· · ·"）

```html
<section style="margin:36px 0;text-align:center;">
  <span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;border:1px solid #D8CFC9;color:#A39C98;font-size:10px;"><span leaf="">·</span></span>
</section>
```

## 组件 13：结尾互动区（图章式圆环图标，**核心改进：完全不用 emoji**）

这是本主题相比静纸/暖信笺最直接可见的改进点。静纸/暖信笺的结尾互动区用 👍👀📤 三个彩色 emoji；这里改用**同一套设计语言的细描边圆环 + 排版符号**，三个圆环共用同一种描边灰、同一种字符色（accent），整体感和印刷感明显强于三个各自带独立色彩的表情符号。

```html
<section style="margin:48px 0 0;padding:32px 0 0;border-top:1px solid #ECE4E1;text-align:center;">
  <p style="font-size:13px;color:#6E6764;line-height:1.7;margin:0 0 22px;">
    <span leaf="">如果这篇文章对你有用，点个赞、留个言，是对写作最好的鼓励。</span>
  </p>
  <section style="display:flex;justify-content:center;gap:28px;">
    <section style="text-align:center;">
      <span style="display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;border:1px solid #D8CFC9;color:#7A2E2E;font-size:13px;"><span leaf="">✓</span></span>
      <p style="font-size:11px;color:#A39C98;margin:8px 0 0;"><span leaf="">赞同</span></p>
    </section>
    <section style="text-align:center;">
      <span style="display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;border:1px solid #D8CFC9;color:#7A2E2E;font-size:12px;"><span leaf="">◎</span></span>
      <p style="font-size:11px;color:#A39C98;margin:8px 0 0;"><span leaf="">在看</span></p>
    </section>
    <section style="text-align:center;">
      <span style="display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;border:1px solid #D8CFC9;color:#7A2E2E;font-size:13px;"><span leaf="">↗</span></span>
      <p style="font-size:11px;color:#A39C98;margin:8px 0 0;"><span leaf="">转发</span></p>
    </section>
  </section>
</section>
```

**用到的字符只有 `✓`/`◎`/`↗`/`·`/`→` 这类通用 Unicode 排版符号**（不是 emoji，不需要 emoji 字体，各平台衬线/无衬线字体都自带，渲染稳定），配合细描边圆环统一色彩语言——这是"文字符号"技术（见 [visual-assets-guide.md](visual-assets-guide.md) 表格第三行）的进一步精修用法，不是新技术。

## 组件 14：作者签名区（末尾仅一处）

```html
<section style="margin:32px 0 0;padding:24px 0 0;text-align:center;">
  <p style="font-size:13px;color:#A39C98;line-height:1.8;margin:0;">
    <span leaf="">{{作者名}} · {{一句话简介，占位待替换}}</span>
  </p>
</section>
```

## 组件 15：深色导语封面区块（可选，仅用于需要仪式感开篇的文章类型）

> **默认不用**，组件 1（衬线大标题 + 图章式期号）仍是首选。这是 [common-components.md](common-components.md)「深色导语封面区块」的酌墨配色变体，且标题延续本主题"衬线大标题"的识别特征——如果只换了深色底却把标题换回无衬线，就丢掉了本主题最核心的辨识度。仅用于深度评论/年度总结/专栏合集这类需要"郑重开场"的文章类型，一篇文章只在最开头用一次，不与组件 1 同时出现。

```html
<section style="margin:0 0 40px;padding:52px 24px;border-radius:3px;background:linear-gradient(165deg,#1A1615 0%,#241E1D 100%);box-sizing:border-box;">
  <p style="margin:0 0 20px;text-align:center;font-size:11px;font-weight:700;letter-spacing:4px;color:#B87A7A;text-transform:uppercase;">
    <span leaf="">{{小标签，如"年度总结""专栏合集"}}</span>
  </p>
  <p style="margin:0 0 24px;text-align:center;font-size:24px;font-weight:700;line-height:1.45;letter-spacing:0.5px;color:#FBF8F6;font-family:&quot;Songti SC&quot;,&quot;STSong&quot;,&quot;SimSun&quot;,serif;">
    <span leaf="">{{文章标题，超过 18 字在语义断点处用 <br/> 分两行}}</span>
  </p>
  <p style="margin:0 auto;text-align:center;max-width:80%;font-size:12px;font-weight:500;line-height:1.6;color:#1C1A1A;background:#FBF8F6;padding:8px 18px;border-radius:20px;">
    <span leaf="">{{一句话副标题/摘要}}</span>
  </p>
</section>
```

（深色底用比正文更深一阶的暖近黑 `#1A1615→#241E1D`，圆角沿用本主题 2~3px 的直角化风格，不借用暖信笺的大圆角；标题保留衬线字体，这是三套变体里唯一延续"标题衬线/正文无衬线"对比结构的一处，其余两套主题的深色区块标题都是无衬线，不要混用；底部白色药丸换成 `page` 色 `#FBF8F6` 而不是纯白，全篇没有一处纯白色块；小标签用 accent 的浅色变体 `#B87A7A`，原理同另外两套主题——深色底上原色 `#7A2E2E` 不够醒目。）

---

## 完整文章模板骨架

```
组件1 文章头部
[组件2 导读]（3章节以上时生成）
循环：
  组件3 章节标题
  组件4 正文段落（组件7/9/10/11按内容需要插入，组件5引用/组件6金句全篇各只用1次）
组件12 分割线（可选，仅内容天然有大转折时插入）
组件13 结尾互动区
组件14 作者签名区
```

## 文章类型 → 组件组合配方

| 文章类型 | 核心组件 | 点缀组件（按需，不要堆） |
|---|---|---|
| 深度评论/书评影评/行业观察 | 组件1+3+4+6 | 组件5 引用（≤2处）、组件7 提示 |
| 访谈实录 | 组件1+2+3+4+5 | 组件9 图片 |
| 年度总结/复盘 | 组件1+2+3+4+11 | 组件9 图片、组件7 提示 |
| 教程/操作指南 | 组件1+2+3+4+10 | 组件8 代码块、组件9 图片 |

## Markdown → 组件映射规则表

| Markdown 元素 | 对应组件 |
|---|---|
| `# 标题` | 组件 1 |
| `## 章节` | 组件 3（大号，编号） |
| `### 子章节` | 组件 3（小节标题变体，不编号） |
| 开头 `> 引用` | 组件 1 副标题（一句话摘要）或组件 5（独立引言） |
| 正文 `> 引用` | 组件 5 |
| `**加粗**` | 组件 4 的"次要说明"变体 |
| `==高亮==` / 全文最重要的一句 | 组件 4 关键词强调（下划线）；全文最重要的一句用组件 6（仅一次） |
| 代码块 | 组件 8 |
| `![]()` | 组件 9 |
| 列表 | 组件 10 |
| 表格 | 组件 11 |
| `---` | 组件 12（仅内容有大转折时用） |

---

## Gotchas（本主题设计时刻意规避的坑）

- **不用彩色 emoji 做任何图标**：结尾互动区、分割线、图章角标全部用「细描边圆环 + 单色 Unicode 符号」，理由见组件 13 说明——这是本主题存在的核心原因之一，不要为了"省事"改回 emoji。
- **代码块顶栏不加三色圆点**：那是模仿终端截图的装饰，和克制配色体系冲突，只保留语言标签文字。
- **衬线字体只用在标题/引用/金句三处，不用于正文**：正文（组件 4）保持无衬线，两种字体的对比才是层级感的来源；如果正文也用衬线，反而会显得"整篇都很重"，失去对比。
- **衬线字体声明必须写四个候选值**（`"Songti SC","STSong","SimSun",serif`），不要只写一个，避免个别设备缺字导致标题掉回默认字体却没有兜底。
- **图章圆环统一用 `border.ring #D8CFC9` 描边、accent 色文字**，不要每处圆环换不同描边色，那样会失去"同一套图章语言"的统一感。
- **accent 全篇 ≤4 处**：金句卡（≤1次）+ 正文下划线强调（按段落克制使用）+ 结尾图章的 accent 字符不占额外配额（图章圆环描边用中性色，字符本身虽是 accent 但属于"结构性重复元素"里唯一的例外，因为三个图章共享统一语义，视觉上不构成"新的强调点"，登记在此供后续者理解，不要因为这条就随意扩大 accent 用量）。
- **不用虚线框、不用负字距**：与静纸同规则。
