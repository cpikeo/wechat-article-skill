---
name: wechat-article
description: Director-Level WeChat Editorial Design Intelligence。把 Markdown/Word/PDF/纯文本排版成可直接粘贴进公众号编辑器的世界级编辑设计水准 HTML，可选官方 API 自动建草稿/发布。核心能力不是"套模板"而是"判断驱动的版式编排"：先判断受众→核心主张→信息层级→阅读节奏→情绪温度，再决定用什么空间、文字、比例、图片表达。内置三套设计语言（静纸/暖信笺/酌墨）覆盖克制/温暖/笃定三种阅读人格；支持按描述或参考图生成新主题。触发场景：用户提到"公众号排版/微信排版/gzh/公众号文章"或给 md/docx/pdf/纯文本要转成公众号 HTML；用户说"自动排版/一键排版"；用户想生成新主题；用户提到"自动发布/真发布拿链接/配置微信凭证"。不用于生成普通网页/落地页/PPT。
---

# 公众号编辑设计 Intelligence

把一篇文章变成能发到微信公众号的成品——**判断驱动的世界级编辑设计**，不是模板套色。

## 核心判断链（必读）

不要让"文章类型→主题→组件→HTML"成为唯一决策路径。**先判断，再设计，最后才装配**：

```
1. Audience（读者是谁）→ 决定语气、密度、距离感
2. Purpose（这篇文章要让读者做什么）→ 决定锚点分布
3. Core Claim（最该记住的一句话）→ 决定视觉高潮位置
4. Information Hierarchy（哪些信息必须看见，哪些应该弱化）→ 决定层级
5. Reading Pace（哪里快、哪里停、哪里转场）→ 决定节奏
6. Emotional Temperature（冷静/温暖/笃定/轻快）→ 决定 Design Language 选择
7. Visual Weight（哪里重、哪里轻、哪里留白）→ 决定组件取舍
8. Spatial Rhythm（段落密度、图文比例、章节间隔）→ 决定留白
9. Composition（版面组合）→ 最终组件
10. HTML 输出
```

**核心原则**：
> **Field（空间）> Line（线条）> Type（文字）> Container（容器）**
>
> 优先用空间、文字、比例、对齐、节奏、图片解决问题，而不是依赖卡片和装饰。
>
> 少组件 + 强判断 > 多组件 + 强模板。**禁止**为了"丰富"机械增加卡片、标签、图标、下划线、分割线或装饰。

## 路由

| 用户意图 | 行为 |
|---|---|
| "把这篇排成公众号 / gzh / 排版" | 走「排版引擎」 |
| "润色 / 优化文笔 / 调整节奏"（不含排版诉求） | 读 [references/content-editing.md](references/content-editing.md)，只改文字，不改样式 |
| "自动发布 / 建草稿 / 拿链接 / 配 AppID" | 读 [references/auto-publish.md](references/auto-publish.md)，先说明两条边界（草稿灰度开关待验证、真发布需企业认证；都不等于推送给粉丝） |
| "生成新主题 / 自定义风格 / 按参考图做" | 读 [references/theme-generator.md](references/theme-generator.md) |
| "帮我写一篇公众号文章"（只有话题没内容） | 先用写作能力产出 Markdown 草稿，再进排版引擎——这是两步独立执行，不把选题策划塞进排版规则 |
| "直接排 / 一键 / 不用问" | 全自动模式：自行推断结构、选主题、排版校验，交付时附决策说明 |

## 排版引擎（一次读取，最小 Context）

### 0. 输入归一化（只读一次）

| 输入 | 处理 |
|---|---|
| Markdown / `.md` | 直接用 |
| `.docx` | `python3 scripts/extract_docx.py 文件.docx -o 文章.md` |
| PDF | Read 分页读取，删页眉页脚/页码，合并硬断行，图位留占位 |
| 纯文本 / `.txt` | 按标题启发式推断结构（短行 + 前后空行 + 序号前缀 = 标题） |
| 网页/富文本 | 剥样式，HTML→Markdown 语义映射 |
| `.doc`（老格式） | 提示另存为 .docx |

归一化后**一次读取全文，后续步骤全部复用**，不重复读文件。

### 1. 选 Design Language（按判断，不是按标签）

读 [references/design-system.md](references/design-system.md) 理解三套 Design Language 的 9 维定位；完整组件与组合规则读 [references/themes.md](references/themes.md)（**这是唯一的主题组件来源，一次性读入**）。

| 判断信号 | 选择 |
|---|---|
| 深度分析/观点/教程/复盘/通用/不确定 | **静纸 Silent Paper** |
| 人物故事/品牌故事/访谈/回忆录/情感随笔 | **暖信笺 Warm Letter** |
| 深度评论/书评影评/行业观察/年度总结/反感 emoji 图标 | **酌墨 Wine Ink** |
| 用户明确指定"用 XX" | 按用户说的 |
| 气质与三套都冲突（要营销感/鲜艳色/强促销） | 如实说明三套定位，走自定义主题生成 |

### 2. 解析与判断（一次完成，不重复）

从 Markdown 一次提取：
- 文章标题（`#` 或 frontmatter）
- 章节结构（`##` 层级，自动分配 01/02/03…编号；末章为结语用变体）
- 开头引言（最开头的 `>` 块）
- 正文段落、引用（非开头 `>`）、图片/GIF、代码块、列表、表格
- 加粗/高亮/下划线语义标记

**同步做出 Editor 判断（写入装配决策，不重复推理）**：
- **Core Claim**：全文最核心的一句话，用于金句卡（全篇仅 1 次，用在判断上的视觉高潮位置，不是机械放在第一个章节）
- **Anchor Points**：锚点层位置 ≤4 处（核心结论/关键数据/最强判断）
- **Keyword Marks**：每段 1-2 处关键词下划线（4-15 字，优先核心观点/结论/专有名词），即使原文无加粗也主动加
- **Pacing Plan**：哪里需要引用停、哪里需要图片转场、哪里需要节奏变化；连续 3-4 段纯文字必须考虑打断（用引用/提示/图片/分割线之一，不是都加）
- **Image Decisions**：每张图判断"情绪建立/概念解释/证据/转场/高潮"哪一种职责；没有职责的图删掉；图片过密就减
- **开头策略**：是否用深色导语封面（仅深度报道/年度总结/专栏合集这类需要郑重开场时用，替代而非叠加头部）
- **结尾策略**：签名区有且仅有末尾一处；原文已有签名则合并；不重复生成三连引导

### 3. 装配 HTML

所有 HTML **从 [references/themes.md](references/themes.md) 取**，不手写、不凭记忆。通用元素（代码块/图片/占位）同样在该文件中，不再单独读取 common-components。

装配纪律：
- **一篇文章只用一套 Design Language 的组件**，不跨主题混用
- **行内标记语义转换**：`**加粗**`→次要色加粗（不占 accent 配额）；`==高亮==`/核心结论→accent 下划线；`<u>`/`++`→下划线；`>引用`→对应主题引用组件
- **中文标点全角**：正文直接写弯引号，代码块/英文专名/URL 保持原样
- **段落呼吸感**：单句 40-70 个汉字，超过在语义断点拆段；大号标题 ≤2 行且按语义断行；英文短语/数字单位（≤15 字符）套 `<span style="white-space:nowrap;"><span leaf="">...</span></span>` 防中间断行
- **章节导读**：从 `##` 取前 3 个作为导读（仅 ≥3 章节时生成，用对应主题导读组件）
- **署名占位**：无明确作者用 `{{作者名}}` / `{{简介}}` 占位，不写死人名

### 4. 质量三关（确定性脚本 + 判断）

**第一关：平台合规（必须 0 ERROR / 0 半角 WARNING）**
```bash
python3 scripts/validate_gzh_html.py <产物.html>
```

**第二关：设计质检（必须 0 ERROR，WARNING 逐条有理由）**
```bash
# 静纸 --accent '#6A7567' --accent-quota 4
# 暖信笺 --accent '#B8583A' --accent-quota 4
# 酌墨 --accent '#7A2E2E' --accent-quota 4
python3 scripts/design_quality_check.py <产物.html> --accent '<对应色>' --accent-quota 4
```

**第三关：Editorial Judgment（不可自动化，必须通读）**
按 [references/design-system.md](references/design-system.md)「Editorial QA 清单」逐条过：首屏抓人？节奏是否服务于核心主张？视觉高潮是否落在 Core Claim？图文比例？强调是否正确？结尾是否克制？

**禁止输出虚假的"综合审美 XX 分"**——只输出真实证据、问题严重度、修改决策。三关全过才进入输出。

### 5. 输出

1. **干净正文文件**：`{原文件名}_排版_{主题英文名}.html`，纯 `<section>...</section>`，不含 `<!DOCTYPE>/<html>/<head>/<body>`。
2. **一键复制预览页**：
   ```bash
   python3 scripts/wrap_preview.py <上面的.html>
   ```
   产出 `{...}_预览.html`，浏览器打开→右上角「复制」→公众号编辑器粘贴。
3. 交付说明：所用 Design Language + 判断依据、两脚本结论摘要、用户需完成的手动步骤（粘贴/替换署名/配凭证等）。

---

## 平台红线（唯一权威来源：[references/platform-rules.md](references/platform-rules.md)）

核心摘要：
- **禁止**：`<style>/<script>/<div>`、`class/id`、`position:fixed/absolute/sticky`、`float`、`@media/@keyframes`、`display:grid`、CSS 变量、外部字体/CSS、`<svg>`、图标库 CDN、图库外链。
- **必须**：样式全部内联；所有文字节点用 `<span leaf="">文字</span>` 包裹；装饰性空元素内放 `<span leaf=""><br></span>` 占位。
- **可用**：有限 `display:flex`、`linear-gradient`、`border-radius`、`box-shadow`、`<section>/<p>/<span>/<strong>/<img>/<h3>`。
- **图片**：必须本地文件→（手动粘贴时用户自上传）/（API 直发时脚本自动上传替换成微信域名），不直接用图库外链。
- **图标**：只用 Unicode 字符/CSS 几何图形/数字/经判断的少量 Emoji；酌墨全篇用「细描边圆环+Unicode 排版符号」不用 emoji。

---

## 官方 API 直发（可选）

仅在用户明确要"自动建草稿/自动发布/真发布拿链接"时使用。读 [references/auto-publish.md](references/auto-publish.md)。脚本在 `assets/automation/wechat_official_publish.py`，纯 Python 标准库：

```bash
python3 assets/automation/wechat_official_publish.py --appid "ID" --secret "SECRET" --check-draft-switch
python3 assets/automation/wechat_official_publish.py --appid "ID" --secret "SECRET" --html "文章.html" --cover "封面.jpg" --title "标题" --author "作者" --digest "摘要"
# 企业认证账号加 --submit 自动发布
```

---

## 自定义主题生成

用户想要新风格时读 [references/theme-generator.md](references/theme-generator.md)，流程：收集偏好（一次问全）→ 生成区块库预览（存 `assets/theme-previews/`）→ 确认后转标准主题并登记进 [references/themes.md](references/themes.md)→跑 `python3 scripts/component_lint.py .` 到 0 ERROR。配色起点可参考 [references/design-system.md](references/design-system.md) 的色板预设，不重复讨论。

---

## 交付前自检

- [ ] 三关全过：合规 0 ERROR/WARNING，设计质检 0 ERROR + WARNING 有理由，Editorial QA 通读完成
- [ ] 只用了一套 Design Language 的组件，没有跨主题混用
- [ ] 锚点层 ≤4 处，都落在真正重要的判断/结论/数据上
- [ ] Core Claim 位置正确，是全文视觉高潮
- [ ] 图片每张都有明确职责，没有为填空配图
- [ ] 图标只用安全技术（Unicode/CSS 几何/数字/酌量 emoji），没有 SVG/图标库外链
- [ ] `<span leaf="">` 全覆盖，装饰空元素有 `<br>` 占位
- [ ] 署名区仅末尾一处，占位符已提示用户替换
- [ ] 交付说明包含：Design Language 选择理由、两脚本结论、用户待办事项
- [ ] 涉及自动发布：如实说明两条边界，未暗示"推送粉丝"
