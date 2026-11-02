"""agreement.py 的单元测试：python3 -m unittest discover tests"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import agreement as ag

BLOCKS = {
    "version": "0.3.0",
    "source": "synthetic.srt",
    "format": "srt",
    "timed": True,
    "duration_s": 40.0,
    "blocks": [{"i": i, "start": i * 4.0, "end": (i + 1) * 4.0, "text": f"第{i}句。"} for i in range(10)],
}


def ann(*segments) -> dict:
    return {"video_id": "x", "segments": [
        {"role": role, "start": start, "end": end} for role, start, end in segments
    ]}


A = ann(("hook", 0, 8), ("build", 8, 24), ("twist", 24, 32), ("cta", 32, 40))


class AgreementTests(unittest.TestCase):
    def test_identical_annotations(self):
        result = ag.compare(BLOCKS, A, A)
        self.assertEqual(result["label_agreement"], 1.0)
        self.assertEqual(result["kappa"], 1.0)
        self.assertEqual(result["boundary"]["f1"], 1.0)
        self.assertEqual(result["window_diff"], 0.0)
        self.assertTrue(result["same_sequence"])
        self.assertEqual(result["disagreements"], [])

    def test_near_miss_boundary_counts_with_tolerance(self):
        b = ann(("hook", 0, 8), ("build", 8, 28), ("twist", 28, 32), ("cta", 32, 40))
        result = ag.compare(BLOCKS, A, b)
        self.assertEqual(result["boundary"]["f1"], 1.0)          # ±1 句块内算命中
        self.assertEqual(result["boundary"]["matched_offsets_s"], [0.0, 4.0, 0.0])
        self.assertEqual(result["label_agreement"], 0.9)
        self.assertGreater(result["window_diff"], 0.0)            # WindowDiff 仍记录偏差
        self.assertEqual([d["block_i"] for d in result["disagreements"]], [6])

    def test_missing_segment_lowers_recall(self):
        b = ann(("hook", 0, 8), ("build", 8, 32), ("cta", 32, 40))
        result = ag.compare(BLOCKS, A, b)
        self.assertFalse(result["same_sequence"])
        self.assertEqual(result["boundary"]["precision"], 1.0)
        self.assertAlmostEqual(result["boundary"]["recall"], 0.6667, places=4)

    def test_kappa_known_value(self):
        # 2×2 例：50 个样本观测一致 0.7；a 边际 0.5/0.5、b 边际 0.6/0.4 → 期望一致 0.5 → kappa 0.4
        a = ["x"] * 25 + ["y"] * 25
        b = ["x"] * 20 + ["y"] * 5 + ["x"] * 10 + ["y"] * 15
        self.assertAlmostEqual(ag.cohen_kappa(a, b), 0.4, places=4)

    def test_landis_koch_bands(self):
        self.assertEqual(ag.landis_koch(-0.1), "差（poor）")
        self.assertEqual(ag.landis_koch(0.5), "中等（moderate）")
        self.assertEqual(ag.landis_koch(0.9), "几乎完全一致（almost perfect）")

    def test_invalid_annotation_rejected(self):
        with self.assertRaises(ag.an.ValidationError):
            ag.compare(BLOCKS, A, ann(("hook", 5, 2)))

    def test_untimed_rejected(self):
        with self.assertRaises(ag.an.ValidationError):
            ag.compare({**BLOCKS, "timed": False}, A, A)

    def test_render_has_no_score_and_disclaims(self):
        rendered = ag.render(ag.compare(BLOCKS, A, A))
        self.assertIn("不打分", rendered)
        self.assertIn("Cohen's kappa", rendered)


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.blocks = self.tmp / "blocks.json"
        self.blocks.write_text(json.dumps(BLOCKS, ensure_ascii=False), encoding="utf-8")
        self.a = self.tmp / "a.json"
        self.a.write_text(json.dumps(A), encoding="utf-8")

    def test_exit_codes_and_outputs(self):
        self.assertEqual(ag.run([str(self.blocks), str(self.a), "/nonexistent.json"]), 2)
        bad = self.tmp / "bad.json"
        bad.write_text(json.dumps(ann(("hook", 5, 2))), encoding="utf-8")
        self.assertEqual(ag.run([str(self.blocks), str(self.a), str(bad)]), 3)
        out_md, out_json = self.tmp / "r.md", self.tmp / "r.json"
        self.assertEqual(ag.run([str(self.blocks), str(self.a), str(self.a),
                                 "-o", str(out_md), "--json", str(out_json)]), 0)
        self.assertIn("标注一致性报告", out_md.read_text(encoding="utf-8"))
        self.assertEqual(json.loads(out_json.read_text(encoding="utf-8"))["kappa"], 1.0)


if __name__ == "__main__":
    unittest.main()
