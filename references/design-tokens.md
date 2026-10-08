# 高级配色 Design Token 库（公众号 / 官网 / 设计系统通用）

> **配套文档**：[editorial-identity.md](editorial-identity.md) 收录了另外 10 套按"阅读人格"（而非纯颜色名）组织的色板，以及一套排版节奏（字号/行高/段落长度/留白）的 WeChat 安全改编建议——两份文档地位相同，都是"配色预设 + 待落地"，选色板时可以两份一起看。

这是一份可复用的配色预设库，供 [theme-generator.md](theme-generator.md)「自定义主题生成」流程在收集用户偏好时直接引用——用户描述风格时如果匹配下面某一套的气质关键词，可以直接建议对应的 Token 组合，不用从零讨论五个颜色怎么选。**八套方案（方案一~六为原有配色预设，方案七/八是后续按「参考图比对说明」新增）目前都只是可选配色预设，没有对应的完整组件库**（本 Skill 唯一的内置主题「静纸 Silent Paper」用的是 [editorial-identity.md](editorial-identity.md) 里的另一套色板，不在这八套里）——用户明确要其中某一套落地时，走 `theme-generator.md` 的完整生成流程（收集偏好 → 生成区块库 → 转换登记，可参考 `theme-silent-paper.md` 从零设计的方法，而不是机械换色），不要只把颜色抄进现成组件库了事，因为组件的间距、字重、装饰细节也要跟着新气质调整，不是换个颜色变量就完事。

## 统一 Token 结构

新主题设计变量表建议按这个结构梳理（而不是一堆散装颜色值），方便复用和横向比较：

```yaml
color:
  primary: "#657565"      # 正文强调色 / 下划线专用，同时也是最高频出现的结构色
  secondary: "#97A091"    # 次级文字/署名/说明
  accent: "#C6A875"       # 锚点点睛色，必须和 primary 明显可区分，全篇 ≤3~5 处
background:
  page: "#F7F5F1"         # 引用块/目录卡/提示块背景，正文主体仍建议纯白
  surface: "#FFFFFF"      # 正文主体背景
text:
  primary: "#343633"      # 标题色
  secondary: "#7D827C"    # 次要文字
  inverse: "#FFFFFF"      # 深色底上的文字（如引用高亮块）
border:
  default: "#E4E1DA"      # 分割线/边框
  subtle: "#F0EEE9"       # 标签底色等更轻的边界
status:                   # 仅在需要状态提示类组件（成功/警告/风险/信息）时用得上
  success: "#6F8C6B"
  warning: "#C6A875"
  danger: "#B66A5E"
  info: "#6E8794"
shadow:
  light: "rgba(0,0,0,0.04)"
  medium: "rgba(0,0,0,0.08)"
```

**关键约束（决定这套 Token 能不能被 `design_quality_check.py --accent` 自动核查）**：`color.accent` 必须和 `color.primary` 视觉上明显不同（不能只是同色不同透明度），否则和 `accent` 复用 `primary` 的主题一样，只能靠人工核对"锚点层 ≤N 处"，见 `theme-index.md`「锚点强调色核查方式」表的判断逻辑。下面六套方案里，除了下面单独标注的，`accent` 都和 `primary` 拉开了色相/明度差，具备自动核查条件。

---

## 方案一：Nordic Sage（北欧鼠尾草）

气质：温暖、自然、治愈、耐看。视觉关键词：MUJI + Aesop + 北欧家居。适合：植物、面包、咖啡、品牌官网、公众号。

| Token | 说明 | HEX |
|---|---|---|
| Primary | 鼠尾草绿 | `#6F8573` |
| Secondary | 浅橄榄灰 | `#A7B1A3` |
| Accent | 亚麻米色 | `#DCCFB8` |
| Background | 奶白 | `#F7F6F2` |
| Surface | 暖白 | `#FFFFFF` |
| Text | 深灰 | `#353535` |
| Muted | 冷灰 | `#7E827D` |
| Border | 雾灰 | `#E5E4DF` |

> 注意：Accent（亚麻米色 `#DCCFB8`）和 Primary（鼠尾草绿 `#6F8573`）色相拉开了，具备自动核查条件；但亚麻米色明度较高、和背景奶白 `#F7F6F2` 接近，实际落地成组件时要注意锚点色的对比度是否够，必要时加深或用于底色而非文字色。

## 方案二：Warm Stone（暖岩石）

气质：高级酒店风、Apple Store、侘寂。

| Token | HEX |
|---|---|
| Primary | `#5D645E` |
| Secondary | `#8F948C` |
| Accent | `#C9B89B` |
| Background | `#F6F4EF` |
| Surface | `#FFFFFF` |
| Text | `#2F302D` |
| Border | `#E8E4DC` |

## 方案三：Forest Minimal（森林极简）

气质：Apple × Patagonia。适合：公众号、设计网站、植物、户外。

| Token | HEX |
|---|---|
| Primary | `#4E6B58` |
| Secondary | `#7F9583` |
| Accent | `#C8AE79` |
| Background | `#FAF9F5` |
| Surface | `#FFFFFF` |
| Text | `#303430` |
| Border | `#E7E5DF` |

## 方案四：Soft Linen（亚麻纸张）

气质：杂志风、Monocle、Kinfolk，阅读体验佳。

| Token | HEX |
|---|---|
| Primary | `#7A746A` |
| Secondary | `#B1A89A` |
| Accent | `#D8C6A6` |
| Background | `#FBFAF7` |
| Surface | `#FFFFFF` |
| Text | `#363534` |
| Border | `#ECE9E2` |

> 注意：Primary（`#7A746A`）和 Accent（`#D8C6A6`）都偏暖灰调、明度差主要靠深浅拉开而非色相，自动核查前建议先用 `component_lint.py` 跑一遍新生成的组件库，确认锚点组件的颜色出现频次和结构色（下划线等）不会被同一份正则误判为同一种颜色（两者 hex 本身不同，脚本按精确 hex 字符串匹配，不受"看起来接近"影响，但人眼审阅时要留意区分度）。

## 方案五：Modern Ink（现代墨色）

气质：Linear、Raycast、Arc 风格。适合：科技、AI、软件、官网。

| Token | HEX |
|---|---|
| Primary | `#2F4B59` |
| Secondary | `#70828A` |
| Accent | `#B8A06A` |
| Background | `#F8F8F6` |
| Surface | `#FFFFFF` |
| Text | `#26282B` |
| Border | `#E7E8E6` |

## 方案六：Sand & Olive（沙丘橄榄）

气质：自然、安静、克制、高级、长期耐看。融合 Apple、COS、Aesop、Notion、MUJI。这是六套里色相区分度最好、最适合自动化设计质检的一套，但**目前还没有对应的完整组件库**（此前落地过一版，是机械换色而非真正的重新设计，已经和其它 6 套旧主题一起下线删除）。想要这套气质的话，走 `theme-generator.md` 流程重新设计，可以参考 `theme-silent-paper.md` 的方法——围绕色板重新思考间距、字号阶梯、强调手法，而不是复用别的主题骨架改色值。

| Token | HEX |
|---|---|
| Primary | `#657565` |
| Secondary | `#97A091` |
| Accent | `#C6A875` |
| Background (page) | `#F7F5F1` |
| Surface | `#FFFFFF` |
| Text | `#343633` |
| Muted | `#7D827C` |
| Border | `#E4E1DA` |
| Border subtle | `#F0EEE9` |

---

## 参考图比对说明（方案七/八的登记依据）

2026-07 用户提供了 10 张公众号排版参考 HTML（Aesop / Apple Journal / Botanical Letter / COS Minimal / Dark Olive / Financial Times / Kinfolk / Monocle / Museum White / Nordic Morning）用于优化本 Skill，逐一提取主色后发现：Botanical Letter / COS Minimal / Dark Olive / Museum White / Nordic Morning 这 5 套的名字和定位与 [editorial-identity.md](editorial-identity.md) 第四节已登记的同名条目重合（其中 Botanical Letter 参考图实际用的强调色 `#B4654A` 与该文档原先登记的 `#70846C` 不一致，已按参考图数值更新 `editorial-identity.md`，详见该文档第四节的修正说明）；Aesop 的强调色 `#6B7D6A` 与静纸 Silent Paper 的 `#6A7567` 属于同一鼠尾草绿色系，Financial Times 的强调色 `#8C7B65` 与 Kinfolk 的 `#8B7F6B` 几乎无法用肉眼或 `design_quality_check.py --accent` 区分——这几套不重复登记为独立方案，避免和已有资产撞色、也避免自动核查因色相区分度不足而失效。**只有 Apple Journal（蓝）和 Monocle（深青）带来了本库目前完全没有的新色相**，登记为下面的方案七、方案八，用于补齐科技评测/国际时评类内容目前三套内置主题（静纸/暖信笺/酌墨）都不太适配的空白。

## 方案七：Apple Journal（科技蓝调）

气质：产品发布记录感、极简科技感、克制但有信息密度。视觉关键词：科技媒体长文 × 产品评测。适合：科技测评、产品/软件发布解读、工具类公众号——本库现有三套内置主题（静纸/暖信笺/酌墨）都偏人文/生活方式气质，这套补上"理性科技"这个缺口。

| Token | 说明 | HEX |
|---|---|---|
| Primary | 深灰黑，正文强调色 | `#101010` |
| Secondary | 次级文字/说明 | `#4C4C4C` |
| Accent | 品牌蓝，锚点点睛色 | `#2563EB` |
| Background (page) | 浅灰蓝，卡片/引用块底 | `#F3F4F6` |
| Surface | 正文主体背景 | `#FFFFFF` |
| Muted | 次要文字/图注 | `#999999` |
| Border | 分割线 | `#E0E0E0` |

> Accent `#2563EB` 是本库 16+2 套色板里**唯一的蓝色相**，和 Primary（近黑）色相/明度都拉开明显差距，具备自动核查条件，建议全篇用量 ≤4 处（`--accent '#2563EB' --accent-quota 4`）。目前仍只是色板预设，未生成完整组件库，真正要落地时走 `theme-generator.md` 流程。

## 方案八：Monocle Ink（深青时评）

气质：国际时评、深度报道、严谨但不失设计感。视觉关键词：国际新闻周刊 × 版式严谨的评论栏目。适合：国际观察、时事评论、深度报道类公众号——和酌墨（文人刊物感、衬线标题）气质相近但更"新闻编辑室"、更少书卷气，两者可以按内容具体气质二选一。

| Token | 说明 | HEX |
|---|---|---|
| Primary | 近黑，正文强调色 | `#111111` |
| Secondary | 次级文字 | `#333333` |
| Accent | 深青，锚点点睛色 | `#2A4545` |
| Background (page) | 卡片/引用块底 | `#F9F9F8` |
| Surface | 正文主体背景 | `#FFFFFF` |
| Muted | 次要文字/图注 | `#999999` |
| Border | 分割线 | `#DDDDDD` |

> Accent `#2A4545` 是本库唯一的深青色相，和 Primary（近黑）区分明显，具备自动核查条件，建议全篇用量 ≤4 处（`--accent '#2A4545' --accent-quota 4`）。同样仍只是色板预设，未生成完整组件库。

---

## 可选装饰工具：Soft Gradient / Ambient Glow

外部资料建议的一批"氛围感"视觉手法（雾化、噪点、纸张纹理、毛玻璃、杂志网格线）在公众号平台的 HTML 约束下大多无法落地，可行性核查见 [editorial-identity.md](editorial-identity.md) 第七节。**只有下面两种是真实可用的**，登记在此供新主题设计时按需取用（不建议加进静纸 Silent Paper，理由同样见该节）：

```yaml
atmosphere:
  soft_gradient: "linear-gradient(180deg, #FFFFFF 0%, #FAFAF8 100%)"   # 页面/大块背景可选的极轻微渐变，深浅差控制在 2%~3% 明度以内，不要做成能被一眼看出"有渐变"的程度
  ambient_glow: "0 20px 60px rgba(0,0,0,.04)"                          # 卡片阴影的"空气感"版本：扩散半径大、不透明度极低，区别于普通阴影 0 4px 12px rgba(0,0,0,.08) 的"贴地感"
```

用法边界：这两个是**装饰工具**，不是必须使用的默认值；一套新主题的"设计语言"定位（见 `editorial-identity.md` 第八节）如果 Weight 维度是"低"，就不该用 ambient_glow；只有 Weight 定位"中"及以上、且确实需要卡片/区块从背景中"浮起来"的主题才考虑用。

## 如果用户想要方案一~五、七、八落地成正式主题

1. 确认用户要哪一套（或基于哪一套二次调整），把上面的 Token 表当作`theme-generator.md`收集偏好步骤里的"主色/强调色"输入，不用再单独问色值。
2. 其余偏好（字体、圆角、阴影、三类 TAG 命名）仍按 `theme-generator.md` 正常流程收集或取默认值。
3. **参考 `theme-silent-paper.md` 的方法：围绕新色板重新设计间距、字号阶梯、强调手法**，不要机械复用别的主题骨架只换 hex——本 Skill 之前有一版「沙丘橄榄」就是这么做的，结果只是换了颜色的旧组件，被判定"不够高级"后连同其它旧主题一起删除重做。真正决定质感的是节奏和克制，不是颜色本身。
4. 生成后务必跑 `component_lint.py` 和至少一次 `design_quality_check.py`（若 Accent 与 Primary 色相区分明显则带 `--accent` 参数），并按 SKILL.md 第 5.5 步的方法**实际拼一篇真实文章渲染出来看**，参照 `theme-silent-paper.md` 落地时"拼文章→渲染→挑毛病→改组件→再渲染"的检查顺序，不要只凭代码审查判断"应该好看"。
5. 登记进 `theme-index.md`，同时在「锚点强调色核查方式」表里补一行，写清楚这套新主题的锚点色是否独立于结构色。
