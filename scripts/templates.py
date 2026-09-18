#!/usr/bin/env python3
"""结构模板库：从多条拆解卡蒸馏可复用模板，并给新脚本期望落点。

子命令：
  distill  把多张拆解卡（annotate.py --json 产物）聚合为一个模板
           （段序列模式 + 每段占比区间 + 例句 + 题材标签）
  list     列出模板库里的全部模板
  show     查看单个模板详情
  apply    按目标时长把模板占比区间换算成秒级期望落点（借鉴节拍表按百分比打点）

模板只沉淀结构位置与句式功能：不打分、不收录整段文案、不做内容代写。
全部本地运行，零网络；同输入输出一致。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

VERSION = "0.1.0"

ROLES = ("hook", "build", "twist", "cta")
ROLE_CN = {"hook": "钩子", "build": "留人", "twist": "转折", "cta": "转化"}
MAX_EXAMPLES_PER_POSITION = 3

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
        functions: list[str] = []
        examples: list[str] = []
        for card in matching:
            duration = card["duration_s"]
            seg = card["segments"][pos_index]
            if seg["role"] != role:
                continue
            starts.append(round(seg["start"] / duration, 4))
            ends.append(round(seg["end"] / duration, 4))
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
        "| 序 | 角色 | 占比区间 | 功能 | 句式模式 | 例句参考 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for pos in template["positions"]:
        ratio = f"{pos['ratio'][0] * 100:.1f}%–{pos['ratio'][1] * 100:.1f}%" if pos["ratio"] else "—"
        examples = "；".join(f"「{line}」" for line in pos["example_lines"]) or "—"
        patterns = "；".join(pos["patterns"]) or "—"
        lines.append(
            f"| {pos['position']} | {ROLE_CN[pos['role']]} {pos['role']} | {ratio} "
            f"| {('；'.join(pos['functions'])) or '—'} | {patterns} | {examples} |"
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


def run_apply(template: dict, duration: float) -> dict:
    landing = []
    for pos in template["positions"]:
        if not pos["ratio"]:
            landing.append({**pos, "start_s": None, "end_s": None})
            continue
        landing.append({
            **pos,
            "start_s": round(pos["ratio"][0] * duration, 1),
            "end_s": round(pos["ratio"][1] * duration, 1),
        })
    return {
        "version": VERSION,
        "template_id": template["template_id"],
        "name": template["name"],
        "primary_sequence": template["primary_sequence"],
        "duration_s": duration,
        "landing_points": landing,
        "note": (
            f"位置区间样本 {template['positions'][0]['sample_cards'] if template['positions'] else 0} 张拆解卡；"
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
        "| 序 | 角色 | 期望落点（秒） | 占比参考 |",
        "| --- | --- | --- | --- |",
    ]
    for point in result["landing_points"]:
        window = f"{point['start_s']:.1f}–{point['end_s']:.1f}s" if point["start_s"] is not None else "—"
        ratio = f"{point['ratio'][0] * 100:.1f}%–{point['ratio'][1] * 100:.1f}%" if point["ratio"] else "—"
        lines.append(f"| {point['position']} | {ROLE_CN[point['role']]} {point['role']} | {window} | {ratio} |")
    lines += [
        "",
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
                print(f"落点已生成：{args.output}（目标时长 {args.duration:.0f}s）")
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
