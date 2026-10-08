# Platform：微信公众号硬约束

渲染器已内置全部约束（`scripts/check.py`，随渲染自动跑）。人要记住的只有：

**禁**：`<style>/<script>/<div>/<svg>`、class/id、定位/float/grid、`@`规则、CSS 变量、外部字体、图库与图标库外链、`white-space:pre`。

**必须**：样式全内联；文字包 `<span leaf="">`；空装饰元素内放 `<span leaf=""><br></span>`；图片 `max-width:100%`；本地图片随产物交付（手动粘贴时用户自上传，API 直发时脚本自动上传）。

**可用**：有限 flex、linear-gradient、圆角、阴影、系统字体（含宋体衬线、等宽）。

Gate 1 FAIL = 粘贴后一定坏，修到 PASS 才交付。半角标点、字号超 6 级是「建议改」，逐条确认。预览按 390px，不要按桌面宽度判断。
