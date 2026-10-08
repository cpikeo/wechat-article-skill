# Platform Rules：微信公众号平台约束（唯一权威来源）

本文档是平台合规的唯一权威来源。所有"什么能用什么不能用"以此处为准，其他文件不再重复列举。

---

## 标签白名单

**允许**（基础标签）：
`<section> <p> <span> <strong> <em> <br> <img> <h3> <a> <figure> <figcaption> <hr>`

**禁止**（粘贴后被清洗/剥离）：
`<style> <script> <div> <link> <svg> <form> <input> <button> <textarea> <select> <video> <audio> <canvas> <iframe>`

**属性禁止**：`class`、`id`（会被剥离）

---

## CSS 约束

**禁止**：
- `position: fixed / absolute / sticky`、`float`
- `@media`、`@keyframes`、`@import`、`@font-face`
- `display: grid`
- CSS 变量 `var(--x)`
- 外部字体 `url(...woff2/ttf/otf/eot)`
- `backdrop-filter`、复杂滤镜
- 外部 CSS/JS/图标 CDN（`unpkg.com`、`jsdelivr.net`、`cdn.jsdelivr` 等）
- `radial-gradient` / `conic-gradient`（只允许 `linear-gradient`）
- `white-space: pre`（代码块禁用，会导致 HTML 源码缩进/换行被渲染成大空行）
- 图标库/图库外链图片（`unsplash.com`、`pexels.com`、`pixabay.com` 等原始 URL）

**可用**：
- 所有样式必须**内联** `style="..."`
- 有限 `display: flex`
- `linear-gradient`
- `border-radius`、`box-shadow`
- `margin`、`padding`、`color`、`background`、`font-size`、`line-height`、`font-weight`、`text-align`、`border`、`width/height/max-width/min-width`、`box-sizing`
- `font-family` 可以指定**系统预装字体**（如 `"Songti SC","STSong","SimSun",serif`、`Consolas,Monaco,monospace`），不能引用外部字体文件

---

## 必做（否则粘贴后样式丢失）

1. **所有文字节点**必须用 `<span leaf="">文字</span>` 包裹。
2. **装饰性空元素**（分割线、留白占位、细线 span、空 `<section>` 等）内部必须放 `<span leaf=""><br></span>` 占位——否则微信会把看起来"空"的容器连同样式一起剥掉。
3. 代码块每行用 `<p style="margin:0">`，缩进用全角空格 `　`，**不用 `white-space:pre`**。
4. 图片 `max-width:100%;height:auto;display:block;margin:0 auto`，避免固定大宽度（`width:560px` 等）导致手机端横向溢出。
5. 中文大字号标题**禁用负字距**（`letter-spacing` 负值）。
6. 正文标点一律全角弯引号（代码/英文专名/URL 除外）。

---

## 图标规则

- **可以用**：
  - Unicode 排版符号：`→ ✓ ◎ · ※ ◇ ♡ ↗` 等（最推荐）
  - CSS 几何图形：`<span style="width:6px;height:6px;border-radius:50%;background:...">` 圆点/竖线/细线
  - 数字/文字编号：`01` `CHAPTER` `PART`
  - 少量 emoji（仅限已在主题组件里定义的场景，如结尾互动区）
- **禁止**：`<svg>` 标签、Lucide/Phosphor/Heroicons 等图标库、npm/react 图标组件、第三方 Icon CDN（Iconify/Icones/SVG Repo 的 SVG 源码不直接嵌）
- SVG 插图（unDraw/Storyset 等）必须先导出为 PNG/JPG，再按图片流程处理

---

## 图片规则

- 图片 `src` 必须是**本地文件路径**（手动流程由用户在编辑器自上传；API 直发流程脚本自动上传替换成微信域名 `mmbiz.qpic.cn`）。
- 不直接引用图库网站外链 URL（Unsplash/Pexels/Pixabay 原始链接）——既可能防盗链，也可能被接口过滤，链接失效后图片消失。
- GIF 动图同样用 `<img>` 处理，公众号原生支持 GIF 自动播放。

---

## 校验脚本（强制执行）

**第一关 合规**（必须 0 ERROR；半角标点 0 WARNING）：
```bash
python3 scripts/validate_gzh_html.py <file.html>
```

**第二关 设计质检**（必须 0 ERROR；WARNING 逐条复核有理由）：
```bash
python3 scripts/design_quality_check.py <file.html> --accent '<HEX>' --accent-quota 4
```

**第三关 Editorial Judgment**（人工通读，见 design-system.md 第九节）。

三关全过才交付。
