import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import step15v2_evaluate as ev


class EvaluatorTests(unittest.TestCase):
    def test_forbidden_and_test_patient_paths_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            reader = ev.AuditedReader(Path(td))
            for rel in [".claude/MEMORY.md", "exp/step14_value_context_recovery/STEP14_REPORT.md", "data/ddxplus/en/release_test_patients"]:
                with self.assertRaises(ev.IndependenceError):
                    reader.resolve(rel)

    def test_freeze_mismatch_stops_evaluation(self):
        with tempfile.TemporaryDirectory() as td:
            profile = Path(td) / "profile"
            profile.mkdir()
            (profile / "a.csv").write_text("original", encoding="utf-8")
            freeze = {"file_sha256": {"a.csv": ev.sha256_file(profile / "a.csv")}}
            (profile / "PROFILE_FREEZE_V2.json").write_text(json.dumps(freeze), encoding="utf-8")
            (profile / "a.csv").write_text("changed", encoding="utf-8")
            with self.assertRaisesRegex(ev.InvalidFreezeError, "STEP15V2_EVAL_INVALID_FREEZE"):
                ev.verify_freeze(profile, ["a.csv"])

    def test_mapping_statuses_are_conservative(self):
        cases = [
            ({"base_concept": "Cough"}, {"base_concept": "Cough"}, "DIRECT_MATCH"),
            ({"base_concept": "Chest pain", "trigger": "exertion"}, {"base_concept": "Chest pain", "trigger": "exertion"}, "ATTRIBUTE_MATCH"),
            ({"base_concept": "Chest pain", "trigger": "exertion"}, {"base_concept": "Chest pain", "trigger": "rest"}, "PARTIAL_MATCH"),
            ({"base_concept": "Fever"}, {"base_concept": "Cough"}, "NO_MATCH"),
            ({"base_concept": "Age", "not_applicable": True}, {"base_concept": "Age"}, "NOT_APPLICABLE"),
        ]
        for evidence, fact, want in cases:
            with self.subTest(want=want):
                self.assertEqual(ev.classify_match(evidence, fact)[0], want)

    def test_partial_is_excluded_from_strict_and_not_applicable_from_denominator(self):
        rows = [{"mapping_status": x} for x in ["DIRECT_MATCH", "ATTRIBUTE_MATCH", "PARTIAL_MATCH", "NO_MATCH", "NOT_APPLICABLE"]]
        got = ev.coverage_counts(rows)
        self.assertEqual(got["total_relevant_evidence"], 4)
        self.assertEqual(got["strict_coverage"], 0.5)
        self.assertEqual(got["lenient_coverage"], 0.75)

    def test_medically_discriminative_can_be_unobservable(self):
        got = ev.observability_record("duration >= 12 weeks", [], True)
        self.assertTrue(got["medically_discriminative"])
        self.assertFalse(got["experimentally_observable"])

    def test_patient_stats_count_zero_matchable(self):
        got = ev.patient_observability_stats([["E_1", "E_2"], ["E_9"]], {"E_1", "E_2"})
        self.assertEqual(got, {"patient_count": 2, "mean_visible_evidence": 1.5, "mean_profile_matchable": 1.0, "median_profile_matchable": 1.0, "zero_matchable_rate": 0.5})

    def test_request_names_resolve_to_frozen_csv_names(self):
        facts = {
            "Acute HIV infection": [{"fact_id": "H1"}],
            "PSVT": [{"fact_id": "P1"}],
        }
        self.assertEqual(ev.facts_for_disease(facts, "Acute / initial HIV infection")[0]["fact_id"], "H1")
        self.assertEqual(ev.facts_for_disease(facts, "Paroxysmal supraventricular tachycardia (PSVT)")[0]["fact_id"], "P1")

    def test_pair_features_come_only_from_explicit_frozen_labels(self):
        text = (
            "DURATION: acute <12 weeks vs chronic >=12 weeks. "
            "ONSET: acute sudden vs chronic lingering. "
            "Shared symptoms are not discriminating. "
            "OBJECTIVE: chronic requires CT evidence."
        )
        got = ev.split_pair_features(text)
        self.assertEqual([x[0] for x in got], ["DURATION", "ONSET", "OBJECTIVE"])
        self.assertIn("Shared symptoms", got[1][1])


if __name__ == "__main__":
    unittest.main()
