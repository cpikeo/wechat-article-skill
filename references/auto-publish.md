# Auto Publish：官方 API 直发（可选）

**边界先讲清楚**：
- 做到的是"把文章发布成一篇正式文章、拿到链接"，**不等于**"主动推送消息提醒所有粉丝"（那是另一套受限群发机制，不提供、不暗示能做到）。
- 两道独立门槛：
  1. **草稿箱灰度开关**（`draft/switch`）：和认证无关。开关未开是否一定导致建草稿失败，2026-07 复核后证据不确凿（官方文档同时写了"无论开关与否新旧 API 均可使用"）。遇到 `48001` 把开关状态作为排查方向之一，不预设是唯一原因。
  2. **企业认证（`freepublish/submit` 真发布）**：这一条已核实——**仅企业主体已认证账号**能自动提交发布，个人/未认证账号止步于建草稿。

## 凭证准备

1. 微信开发者平台 `https://developers.weixin.qq.com/platform` → 开发接口管理 → 拿到 `AppID` 和 `AppSecret`（`AppSecret` 点"重置"获取，妥善保管）。
2. 报 "ip xxx not in whitelist" → 在**实际运行脚本的机器**上 `curl ifconfig.me` 查公网 IP → 加进 IP 白名单（本地电脑查的 IP ≠ 云服务器公网 IP），等 1-5 分钟生效。

## 使用

```bash
# 1. 第一次先查开关状态
python3 assets/automation/wechat_official_publish.py \
  --appid "AppID" --secret "AppSecret" --check-draft-switch

# 2. 只建草稿（任何认证状态的账号开关开了都能用）
python3 assets/automation/wechat_official_publish.py \
  --appid "AppID" --secret "AppSecret" \
  --html "排版好的.html" --cover "封面图.jpg" \
  --title "标题" --author "作者" --digest "一句话摘要"

# 3. 建草稿 + 自动发布（仅企业主体已认证账号）
python3 assets/automation/wechat_official_publish.py \
  --appid "AppID" --secret "AppSecret" \
  --html "排版好的.html" --cover "封面图.jpg" \
  --title "标题" --author "作者" --digest "一句话摘要" --submit
```

开关没开且确认要开（**不可逆**，会永久把后台"图文素材库"升级为"草稿箱"）时加 `--enable-draft-switch`。

脚本自动处理：正文本地图片上传替换成微信域名、封面走永久素材接口、`access_token` 用稳定版、发布状态异步轮询。

## 错误排查

| errcode/现象 | 排查 |
|---|---|
| `ip ... not in whitelist` | 白名单 IP 是否是实际运行机器的公网 IP |
| `45004` | 先查 `--digest`≤128字/`--author`≤16字/`--title`≤32字，不先怀疑正文过长 |
| 建草稿报"缺少封面" | `--cover` 传本地图片路径，不能复用 URL |
| 建草稿 `48001 api unauthorized` | 查开关状态（`--check-draft-switch`）+ access_token 有效性 + IP 白名单 + 参数长度；不预设是开关或认证问题 |
| `--submit` 报 `48001` | **已核实**：账号不是企业主体已认证；草稿已建好，需去后台手动点发布 |
| `43002 require POST method` | 请求方式写成 GET 了，用 POST |
| 发布状态一直"发布中" | 正常异步等待，脚本自动轮询；超时用 `--check-publish-id` 单独查 |

**优先信实际返回的 errcode 和当时最新的官方文档，不要死磕本文件历史结论**——微信接口权限会随平台策略调整。

## 脚本其他命令

```bash
# 查发布状态
python3 assets/automation/wechat_official_publish.py \
  --appid "AppID" --secret "AppSecret" --check-publish-id "PUBLISH_ID"
```

## 发布状态码

| status | 含义 |
|---|---|
| 0 | 成功，`article_url` 是正式链接 |
| 1 | 发布中，继续等 |
| 2 | 原创审核失败 |
| 3 | 常规失败 |
| 4 | 平台审核不通过 |
| 5/6 | 发布后被删/封禁 |
