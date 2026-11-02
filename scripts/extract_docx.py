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

from check import safe_http_url

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
WP = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}"


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
        match = re.search(r"(?:heading|标题)\s*([1-6])", name, re.I) \
            or re.fullmatch(r"([1-6])", sid)
        if match:
            levels[sid] = int(match.group(1))
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


def load_links(z):
    """外部超链接 rId → URL；与正文/发布预检共用 URL 安全边界。"""
    try:
        root = ET.fromstring(z.read("word/_rels/document.xml.rels"))
    except KeyError:
        return {}
    links = {}
    for rel in root:
        if not rel.get("Type", "").endswith("/hyperlink"):
            continue
        target = rel.get("Target", "")
        if not safe_http_url(target):
            raise ValueError(f"不支持的超链接：{target}")
        rid = rel.get("Id")
        if not rid:
            raise ValueError("超链接缺少关系 ID")
        links[rid] = target.replace("(", "%28").replace(")", "%29")
    return links


def para_text(p, links=None):
    """段内 run → 行内 Markdown（粗体→**、下划线→<u>）。"""
    links = links or {}
    out = []
    run_links = {id(run): links.get(h.get(f"{R}id"), "")
                 for h in p.iter(f"{W}hyperlink") for run in h.iter(f"{W}r")}
    for r_el in p.iter(f"{W}r"):
        rpr = r_el.find(f"{W}rPr")
        bold = rpr is not None and rpr.find(f"{W}b") is not None \
            and (rpr.find(f"{W}b").get(f"{W}val") or "1") not in ("0", "false")
        underline = rpr is not None and rpr.find(f"{W}u") is not None \
            and rpr.find(f"{W}u").get(f"{W}val") != "none"
        text = "".join(
            (node.text or "") if node.tag == f"{W}t"
            else "\n" if node.tag == f"{W}br"
            else "\t" if node.tag == f"{W}tab" else ""
            for node in r_el
        )
        if not text:
            continue
        if bold:
            text = f"**{text}**"
        if underline:
            text = f"<u>{text}</u>"
        url = run_links.get(id(r_el))
        if url:
            text = f"[{text}]({url})"
        out.append(text)
    return re.sub(r"\*\*\*\*", "", "".join(out))  # 相邻粗体 run 合并的空标记


def image_alt(p, rid):
    """取 rid 对应图片的替换文字（docPr 的 descr / title）。"""
    for tag in ("inline", "anchor"):
        for container in p.iter(f"{WP}{tag}"):
            if not any(blip.get(f"{R}embed") == rid for blip in container.iter(f"{A}blip")):
                continue
            doc_pr = container.find(f"{WP}docPr")
            if doc_pr is not None:
                return (doc_pr.get("descr") or doc_pr.get("title") or "").strip()
    return ""


def validate_body(z, body, links, media_of):
    """写出前定位所有不可保真的结构；返回空列表才允许继续。"""
    unsupported = {"txbxContent", "altChunk", "footnoteReference", "endnoteReference",
                   "gridSpan", "vMerge", "ins", "del", "fldChar", "chart", "diagram",
                   "pict", "object", "oMath", "sdt"}
    names = set(z.namelist())
    problems = []
    for index, el in enumerate(body, 1):
        tags = {node.tag.split("}")[-1] for node in el.iter()}
        bad = sorted(tags & unsupported)
        if el.tag == f"{W}tbl":
            if any(tc.findall(f".//{A}blip") for tc in el.iter(f"{W}tc")):
                bad.append("表格内图片")
            widths = [len(row.findall(f"{W}tc")) for row in el.findall(f"{W}tr")]
            if widths and (not widths[0] or any(width != widths[0] for width in widths)):
                bad.append("表格行列不齐")
            if any(len(tc.findall(f"{W}p")) > 1 for tc in el.iter(f"{W}tc")):
                bad.append("单元格多段落")
            if any(node.tag in (f"{W}br", f"{W}tab")
                   for tc in el.iter(f"{W}tc") for node in tc.iter()):
                bad.append("单元格内换行或制表符")
        if len(list(el.iter(f"{W}tbl"))) > (1 if el.tag == f"{W}tbl" else 0):
            bad.append("嵌套表格")
        if bad:
            problems.append(f"正文块 {index}：{', '.join(bad)}")
        if el.tag not in {f"{W}p", f"{W}tbl", f"{W}sectPr"}:
            problems.append(f"正文块 {index}：不支持的顶层结构 {el.tag}")
        for hyperlink in el.iter(f"{W}hyperlink"):
            if hyperlink.get(f"{R}id") not in links:
                problems.append(f"正文块 {index}：内部锚点或缺失的链接关系")
        for blip in el.iter(f"{A}blip"):
            src = media_of.get(blip.get(f"{R}embed"))
            if not src or src not in names:
                problems.append(f"正文块 {index}：外链图片或缺失素材关系")
    return problems


def notes_with_text(z):
    """列出含正文的脚注、尾注或批注部件；这些不能被静默丢弃。"""
    found = []
    for name in z.namelist():
        if not re.match(r"word/(?:footnotes|endnotes|comments).*\.xml$", name):
            continue
        try:
            root = ET.fromstring(z.read(name))
        except ET.ParseError as error:
            raise ValueError(f"注释部件 XML 无效：{name}") from error
        if any((node.text or "").strip() for node in root.iter(f"{W}t")):
            found.append(name)
    return found


def plan_images(z, body, img_dir, media_of):
    """先读完并检查全部图片，再允许任何文件写入，避免半成品覆盖。"""
    planned = []
    for paragraph in body.iter(f"{W}p"):
        for blip in paragraph.iter(f"{A}blip"):
            src = media_of.get(blip.get(f"{R}embed"))
            if not src:
                continue
            target = os.path.join(img_dir, f"{len(planned) + 1:02d}-" + os.path.basename(src))
            data = z.read(src)
            if os.path.exists(target):
                with open(target, "rb") as existing:
                    if existing.read() != data:
                        raise ValueError(f"输出图片同名不同内容，拒绝覆盖：{target}")
            planned.append((target, data))
    return planned


def write_images(out_dir, img_dir, planned):
    os.makedirs(out_dir, exist_ok=True)
    if planned:
        os.makedirs(img_dir, exist_ok=True)
    for target, data in planned:
        with open(target, "wb") as output:
            output.write(data)


def table_lines(table, links):
    """普通表格保住行列；复杂表格已在 validate_body 拦截。"""
    source_rows = table.findall(f"{W}tr")
    if not source_rows:
        return []
    rows = []
    for row in source_rows:
        cells = [" / ".join(para_text(p, links) for p in cell.findall(f"{W}p"))
                 .strip().replace("|", "\\|") or " "
                 for cell in row.findall(f"{W}tc")]
        rows.append("| " + " | ".join(cells) + " |")
    columns = len(source_rows[0].findall(f"{W}tc"))
    return [rows[0], "|" + "---|" * columns, *rows[1:], ""]


def paragraph_lines(paragraph, heading_of, media_of, links, image_start):
    """返回 Markdown 行、图片序号、人工核对提示与文字类别。"""
    lines, notices = [], []
    blips = list(paragraph.iter(f"{A}blip"))
    text = para_text(paragraph, links).strip()
    if blips and text:
        notices.append("注意：图文混排段归一为图片后接文字，请核对位置")
    image_number = image_start
    for blip in blips:
        rid = blip.get(f"{R}embed")
        src = media_of.get(rid)
        if not src:
            continue
        image_number += 1
        filename = f"{image_number:02d}-" + os.path.basename(src)
        alt = image_alt(paragraph, rid).replace("[", "(").replace("]", ")").replace("\n", " ")
        lines.extend([f"![{alt}](images/{filename})", ""])
        if alt:
            notices.append(f"图注来自 Word 替换文字：{alt[:40]}（仍须补职责与来源）")
    if not text:
        return lines, image_number, notices, None

    ppr = paragraph.find(f"{W}pPr")
    style_el = ppr.find(f"{W}pStyle") if ppr is not None else None
    style_id = style_el.get(f"{W}val") if style_el is not None else ""
    level = heading_of.get(style_id)
    is_list = (ppr is not None and ppr.find(f"{W}numPr") is not None) \
        or bool(re.search(r"list|列表", style_id or "", re.I))
    if level:
        clean = re.sub(r"^\*\*(.*)\*\*$", r"\1", text)
        lines.append("#" * min(level, 3) + " " + clean)
        category = "heading"
        if level > 3:
            notices.append(f"注意：标题{level}归一化为三级，请核对层级")
    elif is_list:
        notices.append("注意：列表编号/嵌套归一为无序列表，请核对顺序语义")
        lines.append("- " + text)
        category = "list"
    else:
        lines.append(text)
        category = "paragraph"
    lines.append("")
    return lines, image_number, notices, category


def extract(docx_path, out_md):
    try:
        archive = zipfile.ZipFile(docx_path)
    except (OSError, zipfile.BadZipFile) as error:
        print(f"✗ 不是合法 docx：{error}", file=sys.stderr)
        return 1

    try:
        with archive as z:
            try:
                if len(z.infolist()) > 10000 or sum(i.file_size for i in z.infolist()) > 100 * 1024 * 1024:
                    raise ValueError("DOCX 解压内容超过 100MB 或 10000 项限制")
                doc = ET.fromstring(z.read("word/document.xml"))
            except (ValueError, KeyError, zipfile.BadZipFile, ET.ParseError) as error:
                print(f"✗ 不是合法 docx：{error}", file=sys.stderr)
                return 1
            try:
                heading_of = load_styles(z)
                media_of = load_rels(z)
                links = load_links(z)
            except (ET.ParseError, ValueError) as error:
                print(f"✗ docx 关系或 XML 无效：{error}", file=sys.stderr)
                return 1

            body = doc.find(f"{W}body")
            if body is None:
                print("✗ docx 缺少正文 body", file=sys.stderr)
                return 1
            problems = validate_body(z, body, links, media_of)
            if problems:
                print("✗ 转换会丢失语义，未写出成稿；请先在 Word 展平或另附材料：\n"
                      + "\n".join(problems), file=sys.stderr)
                return 1
            try:
                notes = notes_with_text(z)
            except ValueError as error:
                print(f"✗ {error}，未写出成稿", file=sys.stderr)
                return 1
            if notes:
                print("✗ 文档含脚注／尾注／批注正文，转换会丢失内容；请先在 Word 中把它们并入正文：\n  "
                      + "\n  ".join(notes), file=sys.stderr)
                return 1

            furniture = [name for name in z.namelist()
                         if re.match(r"word/(?:header|footer).*\.xml$", name)]
            if furniture:
                print("  注意：仅提取正文；页眉页脚未转换，请人工核对是否含正文信息："
                      + ", ".join(furniture), file=sys.stderr)

            out_dir = os.path.dirname(os.path.abspath(out_md)) or "."
            img_dir = os.path.join(out_dir, "images")
            try:
                planned = plan_images(z, body, img_dir, media_of)
            except ValueError as error:
                print(f"✗ {error}", file=sys.stderr)
                return 1
            write_images(out_dir, img_dir, planned)

            lines, image_number, tables = [], 0, 0
            counts = {"paragraph": 0, "heading": 0, "list": 0}
            for element in body:
                if element.tag == f"{W}tbl":
                    converted = table_lines(element, links)
                    if converted:
                        lines.extend(converted)
                        tables += 1
                    continue
                if element.tag != f"{W}p":
                    continue
                converted, image_number, notices, category = paragraph_lines(
                    element, heading_of, media_of, links, image_number)
                lines.extend(converted)
                for notice in notices:
                    print(f"  {notice}", file=sys.stderr)
                if category:
                    counts[category] += 1
            markdown = "\n".join(lines).rstrip() + "\n"

        with open(out_md, "w", encoding="utf-8") as output:
            output.write(markdown)
    except (OSError, KeyError, ValueError, zipfile.BadZipFile, ET.ParseError) as error:
        print(f"✗ docx 抽取失败：{error}", file=sys.stderr)
        return 1

    print(f"✓ {os.path.basename(docx_path)} → {out_md}")
    print(f"  段落 {counts['paragraph']} · 标题 {counts['heading']} · 列表 {counts['list']} · 图片 {image_number}"
          + (f" · 表格 {tables}（已转 Markdown 表格）" if tables else ""))
    if image_number:
        print(f"  ⚠ 抽出的 {image_number} 张图没有职责：进 render 前先补成 ![说明](路径 \"职责\")，"
              "否则 Gate 2 会判「必须改」", file=sys.stderr)
    return 0


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("docx")
    parser.add_argument("-o", "--out", help="输出 md 路径（默认同名 .md）")
    args = parser.parse_args()
    if not args.docx.lower().endswith(".docx"):
        parser.error("仅支持 .docx，不支持旧版 .doc / PDF")
    if not os.path.isfile(args.docx):
        print(f"✗ 文件不存在: {args.docx}", file=sys.stderr)
        sys.exit(1)
    out = args.out or re.sub(r"\.docx$", "", args.docx, flags=re.I) + ".md"
    sys.exit(extract(args.docx, out))


if __name__ == "__main__":
    main()
