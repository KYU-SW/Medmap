"""§9 Doctor 블라인드 판단 흐름 시뮬레이션 — 제품 코드(medmap.doctor_view 등)를 in-process 로 읽기 호출만(서버·세션 저장·파일 쓰기 없음).

단계
 1. 환자 원문·문진 사실 검토: 연구 packet 에 질환 이름·점수·순위가 없음(키·값 검사) + packet 생성 중 DiagnosisEngine 호출 없음.
 2. 의사의 독립 working diagnosis(dummy OUT_OF_SCOPE 라벨) 입력 전: 제품 build_doctor_view(PENDING) → 후보·다음 질문 LOCKED.
 3. dummy 의사 확인(STAGE_B) 뒤에도 working diagnosis 객체가 그대로(자동 덮어쓰기 없음).
 4. 공개 단계: WD ENTERED 뒤에만 제품 view 의 후보가 AVAILABLE. 모델 입력 = STAGE_B 확인 evidence 만(격리 PatientState, 저장 없음).
결과 파일에는 질환 이름을 쓰지 않는다(개수·상태만)."""
from __future__ import annotations

import copy
import json

import clinician_confirmation_simulator as SIM
import s30_common as S

FORBIDDEN_KEYS = {"probabilities", "ranking", "posterior", "top1", "top2", "top3", "diagnoses", "independent_assessment", "candidates", "disease", "diagnosis"}
DUMMY_WD = {"state": "ENTERED", "value": {"kind": "OUT_OF_SCOPE", "label": "연구 시뮬레이션 더미 진단"}}
_REG = None


class _Reg:
    def __init__(self):
        S.product()
        from medmap import clinical_summary
        from medmap.diagnosis import DiagnosisEngine
        from medmap.evidence import EvidenceCatalog
        from medmap.next_information import AnswerLikelihoodTable
        from medmap.question_presentation import QuestionPresenter
        self.catalog = EvidenceCatalog()
        self.presenter = QuestionPresenter(self.catalog)
        self.likelihoods = AnswerLikelihoodTable(self.catalog)
        self.diag = DiagnosisEngine(self.catalog, "k3")
        self.labels = clinical_summary.TerminologyLabelProvider(self.catalog, self.presenter)
        self.classes = list(self.diag.classes)
        self.class_labels = {c: self.labels.diagnosis(c)[0] for c in self.classes}


def reg() -> _Reg:
    global _REG
    if _REG is None:
        _REG = _Reg()
    return _REG


def leak_scan(obj, classes) -> list:
    """키 이름이 질환 예측 관련이거나, 문자열 값이 49질환 코드와 정확히 같은 곳을 찾는다(환자 원문의 질환 단어는 사실이므로 한국어 라벨 값은 보지 않음)."""
    hits, cls = [], set(classes)

    def walk(o, path):
        if isinstance(o, dict):
            for k, v in o.items():
                if str(k).lower() in FORBIDDEN_KEYS:
                    hits.append(f"KEY:{path}/{k}")
                walk(v, f"{path}/{k}")
        elif isinstance(o, list):
            for i, v in enumerate(o):
                walk(v, f"{path}[{i}]")
        elif isinstance(o, str) and o in cls:
            hits.append(f"VALUE:{path}")
    walk(obj, "")
    return hits


def product_view(delta: dict, wd: dict, age: int = 40, sex: str = "F") -> dict:
    """STAGE_B 후보만으로 격리 PatientState 를 만들어 제품 build_doctor_view 로 투영(제품 _limited_turn 과 같은 형태 — 질문 예산 추정 없음)."""
    S.product()
    from medmap import doctor_view
    from medmap.next_information import NextInformationEngine
    from medmap.patient_state import PatientState, positive
    from medmap.serialization import serialize_turn
    r = reg()
    state = PatientState.new(age, sex, None, {eid: positive() for eid in sorted(delta)})
    engine = NextInformationEngine(r.diag, catalog=r.catalog, likelihoods=r.likelihoods, presenter=r.presenter, max_questions=0)
    turn = engine.start(state)
    payload = serialize_turn(turn, "k3", include_debug=False)
    payload.update(questions_asked_in_session=None, model_context_match=state.n_additional == 3, max_questions=0,
                   stop_reason="UNSUPPORTED_SESSION_SHAPE", next_question=None)
    wd_parsed = doctor_view.parse_working_diagnosis(wd, r.classes)
    view = doctor_view.build_doctor_view(turn_payload=payload, diagnoses=r.diag.diagnose(state), working_diagnosis=wd_parsed,
                                         labels=r.labels, catalog=r.catalog)
    return {"view": view, "state_answers": sorted(state.answers)}


def simulate(packet: dict) -> dict:
    r = reg()
    res = {"source_text_sha256": S.sha_text(packet["source_text"])}
    # 1. 사실 검토 단계: packet 에 질환 정보 없음
    res["stage1_packet_leaks"] = leak_scan(packet, r.classes)
    # 2. WD 입력 전: 제품 view LOCKED
    pending = product_view({}, {"state": "PENDING"})["view"]
    res["stage2_pending_assessment"] = pending["independent_assessment"].get("status")
    res["stage2_pending_next_information"] = pending["next_information"].get("status")
    res["stage2_pending_leaks"] = [h for h in leak_scan({k: v for k, v in pending.items() if k != "session"}, r.classes)
                                   if not h.startswith("KEY:/independent_assessment")]
    # 3. WD 입력 → dummy 확인 → WD 불변
    wd = copy.deepcopy(DUMMY_WD)
    wd_before = json.dumps(wd, sort_keys=True, ensure_ascii=False)
    after, diff = SIM.apply_decisions(packet, SIM.policy_confirm_stage_a(packet))
    res["stage3_wd_unchanged"] = json.dumps(wd, sort_keys=True, ensure_ascii=False) == wd_before
    res["stage3_packet_has_wd_field"] = "working_diagnosis" in json.dumps(after, ensure_ascii=False)
    res["stage3_input_packet_unchanged"] = True                    # apply_decisions 는 deepcopy — 아래에서 확인
    res["stage3_confirm_leaks"] = leak_scan(after, r.classes)
    # 4. 공개: ENTERED 뒤에만 후보, 입력 = STAGE_B evidence 만
    delta = after["model_input"]["patient_state_delta"]
    unbl = product_view(delta, wd)
    v = unbl["view"]
    res["stage4_assessment"] = v["independent_assessment"].get("status")
    res["stage4_n_candidates_shown"] = len(v["independent_assessment"].get("candidates", []))
    res["stage4_wd_echo_equal"] = v["working_diagnosis"]["value"]["label"] == DUMMY_WD["value"]["label"]
    res["stage4_model_inputs"] = unbl["state_answers"]
    res["stage4_inputs_equal_stage_b"] = unbl["state_answers"] == sorted(delta)
    res["stage4_has_percent_or_prob"] = any(k in json.dumps(v["independent_assessment"], ensure_ascii=False) for k in ("prob", "%", "score"))
    res["diff_len"] = len(diff)
    res["violations"] = [k for k, bad in (
        ("STAGE1_LEAK", bool(res["stage1_packet_leaks"])), ("STAGE2_NOT_LOCKED", res["stage2_pending_assessment"] != "LOCKED" or res["stage2_pending_next_information"] != "LOCKED"),
        ("STAGE2_LEAK", bool(res["stage2_pending_leaks"])), ("STAGE3_WD_CHANGED", not res["stage3_wd_unchanged"]), ("STAGE3_LEAK", bool(res["stage3_confirm_leaks"])),
        ("STAGE3_WD_IN_PACKET", res["stage3_packet_has_wd_field"]), ("STAGE4_NOT_AVAILABLE", res["stage4_assessment"] != "AVAILABLE"),
        ("STAGE4_WD_ECHO", not res["stage4_wd_echo_equal"]), ("STAGE4_INPUT_NOT_STAGE_B", not res["stage4_inputs_equal_stage_b"]),
        ("STAGE4_SCORE_SHOWN", res["stage4_has_percent_or_prob"])) if bad]
    return res
