# Eval Cases：触发与主题选择回归用例

维护本 skill 后用这组用例核对。

## 正例（应触发排版）

- "帮我把这篇 Markdown 做成公众号排版"
- "微信公众号文章排版"
- "gzh，这篇用酌墨主题"
- "把这篇转成能直接粘进公众号的 HTML"
- "直接排，不用问我"（→ 全自动模式）
- "生成一套新主题/按这张参考图做"（→ theme-generator）
- "自动发布拿链接/配置 AppID"（→ auto-publish）

## 反例（不应触发）

- "帮我做一个网页落地页" → 前端 skill
- "做成 PPT" → PPT skill
- "帮我排版这个 Word 文档"（没说公众号）→ 说明需求
- "写一篇公众号文章"（只有话题没内容）→ 先写 Markdown 草稿，再排版

## 主题选择

- 深度分析/观点/教程/复盘/通用/不确定 → **静纸**
- 人物故事/品牌/访谈/回忆录/情感随笔 → **暖信笺**
- 深度评论/书评影评/行业观察/年度总结/反感 emoji → **酌墨**
- 用户明确指定 → 按用户说的
- 气质与三套都冲突 → 如实说明三套定位，走自定义主题生成
- 用户只说"直接排"→ 按类型自动判断，交付时说明理由

## 关键行为核对（用 assets/sample-article.md 跑一遍）

- [ ] 只读取一次全文、一次读入 themes.md，没有重复读文件
- [ ] 判断 Core Claim、Anchor Points、Pacing Plan 一次完成，不重复推理
- [ ] 只用了一套 Design Language 的组件，没跨主题混用
- [ ] 锚点 ≤4 处，落在真正重要的位置
- [ ] Core Claim 用了金句卡且全篇仅 1 次，位置是视觉高潮
- [ ] 导读在 ≥3 章节时才生成，紧跟头部
- [ ] 中文标点全角弯引号，代码/英文专名/URL 除外
- [ ] 代码块每行 `<p style="margin:0">`，无 `white-space:pre`
- [ ] 图片 `max-width:100%`，不用 `width:100%`
- [ ] 半角标点 WARNING 清零
- [ ] 署名区仅末尾一处，占位符已提示
- [ ] 无四周虚线框（待补素材块除外）
- [ ] 无 `<svg>`/图标库/图库外链
- [ ] 字号严格 6 级（11/13/15/16/17/22px）
- [ ] 中文大标题无负字距
- [ ] `<span leaf="">` 全覆盖，装饰空元素有 `<br>` 占位
- [ ] 跑完 validate + design_quality_check 两脚本，ERROR 0
- [ ] 通读完成 Editorial QA 12 项

## 维护循环

改了组件或 SKILL 后：
1. `python3 scripts/component_lint.py .` → 0 ERROR（源头关）
2. 排版 `assets/sample-article.md`（生成关）
3. `python3 scripts/validate_gzh_html.py <产物.html>` → 0 ERROR（产物关）
4. `python3 scripts/design_quality_check.py <产物.html> --accent ... --accent-quota 4` → 0 ERROR
5. 任一关不过回去修。
