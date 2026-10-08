#!/usr/bin/env python3
"""微信公众号官方 API：草稿 → 可选发布 → 永久链接。只用标准库。

排版流水线完成后再调用。`--submit` 仅企业认证账号；个人账号止步于草稿。
`--check-draft-switch` 只查询灰度开关（开启不可逆，必须显式 `--enable-draft-switch`）。
48001 不要预设单因：开关、token、权限都要查。边界与排查见 `references/publish.md`。
"""

import argparse
import json
import mimetypes
import os
import re
import sys
import time
import uuid
import urllib.request
import urllib.error

API_BASE = "https://api.weixin.qq.com/cgi-bin"


class WeChatAPIError(RuntimeError):
    """封装微信接口返回的 errcode/errmsg，避免调用方去猜字段名。"""

    def __init__(self, errcode, errmsg, raw=None):
        self.errcode = errcode
        self.errmsg = errmsg
        self.raw = raw
        super().__init__(f"微信接口报错 errcode={errcode} errmsg={errmsg}")


def _post_json(url, payload):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if isinstance(body, dict) and body.get("errcode", 0) != 0:
        raise WeChatAPIError(body.get("errcode"), body.get("errmsg"), body)
    return body


def _get_json(url):
    with urllib.request.urlopen(url, timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if isinstance(body, dict) and body.get("errcode", 0) not in (0, None):
        raise WeChatAPIError(body.get("errcode"), body.get("errmsg"), body)
    return body


def _post_multipart_file(url, filepath, field_name="media", extra_fields=None):
    """手写 multipart/form-data，不依赖 requests 库。"""
    boundary = uuid.uuid4().hex
    filename = os.path.basename(filepath)
    mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"

    parts = []
    for key, val in (extra_fields or {}).items():
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{key}\"\r\n\r\n{val}\r\n".encode("utf-8")
        )
    with open(filepath, "rb") as f:
        file_bytes = f.read()
    parts.append(
        (
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field_name}\"; "
            f"filename=\"{filename}\"\r\nContent-Type: {mime_type}\r\n\r\n"
        ).encode("utf-8")
    )
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode("utf-8"))
    body = b"".join(parts)

    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    if isinstance(result, dict) and result.get("errcode", 0) not in (0, None):
        raise WeChatAPIError(result.get("errcode"), result.get("errmsg"), result)
    return result


# ---------- 1. access_token ----------

def get_stable_access_token(appid, secret, force_refresh=False):
    """官方推荐的稳定版凭据获取方式，多进程/多任务并发调用不会互相顶掉对方的 token。"""
    url = f"{API_BASE}/stable_token"
    payload = {
        "grant_type": "client_credential",
        "appid": appid,
        "secret": secret,
        "force_refresh": force_refresh,
    }
    body = _post_json(url, payload)
    return body["access_token"]


# ---------- 2. 草稿箱开关（灰度功能，务必先查） ----------

def check_draft_switch(access_token):
    """查询"草稿箱和发布功能"开关状态，不会修改任何东西。
    is_open == 0：这个账号的草稿箱/发布新接口还没开通；这是否会导致 draft/add
                  报 48001 目前证据不确凿（见文件头部 2026-07 复核说明），仅作参考。
    is_open == 1：开关已开，draft/add 应该能正常调用（发布 freepublish_submit 是否能用
                  仍取决于企业认证状态，这一条已核实）。

    请求方式用 POST：官方文档明确标注 `draft/switch` 是 POST 接口，本函数按文档实现。
    """
    url = f"{API_BASE}/draft/switch?access_token={access_token}"
    body = _post_json(url, {"checkonly": 1})
    return bool(body.get("is_open"))


def enable_draft_switch(access_token):
    """开启"草稿箱和发布功能"开关。**这个操作不可逆**——开启后公众号后台的
    "图文素材库"会永久升级成"草稿箱"，无法再切回旧版。本脚本不会在没有明确
    调用这个函数（等价于用户明确同意）的情况下自动执行这一步。

    同上用 POST，是官方文档标注的请求方式，不是"实测才发现"的结果。
    """
    url = f"{API_BASE}/draft/switch?access_token={access_token}"
    body = _post_json(url, {})
    return bool(body.get("is_open"))


# ---------- 3. 素材上传 ----------

def upload_thumb_material(access_token, cover_path):
    """上传封面为永久素材，返回 thumb_media_id（draft/add 建草稿必须用这个，不能用临时素材）。"""
    url = f"{API_BASE}/material/add_material?access_token={access_token}&type=image"
    result = _post_multipart_file(url, cover_path, field_name="media")
    return result["media_id"]


def upload_content_image(access_token, image_path):
    """上传正文里用到的图片，返回可以直接写进 content HTML 的微信图片 URL。
    正文里但凡出现非微信域名的外链图片，draft/add 会把它过滤掉，所以正文图片必须先过这一步。
    """
    url = f"{API_BASE}/media/uploadimg?access_token={access_token}"
    result = _post_multipart_file(url, image_path, field_name="media")
    return result["url"]


IMG_SRC_RE = re.compile(r'(<img[^>]+src=["\'])([^"\']+)(["\'])', re.IGNORECASE)


def rewrite_local_images(html, access_token, base_dir="."):
    """扫描 HTML 里的 <img src="本地路径">，逐个上传替换成微信图片 URL。
    已经是 http(s) 链接的图片不动（是否会被微信过滤由官方接口决定，这里不重复判断）。
    """
    def _replace(match):
        prefix, src, suffix = match.groups()
        if src.startswith("http://") or src.startswith("https://"):
            return match.group(0)
        local_path = src if os.path.isabs(src) else os.path.join(base_dir, src)
        if not os.path.isfile(local_path):
            print(f"  警告：正文引用的本地图片不存在，原样保留 src：{src}", file=sys.stderr)
            return match.group(0)
        wechat_url = upload_content_image(access_token, local_path)
        print(f"  已上传正文图片 {src} -> {wechat_url}")
        return f"{prefix}{wechat_url}{suffix}"

    return IMG_SRC_RE.sub(_replace, html)


# ---------- 4. 草稿 ----------

def create_draft(access_token, title, content_html, thumb_media_id, author=None, digest=None):
    article = {
        "article_type": "news",
        "title": title[:32],
        "content": content_html,
        "thumb_media_id": thumb_media_id,
    }
    if author:
        article["author"] = author[:16]
    if digest:
        article["digest"] = digest[:128]
    url = f"{API_BASE}/draft/add?access_token={access_token}"
    body = _post_json(url, {"articles": [article]})
    return body["media_id"]


# ---------- 5. 发布（仅企业认证账号可用） ----------

def submit_publish(access_token, media_id):
    """提交发布。errcode=48001 通常意味着当前账号不是企业认证账号，调不了这个接口——
    这不是脚本的问题，是微信官方对该接口的账号类型限制（详见模块顶部文档说明）。"""
    url = f"{API_BASE}/freepublish/submit?access_token={access_token}"
    body = _post_json(url, {"media_id": media_id})
    return body["publish_id"]


PUBLISH_STATUS_TEXT = {
    0: "成功",
    1: "发布中（还没结束，需要继续轮询）",
    2: "原创审核失败",
    3: "常规失败",
    4: "平台审核不通过",
    5: "成功后用户自己删除了所有文章",
    6: "成功后系统封禁了所有文章",
}


def poll_publish_status(access_token, publish_id, interval=10, timeout=600):
    """轮询发布状态直到成功/失败/超时。发布是异步的，submit 成功只代表"任务提交成功"。"""
    url = f"{API_BASE}/freepublish/get?access_token={access_token}"
    waited = 0
    while waited <= timeout:
        body = _post_json(url, {"publish_id": publish_id})
        status = body.get("publish_status")
        status_text = PUBLISH_STATUS_TEXT.get(status, f"未知状态码 {status}")
        if status == 1:
            print(f"  发布中，已等待 {waited}s，{interval}s 后重试…")
            time.sleep(interval)
            waited += interval
            continue
        if status == 0:
            urls = [item["article_url"] for item in body.get("article_detail", {}).get("item", [])]
            return {"status": status, "status_text": status_text, "article_urls": urls, "raw": body}
        # 2/3/4/5/6 都是终态失败，不用继续轮询
        return {"status": status, "status_text": status_text, "article_urls": [], "raw": body}
    return {"status": None, "status_text": f"轮询超时（{timeout}s），发布任务可能仍在进行，请稍后手动用 --check-publish-id 查询", "article_urls": [], "raw": None}


# ---------- 一键流程 ----------

def publish_html_article(appid, secret, html_path, cover_path, title, author=None, digest=None, do_submit=True, poll_timeout=600, auto_enable_switch=False):
    print("[1/6] 获取 access_token …")
    token = get_stable_access_token(appid, secret)

    print("[2/6] 检查「草稿箱和发布功能」开关状态 …")
    is_open = check_draft_switch(token)
    if not is_open:
        if auto_enable_switch:
            print("  开关未开启，已传 --enable-draft-switch，正在开启（注意：此操作不可逆）…")
            enable_draft_switch(token)
            print("  已开启。")
        else:
            print(
                "  ⚠️ 开关处于关闭状态：这个账号还没被灰度覆盖新版草稿箱/发布功能。"
                "接下来的 draft/add 是否会因此报 48001 目前没有确凿证据（详见文件头部 2026-07 复核说明），"
                "先当作一个可能原因，如果报错请同时检查 access_token 和参数是否正确。\n"
                "  想现在开启，重新执行时加 --enable-draft-switch"
                "（提醒：开启后公众号后台「图文素材库」会永久升级成「草稿箱」，不可逆，且不确定能否解决 48001，请自行确认后再开）。\n"
                "  继续尝试建草稿……"
            )

    print("[3/6] 上传封面为永久素材 …")
    thumb_media_id = upload_thumb_material(token, cover_path)
    print(f"  thumb_media_id = {thumb_media_id}")

    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    print("[4/6] 检查并上传正文里的本地图片（如有）…")
    base_dir = os.path.dirname(os.path.abspath(html_path))
    html = rewrite_local_images(html, token, base_dir=base_dir)

    print("[5/6] 新增草稿 …")
    try:
        media_id = create_draft(token, title, html, thumb_media_id, author=author, digest=digest)
    except WeChatAPIError as e:
        if e.errcode == 48001:
            print(
                "\n❌ 建草稿被拒绝（api unauthorized）：这一步失败可能是下面几个原因之一，"
                "不要一律归因于'个人账号不能用'，也不要预设就是某一个——\n"
                "  1) 「草稿箱和发布功能」开关还没开（上一步如果打印了 ⚠️ 未开启，是个候选原因，"
                "     但开关状态和 48001 的因果关系目前没有确凿证据，重新执行时可以加 --enable-draft-switch 试试，"
                "     注意这个操作不可逆）；\n"
                "  2) access_token 无效/过期，或 appid、secret 本身有误；\n"
                "  3) 账号本身没有获得草稿箱相关接口权限（去公众平台后台「设置与开发 → 接口权限」核实）。\n"
                "  都排除了还是报错的话，草稿箱这条路径本身对这个账号可能走不通，只能回到手动复制粘贴。",
                file=sys.stderr,
            )
        raise
    print(f"  草稿 media_id = {media_id}")

    if not do_submit:
        print("\n未传 --submit，已止步于「草稿已建好」，需要发布请到公众平台后台手动操作，或重新带 --submit 执行。")
        return {"media_id": media_id, "publish_id": None, "article_urls": []}

    print("[6/6] 提交发布 …")
    try:
        publish_id = submit_publish(token, media_id)
    except WeChatAPIError as e:
        if e.errcode == 48001:
            print(
                "\n❌ 提交发布被拒绝（api unauthorized）：草稿已经建好了（说明开关和基础权限都没问题），"
                "这一步单独失败大概率是因为账号不是企业主体已认证账号——"
                "freepublish_submit 这一组接口 2025 年 7 月起只对企业认证账号开放。"
                "可以去公众平台后台手动发布，或者升级账号认证后再用本脚本 --submit。",
                file=sys.stderr,
            )
        raise
    print(f"  publish_id = {publish_id}，开始轮询发布状态（这是异步任务，不会立刻返回文章链接）…")

    result = poll_publish_status(token, publish_id, timeout=poll_timeout)
    print(f"\n发布结果：{result['status_text']}")
    if result["article_urls"]:
        for u in result["article_urls"]:
            print(f"  文章链接: {u}")
    return {"media_id": media_id, "publish_id": publish_id, **result}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--appid", required=True, help="公众号 AppID")
    ap.add_argument("--secret", required=True, help="公众号 AppSecret（不要写进脚本里提交到 Git，建议用环境变量传入）")
    ap.add_argument("--html", help="正文 HTML 文件路径（排版引擎生成的 HTML 或任意合规 HTML）")
    ap.add_argument("--cover", help="封面图片本地路径")
    ap.add_argument("--title", help="文章标题，超过32字会被截断")
    ap.add_argument("--author", default=None, help="作者，超过16字会被截断")
    ap.add_argument("--digest", default=None, help="摘要，超过128字会被截断")
    ap.add_argument("--submit", action="store_true", help="建草稿后是否继续提交发布（需要企业认证账号）；不加则只建草稿")
    ap.add_argument("--poll-timeout", type=int, default=600, help="发布状态轮询超时秒数，默认 600")
    ap.add_argument("--check-publish-id", default=None, help="只查询某个 publish_id 的发布状态，不做其它任何操作")
    ap.add_argument("--check-draft-switch", action="store_true", help="只查询「草稿箱和发布功能」开关状态，不做其它任何操作")
    ap.add_argument(
        "--enable-draft-switch",
        action="store_true",
        help="如果开关未开启，自动开启它。注意：此操作不可逆（会把公众号后台图文素材库永久升级成草稿箱），请自行确认后再加这个参数",
    )
    args = ap.parse_args()

    if args.check_publish_id:
        token = get_stable_access_token(args.appid, args.secret)
        result = poll_publish_status(token, args.check_publish_id, timeout=0)  # timeout=0：只查一次不轮询
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.check_draft_switch:
        token = get_stable_access_token(args.appid, args.secret)
        is_open = check_draft_switch(token)
        print(json.dumps({"is_open": is_open}, ensure_ascii=False, indent=2))
        if not is_open:
            print(
                "\n开关处于关闭状态：草稿箱/发布新接口大概率还没对这个账号开通，"
                "和企业认证与否无关。想开启，加 --enable-draft-switch 单独跑一次"
                "（提醒：不可逆，会把公众号后台图文素材库永久升级成草稿箱）。",
                file=sys.stderr,
            )
        return

    missing = [n for n, v in [("--html", args.html), ("--cover", args.cover), ("--title", args.title)] if not v]
    if missing:
        ap.error(f"缺少必填参数：{', '.join(missing)}")

    try:
        publish_html_article(
            args.appid,
            args.secret,
            args.html,
            args.cover,
            args.title,
            author=args.author,
            digest=args.digest,
            do_submit=args.submit,
            poll_timeout=args.poll_timeout,
            auto_enable_switch=args.enable_draft_switch,
        )
    except WeChatAPIError as e:
        print(f"\n❌ {e}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"\n❌ 网络请求失败: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
