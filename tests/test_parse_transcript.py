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
        # 第二条与第三条之间 gap 2s(5.0→8.0) > 0.8s → 应切成两块
        self.assertFalse(self.doc["punctuation"])
        self.assertEqual(self.doc["block_count"], 2)
        self.assertEqual(self.doc["blocks"][0]["end"], 5.0)
        self.assertEqual(self.doc["blocks"][1]["start"], 8.0)

    def test_small_gap_stays_joined(self):
        doc = pt.parse_transcript(write("s2", SRT_NO_PUNCT.replace(
            "00:00:08,000 --> 00:00:10,000", "00:00:05,200 --> 00:00:07,400"), ".srt"))
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


if __name__ == "__main__":
    unittest.main()
