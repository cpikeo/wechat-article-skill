---
name: wechat-article
description: 把 Markdown/Word/纯文本排成可直接粘贴进公众号编辑器的编辑设计水准 HTML。判断驱动：先写 Decision（受众→主张→层级→节奏→主题），再输出 Composed Markdown，一次渲染生成正文 HTML + 手机预览 + 合规/构成检查。可选官方 API 建草稿/发布。触发：公众号排版/微信排版/gzh/一键排版/自动发布/新主题。不用于普通网页/落地页/PPT。
---

# WeChat Article · 编辑设计智能

把一篇文章变成值得读完、值得记住的公众号成品。判断驱动，不是模板套色。

## 流水线

```
UNDERSTAND → JUDGE → EDIT → COMPOSE → RENDER → VERIFY
```

| 步骤 | 做什么 | 说明 |
|---|---|---|
| 1 Understand | 只读一次原文：受众、目的、核心主张、结构 | 不重复读文件 |
| 2 Judge | 写 Decision（9 行），选主题 | 见 `references/decide.md` |
| 3 Edit | 按 Decision 修文字：断段、降级多余强调、删废话 | 不擅改事实与观点 |
| 4 Compose | 按 Decision 重排结构，输出 Composed Markdown | 见下面「Compose 语法」 |
| 5 Render | 一次调用：HTML + 手机预览 + Gate 1/2 报告 | `python3 scripts/render.py 文章.md` |
| 6 Verify | 通读预览（Gate 3），交付 | 不打分，只写必须改/建议改/保留 |

默认全自动：不问用户，直接走完六步。交付时附 Decision + 三关结论 + 用户待办（替换署名/补素材/粘贴）。

## 路由

| 用户说什么 | 做什么 |
|---|---|
| 排版/公众号/gzh/转成 HTML/直接排 | 六步流水线 |
| .docx 输入 | 先 `python3 scripts/extract_docx.py 文件.docx -o 文章.md`，再进流水线 |
| 润色/改文字（不要排版） | 只做 Edit，不 Render |
| 自动发布/建草稿/拿链接/配凭证 | 先走完流水线，再读 `references/publish.md` |
| 新主题/换风格/按参考图做 | 按 `references/decide.md` 末尾加一节到 `assets/themes.json`，并跑通回归 |

## Compose 语法

标准 Markdown，只加四样东西。

frontmatter（标题 `|` 处断行；toc 需 ≥3 章才生效）：

```yaml
---
title: 主标题|断行后半
kicker: LETTER
theme: letter        # paper / letter / ink
density: airy        # dense / standard / airy
date: 2026年10月8日
toc: true
author: 甲木
bio: 一句话简介
cta: 结尾一句话（不写则没有）
---
```

正文：

| 写法 | 含义 |
|---|---|
| `> 开头引用` | lead 引言（首屏钩子）；正文中的 `>` 是 quote；末行 `——来源` 是出处 |
| `::: peak … :::` | 全文唯一 Visual Peak：Core Claim 落在这里，全篇只许一次 |
| `::: note 标签 … :::` | 旁注；`::: data … :::` 数字摘要（每行 `数字｜说明`） |
| `==标记==` | 稀缺强调（全篇 ≤3）；`**加粗**` 只做弱强调；多数段落完全不强调 |
| `![说明](路径 "职责")` | 图片职责必填；路径写 `todo` 生成待补素材位 |
| `---` | 章节转场（按主题渲染为圆点/细线/图章） |

## Decision（判断先行，9 行）

```
Audience / Purpose / Core Claim / Tone / Density / Visual Anchor / Image Strategy / Design Language / Composition
```

一行一个判断。不确定的写"未知，按默认"——不许编造。主题选择：沉静克制 → paper；温暖叙事 → letter；笃定评论 → ink。细则见 `references/decide.md`。

## QA 三关

- **Gate 1 Platform**（脚本，随渲染自动跑）：FAIL 就修到 PASS，不交付 FAIL。
- **Gate 2 Composition**（脚本，随渲染自动跑）：必须改修完；建议改逐条给理由（改或保留）。
- **Gate 3 Art Direction**（通读预览）：首屏凭什么让人读下去？高潮是不是 Core Claim？哪一个元素删掉更好？结论只写必须改/建议改/保留，不打分。

## 硬规则

1. 不手写 HTML，不拼 `<section>`，不改渲染器输出——要改就改 Composed Markdown 重渲染。
2. 不编造：引言、数据、金句出处、图片说明，没有就不写。
3. 图片本地化：先下载到本地再引用，不用外链；说不出职责的图片删除。
4. Gate 1/2 有"必须改"就不交付。
