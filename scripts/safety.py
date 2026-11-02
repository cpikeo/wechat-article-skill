"""Deterministic local asset boundary and content hashes; not an authenticity signature."""
import hashlib
import os
import re


def local_path(src, root):
    if not isinstance(src, str) or not src or '\x00' in src or '\\' in src:
        raise ValueError('非法本地资源路径')
    if os.path.isabs(src) or re.match(r'^[a-zA-Z]:|^[a-zA-Z][a-zA-Z0-9+.-]*:|^//', src):
        raise ValueError(f'资源路径必须相对文章目录：{src}')
    if any(part == '..' for part in src.split('/')):
        raise ValueError(f'资源路径禁止 ..：{src}')
    base = os.path.realpath(root)
    path = os.path.realpath(os.path.join(base, src))
    if os.path.commonpath([base, path]) != base:
        raise ValueError(f'资源符号链接越界：{src}')
    return path


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


def contrast(foreground, background):
    """WCAG relative luminance for opaque #RRGGBB; does not assess device rendering."""
    def luminance(color):
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError('颜色必须是 #RRGGBB')
        rgb = [int(color[i:i+2], 16) / 255 for i in (1, 3, 5)]
        rgb = [x / 12.92 if x <= .04045 else ((x + .055) / 1.055) ** 2.4 for x in rgb]
        return .2126 * rgb[0] + .7152 * rgb[1] + .0722 * rgb[2]
    a, b = sorted((luminance(foreground), luminance(background)))
    return (b + .05) / (a + .05)
