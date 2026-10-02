import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

MODULE = os.environ.get("EVALUATOR_MODULE", "step15v2_evaluate_fixed")
sys.path.insert(0, os.environ.get("EVALUATOR_DIR", str(Path(__file__).resolve().parent)))
ev = importlib.import_module(MODULE)


class RepairRegressionTests(unittest.TestCase):
    def test_a_old_kg_coverage_never_exceeds_one(self):
        self.assertTrue(hasattr(ev, "old_kg_coverage"), "old_kg_coverage missing")
        overlap, coverage = ev.old_kg_coverage({"E1", "E2", "E3"}, {"E1", "E2"})
        self.assertEqual(overlap, {"E1", "E2"})
        self.assertEqual(coverage, 1.0)

    def test_b_e218_extracts_exertion_trigger(self):
        self.assertTrue(hasattr(ev, "atomic_decompose"), "atomic_decompose missing")
        row = ev.atomic_decompose("E_218", "Do you have symptoms that are increased with physical exertion but alleviated with rest?", "Triggered by exertion")
        self.assertEqual(row["trigger"], "exertion")

    def test_c_e218_extracts_rest_relief(self):
        self.assertTrue(hasattr(ev, "atomic_decompose"), "atomic_decompose missing")
        row = ev.atomic_decompose("E_218", "Do you have symptoms that are increased with physical exertion but alleviated with rest?", "Triggered by exertion")
        self.assertEqual(row["relieving_factor"], "rest")

    def test_d_e13_extracts_progression_and_threshold(self):
        self.assertTrue(hasattr(ev, "atomic_decompose"), "atomic_decompose missing")
        row = ev.atomic_decompose("E_13", "Do you find that your symptoms have worsened over the last 2 weeks and that progressively less effort is required to cause the symptoms?", "Progressive")
        self.assertEqual(row["progression"], "worsening/crescendo")
        self.assertEqual(row["trigger"], "progressively less exertion")
        self.assertEqual(row["duration"], "last 2 weeks")

    def test_e_e14_extracts_rest_context(self):
        self.assertTrue(hasattr(ev, "atomic_decompose"), "atomic_decompose missing")
        row = ev.atomic_decompose("E_14", "Do you have chest pain even at rest?", "Chest pain at rest")
        self.assertEqual(row["base_concept"], "Chest pain")
        self.assertEqual(row["trigger"], "rest")

    def test_e14_evidence_struct_keeps_base_and_rest_separate(self):
        raw = {"question_en": "Do you have chest pain even at rest?", "data_type": "B", "possible-values": []}
        vmap = {"E_14": {"base_concept": "Chest pain at rest"}}
        row = ev.evidence_struct("E_14", raw, vmap)
        self.assertEqual(row["base_concept"], "Chest pain")
        self.assertEqual(row["trigger"], "rest")

    def test_f_generic_pain_does_not_prove_larynx_pharynx_location(self):
        self.assertTrue(hasattr(ev, "location_observable"), "location_observable missing")
        atomic = {"base_concept": "Pain", "location": "", "original_question": "Do you feel pain somewhere?"}
        self.assertFalse(ev.location_observable("larynx vs pharynx", atomic))

    def test_g_hoarseness_does_not_prove_temporal_course(self):
        self.assertTrue(hasattr(ev, "course_observable"), "course_observable missing")
        atomic = {"base_concept": "Hoarseness", "duration": "", "onset": "", "progression": "", "original_question": "Is your voice hoarse?"}
        self.assertFalse(ev.course_observable("worse for 3 days then resolves in 1-2 weeks", atomic))

    def test_h_partial_is_excluded_from_strict(self):
        got = ev.coverage_counts([{"mapping_status": x} for x in ["DIRECT_MATCH", "ATTRIBUTE_MATCH", "PARTIAL_MATCH", "NO_MATCH"]])
        self.assertEqual(got["strict_coverage"], 0.5)

    def test_i_file_snapshot_detects_no_change(self):
        self.assertTrue(hasattr(ev, "snapshot_files"), "snapshot_files missing")
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "f"
            p.write_text("frozen", encoding="utf-8")
            before = ev.snapshot_files([p])
            after = ev.snapshot_files([p])
            self.assertEqual(before, after)

    def test_pair_key_matches_regardless_of_order(self):
        self.assertTrue(hasattr(ev, "pair_keys_equal"), "pair_keys_equal missing")
        self.assertTrue(ev.pair_keys_equal("Stable angina", "Unstable angina", "Unstable angina", "Stable angina"))

    def test_semicolon_fact_ids_are_split(self):
        self.assertTrue(hasattr(ev, "split_fact_ids"), "split_fact_ids missing")
        self.assertEqual(ev.split_fact_ids(["D05_F001;D05_F004; D05_F014"]), {"D05_F001", "D05_F004", "D05_F014"})


if __name__ == "__main__":
    unittest.main()
