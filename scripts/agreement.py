#!/usr/bin/env python3
"""两份结构标注的一致性：把「段边界是主观判定」变成可量化的数字。

输入：同一份 blocks.json + 两份 annotation.json（例如 Agent 两次独立标注，或 Agent 与人工各标一次）。
输出：一致性报告 Markdown（-o）与 JSON（--json）。

口径（全部确定性，按句块计）：
  1. 角色一致率：每个句块按其时间中点归入所在段的角色（未覆盖记 none），两份标注逐块比对；
  2. Cohen's kappa：扣除随机一致后的角色一致度（Cohen 1960）；分档参照 Landis & Koch (1977)，
     该分档是经验约定而非统计检验，只作阅读参照；
  3. 边界 P/R/F1：段起点落在哪个句块，以标注 A 为参照、允许 ±1 个句块的近似命中；
  4. WindowDiff（Pevzner & Hearst 2002）：窗口 k 取标注 A 平均段长（句块数）的一半，
     越小越一致（0 = 边界完全一致）；
  5. 段序列是否相同、配对边界的秒数差。

不打分、不判谁对：一致性低说明这条稿子的段边界本身有歧义，需要人工复核，而不是某一方错了。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import annotate as an  # noqa: E402

VERSION = an.VERSION
BOUNDARY_TOLERANCE_BLOCKS = 1


def block_labels(blocks: list[dict], segments: list[dict]) -> tuple[list[str], list[int]]:
    """每个句块的角色与所在段序号（按句块时间中点归属；未覆盖为 none / -1）。"""
    labels, seg_ids = [], []
    for block in blocks:
        mid = (block["start"] + block["end"]) / 2
        hit = next(
            (k for k, seg in enumerate(segments) if seg["start"] - an.EPS <= mid < seg["end"] + an.EPS),
            None,
        )
        labels.append(segments[hit]["role"] if hit is not None else "none")
        seg_ids.append(hit if hit is not None else -1)
    return labels, seg_ids


def boundaries(seg_ids: list[int]) -> list[int]:
    """段起点所在的句块下标（不含第 0 块）。"""
    return [i for i in range(1, len(seg_ids)) if seg_ids[i] != seg_ids[i - 1]]


def cohen_kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if n == 0:
        return None
    observed = sum(1 for x, y in zip(a, b) if x == y) / n
    cats = set(a) | set(b)
    expected = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    if abs(1 - expected) < 1e-12:
        return 1.0 if observed == 1 else None
    return round((observed - expected) / (1 - expected), 4)


def landis_koch(kappa: float | None) -> str:
    if kappa is None:
        return "无法计算"
    if kappa < 0:
        return "差（poor）"
    for upper, label in ((0.2, "轻微（slight）"), (0.4, "一般（fair）"),
                         (0.6, "中等（moderate）"), (0.8, "较强（substantial）")):
        if kappa <= upper:
            return label
    return "几乎完全一致（almost perfect）"


def match_boundaries(ref: list[int], hyp: list[int], tol: int) -> list[tuple[int, int]]:
    """贪心配对：每个参照边界配最近且未被用过的假设边界（距离 ≤ tol）。"""
    used: set[int] = set()
    pairs = []
    for r in ref:
        candidates = sorted((abs(h - r), h) for h in hyp if h not in used and abs(h - r) <= tol)
        if candidates:
            h = candidates[0][1]
            used.add(h)
            pairs.append((r, h))
    return pairs


def window_diff(ref: list[int], hyp: list[int], n_blocks: int, k: int) -> float | None:
    ref_vec = [1 if i in ref else 0 for i in range(n_blocks)]
    hyp_vec = [1 if i in hyp else 0 for i in range(n_blocks)]
    windows = n_blocks - k + 1
    if windows <= 0:
        return None
    errors = sum(
        1 for i in range(windows)
        if sum(ref_vec[i:i + k]) != sum(hyp_vec[i:i + k])
    )
    return round(errors / windows, 4)


def compare(blocks_doc: dict, ann_a: dict, ann_b: dict) -> dict:
    if not blocks_doc.get("timed") or blocks_doc.get("duration_s") is None:
        raise an.ValidationError("该转写稿无时间码，无法比较时间轴标注")
    duration = float(blocks_doc["duration_s"])
    seg_a = an.validate_segments(ann_a, duration)
    seg_b = an.validate_segments(ann_b, duration)
    blocks = [b for b in blocks_doc["blocks"] if b.get("start") is not None]
    if not blocks:
        raise an.ValidationError("blocks.json 没有带时间的句块")
    lab_a, ids_a = block_labels(blocks, seg_a)
    lab_b, ids_b = block_labels(blocks, seg_b)
    n = len(blocks)
    agree = sum(1 for x, y in zip(lab_a, lab_b) if x == y)
    kappa = cohen_kappa(lab_a, lab_b)
    bound_a, bound_b = boundaries(ids_a), boundaries(ids_b)
    pairs = match_boundaries(bound_a, bound_b, BOUNDARY_TOLERANCE_BLOCKS)
    precision = len(pairs) / len(bound_b) if bound_b else (1.0 if not bound_a else 0.0)
    recall = len(pairs) / len(bound_a) if bound_a else (1.0 if not bound_b else 0.0)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    seg_lengths = [ids_a.count(k) for k in sorted(set(ids_a)) if k >= 0]
    mean_len = sum(seg_lengths) / len(seg_lengths) if seg_lengths else n
    k = max(2, round(mean_len / 2))
    wd = window_diff(bound_a, bound_b, n, k)
    disagreements = [
        {"block_i": blocks[i]["i"], "start": blocks[i]["start"], "end": blocks[i]["end"],
         "a": lab_a[i], "b": lab_b[i]}
        for i in range(n) if lab_a[i] != lab_b[i]
    ]
    offsets = [
        round(blocks[h]["start"] - blocks[r]["start"], 2) for r, h in pairs
    ]
    return {
        "version": VERSION,
        "transcript": blocks_doc.get("source", ""),
        "block_count": n,
        "a": {"video_id": ann_a.get("video_id", ""), "pattern": "→".join(s["role"] for s in seg_a)},
        "b": {"video_id": ann_b.get("video_id", ""), "pattern": "→".join(s["role"] for s in seg_b)},
        "same_sequence": [s["role"] for s in seg_a] == [s["role"] for s in seg_b],
        "label_agreement": round(agree / n, 4),
        "kappa": kappa,
        "kappa_band": landis_koch(kappa),
        "boundary": {
            "a_count": len(bound_a),
            "b_count": len(bound_b),
            "matched": len(pairs),
            "tolerance_blocks": BOUNDARY_TOLERANCE_BLOCKS,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "matched_offsets_s": offsets,
        },
        "window_diff": wd,
        "window_k": k,
        "disagreements": disagreements,
    }


def render(result: dict) -> str:
    b = result["boundary"]
    lines = [
        "# 标注一致性报告",
        "",
        f"- 稿源：{result['transcript']} ｜ 句块 {result['block_count']} 个",
        f"- 标注 A：{an.role_chain(result['a']['pattern'])}",
        f"- 标注 B：{an.role_chain(result['b']['pattern'])}"
        f"（段序列{'相同' if result['same_sequence'] else '不同'}）",
        "",
        "| 指标 | 数值 | 口径 |",
        "| --- | --- | --- |",
        f"| 角色一致率 | {result['label_agreement'] * 100:.1f}% | 逐句块比对角色 |",
        f"| Cohen's kappa | {result['kappa'] if result['kappa'] is not None else '—'} "
        f"| 扣除随机一致；Landis & Koch 分档：{result['kappa_band']}（经验约定，仅作参照） |",
        f"| 边界 P / R / F1 | {b['precision']:.2f} / {b['recall']:.2f} / {b['f1']:.2f} "
        f"| 以 A 为参照，允许 ±{b['tolerance_blocks']} 个句块；A {b['a_count']} 个边界、B {b['b_count']} 个、配对 {b['matched']} 个 |",
        f"| WindowDiff | {result['window_diff'] if result['window_diff'] is not None else '—'} "
        f"| 窗口 k={result['window_k']} 个句块；0 为边界完全一致，越大越分歧 |",
    ]
    if b["matched_offsets_s"]:
        offsets = "、".join(f"{x:+.1f}s" for x in b["matched_offsets_s"])
        lines.append(f"| 配对边界秒差（B−A） | {offsets} | 近似命中的边界差了多少秒 |")
    lines += ["", "## 分歧句块", ""]
    if result["disagreements"]:
        lines += ["| 句块 | 时间 | A | B |", "| --- | --- | --- | --- |"]
        for d in result["disagreements"]:
            lines.append(
                f"| {d['block_i']} | {an.fmt_clock(d['start'])}–{an.fmt_clock(d['end'])} "
                f"| {an.ROLE_CN.get(d['a'], d['a'])} | {an.ROLE_CN.get(d['b'], d['b'])} |"
            )
    else:
        lines.append("无：两份标注逐句块角色一致。")
    lines += [
        "",
        "## 怎么读",
        "",
        "- 一致性低说明这条稿子的段边界本身有歧义，应把分歧句块交给人工复核，不代表某一方错了。",
        "- 本报告只比较结构标注，不评价内容质量、不打分。",
        f"- 版本 {VERSION}（viral-structure-teardown）。",
        "",
    ]
    return "\n".join(lines)


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("blocks", type=Path, help="parse_transcript.py 产出的句块 JSON")
    parser.add_argument("annotation_a", type=Path, help="标注 A（参照）")
    parser.add_argument("annotation_b", type=Path, help="标注 B")
    parser.add_argument("-o", "--output", type=Path, help="一致性报告 Markdown 输出路径")
    parser.add_argument("--json", type=Path, help="一致性 JSON 输出路径")
    args = parser.parse_args(argv)
    for path in (args.blocks, args.annotation_a, args.annotation_b):
        if not path.is_file():
            print(f"输入文件不存在：{path}", file=sys.stderr)
            return 2
    try:
        blocks_doc = an.load_json(args.blocks, "blocks.json")
        ann_a = an.load_json(args.annotation_a, "annotation A")
        ann_b = an.load_json(args.annotation_b, "annotation B")
        result = compare(blocks_doc, ann_a, ann_b)
    except an.ValidationError as exc:
        print(f"比较失败（exit 3）：{exc}", file=sys.stderr)
        return 3
    rendered = render(result)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    b = result["boundary"]
    print(
        f"一致性：角色 {result['label_agreement'] * 100:.1f}% · kappa {result['kappa']} "
        f"（{result['kappa_band']}）· 边界 F1 {b['f1']:.2f} · WindowDiff {result['window_diff']}",
        file=sys.stderr if not args.output else sys.stdout,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
