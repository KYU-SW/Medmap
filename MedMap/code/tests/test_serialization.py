"""세션 JSON 계약(v1) 회귀 테스트 — 왕복 불변성·검증 실패·세션 재개."""
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from medmap import (AnswerStatus, DiagnosisEngine, EvidenceCatalog, NextInformationEngine, PatientState,
                    negative, not_applicable, positive, unknown, value)
from medmap.question_presentation import QuestionPresenter
from medmap.serialization import (ANSWER_SCHEMA_VERSION, SESSION_SCHEMA_VERSION, TURN_SCHEMA_VERSION,
                                  SessionValidationError, UnsupportedSchemaVersion, deserialize_patient_state,
                                  deserialize_session, dumps_patient_state, loads_patient_state,
                                  parse_answer_submission, serialize_patient_state, serialize_turn)

CATALOG = EvidenceCatalog()
PRESENTER = QuestionPresenter(CATALOG)
ENGINE = NextInformationEngine(DiagnosisEngine(CATALOG, "k3"), presenter=PRESENTER)


def roundtrip(state, model_context="k3"):
    return deserialize_session(json.loads(json.dumps(serialize_patient_state(state, model_context))), CATALOG)


class RoundTripTests(unittest.TestCase):
    def test_01_empty_state(self):
        state = PatientState.new(30, "F")
        snapshot = roundtrip(state)
        self.assertEqual(snapshot.state, state)
        self.assertEqual(snapshot.state.answers, {})

    def test_02_positive(self):
        state = PatientState.new(30, "F", "E_53")
        self.assertIs(roundtrip(state).state.answers["E_53"].status, AnswerStatus.POSITIVE)

    def test_03_negative(self):
        state = PatientState.new(30, "F", None, {"E_155": negative()})
        self.assertIs(roundtrip(state).state.answers["E_155"].status, AnswerStatus.NEGATIVE)

    def test_04_unknown(self):
        state = PatientState.new(30, "F", None, {"E_155": unknown()})
        restored = roundtrip(state).state
        self.assertIs(restored.answers["E_155"].status, AnswerStatus.UNKNOWN)
        self.assertIsNot(restored.answers["E_155"].status, AnswerStatus.NEGATIVE)

    def test_04b_not_applicable(self):
        state = PatientState.new(30, "F", "E_129", {"E_130": not_applicable()})
        self.assertIs(roundtrip(state).state.answers["E_130"].status, AnswerStatus.NOT_APPLICABLE)

    def test_05_single_value(self):
        state = PatientState.new(30, "F", "E_129", {"E_130": value("V_156")})
        self.assertEqual(roundtrip(state).state.answers["E_130"].values, ("V_156",))

    def test_06_multi_value(self):
        state = PatientState.new(30, "F", "E_53", {"E_54": value("V_181", "V_183")})
        self.assertEqual(roundtrip(state).state.answers["E_54"].values, ("V_181", "V_183"))
        payload = serialize_patient_state(state)["patient_state"]["answers"][-1]
        self.assertIsInstance(payload["value"], list)          # VALUE 는 항상 배열

    def test_07_asked_order_is_preserved(self):
        state = PatientState.new(45, "M", "E_53", {"E_55": value("V_89"), "E_155": negative(), "E_0": unknown()})
        restored = roundtrip(state).state
        self.assertEqual(restored.asked, state.asked)
        self.assertEqual(restored.n_additional, state.n_additional)
        self.assertEqual(restored.initial_evidence, "E_53")

    def test_08_model_context_is_preserved(self):
        state = PatientState.new(45, "M", "E_53")
        for context in ("k3", "k5", "k10"):
            self.assertEqual(roundtrip(state, context).model_context, context)

    def test_08b_unasked_is_not_serialized(self):
        payload = serialize_patient_state(PatientState.new(45, "M", "E_53"))["patient_state"]
        self.assertEqual([a["question_id"] for a in payload["answers"]], ["E_53"])
        self.assertNotIn("E_91", json.dumps(payload))

    def test_08c_text_helpers_round_trip(self):
        state = PatientState.new(45, "M", "E_53", {"E_55": value("V_89")})
        self.assertEqual(loads_patient_state(dumps_patient_state(state, "k5"), CATALOG).state, state)


class ValidationTests(unittest.TestCase):
    def payload(self, **overrides):
        data = serialize_patient_state(PatientState.new(45, "M", "E_53"), "k3")
        data["patient_state"].update(overrides)
        return data

    def test_09_unsupported_schema_version_is_rejected(self):
        data = self.payload()
        data["schema_version"] = "medmap-session-v2"
        with self.assertRaises(UnsupportedSchemaVersion):
            deserialize_session(data, CATALOG)
        with self.assertRaises(UnsupportedSchemaVersion):
            parse_answer_submission({"schema_version": "x", "question_id": "E_155",
                                     "answer": {"kind": "NEGATIVE", "value": None}}, CATALOG)

    def test_10_unknown_evidence_id_is_rejected(self):
        with self.assertRaises(SessionValidationError):
            deserialize_session(self.payload(answers=[{"question_id": "E_9999", "kind": "POSITIVE", "value": None}],
                                             asked_question_ids=["E_9999"], n_additional_questions=1), CATALOG)
        with self.assertRaises(SessionValidationError):
            parse_answer_submission({"question_id": "NOPE", "answer": {"kind": "POSITIVE", "value": None}}, CATALOG)

    def test_11_unknown_value_id_is_rejected(self):
        with self.assertRaises(SessionValidationError):
            parse_answer_submission({"question_id": "E_130", "answer": {"kind": "VALUE", "value": ["V_NOPE"]}}, CATALOG)

    def test_12_answer_kind_must_match_the_question_type(self):
        with self.assertRaises(SessionValidationError):
            parse_answer_submission({"question_id": "E_155", "answer": {"kind": "VALUE", "value": ["V_10"]}}, CATALOG)
        with self.assertRaises(SessionValidationError):
            parse_answer_submission({"question_id": "E_130", "answer": {"kind": "POSITIVE", "value": None}}, CATALOG)
        with self.assertRaises(SessionValidationError):
            parse_answer_submission({"question_id": "E_155", "answer": {"kind": "NEGATIVE", "value": ["V_10"]}}, CATALOG)
        with self.assertRaises(SessionValidationError):
            parse_answer_submission({"question_id": "E_155", "answer": {"kind": "MAYBE", "value": None}}, CATALOG)

    def test_13_excluded_questions_cannot_be_submitted_or_restored(self):
        for excluded in ("E_134", "E_152"):
            with self.assertRaises(SessionValidationError):
                parse_answer_submission({"question_id": excluded, "answer": {"kind": "VALUE", "value": ["0"]}}, CATALOG)
            with self.assertRaises(SessionValidationError):
                deserialize_session(self.payload(answers=[{"question_id": excluded, "kind": "VALUE", "value": ["0"]}],
                                                 asked_question_ids=[excluded], n_additional_questions=1), CATALOG)

    def test_14_parent_gate_violation_is_rejected(self):
        closed = PatientState.new(45, "M", None, {"E_129": negative()})
        with self.assertRaises(SessionValidationError):
            parse_answer_submission({"question_id": "E_130", "answer": {"kind": "VALUE", "value": ["V_156"]}},
                                    CATALOG, closed)
        with self.assertRaises(SessionValidationError):   # 저장된 세션 자체가 gate 를 어긴 경우
            deserialize_session(self.payload(
                answers=[{"question_id": "E_129", "kind": "NEGATIVE", "value": None},
                         {"question_id": "E_130", "kind": "VALUE", "value": ["V_156"]}],
                asked_question_ids=["E_129", "E_130"], initial_evidence=None, n_additional_questions=2), CATALOG)

    def test_14b_duplicate_answer_and_bad_scalars_are_rejected(self):
        state = PatientState.new(45, "M", "E_53")
        with self.assertRaises(SessionValidationError):
            parse_answer_submission({"question_id": "E_53", "answer": {"kind": "POSITIVE", "value": None}}, CATALOG, state)
        for bad in ({"age": -1}, {"age": "45"}, {"sex": "X"}, {"model_context": "k7"}):
            with self.assertRaises(SessionValidationError):
                deserialize_session(self.payload(**bad), CATALOG)


class TurnSerializationTests(unittest.TestCase):
    def state(self):
        return PatientState.new(45, "M", "E_53", {"E_55": value("V_89"), "E_56": value("2"), "E_204": value("V_10")})

    def test_15_turn_is_serialized_with_public_fields(self):
        payload = serialize_turn(ENGINE.start(self.state()))
        self.assertEqual(payload["schema_version"], TURN_SCHEMA_VERSION)
        self.assertEqual(len(payload["diagnoses"]), 3)
        self.assertEqual(set(payload["diagnoses"][0]), {"name", "probability"})
        self.assertIn("question_ko", payload["next_question"])
        self.assertIsNone(payload["stop_reason"])
        self.assertEqual(payload["session"]["schema_version"], SESSION_SCHEMA_VERSION)
        json.dumps(payload)                       # 표준 json 으로 직렬화 가능

    def test_16_full_posterior_is_hidden_unless_debug(self):
        turn = ENGINE.start(self.state())
        public = serialize_turn(turn)
        self.assertNotIn("debug", public)
        self.assertEqual(len(public["diagnoses"]), 3)
        self.assertNotIn("probabilities", json.dumps(public))
        debug = serialize_turn(turn, include_debug=True)
        self.assertEqual(len(debug["debug"]["posterior"]), len(ENGINE.diagnosis.classes))
        self.assertNotIn("posterior", json.dumps(public["session"]))   # 세션에는 posterior 미저장

    def test_16b_session_json_has_no_identifying_fields(self):
        text = json.dumps(serialize_turn(ENGINE.start(self.state()))["session"])
        for forbidden in ["name", "phone", "address", "patient_id", "ssn"]:
            self.assertNotIn(forbidden, text)


class ResumeTests(unittest.TestCase):
    def test_17_18_19_save_restore_and_continue_is_identical(self):
        state = PatientState.new(45, "M", "E_53", {"E_55": value("V_89"), "E_56": value("2"), "E_204": value("V_10")})
        first = ENGINE.start(state)
        qid = first.next_question.evidence_id
        answered = ENGINE.answer(first, qid, PRESENTER.to_answer(qid, "타는 듯한"))

        text = dumps_patient_state(answered.state, "k3")
        del state, first
        snapshot = loads_patient_state(text, CATALOG)
        restored = NextInformationEngine(DiagnosisEngine(CATALOG, snapshot.model_context),
                                         presenter=PRESENTER).start(snapshot.state)

        self.assertEqual(snapshot.state, answered.state)
        self.assertEqual(restored.diagnoses.probabilities, answered.diagnoses.probabilities)      # 17
        self.assertEqual([d for d, _ in restored.diagnoses.top3], [d for d, _ in answered.diagnoses.top3])
        self.assertEqual(restored.next_question.evidence_id, answered.next_question.evidence_id)  # 18
        self.assertAlmostEqual(restored.next_question.information_gain,
                               answered.next_question.information_gain, places=12)                # 19
        next_id = restored.next_question.evidence_id
        submission = {"schema_version": ANSWER_SCHEMA_VERSION, "question_id": next_id,
                      "answer": {"kind": "VALUE", "value": ["V_123"]}}
        parsed_id, parsed_answer = parse_answer_submission(submission, CATALOG, restored.state)
        continued = ENGINE.answer(restored, parsed_id, parsed_answer)
        direct = ENGINE.answer(answered, next_id, PRESENTER.to_answer(next_id, "V_123"))
        self.assertEqual(continued.diagnoses.probabilities, direct.diagnoses.probabilities)
        self.assertEqual(continued.next_question.evidence_id, direct.next_question.evidence_id)

    def test_20_presentation_layer_still_works_after_restore(self):
        state = PatientState.new(45, "M", "E_53", {"E_55": value("V_89")})
        snapshot = loads_patient_state(dumps_patient_state(state, "k3"), CATALOG)
        view = serialize_turn(ENGINE.start(snapshot.state))["next_question"]
        self.assertIn("question_ko", view)
        self.assertIn("choices", view)
        self.assertNotIn(view["question_id"], ("E_134", "E_152"))


if __name__ == "__main__":
    unittest.main()
