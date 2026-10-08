# v3 重构报告：从组件库到 Art Director

## 1. Architecture Before / After

Before（v2）：文章类型 → Theme → Recipe → Component → 手工拼 HTML → 双脚本校验

- 大脑 = 40KB 的 themes.md（60+ HTML 块，模型逐块复制）
- 判断 = 分散在 SKILL.md + design-system.md 的规则清单
- 渲染 = 模型手写 HTML（每篇输出 30–50KB，必然带错再修）

After（v3）：`UNDERSTAND → JUDGE → EDIT → COMPOSE → RENDER → VERIFY`

- 大脑 = Decision（9 行判断）+ `references/decide.md`
- 手 = `scripts/render.py`（确定性渲染器，HTML 零手写）
- 约束 = `assets/themes.json`（每主题 20 个键）+ Gate 1/2（随渲染自动跑）

## 2. 删除清单

文件（13 删、2 搬家）：

| 删除 | 原因 |
|---|---|
| `references/themes.md`（40KB） | 最大 Context 杀手；60+ HTML 块由渲染器 + tokens 替代 |
| `references/design-system.md` | 判断收敛进 `decide.md`（1/5 体量）；能代码化的进脚本 |
| `references/platform-rules.md` | 收敛进 `platform.md` + `check.py`（机器可验证的不再靠人阅读） |
| `references/theme-generator.md` | 新主题 = 加 20 个键；"生成 45–75 个 Block"流程作废 |
| `references/format-normalize.md` | 归一化只剩 docx 一行命令，进 SKILL.md 路由表 |
| `references/content-editing.md` + `scripts/content_consistency_check.py` | 润色是通用写作能力，不需要 skill 专属规则与脚本 |
| `references/eval-cases.md` | 由 `eval/` 可执行回归替代（含 expected diff） |
| `scripts/validate_gzh_html.py` + `scripts/design_quality_check.py` | 合并为 `check.py`（Gate 1）+ render 内置 Gate 2，单次调用 |
| `scripts/component_lint.py` | 没有组件库可 lint |
| `scripts/wrap_preview.py` + `assets/preview-template.html` | 预览生成并入 render.py 一次调用 |
| `CHANGELOG-v2.md` | 历史进 git，工作区只留现状 |
| `assets/sample-article.md` | 删除（v2 旧样本，无消费者） |

规则/字段：

- "每段 1–2 处关键词下划线" → Selective Emphasis（全篇 ≤3，多数段落零强调）
- `--accent-quota` 配额计数 → 渲染器天然只输出 ≤3 处强调，Gate 2 只做超标提醒
- 配方表（文章类型→组件）→ Composition 一句话，由 Decision 决定
- 组件编号体系（S1–S14 / W1–W21 / K1–K14）→ 11 个原语
- 三类 TAG、9 维定位表、14 套色板预设 → 删除（新主题流程不再需要）
- 解释性长文（"为什么不能用 SVG/图标库"等）→ 删，check.py 直接拦截

## 3. 保留清单（及为什么必须存在）

| 保留 | 为什么 |
|---|---|
| 三套主题人格 | 压缩为 tokens（每套 20 个键，零 HTML），覆盖克制/温暖/笃定 |
| 图章圆环语言 | 收敛为 seal 机制（编号/转场/署名统一），不是散落组件 |
| 6 级字号、15px 正文 | 进渲染器常量，全篇强制一致 |
| leaf 包裹、空元素占位、max-width 图片 | `check.py` 确定性检查，粘贴后不丢样式的底线 |
| `scripts/publish.py`、`scripts/extract_docx.py` | 有真实消费者，原样保留，仅搬家到 scripts/ |
| Editorial QA | 收敛为 Gate 3 四问（首屏/高潮/删减/连续性） |

## 4. 最短生产路径

```
输入.md →（docx 先 extract）→ 写 Decision → 写 Composed Markdown
  → render.py 一次调用（HTML + 预览 + Gate 1/2）→ 通读预览 → 交付/发布
```

Tool calls：读输入(1) + 写 compose(1) + render(1) + 看预览(1) = **4**。
v2 实测：读 SKILL + 读 design-system + 读 themes（40KB）+ 写 HTML（多段）+ validate + design_check + 修错重跑 ≈ **10+**。

## 5. Context Reduction

- 每次任务常驻 Context：65,802 B（SKILL + design-system + themes）→ 6,997 B（SKILL 4,179 + decide 2,818），**降 89%**。
- 文本总量：158,035 B / 3,124 行 → 80,957 B / ~1,630 行，**降 49%**（含新增可执行回归；另有 expected fixtures 36KB 与回归照片 405KB 为机器/测试消费，不进任务 Context）。
- 质量保证从"读更多规则"变为"确定性执行"：HTML 正确性由渲染器保证，不依赖模型记忆 60 个组件。

## 6. Tool Call Reduction

- 校验 2 次调用 → 随渲染自动跑，0 次额外调用。
- 预览 1 次调用 → 并入渲染。
- 手写 HTML（多段输出，易错修）→ 写 Composed Markdown（纯文本，短 60%）。
- 输入只读一次；结构、主题、主张各只判断一次。

## 7. Design Judgment Upgrade（新增的判断，不是组件）

1. **Decision 九行**：Audience / Purpose / Core Claim / Tone / Density / Visual Anchor / Image Strategy / Design Language / Composition——排版前必须先判断。
2. **Selective Emphasis**：强调分四级，多数段落零强调。
3. **图片职责制**：8 种职责，声明缺失 = 必须改，交付不了。
4. **Composition 一句话**：整篇节奏先想好，不许逐段套组件。
5. **Gate 3 四问**：至少找到一个"删掉更好"的候选，再决定删不删。
6. **结语变体、待补素材位、目录三章门槛、中西混排自动左对齐**——都是判断的产物，不是组件的堆积。

## 8. Visual Asset Upgrade

- 图片：职责声明强制化 + 本地化 + 分辨率门槛（宽≥1200px）+ 待补位机制（宁缺毋滥）。
- 图标：只允许文字/数字/Unicode/CSS 几何；图章圆环收敛为统一机制。
- 字体：字号 6 级进渲染器常量；衬线只出现在 ink 的标题/引文/高潮。
- 留白：density 三档（0.8 / 1.0 / 1.2）由 Decision 决定，不再每组件手调。
- 对齐：纯中文两端对齐、中西混排左对齐，渲染器自动判断，消灭字距河流。

## 9. Regression

三篇真实文章全链路：Normalize → Decide → Compose → Render → Gate 1/2 → 通读预览（Gate 3）→ 定稿。

| 用例 | 主题 | Gate 1 | Gate 2 | Gate 3 |
|---|---|---|---|---|
| skills（观点长文，5 章/双列表/Peak） | paper | PASS | PASS | 通过：高潮 = Core Claim，无可删元素 |
| letter（叙事，TOC/实图/待补/note/转场） | letter | PASS | PASS（待补 1 处，已声明） | 通过 |
| ink（评论，表格/代码/引文/深墨 Peak/结语） | ink | PASS | PASS | 通过 |

回归过程真实发现并修复两个渲染器缺陷：中西混排两端对齐的字距河流；空表格头单元格的占位。修复后三篇全量重跑（重渲染 + 重截图 + 通读），定稿见 `eval/expected/`。

```bash
cd eval
mkdir -p /tmp/gzh-eval
for f in skills letter ink; do python3 ../scripts/render.py $f.md -o /tmp/gzh-eval/$f.html || exit 1; done
diff /tmp/gzh-eval/skills.html expected/skills_paper.html \
  && diff /tmp/gzh-eval/letter.html expected/letter_letter.html \
  && diff /tmp/gzh-eval/ink.html expected/ink_ink.html \
  && echo REGRESSION-PASS
```
