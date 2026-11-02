# V7 审计记录（先审计，后修改）

本文件记录 V7 优化开始前对 V6.0.0 的**真实代码审计**：每条都给出可复现的证据（命令、行号、样稿输出），
以及后续处置。审计只覆盖能验证的部分；无法验证的项目明确标 `BLOCKED/UNVERIFIED`。

审计环境：`git 54d188a`，Python 3.13.16，Chromium 156（Playwright headless），Noto Sans CJK SC 已安装。

## 0. 基线可复现状态

```bash
python3 tests/run.py            # 回归：全部通过（exit 0）
python3 tests/visuals.py        # Browser visual review: PASS（6 样稿×4 宽度 + 6 主题×4 宽度）
```

基线本身是健康的**工程**状态。V7 的缺口不在“测试红了”，而在
“测试能证明什么”：现有断言几乎全是结构/安全/一致性，编辑质量与视觉质量基本无机器可验证面，
且部分“编辑智能”结论可以由关键词命中直接得出。

## 1. 编辑智能（P0）

| 发现 | 证据 | 影响 |
|---|---|---|
| ① 现有“编辑智能”只有 11 个正则线索，**没有 AI 腔、机械扩写、同义反复、句长节奏、抽象名词空转**检测 | `grep -n "^CAUSAL\|^HEDGE\|^ATTRIB\|^CLICHE\|^ABSOLUTE\|^EMPH" scripts/editorial.py`（6 个正则，全文件） | 一组刻意写成 AI 腔的样稿（`/home/user/probe/slop.md`：套语开头 + “既是…也是…更是” + 三段“X很重要”) 只触发 3 条提示，其中 1 条还是误报的“章节失衡”；Gate 2 判 PASS |
| ② 逐节“信息增量”没有度量 | `_section_stats()` 只统计 `chars` 与 `kinds`；`argument_map[*].information_gain` 恒为 `"UNVERIFIED"` 字面量 | 长文中段复述无法定位，“每节要带来新信息”只是文档口号 |
| ③ 事实/推断/观点/未知**没有可表达的载体** | `render()` 的原语分发只有 `peak/note/data/bars/table/list/code/img/hr`；SKILL.md 也没有“未知项”写法 | 新闻/分析稿的“未知”只能写进正文段落，与事实同形，读者无法区分；`audit()` 也无从检查 |
| ④ 引文无出处不被检查 | `r.quote(b[0], b[1], kind)` 中 `src` 可为空；`editorial.py` 无对应线索 | 引文冒充事实的入口敞开 |
| ⑤ 作者声音没有画像，`--against` 不检测声音被抹平 | `compare_facts()` 只比数字/日期/引语/限定；无第一人称、疑问句、破折号、旁白等标记 | “改稿更顺但不像作者”无法被任何检查发现 |
| ⑥ 标题数字承诺未被覆盖 | `promise_ledger()` 只处理 `个/项/种/步…` 数量词与《》对象 | 标题写“37%”“9000 人”而正文无对应数字时，台账不报 |
| ⑦ 机器线索与语义判断的边界靠注释维持，报告里未结构化 | `_add(class=...)` 有 `mechanical/judgment`，但 `render_report()` 未分节呈现，也没有“这不是质量结论”的显式字段 | 读者容易把“命中关键词”读成结论 |

## 2. 视觉体系（P0）

| 发现 | 证据 | 影响 |
|---|---|---|
| ① 字号层级自相矛盾：`paper` 的导语 22px/700 **大于**章节标题 20px/600；`folio` 导语 24px/700 与 H2 24px/700 同级 | `assets/themes.json` `type.lead_size/heading_size`；`paper_business_390` 截图首屏 | 首屏出现两个同级入口，H2 反而弱于导语，层级链断裂 |
| ② `bone` 用字面 “SECTION” 反复标记每一节 | `same-draft_bone_390.jpg`：3 节均印 `SECTION`；`render.py h2()` `mode == "atelier"` 分支硬编码 `"SECTION"` | 机械重复的英文装饰标签，正是 SKILL.md 自己反对的做法 |
| ③ 主题轴的取值靠 `if/else` 的**隐式 default** 兜底，配置里的值可能根本没有独立视觉含义 | `h3: "label"`、`peak: "rule"`、`quote: "rule"`、`divider: "slash"` 在 `render.py` 中字面引用次数为 0，全部落到函数末尾的 return | 主题配置写错一个词会静默变成默认样式，测试也无法区分；文件里存在“看着可配、实则无效”的取值 |
| ④ 视觉决策字段只有写入、没有校验 | `composition/visual_concept/information_shape/asset_strategy/mobile_risk/design_rationale` 只在 `audit()` 被塞进 dict、在 `meta.json` 落盘；`grep` 无任何消费方 | “内容类型→视觉概念→构图→排版”的决策链没有强制环节，等于可写可不写 |
| ⑤ 首屏多入口只是“建议改” | `build()` 中 `s2.append(...)` | 与“首屏唯一视觉入口”的定位不一致 |

## 3. 构图与素材（P0）

| 发现 | 证据 | 影响 |
|---|---|---|
| ① 证据类图片与其解释文字之间没有邻接检查 | `compose_gate()` 只在 `role0 in {证据,数据}` 时要求 URL | 一张“证据”图可以孤零零夹在两段无关正文之间 |
| ② 没有“资料图/实拍/示意”的区分机制 | 角色词表只有 `ai/generated` 修饰词 | 扫描件、档案图、新闻图片一律按普通配图处理，出处不入图注要求 |
| ③ 封面只有比例检查，没有焦点安全区 | `COVER_BAND`、`COVER_RATIO`；预览两种裁切固定居中 | 主体偏侧的封面在 1:1 缩略里被切掉，只能人工发现 |

## 4. 渲染与移动端（P1）

| 发现 | 证据 | 影响 |
|---|---|---|
| ① 正文根节点用 `overflow-wrap:anywhere` | `render()` 末段 `body = f'...overflow-wrap:anywhere;...'` | 对中文/英文混排过激，任意位置断词；应只对长 URL 与不可拆数值局部开启 |
| ② 无微信环境验收的三级区分 | `references/publish.md` 有描述，产物只有 `验收.md` 的两级列表 | 浏览器 PASS／API 回读 PASS／真机 PASS 无法在产物里分别留痕 |

## 5. 输入转换（P1）

| 发现 | 证据 | 影响 |
|---|---|---|
| ① DOCX 图片的原始 alt 文本（`wp:docPr@descr`，Word 的“替换文字”）被丢弃 | `extract_docx.py` 写 `![](images/xx.png)`，未读取 `docPr` | 作者在 Word 里写的图注/出处静默丢失——正是“禁止静默丢失图片信息”要防的 |

## 6. 安全与发布（P1）

| 发现 | 证据 | 影响 |
|---|---|---|
| ① 发布审计日志字段未做脱敏断言 | `main()` 的 `audit()` 写 `body_sha256` 等；无测试断言 token/secret 不入日志 | 依赖“没人写错”，没有回归护栏 |
| ② 素材删除无二次确认 | `--delete-material` 直接调用 `delete_material()` | 不可逆操作缺少单次显式确认 |

## 7. 测试与验证（P0）

| 发现 | 证据 | 影响 |
|---|---|---|
| ① 六类文章“真实模型评估”无运行器、无固定提示词、无重复与方差记录 | `tests/editorial_eval.py` 只比对仓库内既有成对样稿；`evaluation/RESULTS.md` 自述“不是一次受控、可重复的真实模型生成实验” | 编辑质量提升无法被证明，也无法被发现回归 |
| ② 盲评包可生成但无评分表与回填格式 | `--blind-dir/--key-file` 只写文件 | 独立评审无法结构化回收 |
| ③ 无逐项来源核验记录结构 | `cases.json` 只有 source_url | “新增事实必须回源”无法留痕 |
| ④ 视觉回归只验“不溢出/不拆行/最小字号”，不验层级与节奏 | `tests/visuals.py inspect_page()` 的断言集合 | 字体层级矛盾（见 2.①）能全绿通过 |

## 8. 架构与冗余（P1）

| 发现 | 证据 | 处置 |
|---|---|---|
| ① 未使用局部变量 `palette`、`s1`/`s2` | `python3 -m pyflakes scripts/*.py tests/*.py` | 删除 |
| ② `tests/visuals.py` 未使用的 import（`PIL.Image/ImageChops/ImageStat`、`sync_playwright`） | 同上 | 改为按需局部导入（依赖检查仍需探测） |
| ③ 行内标记剥离逻辑在 `editorial.plain()` 与 `render.auto_digest()` 各写一遍 | `render.py auto_digest()` 里三个 `re.sub` 与 `editorial.plain` + `visible_len` 重叠 | 合并为一处（`editorial.plain`） |
| ④ `render.py` 1601 行 | 解析/组件/Gate/交付共享同一渲染契约 | **不拆**：拆分会把同一个契约分散到 4 个文件，收益低于成本（与 V6 结论一致，此处复核后维持） |
| ⑤ 主题轴取值无枚举校验（同 2.③） | — | 显式派发表 + 载入时校验，未知取值直接报错 |

## 9. 无法验证（必须如实标注）

- 真实微信账号、草稿 API 回读、后台重开、iOS/Android 真机与客户端裁切：`BLOCKED`（无凭证、无设备）。
- 独立外部盲评：`UNVERIFIED`（本会话内没有独立评审者）。
- 受控多模型复跑：本会话只有单一执行者，`temperature/top_p` 等采样参数不可钉住；
  V7 记录为“会话内自我复跑，n=3，非独立实验室复跑”，并保留提示词与输出哈希以便第三方复跑。

## 10. 复核中发现的自我印证风险（第二轮）

第一轮验收用的 AI 腔负例（`tests/v7.py` 的 `SLOP`）是**按规则表写的**，因此它能全绿并不证明规则对真实 AI 文风有效。

| 发现 | 证据 | 处置 |
|---|---|---|
| ① 不看规则、独立写一段典型 AI 腔（套语开头 + 首先/其次/再次/最后 + 排比 + 空洞号召结尾），线索命中 **0 条** | `prose_clues()` 对该样稿返回 0；而 `render.py` 只报了首屏套语（另一条规则） | 新增 `PROSE-ORDINAL`（一段 ≥3 个口语序号）、`PARALLEL-HEAD`（连续 ≥3 个分句同开头）、`HOLLOW-CLOSE`（结尾 ≥2 个号召词且无数字/来源/引语）；`CLICHE` 增补「总之，」；`ABSOLUTE` 增补「只要我们…就一定」「就一定能够」 |
| ② 只有一份负例，规则可以被调成只对它有效 | `tests/v7.py` 里唯一的负例是 `SLOP` | 增加第二份负例 `SLOP_FRESH`（独立写），并加反向检查 `_style_hits_in_corpus()`：六组案例 + 18 篇真实稿件上出现新线索即红 |
| ③ 评估脚本的线索码集合与线上规则脱节 | `tests/model_eval.py` 的 `STYLE_CODES` 未含新码 | 同步为与 `editorial.py` 一致的 17 个码 |

效果：独立样稿从 0 条线索 → 3 条（`PROSE-ORDINAL`、`HOLLOW-CLOSE`、`OPENING-CLICHE`×3、`CAUSAL-STRONG`）；32 个真实文件（18 篇评估稿 + 六组案例 + 示例）新增线索 **0** 条，误报为 0。`tests/v7.py` 50 → 54 项。
