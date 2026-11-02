#!/usr/bin/env python3
"""Word .docx → Markdown 提取器（零外部依赖）。

格式归一化层的确定性组件：把 docx 的标题层级 / 粗体 / 列表 / 图片
转成本 skill 排版流程认识的 Markdown。

用法：
    extract_docx.py 文章.docx [-o 输出.md]
    # 内嵌图片解包到 输出.md 同目录的 images/ 下，md 里用相对路径引用

退出码：0 成功；1 失败（文件不存在 / 不是合法 docx）。
普通表格转成 Markdown；合并单元格、文本框等不能保真的结构定位报错，不静默跳过。
抽完只是素材，不是成稿：图片必须补职责（![说明](路径 "职责")），文字还要走一遍 EDIT。
"""

import argparse
import os
import posixpath
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"


def load_styles(z):
    """styleId → 标题级别（1/2/3…）；非标题样式不入表。"""
    levels = {}
    try:
        root = ET.fromstring(z.read("word/styles.xml"))
    except KeyError:
        return levels
    for st in root.iter(f"{W}style"):
        sid = st.get(f"{W}styleId") or ""
        name_el = st.find(f"{W}name")
        name = (name_el.get(f"{W}val") if name_el is not None else "") or ""
        m = re.search(r"(?:heading|标题)\s*([1-6])", name, re.I) \
            or re.fullmatch(r"([1-6])", sid)
        if m:
            levels[sid] = int(m.group(1))
    return levels


def load_rels(z):
    """rId → 媒体文件路径（word/media/...）。"""
    rels = {}
    try:
        root = ET.fromstring(z.read("word/_rels/document.xml.rels"))
    except KeyError:
        return rels
    for rel in root:
        target = rel.get("Target") or ""
        if rel.get("TargetMode") == "External":
            continue
        resolved = posixpath.normpath(posixpath.join("word", target))
        if resolved.startswith("word/media/") and ".." not in resolved.split("/"):
            rels[rel.get("Id")] = resolved
    return rels


def para_text(p, links=None):
    """段内 run → 行内 Markdown（粗体→**、下划线→<u>）。"""
    links = links or {}
    out = []
    # Map runs to enclosing hyperlink; preserve target without flattening semantics.
    run_links = {id(run): links.get(h.get(f"{R}id"), "")
                 for h in p.iter(f"{W}hyperlink") for run in h.iter(f"{W}r")}
    for r_el in p.iter(f"{W}r"):
        rpr = r_el.find(f"{W}rPr")
        bold = rpr is not None and rpr.find(f"{W}b") is not None \
            and (rpr.find(f"{W}b").get(f"{W}val") or "1") not in ("0", "false")
        ul = rpr is not None and rpr.find(f"{W}u") is not None and rpr.find(f"{W}u").get(f"{W}val") != "none"
        text = "".join((x.text or "") if x.tag == f"{W}t" else "\n" if x.tag == f"{W}br" else "\t" if x.tag == f"{W}tab" else "" for x in r_el)
        if not text:
            continue
        if bold:
            text = f"**{text}**"
        if ul:
            text = f"<u>{text}</u>"
        url = run_links.get(id(r_el))
        if url:
            text = f"[{text}]({url})"
        out.append(text)
    s = "".join(out)
    return re.sub(r"\*\*\*\*", "", s)  # 相邻粗体 run 合并的空标记


def extract(docx_path, out_md):
    try:
        z = zipfile.ZipFile(docx_path)
        if len(z.infolist()) > 10000 or sum(i.file_size for i in z.infolist()) > 100 * 1024 * 1024:
            raise ValueError("DOCX 解压内容超过 100MB 或 10000 项限制")
        doc = ET.fromstring(z.read("word/document.xml"))
    except (OSError, ValueError, zipfile.BadZipFile, KeyError, ET.ParseError) as e:
        print(f"✗ 不是合法 docx：{e}", file=sys.stderr)
        return 1

    try:
        heading_of = load_styles(z)
        media_of = load_rels(z)
        links = {}
        if "word/_rels/document.xml.rels" in z.namelist():
            for rel in ET.fromstring(z.read("word/_rels/document.xml.rels")):
                if rel.get("Type", "").endswith("/hyperlink"):
                    target = rel.get("Target", "")
                    if not re.match(r"^https?://[^\s]+$", target):
                        raise ValueError(f"不支持的超链接：{target}")
                    links[rel.get("Id")] = target.replace("(", "%28").replace(")", "%29")
    except (ET.ParseError, ValueError) as e:
        z.close()
        print(f"✗ docx XML无效：{e}", file=sys.stderr)
        return 1
    out_dir = os.path.dirname(os.path.abspath(out_md)) or "."
    img_dir = os.path.join(out_dir, "images")
    lines, img_n, tables = [], 0, 0

    body = doc.find(f"{W}body")
    if body is None:
        print("✗ docx 缺少正文body", file=sys.stderr)
        z.close()
        return 1
    # Reject lossy structures before writing any output; paragraph index locates the problem.
    problems = []
    unsupported = {"txbxContent", "altChunk", "footnoteReference", "endnoteReference",
                   "gridSpan", "vMerge", "ins", "del", "fldChar", "chart", "diagram", "pict", "object", "oMath", "sdt"}
    for index, el in enumerate(body, 1):
        tags = {node.tag.split("}")[-1] for node in el.iter()}
        bad = sorted(tags & unsupported)
        if el.tag == f"{W}tbl" and any(True for tc in el.iter(f"{W}tc") for _ in tc.iter(f"{A}blip")):
            bad.append("表格内图片")
        if len(list(el.iter(f"{W}tbl"))) > (1 if el.tag == f"{W}tbl" else 0):
            bad.append("嵌套表格")
        if el.tag == f"{W}tbl":
            widths = [len(row.findall(f"{W}tc")) for row in el.findall(f"{W}tr")]
            if widths and (not widths[0] or any(w != widths[0] for w in widths)):
                bad.append("表格行列不齐")
            if any(len(tc.findall(f"{W}p")) > 1 for tc in el.iter(f"{W}tc")):
                bad.append("单元格多段落")
            if any(node.tag in (f"{W}br", f"{W}tab") for tc in el.iter(f"{W}tc") for node in tc.iter()):
                bad.append("单元格内换行或制表符")
        if bad:
            problems.append(f"正文块 {index}：{', '.join(bad)}")
        if el.tag not in {f"{W}p", f"{W}tbl", f"{W}sectPr"}:
            problems.append(f"正文块 {index}：不支持的顶层结构 {el.tag}")
        # Tables may also contain hyperlinks; validate all descendants.
        for h in el.iter(f"{W}hyperlink"):
            if h.get(f"{R}id") not in links:
                problems.append(f"正文块 {index}：内部锚点或缺失的链接关系")
        for blip in el.iter(f"{A}blip"):
            if blip.get(f"{R}embed") not in media_of or media_of.get(blip.get(f"{R}embed")) not in z.namelist():
                problems.append(f"正文块 {index}：外链图片或缺失素材关系")
    if problems:
        z.close()
        print("✗ 转换会丢失语义，未写出成稿；请先在 Word 展平或另附材料：\n" + "\n".join(problems), file=sys.stderr)
        return 1
    # 脚注／尾注／批注是正文内容的一部分：静默丢掉就是改稿。必须阻断，让作者先展平。
    with_text = []
    for name in z.namelist():
        if re.match(r"word/(?:footnotes|endnotes|comments).*\.xml$", name):
            try:
                note_root = ET.fromstring(z.read(name))
            except ET.ParseError:
                z.close()
                print(f"✗ 注释部件 XML 无效，未写出成稿：{name}", file=sys.stderr)
                return 1
            if any((node.text or "").strip() for node in note_root.iter(f"{W}t")):
                with_text.append(name)
    if with_text:
        z.close()
        print("✗ 文档含脚注／尾注／批注正文，转换会丢失内容；请先在 Word 中把它们并入正文：\n  "
              + "\n  ".join(with_text), file=sys.stderr)
        return 1
    # 页眉页脚通常是页码等页面家具：不阻断，但必须显式列出让人核对。
    furniture = [name for name in z.namelist()
                 if re.match(r"word/(?:header|footer).*\.xml$", name)]
    if furniture:
        print("  注意：仅提取正文；页眉页脚未转换，请人工核对是否含正文信息："
              + ", ".join(furniture), file=sys.stderr)
    planned_images = []
    image_index = 0
    for p in body.iter(f"{W}p"):
        for blip in p.iter(f"{A}blip"):
            src = media_of.get(blip.get(f"{R}embed"))
            if not src:
                continue
            image_index += 1
            fname = f"{image_index:02d}-" + os.path.basename(src)
            target = os.path.join(img_dir, fname)
            data = z.read(src)
            if os.path.exists(target):
                with open(target, "rb") as existing:
                    if existing.read() != data:
                        z.close()
                        print(f"✗ 输出图片同名不同内容，拒绝覆盖：{target}", file=sys.stderr)
                        return 1
            planned_images.append((target, data))
    os.makedirs(out_dir, exist_ok=True)
    for target, data in planned_images:
        os.makedirs(img_dir, exist_ok=True)
        with open(target, "wb") as f:
            f.write(data)
    for el in body:
        tag = el.tag
        if tag == f"{W}tbl":
            # 普通表格保住行列；复杂表格已在写出前拦截
            rows = []
            for tr in el.findall(f"{W}tr"):
                cells = [" / ".join(para_text(p, links) for p in tc.findall(f"{W}p"))
                         .strip().replace("|", "\\|") or " "
                         for tc in tr.findall(f"{W}tc")]
                rows.append("| " + " | ".join(cells) + " |")
            if rows:
                lines.append(rows[0])
                ncols = len(el.findall(f"{W}tr")[0].findall(f"{W}tc"))
                lines.append("|" + "---|" * ncols)
                lines.extend(rows[1:])
                lines.append("")
                tables += 1
            continue
        if tag != f"{W}p":
            continue
        p = el
        # 图片
        if any(True for _ in p.iter(f"{A}blip")) and para_text(p, links).strip():
            print("  注意：图文混排段归一为图片后接文字，请核对位置", file=sys.stderr)
        for blip in p.iter(f"{A}blip"):
            rid = blip.get(f"{R}embed")
            src = media_of.get(rid)
            if not src:
                continue
            img_n += 1
            fname = f"{img_n:02d}-" + os.path.basename(src)
            lines.append(f"![](images/{fname})")
            lines.append("")
        text = para_text(p, links).strip()
        if not text:
            continue
        ppr = p.find(f"{W}pPr")
        style_el = ppr.find(f"{W}pStyle") if ppr is not None else None
        sid = style_el.get(f"{W}val") if style_el is not None else ""
        lvl = heading_of.get(sid)
        # 列表识别：直接编号(numPr) 或 列表类段落样式（List Bullet/Number/Paragraph/中文"列表"）
        is_list = (ppr is not None and ppr.find(f"{W}numPr") is not None) \
            or bool(re.search(r"list|列表", sid or "", re.I))
        if lvl:
            text_clean = re.sub(r"^\*\*(.*)\*\*$", r"\1", text)  # 标题不需要再加粗
            lines.append("#" * min(lvl, 3) + " " + text_clean)
            if lvl > 3:
                print(f"  注意：标题{lvl}归一化为三级，请核对层级", file=sys.stderr)
        elif is_list:
            print("  注意：列表编号/嵌套归一为无序列表，请核对顺序语义", file=sys.stderr)
            lines.append("- " + text)
        else:
            lines.append(text)
        lines.append("")

    z.close()
    md = "\n".join(lines).rstrip() + "\n"
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"✓ {os.path.basename(docx_path)} → {out_md}")
    print(f"  段落 {sum(1 for l in lines if l and not l.startswith(('#','-','![')))} · "
          f"标题 {sum(1 for l in lines if l.startswith('#'))} · "
          f"列表 {sum(1 for l in lines if l.startswith('- '))} · 图片 {img_n}"
          + (f" · 表格 {tables}（已转 Markdown 表格）" if tables else ""))
    if img_n:
        print(f"  ⚠ 抽出的 {img_n} 张图没有职责：进 render 前先补成 ![说明](路径 \"职责\")，"
              f"否则 Gate 2 会判「必须改」", file=sys.stderr)
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("-o", "--out", help="输出 md 路径（默认同名 .md）")
    args = ap.parse_args()
    if not args.docx.lower().endswith(".docx"):
        ap.error("仅支持 .docx，不支持旧版 .doc / PDF")
    if not os.path.isfile(args.docx):
        print(f"✗ 文件不存在: {args.docx}", file=sys.stderr)
        sys.exit(1)
    out = args.out or re.sub(r"\.docx$", "", args.docx, flags=re.I) + ".md"
    try:
        sys.exit(extract(args.docx, out))
    except (OSError, KeyError, ET.ParseError) as e:
        sys.exit(f"✗ docx 抽取失败：{e}")


if __name__ == "__main__":
    main()
