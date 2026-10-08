# Theme Generator：自定义主题生成

用户想要内置三套 Design Language 之外的新风格时走本流程。**约束与平台规则统一读 [platform-rules.md](platform-rules.md) 和 [design-system.md](design-system.md)，这里不重复列举**。

## 触发

- "生成一套新主题/自定义风格/我要 XX 风格"
- 上传参考图"按这个做"
- 对三套都不满意

## 第一步：收集偏好（一次问全）

| 字段 | 必填 | 为空时 |
|---|---|---|
| 主题描述（气质/场景/感觉） | **是**（或由参考图推导） | — |
| 参考图 | 否 | — |
| 主题名 / ID | 否 | 自动生成（`theme-xxx`，小写+连字符，12-40字符） |
| 色值（主/背/文/强/装） | 否 | 由描述/参考图推导；**先查 design-system.md 第七节色板预设**，命中气质关键词（"北欧/侘寂/杂志/科技/植物信件"等）直接用现成色板，不重复讨论 |
| 字体偏好 | 否 | 按风格选：system / pingfang / serif / monospace / kaiti 等（衬线仅限标题/引用/金句，正文保持无衬线） |
| 三类 TAG（设计技巧/风格特征/适用场景，各2-4个短语） | 否 | 自动生成 |
| 圆角/阴影偏好 | 否 | 按风格定（克制主题少/无阴影；温暖主题允许柔和阴影） |

## 第二步：9 维定位（先判断再设计）

在生成区块库前，先用 design-system.md 第六节的 9 维表写一句定位：
> Silence/Weight/Breathing/Rhythm/Contrast/Pace/Emotion/Temperature/Distance

例如"Silence 高 / Weight 低 / Rhythm 中 / Contrast 低 / Emotion 沉静"决定了这套主题应该大留白、无阴影、靠留白而非组件切换制造变化。**9 维矛盾（Weight 低却大量卡片阴影）是"气质散"的根源，比色值不对更致命。**

## 第三步：生成区块库预览 HTML

生成 45-75 个 Block，保存到 `assets/theme-previews/{theme-id}.html`，全部区块在同一页连续排布，用户**一次性浏览整套风格**。

**生成要求**（关键约束，其余参考现有主题文件的占位文案规范和微信兼容约束）：

1. 文件开头输出主题元信息注释：
```
<!-- THEME-NAME/ID/DESCRIPTION/COLOR/BACKGROUND/TEXT/ACCENT/DECORATION/FONT/DESIGN-TECHNIQUE-TAGS/STYLE-FEATURE-TAGS/SCENE-TAGS/RADIUS/SHADOW -->
```
2. 每个 Block 用注释 `<!-- Block: 名称 -->`，顶层 `<section>` 带 `id="block-{缩写}-{语义}"`（仅预览用，进主题库时去掉 id）。
3. 覆盖核心语义：hero / title hierarchy / paragraph / quote-notice / list / media / code / data / compare / process / faq / resource / author / cta / ending，但权重按"主题结构模型"分配（叙事类重引文/证言，文档类重目录/步骤，杂志类重刊头/摘要）。
4. 所有样式**内联**；所有字号 ≤24px（实际用于正文≤22px）；不用 `<style>/<script>/<div>/<svg>/<table布局>/class/id/position/grid/var`；按钮用 `<span>` 模拟不用 `<button>`；图片占位用 `https://placehold.co/` 系列。
5. 文案是"结构化占位+风格化表达"（如"专题导语占位/章节标题占位/引用内容占位"），不写成真实产品/品牌/人物/地名。
6. 深色/浅色系主题都以**白底或近白底为主**，仅局部卡片/提示块/强调区用主题色或浅衬底，不大面积深色铺底（除非明确是反白体系）。
7. **不照搬任何现有主题骨架**——从 9 维定位 + 色板推导骨架、区块类型、命名、节奏、装饰语言。

## 第四步：转换为标准主题并登记

用户确认预览后，转换为 `references/themes.md` 中的一个新主题块（追加到文件末尾，不新建独立文件），必须完成：

1. **补 `<span leaf="">`**：所有文字节点包 `<span leaf="">文字</span>`，装饰空元素内放 `<span leaf=""><br></span>`。
2. **去掉预览 id**，所有 `id="block-*"` 删除。
3. 按照 themes.md 的结构组织：主题速选表追加一行 → 新增章节「四、{名称} 组件」→ 包含完整 Design Token、每个核心组件的 HTML（精选 20-35 个核心组件，预览 HTML 保留全量）、文章骨架、配方表、Markdown 映射表追加到通用映射表中（如有专属差异）。
4. 强调色 hex 与全篇配额写进 Token 表，保证 `design_quality_check.py --accent` 可自动核查（accent 必须和 structural 色视觉上明显区分）。
5. **字号严格 6 级**（11/13/15/16/17/22px），不开新字号。
6. 跑检查：
```bash
python3 scripts/component_lint.py .   # 0 ERROR
```
7. 实际拼一篇真实文章渲染 → validate + design_quality_check 都通过，不只靠代码审查。

## 维护

- 改主题：改 themes.md 中对应块，重跑 lint。
- 删主题：从 themes.md 删除对应章节，删除预览 HTML，从速选表移除。
- 名/ID 冲突：提示换名或确认覆盖，不静默覆盖。
- 新主题**不自动替换静纸为默认**，除非用户明确要求切换默认或纳入自动判断范围。
