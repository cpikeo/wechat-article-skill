# Platform：微信公众号硬约束

渲染器已内置全部约束（`scripts/check.py`，随渲染自动跑）。人要记住的只有：

**禁**：`<style>/<script>/<div>/<svg>`、class/id、定位/float/grid、`@`规则、CSS 变量、外部字体、图库与图标库外链（图片外链一律 FAIL，必须本地化后由用户上传或 API 上传）、`white-space:pre`。

**必须**：样式全内联；文字包 `<span leaf="">`；空装饰元素内放 `<span leaf=""><br></span>`；图片 `max-width:100%`。

**可用**：有限 flex、linear-gradient、圆角、阴影、系统字体（含宋体衬线、等宽）。

图片尺寸下限与落地命名见 `references/direction.md`「素材落地」；封面比例与安全区见「封面工艺」。

Gate 1 FAIL = 粘贴后一定坏，修到 PASS 才交付。半角标点、字号超 6 级是「建议改」，逐条确认。预览按 390px，不要按桌面宽度判断。
