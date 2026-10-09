# Publish：官方 API 直发（可选）

先走完排版流水线，再读这份文档。脚本只用标准库：`scripts/publish.py`。

## 边界（先讲清楚）

- 做到的是"发布成正式文章、拿到链接"，不等于推送给粉丝。
- 两道门：草稿箱灰度开关（先查状态，不预设结论）；真发布（`--submit`）仅企业认证账号。

## 凭证

公众平台 `developers.weixin.qq.com` → 开发接口管理 → AppID + AppSecret。报 IP 白名单错时，在实际跑脚本的机器上查公网 IP 再加白。

## 封面

`--cover` 需要一张 2.35:1（900×383 起）的图片，默认不放文字——方向与安全区见 `references/direction.md` 封面工艺。渲染预览顶部会给出 2.35:1 与 1:1 两种裁切，用来确认主体不会被切掉。

## 命令

```bash
python3 scripts/publish.py --appid "ID" --secret "S" --check-draft-switch
# 推荐：消费 render.py 产出的发布字段文件（title 转｜ / author / digest / cover / 原文链接）
python3 scripts/publish.py --appid "ID" --secret "S" --html "文章.html" --meta "文章.meta.json"
# 或手工给字段；命令行逐项覆盖 --meta
python3 scripts/publish.py --appid "ID" --secret "S" --html "文章.html" --cover "封面.jpg" --title "标题" --author "作者" --digest "摘要"
# 企业认证加 --submit 真发布；查发布状态加 --check-publish-id ID
```

脚本自动处理：正文图片上传替换、封面永久素材、稳定版 token、发布轮询。

## 永久素材管理（封面复用 / 对账 / 清理）

草稿封面必须是**永久** MediaID。旧做法每次建草稿都 `add_material` 传新封面，
发几次就堆几张同款永久素材。现在：

- **复用**：封面按内容 sha256 记进 `.wechat_material_cache.json`（sha256→media_id），
  同图直接复用；复用前 `get_material` 验活，素材在后台被删（40007）会自动重传并更新缓存。
  `--no-reuse-cover` 强制重传；`--material-cache PATH` 换缓存位置。
- **对账**：`--material-count`（官方 GET 接口，image+news 上限 100000）看总量；
  `--list-materials [--material-type image|video|voice|news]` 翻页取全列表（count≤20/页）。
- **清理**：`--delete-material MEDIA_ID` 调 `del_material`，不可恢复——先 `--list-materials` 核对。
- **临时素材不接入**：`media/upload` 的临时素材 3 天过期、且 draft/add 封面要求永久 MediaID；
  正文图片走 `media/uploadimg`（返回 url，不占永久素材额度），两者都不要混。

## 与编辑器对齐的默认值（草稿底部状态）

- **留言**默认开启（`need_open_comment=1`），与编辑器新建文章的「留言自动精选公开」一致；
  API 自身默认是 0，不显式传，草稿底部会变成「不开启留言」。`--no-open-comment` 关、`--fans-only-comment` 仅粉丝。
- **原文链接**进 `content_source_url`（草稿底部「原文链接」）：frontmatter 写 `source:` 或 `--source-url`。
- **原创声明**API 没有对应参数：建草稿后到公众平台后台手动声明。
- **摘要**上限 120 字（2026-07-14 官方对齐 mp 端）；不传时用 render 的 `.meta.json`
  （lead > deck > 首段），不让微信从正文开头抓——抓到的开头不稳定（副题等），不是摘要。
- **标题/作者**只走原生字段：render 的正文 HTML 已不再印标题与作者名，草稿里不会出现两次；
  frontmatter 的 `|` 断行标记在原生标题栏自动转全角｜。

## 排查

| 现象 | 先看 |
|---|---|
| ip not in whitelist | 白名单里的是不是这台机器的公网 IP |
| 45004 | digest≤120字 / author≤16字 / title≤32字 |
| 建草稿 48001 | 开关状态 + token 有效性 + 接口权限，不预设单因 |
| --submit 48001 | 非企业认证，只能后台手动发布 |
| 一直"发布中" | 异步正常，轮询或稍后单查 |

信实际返回的 errcode，不死磕历史结论。
