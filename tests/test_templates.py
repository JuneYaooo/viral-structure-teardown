"""templates.py 的单元测试：python3 -m unittest discover tests"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import templates as tp

CARD_STD = {
    "version": "0.1.0",
    "video_id": "standard-four-part-v1",
    "title": "标准四段（合成样本）",
    "genre": "好物测评",
    "duration_s": 58.0,
    "structure_pattern": "hook→build→twist→cta",
    "patterns": {"hook": ["别再…了"], "twist": ["最贵的…反而垫底"]},
    "segments": [
        {"index": 1, "role": "hook", "start": 0.0, "end": 7.0, "duration_s": 7.0,
         "ratio": 0.1207, "evidence": "别再跟风买锅了", "reason": "否定式开场"},
        {"index": 2, "role": "build", "start": 7.0, "end": 33.0, "duration_s": 26.0,
         "ratio": 0.4483, "evidence": "先说三个测试标准", "reason": "立标准"},
        {"index": 3, "role": "twist", "start": 33.0, "end": 45.0, "duration_s": 12.0,
         "ratio": 0.2069, "evidence": "最贵的反而垫底", "reason": "反常识结论"},
        {"index": 4, "role": "cta", "start": 45.0, "end": 58.0, "duration_s": 13.0,
         "ratio": 0.2241, "evidence": "数据表在评论区", "reason": "评论区+关注"},
    ],
}

CARD_LOOP = {
    "version": "0.1.0",
    "video_id": "double-hook-loop-v1",
    "title": "双钩子循环（合成样本）",
    "genre": "剧情维权",
    "duration_s": 63.0,
    "structure_pattern": "hook→build→twist→hook→build→cta",
    "patterns": {},
    "segments": [
        {"index": 1, "role": "hook", "start": 0.0, "end": 7.5, "duration_s": 7.5,
         "ratio": 0.119, "evidence": "住到第二十天才发现是隔断房", "reason": "倒霉开局"},
        {"index": 2, "role": "build", "start": 7.5, "end": 20.0, "duration_s": 12.5,
         "ratio": 0.1984, "evidence": "墙体是空心的", "reason": "发现过程"},
        {"index": 3, "role": "twist", "start": 20.0, "end": 26.5, "duration_s": 6.5,
         "ratio": 0.1032, "evidence": "聊天记录实锤", "reason": "第一次反转"},
        {"index": 4, "role": "hook", "start": 26.5, "end": 30.5, "duration_s": 4.0,
         "ratio": 0.0635, "evidence": "你以为就能退钱了", "reason": "二次钩子"},
        {"index": 5, "role": "build", "start": 30.5, "end": 50.0, "duration_s": 19.5,
         "ratio": 0.3095, "evidence": "逐帧对时间戳", "reason": "反击过程"},
        {"index": 6, "role": "cta", "start": 50.0, "end": 63.0, "duration_s": 13.0,
         "ratio": 0.2063, "evidence": "模板在评论区", "reason": "评论区+预告"},
    ],
}


class DistillArgs:
    def __init__(self, template_id="t1", name="模板", genres="好物测评", created="2026-09-19"):
        self.template_id = template_id
        self.name = name
        self.genres = genres
        self.created = created


class DistillTests(unittest.TestCase):
    def setUp(self):
        self.template = tp.distill([CARD_STD, CARD_LOOP], DistillArgs())

    def test_primary_sequence_is_most_frequent_then_shortest(self):
        self.assertEqual(self.template["primary_sequence"], ["hook", "build", "twist", "cta"])
        self.assertEqual(len(self.template["role_sequences"]), 2)

    def test_positions_from_matching_cards(self):
        # 双钩子卡与主序列不匹配，位置区间只来自标准四段卡
        self.assertEqual(self.template["positions"][0]["sample_cards"], 1)
        self.assertEqual(self.template["positions"][0]["ratio"], [0.0, 0.1207])
        self.assertEqual(self.template["positions"][2]["role"], "twist")

    def test_role_ranges_span_all_cards(self):
        hook = self.template["role_ratio_ranges"]["hook"]
        self.assertEqual(hook[0], 0.0)
        self.assertEqual(hook[1], round(30.5 / 63.0, 4))  # 二次钩子把 hook 范围拉长

    def test_examples_and_patterns_merged(self):
        self.assertIn("别再跟风买锅了", self.template["positions"][0]["example_lines"])
        self.assertIn("别再…了", self.template["patterns"]["hook"])

    def test_red_lines_present(self):
        self.assertTrue(any("不打分" in rule for rule in self.template["red_lines"]))


class ApplyTests(unittest.TestCase):
    def test_landing_seconds(self):
        result = tp.run_apply(tp.distill([CARD_STD], DistillArgs()), 90.0)
        points = result["landing_points"]
        self.assertEqual(points[0]["start_s"], 0.0)
        self.assertEqual(points[0]["end_s"], round(0.1207 * 90, 1))
        self.assertEqual(points[3]["end_s"], 90.0)

    def test_render_contains_boundaries(self):
        result = tp.run_apply(tp.distill([CARD_STD], DistillArgs()), 90.0)
        rendered = tp.render_apply_md(result)
        self.assertIn("| 1 | 钩子 hook | 0.0–10.9s |", rendered)
        self.assertIn("不打分", rendered)


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.library = self.tmp / "templates"

    def write_card(self, name: str, card: dict) -> Path:
        path = self.tmp / f"{name}.json"
        path.write_text(json.dumps(card, ensure_ascii=False), encoding="utf-8")
        return path

    def test_distill_list_show_apply(self):
        card_path = self.write_card("card", CARD_STD)
        code = tp.main([
            "distill", str(card_path), "--template-id", "twist-v1", "--name", "标准四段反转体",
            "--library", str(self.library),
        ])
        self.assertEqual(code, 0)
        self.assertTrue((self.library / "twist-v1.json").exists())
        self.assertTrue((self.library / "twist-v1.md").exists())

        import io
        from contextlib import redirect_stdout
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(tp.main(["list", "--library", str(self.library)]), 0)
        self.assertIn("twist-v1", out.getvalue())
        self.assertIn("标准四段反转体", out.getvalue())

        out = io.StringIO()
        with redirect_stdout(out):
            self.assertEqual(tp.main(["show", "twist-v1", "--library", str(self.library)]), 0)
        self.assertIn("段位与占比区间", out.getvalue())

        out_path = self.tmp / "apply.md"
        self.assertEqual(tp.main([
            "apply", "twist-v1", "--duration", "90", "-o", str(out_path),
            "--library", str(self.library),
        ]), 0)
        text = out_path.read_text(encoding="utf-8")
        self.assertIn("期望落点（秒）", text)

    def test_missing_template_exit_2(self):
        self.library.mkdir()
        self.assertEqual(tp.main(["show", "ghost", "--library", str(self.library)]), 2)

    def test_missing_library_exit_3(self):
        self.assertEqual(tp.main(["list", "--library", str(self.tmp / "nope")]), 3)

    def test_bad_duration_exit_3(self):
        self.library.mkdir()
        (self.library / "twist-v1.json").write_text(
            json.dumps(tp.distill([CARD_STD], DistillArgs("twist-v1", "模板")), ensure_ascii=False),
            encoding="utf-8")
        self.assertEqual(tp.main(["apply", "twist-v1", "--duration", "0", "--library", str(self.library)]), 3)

    def test_invalid_card_rejected(self):
        path = self.write_card("bad", {"segments": []})
        with self.assertRaises(tp.TemplateError):
            tp.load_card(path)


if __name__ == "__main__":
    unittest.main()
