"""Clinical Summary(medmap-clinical-summary-v1) 테스트 — 모델 없이 EvidenceCatalog + 정적 라벨만 사용.

summary 는 PatientState(+ 최종 Turn 의 top3)의 결정적 투영이다. 세션에 없는 정보(intake cache,
bootstrap UNKNOWN, 원문)는 만들지 않는다.
"""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medmap import EvidenceCatalog, PatientState, negative, not_applicable, positive, unknown, value
from medmap import api as api_module
from medmap.clinical_summary import (CLINICAL_SUMMARY_SCHEMA_VERSION, DISCLAIMER_KO, SUMMARY_KEYS,
                                     PresenterLabelProvider, build_clinical_summary, questions_used,
                                     summary_from_session, summary_from_turn_payload)
from medmap.serialization import (SessionValidationError, UnsupportedSchemaVersion, deserialize_session,
                                  serialize_patient_state)

CATALOG = EvidenceCatalog()
LABELS = PresenterLabelProvider(CATALOG)
FIXTURE = ROOT / "tests" / "fixtures" / "clinical_summary_turn_answer3.json"
WEB_FIXTURE = ROOT / "medmap-web" / "src" / "test" / "fixtures" / "turn.answer3.json"
TOP3 = [("URTI", 0.4), ("PSVT", 0.2), ("Anemia", 0.1)]

EXPECTED_KEYS = ["schema_version", "chief_complaint", "confirmed_positive", "confirmed_negative",
                 "confirmed_values", "not_applicable", "unknown", "answered_questions",
                 "diagnosis_candidates", "questions_used", "disclaimer"]
FORBIDDEN_WORDS = ["최종 진단", "최종진단", "final diagnosis", "final_diagnosis", "진단했습니다",
                   "진단 결과입니다", "확진", "1위", "2위", "3위"]
FORBIDDEN_KEYS = {"information_gain", "matched_text", "text", "transcript", "posterior", "candidates",
                  "final_diagnosis", "diagnosis"}


def load_turn():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def mixed_state():
    """initial + POSITIVE/NEGATIVE/VALUE/NA/UNKNOWN 이 섞인 합성 상태(부모 gate 는 검증하지 않는 경로)."""
    return PatientState.new(30, "F", "E_53", {
        "E_66": positive(), "E_155": negative(), "E_55": value("V_89", "V_101"),
        "E_56": not_applicable(), "E_91": unknown(), "E_146": negative(),
    })


def ids(items):
    return [item["question_id"] for item in items]


def walk_keys(obj):
    if isinstance(obj, dict):
        for key, val in obj.items():
            yield key
            yield from walk_keys(val)
    elif isinstance(obj, list):
        for val in obj:
            yield from walk_keys(val)


class SchemaTests(unittest.TestCase):
    def test_01_key_order_and_version(self):
        summary = build_clinical_summary(mixed_state(), "k3", TOP3, labels=LABELS)
        self.assertEqual(list(summary), EXPECTED_KEYS)
        self.assertEqual(list(SUMMARY_KEYS), EXPECTED_KEYS)
        self.assertEqual(summary["schema_version"], "medmap-clinical-summary-v1")
        self.assertEqual(CLINICAL_SUMMARY_SCHEMA_VERSION, "medmap-clinical-summary-v1")

    def test_02_disclaimer_exact(self):
        summary = build_clinical_summary(mixed_state(), "k3", TOP3, labels=LABELS)
        expected = ("현재까지 입력하고 확인한 내용을 진료 전 참고용으로 정리한 것입니다.\n"
                    "진단 결과가 아니며, 진단에는 의료진의 평가가 필요합니다.")
        self.assertEqual(summary["disclaimer"], expected)
        self.assertEqual(DISCLAIMER_KO, expected)

    def test_03_forbidden_wording_and_keys(self):
        summary = summary_from_turn_payload(load_turn(), catalog=CATALOG, labels=LABELS)
        text = json.dumps(summary, ensure_ascii=False)
        for word in FORBIDDEN_WORDS:
            self.assertNotIn(word, text, word)
        self.assertNotIn("MEDMAP_", text)
        self.assertFalse(FORBIDDEN_KEYS & set(walk_keys(summary)), FORBIDDEN_KEYS & set(walk_keys(summary)))


class ChiefComplaintTests(unittest.TestCase):
    def test_04_initial_is_chief_complaint(self):
        summary = build_clinical_summary(mixed_state(), "k3", TOP3, labels=LABELS)
        chief = summary["chief_complaint"]
        self.assertEqual(chief["question_id"], "E_53")
        self.assertEqual(chief["status"], "POSITIVE")
        self.assertEqual(chief["label_ko"], "통증")
        self.assertEqual(chief["answer_ko"], "예")
        self.assertFalse(chief["is_fallback"])
        self.assertNotIn("E_53", ids(summary["confirmed_positive"]))

    def test_05_no_initial_gives_null(self):
        state = PatientState.new(30, "F", None, {"E_66": positive()})
        summary = build_clinical_summary(state, "k3", TOP3, labels=LABELS)
        self.assertIsNone(summary["chief_complaint"])
        self.assertEqual(ids(summary["confirmed_positive"]), ["E_66"])


class PartitionTests(unittest.TestCase):
    def setUp(self):
        self.summary = build_clinical_summary(mixed_state(), "k3", TOP3, labels=LABELS)

    def test_06_status_partition(self):
        s = self.summary
        self.assertEqual(ids(s["confirmed_positive"]), ["E_66"])
        self.assertEqual(ids(s["confirmed_negative"]), ["E_155", "E_146"])
        self.assertEqual(ids(s["confirmed_values"]), ["E_55"])
        self.assertEqual(ids(s["not_applicable"]), ["E_56"])
        self.assertEqual(ids(s["unknown"]), ["E_91"])
        self.assertEqual(ids(s["answered_questions"]),
                         ["E_53", "E_66", "E_155", "E_55", "E_56", "E_91", "E_146"])
        parts = sum((ids(s[k]) for k in ("confirmed_positive", "confirmed_negative", "confirmed_values",
                                         "not_applicable", "unknown")), [])
        self.assertEqual(sorted(parts), sorted(ids(s["answered_questions"])[1:]))

    def test_07_unknown_is_not_negative(self):
        item = self.summary["unknown"][0]
        self.assertEqual(item["status"], "UNKNOWN")
        self.assertEqual(item["answer_ko"], "잘 모르겠어요")
        self.assertNotIn("E_91", ids(self.summary["confirmed_negative"]))

    def test_08b_asked_without_answer_rejected(self):
        # PatientState.__post_init__ 은 answers ⊆ asked 만 검사하므로 asked 에만 있는 상태를 만들 수 있다.
        state = PatientState(age=30, sex="F", initial_evidence="E_53",
                             answers={"E_53": positive()}, asked=("E_53", "E_66"))
        with self.assertRaises(ValueError) as ctx:
            build_clinical_summary(state, "k3", TOP3, labels=LABELS)
        self.assertEqual(str(ctx.exception), "MEDMAP_SUMMARY_ASKED_WITHOUT_ANSWER:E_66")

    def test_08_unasked_never_listed(self):
        text = json.dumps(self.summary, ensure_ascii=False)
        for unasked in ("E_201", "E_175", "E_88", "E_129"):
            self.assertNotIn(f'"{unasked}"', text)

    def test_09_value_labels(self):
        item = self.summary["confirmed_values"][0]
        self.assertEqual(item["values"], ["V_89", "V_101"])
        self.assertEqual(item["answer_ko"], "이마, 위쪽 가슴")
        self.assertEqual(self.summary["not_applicable"][0]["answer_ko"], "해당 없음")
        self.assertEqual(self.summary["confirmed_positive"][0]["values"], [])

    def test_10_scale_value_is_number_string(self):
        state = PatientState.new(30, "F", "E_53", {"E_56": value("7")})
        item = build_clinical_summary(state, "k3", TOP3, labels=LABELS)["confirmed_values"][0]
        self.assertEqual(item["answer_ko"], "7")
        self.assertFalse(item["is_fallback"])

    def test_11_english_fallback_flagged(self):
        # 한국어 질문이 없는 evidence 는 원문 + is_fallback=True 로 표시한다. 정본이 전 질문을 한국어화했으므로
        # (C, 2026-09-27) E_146 한국어 문구를 뺀 합성 라벨 파일로 fallback 경로를 고정한다.
        import tempfile
        from medmap.question_presentation import LABELS_PATH, QuestionPresenter
        data = json.loads(Path(LABELS_PATH).read_text(encoding="utf-8"))
        data["questions"].pop("E_146")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.json"
            path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            labels = PresenterLabelProvider(CATALOG, QuestionPresenter(CATALOG, path))
            summary = build_clinical_summary(mixed_state(), "k3", TOP3, labels=labels)
        item = [i for i in summary["confirmed_negative"] if i["question_id"] == "E_146"][0]
        self.assertTrue(item["is_fallback"])
        self.assertEqual(item["question_ko"], item["question_original"])
        self.assertTrue(item["question_original"].startswith("Are you taking"))
        korean = summary["confirmed_negative"][0]
        self.assertFalse(korean["is_fallback"])
        self.assertNotEqual(korean["question_ko"], korean["question_original"])
        # 실제 정본 기준으로는 같은 항목이 한국어다
        real = [i for i in self.summary["confirmed_negative"] if i["question_id"] == "E_146"][0]
        self.assertFalse(real["is_fallback"])
        self.assertIn("항응고제", real["question_ko"])


class QuestionsUsedTests(unittest.TestCase):
    def test_12_parity_with_api(self):
        for context in ("k3", "k5", "k10"):
            for n in range(0, 14):
                observed = {e: positive() for e in CATALOG.selectable_ids()
                            if CATALOG.question(e).answer_type == "BINARY" and e != "E_53"}
                chosen = dict(list(observed.items())[:n])
                state = PatientState.new(30, "F", "E_53", chosen)
                self.assertEqual(questions_used(state, context), api_module._questions_used(state, context),
                                 (context, n))

    def test_13_counts(self):
        self.assertEqual(build_clinical_summary(mixed_state(), "k3", TOP3, labels=LABELS)["questions_used"], 3)
        short = PatientState.new(30, "F", "E_53", {"E_66": positive()})
        self.assertIsNone(build_clinical_summary(short, "k3", TOP3, labels=LABELS)["questions_used"])


class CandidateTests(unittest.TestCase):
    def test_14_top3_only_in_given_order(self):
        five = TOP3 + [("GERD", 0.05), ("Bronchitis", 0.01)]
        cands = build_clinical_summary(mixed_state(), "k3", five, labels=LABELS)["diagnosis_candidates"]
        self.assertEqual([c["name"] for c in cands], ["URTI", "PSVT", "Anemia"])
        self.assertEqual(cands[0], {"name": "URTI", "display_name": "URTI", "is_fallback": True,
                                    "probability": 0.4})

    def test_15_accepts_turn_dicts_and_empty(self):
        dicts = [{"name": n, "probability": p} for n, p in TOP3]
        a = build_clinical_summary(mixed_state(), "k3", dicts, labels=LABELS)
        b = build_clinical_summary(mixed_state(), "k3", TOP3, labels=LABELS)
        self.assertEqual(a, b)
        self.assertEqual(build_clinical_summary(mixed_state(), "k3", [], labels=LABELS)["diagnosis_candidates"], [])

    def test_16b_malformed_tuple_candidate_rejected(self):
        for bad in ([("URTI",)], [("URTI", 0.4, "x")], [42], [None]):
            with self.assertRaises(ValueError) as ctx:
                build_clinical_summary(mixed_state(), "k3", bad, labels=LABELS)
            self.assertTrue(str(ctx.exception).startswith("MEDMAP_SUMMARY_INVALID_CANDIDATE"), bad)

    def test_16_unsorted_candidates_rejected(self):
        with self.assertRaises(ValueError):
            build_clinical_summary(mixed_state(), "k3", [("A", 0.1), ("B", 0.5)], labels=LABELS)
        with self.assertRaises(ValueError):
            build_clinical_summary(mixed_state(), "k3", [("A", 1.5)], labels=LABELS)


class SessionTurnTests(unittest.TestCase):
    def test_17_turn_payload_fixture(self):
        summary = summary_from_turn_payload(load_turn(), catalog=CATALOG, labels=LABELS)
        self.assertEqual(summary["questions_used"], 3)
        self.assertEqual(summary["chief_complaint"]["question_id"], "E_53")
        self.assertEqual(ids(summary["confirmed_values"]), ["E_55", "E_56", "E_204", "E_54", "E_57"])
        self.assertEqual(ids(summary["confirmed_negative"]), ["E_146"])
        self.assertEqual([c["name"] for c in summary["diagnosis_candidates"]],
                         ["URTI", "PSVT", "HIV (initial infection)"])
        self.assertEqual(summary["diagnosis_candidates"][0]["probability"], 0.3879264295101166)
        self.assertEqual(summary["confirmed_values"][0]["answer_ko"], "이마")

    def test_18_refresh_roundtrip_identical(self):
        turn = load_turn()
        original = summary_from_turn_payload(turn, catalog=CATALOG, labels=LABELS)
        snapshot = deserialize_session(turn["session"], CATALOG)
        stored = json.loads(json.dumps(serialize_patient_state(snapshot.state, snapshot.model_context)))
        resumed = summary_from_session(stored, turn["diagnoses"], catalog=CATALOG, labels=LABELS)
        self.assertEqual(json.dumps(resumed, ensure_ascii=False), json.dumps(original, ensure_ascii=False))

    def test_19_deterministic(self):
        a = summary_from_turn_payload(load_turn(), catalog=CATALOG, labels=LABELS)
        b = summary_from_turn_payload(load_turn(), catalog=CATALOG, labels=PresenterLabelProvider(CATALOG))
        self.assertEqual(json.dumps(a, ensure_ascii=False), json.dumps(b, ensure_ascii=False))

    def test_20_inputs_not_mutated(self):
        turn = load_turn()
        before = copy.deepcopy(turn)
        summary_from_turn_payload(turn, catalog=CATALOG, labels=LABELS)
        self.assertEqual(turn, before)
        state = mixed_state()
        frozen = (dict(state.answers), state.asked)
        build_clinical_summary(state, "k3", TOP3, labels=LABELS)
        self.assertEqual((dict(state.answers), state.asked), frozen)

    def test_21_invalid_session_propagates(self):
        turn = load_turn()
        bad = copy.deepcopy(turn["session"])
        bad["schema_version"] = "medmap-session-v0"
        with self.assertRaises(UnsupportedSchemaVersion):
            summary_from_session(bad, turn["diagnoses"], catalog=CATALOG, labels=LABELS)
        gate = copy.deepcopy(turn["session"])
        gate["patient_state"]["answers"][0]["kind"] = "NEGATIVE"      # E_53 음성 → 자식 E_55 부모 gate 위반
        gate["patient_state"]["initial_evidence"] = None
        with self.assertRaises(SessionValidationError):
            summary_from_session(gate, turn["diagnoses"], catalog=CATALOG, labels=LABELS)

    def test_22_turn_count_mismatch_rejected(self):
        turn = load_turn()
        turn["questions_asked_in_session"] = 2
        with self.assertRaises(ValueError):
            summary_from_turn_payload(turn, catalog=CATALOG, labels=LABELS)

    @unittest.skipUnless(WEB_FIXTURE.exists(), "frontend fixture 없음")
    def test_23_fixture_copy_identical(self):
        self.assertEqual(json.loads(FIXTURE.read_text(encoding="utf-8")),
                         json.loads(WEB_FIXTURE.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
