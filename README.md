# WeChat Article Skill · V6.0.0

把 Markdown、Word `.docx` 或纯文本编辑为可信、克制、适合手机阅读的微信公众号正文 HTML、独立预览与可核验交付记录。它是 AI 编辑与视觉排版 Skill，不是网页模板库、SaaS 或微信编辑器。

**工作顺序：THINK → EDIT → DESIGN → COMPOSE → RENDER → VERIFY。** 内容判断先于视觉；视觉概念先于装饰；删除 > 合并 > 简化 > 复用 > 新增。

- 唯一编辑与设计判断入口：[SKILL.md](SKILL.md)
- 六类真实来源样稿、确定性评估与未验证状态：[evaluation/RESULTS.md](evaluation/RESULTS.md)
- 测试语料许可与盲评方法：[evaluation/README.md](evaluation/README.md)
- 公众号边界、素材方向与发布安全：[references/](references/)

## 快速使用

运行时只依赖 Python 3 标准库。其他截图/开发依赖仅用于评估，不进入 Skill 运行时。

```bash
# Markdown / 纯文本 → 正文 HTML、浏览器预览、meta
python3 scripts/render.py 文章.md

# 指定六种主题之一
python3 scripts/render.py 文章.md --theme frost -o 交付/正文.html

# 对照原稿的事实字面变化并校验五列表格修改台账
python3 scripts/render.py 文章.md --against 原稿.md --ledger 修改台账.md

# 一次交付源稿、HTML、预览、meta、记录、验收和本地素材
python3 scripts/render.py 文章.md --deliver 交付目录/

# Word 转换为 Markdown；转换后须对照原件核查
python3 scripts/extract_docx.py 文章.docx -o 文章.md
```

`render.py` 输出正文 HTML、独立浏览器预览和 `.meta.json`。预览中的工具栏、封面裁切、素材表及模拟标题/作者不会复制进正文。退出码 1 表示 Gate 1/2 有必须修事项；`todo` 允许预览但会被发布预检阻断。不要手改生成的 HTML。

## 六种主题

`paper` 静纸、`letter` 暖信笺、`ink` 酌墨、`frost` 北霜、`bone` 素作、`folio` 特稿。主题差异来自网格、字体、章节、导语、重点、引文、数据、表格、列表、图片及阅读节奏，不只换颜色；推荐依据是内容关系与读者任务，可合理混合构图，不强制套用。参数唯一来源为 [`assets/themes.json`](assets/themes.json)。

六类真实来源样稿在四种手机宽度回归；同一篇含真实 Met CC0 馆藏图像的视觉样稿再覆盖六主题 × 四宽度，并做去色后的结构对照。截图只作审阅输入，不代表独立盲评或微信真机通过。

## 编辑与交付边界

六类策略覆盖新闻、分析、教程、人物、评论、长文。`--against` 比对数字、单位、日期精度、正负号、限定、链接与直接引语；它不是事实核真。新事实须回源，机器线索不代替语义判断。修改要留下位置、问题、动作、收益和保留检查。

四宽度检查覆盖 320/360/390/430px；确实放不下的表格降级为保留全部字段的记录卡，不缩字号。浏览器验证与微信真机验收分开记录。

## 测试与评估

```bash
python3 tests/run.py
python3 tests/editorial_eval.py --check-report evaluation/RESULTS.md

# 一次性安装截图评估依赖（另需系统安装 Noto CJK 字体）
python3 -m pip install playwright pillow
python3 -m playwright install --with-deps chromium

# 运行浏览器评估
python3 tests/run.py --shots --shoot examples/draft-handoff.md
python3 tests/visuals.py
```

`tests/visuals.py` 对六篇真实来源样稿做四宽度浏览器截图，并把同一篇含 Met CC0 真实馆藏图像的视觉样稿以六种主题渲染；去色全页截图只检测结构是否趋同，不是美学排名。回归与评估截图统一落在被忽略的 `evaluation/visual-review/`，不再写入 `assets/`。真实模型复跑、独立外部盲评、逐项第二来源核真和真实微信账号/真机未执行时，须标 `BLOCKED` 或 `UNVERIFIED`，不可伪造结果；当前状态见 [评估记录](evaluation/RESULTS.md)。

## 发布保护

```bash
cp config.example.json config.json
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --preflight
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json

# 仅本次显式授权正式发布，标题必须逐字一致
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json \
  --submit --confirm-title "逐字标题"
```

默认止于草稿。`config.json` 不接受持久发布授权；正式提交必须同时具有本次 `--submit` 和逐字匹配的 `--confirm-title`。凭证不进文章或仓库。预检、API 回读、后台重开、手机端样式与封面裁切是不同验收项；没有真实账号就不能声称微信兼容或发布已验证。详见 [`references/publish.md`](references/publish.md)。

## V6 审计与处置摘要

| 发现（证据） | 处理 |
|---|---|
| README 曾链接不存在的 `AUDIT.md`；文档与当前 V5 代码版本不一致 | 改为现有评估记录；统一版本为 V6 |
| `evaluation/logs/` 存有旧运行日志和本机路径，不能复现当前状态 | 删除历史日志，不把截图/临时输出纳入运行时 |
| 旧主题测试强制每个结构键都不同，容易奖励机械差异；主题截图未覆盖真实样稿和去色辨识 | 改为真实稿四宽度样张、同稿六主题与去色结构比较 |
| `assets/shots/` 是约 30MB 的忽略生成输出目录，`tests/run.py` 与 CI 使用，误放在运行时资产区 | 将回归截图移到 `evaluation/visual-review/regression/`，同步 CI artifact 与 ignore；删除本机生成物，保留 clipboard/style/payload 断言 |
| `render.py` 较大，但解析、组件、安全检查和交付共享同一渲染契约；无清晰独立边界 | 保持单一运行时渲染器，不为拆分而加模块 |
| 真实模型执行、独立盲评与微信真机无可调用环境 | 标为 `BLOCKED/UNVERIFIED`；不冒充测试结果 |

运行时仅保留编辑规则、六主题参数、Markdown/Word 转换、渲染、安全与发布能力；回归/评估仍隔离在 `tests/`、`evaluation/`。详细机器结果在 [evaluation/RESULTS.md](evaluation/RESULTS.md)。

[MIT](LICENSE.txt) © 2026 cpikeo。第三方评估摘录遵循各自许可，详见 [`evaluation/README.md`](evaluation/README.md)。
