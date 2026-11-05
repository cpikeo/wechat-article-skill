# 官方 API 交付（按需读取）

设计与事实验收见 [`SKILL.md`](../SKILL.md)；本文件仅说明 `scripts/publish.py`（纯 Python 3 标准库）。无凭证时仅可执行 `--preflight` 离线预检。

## 安全与权限边界

- **默认止于草稿，严禁持久发布授权**：只有本次命令行同时显式给出 `--submit --confirm-title "标题"`（标题与上行 `api_title` 逐字一致）才会调用发布接口；`config.json` 中写 `submit: true` 直接报错拒绝。
- **不可逆操作前置双确认**：草稿箱开关开启不可逆，仅在显式传入 `--enable-draft-switch` 时执行；永久素材删除不可恢复，必须在获取 `access_token` **之前**同时通过 `--delete-material <ID>` 与逐字一致的 `--confirm-delete-media-id <ID>` 及格式校验，未确认操作零网络副作用。
- **脱敏审计日志**：`--audit-log` 统一以 `0600` 文件权限写入，仅接受标量白名单字段（`submit` / `body_sha256` / `media_id` / `publish_id` / `error_type` / `media_id_sha256` / `stage` / `snapshot_sha256`），凭证与正文在结构上无法进入日志；异常输出自动脱敏 `secret` 与 `access_token`。
- **网络边界**：仅允许 HTTPS `api.weixin.qq.com:443/cgi-bin/`，拒绝 userinfo、非标准端口、片段与非官方主机；重定向不跟随，避免把 query token 转发到其它主机。`draft/add` 网络结果未知时不自动重试；回读异常或不一致时保留 `media_id` 并阻断发布。

## 配置与命令

复制 `config.example.json` 为 `config.json`（已被 `.gitignore` 忽略），或通过环境变量 `WECHAT_APPID` / `WECHAT_APPSECRET` 传入凭证（推荐环境变量，避免命令行历史暴露密钥）。优先级：命令行参数 > `--meta` > `config.json`。

```bash
# 1. 离线预检（无需凭证：校验 Gate 1、字段上限、封面/正文图存在性与同名 .meta.json 哈希一致性）
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --preflight

# 2. 上传素材并新建草稿 + 自动 API 回读核验（默认不发布）
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json --evidence-dir 回读证据/

# 3. 本次显式确认正式发布
python3 scripts/publish.py --html 正文.html --meta 正文.meta.json \
  --submit --confirm-title "文章标题"

# 4. 单独查询发布任务或管理永久素材
python3 scripts/publish.py --check-publish-id <PUBLISH_ID>
python3 scripts/publish.py --material-count
python3 scripts/publish.py --list-materials --material-type image
python3 scripts/publish.py --delete-material <MEDIA_ID> --confirm-delete-media-id <MEDIA_ID>
```

## 一致性与回读保护

- **字段上限硬门禁**：标题 32 字、作者 16 字、摘要 120 字；超限直接拒绝上行，绝不静默截断。
- **防陈旧稿侧车校验**：预检强制要求同名 `.meta.json`，核对 `integrity_version=3`、`skill_version`、`renderer_sha256`、`theme_config_sha256`、源 Markdown SHA-256、正文 HTML SHA-256 及全部正文图/封面 SHA-256；任一变更均要求重新运行 `render.py`。上行使用已冻结字节，不在上传时重新读取可能已变化的文件。
- **封面缓存验活**：永久封面按账号哈希 + 内容 SHA-256 缓存在 `.wechat_material_cache.json`（权限 `0600`，不存明文账号/凭证），复用前调用 `get_material` 验活；仅 `40007` 失效重传，凭证/权限错误直接终止。
- **草稿回读阻断防重**：创建草稿后立即调用 `draft/get` 核对 `title`、`content`、`thumb_media_id` 及已上行的 `author`、`digest`、`content_source_url`；回读失败或字段不一致时立即停止后续发布并打印已创建的 `media_id`，防止重复建稿。

## 官方接口参考与限制

- 新增草稿：`https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html`
- 获取永久素材：`https://developers.weixin.qq.com/doc/subscription/api/material/permanent/api_getmaterial.html`
- 遇到 `48001` 请依次排查接口权限、草稿箱开关与凭证；遇到 IP 白名单错误请核对当前机器出口公网 IP。API 回读通过不代替后台重开检查与手机微信真机验收。
