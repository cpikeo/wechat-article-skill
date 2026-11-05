# WeChat Article Skill · V14.0.0

将 Markdown、Word `.docx` 或纯文本编辑并排版为可信、克制、适合手机阅读的微信公众号正文 HTML、独立移动预览与可核验交付包。零第三方运行时依赖，仅使用 Python 3 标准库。

**工作流：THINK → EDIT → DESIGN → COMPOSE → RENDER → VERIFY。** 内容判断先于视觉；删除 > 合并 > 简化 > 复用 > 新增。完整编辑/设计契约以 [`SKILL.md`](SKILL.md) 为唯一核心入口。

## V14 重点

- 读者版面去制作化：正文与预览不再印「AI 生成示意 / 素材说明 / 来源 / 来源与授权 / 待补素材 / 资产清单」等模板标签与占位模块；来源与合规记录保留在侧车，必要归属以一句散文简洁呈现。
- 视觉降噪：移除图片衬底/圆角/描边、导语与引文色块边框、章节装饰线与首字下沉；六主题靠字体、字重、间距与低饱和色辨识，版面更干净耐读。
- 预览只保留读者可见内容与宽度/字体/复制控件；封面裁切对照移至开发报告 `V14-visual-comparison.html`。
- 样稿图片与内容重新对齐：色彩校样/色样静物/编辑工序封面替换无关配图；流程图重绘为清晰中文。

## V13 重点（保留）

- 图片艺术指导：生成前七项策划单、六类视觉表达、构图/材质/光影/色彩方向、整篇视觉叙事与生成后看图淘汰；详见 `references/direction.md`。
- 封面 `cover_focal` 焦点裁切（2.35:1 与 1:1 双模拟）；AI 生成图硬拦截冒充资料/实拍/证据/数据；全文同表达方式同质化预警；新增 `macro`/`收束` 语法。

## V12 重点（保留）

- 主题载入即校验所有文字色 × 背景色 WCAG AA ≥ 4.5:1，覆盖 `page` 与 `field` 两类背景。
- 排版保护事实载体：直接引语内部、URL、行内代码、技术单位与数字比不被斜杠规则改写。
- 封面 `cover_note` 与素材侧车记录来源、授权与是否 AI 生成（内部合规，不在版面显示）。
- 独立预览支持 320/360/375/390/430 五宽度与 iOS/Android 字体栈切换；复制只含正文。
- 修复预览字体切换未作用于正文根节点、`check.py --help`、无 `--meta` 时侧车自动发现等问题。

## 目录

| 路径 | 职责 |
|---|---|
| [`SKILL.md`](SKILL.md) | 唯一核心入口：六类编辑策略、六主题设计系统、构图与三级验收 |
| `scripts/render.py` | Markdown 解析、六主题排版、预览、侧车与 Gate 1/2 交付 |
| `scripts/editorial.py` | 编辑审计：类型策略、文风线索、标题承诺、事实与声音比对 |
| `scripts/check.py` | 公众号 HTML 标签、属性、协议、内联 CSS 白名单静态门禁 |
| `scripts/extract_docx.py` | `.docx` → Markdown 结构保真提取，有损结构阻断 |
| `scripts/publish.py` | 官方 API：离线预检 → 素材复用 → 草稿回读 → 单次确认发布 |
| `scripts/safety.py` | 路径边界、哈希、原子写入与 WCAG 对比度 |
| `scripts/typography.py` | 装饰性分隔归一、编辑说明移除、代码/引语保护 |
| `assets/themes.json` | 六主题唯一参数真源 |
| `assets/preview.template.html` | 移动预览：五宽度、双字体栈、复制；只呈现读者可见内容 |
| `references/` | 工程参考：[素材](references/direction.md)、[HTML 门禁](references/platform.md)、[API 交付](references/publish.md) |
| `config.example.json` | 公众号配置示例；复制为被 Git 忽略的 `config.json` |
| `dev/` | 测试、样稿、浏览器评测与审计；不进入正式运行包 |

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

## 验证

```bash
python3 -m unittest discover -s dev -p 'test_*.py' -v
python3 dev/evaluate.py
python3 -m pip install -r dev/requirements.txt
python3 -m playwright install chromium
python3 dev/browser_check.py
python3 dev/audit.py
```

| 入口 | 能证明 | 不能证明 |
|---|---|---|
| `dev/test_skill.py` | 主题、排版、预览、交付、DOCX、发布安全的确定性契约 | 文章语义质量 |
| `dev/evaluate.py` | 六类样稿与注入缺陷的机器线索触发 | 语义编辑准确率 |
| `dev/browser_check.py` | 真实 Chromium 五宽度 × 双字体栈、复制隔离、截图 | 微信客户端清洗与真机 |
| `dev/audit.py` | 文件规模、import 图与引用图 | 删除决策本身 |

证据输出：`dev/reports/browser.json`、`dev/reports/editorial.json`、`dev/reports/audit.json`、`dev/reports/visual-comparison.html`、`dev/reports/V14-visual-comparison.html` 与 `dev/reports/browser/` 截图。验收报告：`dev/reports/V14-验收报告.md`；图片策划与淘汰：`dev/reports/V13-image-briefs.md`。

## 边界

- 机器线索只定位回看原文的地址，不代替语义判决，不虚构事实、来源、引语或图片内容。
- 六主题由字体、网格、标题结构与组件语法驱动，去色后仍可辨；320px 自动执行数据自适应与表格记录卡降级。
- 禁止路径越界、外链图片直引、危险 CSS/脚本与持久发布授权；草稿回读与删除永久素材均有独立强校验。
- 浏览器 PASS、API 回读 PASS、微信真机 PASS 严格分离；未执行项如实记为 `UNVERIFIED` 或 `BLOCKED`。

## 许可

[MIT](LICENSE.txt) © 2026 cpikeo。
