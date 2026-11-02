# V4.0 审计：优化前后、文件账与未验证项

基线 commit `09bbf40`（V3.0.0），V4.0.0 的主体提交是 `7f7cb60`。本文件记录实际改动与可核对结果；**2026-11-02 按要求删除了 `evaluation/` 与 `assets/shots/`**，因此文中部分数字无法再从本仓库重跑，见 §7。

## 0. 摘要

| 维度 | V3.0.0 | V4.0.0 | 现在怎么核对 |
|---|---|---|---|
| 编辑判断 | 渲染器内嵌少量文本检查，无类型策略、无承诺台账、无事实单元 | 独立 `editorial.py`：6 类型策略、31 处检查（18 mechanical／13 judgment）、承诺台账、事实单元、台账五列 | 回归 ⑬；`render.py --against`、`--ledger` |
| 视觉语言 | 配置有 6 套轴值，渲染层把网格差异塌成一套 | 新增 `grid` 轴并落到渲染层：正文 15/16/17px、段首缩进 0/32px、行距 1.72–1.95、导语 17–24px、图注 12–14px | 回归 ③⑩；`--shots` 的六人格截图 |
| 构图素材 | 图片职责已解析，人格层缺默认处理 | 六种人格默认处理 + 九种表达覆盖；每条边只声明一次 | 回归 ⑭、⑯ |
| 移动端 | 表格靠 16px 字号与折行硬排，无排版测量 | 320px 单次判定 + 记录卡降级 + 短标签下限；`--shots` 实测最小字号／每行字数／首屏字数 | 回归 ⑭；`assets/shots/REVIEW.md`（需自己生成） |
| 输入转换 | 脚注／尾注／批注只给警告，正文会被静默丢弃 | 含 `<w:t>` 即阻断、不产文件；页眉页脚单独提示 | 回归 ⑮ |
| 测试 | 124 条断言 | **16 组、163 条断言** | `python3 tests/run.py` |
| 架构 | 判读混在渲染器里 | 判读独立成模块；`SKILL.md` 23,003 → 18,494 B 且覆盖更多内容 | §6 文件账 |

结论：V4 的增益在**判断可追溯**与**窄屏不靠硬塞**两件事上，不在主题或组件数量。自动化通过不构成内容或审美合格的证明（§8）。

## 1. 方法

- 基线：`git worktree add /tmp/v3 09bbf40`，V3、V4 用同一份稿子渲染后再比。
- 渲染：`python3 scripts/render.py <稿> --theme <人格> -o <文件>`；截图用 Chromium（Playwright，deviceScaleFactor=2）。
- 实测口径：`getComputedStyle` 取字号／行距／缩进；`scrollWidth > clientWidth` 判溢出；表格单行宽用同字体隐藏 span 量，不做字符数估算。
- 回归：`python3 tests/run.py`；截图：`python3 tests/run.py --shots --shoot <稿>`。

## 2. 编辑质量

| | V3 | V4 |
|---|---|---|
| 类型策略 | 无（所有文章一套检查） | 6 种：新闻／分析／教程／人物／评论／长文，各给入口、结构、证据要求、常见失败 |
| 标题承诺 | 只查数量承诺 | 数量承诺 + 书名号对象 + 问题型标题，输出「期望／可见／状态／位置」 |
| 事实保留 | 无跨稿比对 | `--against` 比对数字+单位／日期／链接；消失须在 `removed_facts` 声明，新增须就近可核 |
| 修改台账 | 自由格式 | 五列强制（位置／问题／动作／收益／保留检查），位置必须回得到正文 |
| 判断边界 | 未区分 | 每条问题带 `class`（mechanical/judgment）与 `needs`（none/editor/fact-check） |

V4 交付时曾用 6 个真实来源样本（新闻／分析／教程／人物／评论／长文，三档复杂度）跑通全部确定性检查，当时结论是 6/6 通过、事实单元 0 未声明丢失。**这套样本与结果报告已按要求删除**，现在只能用你自己的稿子复跑同一套规则：

```bash
python3 scripts/render.py 稿.md --against 原稿.md --ledger 台账.md --deliver 交付/
```

## 3. 视觉语言

### 3.1 结构轴

`assets/themes.json` 在 V3 已有 heading/lead/quote/peak/data/table/list/image/divider/type/h3 各 6 个取值，但**网格轴只有 1 个取值**，渲染层也没有把差异落到正文。V4 拆出 `grid`（`inset`／`paragraph`／`indent`／`body`／`caption`／`chapter_gap`／`paragraph_gap`），V3 1 → V4 6 个取值。

### 3.2 同稿实测（商业分析优化稿，390px，Chromium；稿件已随 evaluation 删除）

| 量 | V3 六人格取值 | V4 六人格取值 |
|---|---|---|
| 正文字号 | 16 / 16 / 16 / 16 / 16 / 16 | 16 / 16 / 16 / **15** / **17** / 16 |
| 段首缩进 | 0 / 0 / 0 / 0 / 0 / 0 | 0 / **32px** / 0 / 0 / 0 / 0 |
| 行距 | 1.75 / 1.80 / 1.80 / 1.72 / 1.85 / 1.75 | 1.75 / **1.90** / **1.90** / 1.72 / **1.95** / 1.75 |
| 导语字号 | 18 / 18 / 19 / 17 / 18 / 22 | **22** / 19 / 19 / 17 / 18 / **24** |
| 导语字重 | 400 / 400 / 400 / 500 / 400 / 700 | **700** / 500 / 400 / 500 / 400 / 700 |
| 320px 每行字数 | 16 ×6 | 16 / 16 / 16 / **20** / 16 / 16 |

15 个在该页可测的结构属性里，随人格变化的从 3 个增至 7 个。回归用**网格签名唯一性**（7 个网格键组成的元组不得重复）与四轴阈值（body ≥3 种、caption ≥2 种、chapter_gap ≥4 种、inset ≥2 种）把差异钉住，避免退回「只换颜色」。上表是删除前的测量，现可用任意稿件 + `--shots` 复现同样的量法。

### 3.3 导语与组件

- 导语按 `[。！？；]` 拆成 `span{display:block}`，folio 24px 导语不再从句子中间折行；行高 1.55。
- 表格行线从单元格挪到 `tr`，边线只出现一次，不再因单元格内距叠成双线。
- `img()` 重写：人格默认（soft/inkline/report/mat/folio/flush）+ 表达覆盖（hero/full-width/inset/plate/detail/sequence/comparison/evidence/explainer/data）；每条边只声明一次（hero 用强调色底线**替换**人格底线）；`detail` 保持原比例仅内缩 5%；图注按职责取字号；GIF 前缀；无职责图片渲染为「待补素材」占位而不是崩溃。
- V3 的图片职责解析本来就存在（同一页 7 张图 5 种 wrapper），所以不宣称「V3 没有职责」；V4 的差别在人格默认处理与单边一线。

## 4. 移动端：一次自我回归与校准

V4 最初的表格宽度模型按「ASCII 0.5em + 每列 20px 内距」估算，把一张 4 列 8 位数的表判成放不下，在 320 与 390 都降级成记录卡。用 Chromium 量真实字宽后（Noto Sans CJK：数字 7.78px／汉字 14px／字号 14px；内距实测 2×6 或 2×7px），发现该表真实需要 270px、可用 288px，**本来放得下**。这是 V4 自己引入的回归，已修：

1. 拆出 `text_px()`（纯字宽）与 `cell_min_px(text, pad)`（加该人格真实内距），`table_pad()` 给出 12/14px。
2. `table_fits` / `col_widths` 同步接受 `pad`；列宽下限加 2px（`TABLE_SLACK`），消除 `table-layout:fixed` 小数取整造成的「一季／度」孤字。
3. 短标签下限从「仅表头」扩到任何 ≤4 字且无空格的单元格——正文的「一季度」和表头的「观察对象」是同一种断行风险。
4. 数字 `nowrap` 改为**先算可用像素再决定**：够就不断行，不够允许折行，不再撑破单元格。

当时核查范围：4 篇稿 × 6 人格 × 320/360/390/430 = 96 次渲染，0 处元素溢出、0 处短标签或数字折行。现在这条结论可用你的稿件重跑（`--shots` 会在四宽度做元素级溢出检查），或直接用上面的量法自测。

**不做响应式断点**：微信剥离媒体查询，所以窄屏形态按 320px 一次判定，同一 HTML 各宽度同形；`bone` 因 6px 内衬在 320px 更早改用记录卡。

## 5. 输入转换与交付

- V3 对 `footnotes/endnotes/comments` 只打印一条「须人工核对」，正文内容会被**静默丢弃**；V4 改为：这些 XML 里出现 `<w:t>` 就阻断转换、不写任何输出并列出文件。页眉页脚仍不阻断，但单独提示。
- `--deliver` 一次产出源稿、正文、预览、meta、修改记录、验收与素材；回归 ⑯ 校验产物齐全且互相一致。
- 发布侧未改协议：默认只建草稿，正式发布须本次 `--submit --confirm-title`，配置不能保存授权；预检比对渲染器版本、主题配置指纹与文件哈希。

## 6. 文件账

四类分法：**运行时**（`scripts/`、`assets/themes.json`）、**开发测试**（`tests/`）、**交付资产**（`assets/themes.html`、`examples/`、`references/`）；原「评估证据」类（`evaluation/`）已按 §7 删除。

| 动作 | 文件 | 理由 |
|---|---|---|
| 新增 | `scripts/editorial.py` | 编辑判读与排版执行分离；`render.py` 只调用，不再内嵌 31 处判读 |
| 合并 | `render.py` 的 `locate_row()` → `editorial.locate()` | 台账位置回查在 CLI 与审计里是同一件事，两处实现会漂移 |
| 删除 | `render.py` 未使用的 `difflib`／`visible_len`／`TYPES` 导入 | 死导入；`TYPES` 已由 `editorial.resolve_type` 承担 |
| 压缩 | `SKILL.md` 23,003 B → 18,494 B（-20%） | 首版 V4 有整段重复（流程表与正文、语法表与分节）；合并成一张语法表，判断条目不减 |
| 保留 | `references/*.md` | 素材工艺、平台边界、发布接口按需读取，从 SKILL 正文剥离才让单文件入口成立 |
| 保留 | `assets/themes.html` | 生成物但入库：六人格对照的可视基线，回归校验它能被 `--specimen` 精确再生成 |
| 删除 | `tests/editorial_eval.py`、`evaluation/` | 见 §7：样本集与评估报告按用户要求移除 |
| 删除 | `tests/visuals.py` | 它的唯一职责是重出 `evaluation/visual/` 的对照图，目录不存在后无用 |

没有删除运行时脚本：`scripts/{render,editorial,check,publish,extract_docx,safety}.py` 逐个核对过调用方与回归覆盖，均有实际职责。

## 7. 交付物移除记录（2026-11-02）

按用户明确要求删除：

| 删除 | 体积 | 直接后果 |
|---|---|---|
| `assets/shots/`（git 忽略的产物） | 43 MB | 本机不再保留上一轮截图包；`python3 tests/run.py --shots` 一条命令重出 |
| `evaluation/`（样本、`RESULTS.md`、视觉对照图） | 5.3 MB | 6 样本评估与 V3/V4 视觉对照无法从仓库重跑；`tests/run.py` 的 ⑬、六人格截图源、`tests/visuals.py` 依赖随之调整 |

同步改动：删 ⑬（真实来源评估），六人格截图改用回归内置的合成对照稿（`tests/run.py` 里生成，覆盖导语／引文／章节／peak／列表／表格／data），删 `tests/editorial_eval.py` 与 `tests/visuals.py`，CI 的 `--against` 改为对 `examples/draft-handoff.md` 自比对冒烟。回归从 17 组 169 条变为 **16 组 163 条**，仍全绿。

**代价要说清楚**：仓库现在不能自证「编辑改写前后」与「六人格视觉前后」这两类证据，只能自证规则、渲染与发布保护。要恢复，需要重新准备带许可与来源的样本稿，并按 `--against`／`--shots` 重跑；`git show 7f7cb60` 仍可取回被删内容。

## 8. 未验证（UNVERIFIED）

1. **独立外部读者 A/B 盲测**：随 `editorial_eval.py` 一起删除，当前没有任何盲测结果，也没有生成工具。现有检查是同团队规则核对。
2. **逐项第二来源核真**：事实单元比对只认字面，未逐条回查第二个独立来源。
3. **微信草稿 API 回读**：`publish.py` 的接口路径只有 mock 契约测试，没有真实 AppID 下的建稿、回读、字段核对与后台重开检查。
4. **iOS／Android 真机与封面双裁切**：浏览器四宽度截图不等于真机；2.35:1 与 1:1 裁切只在预览里模拟。

另两项属于**推断**：WebView 对 `table-layout:fixed` 小数百分比的取整、微信编辑器对 `display:flex` 记录卡的清洗。

## 9. 复跑

```bash
python3 tests/run.py
python3 scripts/render.py 稿.md --against 原稿.md --ledger 台账.md --deliver 交付/
pip install playwright && python3 -m playwright install --with-deps chromium
python3 tests/run.py --shots --shoot examples/draft-handoff.md
```
