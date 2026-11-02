# WeChat Article Skill · V8.0.0

把 Markdown、Word `.docx` 或纯文本编辑为可信、克制、适合手机阅读的微信公众号正文 HTML、独立预览与可核验交付记录。它是 AI 编辑与视觉排版 Skill，不是网页模板库、SaaS、CMS 或独立软件系统。

**工作顺序：THINK → EDIT → DESIGN → COMPOSE → RENDER → VERIFY。** 内容判断先于视觉；视觉概念先于装饰；删除 > 合并 > 简化 > 复用 > 新增。机器负责确定性检查，模型/编辑负责语义与审美判断。

## 包里有什么

| 路径 | 作用 |
|---|---|
| [`SKILL.md`](SKILL.md) | 唯一核心入口：六类编辑策略、事实边界、六主题、构图与验收口径 |
| `scripts/render.py` | Markdown → 正文 HTML / 浏览器预览 / `.meta.json`，含 Gate 1/2 与交付 |
| `scripts/editorial.py` | 编辑候选：文风、重复、标题承诺、逐节增量、作者声音与事实字面变化 |
| `scripts/check.py` | 标签、属性、协议、CSS、图片路径白名单与 HTTP(S) URL 校验 |
| `scripts/publish.py` | 公众号官方 API：离线预检 → 草稿 → 可选发布；默认止于草稿 |
| `scripts/extract_docx.py` | Word `.docx` → Markdown；保留每张图片自己的替换文字 |
| `scripts/safety.py` | 本地资源路径边界、文件哈希与颜色对比度 |
| `assets/themes.json` | 六主题参数的**唯一来源** |
| `references/` | 按需读取：素材工艺、公众号工程边界、API 发布 |
| `config.example.json` | 凭证与开关示例；复制为已被忽略的 `config.json` |

运行时只依赖 Python 3 标准库。正式包不含测试、评测集、真实样稿、截图、基准报告或开发文档。

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

`render.py` 输出正文 HTML、独立浏览器预览和 `.meta.json`。预览中的工具栏、封面裁切、素材表及模拟标题/作者不会复制进正文。退出码 1 表示 Gate 1/2 有必须修事项；`todo` 允许预览但会被发布预检阻断。不要手改生成 HTML——要改就回 Markdown 重渲。

## 六类编辑策略

新闻、分析、教程、人物、评论、长文分别核对不同的读者任务、入口、证据、反例/失败路径与作者声音。类型可以复合，策略不是写作模板。

- 标题数量、对象、问题和最高级只生成可定位的复核事项；**H2 数量不等于语义兑现**，无法在普通段落中机器计数时不作硬判决。
- 文风命中只是回原文的地址。数字时间线不当作主语复读，日历日期不与统计数字共用来源规则，空泛收尾只检查最后一个实质正文段。
- `--against` 比对数字、单位、日期精度、正负号、限定、链接与直接引语；引号前后的归属动词都可识别。它只做字面比对，不是事实核真。
- 新闻与分析须明确未知项；`::: unknown` 可把未知单独成块。事实、推断、观点与未知的语义判定由编辑完成。
- 修改台账五列：`位置｜问题｜动作｜收益｜保留检查`。无法说明具体收益的润色不做。

## 六种主题

`paper` 静纸、`letter` 暖信笺、`ink` 酌墨、`frost` 北霜、`bone` 素作、`folio` 特稿。差异来自网格、字体、章节、导语、重点、引文、数据、表格、列表、图片及阅读节奏，不只换颜色。选择依据是内容关系与读者任务，允许内容驱动的局部调整。

主题轴（`lead/heading/h3/peak/divider/quote/image/data/table/list`）的取值全集登记在 `render.py` 的 `THEME_AXES`，配置载入时逐项校验。字号层级是硬约束：导语 < H2，导语 > 正文，H2 > H3，正文 15–17px，最小 12px。去色后仍须凭结构辨认主题。

数据组件先计算数值在 320px 可用宽度，再选择分栏、左右记录或上下记录；长表格降级为保留全部字段与顺序的记录卡，不缩字硬塞。

## 图片与构图

每张图先声明职责：入口、解释、证据、对比、结构、场景、叙事、隐喻、停顿、数据、资料或实拍。说不出信息增量就不配图。解释/证据靠近其说明对象；多图顺序与比较口径必须可解释。

资料图/实拍须写明出处与授权；证据/数据图须给可核对来源，生成示意不得承担真实证据职责。封面检查 2.35:1 与 1:1 两种本地模拟裁切，但不冒充微信各入口的真实裁切。

## 发布保护

```bash
cp config.example.json config.json
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --preflight
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json

# 仅本次显式授权正式发布，标题必须逐字一致
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json \
  --submit --confirm-title "逐字标题"
```

默认止于草稿。`config.json` 不接受持久发布授权；正式提交必须同时具有本次 `--submit` 和逐字匹配的 `--confirm-title`。删除永久素材需要 `--delete-material <ID>` 与逐字一致的 `--confirm-delete-media-id <ID>`，两项校验都在获取 access_token 之前完成。凭证不进文章、仓库或审计日志。详见 [`references/publish.md`](references/publish.md)。

## 验收口径（不要混用）

| 级别 | 能证明 | 不能证明 |
|---|---|---|
| 浏览器 PASS | 本地 320/360/390/430px 的几何、字号、溢出、数值不拆行、复制事件 | 微信清洗后的样式、真机字体、客户端裁切 |
| API 回读 PASS | 草稿字段与本地正文逐字一致 | 后台重开后的样式、手机端阅读 |
| 微信真机 PASS | 客户端实际渲染、保存重开、iOS/Android、封面两种裁切 | 长期稳定性、不同账号权限差异 |

`--deliver` 生成的 `验收.md` 默认把三级都写成 `UNVERIFIED`；脚本不会自动改成 PASS。没有授权账号或设备时，API 回读与微信真机分别为 `BLOCKED`；独立外部盲评和逐项第二来源核真未执行时也必须标 `UNVERIFIED`。

## V8 当前实现要点

| 方向 | 实现 |
|---|---|
| 编辑判别力 | 语义不确定的标题承诺不再硬阻断；修正普通词最高级误判、数字主语复读、非结尾口号、后置引语归属与证据窗口 |
| 视觉与移动 | 保留六主题结构语言；数据布局单次决策并共用宽度余量；四宽度与复制由开发评测验证，不写入运行时 PASS |
| 构图 | 补齐入口/叙事职责；保留来源、授权、邻接与生成图证据边界 |
| 架构 | `themes.json` 单一来源；渲染只审计一次；Gate 2 在同文件内分资产/数据/结构职责；无新增运行依赖 |
| DOCX 与安全 | 同段多图按关系 ID 保留各自替换文字；原文链接与正文链接共用有效主机校验；文件显式关闭 |

V7 生成的 sidecar 带有旧版本号，发布预检会要求用 V8 重渲；不要手改版本字段或哈希。命令行与 Markdown 原语保持兼容。

## 许可

[MIT](LICENSE.txt) © 2026 cpikeo。本包不含第三方图片或字体资产。
