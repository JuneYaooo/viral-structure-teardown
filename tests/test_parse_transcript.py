"""parse_transcript.py 的单元测试：python3 -m unittest discover tests"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import parse_transcript as pt


def write(name: str, content: str, suffix: str) -> Path:
    tmp = Path(tempfile.mkdtemp())
    path = tmp / f"{name}{suffix}"
    path.write_text(content, encoding="utf-8")
    return path


SRT_PUNCT = """1
00:00:00,000 --> 00:00:04,000
别再跟风买锅了，我测了五款。

2
00:00:04,000 --> 00:00:06,500
结论在最后！

3
00:00:09,000 --> 00:00:12,000
先说测试标准。
"""

SRT_NO_PUNCT = """1
00:00:00,000 --> 00:00:02,000
别再跟风买锅了我测了五款

2
00:00:02,300 --> 00:00:05,000
温差超十五度直接淘汰

3
00:00:08,000 --> 00:00:10,000
涂层耐磨是第二关
"""


class SrtPunctTests(unittest.TestCase):
    def setUp(self):
        self.doc = pt.parse_transcript(write("s", SRT_PUNCT, ".srt"))

    def test_metadata(self):
        self.assertTrue(self.doc["timed"])
        self.assertTrue(self.doc["punctuation"])
        self.assertEqual(self.doc["duration_s"], 12.0)

    def test_each_cue_one_block(self):
        texts = [b["text"] for b in self.doc["blocks"]]
        self.assertEqual(texts, ["别再跟风买锅了，我测了五款。", "结论在最后！", "先说测试标准。"])

    def test_times_carry_cue_interval(self):
        first = self.doc["blocks"][0]
        self.assertEqual((first["start"], first["end"]), (0.0, 4.0))

    def test_determinism(self):
        # source 路径不同属预期；其余字段必须逐位一致
        strip_source = lambda doc: {k: v for k, v in doc.items() if k != "source"}
        again = pt.parse_transcript(write("s2", SRT_PUNCT, ".srt"))
        self.assertEqual(strip_source(self.doc), strip_source(again))


class SrtNoPunctTests(unittest.TestCase):
    def setUp(self):
        self.doc = pt.parse_transcript(write("s", SRT_NO_PUNCT, ".srt"))

    def test_gap_splits_block(self):
        # 第二条与第三条之间 gap 3s(5.0→8.0) ≥ 0.5s → 应切成两块
        self.assertFalse(self.doc["punctuation"])
        self.assertEqual(self.doc["block_count"], 2)
        self.assertEqual(self.doc["blocks"][0]["end"], 5.0)
        self.assertEqual(self.doc["blocks"][1]["start"], 8.0)

    def test_small_gap_stays_joined(self):
        doc = pt.parse_transcript(write("s2", SRT_NO_PUNCT.replace(
            "00:00:08,000 --> 00:00:10,000", "00:00:05,200 --> 00:00:05,900"), ".srt"))
        self.assertEqual(doc["block_count"], 1)

    def test_long_run_splits_at_60_chars(self):
        cues = []
        for i in range(10):
            cues.append(
                f"{i + 1}\n00:00:{i * 2:02d},000 --> 00:00:{i * 2 + 1:02d},000\n第{i}句没有标点\n"
            )
        doc = pt.parse_transcript(write("s3", "\n".join(cues), ".srt"))
        self.assertGreaterEqual(doc["block_count"], 2)


class PlainTextTests(unittest.TestCase):
    def test_punctuated_text(self):
        doc = pt.parse_transcript(write("t", "先说结论。再说过程？最后求关注！", ".txt"))
        self.assertFalse(doc["timed"])
        self.assertEqual([b["text"] for b in doc["blocks"]], ["先说结论。", "再说过程？", "最后求关注！"])

    def test_no_punct_fixed_length(self):
        text = "这" * 95
        doc = pt.parse_transcript(write("t", text, ".txt"))
        self.assertEqual(doc["block_count"], 3)
        self.assertEqual([len(b["text"]) for b in doc["blocks"]], [40, 40, 15])
        self.assertIsNone(doc["blocks"][0]["start"])

    def test_empty_text_rejected(self):
        with self.assertRaises(pt.ParseError):
            pt.parse_transcript(write("t", "  \n \n", ".txt"))


class SrtErrorTests(unittest.TestCase):
    def test_bad_timecode(self):
        with self.assertRaises(pt.ParseError):
            pt.parse_transcript(write("s", "1\n00:00:0x,000 --> 00:00:04,000\n文本\n", ".srt"))

    def test_inverted_timecode(self):
        with self.assertRaises(pt.ParseError):
            pt.parse_transcript(write("s", "1\n00:00:04,000 --> 00:00:00,000\n文本\n", ".srt"))

    def test_empty_srt(self):
        with self.assertRaises(pt.ParseError):
            pt.parse_transcript(write("s", "\n\n", ".srt"))


class CliTests(unittest.TestCase):
    def test_missing_file_exit_2(self):
        self.assertEqual(pt.run(["/nonexistent/virtual.srt"]), 2)

    def test_end_to_end_stdout_json(self):
        path = write("s", SRT_PUNCT, ".srt")
        buf = __import__("io").StringIO()
        real_stdout = sys.stdout
        sys.stdout = buf
        try:
            code = pt.run([str(path)])
        finally:
            sys.stdout = real_stdout
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["block_count"], 3)


VTT_NO_HOURS = """WEBVTT
Kind: captions

NOTE 这是注释块，应被忽略

STYLE
::cue { color: yellow }

intro-1
00:00.000 --> 00:02.000 align:start position:10%
<v 主播>你家的水壶</v> 用了多久了

00:02.000 --> 00:04.500
我拆了<c.red>三台</c>

00:05.200 --> 00:07.000
先说结论
"""


class VttTests(unittest.TestCase):
    """v0.3.0：WebVTT（Whisper/YouTube 常见输出，小时位可省略）此前被当成纯文本误解析。"""

    def setUp(self):
        self.doc = pt.parse_transcript(write("v", VTT_NO_HOURS, ".vtt"))

    def test_parsed_as_timed_vtt(self):
        self.assertEqual(self.doc["format"], "vtt")
        self.assertTrue(self.doc["timed"])
        self.assertEqual(self.doc["duration_s"], 7.0)
        self.assertEqual(self.doc["cue_count"], 3)

    def test_header_note_style_settings_tags_removed(self):
        text = "".join(b["text"] for b in self.doc["blocks"])
        for junk in ("WEBVTT", "NOTE", "cue", "align", "<", "主播>"):
            self.assertNotIn(junk, text)
        self.assertIn("我拆了三台", text)

    def test_pause_gap_splits(self):
        # 4.5→5.2 间隔 0.7s ≥ 0.5s → 切开
        self.assertEqual([b["start"] for b in self.doc["blocks"]], [0.0, 5.2])

    def test_webvtt_header_detected_without_suffix(self):
        doc = pt.parse_transcript(write("v2", VTT_NO_HOURS, ".srt"))
        self.assertEqual(doc["format"], "vtt")


class MultiSentenceCueTests(unittest.TestCase):
    """v0.3.0：同一字幕条内多句按字数比例插值，不再产生 0 时长句块。"""

    SRT = """1
00:00:00,000 --> 00:00:06,000
早起没用？错了。我坚持一年反而更累。

2
00:00:06,000 --> 00:00:10,000
问题在第一个小时。
"""

    def setUp(self):
        self.doc = pt.parse_transcript(write("m", self.SRT, ".srt"))

    def test_no_zero_length_blocks(self):
        for block in self.doc["blocks"]:
            self.assertGreater(block["end"], block["start"])

    def test_proportional_times(self):
        blocks = self.doc["blocks"]
        self.assertEqual([b["text"] for b in blocks][:3], ["早起没用？", "错了。", "我坚持一年反而更累。"])
        # 第 1 条 18 字 6 秒：「早起没用？」5 字 → 0–1.67s
        self.assertEqual((blocks[0]["start"], blocks[0]["end"]), (0.0, 1.67))
        self.assertEqual(blocks[2]["end"], 6.0)
        self.assertEqual((blocks[3]["start"], blocks[3]["end"]), (6.0, 10.0))

    def test_blocks_monotonic(self):
        ends = [b["end"] for b in self.doc["blocks"]]
        self.assertEqual(ends, sorted(ends))


class SparsePunctTests(unittest.TestCase):
    """Netflix 中文字幕规范：不用逗号句号、保留问号 → 标点稀疏，不能按问号切出巨块。"""

    def test_sparse_question_marks_do_not_make_giant_blocks(self):
        cues = []
        texts = ["你家水壶用了多久了？", "我拆了三台 内胆全是水垢", "先说结论 不锈钢也会结垢",
                 "区别只在于 你能不能看见", "第一台是玻璃壶", "第二台是不锈钢",
                 "那为什么一体成型最难清理？", "因为它没有可拆的底盖"]
        for i, text in enumerate(texts):
            cues.append(f"{i + 1}\n00:00:{i * 3:02d},000 --> 00:00:{i * 3 + 3:02d},000\n{text}\n")
        doc = pt.parse_transcript(write("sp", "\n".join(cues), ".srt"))
        self.assertEqual(doc["strategy"], "sparse_punct")
        self.assertLessEqual(doc["max_block_s"], 6.0)
        self.assertGreaterEqual(doc["block_count"], 4)

    def test_dense_punct_keeps_sentence_mode(self):
        doc = pt.parse_transcript(write("s", SRT_PUNCT, ".srt"))
        self.assertEqual(doc["strategy"], "sentence_punct")


class CueBoundaryLimitTests(unittest.TestCase):
    def contiguous(self, n: int, step: int, text: str) -> str:
        return "\n".join(
            f"{i + 1}\n00:00:{i * step:02d},000 --> 00:00:{(i + 1) * step:02d},000\n{text}{i}\n"
            for i in range(n)
        )

    def test_contiguous_whisper_style_capped_at_6s(self):
        # Whisper 中文 SRT 实测：字幕条首尾相接（间隔 0）且无标点，停顿规则失效，必须靠时长/字数上限
        doc = pt.parse_transcript(write("w", self.contiguous(15, 2, "没有标点的短句"), ".srt"))
        self.assertLessEqual(doc["max_block_s"], 6.0)
        self.assertEqual(doc["block_count"], 5)

    def test_char_cap(self):
        doc = pt.parse_transcript(write("c", self.contiguous(6, 1, "十个字的字幕条文本"), ".srt"))
        for block in doc["blocks"]:
            self.assertLessEqual(len(block["text"]), pt.MAX_BLOCK_CHARS)

    def test_custom_params(self):
        doc = pt.parse_transcript(write("w", self.contiguous(15, 2, "短句"), ".srt"),
                                  pause_gap=0.5, max_chars=200, max_block_s=60)
        self.assertEqual(doc["block_count"], 1)
        self.assertEqual(doc["params"]["max_block_s"], 60)


class CueOrderTests(unittest.TestCase):
    def test_unsorted_cues_reordered_and_duration_is_max_end(self):
        srt = ("2\n00:00:03,000 --> 00:00:05,000\n后一句\n\n"
               "1\n00:00:00,000 --> 00:00:02,000\n前一句\n")
        doc = pt.parse_transcript(write("o", srt, ".srt"))
        self.assertTrue(doc["diagnostics"]["reordered"])
        self.assertEqual(doc["blocks"][0]["text"], "前一句")
        self.assertEqual(doc["duration_s"], 5.0)

    def test_overlap_and_rolling_repeat_reported(self):
        srt = ("1\n00:00:00,000 --> 00:00:03,000\n第一行\n\n"
               "2\n00:00:02,000 --> 00:00:05,000\n第一行\n第二行\n")
        doc = pt.parse_transcript(write("r", srt, ".srt"))
        self.assertEqual(doc["diagnostics"]["overlapping_cues"], 1)
        self.assertEqual(doc["diagnostics"]["dropped_repeat_lines"], 1)
        self.assertEqual("".join(b["text"] for b in doc["blocks"]), "第一行第二行")

    def test_bad_params_exit_3(self):
        path = write("s", SRT_PUNCT, ".srt")
        self.assertEqual(pt.run([str(path), "--max-block-s", "0"]), 3)


if __name__ == "__main__":
    unittest.main()
