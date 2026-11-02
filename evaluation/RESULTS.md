# Editorial Evaluation Results · V7

本页只写**已经执行并留下证据**的事，以及**没有执行**的事。V6 页面的自述仍然有效：仓库内的成对样稿
是既有编辑稿的回归，不是受控生成实验。V7 补上了后者，同时把「自动指标 / 人工评审 / 未完成」三类分开。

## 1. 确定性回归（可复算）

| 套件 | 覆盖 | 本轮结果 |
|---|---|---|
| `tests/run.py` | Gate 1/2、解析、事实限定、主题配置、交付包、发布保护、DOCX 边界 + V7 新增断言 | PASS |
| `tests/v7.py` | 文风线索（含独立负例与真实语料反向检查）、未知项、声音比对、决策链、主题轴校验、层级断言、发布删除授权、DOCX 替换文字 | 54/54 PASS |
| `tests/visuals.py` | 六篇真实来源样稿 × 320/360/390/430px；同一含图文章 × 六主题 × 四宽度；去色同稿比较；**新增**导语/H2 层级断言与章节标记复读断言 | PASS（15 对去色比较） |
| `tests/editorial_eval.py --check-report` | 六类成对样稿的字面与结构检查、台账、报告新鲜度（机器报告：`evaluation/pairs-report.md`） | PASS |
| `python3 -m pyflakes scripts/*.py tests/*.py` | 未用变量/未用导入 | 干净 |

机器能证明的只到这里：解析、版式几何、安全边界、字面一致性。**它证明不了稿子写得好。**

## 2. 六类文章受控评估（V7 新增，会话内执行）

- 协议：`evaluation/model-eval/prompts/edit.md`（v7-eval-1）+ 六份类型要求，输入与提示词指纹冻结。
- 执行：单一执行者，每类 3 次重复，共 18 篇；采样参数**无法钉住**，已在 `run.json` 声明。
- 详细指标、逐篇明细、重复间稳定性：`evaluation/model-eval/REPORT.md`
- 首轮失败与修正记录：`evaluation/model-eval/RUN-NOTES.md`

修正后只有三个不变量，且都由 `tests/model_eval.py` 复算：**18/18 Gate 1/2 通过、无源新增 0、未兑现标题承诺 0。**
逐类指标（字数、线索密度、事实字面保留率、句长σ、最长段、决策链缺环）只放在
`evaluation/model-eval/REPORT.md`（脚本生成），本文件不再抄一份——两处各写一遍就会漂移。

**这些数字说明什么、不说明什么：**

- 说明：在固定提示词下，六类稿件都能通过 Gate 1/2，且没有凭空新增事实、没有未兑现的标题数字承诺；
  文风线索密度低（0–1.15/千字），说明模板排比与主语复读没有复发。
- 不说明：不能证明「比原稿更好」，也不能证明「换了模型仍成立」。同一执行者在同一会话内重复三次，
  第三次已见过前两次的思路，这不是独立实验室复跑。
- 首轮**不是满分**：4 篇被 Gate 2 拦下（data 块缺紧邻来源、标题承诺与列表不一致），另有 3 处
  执行者自己写出的错误（凭空补年份、编造访问日期、标题写人数量词而正文不写），已逐条修正并记录。
  这类失败恰恰是评估的价值所在；把它藏起来会让整份报告失效。

## 3. 盲评（未执行）

```bash
python3 tests/model_eval.py --blind --run-dir evaluation/model-eval/runs/in-session-v7 \
  --out evaluation/model-eval/x --key /tmp/wechat-blind-key.json
```

生成内容包括每组 A/B 两份稿与 `FORM.md`（标题兑现 / 信息增量 / 逻辑 / 事实与限定 / 作者声音 /
手机可读性 / 总体偏好 + 依据引用），答案 key 单独存放且不入库。

- **独立外部盲评：UNVERIFIED。** 本会话没有独立评审者，不报告偏好胜负，也不给自评分。
- 任何「优化稿更好」的结论，都必须等第三方按表单回填后才成立。

## 4. 视觉回归（浏览器，非审美评分）

- `tests/visuals.py` 本轮新增两类断言，它们抓的是**层级链断裂**而非美感：
  1. 导语字号 ≥ 章节标题 → 首屏两个同级入口（V6 的 `paper` 22px 导语 / 20px H2 曾被此断言抓住前先在载入校验拦住）；
  2. 同一章节标记连续出现 ≥3 次 → 机械复读（V6 的 `bone` 曾每节印 `SECTION`，已改为留白 + 发丝线）。
- 截图与 `REPORT.md` 生成在被忽略的 `evaluation/visual-review/`，只作审阅输入；该目录不随仓库分发，删掉后用 `python3 tests/visuals.py` 原样重建（已核：与旧输出逐字节一致）。每次运行都会清理本轮不再生成的旧截图。
- **人工审美评审：UNVERIFIED。** 浏览器几何通过不等于好看。

## 5. 逐项来源核验与微信验收（未执行）

- **真实来源逐项核真：UNVERIFIED。** 本仓库只做字面比对；`cases.json` 里的来源与许可备注不是本轮核真记录。
- **微信账号 / 草稿 API 回读 / iOS·Android 真机 / 客户端裁切：BLOCKED。** 无凭证、无设备。
  验收文件（`render.py --deliver` 生成的 `验收.md`）把三级状态分开列出，默认全部 `UNVERIFIED`。

## 6. V7 审计与处置

完整审计（每条带证据）见 [`AUDIT-V7.md`](AUDIT-V7.md)。摘要：

| 发现 | 处置 |
|---|---|
| 「编辑智能」只有 11 条正则，无 AI 腔/机械扩写/同义反复/抽象名词线索 | 新增 12 条形态线索 + `section_gain` + `voice_profile`，全部标 `mechanical` 并附命中依据 |
| 事实/推断/观点/未知无表达载体 | 新增 `::: unknown` 原语；新闻/分析缺未知项会被提示 |
| 六个视觉决策字段只写不校验 | 新增 `decision_chain()`，逐环 DECLARED/INFERRED/MISSING |
| 主题轴取值靠隐式默认兜底（`h3=label`、`peak=rule`、`quote=rule`、`divider=slash` 无分支） | `THEME_AXES` 派发表 + 载入校验；补 `label`/`rules`/`columns` 真实分支；未登记取值直接报错 |
| 字号层级自相矛盾（paper 导语 22 > H2 20；folio 导语=H2=24） | 配置修正 + `validate_themes()` 硬约束 + 浏览器层级断言 |
| `bone` 每节印 `SECTION` | 删除该装饰标签 |
| 正文根 `overflow-wrap:anywhere` 会打断中文 | 改 `break-word`；`anywhere` 只留给表格/代码等固定布局容器 |
| Gate 1 的「建议改」算完即丢 | 并入 Gate 2 建议；`s1` 未用变量消除 |
| `资料图/实拍` 无出处要求；证据图可孤立存在 | 新增职责词与两条 Gate 2 规则 |
| DOCX 图片的 Word「替换文字」被丢弃 | 提取 `wp:docPr@descr` 进图注 |
| 删除永久素材无二次确认；审计日志字段无白名单 | 逐字 `--confirm-delete-media-id`（取 token 前校验）+ 字段白名单 |
| 无受控六类评估、无盲评表单、无声音比对 | `tests/model_eval.py` + 盲评包 + `compare_voice()` |

## 7. 复现

```bash
python3 tests/run.py
python3 tests/visuals.py            # 需 playwright + Noto Sans CJK
python3 tests/editorial_eval.py --check-report
python3 tests/model_eval.py --report --run-dir evaluation/model-eval/runs/in-session-v7 \
  --out evaluation/model-eval/REPORT.md
```
