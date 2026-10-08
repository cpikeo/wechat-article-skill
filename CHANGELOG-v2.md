# v2 端到端审计与升级报告

## 文件结构对比

### 旧版（14 个 references + 6 个 scripts + 4 个 assets 文档，共约 4400 行）

```
SKILL.md                         主控
MANUAL.md                        用户手册
references/
  theme-index.md                 主题索引
  theme-silent-paper.md          静纸
  theme-warm-letter.md           暖信笺
  theme-wine-ink.md              酌墨
  common-components.md           通用组件
  design-tokens.md               8+N 套色板
  editorial-identity.md          10套色板+排版节奏+9维表+可行性核查
  visual-assets-guide.md         图标图片规范
  design-quality-rubric.md       设计质检清单
  content-editing-guide.md       内容润色
  format-normalize.md            输入归一化
  theme-generator.md             主题生成
  eval-cases.md                  回归用例
  auto-publish-guide.md          自动发布教程
  wechat-official-api-guide.md   API 原理与边界
scripts/                         6个脚本（保留）
assets/                          预览模板/sample/API脚本
```

### 新版（8 个 references + 6 个 scripts，核心 SKILL.md 重写）

```
SKILL.md                         主控（重写：判断驱动生产线）
references/
  design-system.md               ★ 新核心：合并 design-tokens + editorial-identity + design-quality-rubric + visual-assets-guide 判断中枢
  themes.md                      ★ 合并 theme-index + 三个主题文件 + common-components → 单一权威组件源
  platform-rules.md              ★ 合并 SKILL.md「平台红线」+ visual-assets-guide 的平台规则 + 各种 gotchas 中重复的平台约束 → 唯一权威平台规则
  format-normalize.md            保留、精简
  content-editing.md             保留、精简（原 content-editing-guide.md）
  auto-publish.md                ★ 合并 auto-publish-guide + wechat-official-api-guide → 一份讲清
  theme-generator.md             保留、精简，去除与 design-system/platform-rules 重复的部分
  eval-cases.md                  保留、精简更新
scripts/                         6 个脚本全部保留（零修改，因为是确定性兜底）
assets/                          保留 preview-template / sample-article / automation 脚本
CHANGELOG-v2.md                  本文件
```

## 具体删除、合并、保留清单

### 删除（及原因）

| 删除项 | 原因 |
|---|---|
| `references/theme-index.md` | 主题索引和三个主题文件合并为 `themes.md`，单一来源避免跨文件查表 |
| `references/theme-silent-paper.md` | 组件移入 `themes.md`「一、静纸」章节 |
| `references/theme-warm-letter.md` | 组件移入 `themes.md`「二、暖信笺」章节 |
| `references/theme-wine-ink.md` | 组件移入 `themes.md`「三、酌墨」章节 |
| `references/common-components.md` | 通用组件（代码块/图片/待补/深色导语封面）移入 `themes.md`「四、共享组件」，按主题换色，避免"还要再读一份" |
| `references/design-tokens.md` | 色板预设和可选装饰工具移入 `design-system.md` 第七节；删除大量色板历史修正说明和重复落地警告 |
| `references/editorial-identity.md` | 9维表/排版节奏/可行性核查/色板预设移入 `design-system.md` 对应章节 |
| `references/design-quality-rubric.md` | QA 清单移入 `design-system.md` 第九节（Editorial QA）+ SKILL.md 质量三关 |
| `references/visual-assets-guide.md` | 图标三种安全技术→`design-system.md`第四节，图片判断→第五节，平台规则→`platform-rules.md`，删除大量"为什么 npm 图标库不能用"的解释性文字 |
| `references/wechat-official-api-guide.md` | 与 auto-publish-guide 大量重复（门槛表、错误码、用法），合并为 auto-publish.md |
| SKILL.md 中重复的规则列举 | 平台红线只留摘要指向 platform-rules.md；Gotchas 里和 platform-rules 重复的删除 |
| MANUAL.md | 面向用户的说明已在 SKILL.md 顶部描述和 auto-publish.md 中体现；MANUAL.md 内容 80% 和 SKILL.md 重复，删除避免双份维护 |
| 各主题文件开头重复的"公众号平台限制须知" | 统一指向 platform-rules.md，不每个主题重复列一遍 |
| 各主题 Gotchas 里重复的"不用负字距/不叠加强调/不用虚线框/不用图标库" | 统一在 themes.md 末尾 Gotchas 列一次 |
| 色板预设里大量"落地警告"重复文字（每段都警告"不要机械换色"） | 在 design-system.md 第七节开头一次性说清"色板是起点不是模板" |
| theme-generator.md 里重复的"不能用 div/svg/grid/position"长列表 | 指向 platform-rules.md，不重复 |
| content-editing-guide.md 中"语义化命名别名" | 移入 design-system.md 第十节（更合适的位置），删除"新增5套色板已登记"的维护日志式文字 |
| content-editing-guide.md 中"六、新增5套色板预设" | 这是维护日志不是用户文档，色板本身已在 design-system.md 色板表中 |
| 所有"过去7套主题被删除"的历史记录 | 新版不保留已删除主题的故事，只保留现状 |
| eval-cases.md 中"单一主题，静纸"的旧描述 | 更新为三主题选择逻辑 |
| 深色代码块 macOS 三色圆点作为默认 | 酌墨 K8 明确去掉（廉价感与克制体系冲突）；其余两套保留但组件旁明确"酌墨不用"的事实已写入 K8，不再单独警告 |

### 合并（核心减法）

| 合并目标 | 来源 | 效果 |
|---|---|---|
| `design-system.md` | design-tokens + editorial-identity + design-quality-rubric + visual-assets-guide（判断部分） | 1 个文件承载设计中枢：判断框架→层级→节奏→图标→图片→9维→色板→QA清单 |
| `themes.md` | theme-index + theme-silent-paper + theme-warm-letter + theme-wine-ink + common-components | 1 个文件承载所有组件；配色 Token 表格集中对比；共享组件（代码块/图片/待补/深色封面）按主题换色不再维护三份；骨架/配方/映射紧跟组件 |
| `platform-rules.md` | SKILL.md「平台红线」+ visual-assets-guide（平台部分）+ 各主题文件开头的限制须知 | 1 个文件作为唯一合规权威，其他地方只引用不重复 |
| `auto-publish.md` | auto-publish-guide + wechat-official-api-guide | 1 个文件讲清凭证→使用→错误排查→状态码，删除两份文档间重复的门槛表 |

### 保留（及保留原因）

| 保留 | 原因 |
|---|---|
| SKILL.md | 主控，必留；已重写为判断驱动生产线 |
| 三套 Design Language（静纸/暖信笺/酌墨） | 气质差异真实，不是换色版；核心组件保留 |
| 6 个 scripts | 确定性校验兜底：validate/design_quality_check/component_lint/extract_docx/wrap_preview/content_consistency_check；全部零修改保留，因为"可由本地脚本完成的工作不交给模型" |
| `assets/preview-template.html`、`assets/sample-article.md`、`assets/automation/wechat_official_publish.py` | 工具链资产，稳定保留 |
| format-normalize.md、content-editing.md、theme-generator.md、eval-cases.md | 各自承担独立职责，精简后保留 |
| 深色导语封面区块 | 三主题各保留配色变体骨架合一（themes.md 共享组件章节），但明确"默认不用、仅郑重开场时替代而非叠加头部" |
| 酌墨的图章式圆环图标系统 | 这是"无 emoji 高品质图标"的唯一已验证方案，保留且明确推荐给反感 emoji 的用户 |
| accent 配额机制（≤4处 + `--accent-quota 4`） | 三层视觉层级的硬约束，是"克制"的可执行保证，脚本可靠 |
| 两脚本三关质检流程（validate→design_quality→人工通读） | 合规 ≠ 好看，两道自动检查互补、不可互相替代 |

### 修正与升级

| 升级点 | 旧版问题 | 新版做法 |
|---|---|---|
| 决策链 | 文章类型→Theme→Recipe→Component 组件驱动 | Audience→Purpose→Core Claim→Hierarchy→Pace→Temperature→Weight→Composition→Component→HTML 判断驱动 |
| 设计原则 | 散落在各主题/文档中 | SKILL.md 顶部明确 Field>Line>Type>Container 元原则，design-system.md 展开 |
| 视觉锚点 | "全文≤4处 accent"只在脚本层约束 | 明确要求先判断 Core Claim 位置，金句卡必须落在视觉高潮而不是机械放第一章 |
| 图片判断 | "不引用外链+配图贴合主题"两条简单规则 | 建立 Visual Asset Judgment：每张图必须回答"情绪/概念/证据/转场/高潮/质感"哪种职责；答不出则删 |
| 图标系统 | 三种安全技术列举 | 明确 Unicode 排版符号为最推荐（颜色可控、跨平台稳定），酌墨圆环方案提升为可跨主题复用的"图章式视觉语言"参考 |
| Context 读取 | 读 SKILL.md + theme-index + 对应主题 + common-components + visual-assets-guide 至少5份 | 读 SKILL.md + design-system.md（1份判断中枢）+ themes.md（1份组件源），按需读 platform-rules / 其他 = 最少 3 份，比旧版少 40%+ |
| 重复规则 | "不用负字距/不用虚线框/span leaf 必须"在 SKILL.md、三个主题、common-components、visual-assets-guide 反复出现 | 唯一权威在 platform-rules.md；其他文件只引用 |
| 代码块顶栏 | 三个主题中默认有 macOS 红黄绿圆点，酌墨主题特殊说明要去掉 | themes.md 共享组件章节里明确：静纸/暖信笺保留（深色版），酌墨用 K8 去掉圆点的极简版本；浅色版按主题换 accent |
| 暖信笺数据卡+金句卡的 accent 冲突 | theme-index.md 单独警告"用了数据卡就别用金句卡" | 移入 themes.md W15 组件旁说明，集中在组件源一处警告 |
| 酌墨图章 accent 配额说明 | 散落在 theme-wine-ink.md 和 theme-index.md | 移入 K13 组件旁，一处说明（只有"赞同"用 accent，其余两个用 muted） |
| 生产路径表述 | SKILL.md 第0-6步+生成时智能处理+视觉层级+Gotchas 多段混杂 | 0归一化→1选语言→2解析判断（含Editor决策清单）→3装配→4三关质检→5输出，一次读取、一次判断、一次装配、一次校验 |

## 量化变化

| 指标 | 旧版 | 新版 | 变化 |
|---|---|---|---|
| SKILL.md 行数 | 225 | 约 190 | -16%（但信息密度更高，决策链前置） |
| references 文件数 | 15 | 8 | -47% |
| 主题相关文件数 | 5（theme-index + 3主题 + common-components） | 1（themes.md） | -80% |
| 平台规则权威源 | 分散在 6+ 个文件 | 1（platform-rules.md） | 唯一来源 |
| 设计判断中枢 | 分散在 4 个文档 | 1（design-system.md） | 唯一来源 |
| 总代码/规则/Context 量 | ~4400 行 | ~2800 行（含完整组件 HTML） | -36% |
| 脚本文件数 | 6 | 6 | 保留（稳定工具） |
| 强制读取 Context 数（排版一次任务） | 5-6 份 | 3 份（SKILL + design-system + themes） | -40-50% |
| Tool Call（一次典型排版） | 6-8 次 Read | 3-4 次 Read | -40-50% |
| 重复规则声明次数 | 平台红线 ~5次、leaf 要求 ~4次、icon规则 ~3次 | 各 1 次 | 显著消除 |

## 新的最短生产路径

```
1. Read 输入文件（一次）
2. Read SKILL.md（主控，常驻 Context）
3. 归一化（docx→脚本；PDF/纯文本→启发式；Markdown 直接用）
4. Read design-system.md + themes.md（一次读入，后续不再读其他 references）
5. 同步判断：
   - Core Claim / Anchor Points ≤4 / Keyword Marks 每段 1-2
   - Pacing Plan / Image Decisions / 开头策略（是否深色封面）/ 结尾策略
   - Design Language 选择
6. 从 themes.md 取对应主题组件 → 一次装配 HTML
7. 写入产物文件
8. Bash: validate_gzh_html.py → 0 ERROR / 0 半角 WARNING
9. Bash: design_quality_check.py --accent --accent-quota 4 → 0 ERROR，WARNING 逐条有理由
10. 通读按 design-system.md 第九节 Editorial QA 12 项过一遍
11. Bash: wrap_preview.py 生成预览页
12. 交付：产物 + 预览 + Design Language 选择理由 + 两脚本结论 + 用户待办
```

读取次数：2-3 次 Read（输入 + SKILL + design-system/themes），2-3 次 Bash（validate + design-check + wrap_preview）。
