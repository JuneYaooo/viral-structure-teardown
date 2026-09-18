#!/usr/bin/env python3
"""把爆款视频/口播转写稿（SRT 或纯文本）解析成带时间戳的句块列表 JSON。

输入：SRT 字幕文件（带时间码）或纯文本（.txt，无时间码）。
输出：句块 JSON —— 每块 {i, start, end, text}，供 annotate.py 做结构标注。

切块规则（确定性）：
  1. 有终止标点（。！？!?；;…）：按句切，时间取所在字幕条的时间区间。
  2. SRT 全篇无标点（ASR 常见）：按停顿切 —— 相邻字幕条间隔 > 0.8s 视为停顿
     边界；单块累积超过 60 字时在字幕条边界强制切开。
  3. 纯文本无标点：按每 40 字切一块（无时间码，start/end 为 null）。

只做本地文本解析，零网络；同输入输出一致。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERSION = "0.1.0"

SENTENCE_END = "。！？!?；;…"
PAUSE_GAP_S = 0.8          # 相邻字幕条间隔超过该值视为停顿边界
NO_PUNCT_MAX_CHARS = 60    # 无标点 SRT 单块最大累积字数
TXT_CHUNK_CHARS = 40       # 无标点纯文本的切块长度

SRT_TIME_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})"
)


class ParseError(ValueError):
    pass


def join_text(left: str, right: str) -> str:
    """拼接文本：两侧都是 ASCII 字母数字时补空格，否则直接相连（中文）。"""
    if left and right and left[-1].isascii() and left[-1].isalnum() \
            and right[0].isascii() and right[0].isalnum():
        return left + " " + right
    return left + right


def parse_timestamp_to_s(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")) / 1000.0


def parse_srt_cues(path: Path) -> list[dict]:
    raw = path.read_text(encoding="utf-8-sig")
    cues: list[dict] = []
    for chunk in re.split(r"\n\s*\n", raw):
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        if not lines:
            continue
        time_line = None
        time_index = 0
        for idx, line in enumerate(lines):
            if "-->" in line:
                time_line = line
                time_index = idx
                break
        if time_line is None:
            raise ParseError(f"SRT 块缺少时间轴行（-->）：{lines[0][:30]}…")
        match = SRT_TIME_RE.search(time_line)
        if not match:
            raise ParseError(f"SRT 时间码无法解析：{time_line}")
        g = match.groups()
        start = parse_timestamp_to_s(g[0], g[1], g[2], g[3])
        end = parse_timestamp_to_s(g[4], g[5], g[6], g[7])
        if end < start:
            raise ParseError(f"SRT 时间码倒置：{time_line}")
        text = join_cue_text(lines[time_index + 1:])
        if text:
            cues.append({"start": start, "end": end, "text": text})
    if not cues:
        raise ParseError("SRT 中没有可用的字幕条")
    return cues


def join_cue_text(lines: list[str]) -> str:
    text = ""
    for line in lines:
        text = join_text(text, line.strip())
    return text.strip()


def has_sentence_punct(text: str) -> bool:
    return any(ch in SENTENCE_END for ch in text)


def round2(value: float) -> float:
    return round(value + 0.0, 2)


def split_timed_by_punct(cues: list[dict]) -> list[dict]:
    """按句切：终止标点处断句，块时间 = 所在字幕条区间（跨条句子取首条 start、末条 end）。"""
    blocks: list[dict] = []
    buf = ""
    buf_start: float | None = None
    for cue in cues:
        if buf_start is None:
            buf_start = cue["start"]
        buf = join_text(buf, cue["text"])
        while True:
            cut = min(
                (buf.index(ch) for ch in SENTENCE_END if ch in buf),
                default=None,
            )
            if cut is None:
                break
            sentence = buf[: cut + 1].strip()
            rest = buf[cut + 1:]
            if sentence:
                blocks.append({
                    "start": round2(buf_start),
                    "end": round2(cue["end"]),
                    "text": sentence,
                })
            buf = rest.lstrip()
            buf_start = cue["end"]  # 同一条内被切开时，余句从此条末尾近似起算
    if buf.strip():
        blocks.append({
            "start": round2(buf_start if buf_start is not None else cues[-1]["end"]),
            "end": round2(cues[-1]["end"]),
            "text": buf.strip(),
        })
    return blocks


def split_timed_no_punct(cues: list[dict]) -> list[dict]:
    """无标点 SRT：按停顿（gap>0.8s）与 60 字上限在字幕条边界切块。"""
    blocks: list[dict] = []
    cur_text = ""
    cur_start: float | None = None
    cur_end: float | None = None
    prev_end: float | None = None
    for cue in cues:
        new_block = (
            cur_text
            and prev_end is not None
            and (cue["start"] - prev_end > PAUSE_GAP_S or len(cur_text) >= NO_PUNCT_MAX_CHARS)
        )
        if new_block:
            blocks.append({
                "start": round2(cur_start),
                "end": round2(cur_end),
                "text": cur_text,
            })
            cur_text = ""
            cur_start = None
        if cur_start is None:
            cur_start = cue["start"]
        cur_text = join_text(cur_text, cue["text"])
        cur_end = cue["end"]
        prev_end = cue["end"]
    if cur_text:
        blocks.append({
            "start": round2(cur_start),
            "end": round2(cur_end),
            "text": cur_text,
        })
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


def parse_transcript(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".srt":
        cues = parse_srt_cues(path)
        punctuated = has_sentence_punct("".join(cue["text"] for cue in cues))
        if punctuated:
            blocks = split_timed_by_punct(cues)
            strategy = "sentence_punct"
        else:
            blocks = split_timed_no_punct(cues)
            strategy = "pause_gap" if len(blocks) > 1 else "single_block"
        duration = round2(cues[-1]["end"])
        return {
            "version": VERSION,
            "source": str(path),
            "format": "srt",
            "timed": True,
            "duration_s": duration,
            "punctuation": punctuated,
            "strategy": strategy,
            "block_count": len(blocks),
            "blocks": [{"i": i, **block} for i, block in enumerate(blocks)],
        }
    blocks = split_plain_text(path.read_text(encoding="utf-8-sig"))
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
        return (
            f"解析完成：{'SRT' if result['format'] == 'srt' else 'TXT'} · "
            f"{result['block_count']} 个句块 · 全长 {result['duration_s']}s "
            f"（切法 {result['strategy']}）→ {target}"
        )
    return (
        f"解析完成：纯文本 · {result['block_count']} 个句块 · 无时间码"
        f"（切法 {result['strategy']}）→ {target}"
    )


def run(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("transcript", type=Path, help="转写稿（.srt 或纯文本 .txt）")
    parser.add_argument("-o", "--output", type=Path, help="句块 JSON 输出路径（缺省打印到 stdout）")
    args = parser.parse_args(argv)

    if not args.transcript.is_file():
        print(f"输入文件不存在：{args.transcript}", file=sys.stderr)
        return 2
    try:
        result = parse_transcript(args.transcript)
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
