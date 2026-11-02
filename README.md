# wechat-article · V4.0.0

把 Markdown／Word／纯文本编辑为公众号正文 HTML、独立嵌图预览、发布字段与可核验交付记录。它是 **Editorial Intelligence × Editorial Design × WeChat Publishing**，不是网页模板库。

V4 的重点不是功能变多，而是三个判断变准：编辑问题能被定位到段落并区分「机器可查」与「需要判断」；六种人格拥有各自完整的网格、字体与组件语法；窄屏不再靠缩字号硬塞，而是换一种信息形态交付同样的内容。

- 唯一编辑与设计判断入口：[SKILL.md](SKILL.md)
- V4 审计、优化前后对照、测试与未验证项：[AUDIT.md](AUDIT.md)
- 六人格与四宽度截图：`python3 tests/run.py --shots`（产物写入被忽略的 `assets/shots/`，含 `REVIEW.md`）

## 运行

运行时仅需 Python 3 标准库。

```bash
python3 scripts/render.py 文章.md
python3 scripts/render.py 文章.md --theme frost -o 交付/正文.html
python3 scripts/render.py 文章.md --against 原稿.md --ledger 修改台账.md
python3 scripts/render.py 文章.md --deliver 交付/
python3 scripts/extract_docx.py 文章.docx -o 文章.md
python3 scripts/render.py --specimen       # 可复现 assets/themes.html
```

`render.py` 输出：

- **正文 HTML**：不重印微信原生标题／作者；只含保守内联样式。
- **`*_预览.html`**：模拟原生字段、嵌入本地图片、封面 2.35:1／1:1 裁切和资产表；工具栏不进正文。
- **`.meta.json`**：字段、文章类型、编辑审计（承诺台账／问题清单／类别）、设计决策、网格、首屏结构、主题配置指纹、源稿／正文／素材哈希和阻断项。
- **`--deliver` 交付包**：`源稿.md`、`正文.html`、`*_预览.html`、`*.meta.json`、`修改记录.md`、`验收.md` 与 `images/`。

退出码 1 表示 Gate 1/2 有必须修复的问题。`todo` 可生成待补预览，但发布预检拒绝待补稿。跨目录输出会复制素材到交付目录；同名不同内容拒绝覆盖。

## 编辑智能

- **六种类型策略**：新闻、分析、教程、人物、评论、长文，各自规定入口、结构、证据要求与常见失败。类型决定改法，而不是所有文章一套处理。
- **标题承诺台账**：数量承诺（“三个方法”）、对象承诺（书名号对象）、问题型标题，逐项列出期望／可见／状态／位置。
- **事实单元比对**：`--against 原稿.md` 比对改写前后的数字+单位、日期与链接；消失必须声明，新增必须就近可核。
- **修改台账校验**：`--ledger` 逐行检查五列齐全，且位置能回到正文。
- **边界诚实**：每条问题都标注 `mechanical`（机器可查）或 `judgment`（需人或模型判断）与 `needs`（none／editor／fact-check）。脚本不做语义判决，也不改稿。

## 六种编辑人格

固定保留六种，每种的网格、字体关系与组件形态都不同（细节见 [SKILL.md §4](SKILL.md)）：

|人格|语法核心|适合|
|---|---|---|
|`paper` 静纸|工作纸：索引章标、开放表格、三列数据|理性分析、开放基线|
|`letter` 暖信笺|长信：**段首缩进**、无编号、人声引文|温暖叙事、人物声音|
|`ink` 酌墨|书页：圆章、**首字下沉**、账簿数据|东方评论、论辩|
|`frost` 北霜|电讯稿：`01 /` 章标、**15px 紧凑正文**|新闻报道、事实分层|
|`bone` 素作|台纸：`SECTION` 小标、**17px 舒展正文**、规格表|器物工艺、细节|
|`folio` 特稿|杂志开篇：**40px 红编号**、按句分行的 24px 导语、反色表头|国际特稿、强视觉重心|

差异真实落在导语、标题、H3、引文、重点、分隔、图片、数据、表格、列表与网格上。`assets/themes.json` 是参数单一来源，`assets/themes.html` 由真实渲染器生成；回归会逐轴检查六者不重复，并检查展示板可精确再生成。

## 移动端

- 320／360／390／430px 四宽度截图与逐元素溢出检查。
- 实测**最小字号**与**中文每行字数**，写入截图证据包的 `REVIEW.md`（12px 以下、320px 每行少于 12 字或超过 20 字都会被标出来）。
- 表格按 320px 判一次：放得下就保持表格（短标签与数字不折行），放不下就改为**记录卡**——一行一条记录，字段名与值成对，信息不丢、字号不缩。微信剥离媒体查询，所以不做响应式断点。
- 每个主题按自己的左右留白与表格内距计算可用宽度：`paper/ink/frost/folio` 在 320px 仍用表格，`bone` 因 6px 内衬改用记录卡。

## 回归与截图

```bash
python3 tests/run.py
```

Gate 3 截图是可选开发依赖，不进入 Skill 运行包：

```bash
pip install playwright
python3 -m playwright install --with-deps chromium
python3 tests/run.py --shots --shoot examples/draft-handoff.md
```

截图覆盖四宽度、复制内容与内联样式、分组构图、同稿六人格，以及**排版测量表**；产物写入被忽略的 `assets/shots/` 并由 CI 上传，需要时一条命令重出。仓库不保存截图基线，因此"六人格差在哪"必须以本次渲染结果为准。截图成功不等于视觉通过。

## 发布与授权边界

```bash
cp config.example.json config.json
# 推荐用 WECHAT_APPID / WECHAT_APPSECRET；config.json 已忽略
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --preflight
# 只有本次明确授权才继续正式发布：
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json \
  --submit --confirm-title "逐字一致的标题"
```

默认止于草稿；`config.json` 不接受 `submit:true`。真实入口先做同一预检，检查正文、源稿、素材、渲染版本与主题配置一致性，再上传封面／正文图、建稿并回读核心字段。发布不是群发。

没有目标账号时，不得声称微信兼容或发布验证完成。Gate 4 必须单独记录：API 草稿回读、后台退出重开、手机端样式／图片、封面裁切。详见 [references/publish.md](references/publish.md)。

## 文件职责

|路径|职责|
|---|---|
|`SKILL.md`|唯一编辑、视觉、事实与验收判断入口|
|`assets/themes.json`|六人格参数（色彩 + 结构轴 + 网格）单一来源|
|`assets/themes.html`|渲染器生成的六人格对照板|
|`scripts/editorial.py`|类型策略、文本度量、承诺台账、事实单元、修改台账|
|`scripts/render.py`|解析、六套组件、Gate 2、预览、meta 与交付包|
|`scripts/check.py`|Gate 1 保守 HTML 检查|
|`scripts/publish.py`|预检、素材、草稿回读与单次发布授权|
|`scripts/extract_docx.py`|零依赖 Word 抽取与丢失阻断|
|`scripts/safety.py`|路径边界、哈希和对比度共享实现|
|`tests/run.py`|16 组工程／渲染／编辑／接口／浏览器回归（163 条断言）|
|`tests/fixtures.py`|运行时生成的合成语料（含六种图片职责）与图片|
|`references/`|按需读取的素材、平台与发布边界|
|`AUDIT.md`|V4 变更、优化前后评估、文件账、测试与未验证项|

运行时仍保留 Markdown 唯一成稿、素材路径安全、发布单次授权、草稿回读和完整性校验。SHA-256 用于发现变化，不是签名或来源认证。

[MIT](LICENSE.txt) © 2026 cpikeo
