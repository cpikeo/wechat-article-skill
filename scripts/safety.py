"""Local path boundaries, hashes, atomic output and WCAG contrast (stdlib only)."""
import hashlib
import os
import re
import tempfile


def validate_relpath(src):
    """Validate relative asset syntax without touching the filesystem."""
    if not isinstance(src, str) or not src or src != src.strip() or "\\" in src:
        raise ValueError("非法本地资源路径")
    if any(ord(c) < 0x20 or ord(c) == 0x7F for c in src):
        raise ValueError("本地资源路径不得含控制字符")
    if any(c in src for c in "?#%"):
        raise ValueError("本地资源路径不得含 URL 查询、片段或百分号编码")
    if os.path.isabs(src) or re.match(r"^[a-zA-Z]:|^[a-zA-Z][a-zA-Z0-9+.-]*:|^//", src):
        raise ValueError(f"资源路径必须相对文章目录：{src}")
    if any(part in ("", "..", ".") for part in src.split("/")):
        raise ValueError(f"资源路径含越界、空段或当前目录段：{src}")


def is_safe_relpath(src):
    try:
        validate_relpath(src)
        return True
    except ValueError:
        return False


def local_path(src, root):
    validate_relpath(src)
    base = os.path.realpath(root)
    path = os.path.realpath(os.path.join(base, src))
    if os.path.commonpath([base, path]) != base:
        raise ValueError(f"资源符号链接越界：{src}")
    return path


def output_path(path):
    """User-selected output may be outside the source root, but never a symlink."""
    path = os.path.abspath(path)
    if os.path.islink(path):
        raise ValueError(f"输出文件不能是符号链接：{path}")
    if os.path.exists(path) and not os.path.isfile(path):
        raise ValueError(f"输出目标不是普通文件：{path}")
    return path


def atomic_write(path, data, mode=0o644):
    """Replace one complete file; a failed write never truncates the previous file."""
    target = output_path(path)
    os.makedirs(os.path.dirname(target), exist_ok=True)
    payload = data.encode("utf-8") if isinstance(data, str) else data
    fd, temporary = tempfile.mkstemp(prefix=".wechat-write-", dir=os.path.dirname(target))
    try:
        with os.fdopen(fd, "wb") as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return target


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def contrast(foreground, background):
    """WCAG relative luminance for opaque #RRGGBB, not a device-rendering claim."""
    def luminance(color):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("颜色必须是 #RRGGBB")
        rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        rgb = [x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in rgb]
        return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]
    a, b = sorted((luminance(foreground), luminance(background)))
    return (b + 0.05) / (a + 0.05)
