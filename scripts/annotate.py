#!/usr/bin/env python3
"""对结构标注做确定性校验并渲染拆解卡。

输入：
  blocks.json     parse_transcript.py 产出的句块列表
  annotation.json Agent 产出的结构标注（每段 role/start/end/evidence/reason）
输出：
  拆解卡 Markdown（-o）与结构化 JSON（--json）

确定性校验（不打分，只查合法性与一致性）：
  1. 时间轴合法：end > start、无重叠、单调递增、均在全片时长内；
  2. 覆盖率：标注段覆盖全片时长的比例，未覆盖区间如实列出；
  3. 四段齐缺：hook/build/twist/cta 缺哪个如实标注，不强行补段；
  4. 边界对齐：段边界是否切开了句块（切开处逐条列出，供人工复核）；
  5. 例句核对：evidence 是否真的出现在对应时间段内。

校验不通过（时间轴非法等）以退出码 3 结束，不输出任何半成品卡片。
红线：不给内容打分、不生成或改写文案。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VERSION = "0.2.0"

ROLES = ("hook", "build", "twist", "cta")
ROLE_CN = {"hook": "钩子", "build": "留人", "twist": "转折", "cta": "转化"}
EPS = 1e-6
COVERAGE_WARN = 0.6  # 覆盖率低于 60% 时提示可能有漏标（仅提示，不拦截）


class ValidationError(ValueError):
    pass


def load_json(path: Path, label: str) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"{label} 不是合法 JSON：{exc.msg}（第 {exc.lineno} 行）") from exc
    if not isinstance(data, dict):
        raise ValidationError(f"{label} 顶层必须是 JSON 对象")
    return data


def norm_text(text: str) -> str:
    """归一化：去掉所有空白后比较（ASR 空格不稳定）。"""
    return "".join(text.split())


def fmt_clock(seconds: float) -> str:
    total = round(max(seconds, 0.0), 1)
    minutes = int(total // 60)
    rest = total - minutes * 60
    return f"{minutes:02d}:{rest:04.1f}"


def validate_segments(annotation: dict, duration: float) -> list[dict]:
    segments = annotation.get("segments")
    if not isinstance(segments, list) or not segments:
        raise ValidationError("annotation.json 缺少 segments（结构段列表）或其为空")
    errors: list[str] = []
    cleaned: list[dict] = []
    prev_end: float | None = None        # 上一段（用于单调性报告）
    last_valid_end: float | None = None  # 最近一个时间轴合法段的 end（跳过非法段也要查重叠）
    for index, seg in enumerate(segments, 1):
        role = seg.get("role")
        if role not in ROLES:
            errors.append(
                f"第 {index} 段 role 非法：{role!r}（只允许 {'/'.join(ROLES)}，"
                f"分别对应 钩子/留人/转折/转化）"
            )
            cleaned.append({"index": index, "role": role})
            prev_end = None
            continue
        start, end = seg.get("start"), seg.get("end")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) \
                or isinstance(start, bool) or isinstance(end, bool):
            errors.append(f"第 {index} 段（{ROLE_CN[role]}）start/end 必须是数字")
            cleaned.append({"index": index, "role": role})
            prev_end = None
            continue
        start, end = float(start), float(end)
        errors_before = len(errors)
        if end <= start + EPS:
            errors.append(
                f"第 {index} 段（{ROLE_CN[role]}）时间轴非法：end {end:.1f}s ≤ start {start:.1f}s"
            )
            cleaned.append({"index": index, "role": role})
            prev_end = None
            continue
        if start < -EPS:
            errors.append(f"第 {index} 段（{ROLE_CN[role]}）start 为负数：{start:.1f}s")
        if duration is not None and end > duration + 0.05:
            errors.append(
                f"第 {index} 段（{ROLE_CN[role]}）超出转写时长 {duration:.1f}s：end {end:.1f}s"
            )
        if prev_end is not None and start < prev_end - EPS:
            errors.append(
                f"第 {index} 段（{ROLE_CN[role]}）与前一段重叠或乱序："
                f"start {start:.1f}s < 前一段 end {prev_end:.1f}s"
            )
        elif last_valid_end is not None and start < last_valid_end - EPS:
            errors.append(
                f"第 {index} 段（{ROLE_CN[role]}）与前面的段重叠："
                f"start {start:.1f}s < 最近合法段 end {last_valid_end:.1f}s"
            )
        cleaned.append({
            "index": index, "role": role, "start": round(start, 2), "end": round(end, 2),
            "evidence": str(seg.get("evidence", "")).strip(),
            "reason": str(seg.get("reason", "")).strip(),
        })
        prev_end = end
        if len(errors) == errors_before:
            last_valid_end = end if last_valid_end is None else max(last_valid_end, end)
    if errors:
        raise ValidationError("时间轴校验失败：\n" + "\n".join(f"- {e}" for e in errors))
    return cleaned


def block_text_in_range(blocks: list[dict], start: float, end: float) -> str:
    parts = []
    for block in blocks:
        b_start, b_end = block.get("start"), block.get("end")
        if b_start is None or b_end is None:
            continue
        if b_end > start + EPS and b_start < end - EPS:
            parts.append(block["text"])
    return norm_text("".join(parts))


def find_cut_blocks(blocks: list[dict], start: float, end: float) -> list[dict]:
    cuts = []
    for block in blocks:
        b_start, b_end = block.get("start"), block.get("end")
        if b_start is None or b_end is None:
            continue
        for boundary, side in ((start, "start"), (end, "end")):
            if b_start + 0.02 < boundary < b_end - 0.02:
                cuts.append({"block_i": block["i"], "boundary": round(boundary, 2), "edge": side})
    return cuts


def build_card(annotation: dict, blocks_doc: dict, segments: list[dict]) -> dict:
    if not blocks_doc.get("timed") or blocks_doc.get("duration_s") is None:
        raise ValidationError(
            "该转写稿无时间码（纯文本），无法做时间轴标注："
            "请改用 SRT 转写，或先为文本补齐时间戳"
        )
    blocks = blocks_doc["blocks"]
    duration = blocks_doc.get("duration_s")
    timed = bool(blocks_doc.get("timed"))

    for seg in segments:
        if "start" not in seg:  # 前面校验已抛错，这里只为类型完整
            raise ValidationError(f"第 {seg['index']} 段缺少合法时间轴")
        seg["duration_s"] = round(seg["end"] - seg["start"], 2)
        seg["ratio"] = round(seg["duration_s"] / duration, 4) if duration else None
        if timed and seg["evidence"]:
            seg["evidence_ok"] = norm_text(seg["evidence"]) in block_text_in_range(
                blocks, seg["start"], seg["end"]
            )
        elif seg["evidence"]:
            seg["evidence_ok"] = norm_text(seg["evidence"]) in norm_text(
                "".join(b["text"] for b in blocks)
            )
        else:
            seg["evidence_ok"] = None
        seg["cut_blocks"] = find_cut_blocks(blocks, seg["start"], seg["end"]) if timed else []

    covered = sum(seg["duration_s"] for seg in segments)
    coverage = round(covered / duration, 4) if duration else None

    uncovered: list[dict] = []
    if timed:
        cursor = 0.0
        for seg in segments:
            if seg["start"] - cursor > 0.05:
                uncovered.append({"start": round(cursor, 2), "end": round(seg["start"], 2)})
            cursor = max(cursor, seg["end"])
        if duration - cursor > 0.05:
            uncovered.append({"start": round(cursor, 2), "end": round(duration, 2)})

    roles_present, roles_missing = [], []
    for role in ROLES:
        (roles_present if any(s["role"] == role for s in segments) else roles_missing).append(role)
    sequence = [s["role"] for s in segments]

    role_stats: dict[str, dict] = {}
    for role in ROLES:
        own = [s for s in segments if s["role"] == role]
        if not own:
            continue
        role_stats[role] = {
            "count": len(own),
            "duration_s": round(sum(s["duration_s"] for s in own), 2),
            "ratio": round(sum(s["duration_s"] for s in own) / duration, 4) if duration else None,
        }

    cut_total = sum(len(s["cut_blocks"]) for s in segments)
    evidence_total = sum(1 for s in segments if s["evidence"])
    evidence_hits = sum(1 for s in segments if s["evidence"] and s["evidence_ok"])

    return {
        "version": VERSION,
        "video_id": annotation.get("video_id", ""),
        "title": annotation.get("title", ""),
        "genre": annotation.get("genre", ""),
        "transcript": annotation.get("transcript", blocks_doc.get("source", "")),
        "timed": timed,
        "duration_s": duration,
        "block_count": len(blocks),
        "structure_pattern": "→".join(sequence),
        "roles_present": roles_present,
        "roles_missing": roles_missing,
        "segments": segments,
        "role_stats": role_stats,
        "coverage": coverage,
        "uncovered": uncovered,
        "cut_block_count": cut_total,
        "evidence_total": evidence_total,
        "evidence_hits": evidence_hits,
        "checks": {
            "timeline_legal": True,
            "coverage_ok": coverage is None or coverage >= COVERAGE_WARN,
            "alignment_clean": cut_total == 0,
            "evidence_all_found": evidence_total == 0 or evidence_hits == evidence_total,
        },
        "structure_note": str(annotation.get("structure_note", "")).strip(),
    }


def render_card(card: dict) -> str:
    lines = [
        f"# 拆解卡：{card['title'] or card['video_id']}",
        "",
        f"- 稿件 ID：{card['video_id']} ｜ 题材：{card['genre'] or '未标注'}"
        f" ｜ 稿源：{card['transcript']}",
        f"- 全长 {card['duration_s']}s ｜ 句块 {card['block_count']} 个"
        f" ｜ 标注段 {len(card['segments'])} 段"
        f" ｜ 段序列：{role_chain(card['structure_pattern'])}",
        "",
        "## 结构时间轴",
        "",
        "| # | 角色 | 时间 | 时长 | 占比 | 归类理由 | 例句 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for seg in card["segments"]:
        time_range = f"{fmt_clock(seg['start'])}–{fmt_clock(seg['end'])}"
        ratio = f"{seg['ratio'] * 100:.1f}%" if seg["ratio"] is not None else "—"
        evidence = f"「{seg['evidence']}」" if seg["evidence"] else "—"
        lines.append(
            f"| {seg['index']} | {ROLE_CN[seg['role']]} {seg['role']} | {time_range} "
            f"| {seg['duration_s']}s | {ratio} | {seg['reason'] or '—'} | {evidence} |"
        )
    lines.append("")
    if card["role_stats"]:
        stats = " ｜ ".join(
            f"{ROLE_CN[role]} {card['role_stats'][role]['ratio'] * 100:.1f}%"
            for role in ROLES if role in card["role_stats"]
        )
        lines.append(f"各角色占比：{stats}")
        lines.append("")

    lines += ["## 校验", ""]
    if card["timed"]:
        lines.append("- 时间轴：合法（无重叠、单调递增、均在全片范围内）")
        uncovered = card["uncovered"]
        if uncovered:
            detail = "；".join(
                f"{fmt_clock(u['start'])}–{fmt_clock(u['end'])}" for u in uncovered
            )
            lines.append(f"- 覆盖率：{card['coverage'] * 100:.1f}%（未覆盖区间：{detail}）")
        else:
            lines.append(f"- 覆盖率：{card['coverage'] * 100:.1f}%（全片覆盖）")
        if not card["checks"]["coverage_ok"]:
            lines.append(f"- 覆盖率提示：低于 {COVERAGE_WARN * 100:.0f}%，可能有漏标，请复核")
        if card["cut_block_count"]:
            lines.append(f"- 边界对齐：段边界切开句块 {card['cut_block_count']} 处（边界落在句块中间，请复核是否贴合句块边界）")
        else:
            lines.append("- 边界对齐：段边界与句块边界对齐（0 处错位）")
    else:
        lines.append("- 转写稿无时间码：跳过时间轴校验，占比按字数估算（本卡仅支持句块级结构参考）")
    lines.append(
        f"- 例句核对：{card['evidence_hits']}/{card['evidence_total']} 在对应时间段内命中"
        if card["evidence_total"] else "- 例句核对：未提供例句"
    )
    if card["evidence_total"] and card["evidence_hits"] < card["evidence_total"]:
        misses = "；".join(
            f"第 {s['index']} 段（{ROLE_CN[s['role']]}）「{s['evidence']}」"
            for s in card["segments"] if s["evidence"] and not s["evidence_ok"]
        )
        lines.append(f"- 例句核对提示：以下例句未在其所标时间段内找到，请修正标注或例句：{misses}")
    parts = []
    for role in ROLES:
        if role in card["roles_present"]:
            parts.append(f"{ROLE_CN[role]} ✓")
        else:
            parts.append(f"{ROLE_CN[role]} ✗（未检出，如实标注）")
    lines.append("- 四段齐缺：" + " ｜ ".join(parts))
    lines.append("")

    lines += [
        "## 结构总评（Agent 撰写位）",
        "",
        card["structure_note"] or "（未填写）",
        "",
        "## 边界说明",
        "",
        "- 段边界是主观判定：同一条稿子两次标注的转折点可能不同，本卡时间轴只代表本次标注，占比仅供参考。",
        "- 本工具只做结构标注与模板沉淀：不打分、不评估内容质量、不预测流量、不生成或改写文案。",
        "- 例句仅用于佐证结构功能；写新稿时请替换为你的原创内容，不要照抄他人文案。",
        f"- 版本 {VERSION}（viral-structure-teardown）。",
        "",
    ]
    return "\n".join(lines)


def role_chain(pattern: str) -> str:
    return "→".join(ROLE_CN.get(role, role) for role in pattern.split("→") if role)


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("blocks", type=Path, help="parse_transcript.py 产出的句块 JSON")
    parser.add_argument("annotation", type=Path, help="Agent 产出的标注 JSON")
    parser.add_argument("-o", "--output", type=Path, help="拆解卡 Markdown 输出路径")
    parser.add_argument("--json", type=Path, help="结构化 JSON 输出路径（供 distill 聚合）")
    args = parser.parse_args(argv)

    for path, label in ((args.blocks, "blocks.json"), (args.annotation, "annotation.json")):
        if not path.is_file():
            print(f"输入文件不存在：{path}", file=sys.stderr)
            return 2
    try:
        blocks_doc = load_json(args.blocks, "blocks.json")
        annotation = load_json(args.annotation, "annotation.json")
        if not isinstance(blocks_doc.get("blocks"), list):
            raise ValidationError("blocks.json 缺少 blocks 列表（请先用 parse_transcript.py 解析）")
        if not blocks_doc.get("timed"):
            raise ValidationError(
                "该转写稿无时间码（纯文本），无法做时间轴标注："
                "请改用 SRT 转写，或先为文本补齐时间戳"
            )
        if blocks_doc.get("duration_s") is None:
            raise ValidationError("blocks.json 缺少 duration_s（全片时长）")
        segments = validate_segments(annotation, float(blocks_doc["duration_s"]))
        card = build_card(annotation, blocks_doc, segments)
    except ValidationError as exc:
        print(f"校验失败（exit 3）：{exc}", file=sys.stderr)
        return 3

    rendered = render_card(card)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

    missing = [ROLE_CN[role] for role in card["roles_missing"]]
    complete = "四段齐全（" + role_chain(card["structure_pattern"]) + "）" if not missing \
        else "缺 " + "、".join(missing) + "（已如实标注）"
    print(f"校验通过：时间轴合法 · 覆盖率 {card['coverage'] * 100:.1f}% · {complete}")
    print(
        f"拆解卡已生成：{args.output if args.output else 'stdout'}"
        f"（边界错位 {card['cut_block_count']} 处 · 例句 "
        f"{card['evidence_hits']}/{card['evidence_total']} 命中）"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
