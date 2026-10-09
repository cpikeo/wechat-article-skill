#!/usr/bin/env python3
"""微信公众号官方 API：草稿 → 可选发布 → 永久链接；永久素材对账/复用/清理。只用标准库。

排版流水线完成后再调用。`--submit` 仅企业认证账号；个人账号止步于草稿。
`--check-draft-switch` 只查询灰度开关（开启不可逆，必须显式 `--enable-draft-switch`）。
素材管理：封面永久素材按内容 sha256 复用（`--no-reuse-cover` 可关），
`--material-count` / `--list-materials` / `--delete-material` 做对账与清理。
凭证与默认字段来自 config.json（模板 config.example.json，不入库）；命令行逐项覆盖。
48001 不要预设单因：开关、token、权限都要查。边界与排查见 `references/publish.md`。
"""

import argparse
import hashlib
import json
import mimetypes
import os
import re
import sys
import time
import uuid
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import api_title  # noqa: E402  标题断行标记的转换规则单一来源在 render.py

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
    """官方文档里 get_materialcount 标注为 GET 请求，按文档实现。"""
    with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if isinstance(body, dict) and body.get("errcode", 0) != 0:
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


# ---------- 3.5 素材管理（永久素材：复用 / 对账 / 清理） ----------
# 草稿封面必须是永久 MediaID（draft/add 文档要求）。旧实现每次建草稿都 add_material
# 传一张新永久素材：发十次就堆十张同款封面。这里按文件内容 sha256 复用，
# 并提供 get_materialcount / batchget_material / del_material 做对账与清理。
# 临时素材（media/upload，3 天过期）不能用于草稿封面，本流水线不接入。

MATERIAL_CACHE_DEFAULT = ".wechat_material_cache.json"


def _file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def get_material(access_token, media_id):
    """按 media_id 取永久素材详情；素材被删时返回 errcode=40007。"""
    url = f"{API_BASE}/material/get_material?access_token={access_token}"
    return _post_json(url, {"media_id": media_id})


def get_material_count(access_token):
    """永久素材总数（image+news 上限 100000，其它 1000）。官方标注 GET。"""
    url = f"{API_BASE}/material/get_materialcount?access_token={access_token}"
    return _get_json(url)


def batchget_material(access_token, material_type="image", offset=0, count=20):
    """分页取永久素材列表；count 官方限定 1–20。"""
    url = f"{API_BASE}/material/batchget_material?access_token={access_token}"
    return _post_json(url, {"type": material_type, "offset": offset,
                            "count": max(1, min(20, count))})


def list_materials(access_token, material_type="image"):
    """翻完全部页，返回 (total_count, item 列表)。"""
    items, offset = [], 0
    total = None
    while True:
        body = batchget_material(access_token, material_type, offset, 20)
        total = body.get("total_count", total)
        batch = body.get("item", [])
        items.extend(batch)
        offset += len(batch)
        if not batch or offset >= (total or 0):
            return total, items


def delete_material(access_token, media_id):
    """删除永久素材（不可恢复；后台官网素材管理里的也能删）。"""
    url = f"{API_BASE}/material/del_material?access_token={access_token}"
    return _post_json(url, {"media_id": media_id})


def upload_thumb_material_cached(access_token, cover_path, cache_path=MATERIAL_CACHE_DEFAULT):
    """同一张封面复用同一个永久素材，不重复占用账号素材额度。

    本地缓存 sha256 -> media_id；复用前用 get_material 验活——素材可能在
    后台被手动删掉（40007），缓存命中但已死就重传并更新缓存。
    """
    digest = _file_sha256(cover_path)
    cache = {}
    if cache_path and os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                cache = json.load(f)
        except (ValueError, OSError):
            cache = {}
    media_id = cache.get(digest)
    if media_id:
        try:
            get_material(access_token, media_id)
            print(f"  复用已有封面永久素材 {media_id}")
            return media_id
        except WeChatAPIError as e:
            print(f"  缓存的素材 {media_id} 已不可用（errcode={e.errcode}），重新上传")
    media_id = upload_thumb_material(access_token, cover_path)
    if cache_path:
        cache[digest] = media_id
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    return media_id


# ---------- 4. 草稿 ----------

def create_draft(access_token, title, content_html, thumb_media_id, author=None, digest=None,
                 source_url=None, need_open_comment=1, only_fans_can_comment=0):
    """字段上限以官方文档（2026-07-14 版）为准：title≤32 / author≤16 / digest≤120。

    正文 HTML 由 render.py 产出时已不再印标题与作者名——它们只走这里原生字段，
    否则草稿里标题、作者各出现两次。

    need_open_comment 默认 1：与公众平台编辑器新建文章默认「留言自动精选公开」对齐；
    API 自身默认是 0（不开启留言），不显式传会把草稿底部变成「不开启留言」。
    """
    article = {
        "article_type": "news",
        "title": api_title(title)[:32],
        "content": content_html,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 1 if need_open_comment else 0,
        "only_fans_can_comment": 1 if only_fans_can_comment else 0,
    }
    if author:
        article["author"] = author[:16]
    if digest:
        article["digest"] = digest[:120]
    if source_url:
        article["content_source_url"] = source_url
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

def publish_html_article(appid, secret, html_path, cover_path, title, author=None, digest=None,
                         source_url=None, open_comment=True, fans_only=False,
                         material_cache=MATERIAL_CACHE_DEFAULT,
                         do_submit=True, poll_timeout=600, auto_enable_switch=False):
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
            print("  ⚠️ 开关处于关闭状态：账号还没被灰度覆盖新版草稿箱（与 48001 的因果关系未证实，作为候选原因）。"
                  "想开启加 --enable-draft-switch（不可逆，自行确认）。继续尝试建草稿……")

    print("[3/6] 上传封面为永久素材（同图复用，不重复占额度）…")
    if material_cache:
        thumb_media_id = upload_thumb_material_cached(token, cover_path, material_cache)
    else:
        thumb_media_id = upload_thumb_material(token, cover_path)
    print(f"  thumb_media_id = {thumb_media_id}")

    with open(html_path, encoding="utf-8") as f:
        html = f.read()

    print("[4/6] 检查并上传正文里的本地图片（如有）…")
    base_dir = os.path.dirname(os.path.abspath(html_path))
    html = rewrite_local_images(html, token, base_dir=base_dir)

    print("[5/6] 新增草稿 …")
    try:
        media_id = create_draft(token, title, html, thumb_media_id, author=author, digest=digest,
                                source_url=source_url, need_open_comment=1 if open_comment else 0,
                                only_fans_can_comment=1 if fans_only else 0)
    except WeChatAPIError as e:
        if e.errcode == 48001:
            print("\n❌ 建草稿被拒绝（48001）：逐个排查——① 草稿箱开关未开（可试 --enable-draft-switch，不可逆）；"
                  "② token/appid/secret 无效；③ 账号缺草稿箱接口权限（后台「设置与开发 → 接口权限」）。"
                  "都排除仍报错，则该账号草稿箱路径走不通，回手动粘贴。", file=sys.stderr)
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
            print("\n❌ 提交发布被拒绝（48001）：草稿已建好，此步单独失败多因账号非企业认证"
                  "（freepublish 自 2025-07 起仅企业认证开放）。后台手动发布，或升级认证后再 --submit。",
                  file=sys.stderr)
        raise
    print(f"  publish_id = {publish_id}，开始轮询发布状态（这是异步任务，不会立刻返回文章链接）…")

    result = poll_publish_status(token, publish_id, timeout=poll_timeout)
    print(f"\n发布结果：{result['status_text']}")
    if result["article_urls"]:
        for u in result["article_urls"]:
            print(f"  文章链接: {u}")
    return {"media_id": media_id, "publish_id": publish_id, **result}


CONFIG_NAME = "config.json"
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_config(explicit=None):
    """读发布配置：显式路径必须存在；默认依次找 ./config.json、技能根 config.json。
    找不到返回空 dict——没配置时一切回落到命令行参数。"""
    candidates = [explicit] if explicit else [
        os.path.join(os.getcwd(), CONFIG_NAME),
        os.path.join(ROOT_DIR, CONFIG_NAME),
    ]
    for path in candidates:
        if os.path.isfile(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    if explicit:
        raise FileNotFoundError(f"配置文件不存在: {explicit}")
    return {}


def resolve_settings(args, side, cfg):
    """字段优先级：命令行 > --meta > config.json；开关类：命令行旗标 > config.json > 官方默认。
    空字符串视同未配置。凭证/开关的解析也只此一处，main 的早退分支复用。"""
    return {
        "appid": args.appid or cfg.get("appid") or None,
        "secret": args.secret or cfg.get("secret") or None,
        "title": args.title or side.get("api_title") or side.get("title"),
        "cover": args.cover or side.get("cover") or None,
        "author": args.author if args.author is not None else (side.get("author") or cfg.get("author") or None),
        "digest": args.digest if args.digest is not None else (side.get("digest") or None),
        "source": args.source_url or side.get("source_url") or cfg.get("source_url") or None,
        "open_comment": (not args.no_open_comment) and bool(cfg.get("need_open_comment", True)),
        "fans_only": args.fans_only_comment or bool(cfg.get("only_fans_can_comment", False)),
        "submit": args.submit or bool(cfg.get("submit", False)),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None,
                    help="发布配置文件路径；默认依次找 ./config.json、技能根 config.json（模板：config.example.json）")
    ap.add_argument("--appid", help="公众号 AppID（默认取自 config.json）")
    ap.add_argument("--secret", help="公众号 AppSecret（默认取自 config.json；不要写进仓库）")
    ap.add_argument("--html", help="正文 HTML 文件路径（排版引擎生成的 HTML 或任意合规 HTML）")
    ap.add_argument("--cover", help="封面图片本地路径")
    ap.add_argument("--title", help="文章标题：| 断行标记自动转｜，超过32字会被截断")
    ap.add_argument("--author", default=None, help="作者（原生作者栏），超过16字会被截断；默认取 --meta，再取 config.json")
    ap.add_argument("--digest", default=None, help="摘要（转发卡片/会话摘要），超过120字会被截断（官方上限120）")
    ap.add_argument("--meta", default=None,
                    help="render.py 产出的 *.meta.json：title/author/digest/cover/原文链接；优先级 命令行 > meta > config.json")
    ap.add_argument("--source-url", default=None, help="原文链接（草稿底部「阅读原文」跳转的 URL）")
    ap.add_argument("--no-open-comment", action="store_true",
                    help="关闭留言。默认开启，与编辑器新建文章「留言自动精选公开」对齐")
    ap.add_argument("--fans-only-comment", action="store_true", help="仅粉丝可评论（默认所有人）")
    ap.add_argument("--submit", action="store_true",
                    help="建草稿后继续提交发布（需要企业认证账号）；默认只建草稿，config.json 可把 submit 设为 true")
    ap.add_argument("--poll-timeout", type=int, default=600, help="发布状态轮询超时秒数，默认 600")
    ap.add_argument("--check-publish-id", default=None, help="只查询某个 publish_id 的发布状态，不做其它任何操作")
    ap.add_argument("--check-draft-switch", action="store_true", help="只查询「草稿箱和发布功能」开关状态，不做其它任何操作")
    ap.add_argument(
        "--enable-draft-switch",
        action="store_true",
        help="如果开关未开启，自动开启它。注意：此操作不可逆（会把公众号后台图文素材库永久升级成草稿箱），请自行确认后再加这个参数",
    )
    ap.add_argument("--material-count", action="store_true", help="只查询永久素材总数（image/video/voice/news）")
    ap.add_argument("--list-materials", action="store_true", help="只列出永久素材（对账/清理用，翻页取全）")
    ap.add_argument("--material-type", default="image", choices=("image", "video", "voice", "news"),
                    help="--list-materials 的素材类型，默认 image")
    ap.add_argument("--delete-material", default=None, metavar="MEDIA_ID",
                    help="只删除指定永久素材（不可恢复；先用 --list-materials 核对 media_id）")
    ap.add_argument("--no-reuse-cover", action="store_true", help="不复用缓存的永久素材，封面强制重传")
    ap.add_argument("--material-cache", default=MATERIAL_CACHE_DEFAULT,
                    help=f"封面复用映射文件（sha256→media_id），默认 {MATERIAL_CACHE_DEFAULT}")
    args = ap.parse_args()

    try:
        cfg = load_config(args.config)
    except FileNotFoundError as e:
        ap.error(str(e))
    s = resolve_settings(args, {}, cfg)  # 凭证与开关；文章字段等拿到 --meta 后重算
    appid, secret = s["appid"], s["secret"]
    if not (appid and secret):
        ap.error("缺少 AppID/AppSecret：写进 config.json（模板 config.example.json），或用 --appid/--secret 传入")

    if args.check_publish_id:
        token = get_stable_access_token(appid, secret)
        result = poll_publish_status(token, args.check_publish_id, timeout=0)  # timeout=0：只查一次不轮询
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    if args.check_draft_switch:
        token = get_stable_access_token(appid, secret)
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

    if args.material_count or args.list_materials or args.delete_material:
        token = get_stable_access_token(appid, secret)
        if args.delete_material:
            print(json.dumps(delete_material(token, args.delete_material), ensure_ascii=False))
            return
        if args.material_count:
            print(json.dumps(get_material_count(token), ensure_ascii=False, indent=2))
        if args.list_materials:
            total, items = list_materials(token, args.material_type)
            print(f"total_count = {total}（type={args.material_type}）")
            for it in items:
                name = it.get("name") or "、".join(
                    n.get("title", "") for n in it.get("content", {}).get("news_item", []))
                print(f"  {it.get('media_id')}\t{name}\t{it.get('url', '')}")
        return

    side = {}
    if args.meta:
        with open(args.meta, encoding="utf-8") as f:
            side = json.load(f)
    s = resolve_settings(args, side, cfg)
    title, cover = s["title"], s["cover"]

    missing = [n for n, v in [("--html", args.html), ("--cover", cover), ("--title", title)] if not v]
    if missing:
        ap.error(f"缺少必填参数：{', '.join(missing)}（--cover/--title 可由 --meta 提供）")

    try:
        publish_html_article(
            appid,
            secret,
            args.html,
            cover,
            title,
            author=s["author"],
            digest=s["digest"],
            source_url=s["source"],
            open_comment=s["open_comment"],
            fans_only=s["fans_only"],
            material_cache=None if args.no_reuse_cover else args.material_cache,
            do_submit=s["submit"],
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
