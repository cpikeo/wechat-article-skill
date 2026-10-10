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

render输出：正文HTML（无原生标题作者）、`*_预览.html`（封面裁切／资产表／模拟原生字段）、`.meta.json`（字段／正文哈希／渲染错误／待补资产）。`-o`跨目录会重新定位素材路径；正文交付仍需素材，预览嵌图不能替代上传。
退出码1表示必须改。todo可生成待补预览，但发布预检拒绝待补稿。Word抽取是素材转换，不保证编号、合并单元格、文本框等完全保真；进入编辑前核对原件并补图片职责。

## 发布与可验证边界

```bash
cp config.example.json config.json
# 填凭证；config.json不提交。预检无需凭证
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --preflight
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json
# 只有明确授权才加--submit；默认止于草稿
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
|assets/themes.html、previews/|真实渲染器生成的对照板与缩图|
|scripts/render.py、check.py|渲染、确定性检查、预览、meta|
|scripts/publish.py|统一预检、草稿、可选发布、素材管理|
|scripts/extract_docx.py|标准库Word抽取|
|scripts/selftest.py|案例、缺陷负例、输入／接口与浏览器回归|
|eval/|五篇教学／回归源与素材；不是五篇已经事实认证的新闻稿|
|.github/workflows/ci.yml|回归与可选像素证据上传|

六种材料：paper、letter、ink、frost、bone、folio；用途见SKILL，不在README重复制定设计门槛。

## 审计交付

[audit-magazine/REPORT.md](audit-magazine/REPORT.md) 是第二轮（基线c4303c3）审计；[audit/REPORT.md](audit/REPORT.md)保留第一轮记录，不作当前认证。新报告记录2026-10-10基线、具体修改、命令、结果、局限和评分。案例重写保留现有素材，不新建模板或Agent。教学假设、虚构人物与来源限制在成品正文可见，不以CI通过充当事实认证。

[MIT](LICENSE.txt) © 2026 cpikeo
