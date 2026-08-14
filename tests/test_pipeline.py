import unittest
from pathlib import Path
import importlib.util

SPEC = importlib.util.spec_from_file_location("pipeline", Path(__file__).parents[1] / "src" / "pipeline.py")
pipeline = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pipeline)


class PipelineTests(unittest.TestCase):
    def test_decode_compact_snapshot(self):
        sample = {
            "count": 2,
            "dict": {
                "source": ["gupy"], "company": ["Empresa A", "Empresa B"],
                "area": ["Suporte"], "seniority": ["Pleno"], "work_model": ["remote"],
                "market": ["BR"], "country": ["BR"],
            },
            "jobs": {
                "title": ["Analista de Suporte N2", "Outra vaga"], "src": [0, 0], "cmp": [0, 1],
                "area": [0, 0], "sen": [0, 0], "wm": [0, 0], "mk": [0, 0], "co": [0, 0],
                "city": ["Home Office", ""], "pub": ["2026-08-14T10:00:00-03:00", "2026-08-13"],
                "seen": ["", ""], "url": ["https://example.com/1", "https://example.com/2"],
                "sk": ["SQL · API · ITIL", ""], "ct": ["CLT", "PJ"],
            },
        }
        rows = pipeline.decode_snapshot(sample)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["company"], "Empresa A")
        self.assertEqual(rows[0]["work_model"], "remote")
        self.assertEqual(rows[0]["contract_types"], ["CLT"])

    def test_decode_rejects_bad_count(self):
        with self.assertRaises(RuntimeError):
            pipeline.decode_snapshot({"count": 2, "dict": {}, "jobs": {"title": ["uma"]}})

    def test_canonical_accepts_boolean_remote(self):
        row = pipeline.canonical({"title": "Suporte", "url": "x", "remote": True})
        self.assertEqual(row["work_model"], "True")

    def test_date_only_uses_midday(self):
        dt = pipeline.parse_date("2026-08-14")
        self.assertEqual(dt.hour, 12)
        self.assertEqual(dt.utcoffset().total_seconds(), -10800)

    def test_future_datetime_can_be_parsed(self):
        self.assertIsNotNone(pipeline.parse_date("2026-08-14T13:30:00Z"))

    def test_remote_detection(self):
        self.assertTrue(pipeline.is_remote({"work_model": "remote", "city": ""}))
        self.assertTrue(pipeline.is_remote({"work_model": "", "city": "Home Office"}))
        self.assertFalse(pipeline.is_remote({"work_model": "hybrid", "city": "São Paulo"}))

    def test_unknown_snapshot_fails(self):
        with self.assertRaises(RuntimeError):
            pipeline.decode_snapshot({"foo": "bar"})


if __name__ == "__main__":
    unittest.main()
