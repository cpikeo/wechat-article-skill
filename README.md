# WeChat Article Skill · V16

把 Markdown、Word `.docx` 或纯文本编辑成可信、克制、适合手机阅读的微信公众号正文 HTML、独立移动预览与可核验交付包。零第三方运行时依赖，只用 Python 3 标准库。

**工作流：THINK → EDIT → DESIGN → COMPOSE → RENDER → VERIFY。** 内容判断先于视觉；删除 > 合并 > 简化 > 重组 > 补充。编辑与设计契约的唯一入口是 [`SKILL.md`](SKILL.md)。

## 本版做了什么

V16 修的是"文档承诺了、代码没做到"的地方，以及会让六主题趋同的结构性缺陷。没有新增检查项，只把该生效的生效、把会误报的收窄。

**内容成品**
- **图注回来了**：此前只有 `证据/数据/资料/实拍` 五个职责会印图注，其余全部静默丢弃。现在 alt 是读者要读的那句话（≥6 汉字、不含制作标签）就印，事实类职责整句照印。
- **表格降级不再随口起名**：首列当标题的阈值从 10 字提到 18 字，无列名时不再输出"记录 01"这种占位标题。
- **代码块不再被切成碎行**：`overflow-wrap:anywhere` 改为 `break-word`，长标识符才断词。

**六主题不再趋同**
- **版心只有一套参数**：删掉百分比页边 `measure` 与内缩 `grid.inset` 双系统（长期互相冲突），合并为单一 `margin`（px）。
- **章节开门真正分开**：`paper` 编号悬挂左栏、`frost` 编号在上加压一道通栏细线，此前两者都是"编号在上"；`bone` 的展签线由 2px 收到 1px。
- **目录跟章节开门同构**：目录按 `heading` 轴旧值 `index/report` 分支，改名后 `paper` 与 `frost` 落进同一条兜底逻辑、输出完全一样。已按六轴重写，六主题目录签名 6/6 唯一。
- **目录不再落进第一章**：原按"第一段之后"插入，正文没有引言段时目录会嵌在第一章中间。现在固定落在第一个章节标题之前。
- **代码块六种外观**：此前统一灰卡片。现在上下发丝线 / 纯缩进 / 左朱线 / 浅底 / 浅底+上下线 / 粗上框，六种签名 6/6 唯一。
- **重点句有了自己的层级**：新增 `peak_size`，载入时校验"高于导语、低于章节标题，差不足 4px 时字重必须更低"。`folio` 此前是 26px 正文对 30px 标题，两者被读成同级。

**中文排印**
- **不再改写作者的引号**：`「直角引号」` 原样保留。统一改成弯引号是把一种排版传统判成错误，且会改到直接引语内部。
- **字体栈按平台原生重排**：iOS 用 PingFang/苹方，Android 补 HarmonyOS Sans SC、MiSans 与 Noto/Source Han 衬线候选——此前 `letter/ink/bone` 的衬线标题在 Android 上会静默退化成无衬线。

**编辑审计少误报**
- 标题承诺的数量与章节数相等，不再自动判"已兑现"（"三种工作" + 3 个无关标题曾判 PASS），改为需人工确认。
- 刊头三件套（栏目行 + 摘要行 + 导语）合并计为 1 个首屏入口，不再被算成 3 个重入口。
- 年份不再算作出处；套话只在段首或紧随标题时给建议，其余记提示。

**安全与回读**
- **预览页 DOM XSS 修复**：封面注记曾直接拼进 `innerHTML`，`<img onerror>` 可执行。改为 `textContent` + 安全节点构造。
- **草稿回读改为归一化核验**：原实现要求 `content` 逐字节相等，而微信必然重写 `'`→`&#39;`、图片地址改 `mmbiz` 域名并补 `data-src`、重排 `alt`、无外链权限时剥 `<a>`——结果是草稿建好了却永远判 FAIL。现在核验纯文本逐字、块结构与图片张数。
- **`::: lead` 不再被吞**：它与 `>` 导语块同名，会被当成导语渲染成空文本并把正文挪进署名。现在在解析期直接报错并指出正确语法。

## 目录

| 路径 | 职责 |
|---|---|
| [`SKILL.md`](SKILL.md) | 唯一核心入口：编辑判断、六主题设计系统、图片契约、三级验收 |
| `scripts/render.py` | Markdown 解析、六主题排版、预览、侧车与 Gate 1/2 交付 |
| `scripts/editorial.py` | 编辑审计：类型策略、结构缺环、标题承诺、事实与声音比对 |
| `scripts/check.py` | 公众号 HTML 标签、属性、协议、内联 CSS 白名单静态门禁 |
| `scripts/extract_docx.py` | `.docx` → Markdown 结构保真提取，有损结构阻断 |
| `scripts/publish.py` | 官方 API：离线预检 → 素材复用 → 草稿回读 → 单次确认发布 |
| `scripts/typography.py` | 装饰性分隔归一、编辑说明移除、单位比与引语保护（直角引号保留不改写） |
| `scripts/safety.py` | 路径边界、哈希、原子写入与 WCAG 对比度 |
| `assets/themes.json` | 六主题唯一参数真源 |
| `assets/preview.template.html` | 移动预览：五宽度、双字体栈、封面双裁切、复制只含正文 |
| `references/` | 按需读取：[图片艺术指导](references/direction.md)、[HTML 门禁](references/platform.md)、[API 交付](references/publish.md) |
| `config.example.json` | 公众号配置示例；复制为被 Git 忽略的 `config.json` |

## 快速开始

```bash
python3 scripts/extract_docx.py 文章.docx -o 文章.md
python3 scripts/render.py 文章.md --theme paper
python3 scripts/render.py 文章.md --against 原稿.md --ledger 修改台账.md
python3 scripts/render.py 文章.md --deliver 交付目录/
python3 scripts/publish.py --html 交付目录/正文.html --meta 交付目录/正文.meta.json --preflight
```

## 边界

- 机器线索只定位回看原文的地址，不代替语义判决，不虚构事实、来源、引语或图片内容。
- 主题载入即校验字号层级与全部文字色 × 背景色对比度；320px 自动执行数据自适应与表格记录卡降级。
- **V16 有一处破坏性变更**：自定义 `assets/themes.json` 须把 `measure`（百分比页边）与 `grid.inset` 换成 `margin`（px），并为每个主题补 `code` 轴与 `type.peak_size`，否则载入即报错。包内六个主题已全部就位。
- 禁止路径越界、外链图片直引、危险 CSS/脚本与持久发布授权；草稿回读与删除永久素材均有独立强校验。
- 浏览器 PASS、API 回读 PASS、微信真机 PASS 严格分离；未执行项如实记为 `UNVERIFIED` 或 `BLOCKED`。

## 许可

[MIT](LICENSE.txt) © 2026 cpikeo。
