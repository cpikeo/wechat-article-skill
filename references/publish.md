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
python3 scripts/publish.py --appid "ID" --secret "S" --html "文章.html" --cover "封面.jpg" --title "标题" --author "作者" --digest "摘要"
# 企业认证加 --submit 真发布；查发布状态加 --check-publish-id ID
```

脚本自动处理：正文图片上传替换、封面永久素材、稳定版 token、发布轮询。

## 排查

| 现象 | 先看 |
|---|---|
| ip not in whitelist | 白名单里的是不是这台机器的公网 IP |
| 45004 | digest≤128字 / author≤16字 / title≤32字 |
| 建草稿 48001 | 开关状态 + token 有效性 + 接口权限，不预设单因 |
| --submit 48001 | 非企业认证，只能后台手动发布 |
| 一直"发布中" | 异步正常，轮询或稍后单查 |

信实际返回的 errcode，不死磕历史结论。
