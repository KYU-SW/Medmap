"""medmap/doctor_view.py 단위 테스트 (medmap-doctor-view-v1).

실행: ~/ai_env/bin/python -m unittest tests.test_doctor_view
모델을 로딩하지 않는다: 합성 DiagnosisResult·turn payload 로 투영만 검사한다.
계약: docs/superpowers/specs/2026-09-29-medmap-doctor-mode-foundation.md §6-2·§7-2·§11
"""
import copy
import json
import sys
import unittest
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

from medmap import EvidenceCatalog
from medmap import doctor_view
from medmap.clinical_summary import TerminologyLabelProvider, build_clinical_summary
from medmap.diagnosis import DiagnosisResult
from medmap.question_presentation import QuestionPresenter
from medmap.serialization import deserialize_session

CATALOG = EvidenceCatalog()
LABELS = TerminologyLabelProvider(CATALOG, QuestionPresenter(CATALOG))
FIXTURES = ROOT / "medmap-web" / "src" / "test" / "fixtures"
TURN = json.loads((FIXTURES / "turn.start.json").read_text(encoding="utf-8"))
CLASSES = sorted(json.loads((ROOT / "medmap" / "data" / "terminology_ko.json").read_text(encoding="utf-8"))["diseases"])


def ranking_result(n=12):
    """내림차순 합성 ranking(49 class 중 앞 n 개에 확률, 나머지 0에 가깝게)."""
    probs = [0.3, 0.2, 0.12, 0.09, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01, 0.01][:n]
    rest = (1.0 - sum(probs)) / (len(CLASSES) - len(probs))
    pairs = [(c, p) for c, p in zip(CLASSES, probs)] + [(c, rest) for c in CLASSES[len(probs):]]
    return DiagnosisResult({c: p for c, p in pairs}, tuple(pairs), "k3")


def view(wd, turn=TURN, diagnoses=None):
    return doctor_view.build_doctor_view(turn_payload=turn, diagnoses=diagnoses or ranking_result(),
                                         working_diagnosis=doctor_view.parse_working_diagnosis(wd, CLASSES),
                                         labels=LABELS)


def walk(obj, path=""):
    if isinstance(obj, dict):
        for key, value in obj.items():
            yield f"{path}.{key}", key, value
            yield from walk(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            yield f"{path}[{i}]", None, value
            yield from walk(value, f"{path}[{i}]")


class ParseWorkingDiagnosisTest(unittest.TestCase):
    def test_states(self):
        self.assertEqual(doctor_view.parse_working_diagnosis({"state": "PENDING"}, CLASSES), {"state": "PENDING", "value": None})
        self.assertEqual(doctor_view.parse_working_diagnosis({"state": "SKIPPED"}, CLASSES), {"state": "SKIPPED", "value": None})
        entered = doctor_view.parse_working_diagnosis(
            {"state": "ENTERED", "value": {"kind": "CATALOG", "code": CLASSES[0]}}, CLASSES)
        self.assertEqual(entered["value"]["code"], CLASSES[0])
        out = doctor_view.parse_working_diagnosis(
            {"state": "ENTERED", "value": {"kind": "OUT_OF_SCOPE", "label": "  급성 충수염  "}}, CLASSES)
        self.assertEqual(out["value"], {"kind": "OUT_OF_SCOPE", "code": None, "label": "급성 충수염"})

    def test_invalid(self):
        bad = [None, {}, {"state": "DONE"}, {"state": "ENTERED"}, {"state": "PENDING", "value": {"kind": "CATALOG"}},
               {"state": "ENTERED", "value": {"kind": "CATALOG", "code": "Not a disease"}},
               {"state": "ENTERED", "value": {"kind": "OUT_OF_SCOPE", "label": ""}},
               {"state": "ENTERED", "value": {"kind": "OUT_OF_SCOPE", "label": "   "}},
               {"state": "ENTERED", "value": {"kind": "OUT_OF_SCOPE", "label": "x" * 81}},
               {"state": "ENTERED", "value": {"kind": "OUT_OF_SCOPE", "label": "a\nb"}},
               {"state": "ENTERED", "value": {"kind": "OUT_OF_SCOPE", "label": 3}},
               {"state": "ENTERED", "value": {"kind": "OTHER", "code": CLASSES[0]}}]
        for raw in bad:
            with self.subTest(raw=raw), self.assertRaisesRegex(ValueError, "MEDMAP_INVALID_WORKING_DIAGNOSIS"):
                doctor_view.parse_working_diagnosis(raw, CLASSES)


class BuildDoctorViewTest(unittest.TestCase):
    def test_keys_and_schema(self):
        out = view({"state": "SKIPPED"})
        self.assertEqual(tuple(out), doctor_view.DOCTOR_VIEW_KEYS)
        self.assertEqual(out["schema_version"], "medmap-doctor-view-v1")
        self.assertEqual(out["session"], TURN["session"])

    def test_pending_is_blind(self):
        out = view({"state": "PENDING"})
        self.assertEqual(out["independent_assessment"], {"status": "LOCKED"})
        self.assertEqual(out["next_information"], {"status": "LOCKED"})
        text = json.dumps(out, ensure_ascii=False)
        for name in CLASSES[:8]:
            self.assertNotIn(f'"{name}"', text)
        self.assertNotIn(TURN["next_question"]["question_id"], json.dumps(out["next_information"]))

    def test_no_probability_or_score_anywhere(self):
        for wd in ({"state": "PENDING"}, {"state": "SKIPPED"}):
            out = view(wd)
            for path, key, value in walk(out):
                self.assertNotIn(key, {"probability", "information_gain", "posterior", "score", "confidence"}, path)
                self.assertNotIsInstance(value, float, path)

    def test_candidates_are_ranking_order_max_8(self):
        result = ranking_result()
        out = view({"state": "SKIPPED"}, diagnoses=result)
        cands = out["independent_assessment"]["candidates"]
        self.assertEqual([c["code"] for c in cands], [name for name, _ in result.ranking[:8]])
        self.assertEqual(len(cands), doctor_view.DOCTOR_CANDIDATES_MAX)
        for cand in cands:
            self.assertEqual(set(cand), {"code", "label_ko"})
            self.assertEqual(cand["label_ko"], LABELS.diagnosis(cand["code"])[0])
        self.assertEqual(out["independent_assessment"]["model"], {"context": "k3"})
        self.assertIn("49", out["independent_assessment"]["scope_ko"])

    def test_next_question_strips_numbers(self):
        out = view({"state": "SKIPPED"})
        info = out["next_information"]
        self.assertEqual(info["status"], "QUESTION")
        question = info["question"]
        self.assertEqual(question["question_id"], TURN["next_question"]["question_id"])
        self.assertEqual(set(question), set(doctor_view.QUESTION_KEYS))
        self.assertEqual(question["choices"], TURN["next_question"]["choices"])
        self.assertEqual(info["max_questions"], TURN["max_questions"])
        self.assertEqual(info["questions_used"], TURN["questions_asked_in_session"])

    def test_stop_reasons(self):
        for stop, status in (("MAX_QUESTIONS", "BUDGET_REACHED"), ("NO_ELIGIBLE_QUESTION", "NONE_ELIGIBLE"),
                             ("UNSUPPORTED_SESSION_SHAPE", "UNSUPPORTED_SESSION_SHAPE")):
            turn = copy.deepcopy(TURN)
            turn["next_question"], turn["stop_reason"] = None, stop
            info = view({"state": "SKIPPED"}, turn=turn)["next_information"]
            self.assertEqual(info["status"], status)
            self.assertIsNone(info["question"])

    def test_patient_summary_reuses_clinical_summary(self):
        out = view({"state": "PENDING"})     # 환자 요약은 blind 대상이 아니다
        snapshot = deserialize_session(TURN["session"], CATALOG)
        expected = build_clinical_summary(snapshot.state, snapshot.model_context, [], labels=LABELS)
        summary = out["patient_summary"]
        self.assertEqual(summary["age"], 45)
        self.assertEqual(summary["sex"], "M")
        for key in doctor_view.SUMMARY_FIELDS:
            self.assertEqual(summary[key], expected[key], key)
        self.assertNotIn("diagnosis_candidates", summary)

    def test_working_diagnosis_echo(self):
        out = view({"state": "ENTERED", "value": {"kind": "CATALOG", "code": CLASSES[3]}})
        self.assertEqual(out["working_diagnosis"]["state"], "ENTERED")
        self.assertEqual(out["working_diagnosis"]["value"]["label"], LABELS.diagnosis(CLASSES[3])[0])
        oos = view({"state": "ENTERED", "value": {"kind": "OUT_OF_SCOPE", "label": "급성 충수염"}})
        self.assertEqual(oos["working_diagnosis"]["value"], {"kind": "OUT_OF_SCOPE", "code": None, "label": "급성 충수염"})
        # 비교·일치 판정 키가 없다
        for path, key, _ in walk(oos):
            self.assertNotIn(key, {"match", "rank", "agreement", "discrepancy", "coverage_score"}, path)

    def test_extensions_not_available(self):
        ext = view({"state": "SKIPPED"})["extensions"]
        self.assertEqual(set(ext), set(doctor_view.EXTENSION_REASONS))
        for name, slot in ext.items():
            self.assertEqual(slot, {"status": "NOT_AVAILABLE", "reason": doctor_view.EXTENSION_REASONS[name]})

    def test_deterministic_and_input_untouched(self):
        turn = copy.deepcopy(TURN)
        a = view({"state": "SKIPPED"}, turn=turn)
        b = view({"state": "SKIPPED"}, turn=turn)
        self.assertEqual(a, b)
        self.assertEqual(turn, TURN)


if __name__ == "__main__":
    unittest.main()
