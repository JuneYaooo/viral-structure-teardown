#!/usr/bin/env python3
"""V2 评测产物一键复现：同一输入分别跑 v0.2.0（基线，取自 git 提交 266ad86）与当前版本。

用法（仓库根目录）：
  python3 evals/scripts/run_v2.py                       # 只跑仓库内合成夹具
  python3 evals/scripts/run_v2.py --real-dir <目录>      # 另跑真实 Whisper 输出（目录内需有 real.srt / real.vtt）

产物写入 evals/runs_v2/（before_v0.2.0/ 为基线产物），并重新蒸馏 templates/ 下 5 个模板。
真实转写稿文本不入库：真实用例只把统计量（字幕条数、句块数、时长分布）写进 real_whisper_stats.json。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# 一律用相对仓库根的路径（命令在 ROOT 下执行），避免本机绝对路径写进产物
OUT = Path("evals/runs_v2")
BEFORE = OUT / "before_v0.2.0"
FIX = Path("evals/fixtures")
BASELINE_COMMIT = "266ad86"
PY = sys.executable

PAIRS = {  # 卡片名: (夹具 SRT, 标注)
    "standard": ("standard_four_part_v1.srt", "standard_four_part_annotation_v1.json"),
    "no_twist": ("no_twist_listicle_v1.srt", "no_twist_listicle_annotation_v1.json"),
    "double_hook": ("double_hook_loop_v1.srt", "double_hook_loop_annotation_v1.json"),
    "knowledge_flat": ("knowledge_flat_v1.srt", "knowledge_flat_annotation_v1.json"),
    "double_twist": ("double_twist_v1.srt", "double_twist_annotation_v1.json"),
    "soft_seed": ("soft_seed_v1.srt", "soft_seed_annotation_v1.json"),
    "misplaced_evidence": ("standard_four_part_v1.srt", "misplaced_evidence_annotation_v1.json"),
    "sparse_punct": ("sparse_punct_netflix_style_v1.srt", "sparse_punct_annotation_v1.json"),
}
TEMPLATES = [  # (id, 名称, 卡片)
    ("twist-fourpart-v1", "标准四段反转体", ["standard", "double_hook"]),
    ("listicle-notwist-v1", "无转折清单体", ["no_twist"]),
    ("flat-notwist-v1", "无转折平铺讲解体", ["no_twist", "knowledge_flat"]),
    ("double-twist-v1", "双转折带货体", ["double_twist"]),
    ("soft-seed-v1", "剧情软种草体", ["soft_seed"]),
]
APPLY = [("flat-notwist-v1", 90), ("flat-notwist-v1", 30), ("twist-fourpart-v1", 90), ("listicle-notwist-v1", 60)]


def sh(args: list, cwd: Path = ROOT, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run([str(a) for a in args], cwd=cwd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        raise SystemExit(f"命令失败 {args}: {proc.stderr}")
    return proc


def sha(path: Path) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def block_stats(doc: dict) -> dict:
    blocks = doc["blocks"]
    timed = [b for b in blocks if b.get("start") is not None]
    durs = sorted(round(b["end"] - b["start"], 2) for b in timed)
    return {
        "format": doc.get("format"),
        "timed": doc.get("timed"),
        "strategy": doc.get("strategy"),
        "block_count": len(blocks),
        "zero_length_blocks": sum(1 for d in durs if d <= 0),
        "max_block_s": max(durs) if durs else None,
        "median_block_s": durs[len(durs) // 2] if durs else None,
        "max_block_chars": max(len(b["text"]) for b in blocks),
        "text_contains_timecode": any("-->" in b["text"] for b in blocks),
    }


def baseline_scripts() -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="vst-v020-"))
    for name in ("parse_transcript.py", "annotate.py", "templates.py"):
        src = sh(["git", "show", f"{BASELINE_COMMIT}:scripts/{name}"]).stdout
        (tmp / name).write_text(src, encoding="utf-8")
    return tmp


def run_baseline(old: Path, real_dir: Path | None) -> dict:
    BEFORE.mkdir(parents=True, exist_ok=True)
    report: dict = {"baseline_commit": BASELINE_COMMIT}
    for name, fixture in (("sparse_punct", "sparse_punct_netflix_style_v1.srt"),
                          ("multi_sentence", "multi_sentence_cue_v1.srt")):
        out = BEFORE / f"blocks_{name}.json"
        sh([PY, old / "parse_transcript.py", FIX / fixture, "-o", out])
        report[f"blocks_{name}"] = block_stats(json.loads(out.read_text(encoding="utf-8")))
    proc = sh([PY, old / "annotate.py", BEFORE / "blocks_sparse_punct.json",
               FIX / "sparse_punct_annotation_v1.json", "-o", BEFORE / "card_sparse_punct.md",
               "--json", BEFORE / "card_sparse_punct.json"])
    card = json.loads((BEFORE / "card_sparse_punct.json").read_text(encoding="utf-8"))
    report["card_sparse_punct"] = {
        "stdout": proc.stdout.strip().splitlines(),
        "cut_block_count": card["cut_block_count"],
        "evidence": f"{card['evidence_hits']}/{card['evidence_total']}",
    }
    for tid, dur in (("flat-notwist-v1", 90), ("flat-notwist-v1", 30)):
        stem = f"apply_{tid.replace('-v1', '').replace('-', '_')}_{dur}s"
        sh([PY, old / "templates.py", "--library", "templates", "apply", tid, "--duration", dur,
            "-o", BEFORE / f"{stem}.md", "--json", BEFORE / f"{stem}.json"])
    if real_dir:
        real = {}
        for ext in ("srt", "vtt"):
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / "b.json"
                sh([PY, old / "parse_transcript.py", real_dir / f"real.{ext}", "-o", out])
                real[ext] = block_stats(json.loads(out.read_text(encoding="utf-8")))
        report["real_whisper"] = real
    return report


def run_current(real_dir: Path | None) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {}
    srts = sorted({srt for srt, _ in PAIRS.values()} | {"multi_sentence_cue_v1.srt"})
    for srt in srts:
        out = OUT / f"blocks_{srt.replace('.srt', '')}.json"
        sh([PY, "scripts/parse_transcript.py", FIX / srt, "-o", out])
        report[f"blocks_{srt.replace('.srt', '')}"] = block_stats(json.loads(out.read_text(encoding="utf-8")))
    sh([PY, "scripts/parse_transcript.py", FIX / "no_punctuation_v1.txt", "-o", OUT / "blocks_no_punctuation_v1.json"])
    for name, (srt, ann) in PAIRS.items():
        blocks = OUT / f"blocks_{srt.replace('.srt', '')}.json"
        proc = sh([PY, "scripts/annotate.py", blocks, FIX / ann, "-o", OUT / f"card_{name}.md",
                   "--json", OUT / f"card_{name}.json"])
        card = json.loads((OUT / f"card_{name}.json").read_text(encoding="utf-8"))
        report[f"card_{name}"] = {
            "stdout": proc.stdout.strip().splitlines(),
            "pattern": card["structure_pattern"],
            "cut_block_count": card["cut_block_count"],
            "evidence": f"{card['evidence_hits']}/{card['evidence_total']}",
            "opens_with_hook": card["hook_check"]["opens_with_hook"],
            "first_hook_end_s": card["hook_check"]["first_hook_end_s"],
            "chars_per_s": card["chars_per_s"],
            "sha256_md": sha(OUT / f"card_{name}.md"),
        }
    # 坏时间轴拦截
    proc = sh([PY, "scripts/annotate.py", OUT / "blocks_standard_four_part_v1.json",
               FIX / "bad_timeline_annotation_v1.json", "-o", OUT / "should_not_exist.md"], check=False)
    (OUT / "bad_timeline_rejected.txt").write_text(
        f"exit={proc.returncode}\nstdout={proc.stdout}\nstderr=\n{proc.stderr}", encoding="utf-8")
    report["bad_timeline"] = {"exit": proc.returncode, "card_written": (OUT / "should_not_exist.md").exists()}
    # 确定性：同一标注渲染两次
    with tempfile.TemporaryDirectory() as td:
        again = Path(td) / "again.md"
        sh([PY, "scripts/annotate.py", OUT / "blocks_standard_four_part_v1.json",
            FIX / "standard_four_part_annotation_v1.json", "-o", again])
        report["determinism"] = {"first": sha(OUT / "card_standard.md"), "second": sha(again),
                                 "equal": sha(OUT / "card_standard.md") == sha(again)}
    # 重新蒸馏模板
    for tid, name, cards in TEMPLATES:
        sh([PY, "scripts/templates.py", "distill", *[OUT / f"card_{c}.json" for c in cards],
            "--template-id", tid, "--name", name, "--created", "2026-11-02"])
    listing = sh([PY, "scripts/templates.py", "list"]).stdout
    (OUT / "library_list_v0.3.0.txt").write_text(listing, encoding="utf-8")
    for tid, dur in APPLY:
        stem = f"apply_{tid.replace('-v1', '').replace('-', '_')}_{dur}s"
        proc = sh([PY, "scripts/templates.py", "apply", tid, "--duration", dur,
                   "-o", OUT / f"{stem}.md", "--json", OUT / f"{stem}.json"])
        report[stem] = proc.stdout.strip().splitlines()
    # 一致性
    proc = sh([PY, "scripts/agreement.py", OUT / "blocks_double_twist_v1.json",
               FIX / "double_twist_annotation_v1.json", FIX / "double_twist_annotation_b_v1.json",
               "-o", OUT / "agreement_double_twist.md", "--json", OUT / "agreement_double_twist.json"])
    report["agreement_double_twist"] = proc.stdout.strip().splitlines()
    if real_dir:
        real = {}
        for ext in ("srt", "vtt"):
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / "b.json"
                proc = sh([PY, "scripts/parse_transcript.py", real_dir / f"real.{ext}", "-o", out])
                stats = block_stats(json.loads(out.read_text(encoding="utf-8")))
                doc = json.loads(out.read_text(encoding="utf-8"))
                stats["cue_count"] = doc.get("cue_count")
                stats["summary"] = proc.stdout.strip().replace(str(out), "<blocks.json>")
                real[ext] = stats
        report["real_whisper"] = real
    return report


def main() -> int:
    import os
    os.chdir(ROOT)
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--real-dir", type=Path, help="真实 Whisper 输出目录（含 real.srt / real.vtt），不入库")
    args = parser.parse_args()
    old = baseline_scripts()
    before = run_baseline(old, args.real_dir)
    after = run_current(args.real_dir)
    (BEFORE / "report.json").write_text(json.dumps(before, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "report.json").write_text(json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if args.real_dir:
        real = {"before_v0.2.0": before["real_whisper"], "after_v0.3.0": after["real_whisper"]}
        (OUT / "real_whisper_stats.json").write_text(json.dumps(real, ensure_ascii=False, indent=2) + "\n",
                                                    encoding="utf-8")
    print(f"基线产物：{BEFORE}/ · 当前产物：{OUT}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
