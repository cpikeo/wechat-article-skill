# wechat-article · V5.0.0

把 Markdown／Word／纯文本编辑为公众号正文 HTML、独立嵌图预览、发布字段与可核验交付记录。它是 **AI Skill：Editorial Intelligence × Editorial Design × WeChat Publishing**，不是网页模板库、SaaS 或微信编辑器。

V5 在 V4 的安全/DOCX/发布保护上做最小改造：编辑 must 真正进入退出码；六类型给出不同保护项与语义工作单；事实比对覆盖正负号、日期精度、限定和直接引语；小字对比双重检查；长数值/比较图在窄屏换形态；开发评估与运行时隔离。

- 唯一判断入口：[SKILL.md](SKILL.md)
- 审计、文件账、实测与未验证项：[AUDIT.md](AUDIT.md)
- 六类真实来源编辑评估：[evaluation/RESULTS.md](evaluation/RESULTS.md)
- 截图证据：`python3 tests/run.py --shots`；编辑前后对照：`python3 tests/visuals.py`

## 运行

运行时仅需 Python 3 标准库。

```bash
python3 scripts/render.py 文章.md
python3 scripts/render.py 文章.md --theme frost -o 交付/正文.html
python3 scripts/render.py 文章.md --against 原稿.md --ledger 修改台账.md
python3 scripts/render.py 文章.md --deliver 交付/
python3 scripts/extract_docx.py 文章.docx -o 文章.md
```

输出：正文 HTML（不重印原生标题/作者）、`*_预览.html`（模拟原生字段、嵌图、封面两裁切、资产表）、`.meta.json`（字段、审计、设计决策、网格、对比检查、完整性哈希、阻断项）。`--deliver` 另含源稿、修改记录、验收与素材。退出码 1 表示 Gate 1/2 有必须修；`todo` 可待补预览但发布预检拒绝。

## 编辑智能

六类型策略：新闻、分析、教程、人物、评论、长文。`argument_map` 定位主张/证据/边界候选，推导关系、反例回应、信息增量初始 `UNVERIFIED`，由编辑填写。标题承诺台账区分结构候选与语义兑现。`--against` 做事实字面保留检查，不做核真；`--ledger` 校验五列与位置。编辑 must 进入 Gate 2。

## 六种人格

paper 静纸／letter 暖信笺／ink 酌墨／frost 北霜／bone 素作／folio 特稿。差异落在网格、正文字体、导语、章节、引文、重点、数据、表格、列表、图片与图注，不只是颜色。参数唯一来源 `assets/themes.json`；概念与选择理由见 SKILL.md。开发样张在 `tests/fixtures.py::PERSONALITY_MD`，不进入运行时。

## 移动端与证据

320／360／390／430px 四宽度截图、元素溢出、最小字号、中文每行字数、首屏可见字符、所有叶子文字对比、数值原子拆行检查。表格按320px判一次，放不下改记录卡；长数值data纵向降级；comparison默认纵向同宽，显式parallel才并列；sequence编号并入图注。浏览器通过不等于微信真机通过。

## 回归与评估

```bash
python3 tests/run.py
python3 tests/editorial_eval.py --check-report evaluation/RESULTS.md
pip install playwright pillow
python3 -m playwright install --with-deps chromium
python3 tests/run.py --shots --shoot examples/draft-handoff.md
python3 tests/visuals.py
```

当前回归：185 条打印断言 + 10 个 unittest 用例；V4 基线 163 条打印断言 + 10 个用例。六类真实来源评估覆盖商业分析、新闻、教程、人物、评论、长文；独立外部盲选、逐项第二来源核真、真实微信账号/真机仍为 `UNVERIFIED`。

## 发布与授权

```bash
cp config.example.json config.json
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --preflight
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --evidence-dir 交付/微信证据
# 仅本次明确授权：
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --submit --confirm-title "逐字标题"
```

默认止于草稿；config 不接受 `submit:true`。预检检查正文、源稿、素材、渲染版本、主题指纹与哈希。真实入口上传封面/正文图、建稿、严格回读核心字段；可选保存脱敏回读对照。后台退出重开、手机端样式/图片、封面裁切仍须单独验收。没有目标账号不得声称微信兼容或发布验证完成。详见 [references/publish.md](references/publish.md)。

## 文件职责

|路径|职责|
|---|---|
|`SKILL.md`|唯一编辑、视觉、事实与验收判断入口|
|`assets/themes.json`|六人格参数单一来源|
|`scripts/editorial.py`|类型策略、文本度量、承诺/论证工作单、事实字面、台账|
|`scripts/render.py`|解析、组件、Gate 2、预览、meta、交付|
|`scripts/check.py`|Gate 1 保守 HTML 检查|
|`scripts/publish.py`|预检、素材、草稿回读、单次授权、脱敏证据|
|`scripts/extract_docx.py`|Word 抽取与丢失阻断|
|`scripts/safety.py`|路径边界、哈希、对比度|
|`tests/`|合成回归、浏览器证据、开发评估工具|
|`evaluation/`|六类真实来源原稿/优化稿、许可、台账、结果|
|`references/`|素材、平台、发布边界（按需读取）|
|`examples/`|可渲染交接示例|
|`AUDIT.md`|V5 变更、删除/合并/保留账、实测与未验证项|

[MIT](LICENSE.txt) © 2026 cpikeo。第三方评估摘录遵守各自许可，见 evaluation/README.md。
