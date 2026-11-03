#!/usr/bin/env python3
"""微信公众号官方 API：草稿 → 可选发布 → 永久链接；永久素材对账/复用/清理。只用标准库。

排版流水线完成后再调用。`--submit` 需具备发布权限；账号能力以接口返回与后台权限为准。
发之前先 `python3 scripts/publish.py --html X.html --meta X.meta.json --preflight`：不调接口，
把将要上行的 Gate 1 结论、原生字段（含上限）、封面与待传图片全摆出来，验收完再真发。
`--check-draft-switch` 只查询灰度开关（开启不可逆，必须显式 `--enable-draft-switch`）。
素材管理：封面永久素材按内容 sha256 复用（`--no-reuse-cover` 可关），
`--material-count` / `--list-materials` / `--delete-material` 做对账与清理。
凭证与默认字段来自 config.json（模板 config.example.json，不入库）；命令行逐项覆盖。
48001 不要预设单因：开关、token、权限都要查。边界与排查见 `references/publish.md`。
"""

import argparse
import hashlib
import html as H
import json
import mimetypes
import os
import re
import sys
import time
import uuid
from datetime import datetime, timezone
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render import api_title, img_size, SKILL_VERSION, THEME_CONFIG_SHA256  # noqa: E402
from check import check, image_sources, safe_http_url  # noqa: E402
from safety import local_path, sha256

API_BASE = "https://api.weixin.qq.com/cgi-bin"


class WeChatAPIError(RuntimeError):
    """封装微信接口返回的 errcode/errmsg，避免调用方去猜字段名。"""

    def __init__(self, errcode, errmsg, raw=None):
        self.errcode = errcode
        self.errmsg = errmsg
        self.raw = raw
        super().__init__(f"微信接口报错 errcode={errcode} errmsg={errmsg}")


def _post_json(url, payload, binary=False):
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
        if binary and not raw.lstrip().startswith((b"{", b"[")):
            return raw
        body = json.loads(raw.decode("utf-8"))
    if isinstance(body, dict) and body.get("errcode", 0) not in (0, None):
        raise WeChatAPIError(body.get("errcode"), body.get("errmsg"), body)
    return body


def _get_json(url):
    """官方文档里 get_materialcount 标注为 GET 请求，按文档实现。"""
    with urllib.request.urlopen(urllib.request.Request(url), timeout=30) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    if isinstance(body, dict) and body.get("errcode", 0) not in (0, None):
        raise WeChatAPIError(body.get("errcode"), body.get("errmsg"), body)
    return body


def _multipart_filename(filepath):
    """Multipart filename is metadata, not the uploaded file itself; make it header-safe ASCII."""
    original = os.path.basename(filepath)
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", original).strip("._")
    return (safe[:120] or "upload")


def _post_multipart_file(url, filepath, field_name="media", extra_fields=None):
    """手写 multipart/form-data，不依赖 requests 库。"""
    boundary = uuid.uuid4().hex
    original_filename = os.path.basename(filepath)
    filename = _multipart_filename(filepath)
    mime_type = mimetypes.guess_type(original_filename)[0] or "application/octet-stream"

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


# ---------- 2. 草稿箱开关（灰度功能，显式按需） ----------

def check_draft_switch(access_token):
    """查询"草稿箱和发布功能"开关状态，不会修改任何东西。
    is_open == 0：这个账号的草稿箱/发布新接口还没开通；这是否会导致 draft/add
                  报 48001 目前证据不确凿（权限仍需实际账号核对），仅作参考。
    is_open == 1：开关已开，draft/add 应该能正常调用（发布 freepublish_submit 是否能用
                  需按实际账号接口权限确认）。

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


IMG_SRC_RE = re.compile(r"(<img\b[^>]*?\bsrc\s*=\s*)(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))", re.IGNORECASE)


def rewrite_local_images(html, access_token, base_dir="."):
    """扫描 HTML 里的 <img src="本地路径">，逐个上传替换成微信图片 URL。
    已经是 http(s) 链接的图片不动（是否会被微信过滤由官方接口决定，这里不重复判断）。
    """
    uploaded = {}
    def _replace(match):
        prefix, double, single, bare = match.groups()
        src = H.unescape(next(v for v in (double, single, bare) if v is not None))
        if src.lower().startswith(("http://", "https://")):
            return match.group(0)
        local_file = local_path(src, base_dir)
        if not os.path.isfile(local_file):
            raise ValueError(f"正文图片不存在：{src}")
        if local_file not in uploaded:
            uploaded[local_file] = upload_content_image(access_token, local_file)
        wechat_url = uploaded[local_file]
        print(f"  已上传正文图片 {src} -> {wechat_url}")
        return f'{prefix}"{H.escape(wechat_url)}"'

    return IMG_SRC_RE.sub(_replace, html)


# ---------- 3.5 素材管理（永久素材：复用 / 对账 / 清理） ----------
# 草稿封面必须是永久 MediaID（draft/add 文档要求）。旧实现每次建草稿都 add_material
# 传一张新永久素材：发十次就堆十张同款封面。这里按文件内容 sha256 复用，
# 并提供 get_materialcount / batchget_material / del_material 做对账与清理。
# 临时素材（media/upload，3 天过期）不能用于草稿封面，本流水线不接入。

MATERIAL_CACHE_DEFAULT = ".wechat_material_cache.json"


def get_material(access_token, media_id):
    """按 media_id 取永久素材详情；素材被删时返回 errcode=40007。"""
    url = f"{API_BASE}/material/get_material?access_token={access_token}"
    return _post_json(url, {"media_id": media_id}, binary=True)


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
    digest = sha256(cover_path)
    cache = {}
    if cache_path and os.path.exists(cache_path):
        try:
            with open(cache_path, encoding="utf-8") as f:
                cache = json.load(f)
                if not isinstance(cache, dict):
                    cache = {}
        except (ValueError, OSError):
            cache = {}
    media_id = cache.get(digest)
    if media_id:
        try:
            get_material(access_token, media_id)
            print(f"  复用已有封面永久素材 {media_id}")
            return media_id
        except WeChatAPIError as e:
            if e.errcode != 40007:
                raise
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
    """字段上限以官方文档（见 references/publish.md）为准：title≤32 / author≤16 / digest≤120。

    正文 HTML 由 render.py 产出时已不再印标题与作者名——它们只走这里原生字段，
    否则草稿里标题、作者各出现两次。

    need_open_comment 本工具默认1，可用配置或CLI关闭；不代表所有账号编辑器默认。
    """
    for label, value, cap in (("title", api_title(title), 32), ("author", author or "", 16), ("digest", digest or "", 120)):
        if len(value) > cap or (label == "title" and not value):
            raise ValueError(f"{label} 为空或超过上限 {cap}：请编辑，不静默截断")
    article = {
        "article_type": "news",
        "title": api_title(title),
        "content": content_html,
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 1 if need_open_comment else 0,
        "only_fans_can_comment": 1 if only_fans_can_comment else 0,
    }
    if author:
        article["author"] = author
    if digest:
        article["digest"] = digest
    if source_url:
        article["content_source_url"] = source_url
    url = f"{API_BASE}/draft/add?access_token={access_token}"
    body = _post_json(url, {"articles": [article]})
    return body["media_id"]


def read_draft(access_token, media_id):
    """Read an existing draft; never creates or retries a draft."""
    return _post_json(f"{API_BASE}/draft/get?access_token={access_token}", {"media_id": media_id})


def verify_draft(data, title, content, thumb_media_id):
    items = data.get("news_item", []) if isinstance(data, dict) else []
    if not items or not isinstance(items[0], dict):
        raise ValueError("草稿回读缺少 news_item")
    item = items[0]
    mismatches = [name for name, expected in (("title", api_title(title)), ("content", content),
                                               ("thumb_media_id", thumb_media_id))
                  if item.get(name) != expected]
    return mismatches


# ---------- 5. 发布（须核对实际账号权限） ----------

def write_readback_evidence(directory, media_id, data, expected):
    """保存脱敏回读对照；只证明 API 字段，后台重开/手机端仍 UNVERIFIED。"""
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", media_id or ""):
        raise ValueError("media_id 不能用作证据目录名")
    item = (data.get("news_item") or [{}])[0] if isinstance(data, dict) else {}
    fields = {}
    for name, want in expected.items():
        got = item.get(name)
        fields[name] = {"match": got == want, "expected_sha256": hashlib.sha256(str(want).encode()).hexdigest(),
                        "observed_sha256": hashlib.sha256(str(got).encode()).hexdigest(),
                        "observed": got if name in ("title", "author", "digest", "thumb_media_id", "content_source_url", "need_open_comment", "only_fans_can_comment") else None}
    root = os.path.join(directory, media_id)
    os.makedirs(root, exist_ok=True)
    payload = {"media_id": media_id, "time": datetime.now(timezone.utc).isoformat(),
               "api_readback": "PASS" if all(f["match"] for f in fields.values()) else "FAIL",
               "fields": fields, "backend_save_reopen": "UNVERIFIED", "wechat_mobile": "UNVERIFIED",
               "note": "仅本地保存的 API 回读对照；不含 token；不等于后台或真机验收。"}
    with open(os.path.join(root, "draft-readback.json"), "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def submit_publish(access_token, media_id):
    """提交发布；48001提示接口未授权，按实际账号核对，不推断认证身份。"""
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
            if waited >= timeout:
                return {"status": 1, "status_text": "仍在发布中；请稍后查询", "article_urls": [], "raw": body}
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


def resolve_cover(cover, html_path):
    """封面相对路径按「文章目录」解析，不按当前工作目录。

    meta.json 里的 cover 是 frontmatter 原值（相对 md），而发布命令常从仓库根执行——
    不解析就会 FileNotFoundError 崩在上传那一步。
    """
    if not cover:
        return cover
    return local_path(cover, os.path.dirname(os.path.abspath(html_path)))


def preflight(html_path, s):
    """不调接口，先把「将要上行的东西」摆出来：Gate 1 + 原生字段 + 封面 + 待传正文图。

    发布可靠性只能验到这一层——接口那边是否放行无法预演，但「发出去的东西对不对」必须能验。
    """
    with open(html_path, encoding="utf-8") as f:
        html = f.read()
    must, should = check(html)
    ok = not must
    # Consume the existing render sidecar: detect stale/failed generation, not factual truth.
    side_path = os.path.splitext(html_path)[0] + ".meta.json"
    if os.path.isfile(side_path):
        with open(side_path, encoding="utf-8") as f:
            side = json.load(f)
        if not isinstance(side, dict):
            raise ValueError("meta 必须是JSON对象")
        if side.get("body_sha256") != hashlib.sha256(html.encode()).hexdigest() or side.get("render_errors") or side.get("pending_assets"):
            ok = False
            print("  必须改 · 正文与渲染验收不一致，或 Gate 1/2 未通过：重渲染")
    else:
        print("  注意 · HTML 无渲染验收记录：只做静态检查，不能正式提交发布")
        if s["submit"]:
            ok = False
    if "待补素材" in html:
        ok = False
        print("  必须改 · 正文仍有待补素材")
    base = os.path.dirname(os.path.abspath(html_path))
    local = image_sources(html)
    safe_local = []
    for u in local:
        try:
            safe_local.append(local_path(u, base))
        except ValueError as e:
            ok = False
            print("  必须改 ·", e)
    miss = [u for u in safe_local if not os.path.isfile(u)]
    if s["cover"]:
        try:
            # Callers pass the already resolved cover; it must stay within HTML root.
            rel = os.path.relpath(s["cover"], base)
            local_path(rel, base)
        except ValueError as e:
            ok = False
            print("  必须改 · 封面路径越界", e)
    if os.path.isfile(side_path) and side.get("integrity_version") == 2:
        try:
            if side.get("skill_version") != SKILL_VERSION:
                raise ValueError(f"渲染版本已变化：{side.get('skill_version')} → {SKILL_VERSION}")
            if side.get("theme_config_sha256") != THEME_CONFIG_SHA256:
                raise ValueError("主题配置已变化；正文、配置和展示样张可能不一致")
            source = side["source"]
            if sha256(source["path"]) != source["sha256"]:
                raise ValueError("源 Markdown 已变化")
            assets = {item["path"]: item["sha256"] for item in side["assets"]}
            cover_rel = os.path.relpath(s["cover"], base).replace(os.sep, "/") if s["cover"] else ""
            required = set(local) | ({cover_rel} if cover_rel else set())
            if set(assets) != required:
                raise ValueError("素材清单与正文/封面不一致")
            source_root = os.path.dirname(os.path.abspath(source["path"]))
            for item in side["assets"]:
                path, digest = item["path"], item["sha256"]
                if (sha256(local_path(path, base)) != digest
                        or sha256(local_path(item["source_path"], source_root)) != item["source_sha256"]
                        or digest != item["source_sha256"]):
                    raise ValueError(f"素材已变化：{path}")
        except (KeyError, TypeError, ValueError, OSError) as e:
            ok = False
            print("  必须改 · 一致性校验失败：", e)
    elif os.path.isfile(side_path):
        print("  注意 · 旧版记录缺少当前渲染器／主题配置一致性记录，建议重渲染")
        if s["submit"]:
            ok = False
            print("  必须改 · 正式提交前须用当前版本重渲染")
    print("预检（不调用接口）")
    for m in must:
        print("  必须改 ·", m)
    for x in should:
        print("  建议改 ·", x)
    print(f"  Gate 1 Platform: {'PASS' if not must else 'FAIL'}（仅静态检查）")
    for label, v, cap in (("标题", s["title"] or "", 32), ("作者", s["author"] or "", 16),
                          ("摘要", s["digest"] or "", 120)):
        if len(v) > cap or (label == "标题" and not v.strip()):
            ok = False
        print(f"  {label}  {v or '（空）'}（{len(v)}/{cap}）"
              + (f"  ⚠ 超过官方上限 {cap}，拒绝上行，请编辑" if len(v) > cap else ""))
    print(f"  原文链接  {s['source'] or '（无）'}")
    if s["source"] and not safe_http_url(s["source"]):
        ok = False
        print("  必须改 · 原文链接不是有效的 HTTP(S) URL")
    cover = s["cover"]
    if not cover:
        ok = False
        print("  封面  ⚠ 未设置（草稿必须有封面）")
    elif not os.path.isfile(cover):
        ok = False
        print(f"  封面  ⚠ 文件不存在：{cover}")
    else:
        wh, kb = img_size(cover), os.path.getsize(cover) // 1024
        if not wh or not all(wh):
            ok = False
            print("  必须改 · 封面不是可识别图片")
        print(f"  封面  {cover}" + (f" · {wh[0]}×{wh[1]}（{wh[0] / wh[1]:.2f}:1）· {kb}KB" if wh else f" · {kb}KB"))
    print(f"  正文图片  {len(local)} 张待上传" + (f" · ⚠ 缺失 {miss}" if miss else ""))
    if miss or any(not img_size(u) for u in safe_local):
        ok = False
    print(f"  留言 {'开' if s['open_comment'] else '关'} · 仅粉丝 {'是' if s['fans_only'] else '否'}"
          f" · 建草稿后{'继续发布' if s['submit'] else '止步'}")
    print("\n预检" + ("通过：仅本地工程检查；事实、裁切与微信清洗仍须人工核对" if ok else "未通过：先修完再发"))
    return 0 if ok else 1


# ---------- 一键流程 ----------

def publish_html_article(appid, secret, html_path, cover_path, title, author=None, digest=None,
                         source_url=None, open_comment=True, fans_only=False,
                         material_cache=MATERIAL_CACHE_DEFAULT,
                         do_submit=False, submit_confirm=None, poll_timeout=600, auto_enable_switch=False, audit=None,
                         evidence_dir=None):
    audit = audit or (lambda event, **fields: None)
    if do_submit and api_title(submit_confirm or "") != api_title(title):
        raise ValueError(f"正式发布需要本次运行的单次确认：--confirm-title 必须与本次标题逐字一致"
                         f"（本次标题：{api_title(title)!r}）。没有持久授权这回事，每次发布都要重新确认")
    settings = {"title": title, "author": author, "digest": digest, "cover": cover_path,
                "source": source_url, "open_comment": open_comment, "fans_only": fans_only, "submit": do_submit}
    if preflight(html_path, settings):
        raise ValueError("发布预检未通过：未调用微信接口")
    audit("preflight_pass", body_sha256=sha256(html_path), submit=do_submit)
    print("[1/6] 获取 access_token …")
    token = get_stable_access_token(appid, secret)

    if auto_enable_switch and not check_draft_switch(token):
        print("显式授权开启草稿箱开关（不可逆）…")
        enable_draft_switch(token)

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
    audit("draft_created", media_id=media_id)
    print(f"  草稿 media_id = {media_id}")

    try:
        readback = read_draft(token, media_id)
        differences = verify_draft(readback, title, html, thumb_media_id)
        if evidence_dir:
            write_readback_evidence(evidence_dir, media_id, readback,
                                    {"title": api_title(title), "content": html, "thumb_media_id": thumb_media_id})
    except Exception as e:
        raise RuntimeError(f"草稿已创建 media_id={media_id}，回读失败；请先在后台核对，勿重复建稿：{type(e).__name__}") from None
    if differences:
        raise RuntimeError(f"草稿已创建 media_id={media_id}，回读字段不一致：{', '.join(differences)}；请检查，勿重复建稿")
    audit("draft_readback_match", media_id=media_id)
    print("  草稿 API 回读字段一致；仍需后台重新打开和手机验收。")
    if not do_submit:
        print("\n草稿已建好，未继续发布。请后台检查；不要为查询状态重新建稿。")
        return {"media_id": media_id, "publish_id": None, "article_urls": []}

    print("[6/6] 提交发布 …")
    try:
        publish_id = submit_publish(token, media_id)
    except WeChatAPIError as e:
        if e.errcode == 48001:
            print("\n❌ 提交发布被拒绝（48001）：草稿已建好，此接口未获授权"
                  "。请核对实际接口权限；草稿已保留，不要重复建稿。",
                  file=sys.stderr)
        raise
    audit("publish_submitted", media_id=media_id, publish_id=publish_id)
    print(f"  publish_id = {publish_id}，开始轮询发布状态（这是异步任务，不会立刻返回文章链接）…")

    result = poll_publish_status(token, publish_id, timeout=poll_timeout)
    print(f"\n发布结果：{result['status_text']}")
    if result["article_urls"]:
        for u in result["article_urls"]:
            print(f"  文章链接: {u}")
    if result["status"] != 0:
        raise RuntimeError(f"发布未成功：{result['status_text']}；publish_id={publish_id}")
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
                cfg = json.load(f)
                if not isinstance(cfg, dict):
                    raise ValueError("config 必须是JSON对象")
                allowed = {"_说明", "appid", "secret", "author", "source_url", "need_open_comment", "only_fans_can_comment", "submit"}
                unknown = set(cfg) - allowed
                if unknown:
                    raise ValueError(f"config 非法字段：{', '.join(sorted(unknown))}")
                for key in ("appid", "secret", "author", "source_url"):
                    if key in cfg and not isinstance(cfg[key], str):
                        raise ValueError(f"{key} 必须是字符串")
                if "_说明" in cfg and not isinstance(cfg["_说明"], (str, dict)):
                    raise ValueError("_说明 必须是字符串或对象")
                for key in ("submit", "need_open_comment", "only_fans_can_comment"):
                    if key in cfg and not isinstance(cfg[key], bool):
                        raise ValueError(f"{key} 必须是true/false，不能是字符串")
                if cfg.get("submit"):
                    raise ValueError(
                        "config 不接受 submit:true——正式发布不允许持久授权，一次设置不能影响以后的普通运行。"
                        "去掉该键；确要发布时在本次运行显式加 --submit --confirm-title \"标题\"（单次授权）")
                return cfg
    if explicit:
        raise FileNotFoundError(f"配置文件不存在: {explicit}")
    return {}


def resolve_settings(args, side, cfg):
    """字段优先级：命令行 > --meta > config.json；开关类：命令行旗标 > config.json > 官方默认。
    空字符串视同未配置。凭证/开关的解析也只此一处，main 的早退分支复用。"""
    return {
        "appid": args.appid or os.getenv("WECHAT_APPID") or cfg.get("appid") or None,
        "secret": args.secret or os.getenv("WECHAT_APPSECRET") or cfg.get("secret") or None,
        "title": api_title(args.title or side.get("api_title") or side.get("title") or ""),
        "cover": args.cover or side.get("cover") or None,
        "author": args.author if args.author is not None else (side.get("author") or cfg.get("author") or None),
        "digest": args.digest if args.digest is not None else (side.get("digest") or None),
        "source": args.source_url or side.get("source_url") or cfg.get("source_url") or None,
        "open_comment": (not args.no_open_comment) and bool(cfg.get("need_open_comment", True)),
        "fans_only": args.fans_only_comment or bool(cfg.get("only_fans_can_comment", False)),
        "submit": bool(args.submit),      # 只认本次命令行：config 不允许持久授权发布
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=None,
                    help="发布配置文件路径；默认依次找 ./config.json、技能根 config.json（模板：config.example.json）")
    ap.add_argument("--appid", help="公众号 AppID（默认取自 config.json）")
    ap.add_argument("--secret", help="公众号 AppSecret（默认取自 config.json；不要写进仓库）")
    ap.add_argument("--html", help="正文 HTML 文件路径（排版引擎生成的 HTML 或任意合规 HTML）")
    ap.add_argument("--cover", help="封面图片本地路径")
    ap.add_argument("--title", help="文章标题：| 断行标记自动转｜，超过32字拒绝上行")
    ap.add_argument("--author", default=None, help="作者（原生作者栏），超过16字拒绝上行；默认取 --meta，再取 config.json")
    ap.add_argument("--digest", default=None, help="摘要（转发卡片/会话摘要），超过120字拒绝上行（官方上限120）")
    ap.add_argument("--meta", default=None,
                    help="render.py 产出的 *.meta.json：title/author/digest/cover/原文链接；优先级 命令行 > meta > config.json")
    ap.add_argument("--source-url", default=None, help="原文链接（草稿底部「阅读原文」跳转的 URL）")
    ap.add_argument("--no-open-comment", action="store_true",
                    help="关闭留言。本工具默认开启，不代表所有账号编辑器默认")
    ap.add_argument("--fans-only-comment", action="store_true", help="仅粉丝可评论（默认所有人）")
    ap.add_argument("--submit", action="store_true",
                    help="建草稿后继续提交发布（需账号具备发布权限）；单次授权，只对本次运行生效，"
                         "还须 --confirm-title 逐字确认标题；默认只建草稿，config 不接受 submit:true")
    ap.add_argument("--confirm-title", default=None,
                    help="正式发布的单次确认：逐字等于本次上行标题（|/｜ 等价）；与 --submit 同时给出才发布")
    ap.add_argument("--poll-timeout", type=int, default=600, help="发布状态轮询超时秒数，默认 600")
    ap.add_argument("--check-publish-id", default=None, help="只查询某个 publish_id 的发布状态，不做其它任何操作")
    ap.add_argument("--preflight", action="store_true",
                    help="不调接口：跑 Gate 1 并打印将上行的标题/作者/摘要（含上限）、封面与待传正文图，验收通过再真发")
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
    ap.add_argument("--confirm-delete-media-id", default=None, metavar="MEDIA_ID",
                    help="删除素材的单次授权：必须与 --delete-material 逐字一致（没有持久授权）")
    ap.add_argument("--audit-log", default=".wechat_publish_audit.jsonl", help="本地操作审计 JSONL，不含凭证和正文；默认当前目录")
    ap.add_argument("--evidence-dir", default=None, help="可选：保存脱敏草稿回读对照 JSON；后台重开与手机端仍须单独验收")
    ap.add_argument("--no-reuse-cover", action="store_true", help="不复用缓存的永久素材，封面强制重传")
    ap.add_argument("--material-cache", default=MATERIAL_CACHE_DEFAULT,
                    help=f"封面复用映射文件（sha256→media_id），默认 {MATERIAL_CACHE_DEFAULT}")
    args = ap.parse_args()

    try:
        cfg = load_config(args.config)
    except (OSError, ValueError) as e:
        ap.error(str(e))
    side = {}
    if args.meta:
        if args.html and os.path.realpath(args.meta) != os.path.realpath(os.path.splitext(args.html)[0] + ".meta.json"):
            ap.error("--meta 必须是正文对应的同名 sidecar，避免字段与验收记录错配")
        with open(args.meta, encoding="utf-8") as f:
            side = json.load(f)
        if not isinstance(side, dict):
            ap.error("meta 必须是JSON对象")
    s = resolve_settings(args, side, cfg)
    if args.preflight:                       # 预检不联网：先于凭证检查，没配凭证也能验
        if not args.html:
            ap.error("--preflight 需要 --html")
        s["cover"] = resolve_cover(s["cover"], args.html)
        sys.exit(preflight(args.html, s))
    appid, secret = s["appid"], s["secret"]
    if not (appid and secret):
        ap.error("缺少 AppID/AppSecret：写进 config.json（模板 config.example.json），或用 --appid/--secret 传入")

    if args.check_publish_id:
        token = get_stable_access_token(appid, secret)
        result = poll_publish_status(token, args.check_publish_id, timeout=0)  # timeout=0：只查一次不轮询
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["status"] not in (0, 1):
            sys.exit(1)
        return

    if args.check_draft_switch:
        token = get_stable_access_token(appid, secret)
        is_open = check_draft_switch(token)
        print(json.dumps({"is_open": is_open}, ensure_ascii=False, indent=2))
        if not is_open:
            print(
                "\n开关处于关闭状态：草稿箱/发布新接口大概率还没对这个账号开通，"
                "权限须按实际账号核对。想开启，加 --enable-draft-switch 单独跑一次"
                "（提醒：不可逆，会把公众号后台图文素材库永久升级成草稿箱）。",
                file=sys.stderr,
            )
        return

    # 删除永久素材不可逆：授权与格式检查必须在取 token **之前**完成——
    # 未被确认的破坏性操作不应该先花掉一次凭证请求，更不应该有任何网络副作用。
    if args.delete_material:
        if (args.confirm_delete_media_id or "") != args.delete_material:
            ap.error("删除永久素材不可恢复：必须同时给出 --confirm-delete-media-id "
                     f"\"{args.delete_material}\"（与 --delete-material 逐字一致，本次有效）")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", args.delete_material):
            ap.error("media_id 格式非法，拒绝调用删除接口")

    if args.material_count or args.list_materials or args.delete_material:
        token = get_stable_access_token(appid, secret)
        if args.delete_material:
            result = delete_material(token, args.delete_material)
            print(json.dumps(result, ensure_ascii=False))
            try:
                with open(args.audit_log, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"time": datetime.now(timezone.utc).isoformat(),
                                        "event": "material_deleted",
                                        "media_id_sha256": hashlib.sha256(
                                            args.delete_material.encode()).hexdigest()},
                                       ensure_ascii=False) + "\n")
            except OSError:
                pass
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

    title, cover = s["title"], resolve_cover(s["cover"], args.html or ".")
    s["cover"] = cover

    missing = [n for n, v in [("--html", args.html), ("--cover", cover), ("--title", title)] if not v]
    if missing:
        ap.error(f"缺少必填参数：{', '.join(missing)}（--cover/--title 可由 --meta 提供）")

    AUDIT_FIELDS = {"submit", "body_sha256", "media_id", "publish_id", "error_type",
                    "media_id_sha256", "stage"}

    def audit(event, **fields):
        dropped = set(fields) - AUDIT_FIELDS
        if dropped:
            raise ValueError(f"审计日志不接受字段：{'、'.join(sorted(dropped))}（防止凭证/正文入日志）")
        for value in fields.values():
            if not isinstance(value, (str, int, float, bool, type(None))):
                raise ValueError("审计日志只接受标量字段")
        record = {"time": datetime.now(timezone.utc).isoformat(), "event": event, **fields}
        fd = os.open(args.audit_log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    try:
        audit("attempt", submit=s["submit"])
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
            submit_confirm=args.confirm_title,
            poll_timeout=args.poll_timeout,
            auto_enable_switch=args.enable_draft_switch,
            audit=audit,
            evidence_dir=args.evidence_dir,
        )
        audit("completed")
    except (WeChatAPIError, ValueError, OSError, RuntimeError) as e:
        try:
            audit("failed", error_type=type(e).__name__)
        except OSError:
            pass
        message = str(e).replace(secret, "[REDACTED]") if secret else str(e)
        message = re.sub(r"(?i)(access_token=)[^&\s\"']+", r"\1[REDACTED]", message)
        print(f"\n❌ {message}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, WeChatAPIError) as e:
        sys.exit(f"发布错误：{e}")
