# WeChat Article Skill · V19

把 Markdown、Word `.docx` 或纯文本编辑成可信、克制、适合手机阅读的微信公众号正文 HTML、独立移动预览与可核验交付包。零第三方运行时依赖，只用 Python 3 标准库。

**工作流：THINK → EDIT → DESIGN → COMPOSE → RENDER → VERIFY。** 内容判断先于视觉；删除 > 合并 > 简化 > 重组 > 补充。编辑与设计契约的唯一入口是 [`SKILL.md`](SKILL.md)，本文件只说明装什么、怎么跑、边界在哪。

## 结构

| 路径 | 职责 |
|---|---|
| [`SKILL.md`](SKILL.md) | 唯一核心入口：编辑判断、视觉决策七步、六个世界、信息设计、图片契约、三级验收 |
| `scripts/render.py` | Markdown 解析、六主题排版、预览、侧车与 Gate 1/2 交付 |
| `scripts/editorial.py` | 编辑审计：类型策略、断言与依据、标题承诺、逐节增量、事实与声音比对 |
| `scripts/check.py` | 公众号 HTML 标签、属性、协议、内联 CSS 白名单（这条契约的唯一权威） |
| `scripts/extract_docx.py` | `.docx` → Markdown 结构保真提取，有损结构阻断 |
| `scripts/publish.py` | 官方 API：离线预检 → 素材复用 → 草稿回读 → 单次确认发布 |
| `scripts/typography.py` | 装饰性分隔归一、编辑说明移除、单位比与引语保护 |
| `scripts/safety.py` | 路径边界、哈希、原子写入与 WCAG 对比度 |
| `assets/themes.json` | 六个世界的唯一参数真源（色彩世界、字号阶梯、网格、十四条结构轴） |
| `assets/preview.template.html` | 移动预览：五宽度、双字体栈、封面双裁切、复制只含正文 |
| `references/composition.md` | 构图与节奏：版心量尺、比例、重心、四种间距、图片尺寸阶跃、移动端降级（按需读） |
| `references/direction.md` | 图片艺术指导：策划单、构图、材质、淘汰清单（按需读） |
| `references/publish.md` | 凭证、草稿、回读与素材对账（按需读） |
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
- 主题载入即校验：字号层级、全部文字色 × 背景色对比度、**分隔线在底色与浅底上的可见区间（1.45–3.2:1）**、浅底与页底的分界；不合规直接拒绝启动。
- 320px 自动执行数据自适应、柱图/横条形态选择与表格记录卡降级；负外边距只放行出血图，上限一档页边。
- 禁止路径越界、外链图片直引、危险 CSS/脚本与持久发布授权；草稿回读与删除永久素材均有独立强校验。
- 浏览器 PASS、API 回读 PASS、微信真机 PASS 严格分离；未执行项如实记为 `UNVERIFIED` 或 `BLOCKED`。

## V19 迁移说明

V19 改的是视觉系统本身，输入格式与 CLI 不变：

- **六套配色重做**：旧版六个主题的底色明度都在 95.7–97.8、四个强调色是暖褐红——六个房间同一个世界，正是"米白加棕"的俗套。新版底色跨 88（暖灰）→100（纯白），并新增一档墨底（`ink` 反白，L 9）。`paper` 转冷白 + 靛蓝，`frost` 转冷灰蓝 + 信号蓝，`bone` 回暖灰 + 铜绿，`folio` 纯白 + 血红。
- **分隔线可见性成为硬约束**：旧版 `line` 与底色对比 1.27–1.33:1，手机屏上等于不存在，而章节印记、表格边框、目录栏位全靠它。新版强制 1.45–3.2:1，六个主题实际落在 1.82–2.27。
- **主题新增 `stance` 字段**（这个世界的性格），缺它拒绝启动；同时写进侧车 `theme_profile.stance` 与命令行输出。
- **新增原语 `::: timeline`**：日期列 + 竖轴 + 事件，用于时间关系；`bars` 改为按数据形状选形态（三四项且标签短 → 竖柱；否则横条）。
- **图片新增表达方式 `bleed`**（出血）：反推到屏幕两缘，图注退回正文起笔线。`check.py` 为此放行最多 40px 的负外边距，其余负值仍拒绝。
- **章节间距按分量变化**：开篇章 ×1.34、两段就过去的短章 ×0.72，其余不变。
- **重点句套用标题断行规则**：22px 的句子在 280px 版心上尾行掉一两个字，判排版事故。
- **三列以上表格出现孤字行时自动降级为记录卡**（此前只在"放不下"时降级，于是会渲染出一张挤扁的表）。
- **章节编号悬挂进页边**：标题与正文回到同一条起笔线上，左轴不再被编号打断。
- `kicker`（栏目行 / 期号 / 分类串）继续不输出：读者版面取消装饰性刊头文字，刊头只剩摘要行。frontmatter 仍接受该字段，只给一次提示——请直接删掉那一行。

## 许可

[MIT](LICENSE.txt) © 2026 cpikeo。
