# WeChat Article Skill · V7.0.0

把 Markdown、Word `.docx` 或纯文本编辑为可信、克制、适合手机阅读的微信公众号正文 HTML、独立预览与可核验交付记录。它是 AI 编辑与视觉排版 Skill，不是网页模板库、SaaS 或微信编辑器。

**工作顺序：THINK → EDIT → DESIGN → COMPOSE → RENDER → VERIFY。** 内容判断先于视觉；视觉概念先于装饰；删除 > 合并 > 简化 > 复用 > 新增。

## 包里有什么

| 路径 | 作用 |
|---|---|
| [`SKILL.md`](SKILL.md) | 唯一的编辑与设计判断入口：六类文章策略、文风线索、四类内容、主题选择、构图与验收口径 |
| `scripts/render.py` | Markdown → 正文 HTML / 浏览器预览 / `.meta.json`，含 Gate 1（HTML 安全）与 Gate 2（内容结构） |
| `scripts/editorial.py` | 编辑审计层：文风与机械扩写线索、逐节信息增量、作者声音画像、事实字面变化分类 |
| `scripts/check.py` | 发布正文的确定性风险检查（标签/属性/协议/CSS/图片路径白名单） |
| `scripts/publish.py` | 公众号官方 API：预检 → 草稿 → 可选发布 → 永久链接；默认止于草稿 |
| `scripts/extract_docx.py` | Word `.docx` → Markdown，图片保留 Word「替换文字」作为图注 |
| `scripts/safety.py` | 发布/删除操作的审计记录与凭证边界 |
| `assets/themes.json` | 六主题参数的**唯一来源** |
| `references/` | 按需读取的三篇：素材工艺、公众号工程边界、API 发布 |
| `config.example.json` | 凭证与开关示例（复制为 `config.json`，已被忽略） |

运行时只依赖 Python 3 标准库。本包不含测试与评估资产；回归、六类评估与四宽度截图在开发仓库中执行。

## 快速使用

```bash
# Markdown / 纯文本 → 正文 HTML、浏览器预览、meta
python3 scripts/render.py 文章.md

# 指定六种主题之一
python3 scripts/render.py 文章.md --theme frost -o 交付/正文.html

# 对照原稿的事实字面变化并校验五列表格修改台账
python3 scripts/render.py 文章.md --against 原稿.md --ledger 修改台账.md

# 一次交付源稿、HTML、预览、meta、记录、验收和本地素材
python3 scripts/render.py 文章.md --deliver 交付目录/

# Word 转换为 Markdown；转换后须对照原件核查
python3 scripts/extract_docx.py 文章.docx -o 文章.md
```

`render.py` 输出正文 HTML、独立浏览器预览和 `.meta.json`。预览中的工具栏、封面裁切、素材表及模拟标题/作者不会复制进正文。退出码 1 表示 Gate 1/2 有必须修事项；`todo` 允许预览但会被发布预检阻断。不要手改生成的 HTML——要改就回 Markdown 重渲。

## 六种主题

`paper` 静纸、`letter` 暖信笺、`ink` 酌墨、`frost` 北霜、`bone` 素作、`folio` 特稿。主题差异来自网格、字体、章节、导语、重点、引文、数据、表格、列表、图片及阅读节奏，不只换颜色。选主题的依据是内容关系与读者任务，允许内容驱动的局部偏离，不强制套用。

主题轴（`lead/heading/h3/peak/divider/quote/image/data/table/list`）的取值全集登记在 `render.py` 的 `THEME_AXES`，载入时校验：写错的取值直接报错，不会静默落回默认样式。字号层级是硬约束——**导语必须小于章节标题**（否则首屏出现两个同级入口），导语大于正文，H2 大于 H3，正文 15–17px，最小 12px。

## 编辑与交付边界

六类策略覆盖新闻、分析、教程、人物、评论、长文。`--against` 比对数字、单位、日期精度、正负号、限定、链接与直接引语；它只做字面比对，不是事实核真。新事实必须回源，机器线索不代替语义判断，每一处修改都要留下位置、问题、动作、收益和保留检查。

事实、推断、观点、未知四类内容在版式上分开：新闻与分析必须有未知项（`::: unknown` 单独成块），标题不得把推断写成已确认。

四宽度检查覆盖 320/360/390/430px；确实放不下的表格降级为保留全部字段的记录卡，不缩字号。

## 发布保护

```bash
cp config.example.json config.json
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --preflight
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json

# 仅本次显式授权正式发布，标题必须逐字一致
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json \
  --submit --confirm-title "逐字标题"
```

默认止于草稿。`config.json` 不接受持久发布授权；正式提交必须同时具有本次 `--submit` 和逐字匹配的 `--confirm-title`。删除永久素材需要 `--delete-material <ID>` 与逐字一致的 `--confirm-delete-media-id <ID>`，两项校验都在获取 access_token 之前完成——未确认的破坏性操作不会产生任何网络副作用。凭证不进文章、不进仓库、不进审计日志。详见 [`references/publish.md`](references/publish.md)。

## 验收口径（不要混用）

| 级别 | 能证明 | 不能证明 |
|---|---|---|
| 浏览器 PASS | 本地四宽度下的几何、字号、溢出、数值不拆行 | 微信清洗后的样式、真机字体、客户端裁切 |
| API 回读 PASS | 草稿字段与本地正文逐字一致 | 后台重开后的样式、手机端阅读 |
| 微信真机 PASS | 客户端实际渲染、保存重开、iOS/Android、封面两种裁切 | 长期稳定性、不同账号权限差异 |

`--deliver` 生成的 `验收.md` 默认把三级都写成 `UNVERIFIED`，并列出各自需要什么证据才成立；脚本不会把任何一级自动改成 PASS。**当前状态如实读作**：独立外部盲评 `UNVERIFIED`（没有第三方回填前不给偏好结论）；逐项第二来源核真与微信真机在无账号/设备时为 `BLOCKED`。不伪造结果，也不以合成测试冒充真机验收。

## V7 变更摘要

| 方向 | 实际改动 |
|---|---|
| 编辑判断 | 15 条文风/机械扩写线索（AI 腔、模板排比、主语复读、同义反复、句长过齐、定语堆叠、推断跳步、口语序号、排比开头、空洞呼吁结尾）；线索分 mechanical / judgment / verification 三类呈现，命中只作地址不作判决；`section_gain` 逐节信息增量；`voice_profile` 作者声音画像，`--against` 会报「声音被抹平」 |
| 四类内容 | 新增 `::: unknown` 原语：事实 / 推断 / 观点 / 未知在版式上分开；新闻或分析缺未知项会被提示 |
| 视觉 | 主题轴登记 + 载入时校验（写错取值不再静默落回默认）；字号层级成为硬约束（导语 < H2）；删掉 `bone` 的 `SECTION` 装饰标签；正文断行由 `anywhere` 改为 `break-word`；章节标记不再复读标题 |
| 构图 | `资料/实拍` 职责必须写明出处与授权；证据类图片必须紧邻其解释文字；决策链逐环标 DECLARED / INFERRED / MISSING |
| 安全 | 删除永久素材需逐字二次确认且在取 token 之前校验；审计日志字段白名单；DOCX 图片的 Word 替换文字不再丢失 |
| 冗余 | 合并重复实现（盲评包、行内标记剥离）；删除未用变量与导入；`render.py` 复核后仍不拆分——解析、组件、门禁与交付共享同一个渲染契约，拆开只会把契约分散 |

## V6 审计摘要

| 发现（证据） | 处理 |
|---|---|
| README 曾链接不存在的审计文件；文档与代码版本不一致 | 统一版本；文档只保留能对上代码的段落 |
| 历史运行日志与本机路径混在仓库里，不能复现当前状态 | 删除；截图与临时输出不进运行时 |
| 旧主题测试强制每个结构键都不同，容易奖励机械差异 | 改为真实稿四宽度、同稿六主题与去色结构比较 |
| 截图输出目录（约 30MB）误放在运行时资产区 | 移出运行时，改为按需生成且被忽略 |
| `render.py` 较大，但各段共享同一渲染契约 | 保持单一运行时渲染器，不为拆分而加模块 |
| 真实模型执行、独立盲评与微信真机无可调用环境 | 标为 `BLOCKED/UNVERIFIED`；不冒充测试结果 |

## 许可

[MIT](LICENSE.txt) © 2026 cpikeo。本包不含任何第三方图片或字体资产，仅 MIT 许可适用于全部内容。
