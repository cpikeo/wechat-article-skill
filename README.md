# WeChat Article Skill · V11.0.0

将 Markdown、Word `.docx` 或纯文本编辑并排版为可信、克制、适合手机阅读的微信公众号正文 HTML、独立移动预览与可核验交付包。本仓库是遵循开放标准的 AI 编辑与视觉排版 Skill，零第三方运行时依赖，仅使用 Python 3 标准库。

**工作流：THINK → EDIT → DESIGN → COMPOSE → RENDER → VERIFY。** 内容判断先于视觉，关系组织先于装饰；删除 > 合并 > 简化 > 复用 > 新增。完整规则与编辑/设计契约以唯一核心入口 [`SKILL.md`](SKILL.md) 为准。

## 目录结构

| 路径 | 职责 |
|---|---|
| [`SKILL.md`](SKILL.md) | 唯一核心入口：六类编辑策略、事实与声音保护、六主题设计系统、构图与三级验收契约 |
| `scripts/render.py` | Markdown 解析、六主题排版引擎、独立移动预览、`.meta.json` 与 Gate 1/2 门禁交付 |
| `scripts/editorial.py` | 可定位编辑审计：六类文章判断入口、文风/重复线索、标题承诺、逐节增量、事实与声音比对 |
| `scripts/check.py` | 公众号 HTML 标签、属性、协议、内联 CSS 白名单、字体栈与 HTTP(S) URL 真源校验 |
| `scripts/extract_docx.py` | `.docx` → Markdown 结构保真优先提取（标题、粗体/斜体/下划线/删除线、引用块、多级编号、普通表格；有损结构显式阻断；输出转换记录） |
| `scripts/publish.py` | 微信公众号官方 API：离线预检 → 素材复用 → 草稿创建与回读核验 → 单次确认发布 |
| `scripts/safety.py` | 相对路径穿越/符号链接拦截、SHA-256 指纹与 WCAG 对比度计算 |
| `assets/themes.json` | 六套主题（`paper`/`letter`/`ink`/`frost`/`bone`/`folio`）唯一参数真源 |
| `references/` | 按需工程参考：[`direction.md`](references/direction.md)（素材工艺）、[`platform.md`](references/platform.md)（HTML 门禁）、[`publish.md`](references/publish.md)（API 交付） |
| `config.example.json` | 公众号配置示例（复制为已被 Git 忽略的 `config.json` 使用） |

正式运行时包严格保持干净，不含测试脚本、评测样本、截图或开发报告。开发评测位于 `dev/`，依赖只用于测试，不进入运行时。

## 快速开始

```bash
# 1. Word 转 Markdown（可选；转换后须补图片职责并走编辑流程）
python3 scripts/extract_docx.py 文章.docx -o 文章.md

# 2. 渲染正文 HTML + 独立移动预览 + .meta.json（可选指定主题）
python3 scripts/render.py 文章.md --theme paper

# 3. 对照原稿核查事实单元/作者声音变化，并校验五列修改台账
python3 scripts/render.py 文章.md --against 原稿.md --ledger 修改台账.md

# 4. 生成完整交付包（源稿/正文/预览/meta/修改记录/验收与本地素材）
python3 scripts/render.py 文章.md --deliver 交付目录/

# 5. 公众号发布离线预检 / 创建草稿 / 单次确认正式发布
python3 scripts/publish.py --html 交付目录/正文.html --meta 交付目录/正文.meta.json --preflight
python3 scripts/publish.py --html 交付目录/正文.html --meta 交付目录/正文.meta.json
python3 scripts/publish.py --html 交付目录/正文.html --meta 交付目录/正文.meta.json \
  --submit --confirm-title "逐字标题"
```

## V11 验证与交付

```bash
# 开发环境（运行时不需要这些依赖）
python3 -m pip install -r dev/requirements.txt
python3 -m playwright install chromium
python3 -m unittest discover -s dev/tests -v
python3 dev/evaluate.py
python3 dev/voice_evaluate.py
python3 dev/browser_check.py --output dev/reports/browser
```

- 六主题同稿、320/360/390/430px 真实 Chromium 截图与 JSON 指标：`dev/reports/browser/`。
- 可离线打开的视觉对照：`dev/reports/visual-comparison.html`。
- 九维结果、修改/删除/保留清单、未验证事项与下阶段优先级：`dev/reports/V11-验收报告.md`。
- 编辑评测含 12 篇原创完整情境正负样稿与 6 组真实发表来源短片段；所有注入缺陷均显式标注。检测率只衡量已标注线索，不冒充语义编辑准确率。
- 发布预检冻结 HTML/侧车/源稿/封面/正文图字节；API 仅允许 HTTPS 官方 `api.weixin.qq.com/cgi-bin/`，拒绝重定向；封面缓存按账号隔离并验活。

## 核心边界

- **编辑不造假**：机器线索只定位回看原文的地址，不代替语义判决，不虚构事实、来源、引语或图片内容。
- **六主题不靠换色**：`paper`（静纸）、`letter`（暖信笺）、`ink`（酌墨）、`frost`（北霜）、`bone`（素作）、`folio`（特稿）由字体、网格、标题结构与组件语法驱动，去色后仍清晰可辨；320px 窄屏自动执行多栏自适应与表格记录卡降级。
- **安全与门禁闭环**：禁止路径越界、外链图片直引、危险 CSS/脚本与持久发布授权；草稿回读或删除永久素材均有独立强校验与 `0600` 脱敏审计日志。
- **三级验收分离**：严格区分本地四宽度浏览器验证、微信 API 草稿回读与微信客户端真机验收；未执行项如实记为 `UNVERIFIED` 或 `BLOCKED`。

## 许可

[MIT](LICENSE.txt) © 2026 cpikeo。
