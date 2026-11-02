# 官方 API 交付（按需）

设计与事实验收见 SKILL.md；本文件仅说明 `scripts/publish.py`。只用 Python 标准库。没有凭证时仅做预检，不能宣称草稿或发布成功。

## 安全边界

默认建草稿。正式发布是**单次授权**：只有本次运行显式加 `--submit --confirm-title "标题"`（标题逐字一致）才会发布，config 写 `submit:true` 会被拒绝——一次设置不能影响以后的普通运行。发布不等于群发。草稿箱开关的开启不可逆，仅显式 `--enable-draft-switch`；删除永久素材不可恢复，仅显式 `--delete-material`。
账号权限依后台与接口返回，不把历史个人／企业结论当当前实测。

## 配置与命令

复制 `config.example.json` 为 config.json（已忽略），填写 AppID／AppSecret；不写进文章、不提交凭证。推荐环境变量 `WECHAT_APPID` / `WECHAT_APPSECRET`，凭证优先级 CLI > 环境变量 > config；CLI 会暴露于进程列表或历史，避免使用。查找：`--config` > 当前目录 > Skill 根目录。文章字段：命令行 > meta > config兜底。预检无需凭证。

```bash
python3 scripts/publish.py --html 文章.html --meta 文章.meta.json --preflight
python3 scripts/publish.py --html 文章.html --meta 文章.meta.json
# 仅明确授权后（单次生效；confirm-title 须逐字等于上行标题）
python3 scripts/publish.py --html 文章.html --meta 文章.meta.json --submit --confirm-title "文章标题"
python3 scripts/publish.py --check-publish-id 已返回的ID
```

标题32字、作者16字、摘要120字；超限拒绝上行，不静默改标题。摘要未显式给定时 render 从导语／副题／首段生成，句末收口，须人工确认。author、title是原生字段，date仅预览模拟。source进入content_source_url，与正文事实来源不同。
留言默认为开、仅粉丝默认关，是本工具默认而非已验证的所有账号编辑器行为；`--no-open-comment` / `--fans-only-comment` 覆盖。原创声明须后台处理。

正文／封面必须位于输出 HTML 目录内；路径须为相对路径，不接受绝对路径、`..`、协议或符号链接越界。跨目录渲染时素材会复制，遇不同内容的同名文件拒绝覆盖。预检检查本地资源、字段、待补位，以及同名 meta 中的渲染器版本、主题配置指纹、源稿、源/交付图片与封面和正文 SHA-256、render 错误；主题配置或运行版本变化后须重渲染。记录使用绝对源稿路径，迁移需重渲染，不要公开敏感路径。哈希不是签名；旧记录缺完整性字段时提示重渲染。没有记录的外部合规HTML只可静态核验与建草稿，不能直接正式提交。哈希仅防陈旧稿，不证明事实与艺术验收。
真实发布入口自动复用同一预检，然后获取token、传封面、传正文图、建草稿、回读 title/content/thumb_media_id、可选提交并查询结果。严格回读不一致或回读失败时停止提交并显示已创建的 media_id，不自动重建。平台可能规范化 HTML，严格比较失败不一定是内容丢失，须后台核对；未比较的作者、摘要等字段及手机端仍需人工验收。CLI 本地 JSONL 记录操作阶段与 ID，不记录正文和凭证；妥善保管，避免泄漏运营信息。失败或未完成不报告成功；查状态不重复建草稿。

## 素材

封面用永久MediaID，按内容sha256缓存；复用前验活。get_material 对图片返回二进制，不是JSON；仅40007视为失效重传，凭证／权限错误直接失败。本地缓存不要跨公众号共享，换账号用 `--material-cache` 指定另一文件。同一路径正文图一次任务只上传一次。常规建稿不再预查草稿箱开关（不决定是否建稿）；开关查询按需显式调用，明确开启授权时才查并启用。

```bash
python3 scripts/publish.py --material-count
python3 scripts/publish.py --list-materials --material-type image
python3 scripts/publish.py --delete-material 已核对的MediaID
python3 scripts/publish.py --html 文章.html --meta 文章.meta.json --no-reuse-cover
```

## 目标账号验收（没有账号就列为未验证）

本地通过后，须在授权公众号完成并逐项记录：保存草稿 → 退出重新打开草稿 → 逐段核对正文样式与图片（粘贴清洗后是否变形、图片是否被替换为微信 URL）→ 手机预览长表／代码／图片裁切 → 核对封面两入口裁切与标题／作者／摘要／原文链接原生字段。任一项不符即回到 Markdown 改稿重渲，不修生成的 HTML。当前回归只 mock 接口契约；这些步骤不经真实账号走完，不得写「发布已验证」。

## 文档核对与限制

2026-10-10核对官方文档（不是账号实测）：
- 新增草稿：https://developers.weixin.qq.com/doc/subscription/api/draftbox/draftmanage/api_draft_add.html
- 获取永久素材：https://developers.weixin.qq.com/doc/subscription/api/material/permanent/api_getmaterial.html

官方content说明同时出现「2kb」与「少于2万字符、小于1M」，存在歧义；不编造唯一上限，超大稿须以实际接口及草稿回读核对。本地预检不是接口放行保证。
IP白名单错核对执行机器公网IP；48001依次核对权限、开关和凭证，不把一个错误码写成确定原因。样式、评论、原创、真机裁切与公开文章URL须在授权账号上验证；当前回归仅mock接口契约。
