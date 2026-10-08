# Audit · Editorial + Visual Art Direction

本次把 Skill 从 **Renderer + Judge** 推到 **Editorial Intelligence + Visual Art Direction**：
排版判断保持不变，新增的是「视觉该不该存在、长什么样、由谁负责」这一整层判断。
原则没变：**Delete > Merge > Simplify > Reuse > Add**，新增永远是最后一步。

考核标准写在最后一节，含没做到的部分。

## A. Architecture Audit

```
SKILL.md（宪法 + 决策系统 + 路由）
   ↓                       ↘
references/decide.md   references/direction.md      （判断 / 视觉，按需）
   ↓
Decision（四段导演 brief，不是 JSON）
   ↓
Composed Markdown（唯一可交付源，含封面与图片职责）
   ↓
render.py（一次调用：HTML + 390px 预览 + 封面裁切 + Gate 1/2）
   ↓
Gate 3（CONTENT / EDITORIAL / VISUAL / MOBILE → KEEP / REVISE / DELETE）
```

| 动作 | 对象 | 为什么 |
|---|---|---|
| 新增 | 流水线 JUDGE 与 COMPOSE 之间插入 **DIRECT + VISUALIZE** | 原流程「判断完直接排版」，视觉没有独立决策点，图只能靠临场感觉 |
| 新增 | `references/direction.md`（Visual Knowledge，按需加载） | Thesis / Grammar / Role / Prompt 编译 / 封面 / 图示——只在有视觉时付上下文 |
| 新增 | 图片职责改为 **9 个职能**（锚点/解释/证据/对比/结构/场景/隐喻/停顿/数据） | 旧 7 职混合了「信息类型」与「情绪」，职责无法唯一 |
| 新增 | 原语 `::: bars` | 数量对比原先只能靠配图或 `data` 勉强表达；图示替换插画是最省的视觉增量 |
| 新增 | frontmatter `cover` | 封面原先无家可归，被当成正文图顺手用 |
| 合并 | 图片的生成描述 → Prompt 编译链（Decision → … → 390px） | 不再维护 Prompt 模板库，描述由判断派生 |
| 合并 | 旧 10 问 Gate 3 → 五层（内容/编辑/视觉/移动）有归属的检查 + FINAL JUDGMENT | 十问互相重叠，且没人问「封面是否表达文章」 |
| 删除 | 手写维护的 `assets/themes.html` 样本 | 已被 `render.py --specimen` 取代，杜绝样本漂移 |
| 删除 | 旧 AUDIT / CHANGELOG 的历史叙述 | 历史在 git，工作区只留本审计 |
| 保留 | 六种 Editorial Mode、6 级字号、11 个原语不增删、一次渲染、Gate 1 独立于渲染器 | 都仍有真实消费者 |

**没有做的事**：没有增加 Agent、没有增加模板、没有增加中间文件、没有增加 JSON 字段层、没有把流程拆成多次调用。视觉判断全部落在**已经存在的** Decision 与 Gate 3 里。

## B. Context Audit

| | 旧 | 现在 | 判据 |
|---|---|---|---|
| 常驻核心（SKILL + decide） | 9.0 KB | 12.2 KB（+35%） | 涨在视觉判断（Thesis/Grammar/Role/Budget）与 Decision 四段 |
| 按需（有视觉才读） | — | direction.md 7.1 KB | 纯文字任务、无图任务不付这份钱 |
| 最大按需（封面 + 配图 + 通读） | ~9.0 KB | ~19.3 KB | 本次升级的代价，也是它买到的东西 |
| 脚本（设计路径） | render 566 + check 92 = 658 行 | render 816 + check 92 + **selftest 103** = 1,011 行 | 增加了，且必须承认 |
| 发布 / 抽取（非设计路径） | 543 行 | 543 行，未动 | 本次未碰发布与输入 |

render.py 的 +250 行全部花在**校验与方向**上，没有一行花在「更多组件」：
`img_size` 读文件头取宽高 35 行（因此不必引入 Pillow 依赖）、封面两种裁切与比例检查 ~30 行、
Gate 2 的资产存在性 / 分辨率 / 体积 / 预算检查 ~55 行、`bars` 原语与校验 ~50 行、
对照板与截图源 ~55 行、视觉资产清单 ~15 行。
原语只增加了 1 个（`bars`），而它是**用来替换图片**的。

重复清理：SKILL 的流水线表不再重复「读什么」（与加载表重复）；`platform.md` 不再复制 `check.py` 已强制的规则细节（外链规则收紧后仍只写话术，不写正则）。
`decide.md` 只讲判断，`direction.md` 只讲视觉执行，二者没有同一句话出现两次。

## C. Rule & Function Audit

- 旧「每张图都要有职责标签」的软规则 → 现在是 Gate 2 的**必须改**（无职责 = FAIL）。
- 旧「图片职责不在集合内」→ 保留为建议改，但集合换成了 9 职能，并新增两条确定性护栏：
  **同一职能 ≥3 次 = 凑数**；**张数超出字数档位预算 = 删**。
- 新增确定性检查（都可回归）：文件存在性、`img_size` 读文件头取宽高（PNG/JPEG/GIF/WebP，不引入依赖）、
  <600px 低清必须改、封面比例与缺失、bars 值必须是数字 / ≥2 项 / 标签齐全 / 数值过于接近要改回文字。
- 删除「按 600 字密度估图」的旧阈值，换成显式 Image Budget（0–1 / 1–3 / 2–4），与 Decision 的 Budget 对齐。
- 外链规则从「黑名单图库」收紧为「任何 http(s) 图片外链 = 必须改」：黑名单永远漏，白名单不会。
- `typo()` 一度被写坏（lambda 里混入死分支），已修正；这属于「改动必须跑回归」的直接证据。

## D. I/O & Render Audit

- 输入仍是 Composed Markdown，但多了 `cover`（frontmatter）与 `::: bars`（正文）。
- 输出仍是两个文件（正文 HTML + 预览），预览新增：**封面 2.35:1 裁切 + 1:1 信息流缩略**、首屏 ≈780px 参考线、视觉资产清单。
- 渲染次数上限仍是 2（除非 Gate 2 出现必须改）；视觉判断不产生任何额外调用。
- `--specimen` 复用同一渲染器生成对照板，删掉了 25 KB 手写 HTML 的漂移风险。
- 预览读本地封面文件；微信兼容性不在预览层做，仍由 Gate 1 把关。

## E. Asset & Prompt Audit

- 资产顺序写死：**现有素材 → 生成 → CSS 图示 → 无图**；能图示的不生成。
- Prompt 从「模板集合」改为**编译链**：Intent → Role → Concept → Subject → Composition → Camera → Light → Material → Palette → Safe area → Crop → 390px；
  同篇各条描述共用逐字一致的光线/材质/色盘子句 = 连续性，不再靠「请保持一致」祈求。
- 事实安全进入硬规则：生成图不得制造事实；用于事实性内容必须标注「示意」；`eval/visual.md` 的正文图即按此标注。
- 封面独立成工艺：2.35:1 + **1:1 中央裁切才是真约束**（本次实测发现并写回 direction.md：主体偏侧在 2.35:1 成立、在 1:1 缺角）。
- 落到仓库的资产只有两张实测图（1080×460 / 1264×842，合计 ~232 KB），并且**先看再入库**。

## F. QA Audit

- 旧回归：三篇用例跑一遍，人眼看输出。
- 新回归 `scripts/selftest.py`：① 四篇用例 Gate 1/2 全过（新增视觉完整案例）② **六条护栏**必须仍拦住负例
  （图间无承接 / 封面缺失 / 分辨率过低 / bars 非数字 / bars 单项 / 图片超出预算）。
  判断一旦确定，就冻结成测试；防止后续「优化」把视觉判断悄悄改没。
- Gate 3 从「十问」改为五层归属 + FINAL JUDGMENT，明确要求输出 KEEP / REVISE / DELETE，并强制回答
  **What should disappear?**；不打分，数字只服务回归。

## G. 真实案例：eval/visual.md（新增）

《AI 不缺算力，缺的是电》——完整走一次视觉判断，用来当回归用例兼说明书：

- **Decision**：受众是关心 AI 成本结构的人；Core Claim「扩张速度由电表决定」；mode `frost`；预算 2 图 + 1 图示。
- **Thesis**：结构性冷静——基础设施摄影的尺度 + 编辑式图示；禁止霓虹、发光电路、人物特写。
- **Slots**：Cover（第一印象）· 证据（材料真实感）· 数据（量级对比，用 `::: bars` 而非插画）。
- **验证过程**：首版封面主体偏左，2.35:1 好看但 1:1 被裁掉一半 → 重出封面并把判据写回 `direction.md`；
  首版 bars 与正文数字重复（信息增量 ≈ 0）→ 删正文数字、让图示承担，正文只留「翻一倍、相当于日本一年」；
  首版强调过多（4/9 段）→ Gate 2 拦住并降级。

## H. 没做到的部分（诚实记账）

- 常驻核心 **+37%**。视觉判断必须有落点，压缩到「更少」会伤判断，所以停在 12.4 KB，并把视觉知识挪出常驻。
- 生成图的**质量**仍依赖调用方的模型与审美，Skill 只能保证「有判断、有职责、有护栏」，不能保证「每张都好」。
- Gate 3 无法自动化。`selftest --shots` 只准备真机截图源，最终仍要人（或视觉模型）通读。
- 示例的封面与配图是生成资产，仅示范方向与工艺，不代表题材通用。

---

**Less Code. Less Context（按任务计）. Less Rules. Less Calls.**
**More Judgment. Better Images. Better Covers. Better Reading Experience.**
