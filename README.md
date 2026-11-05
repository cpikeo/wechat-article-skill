# WeChat Article Skill · V15.1

把 Markdown、Word `.docx` 或纯文本编辑成可信、克制、适合手机阅读的微信公众号正文 HTML、独立移动预览与可核验交付包。零第三方运行时依赖，只用 Python 3 标准库。

**工作流：THINK → EDIT → DESIGN → COMPOSE → RENDER → VERIFY。** 内容判断先于视觉；删除 > 合并 > 简化 > 复用 > 新增。编辑与设计契约的唯一入口是 [`SKILL.md`](SKILL.md)。

## 本版做了什么

**编辑判断**
- 判断句不再逐段索要来源。原规则在分析稿里会给几乎每个段落挂一条「无据」提示；现在按章判断：只有带量化或明确因果的断言，且整章找不到任何可核依据时才提示。年份不再被当成出处。
- 推断连接词只在带具体结论时追问前提，纯议论里的「因此」不再误报。
- 六类文章各有一套读者任务、开篇入口、结构环节与「必须保住/最常破坏」清单，不共用一套模板。

**视觉体系**
- 六主题改为六种版式架构：版心（0–6% 页边）、章节开门（编号在上／居中／朱砂印／细线／不编号）、目录语法、图像版心与图注对齐，全部由主题参数驱动。
- 章节标题进入 21–30px 区间，与正文拉开 5px 以上；三级标题 17–18px 不再小于正文。
- 纵向间距落到主题模数（8/9/10px）；段距改跟行距走，不再被网格削薄。
- 标题断行：只在会留下孤字时显式分行，且断在标点后；正常断行不干预，避免大屏被硬拆成两行。章节标题超两行会给编辑提示。
- 目录从「一张表换字体」改为六套语法：数码编号配细线、居中无框、卷目衬线、上下线夹住、展签式双线、特稿加粗条目。

**数据与图表**
- 柱图不再在版面印「最长条代表最大值」这类方法说明，只留「零起点」；方法留在侧车。
- 表格与数据块的可用宽度按主题页边重算，窄屏降级判断更准。

**图片**
- `references/direction.md` 重写为可执行的摄影指导：策划单七项、提示词「用物理条件代替形容词」、六种视觉语言的选择标准、一组图的光源/色温/镜头一致性、AI 图的六种默认失败与反向约束。

## 目录

| 路径 | 职责 |
|---|---|
| [`SKILL.md`](SKILL.md) | 唯一核心入口：编辑判断、六主题设计系统、图片契约、三级验收 |
| `scripts/render.py` | Markdown 解析、六主题排版、预览、侧车与 Gate 1/2 交付 |
| `scripts/editorial.py` | 编辑审计：类型策略、结构缺环、标题承诺、事实与声音比对 |
| `scripts/check.py` | 公众号 HTML 标签、属性、协议、内联 CSS 白名单静态门禁 |
| `scripts/extract_docx.py` | `.docx` → Markdown 结构保真提取，有损结构阻断 |
| `scripts/publish.py` | 官方 API：离线预检 → 素材复用 → 草稿回读 → 单次确认发布 |
| `scripts/typography.py` | 装饰性分隔归一、编辑说明移除、单位比与引语保护 |
| `scripts/safety.py` | 路径边界、哈希、原子写入与 WCAG 对比度 |
| `assets/themes.json` | 六主题唯一参数真源 |
| `assets/preview.template.html` | 移动预览：五宽度、双字体栈、封面双裁切、复制只含正文 |
| `references/` | 按需读取：[图片艺术指导](references/direction.md)、[HTML 门禁](references/platform.md)、[API 交付](references/publish.md) |
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
- 主题载入即校验字号层级与全部文字色 × 背景色对比度；320px 自动执行数据自适应与表格记录卡降级。
- 禁止路径越界、外链图片直引、危险 CSS/脚本与持久发布授权；草稿回读与删除永久素材均有独立强校验。
- 浏览器 PASS、API 回读 PASS、微信真机 PASS 严格分离；未执行项如实记为 `UNVERIFIED` 或 `BLOCKED`。

## 许可

[MIT](LICENSE.txt) © 2026 cpikeo。
