# Themes：三套 Design Language 的完整组件与组合规则

**这是主题组件的唯一来源**。装配 HTML 时所有代码从这里取，不要手写、不要凭记忆、不要跨主题混用。

所有组件遵守平台红线（见 [platform-rules.md](platform-rules.md)）：内联 style、`<span leaf="">` 包裹所有文字、装饰空元素内放 `<span leaf=""><br></span>`、禁 `<div>/<style>/<script>/<svg>/class/id/position/float/grid`。

---

## 主题速选与 Design Token

| 主题 | 阅读人格 | 适用场景 | primary_text | secondary | muted | accent | page_bg | border |
|---|---|---|---|---|---|---|---|---|
| **静纸 Silent Paper** | 安静克制，Apple Journal × Kinfolk × Muji。留白驱动，几乎无卡片阴影 | 深度分析、观点、教程、复盘、通用默认 | `#232323` | `#6E6E6E` | `#9A9995` | `#6A7567` | `#F7F6F3`（引用）/ `#FCFBF9`（标签） | `#F0EEE9` |
| **暖信笺 Warm Letter** | 温暖叙事，像一封写给读者的信。允许暖色卡片+柔和阴影 | 人物故事、品牌故事、访谈、回忆录、生活随笔 | `#362A20` | `#7A6250` | `#A8927A` | `#B8583A` | `#F6EEE1`（卡片）/ `#EEE1CC`（边框） | `#EEE1CC` |
| **酌墨 Wine Ink** | 笃定有文人分量，像装帧讲究的评论集。衬线标题+图章式图标，无 emoji | 深度评论、书评影评、行业观察、年度总结、反 emoji 场景 | `#1C1A1A` | `#6E6764` | `#A39C98` | `#7A2E2E` | `#F2E7E3`（引用）/ `#F6EFEC`（表头） | `#ECE4E1` / `#D8CFC9`（图章描边） |

**字号阶梯（三套统一，6 级）**：

| Token | 字号 | 字重 | 行高 | 用途 |
|---|---|---|---|---|
| micro | 11px | 600 | 1.6 | 标签/编号/图注/署名，letter-spacing:1~1.5px |
| caption | 13px | 400 | 1.7~1.75 | 副标题/导读/提示旁注 |
| body | 15px | 400 | 1.9~1.95 | 正文 |
| quote | 16px | 500 | 1.8~1.85 | 引用块/金句（酌墨/静纸衬线或非） |
| h2 | 17~18px | 700 | 1.5 | 章节标题 |
| h1 | 22px | 700 | 1.4~1.5 | 文章大标题 |

**间距**：section_gap 40/44/40px，image_gap 32/34/32px，paragraph_gap 20/22/20px（静纸/暖信笺/酌墨）。

**accent 配额**：三套均 **全篇 ≤4 处**，用 `design_quality_check.py --accent '<hex>' --accent-quota 4` 核查。

**酌墨衬线字体**（仅大标题/引用/金句三处使用，正文保持无衬线）：`font-family:"Songti SC","STSong","SimSun",serif;`

---

## 一、静纸 Silent Paper 组件

> **纪律**：唯一的强调色是鼠尾草绿，全篇 ≤4 处；没有渐变（金句卡微渐变除外，深浅差仅 8 阶）、没有阴影卡片、没有多重描边。留白本身就是装饰。

### S1 文章头部
```html
<section style="padding:8px 4px 0;margin-bottom:8px;">
  <p style="font-size:11px;font-weight:600;letter-spacing:1.5px;color:#9A9995;margin:0 0 14px;text-transform:uppercase;">
    <span leaf="">{{英文分类标签，如 EDITORIAL}}</span>
  </p>
  <p style="font-size:22px;font-weight:700;color:#232323;line-height:1.4;margin:0 0 12px;letter-spacing:0;">
    <span leaf="">{{文章标题，超16字在语义断点用<br/>分两行}}</span>
  </p>
  <p style="font-size:13px;color:#6E6E6E;line-height:1.7;margin:0 0 20px;">
    <span leaf="">{{一句话副标题}}</span>
  </p>
  <section style="display:flex;align-items:center;gap:10px;">
    <span style="width:24px;height:1px;background:#9A9995;display:inline-block;"><span leaf=""><br></span></span>
    <span style="font-size:11px;color:#9A9995;letter-spacing:0.5px;"><span leaf="">{{日期}} · {{阅读时长}}</span></span>
  </section>
</section>
<section style="height:1px;background:#F0EEE9;margin:24px 0 0;"><span leaf=""><br></span></section>
```

### S2 导读（≥3 章节时生成，紧跟头部）
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

### S3 章节标题
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
小节（`###`，不编号）：
```html
<p style="font-size:15px;font-weight:700;color:#232323;line-height:1.6;margin:28px 0 12px;">
  <span leaf="">{{小节标题}}</span>
</p>
```

### S4 正文段落 + 关键词下划线
```html
<p style="font-size:15px;color:#232323;line-height:1.9;margin:0 0 20px;text-align:justify;">
  <span leaf="">前文，</span><span style="border-bottom:1px solid #6A7567;padding-bottom:1px;"><span leaf="">关键词</span></span><span leaf="">后文。</span>
</p>
```
次要说明（专有名词，不占 accent 配额）：
```html
<p style="font-size:15px;color:#232323;line-height:1.9;margin:0 0 20px;text-align:justify;">
  <span leaf="">提到 </span><strong style="color:#6E6E6E;font-weight:600;"><span leaf="">专有名词</span></strong><span leaf=""> 用字重区分。</span>
</p>
```

### S5 引用块（居中）
```html
<section style="margin:36px 0;padding:28px 24px;background:#F7F6F3;border-radius:4px;text-align:center;">
  <p style="font-size:16px;color:#232323;line-height:1.8;margin:0;font-weight:500;">
    <span leaf="">{{引用，一句话，不超两行}}</span>
  </p>
  <p style="font-size:11px;color:#9A9995;margin:14px 0 0;">
    <span leaf="">—— {{来源，无则删此行}}</span>
  </p>
</section>
```

### S6 金句卡（全篇 ≤1 次，视觉高潮）
```html
<section style="margin:36px 0;padding:32px 24px;background:linear-gradient(160deg,#232323 0%,#2B2B2B 100%);border-radius:6px;text-align:center;">
  <p style="font-size:17px;color:#FFFFFF;line-height:1.7;margin:0;font-weight:500;">
    <span leaf="">{{Core Claim，全文最核心的一句话}}</span>
  </p>
</section>
```

### S7 提示/旁注（左侧细线，无底色）
```html
<section style="margin:0 0 20px;padding:2px 0 2px 16px;border-left:2px solid #9A9995;">
  <p style="font-size:13px;color:#6E6E6E;line-height:1.7;margin:0;">
    <span leaf="">{{提示或补充说明}}</span>
  </p>
</section>
```

### S9 图片 + 说明
```html
<section style="margin:32px 0;">
  <img src="{{图片URL}}" style="max-width:100%;height:auto;display:block;margin:0 auto;border-radius:4px;" />
  <p style="font-size:11px;color:#9A9995;text-align:center;margin:10px 0 0;line-height:1.6;">
    <span leaf="">{{图片说明，无则删整段}}</span>
  </p>
</section>
```

### S10 列表
```html
<section style="margin:0 0 20px;">
  <section style="display:flex;margin-bottom:10px;">
    <span style="flex-shrink:0;width:16px;color:#9A9995;font-size:15px;line-height:1.9;"><span leaf="">·</span></span>
    <p style="font-size:15px;color:#232323;line-height:1.9;margin:0;flex:1;"><span leaf="">{{列表项}}</span></p>
  </section>
</section>
```
有序列表把 `·` 换成 `01` `02`（muted 色，11px）。

### S11 表格替代（卡片化）
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

### S12 分割线（仅内容有大转折时用）
```html
<section style="margin:36px 0;text-align:center;">
  <span style="font-size:13px;color:#9A9995;letter-spacing:6px;"><span leaf="">· · ·</span></span>
</section>
```

### S13 结尾互动区
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

### S14 作者签名区
```html
<section style="margin:32px 0 0;padding:24px 0 0;text-align:center;">
  <p style="font-size:13px;color:#9A9995;line-height:1.8;margin:0;">
    <span leaf="">{{作者名}} · {{一句话简介}}</span>
  </p>
</section>
```

### 静纸文章骨架
```
S1 头部 → [S2 导读（≥3章）] → 循环（S3 章节 → S4 正文穿插 S7/S9/S10/S11，S5/S6 各≤1-2次/1次） → [S12 分割线] → S13 互动 → S14 签名
```

### 静纸配方表

| 文章类型 | 核心组件 | 点缀 |
|---|---|---|
| 深度分析/观点 | S1+S3+S4+S6 | S5引用≤2、S7提示 |
| 教程/操作指南 | S1+S2+S3+S4+S10 | 代码块(共享)、S9图片 |
| 生活方式/随笔 | S1+S4+S5 | S6金句≤1、S9图片 |
| 数据/案例复盘 | S1+S2+S3+S4+S11 | S9图片、S7提示 |

---

## 二、暖信笺 Warm Letter 组件

> **纪律**：温暖但不软化一切——大圆角、暖色阴影只用在少数需要情绪停顿的容器（图片、金句卡），正文排版依然克制。全篇没有纯白色块（卡片底/药丸用 `#F6EEE1` 暖米色）。

### W1 封面头图（信笺式）
```html
<section style="padding:12px 4px 0;margin-bottom:8px;">
  <p style="font-size:13px;color:#7A6250;line-height:1.8;margin:0 0 16px;font-style:italic;">
    <span leaf="">{{一句引导语，如"写给还在寻找答案的你"}}</span>
  </p>
  <p style="font-size:22px;font-weight:700;color:#362A20;line-height:1.5;margin:0 0 14px;letter-spacing:0;">
    <span leaf="">{{标题，超16字语义断行<br/>}}</span>
  </p>
  <p style="font-size:13px;color:#7A6250;line-height:1.75;margin:0 0 22px;">
    <span leaf="">{{一句话副标题}}</span>
  </p>
  <section style="display:flex;align-items:center;gap:10px;">
    <span style="width:20px;height:1px;background:#C7AF8F;display:inline-block;"><span leaf=""><br></span></span>
    <span style="font-size:11px;color:#A8927A;letter-spacing:0.5px;"><span leaf="">{{日期}} · {{阅读时长}}</span></span>
  </section>
</section>
<section style="height:1px;background:#EEE1CC;margin:26px 0 0;"><span leaf=""><br></span></section>
```

### W2 导读（≥3 章节，信纸边栏式）
```html
<section style="margin:32px 0;padding:22px 20px;border:1px solid #EEE1CC;border-radius:14px;">
  <p style="font-size:11px;font-weight:600;letter-spacing:1px;color:#A8927A;margin:0 0 14px;">
    <span leaf="">这篇文章想和你聊聊</span>
  </p>
  <p style="font-size:13px;color:#362A20;line-height:2.1;margin:0;">
    <span leaf="">— {{看点一}}</span><br/>
    <span leaf="">— {{看点二}}</span><br/>
    <span leaf="">— {{看点三}}</span>
  </p>
</section>
```

### W3 章节标题（手记式小圆点）
```html
<section style="margin:44px 0 20px;display:flex;align-items:center;gap:10px;">
  <span style="width:6px;height:6px;border-radius:50%;background:#A8927A;display:inline-block;flex-shrink:0;"><span leaf=""><br></span></span>
  <p style="font-size:18px;font-weight:700;color:#362A20;line-height:1.5;margin:0;">
    <span leaf="">{{章节标题}}</span>
  </p>
</section>
```
小节（`###`，斜体，和正文同号靠字重+斜体区分）：
```html
<p style="font-size:15px;font-weight:700;font-style:italic;color:#362A20;line-height:1.6;margin:26px 0 12px;">
  <span leaf="">{{小节标题}}</span>
</p>
```

### W4 正文段落 + 关键词下划线
```html
<p style="font-size:15px;color:#362A20;line-height:1.95;margin:0 0 22px;text-align:justify;">
  <span leaf="">前文，</span><span style="border-bottom:1px solid #B8583A;padding-bottom:1px;"><span leaf="">关键词</span></span><span leaf="">后文。</span>
</p>
```
次要说明：
```html
<p style="font-size:15px;color:#362A20;line-height:1.95;margin:0 0 22px;text-align:justify;">
  <span leaf="">提到 </span><strong style="color:#7A6250;font-weight:600;"><span leaf="">专有名词</span></strong><span leaf="">，用字重区分。</span>
</p>
```

### W5 情绪停顿句（独立短句，节奏停顿，不占 accent 配额）
```html
<p style="font-size:17px;color:#362A20;line-height:1.7;margin:32px 0;text-align:center;font-weight:500;">
  <span leaf="">{{一句独立短句，作为段落间停顿}}</span>
</p>
```

### W6 引用块（温暖底色居中）
```html
<section style="margin:36px 0;padding:28px 24px;background:#F6EEE1;border-radius:16px;text-align:center;">
  <p style="font-size:17px;color:#362A20;line-height:1.85;margin:0;font-weight:500;">
    <span leaf="">{{引用，一句话不超两行}}</span>
  </p>
  <p style="font-size:11px;color:#A8927A;margin:14px 0 0;">
    <span leaf="">—— {{来源，无则删}}</span>
  </p>
</section>
```

### W7 金句卡（全篇 ≤1 次，赤陶色实底+暖色阴影）
```html
<section style="margin:36px 0;padding:34px 24px;background:linear-gradient(160deg,#B8583A 0%,#A34B2F 100%);border-radius:18px;text-align:center;box-shadow:0 16px 40px rgba(184,88,58,.16);">
  <p style="font-size:17px;color:#FFFFFF;line-height:1.75;margin:0;font-weight:500;">
    <span leaf="">{{Core Claim}}</span>
  </p>
</section>
```

### W8 人物证言卡（当事人原话）
```html
<section style="margin:36px 0;padding:26px 22px;border:1px solid #EEE1CC;border-radius:16px;">
  <p style="font-size:15px;color:#362A20;line-height:1.85;margin:0 0 16px;font-style:italic;">
    <span leaf="">"{{当事人原话，一到两句}}"</span>
  </p>
  <section style="display:flex;align-items:center;gap:10px;">
    <span style="width:28px;height:28px;border-radius:50%;background:#F6EEE1;display:inline-block;"><span leaf=""><br></span></span>
    <p style="font-size:11px;color:#7A6250;margin:0;"><span leaf="">{{姓名}} · {{身份}}</span></p>
  </section>
</section>
```

### W9 提示/旁注
```html
<section style="margin:0 0 22px;padding:2px 0 2px 16px;border-left:2px solid #C7AF8F;">
  <p style="font-size:13px;color:#7A6250;line-height:1.75;margin:0;">
    <span leaf="">{{提示内容}}</span>
  </p>
</section>
```

### W11 图片 + 说明（带暖色空气感阴影）
```html
<section style="margin:34px 0;">
  <section style="border-radius:16px;overflow:hidden;box-shadow:0 20px 44px rgba(58,46,36,.08);">
    <img src="{{图片URL}}" style="max-width:100%;height:auto;display:block;margin:0 auto;" />
  </section>
  <p style="font-size:11px;color:#A8927A;text-align:center;margin:12px 0 0;line-height:1.6;">
    <span leaf="">{{图片说明，无则删}}</span>
  </p>
</section>
```

### W12 双图对比
```html
<section style="margin:34px 0;">
  <section style="border-radius:16px;overflow:hidden;margin-bottom:10px;">
    <img src="{{图一URL}}" style="max-width:100%;height:auto;display:block;margin:0 auto;" />
  </section>
  <p style="font-size:11px;color:#A8927A;text-align:center;margin:0 0 24px;line-height:1.6;"><span leaf="">{{图一说明}}</span></p>
  <section style="border-radius:16px;overflow:hidden;margin-bottom:10px;">
    <img src="{{图二URL}}" style="max-width:100%;height:auto;display:block;margin:0 auto;" />
  </section>
  <p style="font-size:11px;color:#A8927A;text-align:center;margin:0;line-height:1.6;"><span leaf="">{{图二说明}}</span></p>
</section>
```

### W13 列表
```html
<section style="margin:0 0 22px;">
  <section style="display:flex;margin-bottom:12px;">
    <span style="flex-shrink:0;width:16px;color:#A8927A;font-size:15px;line-height:1.95;"><span leaf="">·</span></span>
    <p style="font-size:15px;color:#362A20;line-height:1.95;margin:0;flex:1;"><span leaf="">{{列表项}}</span></p>
  </section>
</section>
```

### W14 岁月时间线（回忆录/故事类，竖线用 flex 不用绝对定位）
```html
<section style="margin:0 0 4px;">
  <section style="display:flex;">
    <section style="width:20px;flex-shrink:0;display:flex;flex-direction:column;align-items:center;">
      <span style="width:8px;height:8px;border-radius:50%;background:#A8927A;display:inline-block;flex-shrink:0;"><span leaf=""><br></span></span>
      <span style="width:1px;flex:1;background:#EEE1CC;min-height:36px;display:inline-block;"><span leaf=""><br></span></span>
    </section>
    <section style="flex:1;padding:0 0 26px 16px;">
      <p style="font-size:11px;font-weight:600;letter-spacing:1px;color:#A8927A;margin:0 0 6px;"><span leaf="">{{年份/时间点}}</span></p>
      <p style="font-size:15px;color:#362A20;line-height:1.85;margin:0;"><span leaf="">{{事件}}</span></p>
    </section>
  </section>
</section>
```
> 注意：时间线连续多节点的竖线连续性在真实公众号客户端未经系统性验证，首次使用建议发真实预览确认。

### W15 关系数据摘要卡（数字服务于情绪，不是说服力；一次用 3 个数字会占满 accent 配额，不要再叠金句卡）
```html
<section style="margin:34px 0;display:flex;justify-content:space-between;text-align:center;">
  <section>
    <p style="font-size:18px;font-weight:700;color:#B8583A;margin:0 0 6px;"><span leaf="">{{数字一}}</span></p>
    <p style="font-size:11px;color:#A8927A;margin:0;"><span leaf="">{{数字一说明}}</span></p>
  </section>
  <section>
    <p style="font-size:18px;font-weight:700;color:#B8583A;margin:0 0 6px;"><span leaf="">{{数字二}}</span></p>
    <p style="font-size:11px;color:#A8927A;margin:0;"><span leaf="">{{数字二说明}}</span></p>
  </section>
  <section>
    <p style="font-size:18px;font-weight:700;color:#B8583A;margin:0 0 6px;"><span leaf="">{{数字三}}</span></p>
    <p style="font-size:11px;color:#A8927A;margin:0;"><span leaf="">{{数字三说明}}</span></p>
  </section>
</section>
```

### W16 表格替代
```html
<section style="margin:0 0 22px;border:1px solid #EEE1CC;border-radius:14px;overflow:hidden;">
  <section style="display:flex;padding:12px 16px;background:#F6EEE1;">
    <p style="flex:1;font-size:11px;font-weight:600;color:#7A6250;margin:0;"><span leaf="">{{列一}}</span></p>
    <p style="flex:1;font-size:11px;font-weight:600;color:#7A6250;margin:0;"><span leaf="">{{列二}}</span></p>
  </section>
  <section style="display:flex;padding:12px 16px;border-top:1px solid #EEE1CC;">
    <p style="flex:1;font-size:13px;color:#362A20;margin:0;"><span leaf="">{{值一}}</span></p>
    <p style="flex:1;font-size:13px;color:#362A20;margin:0;"><span leaf="">{{值二}}</span></p>
  </section>
</section>
```

### W17 分割线（心形）
```html
<section style="margin:36px 0;text-align:center;">
  <span style="font-size:11px;color:#C7AF8F;letter-spacing:8px;"><span leaf="">♡</span></span>
</section>
```

### W18 关注引导（可选，语气像朋友不是营销号）
```html
<section style="margin:36px 0;padding:26px 22px;background:#F6EEE1;border-radius:16px;text-align:center;">
  <p style="font-size:15px;color:#362A20;line-height:1.8;margin:0;">
    <span leaf="">{{邀请读者持续阅读的话}}</span>
  </p>
</section>
```

### W19 结尾互动区
```html
<section style="margin:48px 0 0;padding:32px 0 0;border-top:1px solid #EEE1CC;text-align:center;">
  <p style="font-size:13px;color:#7A6250;line-height:1.75;margin:0 0 20px;">
    <span leaf="">如果这篇文章让你想起点什么，点个赞、留句话，我会看见。</span>
  </p>
  <section style="display:flex;justify-content:center;gap:32px;">
    <section style="text-align:center;">
      <span style="font-size:17px;line-height:1;"><span leaf="">🤍</span></span>
      <p style="font-size:11px;color:#A8927A;margin:6px 0 0;"><span leaf="">点赞</span></p>
    </section>
    <section style="text-align:center;">
      <span style="font-size:17px;line-height:1;"><span leaf="">👀</span></span>
      <p style="font-size:11px;color:#A8927A;margin:6px 0 0;"><span leaf="">在看</span></p>
    </section>
    <section style="text-align:center;">
      <span style="font-size:17px;line-height:1;"><span leaf="">📮</span></span>
      <p style="font-size:11px;color:#A8927A;margin:6px 0 0;"><span leaf="">转发</span></p>
    </section>
  </section>
</section>
```

### W20 延伸阅读（可选）
```html
<section style="margin:28px 0 0;padding:20px 0 0;border-top:1px solid #EEE1CC;">
  <p style="font-size:11px;font-weight:600;letter-spacing:1px;color:#A8927A;margin:0 0 12px;">
    <span leaf="">如果还想接着读</span>
  </p>
  <p style="font-size:13px;color:#362A20;line-height:2;margin:0;">
    <span leaf="">— {{延伸一}}</span><br/>
    <span leaf="">— {{延伸二}}</span>
  </p>
</section>
```

### W21 作者签名区
```html
<section style="margin:32px 0 0;padding:24px 0 0;text-align:center;">
  <p style="font-size:13px;color:#A8927A;line-height:1.8;margin:0;">
    <span leaf="">{{作者名}} · {{一句话简介}}</span>
  </p>
</section>
```

### 暖信笺文章骨架
```
W1 封面头图 → [W2 导读] → 循环（W3 章节 → W4 正文穿插 W5/W6/W8/W9/W11/W13/W14/W15，W7金句≤1次） → [W17 分割线] → [W18 关注引导] → W19 互动 → [W20 延伸阅读] → W21 签名
```

### 暖信笺配方表

| 文章类型 | 核心组件 | 点缀 |
|---|---|---|
| 人物故事/访谈 | W1+W3+W4+W8 | W6引用、W7金句≤1、W11图片 |
| 品牌故事 | W1+W3+W4+W15 | W7金句、W18 CTA、W11图片 |
| 回忆录/岁月记事 | W1+W3+W4+W14 | W12双图、W5情绪停顿 |
| 生活方式/随笔 | W1+W4+W6 | W7金句≤1、W11图片、W17分割线 |

---

## 三、酌墨 Wine Ink 组件

> **纪律**：衬线字体只用在大标题/引用/金句三处，正文保持无衬线；全篇无彩色 emoji，统一「细描边圆环+Unicode 排版符号」（`✓` `◎` `↗` `·`），图章圆环描边用 `#D8CFC9` 中性色、字符用 accent 色；代码块顶栏去掉 macOS 三色圆点（廉价感），只保留语言标签。

酌墨衬线声明：`font-family:&quot;Songti SC&quot;,&quot;STSong&quot;,&quot;SimSun&quot;,serif;`（四个候选值缺一不可，防个别设备缺字）

### K1 文章头部（衬线大标题+图章期号）
```html
<section style="padding:8px 4px 0;margin-bottom:8px;">
  <section style="display:flex;align-items:center;gap:8px;margin-bottom:16px;">
    <span style="display:inline-flex;align-items:center;justify-content:center;width:22px;height:22px;border-radius:50%;border:1px solid #1C1A1A;color:#1C1A1A;font-size:11px;font-weight:700;"><span leaf="">酌</span></span>
    <span style="font-size:11px;font-weight:600;letter-spacing:1.5px;color:#A39C98;text-transform:uppercase;"><span leaf="">{{标签，如 REVIEW}}</span></span>
  </section>
  <p style="font-size:22px;font-weight:700;color:#1C1A1A;line-height:1.45;margin:0 0 12px;letter-spacing:0.5px;font-family:&quot;Songti SC&quot;,&quot;STSong&quot;,&quot;SimSun&quot;,serif;">
    <span leaf="">{{标题，超16字语义断行<br/>}}</span>
  </p>
  <p style="font-size:13px;color:#6E6764;line-height:1.7;margin:0 0 20px;">
    <span leaf="">{{一句话副标题}}</span>
  </p>
  <section style="display:flex;align-items:center;gap:10px;">
    <span style="width:24px;height:1px;background:#D8CFC9;display:inline-block;"><span leaf=""><br></span></span>
    <span style="font-size:11px;color:#A39C98;letter-spacing:0.5px;"><span leaf="">{{日期}} · {{阅读时长}}</span></span>
  </section>
</section>
<section style="height:1px;background:#ECE4E1;margin:24px 0 0;"><span leaf=""><br></span></section>
```
> 图章单字默认"酌"，可按专栏名换（"评"/"记"等），起期刊 Logo 角标作用。图章用 primary_text 色不用 accent（是品牌角标不是内容强调点）。

### K2 导读（≥3 章节）
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

### K3 章节标题（无衬线，与衬线大标题对比）
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
小节：
```html
<p style="font-size:15px;font-weight:700;color:#1C1A1A;line-height:1.6;margin:28px 0 12px;">
  <span leaf="">{{小节标题}}</span>
</p>
```

### K4 正文段落 + 关键词下划线
```html
<p style="font-size:15px;color:#1C1A1A;line-height:1.9;margin:0 0 20px;text-align:justify;">
  <span leaf="">前文，</span><span style="border-bottom:1px solid #7A2E2E;padding-bottom:1px;"><span leaf="">关键词</span></span><span leaf="">后文。</span>
</p>
```
次要说明：
```html
<p style="font-size:15px;color:#1C1A1A;line-height:1.9;margin:0 0 20px;text-align:justify;">
  <span leaf="">提到 </span><strong style="color:#6E6764;font-weight:600;"><span leaf="">专有名词</span></strong><span leaf="">，用字重区分。</span>
</p>
```

### K5 引用块（衬线摘录体，制造"引文"印刷感）
```html
<section style="margin:36px 0;padding:28px 24px;background:#F2E7E3;border-radius:2px;text-align:center;">
  <p style="font-size:16px;color:#1C1A1A;line-height:1.85;margin:0;font-weight:500;font-family:&quot;Songti SC&quot;,&quot;STSong&quot;,&quot;SimSun&quot;,serif;">
    <span leaf="">「{{引用，一句话不超两行}}」</span>
  </p>
  <p style="font-size:11px;color:#A39C98;margin:14px 0 0;">
    <span leaf="">—— {{来源，无则删}}</span>
  </p>
</section>
```

### K6 金句卡（全篇 ≤1 次，衬线+深色底）
```html
<section style="margin:36px 0;padding:32px 24px;background:linear-gradient(160deg,#1C1A1A 0%,#272322 100%);border-radius:3px;text-align:center;">
  <p style="font-size:17px;color:#FBF8F6;line-height:1.75;margin:0;font-weight:500;font-family:&quot;Songti SC&quot;,&quot;STSong&quot;,&quot;SimSun&quot;,serif;">
    <span leaf="">「{{Core Claim}}」</span>
  </p>
</section>
```

### K7 提示/旁注
```html
<section style="margin:0 0 20px;padding:2px 0 2px 16px;border-left:2px solid #A39C98;">
  <p style="font-size:13px;color:#6E6764;line-height:1.7;margin:0;">
    <span leaf="">{{提示内容}}</span>
  </p>
</section>
```

### K8 代码块（去掉 macOS 三色圆点，只保留语言标签）
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

### K9 图片 + 说明
```html
<section style="margin:32px 0;">
  <img src="{{图片URL}}" style="max-width:100%;height:auto;display:block;margin:0 auto;border-radius:2px;" />
  <p style="font-size:11px;color:#A39C98;text-align:center;margin:10px 0 0;line-height:1.6;">
    <span leaf="">{{图片说明，无则删}}</span>
  </p>
</section>
```

### K10 列表
```html
<section style="margin:0 0 20px;">
  <section style="display:flex;margin-bottom:10px;">
    <span style="flex-shrink:0;width:16px;color:#A39C98;font-size:15px;line-height:1.9;"><span leaf="">·</span></span>
    <p style="font-size:15px;color:#1C1A1A;line-height:1.9;margin:0;flex:1;"><span leaf="">{{列表项}}</span></p>
  </section>
</section>
```
有序列表 `·`→`01` `02`（muted 色，11px）。

### K11 表格替代
```html
<section style="margin:0 0 20px;border:1px solid #ECE4E1;border-radius:4px;overflow:hidden;">
  <section style="display:flex;padding:12px 16px;background:#F6EFEC;">
    <p style="flex:1;font-size:11px;font-weight:600;color:#6E6764;margin:0;"><span leaf="">{{列一}}</span></p>
    <p style="flex:1;font-size:11px;font-weight:600;color:#6E6764;margin:0;"><span leaf="">{{列二}}</span></p>
  </section>
  <section style="display:flex;padding:12px 16px;border-top:1px solid #ECE4E1;">
    <p style="flex:1;font-size:13px;color:#1C1A1A;margin:0;"><span leaf="">{{值一}}</span></p>
    <p style="flex:1;font-size:13px;color:#1C1A1A;margin:0;"><span leaf="">{{值二}}</span></p>
  </section>
</section>
```

### K12 分割线（图章式圆环）
```html
<section style="margin:36px 0;text-align:center;">
  <span style="display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;border:1px solid #D8CFC9;color:#A39C98;font-size:10px;"><span leaf="">·</span></span>
</section>
```

### K13 结尾互动区（图章式圆环，无 emoji）
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
      <span style="display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;border:1px solid #D8CFC9;color:#A39C98;font-size:12px;"><span leaf="">◎</span></span>
      <p style="font-size:11px;color:#A39C98;margin:8px 0 0;"><span leaf="">在看</span></p>
    </section>
    <section style="text-align:center;">
      <span style="display:inline-flex;align-items:center;justify-content:center;width:32px;height:32px;border-radius:50%;border:1px solid #D8CFC9;color:#A39C98;font-size:13px;"><span leaf="">↗</span></span>
      <p style="font-size:11px;color:#A39C98;margin:8px 0 0;"><span leaf="">转发</span></p>
    </section>
  </section>
</section>
```
> 三个图章只有"赞同"用 accent，其余两个用 muted——控制 accent 配额。

### K14 作者签名区
```html
<section style="margin:32px 0 0;padding:24px 0 0;text-align:center;">
  <p style="font-size:13px;color:#A39C98;line-height:1.8;margin:0;">
    <span leaf="">{{作者名}} · {{一句话简介}}</span>
  </p>
</section>
```

### 酌墨文章骨架
```
K1 头部 → [K2 导读] → 循环（K3 章节 → K4 正文穿插 K7/K9/K10/K11，K5/K6 各≤1-2次/1次） → [K12 分割线] → K13 互动 → K14 签名
```

### 酌墨配方表

| 文章类型 | 核心组件 | 点缀 |
|---|---|---|
| 深度评论/书评/行业观察 | K1+K3+K4+K6 | K5引用≤2、K7提示 |
| 访谈实录 | K1+K2+K3+K4+K5 | K9图片 |
| 年度总结/复盘 | K1+K2+K3+K4+K11 | K9图片、K7提示 |
| 教程/操作指南 | K1+K2+K3+K4+K10 | K8代码块、K9图片 |

---

## 四、共享组件（三套通用，按主题换色）

### 代码块

**深色代码块（默认，适配所有主题；酌墨去掉顶栏三色圆点，见 K8）**：
```html
<section style="margin:0 0 20px;border-radius:8px;overflow:hidden;background:#1E293B;box-shadow:0 4px 16px -8px rgba(15,23,42,0.4);">
  <section style="display:flex;align-items:center;padding:9px 14px;background:#0F172A;">
    <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#FF5F56;margin-right:7px;font-size:0;line-height:0;overflow:hidden;"><span leaf="">.</span></span>
    <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#FFBD2E;margin-right:7px;font-size:0;line-height:0;overflow:hidden;"><span leaf="">.</span></span>
    <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:#27C93F;margin-right:7px;font-size:0;line-height:0;overflow:hidden;"><span leaf="">.</span></span>
    <span style="margin-left:12px;font-size:12px;color:#64748B;font-family:Consolas,Monaco,monospace;letter-spacing:1px;"><span leaf="">python</span></span>
  </section>
  <section style="padding:11px 14px;">
    <p style="margin:0;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:13px;line-height:1.6;color:#E2E8F0;"><span leaf="">{{代码行}}</span></p>
  </section>
</section>
```

**浅色代码块**（暖信笺使用，左竖条换 accent）：
```html
<section style="margin:0 0 20px;border-radius:8px;overflow:hidden;background:#F6F8FA;border:1px solid #E5E7EB;border-left:3px solid {{ACCENT}};">
  <section style="padding:7px 14px;border-bottom:1px solid #E5E7EB;">
    <span style="font-size:12px;color:#9CA3AF;font-family:Consolas,Monaco,monospace;letter-spacing:1px;"><span leaf="">bash</span></span>
  </section>
  <section style="padding:11px 14px;">
    <p style="margin:0;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:13px;line-height:1.6;color:#24292F;"><span leaf="">{{代码行}}</span></p>
  </section>
</section>
```

**代码块纪律**：每行代码一个 `<p style="margin:0">`，**禁用 `white-space:pre`**；缩进用全角空格 `　`；无语言可删语言标签 span。

**行内代码**：
```html
<span style="background:#F1F5F9;color:{{ACCENT}};padding:1px 6px;border-radius:4px;font-family:'SF Mono',Consolas,Monaco,monospace;font-size:14px;"><span leaf="">{{code}}</span></span>
```

### GIF 动图（同图片组件，加"GIF 动图"角标）
在所用主题的图片组件基础上，图注前加角标：
```html
<span style="display:inline-block;background:{{浅底}};color:{{深字}};font-size:11px;font-weight:700;padding:1px 8px;border-radius:4px;margin-right:6px;"><span leaf="">GIF 动图</span></span>
```

### 待补素材占位（唯一允许虚线框的场景，居中）
```html
<section style="margin:0 0 24px;padding:30px 20px;border:1.5px dashed #DAD7D2;border-radius:14px;background:#FAFAF8;text-align:center;">
  <p style="margin:0 0 10px;font-size:26px;line-height:1;"><span leaf="">🎬</span></p>
  <p style="margin:0;font-size:14px;font-weight:700;color:#9CA3AF;letter-spacing:1px;"><span leaf="">待补素材</span></p>
  <p style="margin:8px 0 0;font-size:13px;color:#B8B5B0;line-height:1.7;"><span leaf="">此处插入：{{说明}}</span></p>
</section>
```
图标：🎬 视频/录屏、🖼 图片、📊 信息图、📎 附件。

### 深色导语封面区块（可选，仅深度报道/年度总结/专栏合集需郑重开场时使用，**替代而非叠加**各主题的头部组件）

三套主题各有配色变体，骨架一致：
```html
<section style="margin:0 0 40px;padding:52px 24px;border-radius:{{RADIUS}};background:linear-gradient(165deg,{{DARK1}} 0%,{{DARK2}} 100%);box-sizing:border-box;">
  <p style="margin:0 0 20px;text-align:center;font-size:11px;font-weight:700;letter-spacing:4px;color:{{ACCENT_LIGHT}};text-transform:uppercase;">
    <span leaf="">{{小标签}}</span>
  </p>
  <p style="margin:0 0 24px;text-align:center;font-size:24px;font-weight:700;line-height:{{HLINE}};color:#FFFFFF;{{SERIF}}">
    <span leaf="">{{标题，超18字语义断行<br/>}}</span>
  </p>
  <p style="margin:0 auto;text-align:center;max-width:80%;font-size:12px;font-weight:500;line-height:1.6;color:{{DARK1}};background:{{PILL_BG}};padding:8px 18px;border-radius:20px;">
    <span leaf="">{{一句话副标题}}</span>
  </p>
</section>
```

| 主题 | RADIUS | DARK1→DARK2 | ACCENT_LIGHT | HLINE | SERIF | PILL_BG |
|---|---|---|---|---|---|---|
| 静纸 | 6px | `#1E1E1E→#272727` | `#8FA88A` | 1.4 | （空） | `#FFFFFF` |
| 暖信笺 | 18px | `#2B2118→#362A20` | `#D89B7C` | 1.5 | （空） | `#F6EEE1` |
| 酌墨 | 3px | `#1A1615→#241E1D` | `#B87A7A` | 1.45 | `font-family:&quot;Songti SC&quot;,&quot;STSong&quot;,&quot;SimSun&quot;,serif;` | `#FBF8F6` |

---

## Markdown → 组件映射（所有主题通用，主题库内有专属组件时优先用专属）

| Markdown 元素 | 映射 |
|---|---|
| `# 标题` | 主题的头部组件 |
| `## 章节` | 主题的章节标题（带编号/圆点） |
| `### 子章节` | 主题的小节标题变体 |
| 开头 `> 引用` | 头部副标题（一句话摘要）或引用组件（独立引言） |
| 正文 `> 引用` | 主题引用组件（人物原话用暖信笺W8证言卡） |
| `**加粗**` | 次要说明 `<strong>`（次要色字重600，不占 accent） |
| `==高亮==` / 核心结论 | accent 下划线；全文最核心一句→金句卡（全篇≤1） |
| 代码块 | 深色/浅色代码块（按主题） |
| 行内 `` `code` `` | 行内代码组件 |
| `![]()` | 主题图片组件；GIF 加动图角标；连续两图对照→暖信笺W12 |
| 列表 | 主题列表组件；时间/年份线索明显→暖信笺W14 |
| 表格 | 主题表格替代组件 |
| `---` | 主题分割线（仅大转折时用，不逢 `---` 必用） |
| `【插入xxx】`占位 | 待补素材占位 |

## 平台 Gotchas（装配时刻记住）

- 漏 `<span leaf="">` 是最常见致命错，validate 脚本兜底。
- 装饰性空元素（分割线/留白占位/细线 span）**内部必须放** `<span leaf=""><br></span>`。
- emoji 不要单独套 `line-height`（不同 emoji 字体 ascent/descent 不同，会导致行高不一致）——直接跟在 `<span leaf="">` 包裹的文字里用同一 line-height。
- 下划线逐段落实，每段 1-2 处，不整段划线也不漏段。
- 章节编号严格按 `##` 顺序，结语变体只用于末章。
- 签名区有且仅有末尾一处；原文已有签名则并入，不重复生成。
- 图片 `max-width:100%;height:auto;display:block;margin:0 auto`，不用 `width:100%`。
- 一篇文章不跨主题混用组件；锚点层 ≤4 处；不遗漏原文段落/图片；占位图无真实 URL 时整行删除；导读只挑 3 个精选看点。
- 中文标点全角，代码/英文专名/URL 内部保持原样；生成时直接写弯引号，不要先写直引号再替换。
