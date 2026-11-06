# WeChat Article Skill · V18

把 Markdown、Word `.docx` 或纯文本编辑成可信、克制、适合手机阅读的微信公众号正文 HTML、独立移动预览与可核验交付包。零第三方运行时依赖，只用 Python 3 标准库。

**工作流：THINK → EDIT → DESIGN → COMPOSE → RENDER → VERIFY。** 内容判断先于视觉；删除 > 合并 > 简化 > 重组 > 补充。编辑与设计契约的唯一入口是 [`SKILL.md`](SKILL.md)，本文件只说明装什么、怎么跑、边界在哪。

## 结构

| 路径 | 职责 |
|---|---|
| [`SKILL.md`](SKILL.md) | 唯一核心入口：编辑判断、六主题设计系统、图片契约、三级验收 |
| `scripts/render.py` | Markdown 解析、六主题排版、预览、侧车与 Gate 1/2 交付 |
| `scripts/editorial.py` | 编辑审计：类型策略、断言与依据、标题承诺、逐节增量、事实与声音比对 |
| `scripts/check.py` | 公众号 HTML 标签、属性、协议、内联 CSS 白名单（这条契约的唯一权威） |
| `scripts/extract_docx.py` | `.docx` → Markdown 结构保真提取，有损结构阻断 |
| `scripts/publish.py` | 官方 API：离线预检 → 素材复用 → 草稿回读 → 单次确认发布 |
| `scripts/typography.py` | 装饰性分隔归一、编辑说明移除、单位比与引语保护 |
| `scripts/safety.py` | 路径边界、哈希、原子写入与 WCAG 对比度 |
| `assets/themes.json` | 六主题唯一参数真源 |
| `assets/preview.template.html` | 移动预览：五宽度、双字体栈、封面双裁切、复制只含正文 |
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
- 主题载入即校验字号层级与全部文字色 × 背景色对比度；320px 自动执行数据自适应与表格记录卡降级。
- 禁止路径越界、外链图片直引、危险 CSS/脚本与持久发布授权；草稿回读与删除永久素材均有独立强校验。
- 浏览器 PASS、API 回读 PASS、微信真机 PASS 严格分离；未执行项如实记为 `UNVERIFIED` 或 `BLOCKED`。

## V18 迁移说明

V18 的破坏性变更都在产物契约里，CLI 与输入格式不变：

- 侧车 `integrity_version` 升到 `4`，删除 `type.strategy`（类型策略全文只进「修改记录.md」，侧车留 `key/label/source`）、`editorial_review`（整份审计不再内嵌侧车，改由「修改记录.md」承载）与 `assets[].source_path/source_sha256`（与 `path/sha256` 完全重复）。旧侧车会被发布预检拒绝，须重渲染。
- 交付清单 `files` 的键从文件名改成目录内相对路径；旧清单无法通过"清单内文件全等"校验，须换新目录。
- **`kicker`（栏目行 / 期号 / 分类串）不再输出**：读者版面取消装饰性刊头文字，刊头只剩摘要行。frontmatter 仍接受该字段，只是给一次提示——请直接删掉那一行。
- **`kicker`（栏目行 / 期号 / 分类串）不再输出**：读者版面取消装饰性刊头文字，刊头只剩摘要行。frontmatter 仍接受该字段，只是给一次提示——请直接删掉那一行。
- 主题新增第十四条轴 `header`（刊头），`themes.json` 缺这条轴会被载入拒绝；自定义主题请补 `rule/lede/seal/band/plate/feature` 之一。

## 许可

[MIT](LICENSE.txt) © 2026 cpikeo。
