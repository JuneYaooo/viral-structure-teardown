#!/usr/bin/env python3
"""把爆款视频/口播转写稿（SRT / WebVTT / 纯文本）解析成带时间戳的句块列表 JSON。

输入：SRT 字幕（.srt）、WebVTT 字幕（.vtt，或首行为 WEBVTT 的文件）、纯文本（.txt，无时间码）。
输出：句块 JSON —— 每块 {i, start, end, text}，供 annotate.py 做结构标注。

切块规则（确定性，v0.3.0 起）：
  1. 标点充足（≥ 半数字幕条带标点）：按终止标点（。！？!?；;…）切句；同一字幕条内
     有多句时，按字数比例在字幕条时间区间内插值起止时间（不再产生 0 时长句块）。
  2. 标点稀疏或无标点（ASR 常见；Netflix 中文字幕规范也要求用空格代替逗号句号、
     只保留问号）：在字幕条边界切块 —— 相邻字幕条间隔 ≥ 0.5s 视为停顿边界、
     上一条以终止标点结尾时切开、单块累积超过 32 字或超过 6 秒时切开
     （句块是段边界的最小单位，粒度必须细于钩子窗口）。
  3. 纯文本：按句切；全篇无标点时按每 40 字切一块（无时间码，start/end 为 null）。

阈值依据见 references/benchmarks.md（Netflix 字幕间隔与每行字数规范、普通话语速）。
只做本地文本解析，零网络；同输入输出一致。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERSION = "0.3.0"

SENTENCE_END = "。！？!?；;…"
SOFT_PUNCT = "，,、：:"
PAUSE_GAP_S = 0.5          # 字幕条间隔 ≥ 0.5s 视为停顿边界（Netflix：间隔要么 2 帧要么 ≥ 半秒）
MAX_BLOCK_CHARS = 32       # 字幕条边界切块的单块字数上限（Netflix 简中 16 字/行 × 2 行）
MAX_BLOCK_S = 6.0          # 字幕条边界切块的单块时长上限（TikTok 官方：钩子优先放在前 6 秒）
PUNCT_DENSE_RATIO = 0.5    # 带标点的字幕条占比 ≥ 该值才按标点切句
TXT_CHUNK_CHARS = 40       # 无标点纯文本的切块长度

TIME_PART = r"(?:(\d{1,3}):)?(\d{1,2}):(\d{2})[,.](\d{1,3})"
CUE_TIME_RE = re.compile(TIME_PART + r"\s*-->\s*" + TIME_PART)
TAG_RE = re.compile(r"<[^>]*>|\{\\[^}]*\}")  # WebVTT/SRT 行内标签：<i> <c.x> <00:00:01.000> {\an8}


class ParseError(ValueError):
    pass


def join_text(left: str, right: str) -> str:
    """拼接文本：两侧都是 ASCII 字母数字时补空格，否则直接相连（中文）。"""
    if left and right and left[-1].isascii() and left[-1].isalnum() \
            and right[0].isascii() and right[0].isalnum():
        return left + " " + right
    return left + right


def to_seconds(h: str | None, m: str, s: str, ms: str) -> float:
    return int(h or 0) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def clean_line(line: str) -> str:
    return TAG_RE.sub("", line).strip()


def is_vtt(path: Path, raw: str) -> bool:
    return path.suffix.lower() == ".vtt" or raw.lstrip("﻿").startswith("WEBVTT")


def parse_cues(path: Path, raw: str, vtt: bool) -> tuple[list[dict], dict]:
    """解析 SRT/WebVTT 字幕条。返回 (按 start 排序的字幕条, 诊断信息)。"""
    cues: list[dict] = []
    dup_lines = 0
    chunks = re.split(r"\r?\n\s*\r?\n", raw.replace("\r\n", "\n").replace("\r", "\n"))
    for n, chunk in enumerate(chunks):
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        if not lines:
            continue
        if vtt:
            head = lines[0].lstrip("﻿")
            if n == 0 and head.startswith("WEBVTT"):
                continue
            if head.startswith(("NOTE", "STYLE", "REGION")):
                continue
        time_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if time_index is None:
            raise ParseError(f"字幕块缺少时间轴行（-->）：{lines[0][:30]}…")
        match = CUE_TIME_RE.search(lines[time_index])
        if not match:
            raise ParseError(f"时间码无法解析：{lines[time_index]}")
        g = match.groups()
        start = to_seconds(*g[0:4])
        end = to_seconds(*g[4:8])
        if end < start:
            raise ParseError(f"时间码倒置：{lines[time_index]}")
        text_lines = [clean_line(line) for line in lines[time_index + 1:]]
        text_lines = [line for line in text_lines if line]
        # 滚动式自动字幕会把上一条的末行原样重复在下一条首行：去掉相邻重复行
        if cues and text_lines and cues[-1]["last_line"] == text_lines[0]:
            text_lines = text_lines[1:]
            dup_lines += 1
        text = ""
        for line in text_lines:
            text = join_text(text, line)
        text = text.strip()
        if text:
            cues.append({"start": start, "end": end, "text": text, "last_line": text_lines[-1]})
    if not cues:
        raise ParseError("字幕中没有可用的字幕条")
    order = sorted(range(len(cues)), key=lambda i: (cues[i]["start"], i))
    reordered = order != list(range(len(cues)))
    cues = [cues[i] for i in order]
    overlaps = sum(1 for a, b in zip(cues, cues[1:]) if b["start"] < a["end"] - 1e-6)
    for cue in cues:
        cue.pop("last_line", None)
    return cues, {"reordered": reordered, "overlapping_cues": overlaps, "dropped_repeat_lines": dup_lines}


def has_sentence_punct(text: str) -> bool:
    return any(ch in SENTENCE_END for ch in text)


def has_any_punct(text: str) -> bool:
    return any(ch in SENTENCE_END or ch in SOFT_PUNCT for ch in text)


def round2(value: float) -> float:
    return round(value + 0.0, 2)


def char_stream(cues: list[dict]) -> list[tuple[str, float, float]]:
    """把字幕条展开成逐字流，每个字按字数比例分到所在字幕条的时间区间里。"""
    stream: list[tuple[str, float, float]] = []
    prev_text = ""
    for cue in cues:
        text = cue["text"]
        if join_text(prev_text, text) != prev_text + text:  # 英文词跨字幕条时补空格
            stream.append((" ", cue["start"], cue["start"]))
        span = cue["end"] - cue["start"]
        n = len(text)
        for k, ch in enumerate(text):
            stream.append((ch, cue["start"] + span * k / n, cue["start"] + span * (k + 1) / n))
        prev_text = text
    return stream


def split_timed_by_punct(cues: list[dict]) -> list[dict]:
    """按终止标点切句；句子起止时间按字数在所在字幕条内比例插值。"""
    blocks: list[dict] = []
    buf: list[tuple[str, float, float]] = []

    def flush():
        chars = list(buf)
        while chars and chars[0][0].isspace():
            chars.pop(0)
        while chars and chars[-1][0].isspace():
            chars.pop()
        if chars:
            blocks.append({
                "start": round2(chars[0][1]),
                "end": round2(chars[-1][2]),
                "text": "".join(c[0] for c in chars),
            })
        buf.clear()

    for item in char_stream(cues):
        buf.append(item)
        if item[0] in SENTENCE_END:
            flush()
    flush()
    return blocks


def split_timed_at_cues(cues: list[dict], pause_gap: float, max_chars: int,
                        max_block_s: float = MAX_BLOCK_S) -> list[dict]:
    """标点稀疏/无标点：只在字幕条边界切 —— 停顿 ≥ pause_gap、上一条以终止标点结尾、
    并入下一条后超过 max_chars 字或 max_block_s 秒。单条字幕本身超限时不再细切（无字级时间）。"""
    blocks: list[dict] = []
    cur_text = ""
    cur_start: float | None = None
    cur_end: float | None = None
    for cue in cues:
        if cur_text:
            boundary = (
                cue["start"] - cur_end >= pause_gap - 1e-9
                or cur_text[-1] in SENTENCE_END
                or len(cur_text) + len(cue["text"]) > max_chars
                or cue["end"] - cur_start > max_block_s + 1e-9
            )
            if boundary:
                blocks.append({"start": round2(cur_start), "end": round2(cur_end), "text": cur_text})
                cur_text, cur_start, cur_end = "", None, None
        if cur_start is None:
            cur_start = cue["start"]
        cur_text = join_text(cur_text, cue["text"])
        cur_end = cue["end"] if cur_end is None else max(cur_end, cue["end"])
    if cur_text:
        blocks.append({"start": round2(cur_start), "end": round2(cur_end), "text": cur_text})
    return blocks


def split_plain_text(raw: str) -> list[dict]:
    """纯文本：按句切；全篇无标点时按 40 字切块。无时间码。"""
    text = ""
    for line in raw.splitlines():
        text = join_text(text, line.strip())
    text = text.strip()
    if not text:
        raise ParseError("纯文本内容为空")
    if has_sentence_punct(text):
        pieces: list[str] = []
        buf = ""
        for ch in text:
            buf += ch
            if ch in SENTENCE_END:
                piece = buf.strip()
                if piece:
                    pieces.append(piece)
                buf = ""
        if buf.strip():
            pieces.append(buf.strip())
    else:
        pieces = [text[i: i + TXT_CHUNK_CHARS] for i in range(0, len(text), TXT_CHUNK_CHARS)]
    return [{"start": None, "end": None, "text": piece} for piece in pieces]


def parse_transcript(path: Path, pause_gap: float = PAUSE_GAP_S,
                     max_chars: int = MAX_BLOCK_CHARS, max_block_s: float = MAX_BLOCK_S) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    vtt = is_vtt(path, raw)
    if path.suffix.lower() == ".srt" or vtt:
        cues, diag = parse_cues(path, raw, vtt)
        punct_ratio = sum(1 for c in cues if has_any_punct(c["text"])) / len(cues)
        any_end = has_sentence_punct("".join(c["text"] for c in cues))
        if any_end and punct_ratio >= PUNCT_DENSE_RATIO:
            blocks = split_timed_by_punct(cues)
            strategy = "sentence_punct"
        else:
            blocks = split_timed_at_cues(cues, pause_gap, max_chars, max_block_s)
            strategy = ("sparse_punct" if any_end else "pause_gap") if len(blocks) > 1 else "single_block"
        durations = [b["end"] - b["start"] for b in blocks]
        return {
            "version": VERSION,
            "source": str(path),
            "format": "vtt" if vtt else "srt",
            "timed": True,
            "duration_s": round2(max(c["end"] for c in cues)),
            "punctuation": any_end,
            "punct_cue_ratio": round(punct_ratio, 4),
            "strategy": strategy,
            "params": {"pause_gap_s": pause_gap, "max_block_chars": max_chars,
                       "max_block_s": max_block_s},
            "cue_count": len(cues),
            "block_count": len(blocks),
            "max_block_s": round2(max(durations)) if durations else 0.0,
            "diagnostics": diag,
            "blocks": [{"i": i, **block} for i, block in enumerate(blocks)],
        }
    blocks = split_plain_text(raw)
    return {
        "version": VERSION,
        "source": str(path),
        "format": "txt",
        "timed": False,
        "duration_s": None,
        "punctuation": has_sentence_punct("".join(b["text"] for b in blocks)),
        "strategy": "sentence_punct" if blocks and any(
            has_sentence_punct(b["text"]) for b in blocks
        ) else "fixed_length",
        "block_count": len(blocks),
        "blocks": [{"i": i, **block} for i, block in enumerate(blocks)],
    }


def summary_line(result: dict, output: Path | None) -> str:
    target = str(output) if output else "stdout"
    if result["timed"]:
        line = (
            f"解析完成：{result['format'].upper()} · {result['cue_count']} 条字幕 → "
            f"{result['block_count']} 个句块 · 全长 {result['duration_s']}s · 最长句块 "
            f"{result['max_block_s']}s（切法 {result['strategy']}）→ {target}"
        )
        diag = result.get("diagnostics", {})
        notes = []
        if diag.get("overlapping_cues"):
            notes.append(f"{diag['overlapping_cues']} 处字幕条时间重叠（可能是滚动字幕），请复核")
        if diag.get("reordered"):
            notes.append("字幕条原顺序非时间序，已按开始时间重排")
        if diag.get("dropped_repeat_lines"):
            notes.append(f"去掉 {diag['dropped_repeat_lines']} 行与上一条重复的滚动字幕行")
        if notes:
            line += "\n提示：" + "；".join(notes)
        return line
    return (
        f"解析完成：纯文本 · {result['block_count']} 个句块 · 无时间码"
        f"（切法 {result['strategy']}）→ {target}"
    )


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("transcript", type=Path, help="转写稿（.srt / .vtt / 纯文本 .txt）")
    parser.add_argument("-o", "--output", type=Path, help="句块 JSON 输出路径（缺省打印到 stdout）")
    parser.add_argument("--pause-gap", type=float, default=PAUSE_GAP_S,
                        help=f"字幕条边界切块的停顿阈值（秒，默认 {PAUSE_GAP_S}）")
    parser.add_argument("--max-chars", type=int, default=MAX_BLOCK_CHARS,
                        help=f"字幕条边界切块的单块字数上限（默认 {MAX_BLOCK_CHARS}）")
    parser.add_argument("--max-block-s", type=float, default=MAX_BLOCK_S,
                        help=f"字幕条边界切块的单块时长上限（秒，默认 {MAX_BLOCK_S}）")
    args = parser.parse_args(argv)

    if not args.transcript.is_file():
        print(f"输入文件不存在：{args.transcript}", file=sys.stderr)
        return 2
    if args.pause_gap <= 0 or args.max_chars <= 0 or args.max_block_s <= 0:
        print("--pause-gap / --max-chars / --max-block-s 必须是正数", file=sys.stderr)
        return 3
    try:
        result = parse_transcript(args.transcript, args.pause_gap, args.max_chars, args.max_block_s)
    except ParseError as exc:
        print(f"解析失败：{exc}", file=sys.stderr)
        return 3

    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(summary_line(result, args.output))
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
