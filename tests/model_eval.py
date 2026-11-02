#!/usr/bin/env python3
"""六类文章的受控评估运行器（标准库，无外部依赖）。

它解决 V6 评估最大的缺口：`evaluation/RESULTS.md` 里的样稿是仓库既有的成对稿，
不是可复现的一次生成实验。本运行器把实验协议、输出、评分与方差固定下来：

    python3 tests/model_eval.py --list
    python3 tests/model_eval.py --manifest                       # 输入/提示词指纹
    python3 tests/model_eval.py --record --run-dir DIR --model ID --temperature 0.7
    python3 tests/model_eval.py --report --run-dir DIR
    python3 tests/model_eval.py --blind --run-dir DIR --out /tmp/blind --key /tmp/key.json

边界（必须先读）：
- 它**不调用**任何模型 API：模型在会话里生成，运行器只负责「固定条件、留证据、算指标」。
  这样任何第三方都能用同一 prompts/ 与同一输入复跑，并用自己的输出覆盖 runs/。
- `--record` 只做结构校验（frontmatter、类型、重复次数、哈希），不评价好坏。
- `--report` 输出的是**可计算指标**（标题兑现台账、事实字面保留、文风线索密度、
  逐节信息增量、声音形态、Gate 1/2）。它明确分开三类证据：
  `automated`（机器可复算）/ `model_self`（模型自评，UNVERIFIED）/ `human`（未执行时 UNVERIFIED）。
- 单一分数会制造不存在的精度，因此报告只给逐项指标与分布，不给「总分」。
"""
import argparse
import hashlib
import json
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "scripts"))

import editorial as E          # noqa: E402
import render as R            # noqa: E402
from check import check       # noqa: E402

CASES_DIR = ROOT / "evaluation" / "cases"
PROMPT_DIR = ROOT / "evaluation" / "model-eval" / "prompts"
DEFAULT_RUNS = ROOT / "evaluation" / "model-eval" / "runs"
TYPES = ("news", "analysis", "tutorial", "profile", "opinion", "longform")
# 评估样本文件名 → 期望类型。原稿 frontmatter 里没有 article_type（它就是待编辑的原料），
# 所以期望类型由协议固定，而不是从输入里读出来自我印证。
CASE_TYPES = {"business": "analysis", "news": "news", "tutorial": "tutorial",
              "profile": "profile", "opinion": "opinion", "longform": "longform"}
# 与 scripts/editorial.py 的线索码保持同一集合：评估里数的「文风线索」必须就是
# 线上会报出来的那些，否则指标会统计一批用户看不到的规则。
STYLE_CODES = {"OPENING-CLICHE", "TEMPLATE-REPEAT", "REPEAT-SUBJECT", "EMPTY-ABSTRACT",
               "MONOTONE", "CIRCULAR", "META-DISCOURSE", "RESTATE-MARKER", "LONG-ATTRIB",
               "WEAK-INFERENCE", "PROSE-ORDINAL", "PARALLEL-HEAD", "HOLLOW-CLOSE",
               "PROSE-LIST", "EMPHASIS-OVERUSE", "DUP-NEAR", "DUP-EXACT"}


def sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_cases():
    """输入 = 仓库里已有的真实来源原稿；不复制第二份，避免语料出现两个版本。"""
    cases = {}
    for path in sorted(CASES_DIR.glob("*.original.md")):
        text = path.read_text(encoding="utf-8")
        meta, blocks = R.parse(text)
        name = path.name.replace(".original.md", "")
        cases[name] = {
            "path": path, "text": text, "meta": meta, "blocks": blocks,
            "declared_type": meta.get("article_type", "") or CASE_TYPES.get(name, ""),
            "resolved_type": CASE_TYPES.get(name, ""),
        }
    return cases


def prompt_for(case):
    """提示词模板 + 该类的编辑要求；同一 case 的每次重复使用完全相同的提示词。"""
    template = (PROMPT_DIR / "edit.md").read_text(encoding="utf-8")
    strategy = (PROMPT_DIR / f"type-{case['resolved_type']}.md")
    type_block = strategy.read_text(encoding="utf-8") if strategy.is_file() else ""
    return template.replace("{{ARTICLE_TYPE}}", case["resolved_type"]) \
                   .replace("{{TYPE_REQUIREMENTS}}", type_block.strip()) \
                   .replace("{{SOURCE}}", case["text"].strip())


def manifest(cases):
    rows = []
    for name, case in cases.items():
        prompt = prompt_for(case)
        rows.append({
            "case": name,
            "type": case["resolved_type"],
            "source_sha256": sha(case["text"]),
            "prompt_sha256": sha(prompt),
            "prompt_chars": len(prompt),
        })
    payload = {"generated_at": "fixed-by-content", "cases": rows,
               "manifest_sha256": sha(json.dumps(rows, sort_keys=True, ensure_ascii=False))}
    payload["generated_at"] = None     # 指纹只由内容决定，保证跨机器一致
    return payload


def record(run_dir, model, temperature, repeats, cases, notes=""):
    """校验并登记一次运行：文件齐全、类型正确、哈希可复算。"""
    run_dir = Path(run_dir)
    problems, entries = [], []
    for name, case in cases.items():
        for n in range(1, repeats + 1):
            path = run_dir / name / f"run-{n}.md"
            if not path.is_file():
                problems.append(f"缺少 {path.relative_to(run_dir)}")
                continue
            text = path.read_text(encoding="utf-8")
            try:
                meta, blocks = R.parse(text)
            except ValueError as exc:
                problems.append(f"{path.relative_to(run_dir)}：解析失败 {exc}")
                continue
            declared, ok = E.resolve_type(meta.get("article_type", ""))
            if not ok or declared != case["resolved_type"]:
                problems.append(f"{path.relative_to(run_dir)}：article_type 应解析为 {case['resolved_type']}，"
                                f"实际 {meta.get('article_type')!r}")
            if not meta.get("visual_concept"):
                problems.append(f"{path.relative_to(run_dir)}：缺 visual_concept（决策链第一环）")
            entries.append({"case": name, "repeat": n, "sha256": sha(text),
                            "chars": E.doc_len(blocks), "path": str(path.relative_to(run_dir))})
    payload = {
        "model": model,
        "temperature": temperature,
        "repeats": repeats,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "declared_limits": notes,
        "manifest_sha256": manifest(cases)["manifest_sha256"],
        "outputs": entries,
        "problems": problems,
        "status": "COMPLETE" if not problems else "INCOMPLETE",
    }
    (run_dir / "run.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def measure(text, case):
    """一次输出的全部可计算指标。每项都写明它测的是什么、不能证明什么。"""
    meta, blocks = R.parse(text)
    review = E.audit(meta, blocks)
    key, _ = E.resolve_type(meta.get("article_type", ""))
    diff = E.compare_facts(case["blocks"], blocks, case["meta"], meta)
    # 事实变化分级：搬进 data/bars 块或只在导语里做年份概括，都不是「丢了事实」。
    # 混在一起会让报告把一次排版决定读成事实损失，评估就失真了。
    dropped_kind = {v: E.classify_fact_change(case["blocks"], blocks, "num", v) for v in diff["dropped"]}
    moved = [v for v, (k, _) in dropped_kind.items() if k == "moved"]
    lost = [v for v, (k, _) in dropped_kind.items() if k not in ("moved", "rounded")]
    rounded_drop = [v for v, (k, _) in dropped_kind.items() if k == "rounded"]
    intro_kind = {v: E.classify_fact_change(case["blocks"], blocks, "date", v) for v in diff["introduced"]}
    rounded_add = [v for v, (k, _) in intro_kind.items() if k == "rounded"]
    unsourced_add = [v for v, (k, _) in intro_kind.items() if k != "rounded"]
    voice_src, voice_dst = E.voice_profile(case["blocks"]), E.voice_profile(blocks)
    body = " ".join(E.block_text(k, b) for k, b in blocks)
    chars = max(1, E.doc_len(blocks))
    codes = [i["code"] for i in review["issues"]]
    style_hits = [c for c in codes if c in STYLE_CODES]
    paragraphs = [len(E.plain(v)) for k, v in blocks if k == "p"]
    sentences = [len(E.plain(s)) for k, v in blocks if k == "p" for s in E._sentence_list(v)]
    promises = review["promise"]
    count_promises = [p for p in promises if p["kind"] in ("count", "number", "object")]
    gains = review["section_gain"]
    gains = [g for g in gains if g["chars"] >= 80]
    gate = R.build_preview_gate(text) if hasattr(R, "build_preview_gate") else None

    # Gate 1/2：直接走真实渲染路径（不写文件）
    m1, _s1 = check(R.render(text)[3])
    m2, _s2 = R.compose_gate(meta, blocks, base=str(ROOT / "evaluation" / "cases"), key=R.render(text)[0])

    metrics = {
        "chars": E.doc_len(blocks),
        "h2": sum(1 for k, _ in blocks if k == "h2"),
        "sections": len(gains),
        "sections_without_new_facts": sum(1 for g in gains if g["new_fact_count"] == 0 and not g["quoted"]),
        "new_facts_per_section": round(sum(g["new_fact_count"] for g in gains) / len(gains), 2) if gains else 0,
        "unknown_marked": bool(re.search(r"尚不清楚|尚不能|尚未|未确认|不能确认|无法确认|未知|未披露|不得而知|待确认",
                                         body)) or any(k == "unknown" for k, _ in blocks),
        "fact_preserved": len(diff["preserved"]),
        "fact_source_units": diff["source_units"],
        "fact_preserved_ratio": round(len(diff["preserved"]) / diff["source_units"], 3) if diff["source_units"] else 1.0,
        "facts_introduced": unsourced_add,
        "facts_dropped": lost,
        "facts_moved_to_block": moved,
        "facts_rounded": rounded_drop + rounded_add,
        "quotes_added": diff["introduced_quotes"],
        "qualifier_changes": len(diff["qualifier_changes"]),
        "style_clue_count": len(style_hits),
        "style_clues_per_1000": round(len(style_hits) / chars * 1000, 2),
        "style_clue_codes": sorted(set(style_hits)),
        "title_promise_total": len(count_promises),
        "title_promise_unfulfilled": [p["promise"] for p in count_promises if p["status"] in ("absent", "mismatch")],
        "avg_sentence_chars": round(statistics.fmean(sentences), 1) if sentences else 0,
        "sentence_stdev": round(statistics.pstdev(sentences), 2) if len(sentences) > 1 else 0,
        "max_paragraph_chars": max(paragraphs) if paragraphs else 0,
        "voice_marks": voice_dst["marks"],
        "voice_retention": {k: (round(voice_dst["marks"][k] / v, 2) if v else None)
                            for k, v in voice_src["marks"].items() if v},
        "gate1_must": len(m1), "gate2_must": len(m2),
        "gate_pass": not m1 and not m2,
        "must": [f"{i['code']}@{i['location']}" for i in review["issues"] if i["severity"] == "must"],
        "decision_chain_missing": [s["step"] for s in review["decision_chain"]["steps"] if s["status"] == "MISSING"],
    }
    metrics["_gate"] = gate
    metrics.pop("_gate")
    return metrics


def report(run_dir, cases):
    run_dir = Path(run_dir)
    meta = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    rows, per_type = [], {}
    for name, case in cases.items():
        for n in range(1, meta["repeats"] + 1):
            path = run_dir / name / f"run-{n}.md"
            if not path.is_file():
                continue
            m = measure(path.read_text(encoding="utf-8"), case)
            m.update({"case": name, "repeat": n})
            rows.append(m)
            per_type.setdefault(case["resolved_type"], []).append(m)

    def agg(values):
        values = [v for v in values if v is not None]
        if not values:
            return "—"
        if len(values) == 1:
            return f"{values[0]:.2f}"
        return f"{statistics.fmean(values):.2f} ± {statistics.pstdev(values):.2f}"

    summary = []
    for type_key in TYPES:
        group = per_type.get(type_key, [])
        if not group:
            continue
        summary.append({
            "type": type_key,
            "n": len(group),
            "chars": agg([m["chars"] for m in group]),
            "gate_pass": sum(1 for m in group if m["gate_pass"]),
            "style_clues_per_1000": agg([m["style_clues_per_1000"] for m in group]),
            "fact_preserved_ratio": agg([m["fact_preserved_ratio"] for m in group]),
            "facts_introduced_unsourced": sum(len(m["facts_introduced"]) for m in group),
            "facts_reformatted": sum(len(m["facts_moved_to_block"]) + len(m["facts_rounded"]) for m in group),
            "unknown_marked": sum(1 for m in group if m["unknown_marked"]),
            "title_promise_unfulfilled": sum(len(m["title_promise_unfulfilled"]) for m in group),
            "new_facts_per_section": agg([m["new_facts_per_section"] for m in group]),
            "sections_without_new_facts": sum(m["sections_without_new_facts"] for m in group),
            "sentence_stdev": agg([m["sentence_stdev"] for m in group]),
            "max_paragraph_chars": agg([m["max_paragraph_chars"] for m in group]),
        })

    # 重复之间的稳定性：同一 case 三次输出字数的极差与相似度，用来说明「可复现」到什么程度。
    stability = []
    for name in {r["case"] for r in rows}:
        group = sorted([r for r in rows if r["case"] == name], key=lambda r: r["repeat"])
        if len(group) < 2:
            continue
        shingles = [E._shingles((run_dir / name / f"run-{r['repeat']}.md").read_text(encoding="utf-8")) for r in group]
        sims = [round(E._jaccard(a, b), 3) for i, a in enumerate(shingles) for b in shingles[i + 1:]]
        chars = [r["chars"] for r in group]
        stability.append({"case": name, "n": len(group), "chars_min": min(chars), "chars_max": max(chars),
                          "chars_range": max(chars) - min(chars), "pairwise_similarity": sims,
                          "mean_similarity": round(statistics.fmean(sims), 3)})
    return meta, rows, summary, stability


def write_report(run_dir, cases, out):
    meta, rows, summary, stability = report(run_dir, cases)
    lines = ["# 六类文章受控评估报告（自动生成）", "",
             f"- 运行目录：`{Path(run_dir).name}`",
             f"- 模型标识：`{meta['model']}`（由执行者声明，运行器无法验证）",
             f"- 采样参数：temperature={meta['temperature']}（其余参数不可钉住者已在 run.json 的 declared_limits 里写明）",
             f"- 每类重复次数：{meta['repeats']}",
             f"- 输入与提示词指纹：`{meta['manifest_sha256'][:32]}…`",
             f"- 运行状态：{meta['status']}" + (f"；问题：{meta['problems']}" if meta["problems"] else ""),
             "", "## 证据分级", "",
             "| 级别 | 内容 | 状态 |", "|---|---|---|",
             "| automated | 标题兑现台账、事实字面保留、文风线索密度、逐节信息增量、声音形态、Gate 1/2 | 本报告表格，可复算 |",
             "| model_self | 模型对自己稿件的判断（是否更好、哪里更好） | UNVERIFIED（本报告不采用自评分） |",
             "| human | 独立盲评、逐项事实核真、审美与真机验收 | UNVERIFIED（见 `blind/` 与 RESULTS.md） |",
             "", "## 按类型汇总（n = 该类全部重复）", "",
             "| 类型 | n | 字数 | Gate 通过 | 文风线索/千字 | 事实保留率 | 无源新增 | 搬进块内/概括 | 标明未知 | 未兑现承诺 | 每节新事实 | 无新事实章节 | 句长标准差 | 最长段 |",
             "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for s in summary:
        lines.append(f"| {s['type']} | {s['n']} | {s['chars']} | {s['gate_pass']}/{s['n']} | {s['style_clues_per_1000']} | "
                     f"{s['fact_preserved_ratio']} | {s['facts_introduced_unsourced']} | {s['facts_reformatted']} | "
                     f"{s['unknown_marked']}/{s['n']} | "
                     f"{s['title_promise_unfulfilled']} | {s['new_facts_per_section']} | {s['sections_without_new_facts']} | "
                     f"{s['sentence_stdev']} | {s['max_paragraph_chars']} |")
    lines += ["", "### 怎么读这张表", "",
              "- **文风线索/千字**：机器命中的 AI 腔/模板/复读线索密度。命中不等于写得差，但密度越高越需要通读复核。",
              "- **事实保留率**：原稿字面事实单元（数字/日期/链接）在改稿中仍在的比例。它是**字面**保留，不是核真。",
              "- **无源新增**：改稿新增、附近没有来源的事实单元个数。任何 >0 都需要逐项回源。",
              "- **搬进块内 / 精度概括**：数值被搬进 data/bars 块（单位写在块标题），或只在导语做年份概括。"
              "运行器把它们单列，不混算成「丢失」——否则一次排版决定会被读成事实损失。",
              "- **每节新事实**：逐节的新事实单元数；无数字的叙事节天然为 0，所以它只作为定位线索。",
              "- **句长标准差**：节奏是否只有一种句长；过小说明句子等长，读起来平。",
              "", "## 重复之间的稳定性（同一提示词、同一输入）", "",
              "| 样本 | n | 字数 min–max | 极差 | 两两相似度 | 平均相似度 |", "|---|---:|---|---:|---|---:|"]
    for s in stability:
        lines.append(f"| {s['case']} | {s['n']} | {s['chars_min']}–{s['chars_max']} | {s['chars_range']} | "
                     f"{'、'.join(str(x) for x in s['pairwise_similarity'])} | {s['mean_similarity']} |")
    lines += ["", "相似度是 3-gram Jaccard：高相似说明重复之间差别主要在同义改写，低相似说明生成不稳定。", "",
              "## 逐篇明细", "",
              "| 样本 | 次 | 字数 | Gate | 文风线索 | 事实保留 | 无源新增 | 未知 | 未兑现承诺 | 句长σ | 最长段 | 决策链缺环 |",
              "|---|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---|"]
    for r in sorted(rows, key=lambda x: (x["case"], x["repeat"])):
        lines.append(f"| {r['case']} | {r['repeat']} | {r['chars']} | {'PASS' if r['gate_pass'] else 'FAIL'} | "
                     f"{r['style_clue_count']} | {r['fact_preserved_ratio']} | {len(r['facts_introduced'])} | "
                     f"{'是' if r['unknown_marked'] else '否'} | {len(r['title_promise_unfulfilled'])} | "
                     f"{r['sentence_stdev']} | {r['max_paragraph_chars']} | {'、'.join(r['decision_chain_missing']) or '—'} |")
    lines += ["", "## 未验证（不得计作通过）", "",
              "- 模型自评：本报告不采集、不呈现，避免用自我评分充当质量证据。",
              "- 独立外部盲评：需第三方按 `blind/` 表单回填后才成立；此前为 UNVERIFIED。",
              "- 逐项第二来源事实核真：运行器只比字面，不核真。",
              "- 微信真机与客户端清洗：与本文档无关，另见 `evaluation/RESULTS.md`。", ""]
    Path(out).write_text("\n".join(lines), encoding="utf-8")
    return summary, stability


def blind_packet(run_dir, cases, out_dir, key_file, seed="reviewer-01"):
    """生成 A/B 盲评包：原稿与一次改稿随机左右，答案 key 单独存放。"""
    import random
    out_dir, key = Path(out_dir), Path(key_file)
    out_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    mapping = {}
    for i, (name, case) in enumerate(sorted(cases.items()), 1):
        run = Path(run_dir) / name / "run-1.md"
        if not run.is_file():
            continue
        texts = [case["text"], run.read_text(encoding="utf-8")]
        order = [0, 1] if rng.random() < .5 else [1, 0]     # order[k] = 标签 A/B 背后的稿子位置
        folder = out_dir / f"{i:02d}-{name}"
        folder.mkdir(parents=True, exist_ok=True)
        for label, pos in zip(("A", "B"), order):
            (folder / f"{label}.md").write_text(texts[pos], encoding="utf-8")
        mapping[folder.name] = {"A": "original" if order[0] == 0 else "edited",
                                "B": "original" if order[1] == 0 else "edited",
                                "type": case["resolved_type"],
                                "sizes": {"A": len(texts[order[0]]), "B": len(texts[order[1]])}}
        (folder / "FORM.md").write_text(
            f"""# 盲评表单 · {folder.name}

两份稿件 A / B 针对同一原文；请**不要**猜测哪份是机器改的，只回答下面的问题。

| 维度 | 更符合（A / B / 无差别） | 依据（引用原文片段） |
|---|---|---|
| 标题承诺兑现 |  |  |
| 信息增量（读完多知道什么） |  |  |
| 论证/结构清晰度 |  |  |
| 事实与限定的保护 |  |  |
| 作者声音 |  |  |
| 手机端可读性 |  |  |
| 总体偏好 |  |  |

最后一句：如果只能发表一份，你选哪一份，为什么？
""", encoding="utf-8")
    key.write_text(json.dumps({"seed": seed, "mapping": mapping,
                               "note": "答案 key 必须与评审目录分开存放，评审结束后再打开。"},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    return mapping


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--manifest", action="store_true")
    ap.add_argument("--record", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--blind", action="store_true")
    ap.add_argument("--run-dir", default=str(DEFAULT_RUNS / "in-session-v7"))
    ap.add_argument("--model", default="unspecified")
    ap.add_argument("--temperature", default="unspecified")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--notes", default="")
    ap.add_argument("--out", default=str(ROOT / "evaluation" / "model-eval" / "REPORT.md"))
    ap.add_argument("--key", default="/tmp/wechat-blind-key.json")
    args = ap.parse_args()
    cases = load_cases()

    if args.list:
        print(f"{'case':10s} {'declared_type':13s} {'type_prompt'}")
        for name, case in cases.items():
            print(f"{name:10s} {case['declared_type']:13s} prompts/type-{case['resolved_type']}.md")
        return 0
    if args.manifest:
        data = manifest(cases)
        Path(args.run_dir).mkdir(parents=True, exist_ok=True)
        (Path(args.run_dir) / "manifest.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(data["cases"], ensure_ascii=False, indent=2))
        return 0
    if args.record:
        payload = record(args.run_dir, args.model, args.temperature, args.repeats, cases, args.notes)
        print(json.dumps({k: payload[k] for k in ("status", "problems", "repeats", "model")},
                         ensure_ascii=False, indent=2))
        return 0 if payload["status"] == "COMPLETE" else 1
    if args.report:
        summary, stability = write_report(args.run_dir, cases, args.out)
        print(f"报告 → {args.out}（{len(summary)} 类 · {len(stability)} 个稳定性样本）")
        return 0
    if args.blind:
        mapping = blind_packet(args.run_dir, cases, Path(args.out).parent / "blind", args.key)
        print(f"盲评包 → {Path(args.out).parent / 'blind'}（{len(mapping)} 组）；key → {args.key}")
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
