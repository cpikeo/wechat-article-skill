---
name: wechat-article
description: 把 Markdown/Word/纯文本排成可直接粘贴进公众号编辑器的编辑设计水准 HTML。判断驱动：先写 Decision（受众→主张→层级→节奏→主题→删什么），再 Compose，一次渲染生成正文 HTML + 手机预览 + 合规/构成检查。可选官方 API 建草稿/发布。触发：公众号排版/微信排版/gzh/一键排版/自动发布/新主题。不用于普通网页/落地页/PPT。
---

# WeChat Article · Editorial Intelligence

把一篇文章变成值得读完、值得记住的公众号成品。代码是执行器，主题是材料，原语是工具。**Design Judgment 才是最高层。**

不要先选主题再填文章。先判断，再设计。每一个元素必须有信息职责。

## 流水线

```
UNDERSTAND → JUDGE → EDIT → DIRECT → COMPOSE → RENDER → VERIFY
```

| 步骤 | 做什么 |
|---|---|
| 1 Understand | 只读一次原文：谁在读、为何读、读完记住什么 |
| 2 Judge | 读 `references/decide.md`，写 Decision（10 行） |
| 3 Edit | 按 Decision 修文字。不改事实 |
| 4 Direct | 不另写文档。Peak、节奏、图职责、主题、Cut 写进 Decision 后半 |
| 5 Compose | 输出 Composed Markdown |
| 6 Render | `python3 scripts/render.py 文章.md` → HTML + 390px 预览 + Gate 1/2 |
| 7 Verify | 通读预览做 Gate 3。只写必须改 / 建议改 / 保留 |

默认全自动。交付：Decision + 三关结论 + 用户待办（署名 / 补素材 / 粘贴）。

## 只加载需要的知识

| 何时 | 读什么 |
|---|---|
| 每次 | 本文件 |
| 写 Decision / Gate 3 | `references/decide.md` |
| Gate 1 FAIL | `references/platform.md` |
| 发布 / 草稿 / 凭证 | `references/publish.md` |
| 回归 | `eval/` 三篇源用例 |
| 不要读 | `scripts/*`、AUDIT |

脚本不是设计规则来源。

## 路由

| 用户说 | 做 |
|---|---|
| 排版 / 公众号 / gzh / 转 HTML | 七步流水线 |
| `.docx` | 先 `python3 scripts/extract_docx.py 文件.docx -o 文章.md`，再流水线（图必须补职责） |
| 只要润色 | 只 Edit |
| 发布 / 草稿 | 先流水线，再读 `references/publish.md` |
| 新主题 | `decide.md` 末尾 |

## Decision（导演 brief，10 行）

不是 JSON。不确定写「未知，按默认」。不许编造。

```
Audience:  谁在读，在什么场景读（通勤滑 / 坐下来读）
Purpose:   读完应该理解、相信、或做什么
Core Claim:全文最值得记住的一句话（落入 Peak）
Hierarchy: 主 / 次 / 弱化或删除
Tone:      六种 Editorial Mode，见 decide.md。气质都不对就说，不硬套
Density:   dense | standard | airy
Rhythm:    首屏钩子 → 停顿 → 高潮 → 恢复 → 收束（按 390px 想）
Anchor:    Peak 之外 0–2 处停留；没有就写「无」
Image:     每张图的职责；说不出就删；不发明图
Cut:       准备删掉或降级的（至少一项）
```

## Compose = Visual Hierarchy Vocabulary

**Core Claim > Section Claim > Evidence > Explanation > Metadata > Decoration**

能用纯文字就不用原语。

```yaml
---
title: 主标题|断行后半
kicker: LETTER
theme: letter          # paper / letter / ink / frost / bone / folio
density: airy          # dense / standard / airy
deck: 一句副题         # 可选；与 lead 不要叠两个钩子
date: 2026年10月8日
toc: true              # ≥3 个 H2 才生效
author: 甲木
bio: 一句话简介
cta: 结尾一句话        # 不写则无
---
```

| 写法 | 职责 |
|---|---|
| `> 开头` | lead，首屏钩子；没有就不写 |
| `::: peak` | 全文唯一高潮 = Core Claim |
| `> 正文` | quote，他者声音；不要做成第二个 Peak |
| `::: data` | 数字并置；关系靠并排才成立时 |
| `::: note 标签` | 旁注；删掉也不伤主线 |
| `==标记==` | 关键判断，全篇 ≤3 |
| `**加粗**` | 弱强调，少用 |
| `![说明](路径 "职责")` | 职责必填：信息/证据/氛围/隐喻/停顿/锚点/数据；`todo`=待补 |
| `---` | 转场；少于 H2 数 |
| H2 / H3 | Section Claim；标题后必须接正文 |

## QA

- **Gate 1 Platform**：脚本。FAIL 不交付。
- **Gate 2 Composition**：脚本。必须改修完；建议改给理由（改或保留）。
- **Gate 3 Art Direction**：通读 390px 预览。十问见 `decide.md`。核心：**哪一个元素应该消失？**

## 硬规则

1. 不手写 HTML，不改渲染器输出——要改就改 Composed Markdown。
2. 不编造引言、数据、出处、图片说明。
3. 图片本地化；说不出职责的删除。
4. 为「看起来丰富」加的元素，全部进 Cut。
5. Gate 1/2 有「必须改」就不交付。
