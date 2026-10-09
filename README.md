# wechat-article

判断驱动的公众号 **Editorial Intelligence**：把 Markdown / Word / 纯文本，做成可直接粘贴进公众号编辑器的成品 HTML。

先理解文章，再判断什么值得存在，然后才是排版；图片、封面、图示按同一套视觉判断产出，生成之后还要选。
**每个元素必须有职责；说不出职责的，删。**

```
UNDERSTAND → JUDGE → EDIT → DIRECT → VISUALIZE → SELECT → COMPOSE → RENDER → VERIFY → REFINE
```

**不是**组件库、换色模板、图片 Prompt 合集，也不是普通网页或 PPT 排版。

## 要求

Python 3，只用标准库，无需 `pip install`。（可选：发布需要公众号 AppID/AppSecret；`selftest.py --shots` 需要 playwright，用于把预览截成 390px PNG 交给人眼或视觉模型通读。）

## 快速开始

```bash
python3 scripts/render.py 文章.md
# 产出 文章_{theme}.html          ← 粘贴进公众号（不含标题/作者，它们走原生字段）
#      文章_{theme}_预览.html    ← 390px 对照（模拟原生标题/作者栏 + 封面两种裁切 + 正文资产表 + 一键复制）
#      文章_{theme}.meta.json    ← 发布字段：title(转｜)/author/digest/cover/原文链接
# 终端打印 Gate 3 证据 + Gate 1/2 结论
```

| 输入 | 命令 |
|---|---|
| Markdown | `python3 scripts/render.py 文章.md` |
| 指定主题 | `python3 scripts/render.py 文章.md --theme frost` |
| Word | `python3 scripts/extract_docx.py 文件.docx -o 文章.md`，再渲染（图必须补职责） |
| 气候对照板 | `python3 scripts/render.py --specimen` → `assets/themes.html`（入库，随时重生成） |
| 发布草稿 | `python3 scripts/publish.py --help`（先排完再发） |
| 发前验收 | `python3 scripts/publish.py --html 文章.html --meta 文章.meta.json --preflight`（不联网） |
| 回归 | `python3 scripts/selftest.py`（CI 每次提交都会跑） |
| Gate 3 截图 | `python3 scripts/selftest.py --shots` → `assets/shots/*.png`（生成物，不入库） |

退出码 `1` = Gate 1/2 仍有「必须改」，不要交付。

最小文章：frontmatter + 正文。

```yaml
---
title: 主标题|断行后半   # | 是断行标记：原生标题栏自动转｜，正文不重印标题
theme: frost          # paper / letter / ink / frost / bone / folio
density: standard     # dense / standard / airy
cover: images/cover.jpg   # 2.35:1；写 todo = 待补
author: 甲木          # 平台原生作者栏，正文不重印
---
```

## 视觉判断（这套 Skill 真正在做的事）

排版之前先回答，答案写进 Decision：

1. **Visual Thesis** —— 这篇看起来像什么？（气质 / 隐喻 / 重量 / 克制点）
2. **Grammar** —— 全篇一套光源、材质、色盘、镜头、画幅，不混搭。并排放在一起要像同一位 Art Director 在同一次创作里完成。
3. **Role + Weight + Budget** —— 每个位置需要什么视觉职能（锚点/解释/证据/对比/结构/场景/隐喻/停顿/数据），视觉重量服从信息权重，全文预算几张。

取资产顺序固定：**现有素材（且真的好）→ CSS 图示（`::: data` / `::: bars` / 表格）→ 生成 → 无图**。
**图示 > 插画；证据 > 装饰；意义 > 丰富度。** 能一眼说清的关系用图示，不生成插画；生成图不得制造事实，用于事实性内容时标注「示意」。

**生成之后要选。** 每个候选只问三句——合语法吗？比正文多给什么？390px 上主语还站得住吗？→ **留下 / 重做 / 删除**，留下的写一句「为什么是这张」，写不出就删。**优先删，而不是重生成。**

封面单独做 art direction：讲的是**文章主张**，不是文章主题；2.35:1，主体落在正中（微信会再裁成 1:1），默认不放文字。

细则：[references/direction.md](references/direction.md)（含失败样例与 gotchas，只追加真实遇到的）。判断与主题：[references/decide.md](references/decide.md)。

## 六个 Editorial Mode

不是六套配色。字号 6 级锁定、行距锁 1.75–1.85 移动阅读档；主题只决定气候与标记语言。

| 主题 | 气候 | 用于 | 标记 |
|---|---|---|---|
| `paper` 静纸 | 暖石 · 干苔 | 观点、分析、教程、默认 | 数字章节 · 细线高潮 |
| `letter` 暖信笺 | 信笺 · 火漆 | 叙事、人物、随笔 | 不编号章节 · 暖底高潮 |
| `ink` 酌墨 | 象牙 · 干血 | 评论、书评、年度 | 图章 · 衬线 · 深色高潮 |
| `frost` 北霜 | 北昼 · 峡湾 | 调查、科技、基础设施 | 数字章节 · 冷底高潮 |
| `bone` 素作 | 石膏 · 铜尘 | 品牌、工艺、空间、材料 | 无编号 · 衬线 · 细线高潮 |
| `folio` 特稿 | 油墨 · 干朱 | 文化特稿 | 数字章节 · 深色高潮 |

效果图（同一篇样张过六种人格；由对照板 `assets/themes.html` 截出，存 `assets/previews/`）：

<table>
<tr>
<td align="center"><img src="assets/previews/paper.png" width="240" alt="静纸 paper"><br><b>静纸 paper</b></td>
<td align="center"><img src="assets/previews/letter.png" width="240" alt="暖信笺 letter"><br><b>暖信笺 letter</b></td>
<td align="center"><img src="assets/previews/ink.png" width="240" alt="酌墨 ink"><br><b>酌墨 ink</b></td>
</tr>
<tr>
<td align="center"><img src="assets/previews/frost.png" width="240" alt="北霜 frost"><br><b>北霜 frost</b></td>
<td align="center"><img src="assets/previews/bone.png" width="240" alt="素作 bone"><br><b>素作 bone</b></td>
<td align="center"><img src="assets/previews/folio.png" width="240" alt="特稿 folio"><br><b>特稿 folio</b></td>
</tr>
</table>

先判断语气，再选主题。气质对不上，不要硬套。
**新增主题的唯一门槛**：必须改变至少两个「编辑语言轴」（章节标记 / 高潮处理 / 转场 / 引文 / 图片气质 / 字体气质）。
只换背景色、accent、字体颜色不算新人格——`selftest` 会把这种主题直接判 FAIL。

## 怎么用这套 Skill

给 Agent 读 [SKILL.md](SKILL.md)。它会：只读一次原文 → 写 Decision（读取 / 节奏 / 视觉 / 复核）→ 编辑文字 → 定视觉方向 → 取并筛选资产 → 输出 Composed Markdown → 一次渲染 → 对照证据通读 390px 预览。

## QA

| 关 | 谁来 | 不过就怎样 |
|---|---|---|
| Gate 1 Platform | `scripts/check.py`（随渲染） | FAIL 不交付 |
| Gate 2 Composition | 渲染器：结构 · 原语密度 · 首屏 · 图片职责/预算/分辨率/裁切 · 图示与正文是否重复 | 「必须改」修完；「建议改」逐条给理由 |
| Gate 3 证据 | 渲染器打印：资产 / 首屏 / 节奏 / 结构 的可核对数字 | 拿它去通读，不要凭印象 |
| Gate 3 Art Direction | 对照证据通读 390px 预览：CONTENT / EDITORIAL / VISUAL / MOBILE / FINAL JUDGMENT | 结论只写 KEEP / REVISE / DELETE，强制回答 **Which element should disappear?** 与「为什么是这张」 |

Gate 3 不打分。数字只服务回归，不替代艺术判断。
**机器只验可确定的缺陷**（坏了 / 无法核对 / 违反已写明的规则）；密度、节奏、强调多少、裁切好不好看是判断，不写成阈值。「建议改」不是待办清单：答不出「改了读者多得到什么」就不改。

## 仓库

```
SKILL.md                 宪法 + 决策系统：原则、视觉判断、流程、语法、QA
references/decide.md     判断知识：Decision、六种人格、删除与强调
references/direction.md  视觉知识：Thesis、Grammar、Role、SELECT、Prompt 编译、封面、图示
references/platform.md   技术约束：微信 HTML 硬约束（按需）
references/publish.md    技术约束：官方 API 草稿 / 发布（按需）
assets/themes.json       六种 Editorial Mode（唯一来源）
assets/themes.html       六格气候对照板（真实渲染器生成，--specimen 重生成）
scripts/render.py        一次调用：正文 HTML + 预览（模拟原生栏 · 封面两裁切 · 正文资产表）+ 发布字段 meta.json + Gate 1/2 + Gate 3 证据
scripts/check.py         Gate 1
scripts/selftest.py      回归：用例 + 六种人格 + 护栏 + 渲染断言
scripts/extract_docx.py  Word → Markdown
scripts/publish.py       发前预检（--preflight，不联网）+ 草稿 → 可选发布；永久素材复用/对账/清理
eval/                    5 篇用例（契约与覆盖表见 eval/README.md；人格渲染另由 ② 样张全覆盖）
config.example.json      发布配置模板（appid/secret/作者/原文链接/留言/submit；真 config.json 不入库）
assets/previews/         六种 Editorial Mode 效果图（--specimen 对照板截图）
LICENSE.txt              MIT © 2026 cpikeo
.github/workflows/       CI：每次提交跑回归与截图证据
```

脚本不是设计规则来源；脚本只执行**可确定**的那部分判断，并把 Gate 3 要用的证据摆出来。

## 回归

```bash
python3 scripts/selftest.py            # ① 五个用例 Gate 1/2 全过 ② 质量基准（5 篇语料的人格/资产/结构/首屏快照）
                                       # ③ 人格系统可渲染 · 不重复 · 键完整 ④ 十四条护栏仍拦住负例
                                       # ⑤ 原语渲染断言 + 目录不占首屏 ⑥ 同文不同 Decision → 不同 Composition
                                       # ⑦ Word 抽取 ⑧ 平台原生字段 ⑨ draft/add payload ⑩ 永久素材管理
                                       # ⑪ 暖信笺无孤立圆点 ⑫ config.json 默认与优先级 ⑬ 发布预检（不联网）
python3 scripts/selftest.py --shots    # 真截 390px PNG 到 assets/shots/，作为 Gate 3 的通读输入
```

改了 `render.py`、`check.py` 或 `themes.json` 之后必须跑（CI 也会跑）。新增判断前先问：这能不能先写成一条护栏测试。

## 发布

排版完成后再调用。`--submit` 仅企业认证账号；个人账号止步于草稿。凭证、白名单、48001 排查见 [references/publish.md](references/publish.md)。

发之前先验收（不需要凭证、不联网）：

```bash
python3 scripts/publish.py --html 文章_frost.html --meta 文章_frost.meta.json --preflight
# Gate 1 结论 · 标题/作者/摘要（含官方上限与截断提醒）· 封面（按文章目录解析）· 待上传的正文图片数
```

先配一次 `config.json`（复制模板 `config.example.json`，已 gitignore 不入库）：
`appid` / `secret` / `author` / `source_url` / `need_open_comment` / `only_fans_can_comment` / `submit`。
优先级：命令行 > `--meta` > `config.json`；草稿还是正式发布由 config 的 `submit` 决定（默认 false 只建草稿）。

```bash
# 推荐：字段全部走 config.json + meta.json，命令行零参数
python3 scripts/publish.py --html 文章_frost.html --meta 文章_frost.meta.json
# 单次覆盖任意字段；留言默认开启（与编辑器一致），--no-open-comment 可关
python3 scripts/publish.py --html 文章_frost.html --cover images/cover.jpg --title "标题" --author "作者" --digest "摘要"

# 永久素材管理：封面同图复用（sha256 缓存，验活后复用，不再每次建草稿堆一张）
python3 scripts/publish.py --material-count
python3 scripts/publish.py --list-materials
python3 scripts/publish.py --delete-material MEDIA_ID  # 不可恢复，先核对
```

正文 HTML 不再印标题与作者名——它们只走草稿的原生字段，避免草稿里出现两次；
摘要不传时由 render 的 meta.json 提供（lead > deck > 首段，≤120 字），不让微信从正文开头乱抓。

AppSecret 只写进 `config.json`（已 gitignore），不要提交到仓库。

## 许可证

[MIT](LICENSE.txt) © 2026 cpikeo
