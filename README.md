# WeChat Article Skill · V15.0.0

把 Markdown、Word `.docx` 或纯文本编辑成可信、克制、适合手机阅读的微信公众号正文 HTML、独立移动预览与可核验交付包。零第三方运行时依赖，只用 Python 3 标准库。

**工作流：THINK → EDIT → DESIGN → COMPOSE → RENDER → VERIFY。** 内容判断先于视觉；删除 > 合并 > 简化 > 复用 > 新增。编辑与设计契约的唯一入口是 [`SKILL.md`](SKILL.md)。

## V15 修了什么

**内容保真**
- 修复技术单位被误改写：`次/日`、`吨/小时`、`元/度` 曾按装饰性斜杠变成「次 · 日」，现在按单位比保护；`与/或` 一类逻辑连词一并保护，装饰性斜杠规则不再触碰事实载体。
- 修复数据来源门禁误判全角年份「（2025）」为缺来源，不再要求把中文括号改成半角。

**六主题成为六种设计**
- 兑现两条此前只存在于配置里的设计轴：`image`（图像版心与图注对齐）与 `divider`（分节符号）。六主题现在在**标题语法、数据语汇、图像版心、分节符号**四条轴上各不相同，去色后仍可辨认。
- 酌墨主题的章节改为朱砂短印（不编号），并启用开篇首字放大；此前它的标题语法与静纸完全相同。
- 修复层级倒置：三级标题曾小于正文（15px < 16px），重点句只比导语大 1px；现在 H3 ≥ 正文、重点句 ≥ 导语 + 2px，且六主题重点句各有字重、缩进与行距语法。

**编辑判断**
- 六类文章各增 `OPENING-ENTRY`（开篇入口）与 `STRUCTURE-GAP`（结构缺环）定位，六种类型不再共用一套模板；同一环节只报一次。
- 新增标题移动端可读性检查：过长（列表截断）、过薄（信息不足）、逐字复述首段。

**预览与交付**
- 预览新增「封面裁切」面板：以 `cover_focal` 模拟公众号 2.35:1 与 1:1 双裁切，`cover_focal` 从只写不读变成可核对项；工具条显示字数与预计阅读时长。
- 清理失效引用：删除全部指向不存在 `dev/` 目录的测试、评测与报告说明；正式包只保留运行所需文件。

## 目录

| 路径 | 职责 |
|---|---|
| [`SKILL.md`](SKILL.md) | 唯一核心入口：六类编辑策略、六主题设计系统、图片契约、三级验收 |
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
python3 scripts/publish.py --html 交付目录/正文.html --meta 交付目录/正文.meta.json
python3 scripts/publish.py --html 交付目录/正文.html --meta 交付目录/正文.meta.json \
  --submit --confirm-title "逐字标题"
```

## 边界

- 机器线索只定位回看原文的地址，不代替语义判决，不虚构事实、来源、引语或图片内容。
- 主题载入即校验字号层级与全部文字色 × 背景色对比度；320px 自动执行数据自适应与表格记录卡降级。
- 禁止路径越界、外链图片直引、危险 CSS/脚本与持久发布授权；草稿回读与删除永久素材均有独立强校验。
- 浏览器 PASS、API 回读 PASS、微信真机 PASS 严格分离；未执行项如实记为 `UNVERIFIED` 或 `BLOCKED`。

## 许可

[MIT](LICENSE.txt) © 2026 cpikeo。
