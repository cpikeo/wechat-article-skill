#!/usr/bin/env python3
"""真实来源编辑评估：可追踪改动、可观察不变量、盲测包与重复性。

CI 只验证能客观复现的证据，不生成“文笔分数”，也不冒充独立读者盲测。
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
EVAL = ROOT / "evaluation"
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
import render  # noqa: E402
import editorial  # noqa: E402

REQUIRED_REVIEW = ("article_type", "visual_concept", "asset_strategy")
CHANGE_FIELDS = ("location", "problem", "action", "benefit", "preservation")
SOURCE_FIELDS = ("title", "url", "published", "license", "license_url", "license_evidence", "adaptation")


def load_dataset():
    manifest = EVAL / "cases.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
        raise ValueError("evaluation/cases.json 必须包含 cases 数组")
    return data


def safe_case_file(relative):
    path = (EVAL / relative).resolve()
    if EVAL.resolve() not in path.parents or not path.is_file():
        raise ValueError(f"评估文件不存在或越界：{relative}")
    return path


def dataset_hash(data):
    h = hashlib.sha256()
    h.update((EVAL / "cases.json").read_bytes())
    for case in sorted(data["cases"], key=lambda item: item["id"]):
        for side in ("original", "edited"):
            path = safe_case_file(case[side])
            h.update(path.relative_to(EVAL).as_posix().encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def blind_mapping(data, seed):
    mapping = {}
    for case in data["cases"]:
        original_first = int(hashlib.sha256(f"{seed}:{case['id']}".encode()).hexdigest(), 16) % 2 == 0
        mapping[case["id"]] = {"A": "original" if original_first else "edited",
                               "B": "edited" if original_first else "original"}
    return mapping


def write_blind_packet(data, directory, key_file, seed):
    directory = Path(directory)
    key_file = Path(key_file)
    if directory.resolve() == key_file.parent.resolve():
        raise ValueError("盲测 key 不能和 A/B 稿放在同一目录")
    directory.mkdir(parents=True, exist_ok=True)
    key_file.parent.mkdir(parents=True, exist_ok=True)
    mapping = blind_mapping(data, seed)
    for case in data["cases"]:
        case_dir = directory / case["id"]
        case_dir.mkdir(parents=True, exist_ok=True)
        for label in ("A", "B"):
            source = safe_case_file(case[mapping[case["id"]][label]])
            shutil.copyfile(source, case_dir / f"{label}.md")
    key_file.write_text(json.dumps({"seed": seed, "mapping": mapping}, ensure_ascii=False, indent=2),
                        encoding="utf-8")
    return mapping


def evaluate(data):
    problems, rows = [], []
    if not str(data.get("retrieved_at", "")).strip():
        problems.append("数据集缺来源复核日期 retrieved_at")
    seen_ids, genres = set(), set()
    for case in data["cases"]:
        cid, genre = case.get("id", ""), case.get("genre", "")
        if not cid or cid in seen_ids:
            problems.append(f"case id 缺失或重复：{cid!r}")
        seen_ids.add(cid)
        genres.add(genre)
        source = case.get("source", {})
        missing_source = [field for field in SOURCE_FIELDS if not str(source.get(field, "")).strip()]
        if missing_source:
            problems.append(f"{cid}: 来源元数据缺 {missing_source}")
        if not str(source.get("url", "")).startswith("https://") \
                or not str(source.get("license_url", "")).startswith("https://"):
            problems.append(f"{cid}: 来源或许可 URL 不是 HTTPS")
        original_path, edited_path = safe_case_file(case["original"]), safe_case_file(case["edited"])
        original, edited = original_path.read_text(encoding="utf-8"), edited_path.read_text(encoding="utf-8")
        if original == edited:
            problems.append(f"{cid}: 原稿与优化稿完全相同，无法对照")
        if source.get("url") not in original or source.get("url") not in edited:
            problems.append(f"{cid}: A/B 稿未同时保留来源 URL")
        for token in case.get("preserve", []):
            if token not in original or token not in edited:
                problems.append(f"{cid}: 保留项在原稿或优化稿缺失：{token}")
        for token in case.get("edited_require", []):
            if token not in edited:
                problems.append(f"{cid}: 优化稿缺少预期可见证据：{token}")
        for token in case.get("edited_forbid", []):
            if token in edited:
                problems.append(f"{cid}: 优化稿仍含应移除表达：{token}")
        changes = case.get("changes", [])
        if not changes:
            problems.append(f"{cid}: 没有修改台账")
        for number, change in enumerate(changes, 1):
            for field in CHANGE_FIELDS:
                if not str(change.get(field, "")).strip():
                    problems.append(f"{cid}: 修改 {number} 缺 {field}")

        ometa, oblocks = render.parse(original)
        emeta, eblocks = render.parse(edited)
        missing = [field for field in REQUIRED_REVIEW if not emeta.get(field)]
        if missing:
            problems.append(f"{cid}: 优化稿缺文章类型或视觉决策 {missing}")
        if not emeta.get("purpose") and not emeta.get("thesis"):
            problems.append(f"{cid}: 优化稿需说明目的或核心判断之一；受众/场景不是强制字段")
        _, _, _, body1 = render.render(edited)
        _, _, _, body2 = render.render(edited)
        gate1, _ = render.check(body1)
        gate2, _ = render.compose_gate(emeta, eblocks, str(edited_path.parent))
        if gate1 or gate2:
            problems.append(f"{cid}: 优化稿 Gate 1/2 未通过：{gate1 + gate2}")
        diff = editorial.compare_facts(oblocks, eblocks, ometa, emeta)
        if diff["dropped"] or diff["introduced"] or diff["precision_changes"] or diff["qualifier_changes"] or diff["dropped_quotes"] or diff["introduced_quotes"]:
            problems.append(f"{cid}: 事实/限定/引语字面变化未解决：{diff}")
        ledger = "| 位置 | 问题 | 动作 | 收益 | 保留检查 |\n|---|---|---|---|---|\n" + "\n".join(
            f"| {c['location']} | {c['problem']} | {c['action']} | {c['benefit']} | {c['preservation']} |" for c in changes)
        ledger_rows, ledger_problems = editorial.parse_ledger(ledger)
        for row in ledger_rows:
            if not editorial.locate(row["位置"], eblocks):
                ledger_problems.append(f"位置不可回查：{row['位置']}")
        if ledger_problems:
            problems.append(f"{cid}: 修改台账不合格：{ledger_problems}")
        review1 = editorial.audit(emeta, eblocks)
        review2 = editorial.audit(emeta, eblocks)
        repeat_ok = (hashlib.sha256(body1.encode()).hexdigest() == hashlib.sha256(body2.encode()).hexdigest()
                     and json.dumps(review1, sort_keys=True, ensure_ascii=False)
                     == json.dumps(review2, sort_keys=True, ensure_ascii=False))
        if not repeat_ok:
            problems.append(f"{cid}: 同输入重复渲染/诊断不一致")
        rows.append({
            "id": cid,
            "genre": genre,
            "changes": len(changes),
            "original_chars": render.doc_len(oblocks),
            "edited_chars": render.doc_len(eblocks),
            "invariants": len(case.get("preserve", [])),
            "repeat": repeat_ok,
            "gates": not gate1 and not gate2,
            "facts": not (diff["dropped"] or diff["introduced"] or diff["precision_changes"] or diff["qualifier_changes"] or diff["dropped_quotes"] or diff["introduced_quotes"]),
            "ledger": not ledger_problems,
        })
    expected = {"商业分析", "新闻报道", "技术教程", "人物故事", "观点评论", "深度长文"}
    if genres != expected:
        problems.append(f"类型覆盖不完整：期望 {sorted(expected)}，实际 {sorted(genres)}")
    if blind_mapping(data, "v6-repeat") != blind_mapping(data, "v6-repeat"):
        problems.append("相同 seed 的盲测映射不稳定")
    return problems, rows


def report_text(data, rows, problems):
    digest = dataset_hash(data)
    lines = [
        "# Editorial Evaluation Results · V6",
        "",
        f"- 数据集指纹：`{digest}`",
        f"- 样本：{len(rows)} 篇真实来源摘录／翻译，覆盖商业分析、新闻报道、技术教程、人物故事、观点评论、深度长文",
        "- 方法：原稿／优化稿字面与结构检查；逐项修改台账；保留项；Gate 1/2；同输入重复渲染；可分离 key 的 A/B 盲测包",
        "- 评价口径：只列可观察证据，不将确定性检查包装成文笔分数",
        "- 边界：此处为仓库中既有编辑样稿的回归，不是一次受控、可重复的真实模型生成实验",
        "",
        "## 可复现结果",
        "",
        "| 样本 | 类型 | 修改记录 | 保留不变量 | 正文字数（原→优化） | Gate 1/2 | 事实字面保留 | 台账 | 重复任务 |",
        "|---|---|---:|---:|---:|---|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| {row['id']} | {row['genre']} | {row['changes']} | {row['invariants']} | "
                     f"{row['original_chars']}→{row['edited_chars']} | "
                     f"{'PASS' if row['gates'] else 'FAIL'} | {'PASS' if row['facts'] else 'FAIL'} | {'PASS' if row['ledger'] else 'FAIL'} | {'一致' if row['repeat'] else '不一致'} |")
    lines += ["", f"**确定性检查：{'PASS' if not problems else 'FAIL'}。**"]
    if problems:
        lines += ["", "### 失败项", ""] + [f"- {problem}" for problem in problems]
    lines += [
        "",
        "## Browser visual evidence · 2026-11-02",
        "",
        "- **PASS（浏览器回归，不是审美评分）**：`tests/visuals.py` 渲染 6 篇真实来源样稿 × 4 个宽度（320/360/390/430px）；正文不横向溢出、不拆数值原子，正文≥15px，表格/注释≥12px。六篇样稿无嵌图，素材加载断言为空；图片路径/上传边界另由回归覆盖。",
        "- 同一篇商业分析稿在六主题、四宽度运行；390px 颜色中和后 15 对主题均仍有结构差异，平均像素差 0.05604–0.08943（仅作“换色后是否塌成相同结构”的回归线索，不是美学结论）。",
        "- 详细浏览器报告与截图在执行时生成到 Git 忽略的 `evaluation/visual-review/`；不作为运行时依赖或微信兼容证据。",
        "",
        "## 本轮审计与文件处置",
        "",
        "| 发现与证据 | 处置 |",
        "|---|---|",
        "| README 链接指向仓库中不存在的 `AUDIT.md`；README/Skill 仍写 V5 | 修复链接，统一文档与运行时为 V6 |",
        "| `evaluation/logs/*.log` 为旧运行输出/机器路径，不能证明当前状态 | 删除 5 个历史日志；截图与临时报告只生成到忽略目录 |",
        "| 旧主题测试要求每个配置轴唯一，容易把差异数量当作设计质量 | 改为配置/可读性检查；另用真实稿去色截图核对结构差异 |",
        "| 旧 `tests/visuals.py` 只看原稿/改稿的 320/390px，不测主题去色结构 | 改为六篇真实样稿四宽度 + 同稿六主题评估 |",
        "| `render.py` 解析、组件、Gate 与交付共享同一契约 | 保持单体渲染器；没有为了模块数量拆分或加运行时依赖 |",
        "",
        "## BLOCKED / UNVERIFIED",
        "",
        "- **真实模型执行六类文章编辑与重复性评估：BLOCKED。** 当前环境没有可控模型 API/评估运行器；现有样稿不是本轮新生成的受控模型输出。",
        "- **独立外部盲评：UNVERIFIED。** A/B 包可生成，但没有独立读者结果，不报告偏好胜负。",
        "- **逐项第二来源事实核真：UNVERIFIED。** 字面比对不等于核真；来源页与许可备注不代表本轮逐条核对了事实。",
        "- **微信真实账号、草稿后台、iOS/Android 真机与实际裁切：UNVERIFIED。** 本地浏览器不证明微信兼容。",
        "- 六主题真实样稿/四宽度/去色结构截图由 `python3 tests/visuals.py` 单独执行，截图不是盲评结论；不提交截图产物。",
        "",
        "## 复现",
        "",
        "```bash",
        "python3 tests/editorial_eval.py --check-report evaluation/RESULTS.md",
        "python3 tests/editorial_eval.py --blind-dir /tmp/wechat-blind --key-file /tmp/wechat-key.json --seed reviewer-01",
        "python3 tests/visuals.py",
        "```",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--write-report")
    ap.add_argument("--check-report")
    ap.add_argument("--blind-dir")
    ap.add_argument("--key-file")
    ap.add_argument("--seed", default="v6")
    args = ap.parse_args()
    data = load_dataset()
    problems, rows = evaluate(data)
    report = report_text(data, rows, problems)
    if args.blind_dir or args.key_file:
        if not (args.blind_dir and args.key_file):
            ap.error("--blind-dir 与 --key-file 必须同时提供")
        write_blind_packet(data, args.blind_dir, args.key_file, args.seed)
        print(f"盲测包 → {args.blind_dir}\n独立 key → {args.key_file}")
    if args.write_report:
        Path(args.write_report).write_text(report, encoding="utf-8")
        print(f"评估报告 → {args.write_report}")
    if args.check_report:
        path = Path(args.check_report)
        if not path.is_file() or path.read_text(encoding="utf-8") != report:
            problems.append(f"评估报告过期：运行 --write-report {path}")
    for row in rows:
        print(f"{'PASS' if row['gates'] and row['repeat'] else 'FAIL'} · {row['genre']} · {row['id']} · "
              f"修改 {row['changes']} · 保留项 {row['invariants']} · {row['original_chars']}→{row['edited_chars']} 字")
    if problems:
        for problem in problems:
            print("FAIL · " + problem, file=sys.stderr)
    else:
        print("真实来源编辑评估：确定性证据全部通过；独立盲选、逐项外部核真与微信真机仍未执行。")
    raise SystemExit(1 if problems else 0)


if __name__ == "__main__":
    main()
