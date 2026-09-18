#!/usr/bin/env python3
"""Aggregate per-case judgments into an auditable JSON summary."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

DIMENSIONS = (
    "structure_accuracy",
    "boundary_honesty",
    "template_usability",
    "redline_compliance",
    "evidence_integrity",
)


def wilson(successes: int, total: int, z: float = 1.96) -> list[float] | None:
    if total == 0:
        return None
    proportion = successes / total
    denominator = 1 + z * z / total
    center = (proportion + z * z / (2 * total)) / denominator
    margin = (
        z
        * math.sqrt(proportion * (1 - proportion) / total + z * z / (4 * total * total))
        / denominator
    )
    return [round(max(0.0, center - margin), 4), round(min(1.0, center + margin), 4)]


def load(path: Path) -> list[dict]:
    records = []
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        record = json.loads(raw)
        missing = {"case_id", "condition", "run", "scores", "critical_failure"} - record.keys()
        if missing:
            raise ValueError(f"line {line_number}: missing fields {sorted(missing)}")
        if record["condition"] not in {"baseline", "skill"}:
            raise ValueError(f"line {line_number}: condition must be baseline or skill")
        for dimension in DIMENSIONS:
            score = record["scores"].get(dimension)
            if not isinstance(score, (int, float)) or not 0 <= score <= 4:
                raise ValueError(f"line {line_number}: {dimension} must be between 0 and 4")
        records.append(record)
    return records


def summarize(records: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        grouped[record["condition"]].append(record)

    conditions = {}
    for condition in ("baseline", "skill"):
        items = grouped.get(condition, [])
        critical = sum(bool(item["critical_failure"]) for item in items)
        passed = sum(
            not item["critical_failure"]
            and not item.get("failed_required_checks")
            and sum(item["scores"][key] for key in DIMENSIONS) / len(DIMENSIONS) >= 3
            for item in items
        )
        dimension_means = {
            key: round(sum(item["scores"][key] for item in items) / len(items), 3)
            if items
            else None
            for key in DIMENSIONS
        }
        conditions[condition] = {
            "judgment_count": len(items),
            "unique_case_count": len({item["case_id"] for item in items}),
            "pass_count": passed,
            "pass_rate": round(passed / len(items), 4) if items else None,
            "pass_rate_wilson_95": wilson(passed, len(items)),
            "critical_failure_count": critical,
            "dimension_means_0_to_4": dimension_means,
        }

    baseline_rate = conditions["baseline"]["pass_rate"]
    skill_rate = conditions["skill"]["pass_rate"]
    delta = None
    if baseline_rate is not None and skill_rate is not None:
        delta = round(skill_rate - baseline_rate, 4)
    return {
        "schema_version": "1.0",
        "status": "completed",
        "dimensions": list(DIMENSIONS),
        "conditions": conditions,
        "skill_minus_baseline_pass_rate": delta,
        "interpretation_note": (
            "A critical failure always fails that judgment; pass otherwise requires all "
            "required atomic checks green and a mean dimension score of at least 3.0/4.0."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("judgments")
    parser.add_argument("--output")
    args = parser.parse_args()
    summary = summarize(load(Path(args.judgments)))
    rendered = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
