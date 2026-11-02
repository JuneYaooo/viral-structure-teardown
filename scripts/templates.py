#!/usr/bin/env python3
"""结构模板库：从多条拆解卡蒸馏可复用模板，并给新脚本期望落点。

子命令：
  distill  把多张拆解卡（annotate.py --json 产物）聚合为一个模板
           （段序列模式 + 每段占比区间 + 例句 + 题材标签）
  list     列出模板库里的全部模板
  show     查看单个模板详情
  apply    按目标时长给秒级期望落点：段边界取各支撑卡的中位数（节拍表式打点），
           并附观测范围；首段钩子的结束点按「绝对秒数」与「占比」取较小者
           （平台建议钩子放在前 3–6 秒，长视频不应按比例把钩子拉长）；
           目标时长超出样本时长范围、或支撑卡 < 3 张时如实提示。

模板只沉淀结构位置与句式功能：不打分、不收录整段文案、不做内容代写。
全部本地运行，零网络；同输入输出一致。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VERSION = "0.3.0"

ROLES = ("hook", "build", "twist", "cta")
ROLE_CN = {"hook": "钩子", "build": "留人", "twist": "转折", "cta": "转化"}
MAX_EXAMPLES_PER_POSITION = 3
COLD_START_CARDS = 3  # 支撑卡少于 3 张时，中位数就是个例值，必须提示冷启动

INTENT_MAP = {
    "hook": "AIDA-Attention",
    "build": "AIDA-Interest/Desire",
    "twist": "HSO-Story",
    "cta": "HSO-Offer",
}


class TemplateError(ValueError):
    pass


def load_card(path: Path) -> dict:
    try:
        card = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise TemplateError(f"{path} 不是合法 JSON：{exc.msg}（第 {exc.lineno} 行）") from exc
    if not isinstance(card, dict) or not card.get("segments"):
        raise TemplateError(f"{path} 不是拆解卡 JSON（缺少 segments），请先用 annotate.py --json 产出")
    if not card.get("duration_s"):
        raise TemplateError(f"{path} 缺少 duration_s，无法计算占比")
    for seg in card["segments"]:
        if seg.get("role") not in ROLES or seg.get("start") is None or seg.get("end") is None:
            raise TemplateError(f"{path} 存在不完整的时间段（缺 role/start/end）")
    return card


def sequence_of(card: dict) -> list[str]:
    return [seg["role"] for seg in card["segments"]]


def median(values: list[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    mid = n // 2
    return ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2


def stats(values: list[float], digits: int = 4) -> dict | None:
    if not values:
        return None
    return {
        "median": round(median(values), digits),
        "min": round(min(values), digits),
        "max": round(max(values), digits),
        "n": len(values),
    }


def dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        key = "".join(item.split())
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def distill(cards: list[dict], args) -> dict:
    durations = [card["duration_s"] for card in cards]
    sequences: dict[tuple[str, ...], int] = {}
    for card in cards:
        sequences[tuple(sequence_of(card))] = sequences.get(tuple(sequence_of(card)), 0) + 1
    ranked = sorted(sequences.items(), key=lambda kv: (-kv[1], len(kv[0]), kv[0]))
    primary = list(ranked[0][0])

    matching = [card for card in cards if sequence_of(card) == primary]
    positions = []
    for pos_index in range(len(primary)):
        role = primary[pos_index]
        starts, ends = [], []
        starts_s, ends_s = [], []
        functions: list[str] = []
        examples: list[str] = []
        for card in matching:
            duration = card["duration_s"]
            seg = card["segments"][pos_index]
            if seg["role"] != role:
                continue
            starts.append(round(seg["start"] / duration, 4))
            ends.append(round(seg["end"] / duration, 4))
            starts_s.append(seg["start"])
            ends_s.append(seg["end"])
            if seg.get("reason"):
                functions.append(seg["reason"])
            if seg.get("evidence"):
                examples.append(seg["evidence"])
        patterns: list[str] = []
        for card in matching:
            patterns.extend((card.get("patterns") or {}).get(role, []))
        positions.append({
            "position": pos_index + 1,
            "role": role,
            "ratio": [min(starts), max(ends)] if starts else None,
            "start_ratio": stats(starts),
            "end_ratio": stats(ends),
            "start_s": stats(starts_s, 2),
            "end_s": stats(ends_s, 2),
            "sample_cards": len(matching),
            "functions": dedupe_keep_order(functions)[:2],
            "example_lines": dedupe_keep_order(examples)[:MAX_EXAMPLES_PER_POSITION],
            "patterns": dedupe_keep_order(patterns)[:3],
        })

    role_ranges: dict[str, list[float]] = {}
    for role in ROLES:
        spans = [
            [round(seg["start"] / card["duration_s"], 4), round(seg["end"] / card["duration_s"], 4)]
            for card in cards for seg in card["segments"] if seg["role"] == role
        ]
        if spans:
            role_ranges[role] = [min(span[0] for span in spans), max(span[1] for span in spans)]

    genres: list[str] = []
    for card in cards:
        if card.get("genre"):
            genres.append(card["genre"])
    for extra in (args.genres or "").split(","):
        if extra.strip():
            genres.append(extra.strip())

    patterns_all = {role: [] for role in ROLES}
    for card in cards:
        for role, items in (card.get("patterns") or {}).items():
            if role in patterns_all:
                patterns_all[role].extend(items)

    return {
        "version": VERSION,
        "template_id": args.template_id,
        "name": args.name,
        "created": args.created,
        "source_cards": [card.get("video_id", "?") for card in cards],
        "card_count": len(cards),
        "genres": dedupe_keep_order(genres),
        "duration_range_s": [min(durations), max(durations)],
        "role_sequences": [
            {"sequence": list(seq), "count": count} for seq, count in ranked
        ],
        "primary_sequence": primary,
        "positions": positions,
        "role_ratio_ranges": role_ranges,
        "patterns": {role: dedupe_keep_order(items)[:3] for role, items in patterns_all.items()},
        "intent_map": INTENT_MAP,
        "red_lines": [
            "只沉淀结构位置与句式功能，不收录整段文案，不做内容代写",
            "不打分：不做流量预测与内容质量打分",
            "例句仅示范该段功能，套用时必须替换为原创内容",
        ],
    }


def render_template_md(template: dict) -> str:
    lines = [
        f"# 模板：{template['name']}（{template['template_id']}）",
        "",
        f"- 蒸馏自 {template['card_count']} 张拆解卡（{', '.join(template['source_cards'])}）",
        f"- 适用题材：{('、'.join(template['genres'])) or '未标注'}"
        f" ｜ 参考时长 {template['duration_range_s'][0]:.0f}–{template['duration_range_s'][1]:.0f}s",
        f"- 主段序列：{role_chain('→'.join(template['primary_sequence']))}",
        "",
        "## 段位与占比区间",
        "",
        "| 序 | 角色 | 起点（中位） | 终点（中位） | 观测包络 | 支撑卡数 | 功能 | 句式模式 | 例句参考 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for pos in template["positions"]:
        ratio = f"{pos['ratio'][0] * 100:.1f}%–{pos['ratio'][1] * 100:.1f}%" if pos["ratio"] else "—"
        examples = "；".join(f"「{line}」" for line in pos["example_lines"]) or "—"
        patterns = "；".join(pos["patterns"]) or "—"
        lines.append(
            f"| {pos['position']} | {ROLE_CN[pos['role']]} {pos['role']} "
            f"| {fmt_stat(pos.get('start_ratio'), pos.get('start_s'))} "
            f"| {fmt_stat(pos.get('end_ratio'), pos.get('end_s'))} | {ratio} "
            f"| {pos.get('sample_cards', '—')} "
            f"| {('；'.join(pos['functions'])) or '—'} | {patterns} | {examples} |"
        )
    cold = template["positions"] and min(p.get("sample_cards", 0) for p in template["positions"]) < COLD_START_CARDS
    lines += [
        "",
        "起点/终点取各支撑卡的中位数（括号内为绝对秒数中位）；观测包络为 [最早起点, 最晚终点]，"
        "样本扩充时只增不减。支撑卡数 = 与主段序列一致的拆解卡数。",
    ]
    if cold:
        lines.append(
            f"冷启动提示：支撑卡少于 {COLD_START_CARDS} 张，中位数即个例值，区间不代表同类爆款的真实波动。"
        )
    lines += [
        "",
        "## 段序列模式",
        "",
    ]
    for item in template["role_sequences"]:
        lines.append(f"- {' → '.join(ROLE_CN[r] for r in item['sequence'])}（{item['count']} 张卡）")
    lines += [
        "",
        "## 红线",
        "",
    ]
    for rule in template["red_lines"]:
        lines.append(f"- {rule}")
    lines.append(f"\n- 版本 {VERSION}（viral-structure-teardown）· 占比区间为合成样本蒸馏结果，边界主观，仅供参考")
    return "\n".join(lines) + "\n"


def fmt_stat(ratio_stat: dict | None, sec_stat: dict | None) -> str:
    if not ratio_stat:
        return "—"
    text = f"{ratio_stat['median'] * 100:.1f}%"
    if sec_stat:
        text += f"（{sec_stat['median']:.1f}s）"
    return text


def run_apply(template: dict, duration: float) -> dict:
    """段边界 = 各支撑卡中位占比 × 目标时长；首段钩子的终点取 min(绝对秒中位, 占比中位 × 时长)。

    旧模板（v0.2.0 及以前，无 start_ratio/end_ratio）退回包络换算并提示重新蒸馏。
    """
    positions = template["positions"]
    has_stats = bool(positions) and all(p.get("start_ratio") and p.get("end_ratio") for p in positions)
    warnings: list[str] = []
    landing = []
    hook_ratio_end = None
    if has_stats:
        bounds = [positions[0]["start_ratio"]["median"] * duration]
        for k, pos in enumerate(positions):
            end = pos["end_ratio"]["median"] * duration
            anchor = None
            if k == 0 and pos["role"] == "hook" and pos.get("end_s") and len(positions) > 1:
                anchor = pos["end_s"]["median"]
                hook_ratio_end = round(end, 1)
                end = min(end, anchor)
            bounds.append(end)
        # 保证落点单调：后一段起点不早于前一段终点
        for k in range(1, len(bounds)):
            bounds[k] = max(bounds[k], bounds[k - 1])
        if positions[-1]["end_ratio"]["median"] >= 0.999:
            bounds[-1] = duration
        for k, pos in enumerate(positions):
            start_s = round(bounds[k], 1)
            end_s = round(bounds[k + 1], 1)
            landing.append({
                "position": pos["position"],
                "role": pos["role"],
                "ratio": pos["ratio"],
                "sample_cards": pos["sample_cards"],
                "functions": pos.get("functions", []),
                "expected_start_s": start_s,
                "expected_end_s": end_s,
                "observed_start_s": [round(pos["start_ratio"]["min"] * duration, 1),
                                     round(pos["start_ratio"]["max"] * duration, 1)],
                "observed_end_s": [round(pos["end_ratio"]["min"] * duration, 1),
                                   round(pos["end_ratio"]["max"] * duration, 1)],
                "hook_anchor_s": pos["end_s"]["median"] if k == 0 and hook_ratio_end is not None else None,
                "hook_ratio_end_s": hook_ratio_end if k == 0 else None,
                # 兼容 v0.2.0 字段：start_s/end_s 为观测包络换算
                "start_s": round(pos["ratio"][0] * duration, 1) if pos["ratio"] else None,
                "end_s": round(pos["ratio"][1] * duration, 1) if pos["ratio"] else None,
            })
    else:
        warnings.append("模板缺少中位数统计（v0.2.0 及以前蒸馏），落点退回观测包络换算；请用 distill 重新蒸馏")
        for pos in positions:
            landing.append({
                **pos,
                "start_s": round(pos["ratio"][0] * duration, 1) if pos["ratio"] else None,
                "end_s": round(pos["ratio"][1] * duration, 1) if pos["ratio"] else None,
            })
    lo, hi = template.get("duration_range_s", [None, None])
    if lo is not None and (duration < lo - 0.5 or duration > hi + 0.5):
        warnings.append(
            f"目标时长 {duration:.0f}s 超出样本时长范围 {lo:.0f}–{hi:.0f}s，属外推：占比是否随时长线性缩放没有样本支撑"
        )
    min_cards = min((p.get("sample_cards", 0) for p in positions), default=0)
    if min_cards < COLD_START_CARDS:
        warnings.append(
            f"冷启动：位置区间仅 {min_cards} 张拆解卡支撑（< {COLD_START_CARDS}），中位落点即个例值"
        )
    return {
        "version": VERSION,
        "template_id": template["template_id"],
        "name": template["name"],
        "primary_sequence": template["primary_sequence"],
        "duration_s": duration,
        "method": "median" if has_stats else "envelope",
        "landing_points": landing,
        "warnings": warnings,
        "note": (
            f"位置区间样本 {positions[0]['sample_cards'] if positions else 0} 张拆解卡；"
            "落点只约束结构位置与时长占比，不约束内容本身"
        ),
    }


def render_apply_md(result: dict) -> str:
    lines = [
        f"# 模板套用落点：{result['name']}（{result['template_id']}）",
        "",
        f"- 目标时长 {result['duration_s']:.0f} 秒 ｜ 主段序列："
        f"{role_chain('→'.join(result['primary_sequence']))}",
        "",
    ]
    if result.get("method") == "median":
        lines += [
            "| 序 | 角色 | 期望落点（中位） | 起点观测范围 | 终点观测范围 | 支撑卡数 |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for p in result["landing_points"]:
            anchor = (
                f"（钩子终点取 min(样本绝对秒 {p['hook_anchor_s']:.1f}s, 占比换算 {p['hook_ratio_end_s']:.1f}s)）"
                if p.get("hook_anchor_s") is not None else ""
            )
            lines.append(
                f"| {p['position']} | {ROLE_CN[p['role']]} {p['role']} "
                f"| {p['expected_start_s']:.1f}–{p['expected_end_s']:.1f}s{anchor} "
                f"| {p['observed_start_s'][0]:.1f}–{p['observed_start_s'][1]:.1f}s "
                f"| {p['observed_end_s'][0]:.1f}–{p['observed_end_s'][1]:.1f}s | {p['sample_cards']} |"
            )
    else:
        lines += [
            "| 序 | 角色 | 期望落点（秒） | 占比参考 |",
            "| --- | --- | --- | --- |",
        ]
        for point in result["landing_points"]:
            window = f"{point['start_s']:.1f}–{point['end_s']:.1f}s" if point["start_s"] is not None else "—"
            ratio = f"{point['ratio'][0] * 100:.1f}%–{point['ratio'][1] * 100:.1f}%" if point["ratio"] else "—"
            lines.append(f"| {point['position']} | {ROLE_CN[point['role']]} {point['role']} | {window} | {ratio} |")
    lines.append("")
    for warning in result.get("warnings", []):
        lines.append(f"- ⚠ {warning}")
    lines += [
        f"- {result['note']}",
        "- 段循环（如二次钩子）时按序列就近落位；区间随模板库扩充而更新。",
        "- 红线：例句只示范结构功能，写稿必须使用原创内容；本落点不打分、不预测流量。",
    ]
    return "\n".join(lines) + "\n"


def role_chain(pattern: str) -> str:
    return "→".join(ROLE_CN.get(role, role) for role in pattern.split("→") if role)


def load_library(library: Path) -> list[dict]:
    if not library.is_dir():
        raise TemplateError(f"模板库目录不存在：{library}")
    templates = []
    for path in sorted(library.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and data.get("template_id"):
            data["_path"] = str(path)
            templates.append(data)
    return templates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, default=Path("templates"), help="模板库目录（默认 templates/）")
    sub = parser.add_subparsers(dest="command", required=True)

    # 子命令内也接受 --library（SUPPRESS 避免覆盖全局默认值）
    lib_opt = argparse.ArgumentParser(add_help=False)
    lib_opt.add_argument("--library", type=Path, default=argparse.SUPPRESS, help="模板库目录")

    p_distill = sub.add_parser("distill", parents=[lib_opt], help="从多张拆解卡聚合模板")
    p_distill.add_argument("cards", nargs="+", type=Path, help="拆解卡 JSON（annotate.py --json 产物）")
    p_distill.add_argument("--template-id", required=True)
    p_distill.add_argument("--name", required=True)
    p_distill.add_argument("--genres", default="", help="题材标签，逗号分隔")
    p_distill.add_argument("--created", default="2026-09-19", help="创建日期（保证输出确定性）")

    p_list = sub.add_parser("list", parents=[lib_opt], help="列出模板库")

    p_show = sub.add_parser("show", parents=[lib_opt], help="查看单个模板")
    p_show.add_argument("template_id")

    p_apply = sub.add_parser("apply", parents=[lib_opt], help="按目标时长给期望落点")
    p_apply.add_argument("template_id")
    p_apply.add_argument("--duration", type=float, required=True, help="新脚本目标时长（秒）")
    p_apply.add_argument("-o", "--output", type=Path, help="落点 Markdown 输出路径")
    p_apply.add_argument("--json", type=Path, help="落点 JSON 输出路径")

    args = parser.parse_args(argv)
    if not hasattr(args, "library"):
        args.library = Path("templates")

    try:
        if args.command == "distill":
            cards = [load_card(path) for path in args.cards]
            template = distill(cards, args)
            args.library.mkdir(parents=True, exist_ok=True)
            json_path = args.library / f"{template['template_id']}.json"
            md_path = args.library / f"{template['template_id']}.md"
            json_path.write_text(json.dumps(template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            md_path.write_text(render_template_md(template), encoding="utf-8")
            seq = " → ".join(ROLE_CN[r] for r in template["primary_sequence"])
            print(f"模板已沉淀：{json_path}（{template['card_count']} 张拆解卡 · 主段序列 {seq}）")
            print(f"模板说明：{md_path}")
            return 0

        templates = load_library(args.library)
        if args.command == "list":
            if not templates:
                print("模板库为空：先用 distill 从拆解卡沉淀模板")
                return 0
            print(f"# 模板库（{args.library}/）· {len(templates)} 个模板")
            print()
            print("| template_id | 名称 | 题材 | 主段序列 | 卡片数 | 参考时长 |")
            print("| --- | --- | --- | --- | --- | --- |")
            for template in templates:
                seq = "→".join(ROLE_CN[r] for r in template["primary_sequence"])
                dur = template["duration_range_s"]
                print(
                    f"| {template['template_id']} | {template['name']} "
                    f"| {('、'.join(template['genres'])) or '—'} | {seq} "
                    f"| {template['card_count']} | {dur[0]:.0f}–{dur[1]:.0f}s |"
                )
            return 0

        found = next((t for t in templates if t["template_id"] == args.template_id), None)
        if found is None:
            print(f"模板不存在：{args.template_id}（用 list 查看模板库）", file=sys.stderr)
            return 2

        if args.command == "show":
            print(render_template_md(found), end="")
            return 0

        if args.command == "apply":
            if not args.duration or args.duration <= 0:
                print(f"--duration 必须是正数（秒），收到：{args.duration}", file=sys.stderr)
                return 3
            result = run_apply(found, float(args.duration))
            rendered = render_apply_md(result)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(rendered, encoding="utf-8")
                print(f"落点已生成：{args.output}（目标时长 {args.duration:.0f}s · 方法 {result['method']}）")
                for warning in result["warnings"]:
                    print(f"提示：{warning}")
            else:
                print(rendered, end="")
            if args.json:
                args.json.parent.mkdir(parents=True, exist_ok=True)
                args.json.write_text(
                    json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                )
            return 0
    except TemplateError as exc:
        print(f"模板操作失败：{exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
