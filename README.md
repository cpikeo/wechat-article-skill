# wechat-article

把 Markdown／Word／纯文本编辑为公众号正文HTML、独立嵌图预览与发布字段。**唯一设计判断入口：[SKILL.md](SKILL.md)**；不要把主题、脚本或本README当另一套设计规范。

## 运行

Python 3，运行脚本只用标准库。截图回归可选安装Playwright，不是Skill运行依赖。

```bash
python3 scripts/render.py 文章.md
python3 scripts/render.py 文章.md --theme frost -o 交付/正文.html
python3 scripts/extract_docx.py 文章.docx -o 文章.md
python3 scripts/render.py --specimen
python3 scripts/selftest.py
# 显式要求像素验收时，浏览器缺失必须失败
pip install playwright
python3 -m playwright install --with-deps chromium
python3 scripts/selftest.py --shots
```

render输出：正文HTML（无原生标题作者）、`*_预览.html`（封面裁切／资产表／模拟原生字段）、`.meta.json`（字段／正文哈希／渲染错误／待补资产）。`-o`跨目录会复制素材至交付目录（遇同名不同内容拒绝覆盖）；正文交付仍需素材，预览嵌图不能替代上传。
退出码1表示必须改。todo可生成待补预览，但发布预检拒绝待补稿。Word抽取保留链接与普通表格；合并单元格、单元格多段落或换行、行列不齐、文本框、脚注、修订等会定位报错，停止输出；编号/嵌套归一会显式警告；Markdown 嵌套、混合或不连续编号列表会停止转换；进入编辑前核对原件并补图片职责。

## 发布与可验证边界

```bash
cp config.example.json config.json
# 填凭证；config.json不提交。预检无需凭证
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --preflight
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json
# 只有明确授权才加 --submit --confirm-title "标题"（单次授权，逐字确认标题）；
# config 不接受 submit:true——一次设置不能影响以后的普通运行。默认止于草稿
```

命令行覆盖meta，meta覆盖config兜底。真实入口也强制预检。详见[接口与素材说明](references/publish.md)。
复制只复制正文，本地图片须在公众号编辑器上传替换；预览工具栏、封面、原生字段不带入正文。静态检查与浏览器截图不证明微信清洗、草稿或真机效果，必须在目标账号核验。发布不是群发。

## 文件职责

|文件|职责|
|---|---|
|SKILL.md|唯一编辑／视觉／事实与质量判断入口|
|references/direction.md|按需素材工艺|
|references/platform.md|按需HTML与粘贴边界|
|references/publish.md|按需接口／配置／素材知识|
|assets/themes.json|六种可复用编辑语言参数，无独立判断权|
|assets/themes.html|真实渲染器生成的对照板；不再保存过期缩图|
|scripts/render.py、check.py|渲染、确定性检查、预览、meta|
|scripts/publish.py|统一预检、草稿、可选发布、素材管理|
|scripts/extract_docx.py|标准库Word抽取|
|scripts/selftest.py|回归：合成语料、缺陷负例、输入／接口与浏览器|
|scripts/fixtures.py|回归用的合成语料与素材，运行时现生成，不入库|
|.github/workflows/ci.yml|回归与可选像素证据上传|

六种材料：paper、letter、ink、frost、bone、folio；用途见SKILL，不在README重复制定设计门槛。

## 回归与验证边界

`python3 scripts/selftest.py` 跑完整回归：语料与素材由 `scripts/fixtures.py` 在临时目录现生成，仓库不再保存语料、审计产物或二进制素材。加 `--shots` 会把每篇预览截成 320/360/390/430px PNG，并包含六人格同稿对照 作为 Gate 3 通读输入（需 playwright 与 fonts-noto-cjk）。
回归只覆盖可确定的缺陷；CI 通过不等于事实核真，也不等于微信端效果，仍须在目标账号核验。

[MIT](LICENSE.txt) © 2026 cpikeo

## V2 设计与验证状态

审计、变更与验证边界见 [AUDIT.md](AUDIT.md)。设计决策可在源稿 frontmatter 写 `article_type`、`composition`、`asset_strategy`、`design_rationale`，随渲染记录在 meta。图片可写 `"解释 inset"`，八种表达的语义与限制见 SKILL。

图片及封面必须是源 Markdown 所在目录内相对路径，不允许 `..`、绝对路径或符号链接越界；输出素材也限制在 HTML 目录内。跨目录输出时 source 的绝对路径记录在 meta 用于回查，迁移后重新渲染；注意该文件的隐私。SHA-256 用于检测变化，不是签名或来源认证。预检不等于艺术或真机验收。

凭证推荐使用 `WECHAT_APPID` 与 `WECHAT_APPSECRET` 环境变量，优先级为命令行 > 环境变量 > 配置；避免命令行秘钥泄露进进程列表和 shell 历史。建稿后回读核心字段；异常时保存 media_id，不要盲目重复建稿。CLI 的默认审计文件 `.wechat_publish_audit.jsonl` 记录操作阶段和 ID，不含正文与凭证；本地应按敏感运营记录保护。
