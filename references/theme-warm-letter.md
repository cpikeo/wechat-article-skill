# 公众号排版组件库 —— 暖信笺（Warm Letter）

> **本 Skill 第二套完整主题**，与「静纸（Silent Paper）」共存，不替代它。两者的设计语言定位刻意拉开差异（对照 [editorial-identity.md](editorial-identity.md) 第八节的 9 维速查表）：静纸是 Weight 低、Contrast 低、Temperature 中性偏暖的"克制阅读"；暖信笺是 Weight 中、Contrast 低、Temperature 暖、Distance 更近的"温暖叙事"——大留白保留，但允许卡片圆角更大、允许极少量暖色调阴影，语气从"安静克制"换成"像一封写给读者的信"。

> **阅读人格**：温暖、感性、有呼吸感的叙事。适合人物故事、品牌故事、访谈、回忆录、生活方式类内容——**不适合**强逻辑的深度分析/教程类内容（那类请仍用静纸或按需再设计一套结构化主题）。**唯一的设计纪律**：卡片圆角、暖色阴影、心形分隔符这些"更有温度"的手法，都只用在少数几个真正需要情绪停顿的地方，不是每个组件都要软化——温暖不等于到处都软。

> **技术性说明（避免误解）**：本主题描述里的"暖色调大留白背景"指的是卡片/引用块这些**局部容器**的暖色底（如 `#F6EEE1`），不是整篇文章的页面背景色——公众号正文是粘贴进编辑器画布里的一段内容片段，编辑器画布本身是白色的（用户主题不深色模式的情况下），没有办法覆盖成暖色全屏背景，这一点和静纸主题的情况完全一样，不是本主题独有的限制。

> **使用说明**：所有组件使用**内联样式**，可直接复制粘贴到微信公众号编辑器。

> **公众号平台限制须知**（和静纸主题完全一致，见 SKILL.md「平台红线」）：
> - ❌ 不支持 `<style>`/`<script>`、CSS class/id/`<div>`、`position:fixed/absolute/sticky`、`float`、`@media`/`@keyframes`、`display:grid`、CSS 变量 `var(--x)`、`<svg>`
> - ✅ 支持内联 `style`、有限 `display:flex`、`border-radius`、`box-shadow`、`linear-gradient`、`<section>/<p>/<span>/<strong>/<img>` 等基础标签
> - 所有"装饰性空元素"必须在内部放 `<span leaf=""><br></span>` 占位
> - 所有文字节点必须用 `<span leaf="">文字</span>` 包裹
> - **中文大字号标题禁止负字距**
> - **一个组件只用一种强调手法**

---

## 设计变量速查表（Design Token）

```yaml
color:
  primary_text: "#362A20"      # 标题、正文主文字（暖棕黑，区别于静纸的冷灰黑 #232323）
  secondary_text: "#7A6250"    # 次要文字、说明、署名
  muted_text: "#A8927A"        # 最弱层级：页码、时间戳、图片说明（同时兼作结构色，不占 accent 配额）
  accent: "#B8583A"            # 唯一锚点色（赤陶橙），全篇 ≤4 处
background:
  soft_tint: "#F6EEE1"          # 引用块/提示卡/CTA 局部容器背景
  card_border: "#EEE1CC"        # 卡片边框、分割细线
typography:
  h1: "22px / weight 700 / line-height 1.5"
  h2: "18px / weight 700 / line-height 1.5（手记式章节标题，也复用于组件 15 数据摘要的大数字）"
  h3: "15px / weight 700 / italic / line-height 1.6（小节标题，和正文同号、靠斜体+字重区分）"
  quote: "17px / weight 500 / line-height 1.75~1.85（引用块/金句卡/情绪停顿句统一用这一档）"
  body: "15px / weight 400 / line-height 1.95"
  caption: "13px / weight 400 / line-height 1.75"
  micro: "11px / weight 600 / letter-spacing 1px（时间戳/图注/署名/证言署名/分割符号统一用这一档，不再额外开 12px）"
spacing:
  section_gap: "44px"           # 比静纸的 40px 略大——温暖叙事需要更明显的呼吸停顿
  image_gap: "34px"
  paragraph_gap: "22px"
radius:
  card: "14~18px"                # 明显大于静纸的 4~6px，圆角本身就是"柔软"的视觉语言
shadow:
  ambient_glow: "0 20px 44px rgba(58,46,36,.08)"   # 仅用于图片容器，登记自 design-tokens.md「可选装饰工具」
  keyquote_glow: "0 16px 40px rgba(184,88,58,.16)" # 仅用于组件 7 金句卡，全篇 ≤1 次
```

**字号阶梯 6 级**（11/13/15/17/18/22px），和静纸一样不额外开新字号——包括组件 15 数据摘要的大数字也复用 18px（h2 同档），不为了"看起来更醒目"单独开 20px。**全篇 accent（`#B8583A`）用量 ≤4 处**，可用 `design_quality_check.py --accent '#B8583A' --accent-quota 4` 自动核查。**结构性重复元素**（时间线圆点/竖线、列表圆点、卡片边框）统一用 `muted_text` 色 `#A8927A` 或更浅的 `#EEE1CC`，不占用 accent 配额——accent 只留给组件 4 的关键词下划线和组件 7 金句卡。

---


## 组件 1：封面头图（信笺式）


不用刊头式大标题、不用杂志式几何装饰——像一封信的第一页：一句手写感导语在上，标题居中偏下，日期像落款一样安静地留在角落。


```html
<section style="padding:12px 4px 0;margin-bottom:8px;">
  <p style="font-size:13px;color:#7A6250;line-height:1.8;margin:0 0 16px;font-style:italic;">
    <span leaf="">{{一句引导语，像写信开头，比如"写给还在寻找答案的你"}}</span>
  </p>
  <p style="font-size:22px;font-weight:700;color:#362A20;line-height:1.5;margin:0 0 14px;letter-spacing:0;">
    <span leaf="">{{文章标题，超过 16 字在语义断点处用 <br/> 分两行}}</span>
  </p>
  <p style="font-size:13px;color:#7A6250;line-height:1.75;margin:0 0 22px;">
    <span leaf="">{{一句话说明这篇文章讲了什么，不是标题的重复}}</span>
  </p>
  <section style="display:flex;align-items:center;gap:10px;">
    <span style="width:20px;height:1px;background:#C7AF8F;display:inline-block;"><span leaf=""><br></span></span>
    <span style="font-size:11px;color:#A8927A;letter-spacing:0.5px;"><span leaf="">{{日期}} · {{阅读时长估计}}</span></span>
  </section>
</section>
<section style="height:1px;background:#EEE1CC;margin:26px 0 0;"><span leaf=""><br></span></section>
```



## 组件 2：导读（可选，仅 3 章节及以上时生成）


不用编号徽章，用信纸边栏式的细线框，语气像目录卡片而不是杂志导览条。


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



## 组件 3：章节标题（手记式，小圆点引导，不用编号）


静纸主题的章节标题用「编号+标题」的杂志式做法；这里换成一个小圆点+标题，像日记里的分段符号，语气更轻。


```html
<section style="margin:44px 0 20px;display:flex;align-items:center;gap:10px;">
  <span style="width:6px;height:6px;border-radius:50%;background:#A8927A;display:inline-block;flex-shrink:0;"><span leaf=""><br></span></span>
  <p style="font-size:18px;font-weight:700;color:#362A20;line-height:1.5;margin:0;">
    <span leaf="">{{章节标题}}</span>
  </p>
</section>
```



## 小节标题（`###`，斜体强调，不单独占用圆点标记）


```html
<p style="font-size:15px;font-weight:700;font-style:italic;color:#362A20;line-height:1.6;margin:26px 0 12px;">
  <span leaf="">{{小节标题}}</span>
</p>
```



## 组件 4：正文段落 + 关键词强调


强调手法：极细下划线（1px，赤陶色），和静纸一样只用一种强调手法，不叠加。段落长度按 [editorial-identity.md](editorial-identity.md) 控制在 40~70 字。


```html
<p style="font-size:15px;color:#362A20;line-height:1.95;margin:0 0 22px;text-align:justify;">
  <span leaf="">这里是正文内容，</span><span style="border-bottom:1px solid #B8583A;padding-bottom:1px;"><span leaf="">这几个字是关键词强调</span></span><span leaf="">，一段最多用 1～2 处。</span>
</p>
```



## 次要说明（比强调更轻，专有名词首次出现用字重区分，不占用 accent 配额）


```html
<p style="font-size:15px;color:#362A20;line-height:1.95;margin:0 0 22px;text-align:justify;">
  <span leaf="">这里提到 </span><strong style="color:#7A6250;font-weight:600;"><span leaf="">某个专有名词</span></strong><span leaf="">，用字重区分即可。</span>
</p>
```



## 组件 5：情绪停顿句（独立成段的大字号短句，区别于金句卡——不是全篇最重的锚点，只是节奏上的停顿）


呼应「Writing Engine」里叙事节奏的建议：一句长、一句短、一句停顿。这个组件就是那个「停顿」——不占用 accent 配额，用正文色本身放大字号。


```html
<p style="font-size:17px;color:#362A20;line-height:1.7;margin:32px 0;text-align:center;font-weight:500;">
  <span leaf="">{{一句独立的短句，作为段落之间的停顿}}</span>
</p>
```



## 组件 6：引用块（温暖底色居中，像信笺里夹的一页引文）


```html
<section style="margin:36px 0;padding:28px 24px;background:#F6EEE1;border-radius:16px;text-align:center;">
  <p style="font-size:17px;color:#362A20;line-height:1.85;margin:0;font-weight:500;">
    <span leaf="">{{引用内容，一句话说完，不超过两行}}</span>
  </p>
  <p style="font-size:11px;color:#A8927A;margin:14px 0 0;">
    <span leaf="">—— {{来源/作者，无来源可删除这一行}}</span>
  </p>
</section>
```



## 组件 7：金句强调卡（全文最多用 1 次，全篇视觉最重的锚点）


用赤陶色实底代替静纸的近黑色实底——同样的「全篇仅一次」纪律，颜色换成本主题的锚点色。


```html
<section style="margin:36px 0;padding:34px 24px;background:linear-gradient(160deg,#B8583A 0%,#A34B2F 100%);border-radius:18px;text-align:center;box-shadow:0 16px 40px rgba(184,88,58,.16);">
  <p style="font-size:17px;color:#FFFFFF;line-height:1.75;margin:0;font-weight:500;">
    <span leaf="">{{全文最核心的一句话}}</span>
  </p>
</section>
```

（同静纸的处理：纯色实底换成同色系微渐变，深浅差不到 10%，只增加材质厚度感，不增加视觉元素数量。）



## 组件 8：人物证言卡（覆盖「引用/证言」语义，比引用块更具体，带来源身份说明）


品牌故事/人物访谈类内容常见的『当事人原话』呈现方式，用小圆点代替头像占位，不使用真实图片时也能成立。


```html
<section style="margin:36px 0;padding:26px 22px;border:1px solid #EEE1CC;border-radius:16px;">
  <p style="font-size:15px;color:#362A20;line-height:1.85;margin:0 0 16px;font-style:italic;">
    <span leaf="">“{{当事人原话，一到两句}}”</span>
  </p>
  <section style="display:flex;align-items:center;gap:10px;">
    <span style="width:28px;height:28px;border-radius:50%;background:#F6EEE1;display:inline-block;"><span leaf=""><br></span></span>
    <p style="font-size:11px;color:#7A6250;margin:0;"><span leaf="">{{姓名}} · {{身份/关系}}</span></p>
  </section>
</section>
```



## 组件 9：提示/旁注（左侧细线，暖灰棕色，不用背景色块）


```html
<section style="margin:0 0 22px;padding:2px 0 2px 16px;border-left:2px solid #C7AF8F;">
  <p style="font-size:13px;color:#7A6250;line-height:1.75;margin:0;">
    <span leaf="">{{提示或补充说明内容}}</span>
  </p>
</section>
```



## 组件 10：代码块（复用通用增量库，仅在极少数场景使用——原文引述/日期备注）


直接用 [common-components.md](common-components.md) 组件 1b 浅色代码块，左侧竖条颜色换成 `#B8583A`；温暖叙事类内容很少需要代码块，出现时不改变通用库结构，只换色跟随本主题锚点色。



## 组件 11：图片 + 说明文字（相册页式，带极轻的暖色空气感阴影）


静纸主题几乎不用阴影；这里在图片容器上用一次「Ambient Glow」（见 `design-tokens.md`「可选装饰工具」），配合本主题「Weight：中」的设计语言定位——比静纸更愿意让图片『浮起来』一点点。


```html
<section style="margin:34px 0;">
  <section style="border-radius:16px;overflow:hidden;box-shadow:0 20px 44px rgba(58,46,36,.08);">
    <img src="{{图片URL}}" style="max-width:100%;height:auto;display:block;margin:0 auto;" />
  </section>
  <p style="font-size:11px;color:#A8927A;text-align:center;margin:12px 0 0;line-height:1.6;">
    <span leaf="">{{图片说明，无说明整段删除，不编造}}</span>
  </p>
</section>
```



## 组件 12：双图对比（上下堆叠 + 图注对照，不用 table 承担布局）


```html
<section style="margin:34px 0;">
  <section style="border-radius:16px;overflow:hidden;margin-bottom:10px;">
    <img src="{{图片一 URL}}" style="max-width:100%;height:auto;display:block;margin:0 auto;" />
  </section>
  <p style="font-size:11px;color:#A8927A;text-align:center;margin:0 0 24px;line-height:1.6;"><span leaf="">{{图一说明}}</span></p>
  <section style="border-radius:16px;overflow:hidden;margin-bottom:10px;">
    <img src="{{图片二 URL}}" style="max-width:100%;height:auto;display:block;margin:0 auto;" />
  </section>
  <p style="font-size:11px;color:#A8927A;text-align:center;margin:0;line-height:1.6;"><span leaf="">{{图二说明}}</span></p>
</section>
```



## 组件 13：列表（小圆点 + 悬挂缩进，语气比静纸更柔和）


```html
<section style="margin:0 0 22px;">
  <section style="display:flex;margin-bottom:12px;">
    <span style="flex-shrink:0;width:16px;color:#A8927A;font-size:15px;line-height:1.95;"><span leaf="">·</span></span>
    <p style="font-size:15px;color:#362A20;line-height:1.95;margin:0;flex:1;"><span leaf="">{{列表项一}}</span></p>
  </section>
  <section style="display:flex;margin-bottom:12px;">
    <span style="flex-shrink:0;width:16px;color:#A8927A;font-size:15px;line-height:1.95;"><span leaf="">·</span></span>
    <p style="font-size:15px;color:#362A20;line-height:1.95;margin:0;flex:1;"><span leaf="">{{列表项二}}</span></p>
  </section>
</section>
```



## 组件 14：岁月时间线（故事/回忆录类的核心组件，覆盖「流程/步骤」语义）


用 flex 竖排模拟时间线的圆点+竖线，不依赖 `position:absolute`——竖线是 flex 列里第二个子元素用 `flex:1` 撑满剩余高度，这是标准 flex 写法，但未在真实公众号客户端做过系统性长文渲染验证，如果多个时间线节点连续使用，建议先发一次真实预览确认竖线连续不断开。


```html
<section style="margin:0 0 4px;">
  <section style="display:flex;">
    <section style="width:20px;flex-shrink:0;display:flex;flex-direction:column;align-items:center;">
      <span style="width:8px;height:8px;border-radius:50%;background:#A8927A;display:inline-block;flex-shrink:0;"><span leaf=""><br></span></span>
      <span style="width:1px;flex:1;background:#EEE1CC;min-height:36px;display:inline-block;"><span leaf=""><br></span></span>
    </section>
    <section style="flex:1;padding:0 0 26px 16px;">
      <p style="font-size:11px;font-weight:600;letter-spacing:1px;color:#A8927A;margin:0 0 6px;"><span leaf="">{{年份/时间点}}</span></p>
      <p style="font-size:15px;color:#362A20;line-height:1.85;margin:0;"><span leaf="">{{这个时间点发生的事}}</span></p>
    </section>
  </section>
</section>
```



## 组件 15：关系数据摘要卡（覆盖「数据/指标」语义，但用温和的方式呈现，不是硬邦邦的数据表）


科技类主题的数据卡会强调精确指标；这里刻意反过来——数字服务于情绪，不是服务于说服力。


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



## 组件 16：表格替代（卡片化，故事类内容少用，但覆盖语义完整性）


```html
<section style="margin:0 0 22px;border:1px solid #EEE1CC;border-radius:14px;overflow:hidden;">
  <section style="display:flex;padding:12px 16px;background:#F6EEE1;">
    <p style="flex:1;font-size:11px;font-weight:600;color:#7A6250;margin:0;"><span leaf="">{{列名一}}</span></p>
    <p style="flex:1;font-size:11px;font-weight:600;color:#7A6250;margin:0;"><span leaf="">{{列名二}}</span></p>
  </section>
  <section style="display:flex;padding:12px 16px;border-top:1px solid #EEE1CC;">
    <p style="flex:1;font-size:13px;color:#362A20;margin:0;"><span leaf="">{{值一}}</span></p>
    <p style="flex:1;font-size:13px;color:#362A20;margin:0;"><span leaf="">{{值二}}</span></p>
  </section>
</section>
```



## 组件 17：分割线（暖色版，用小心形代替静纸的三个点，贴合『故事』气质）


```html
<section style="margin:36px 0;text-align:center;">
  <span style="font-size:11px;color:#C7AF8F;letter-spacing:8px;"><span leaf="">♡</span></span>
</section>
```



## 组件 18：关注引导（语气温和，不是营销号硬广）


```html
<section style="margin:36px 0;padding:26px 22px;background:#F6EEE1;border-radius:16px;text-align:center;">
  <p style="font-size:15px;color:#362A20;line-height:1.8;margin:0;">
    <span leaf="">{{一句邀请读者关注/持续阅读的话，语气像朋友而不是公众号运营}}</span>
  </p>
</section>
```



## 组件 19：结尾互动区（emoji，语气温和克制）


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



## 组件 20：延伸阅读（覆盖「资源/下载引导」语义）


```html
<section style="margin:28px 0 0;padding:20px 0 0;border-top:1px solid #EEE1CC;">
  <p style="font-size:11px;font-weight:600;letter-spacing:1px;color:#A8927A;margin:0 0 12px;">
    <span leaf="">如果还想接着读</span>
  </p>
  <p style="font-size:13px;color:#362A20;line-height:2;margin:0;">
    <span leaf="">— {{延伸阅读一}}</span><br/>
    <span leaf="">— {{延伸阅读二}}</span>
  </p>
</section>
```



## 组件 21：作者签名区（末尾仅一处，信笺落款式）


```html
<section style="margin:32px 0 0;padding:24px 0 0;text-align:center;">
  <p style="font-size:13px;color:#A8927A;line-height:1.8;margin:0;">
    <span leaf="">{{作者名}} · {{一句话简介，占位待替换}}</span>
  </p>
</section>
```

## 组件 22：暖调导语封面区块（可选，仅用于需要仪式感开篇的文章类型）

> **默认不用**，组件 1（信笺式封面头图）仍是首选，两者气质其实有点冲突——组件 1 是"轻声细语的信"，这个是"郑重开场的通稿"，同一篇文章选一个用，不要都用。这是 [common-components.md](common-components.md)「深色导语封面区块」的暖信笺配色变体：深色底换成暖棕色系而不是中性灰黑，呼应本主题"温暖叙事"的定位，不是简单换个 accent 就照抄静纸的版本。

```html
<section style="margin:0 0 40px;padding:52px 24px;border-radius:18px;background:linear-gradient(165deg,#2B2118 0%,#362A20 100%);box-sizing:border-box;">
  <p style="margin:0 0 20px;text-align:center;font-size:11px;font-weight:700;letter-spacing:4px;color:#D89B7C;text-transform:uppercase;">
    <span leaf="">{{小标签，如"年度总结""品牌故事"}}</span>
  </p>
  <p style="margin:0 0 24px;text-align:center;font-size:24px;font-weight:700;line-height:1.5;color:#FFFFFF;">
    <span leaf="">{{文章标题，超过 18 字在语义断点处用 <br/> 分两行}}</span>
  </p>
  <p style="margin:0 auto;text-align:center;max-width:80%;font-size:12px;font-weight:500;line-height:1.6;color:#362A20;background:#F6EEE1;padding:8px 18px;border-radius:20px;">
    <span leaf="">{{一句话副标题/摘要}}</span>
  </p>
</section>
```

（深色底用暖棕渐变 `#2B2118→#362A20`，收尾正好落在本主题 `primary_text` 色上，不是凭空取的深色；圆角沿用本主题的 18px 卡片圆角，不是静纸变体的 6px 直角——圆角本身就是本主题"柔软"的视觉语言，照搬静纸的直角反而破坏一致性；底部白色药丸也换成 `soft_tint` 暖米色 `#F6EEE1`，不用纯白，全篇没有一处纯白色块，保持"温暖"的调性。小标签用赤陶色的浅色变体 `#D89B7C`，原理和静纸一样：深色底上原色 accent `#B8583A` 不够醒目。）




## 完整文章模板骨架

```
组件1 封面头图
[组件2 导读]（3章节以上时生成）
循环：
  组件3 章节标题
  组件4 正文段落（穿插组件5情绪停顿句/组件6引用/组件8证言/组件9提示/组件11图片/组件13列表/组件14时间线/组件15数据摘要，按内容需要，组件7金句全篇仅1次）
组件17 分割线（可选，仅内容天然有大转折时插入）
[组件18 CTA 关注引导]（可选，不是每篇都要）
组件19 结尾互动区
[组件20 延伸阅读]（可选）
组件21 作者签名区
```

## 文章类型 → 组件组合配方

| 文章类型 | 核心组件 | 点缀组件（按需，不要堆） |
|---|---|---|
| 人物故事/访谈 | 组件1+3+4+8 | 组件6 引用、组件7 金句（仅1次）、组件11 图片 |
| 品牌故事/品牌介绍 | 组件1+3+4+15 | 组件7 金句、组件18 CTA、组件11 图片 |
| 回忆录/岁月记事 | 组件1+3+4+14 | 组件12 双图对比、组件5 情绪停顿句 |
| 生活方式/随笔 | 组件1+4+6 | 组件7 金句（仅1次）、组件11 图片、组件17 分割线 |

## Markdown → 组件映射规则表

| Markdown 元素 | 对应组件 |
|---|---|
| `# 标题` | 组件 1 |
| `## 章节` | 组件 3 |
| `### 子章节` | 小节标题变体 |
| 开头 `> 引用` | 组件 1 副标题（一句话摘要）或组件 6（独立引言） |
| 正文 `> 引用` | 组件 6，人物原话优先用组件 8 |
| `**加粗**` | 组件 4 的"次要说明"变体 |
| `==高亮==` / 核心结论 | 组件 4 关键词下划线，全文最重要一句用组件 7（仅一次） |
| 代码块 | 组件 10（说明见上，罕见场景） |
| `![]()` | 组件 11，连续两张对照用组件 12 |
| 列表 | 组件 13 |
| 时间/年份线索明显的列表 | 组件 14 |
| 表格 | 组件 16 |
| `---` | 组件 17（仅内容有大转折时用） |

---

## Gotchas（本主题设计时的取舍）

- **不是静纸的换色版**：结构骨架（手记式章节标题、时间线、人物证言卡、关系数据摘要卡）是围绕"温暖叙事"重新设计的，不是静纸组件换个颜色。
- **阴影只用在两处**：组件 11 图片容器的 ambient glow、组件 7 金句卡的 keyquote glow，其余组件不用阴影——温暖不等于到处加阴影，克制的纪律和静纸是共通的，只是允许的"重量"上限更高一点。
- **时间线用 flex 不用绝对定位**：组件 14 的竖线靠 flex 列 `flex:1` 撑高实现，没有用 `position:absolute`，但连续多个时间线节点堆叠时的竖线连续性未经真实公众号客户端验证，建议首次使用先发一次真实预览确认。
- **accent 色全篇 ≤4 处**：组件 7（≤1 次）+ 组件 4 下划线强调，累计控制在 4 处以内。
- **不用负字距、不叠加强调技巧**：和静纸的纪律完全一致，见 SKILL.md 平台红线。
- **页面背景不是真的暖色**：见文件开头"技术性说明"，暖色调只体现在局部容器和文字色上，不要向用户承诺"整篇文章背景会变成暖白色"。
