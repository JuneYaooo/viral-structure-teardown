"""annotate.py 的单元测试：python3 -m unittest discover tests"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import annotate as an

BLOCKS_DOC = {
    "version": "0.1.0",
    "source": "synthetic.srt",
    "format": "srt",
    "timed": True,
    "duration_s": 58.0,
    "blocks": [
        {"i": 0, "start": 0.0, "end": 4.0, "text": "别再跟风买锅了，我测了五款。"},
        {"i": 1, "start": 4.0, "end": 7.0, "text": "测完当天我就退货了。"},
        {"i": 2, "start": 7.0, "end": 12.0, "text": "先说三个测试标准。"},
    ],
}

GOOD_ANNOTATION = {
    "video_id": "v1",
    "title": "合成样本",
    "genre": "好物测评",
    "transcript": "synthetic.srt",
    "structure_note": "标准四段。",
    "segments": [
        {"role": "hook", "start": 0.0, "end": 7.0, "evidence": "别再跟风买锅了", "reason": "否定式开场"},
        {"role": "build", "start": 7.0, "end": 12.0, "evidence": "先说三个测试标准", "reason": "立标准"},
    ],
}


def annotation(**overrides) -> dict:
    doc = json.loads(json.dumps(GOOD_ANNOTATION))
    doc.update(overrides)
    return doc


class ValidateTests(unittest.TestCase):
    def test_good_passes(self):
        segments = an.validate_segments(GOOD_ANNOTATION, 58.0)
        self.assertEqual(len(segments), 2)

    def test_end_before_start(self):
        doc = annotation(segments=[{"role": "hook", "start": 5.0, "end": 2.0}])
        with self.assertRaises(an.ValidationError) as ctx:
            an.validate_segments(doc, 58.0)
        self.assertIn("时间轴非法", str(ctx.exception))

    def test_overlap_detected(self):
        doc = annotation(segments=[
            {"role": "hook", "start": 0.0, "end": 7.0},
            {"role": "build", "start": 5.0, "end": 12.0},
        ])
        with self.assertRaises(an.ValidationError) as ctx:
            an.validate_segments(doc, 58.0)
        self.assertIn("重叠或乱序", str(ctx.exception))

    def test_out_of_range(self):
        doc = annotation(segments=[{"role": "cta", "start": 55.0, "end": 62.0}])
        with self.assertRaises(an.ValidationError) as ctx:
            an.validate_segments(doc, 58.0)
        self.assertIn("超出转写时长", str(ctx.exception))

    def test_bad_role(self):
        doc = annotation(segments=[{"role": "story", "start": 0.0, "end": 5.0}])
        with self.assertRaises(an.ValidationError) as ctx:
            an.validate_segments(doc, 58.0)
        self.assertIn("role 非法", str(ctx.exception))

    def test_overlap_across_invalid_middle_segment(self):
        # 回归：中间段非法时，其后合法段与更早合法段的重叠也要被发现
        doc = annotation(segments=[
            {"role": "hook", "start": 0.0, "end": 7.0},
            {"role": "cta", "start": 20.0, "end": 15.0},   # 非法：end<start
            {"role": "build", "start": 3.0, "end": 9.0},   # 与 hook 重叠，隔着非法段
        ])
        with self.assertRaises(an.ValidationError) as ctx:
            an.validate_segments(doc, 58.0)
        message = str(ctx.exception)
        self.assertIn("重叠", message)
        self.assertIn("时间轴非法", message)


class BuildCardTests(unittest.TestCase):
    def setUp(self):
        segments = an.validate_segments(GOOD_ANNOTATION, 58.0)
        self.card = an.build_card(GOOD_ANNOTATION, BLOCKS_DOC, segments)

    def test_ratios(self):
        self.assertEqual(self.card["role_stats"]["hook"]["ratio"], round(7.0 / 58.0, 4))
        # 标注覆盖 0–12s / 全片 58s
        self.assertEqual(self.card["coverage"], round(12.0 / 58.0, 4))

    def test_evidence_hit_and_miss(self):
        self.assertTrue(self.card["segments"][0]["evidence_ok"])
        segments = an.validate_segments(annotation(
            segments=[{"role": "hook", "start": 0.0, "end": 7.0, "evidence": "关注我下期再测"}]),
            58.0)
        card = an.build_card(annotation(), BLOCKS_DOC, segments)
        self.assertFalse(card["segments"][0]["evidence_ok"])
        self.assertFalse(card["checks"]["evidence_all_found"])

    def test_cut_block_detected(self):
        doc = annotation(segments=[
            {"role": "hook", "start": 0.0, "end": 5.5},   # 5.5 落在块 1（4.0–7.0）中间
            {"role": "build", "start": 5.5, "end": 12.0},
        ])
        segments = an.validate_segments(doc, 58.0)
        card = an.build_card(doc, BLOCKS_DOC, segments)
        self.assertEqual(card["cut_block_count"], 2)
        self.assertFalse(card["checks"]["alignment_clean"])

    def test_missing_twist_recorded(self):
        self.assertIn("twist", self.card["roles_missing"])
        self.assertIn("cta", self.card["roles_missing"])
        self.assertEqual(self.card["structure_pattern"], "hook→build")

    def test_uncovered_gap_listed(self):
        doc = annotation(segments=[{"role": "hook", "start": 0.0, "end": 7.0}])
        segments = an.validate_segments(doc, 58.0)
        card = an.build_card(doc, BLOCKS_DOC, segments)
        self.assertEqual(len(card["uncovered"]), 1)
        self.assertLess(card["coverage"], 0.6)
        self.assertFalse(card["checks"]["coverage_ok"])


class RenderTests(unittest.TestCase):
    def setUp(self):
        segments = an.validate_segments(GOOD_ANNOTATION, 58.0)
        self.card = an.build_card(GOOD_ANNOTATION, BLOCKS_DOC, segments)
        self.rendered = an.render_card(self.card)

    def test_deterministic_render(self):
        again = an.render_card(self.card)
        self.assertEqual(self.rendered, again)

    def test_contains_timeline_and_boundaries(self):
        self.assertIn("| 1 | 钩子 hook | 00:00.0–00:07.0 | 7.0s | 12.1% |", self.rendered)
        self.assertIn("## 结构总评（Agent 撰写位）", self.rendered)
        self.assertIn("不打分", self.rendered)

    def test_missing_role_honest(self):
        card = dict(self.card, roles_missing=["twist", "cta"], roles_present=["hook", "build"])
        rendered = an.render_card(card)
        self.assertIn("转折 ✗（未检出，如实标注）", rendered)


class UntimedTests(unittest.TestCase):
    def test_untimed_blocks_rejected(self):
        doc = dict(BLOCKS_DOC, timed=False, duration_s=None)
        with self.assertRaises(an.ValidationError):
            an.build_card(annotation(), doc, [])


class RunTests(unittest.TestCase):
    def write(self, name: str, payload, suffix: str) -> Path:
        tmp = Path(tempfile.mkdtemp())
        path = tmp / f"{name}{suffix}"
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return path

    def test_exit_codes(self):
        blocks = self.write("b", BLOCKS_DOC, ".json")
        missing = blocks.parent / "missing.json"
        self.assertEqual(an.run([str(missing), str(missing)]), 2)
        bad_blocks = self.write("b2", "{oops", ".json")
        good = self.write("a", GOOD_ANNOTATION, ".json")
        self.assertEqual(an.run([str(bad_blocks), str(good)]), 3)
        bad_doc = self.write("b3", {"blocks": []}, ".json")
        self.assertEqual(an.run([str(bad_doc), str(good)]), 3)

    def test_end_to_end_outputs(self):
        blocks = self.write("b", BLOCKS_DOC, ".json")
        good = self.write("a", GOOD_ANNOTATION, ".json")
        card = blocks.parent / "card.md"
        summary = blocks.parent / "card.json"
        self.assertEqual(an.run([str(blocks), str(good), "-o", str(card), "--json", str(summary)]), 0)
        self.assertIn("拆解卡：合成样本", card.read_text(encoding="utf-8"))
        payload = json.loads(summary.read_text(encoding="utf-8"))
        self.assertEqual(payload["structure_pattern"], "hook→build")


if __name__ == "__main__":
    unittest.main()
