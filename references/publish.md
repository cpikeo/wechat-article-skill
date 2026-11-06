# 官方 API 交付（按需读取）

发布即上行。本文件只写 `scripts/publish.py` 的操作与权限边界；三级验收定义以 [`SKILL.md`](../SKILL.md) 为唯一真源。无凭证时只有 `--preflight` 可用（纯离线）。

## 权限与不可逆操作

- **默认止于草稿**：只有本次命令行同时给出 `--submit --confirm-title "标题"`（逐字等于上行标题）才调用发布接口；`config.json` 里写 `submit: true` 直接报错——一次设置不能影响以后的普通运行。
- **不可逆动作先双确认**：草稿箱开关开启不可逆，只在显式 `--enable-draft-switch` 时执行；永久素材删除不可恢复，须在取 `access_token` **之前**给出 `--delete-material <ID>` 与逐字一致的 `--confirm-delete-media-id <ID>`，未确认的破坏性调用零网络副作用。
- **网络只认官方源**：仅 HTTPS `api.weixin.qq.com:443/cgi-bin/`，拒绝 userinfo、非标准端口、片段与非官方主机，不跟随重定向（避免 query token 转发）；`draft/add` 网络结果未知时不自动重试。
- **审计日志脱敏**：`--audit-log` 以 `0600` 追加写入，只接受标量白名单字段（哈希、media_id、publish_id、事件名），凭证与正文在结构上进不去；异常输出自动脱敏 `secret` 与 `access_token`。

凭证走 `WECHAT_APPID` / `WECHAT_APPSECRET` 环境变量（推荐）或 `config.json`。优先级：命令行 > `--meta` > `config.json`。

## 命令

```bash
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --preflight   # 离线预检
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --evidence-dir 回读证据/
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --submit --confirm-title "文章标题"
python3 scripts/publish.py --check-publish-id <PUBLISH_ID>
python3 scripts/publish.py --material-count | --list-materials --material-type image
python3 scripts/publish.py --delete-material <MEDIA_ID> --confirm-delete-media-id <MEDIA_ID>
```

## 一致性与回读

- **字段上限硬门禁**：标题 32 字（平台字段上限 64，这里按公众号列表页的编辑口径收紧）、作者 16 字、摘要 120 字；超限拒绝上行，绝不静默截断。
- **侧车防陈旧**：强制同名 `.meta.json`，核对 `integrity_version`、`skill_version`、`renderer_sha256`、`theme_config_sha256`、源稿哈希、正文哈希与全部素材哈希；任一变化即要求重渲染。上行用的是已冻结字节，不在上传时重读可能变化的文件。
- **封面缓存验活**：永久封面按“账号哈希 + 内容 SHA-256”缓存在 `.wechat_material_cache.json`（`0600`，不存明文账号），复用前调 `get_material` 验活；只有 `40007` 才重传，凭证/权限错误直接终止。
- **正文按归一化核验**：微信写入期必然重写正文——`'`→`&#39;`、图片地址换成 `mmbiz.qpic.cn` 并补 `data-src`、重排 `alt`、无外链权限时剥掉 `<a>`、插入 `display:none` 的 `mp-style-type`。核验口径是纯文本逐字 + 块结构计数 + 图片张数，不要求 HTML 逐字节相等。
- **封面判据**：新草稿接口回读 `thumb_media_id` 常为空串而封面其实已绑定，故按 `thumb_media_id` 或 `thumb_url` 之一判定，并在证据里记 `cover_binding`。
- **回读失败即停**：创建草稿后立即 `draft/get` 核对，字段不一致时打印已创建的 `media_id` 并阻断发布，绝不自动重建。

## 接口与排查

- 新增草稿：`https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html`
- 获取永久素材：`https://developers.weixin.qq.com/doc/subscription/api/material/permanent/api_getmaterial.html`
- `48001` 不要预设单因：依次查接口权限、草稿箱开关、凭证。IP 白名单报错核对本机出口公网 IP。API 回读通过不代替后台重开与真机验收。
