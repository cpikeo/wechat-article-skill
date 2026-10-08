# Audit · Editorial Intelligence

v3 已经完成「手写 HTML → 渲染器」。本次不是再加组件，而是把 Skill 从 **Renderer** 升到 **JUDGE + DIRECT**。

原则：Less System. More Judgment. 数字让路给品质——该删的删，会产生视觉价值的判断保留。

## A. Architecture Audit

```
SKILL.md = Intelligence
        ↓
Decision（导演 brief）
        ↓
Editorial Composition（Composed Markdown）
        ↓
Minimal Rendering Engine（render.py）
        ↓
Gate 1 Platform  /  Gate 2 Composition
        ↓
Gate 3 Art Direction（通读 390px 预览）
```

| 动作 | 对象 | 为什么 |
|---|---|---|
| 删除 | `CHANGELOG-v3.md` | 历史进 git；工作区只留本审计 |
| 删除 | 图片职责「情绪/语境/品牌/高潮/解释/转场」 | 与氛围/信息/Peak 原语重叠，鼓励装饰性配图 |
| 删除 | 居中 quote | 与 Peak 互抢高潮；quote 改为左线旁注重量 |
| 删除 | publish.py 约 40 行史论 docstring | 消费者是 `publish.md`，不是模块注释 |
| 删除 | letter `radius: 10` | App 卡片，不是编辑设计 |
| 合并 | JUDGE 的视觉指令 → DIRECT，仍写在同一张 Decision | 不另搞 JSON 工作流 |
| 合并 | 字号魔法数 → 6 级常量 | 主题不得再发明字号 |
| 保留 | 三套 Editorial Mode | 标记语言不同，不是换色 |
| 保留 | 11 个原语、一次渲染、Gate 1 独立于渲染器 | 仍有真实消费者 |
| 保留 | `extract_docx.py` / `publish.py` 行为 | 输入与发布路径未改 |
| 新增 | Decision 的 Hierarchy / Rhythm / Cut | 导演 brief 原先缺删减与节奏 |
| 新增 | 主题键 `image`: flush / soft / line | 图片是编辑语言，不是圆角开关 |
| 删除 | `eval/expected/`、样本图、brief/cases/judgment/specimen | 生成物与说明类文件不进 eval；判断并进 decide.md |

脚本仍然不充当设计规则来源。规则在 `SKILL.md` 与 `decide.md`；`compose_gate` 只执行可确定的子集。

## B. Design Intelligence Audit

强化：

- 先判断再设计：Audience → Claim → Hierarchy → Rhythm → Theme → Cut
- 视觉权重服从信息权重；Plain Text 优先于原语
- 只有 Peak 居中；ink 标题真正用衬线（原先 H2 漏了）
- 图片 7 职 + 按职责决定边距/说明字号/切边
- 数据：≤3 项一行，更多改两列（390px）
- Gate 3 十问，核心是 **Which element should disappear?**
- 同一主张换读者，构成必须变；只换 theme 字段视为失败

删除 / 降级：

- 「每张图都要有一种职责标签」里那些其实是装饰的职责
- quote 作为第二高潮
- 为丰富而存在的组件冲动（原语未增加）

从代码迁到 Decision 的：

- 密度、主题、Peak 位置、图的去留、删什么——不再假装能用配方表决定

## C. Context Audit

| | v3 | 现在 |
|---|---|---|
| 常驻（SKILL + decide） | 6,997 B | 8,350 B |
| 默认不加载 | platform / publish / scripts | 同左，且 SKILL 写明禁止读 scripts 与 AUDIT |
| publish.py 头注释 | ~50 行史论 | 6 行边界 |

常驻多了约 1.3KB：**Hierarchy、Rhythm、Cut、图片提示词、Gate 3 十问**。继续压缩会伤判断，故停止。

重复：Decision 模板只在 SKILL；如何填只在 decide。平台硬约束只在 `check.py`，`platform.md` 仅 Gate 1 FAIL 时读。

Progressive Disclosure：按任务加载。排版 = SKILL + decide；发布才读 publish；不要把 Skill Library 一次性塞进上下文。

## D. Visual Audit

- **Typography**：6 级锁定 11/13/15/17/20/24。ink 的刊头与 H2 使用衬线；正文保持无衬线，保证中文长文可读。
- **Spacing**：density 三档仍在；首屏边距略收，让钩子更早进入 390px。
- **Hierarchy**：kicker 元数据 → 标题 → lead → 正文 → Peak。quote 降为左线，不再与 Peak 同级。
- **Rhythm**：H2 大停顿保留；禁止连续三块非正文原语（Gate 2）。
- **Image**：flush / soft / line 三套处理；职责决定边距与 caption 重量。
- **Icon**：仍只允许文字 / 数字 / Unicode / CSS 几何。
- **Theme**：三个人格，各加 `image` 键；letter 圆角 10→4。
- **Mobile**：预览 414→390；data 防 4+ 挤成三列；表 >3 列 Gate 2 警告；长 quote 不再居中断行。

## E. Complexity Audit

不为数字优化。下列是诚实对照。

| | v3 | 现在 |
|---|---|---|
| 设计相关 tracked 文件 | 21 | 24（+judgment/brief/AUDIT，−CHANGELOG） |
| `scripts/render.py` | 524 行 | 564 行（Gate 2 删除式检查 + 图片职责处理） |
| `scripts/publish.py` | 414 行 | 372 行 |
| 脚本合计 | 1,201 行 | 1,199 行 |
| 主题 | 3 人格 × ~19 键 | 3 人格 × 20 键（+image） |
| 原语 | 11 | 11 |
| 图片职责 | 8 | 7 |
| Decision | 9 行描述 | 10 行导演 brief |
| Gate 3 | 4 问 | 10 问 |
| 渲染次数 | 1 | 1 |
| 排版调用 | 读原文 + 写 compose + render + 预览（decide 名存实亡） | 同上，但 **必须读 decide** |

调用没有变少：判断被当成必做，而不是可跳过的附录。这是有意的。

回归：`eval/` 三篇源用例（skills / letter / ink）Gate 1/2 必须 PASS。不入库生成 HTML。

---

**Less System. More Judgment.**  
**Less Decoration. More Hierarchy.**  
**Less Rules. More Intelligence.**  
**Less Code. Better Output.**
