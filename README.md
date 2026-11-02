# wechat-article · V3.0.0

把 Markdown／Word／纯文本编辑为公众号正文 HTML、独立嵌图预览、发布字段与可核验交付记录。它是 **Editorial Intelligence × Visual Design × WeChat Publishing System**，不是网页模板库。

- 唯一编辑与设计判断入口：[SKILL.md](SKILL.md)
- V3 审计、主题对照、测试与未验证项：[AUDIT.md](AUDIT.md)
- 真实来源原稿／优化稿与结果：[evaluation/](evaluation/README.md)

## 运行

运行时仅需 Python 3 标准库。

```bash
python3 scripts/render.py 文章.md
python3 scripts/render.py 文章.md --theme frost -o 交付/正文.html
python3 scripts/extract_docx.py 文章.docx -o 文章.md
python3 scripts/render.py --specimen       # 可复现 assets/themes.html
```

`render.py` 输出：

- 正文 HTML：不重印微信原生标题／作者；只含保守内联样式。
- `*_预览.html`：模拟原生字段、嵌入本地图片、封面2.35:1／1:1裁切和资产表；工具栏不进正文。
- `.meta.json`：字段、编辑诊断、设计决策、首屏结构、主题配置指纹、源稿／正文／素材哈希和阻断项。

退出码1表示 Gate 1/2 有必须修复的问题。`todo` 可生成待补预览，但发布预检拒绝待补稿。跨目录输出会复制素材到交付目录；同名不同内容拒绝覆盖。

Word 抽取保留链接与普通表格；复杂表格、文本框、脚注、修订、丢失关系等无法保真的结构会定位报错并停止输出。编号或嵌套归一会显式警告；进入编辑前仍须对照原件并为图片补职责／来源。

## 六种编辑人格

固定保留六种：

- `paper`：理性分析、开放基线、精确信息表达。
- `letter`：温暖叙事、自然呼吸、人物声音。
- `ink`：东方评论、宋体展示、圆章与收束强调。
- `frost`：新闻报道、冷静秩序、紧凑数据层级。
- `bone`：器物工艺、台纸图版、精细规格感。
- `folio`：国际特稿、强章标、标题与图片张力。

差异真实落在导语、标题、H3、引文、重点、分隔、图片、数据、表格、列表与空间节奏；不是换色、圆角或间距。`assets/themes.json` 是参数单一来源，`assets/themes.html` 由真实渲染器生成；回归会检查三者一致。

## 回归与截图

开发测试与运行时已分离：运行脚本在 `scripts/`，合成语料、mock接口和浏览器检查在 `tests/`。

```bash
python3 tests/run.py
python3 tests/editorial_eval.py --check-report evaluation/RESULTS.md
```

Gate 3 截图是可选开发依赖，不进入 Skill 运行包：

```bash
pip install playwright
python3 -m playwright install --with-deps chromium
python3 tests/run.py --shots --shoot examples/draft-handoff.md
```

截图覆盖320／360／390／430px、复制内容与内联样式、分组构图，以及**同一篇真实来源商业分析稿的六人格对照**。完整产物写入被忽略的 `assets/shots/` 并由 CI 上传；仓库只保留 [`evaluation/visual/`](evaluation/visual/README.md) 中六张有展示价值的 390px 发布基线。截图成功不等于视觉通过。

## 发布与授权边界

```bash
cp config.example.json config.json
# 推荐用 WECHAT_APPID / WECHAT_APPSECRET；config.json 已忽略
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --preflight
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json
# 只有本次明确授权才继续正式发布：
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json \
  --submit --confirm-title "逐字一致的标题"
```

默认止于草稿；`config.json` 不接受 `submit:true`。真实入口先做同一预检，检查正文、源稿、素材、渲染版本与主题配置一致性，再上传封面／正文图、建稿并回读核心字段。发布不是群发。

没有目标账号时，不得声称微信兼容或发布验证完成。Gate 4 必须单独记录：API草稿回读、后台退出重开、手机端样式／图片、封面裁切。详见 [references/publish.md](references/publish.md)。

## 文件职责

|路径|职责|
|---|---|
|`SKILL.md`|唯一编辑、视觉、事实与验收判断入口|
|`assets/themes.json`|六人格参数单一来源|
|`assets/themes.html`|渲染器生成的同稿对照板|
|`scripts/render.py`|解析、排版、Gate 2、预览和meta|
|`scripts/check.py`|Gate 1保守HTML检查|
|`scripts/publish.py`|预检、素材、草稿回读与单次发布授权|
|`scripts/extract_docx.py`|零依赖Word抽取|
|`scripts/safety.py`|路径边界、哈希和对比度共享实现|
|`tests/run.py`|工程／渲染／接口／浏览器完整回归|
|`tests/fixtures.py`|运行时生成的合成测试语料与图片|
|`tests/editorial_eval.py`|五类型真实来源对照、盲测包与重复性|
|`evaluation/`|原稿、优化稿、修改台账、许可与结果|
|`references/`|按需读取的素材、平台与发布边界|
|`AUDIT.md`|V3变更、六主题结果、测试和未验证项|

运行时仍保留 Markdown 唯一成稿、素材路径安全、发布单次授权、草稿回读和完整性校验。SHA-256 用于发现变化，不是签名或来源认证。

[MIT](LICENSE.txt) © 2026 cpikeo
