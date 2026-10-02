"""initial 96개 표시 라벨 무결성 — 매퍼 alias 가 아니라 표시·검색용 static presentation.

실행: ~/ai_env/bin/python -m unittest tests.test_initial_evidence_catalog
TRAIN 대조(670MB 읽기): MEDMAP_SLOW_TESTS=1 을 붙인다.
"""
import json
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medmap import config
from medmap.intake import IntakeMapper

CATALOG = ROOT / "medmap" / "data" / "initial_evidence_ko.json"
LABELS = ROOT / "medmap" / "data" / "question_labels_ko.json"
KO27 = {"E_9", "E_33", "E_45", "E_50", "E_53", "E_66", "E_77", "E_88", "E_89", "E_91", "E_112", "E_129", "E_148",
        "E_151", "E_155", "E_169", "E_175", "E_181", "E_182", "E_194", "E_201", "E_212", "E_214", "E_216", "E_218",
        "E_220", "E_221"}
PAST_HISTORY_14 = {"E_0", "E_69", "E_70", "E_78", "E_79", "E_104", "E_105", "E_116", "E_120", "E_123", "E_124",
                   "E_189", "E_209", "E_226"}
BOOTSTRAP_ORDER = ["E_91", "E_53", "E_66", "E_201", "E_175", "E_88"]


class InitialCatalogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(CATALOG.read_text(encoding="utf-8"))
        cls.items = cls.data["items"]
        cls.ids = [item["evidence_id"] for item in cls.items]
        cls.evidences = json.loads(config.check_path(config.EVIDENCES_JSON).read_text(encoding="utf-8"))
        cls.labels = json.loads(LABELS.read_text(encoding="utf-8"))["questions"]

    def test_01_exactly_96_unique(self):
        self.assertEqual(len(self.ids), 96)
        self.assertEqual(len(set(self.ids)), 96)

    def test_02_all_binary_and_not_excluded(self):
        for eid in self.ids:
            self.assertIn(eid, self.evidences, eid)
            self.assertEqual(self.evidences[eid]["data_type"], "B", eid)
            self.assertNotIn(eid, config.EXCLUDED_QUESTIONS)

    def test_03_rank_order_matches_counts(self):
        self.assertEqual([item["train_rank"] for item in self.items], list(range(1, 97)))
        counts = [item["train_count"] for item in self.items]
        self.assertEqual(counts, sorted(counts, reverse=True))
        self.assertEqual(sum(counts), 1025602)

    def test_04_ko27_reuse_existing_question_labels(self):
        reused = {item["evidence_id"] for item in self.items if item["detail_source"] == "question_labels_ko"}
        self.assertEqual(reused, KO27)
        for item in self.items:
            if item["detail_source"] == "question_labels_ko":
                self.assertEqual(item["detail_ko"], self.labels[item["evidence_id"]])
            else:
                self.assertEqual(item["detail_source"], "new_static_presentation")

    def test_05_mapper_overlap_is_ko27_and_no_past_history(self):
        self.assertEqual(IntakeMapper().supported & set(self.ids), KO27)
        self.assertFalse(PAST_HISTORY_14 & set(self.ids))

    def test_06_labels_nonempty_and_unique(self):
        labels = [item["label_ko"].strip() for item in self.items]
        self.assertTrue(all(labels))
        self.assertEqual(len(set(labels)), 96)
        self.assertTrue(all(item["detail_ko"].strip() for item in self.items))

    def test_07_frequent_ids_are_top8(self):
        self.assertEqual(self.data["frequent_ids"], self.ids[:8])

    def test_08_bootstrap_questions_have_korean_labels(self):
        for eid in BOOTSTRAP_ORDER:
            self.assertIn(eid, self.labels)
            self.assertEqual(self.evidences[eid]["data_type"], "B")

    @unittest.skipUnless(os.environ.get("MEDMAP_SLOW_TESTS") == "1", "TRAIN 전수 집계 — MEDMAP_SLOW_TESTS=1 일 때만")
    def test_09_matches_train_initial_evidence(self):
        import polars as pl
        path = config.check_path(config.DATA_DIR / "release_train_patients")
        counts = pl.scan_csv(path).select("INITIAL_EVIDENCE").collect()["INITIAL_EVIDENCE"].value_counts()
        self.assertEqual(dict(counts.iter_rows()), {item["evidence_id"]: item["train_count"] for item in self.items})


if __name__ == "__main__":
    unittest.main()
