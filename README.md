# wechat-article

判断驱动的公众号 **Editorial Intelligence**。

把 Markdown / Word / 纯文本，排成可直接粘贴进微信公众号编辑器的成品 HTML。先写 Decision，再构成，再渲染。主题是人格，不是皮肤。

```
UNDERSTAND → JUDGE → EDIT → DIRECT → COMPOSE → RENDER → VERIFY
```

**不是** 组件库、换色模板、普通网页或 PPT 排版。每一个元素必须有信息职责；说不出职责的，删。

## 要求

Python 3。只用标准库，无需 `pip install`。

## 快速开始

```bash
python3 scripts/render.py 文章.md
# 产出 文章_{theme}.html          ← 粘贴进公众号
#      文章_{theme}_预览.html    ← 390px 对照 + 一键复制
```

| 输入 | 命令 |
|---|---|
| Markdown | `python3 scripts/render.py 文章.md` |
| 指定主题 | `python3 scripts/render.py 文章.md --theme frost` |
| Word | `python3 scripts/extract_docx.py 文件.docx -o 文章.md`，再渲染（图必须补职责） |
| 发布草稿 | `python3 scripts/publish.py --help`（先排完再发） |

退出码 `1` = Gate 1/2 仍有「必须改」，不要交付。

最小文章：frontmatter + 正文。语法见 [SKILL.md](SKILL.md)。

```yaml
---
title: 主标题|断行后半
theme: paper          # paper / letter / ink / frost / bone / folio
density: standard     # dense / standard / airy
author: 甲木
---
```

## 六个 Editorial Mode

不是六套配色。字号 6 级锁定；主题只决定气候与标记语言。对照标本：[assets/themes.html](assets/themes.html)。

| 主题 | 气候 | 用于 | 标记 |
|---|---|---|---|
| `paper` 静纸 | 暖石 · 干苔 | 观点、分析、教程、默认 | 数字章节 · 细线高潮 |
| `letter` 暖信笺 | 信笺 · 火漆 | 叙事、人物、随笔 | 圆点章节 · 暖底高潮 |
| `ink` 酌墨 | 象牙 · 干血 | 评论、书评、年度 | 图章 · 衬线 · 深色高潮 |
| `frost` 北霜 | 北昼 · 峡湾 | 调查、科技、旁观 | 数字章节 · 冷底高潮 |
| `bone` 素作 | 石膏 · 铜尘 | 品牌、工艺、空间 | 无编号 · 衬线 · 细线高潮 |
| `folio` 特稿 | 油墨 · 干朱 | 文化特稿 | 数字章节 · 深色高潮 · 无衬线 |

先判断语气，再选主题。气质对不上，不要硬套。

## 怎么用这套 Skill

给 Agent 读 [SKILL.md](SKILL.md)。它会：只读一次原文 → 写 10 行 Decision → 编辑文字 → 输出 Composed Markdown → 一次渲染 → 通读 390px 预览。

判断细则：[references/decide.md](references/decide.md)。平台硬约束只在 Gate 1 失败时读 [references/platform.md](references/platform.md)。

## QA

| 关 | 谁来 | 不过就怎样 |
|---|---|---|
| Gate 1 Platform | `scripts/check.py`（随渲染） | FAIL 不交付 |
| Gate 2 Composition | 渲染器 | 「必须改」修完；「建议改」给理由 |
| Gate 3 Art Direction | 通读预览 | 高潮是不是 Core Claim；哪一个元素应该消失 |

## 仓库

```
SKILL.md                 智能：流程、语法、硬规则
references/decide.md     判断：Decision、六种人格、Gate 3
references/platform.md   微信 HTML 硬约束（按需）
references/publish.md    官方 API 草稿 / 发布（按需）
assets/themes.json       六种 Editorial Mode
assets/themes.html       同一标本、六种气候（设计对照，不进公众号）
scripts/render.py        一次调用：HTML + 预览 + Gate 1/2
scripts/check.py         Gate 1
scripts/extract_docx.py  Word → Markdown
scripts/publish.py       草稿 → 可选发布
eval/                    三篇源用例：skills / letter / ink
AUDIT.md                 架构审计
```

脚本不是设计规则来源。规则在 `SKILL.md` 与 `decide.md`。

## 回归

改了 `scripts/render.py` 或 `assets/themes.json` 之后，三篇源用例必须 Gate 1/2 全过。

```bash
cd eval
for f in skills letter ink; do python3 ../scripts/render.py $f.md -o /tmp/$f.html || exit 1; done
```

## 发布

排版完成后再调用。`--submit` 仅企业认证账号；个人账号止步于草稿。凭证、白名单、48001 排查见 [references/publish.md](references/publish.md)。

```bash
python3 scripts/publish.py --appid "$APPID" --secret "$SECRET" \
  --html 文章_paper.html --cover 封面.jpg --title "标题" --author "作者" --digest "摘要"
```

不要把 AppSecret 写进仓库。
