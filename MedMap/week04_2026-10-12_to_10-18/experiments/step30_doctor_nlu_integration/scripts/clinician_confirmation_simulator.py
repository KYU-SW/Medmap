"""§6·§10 의사 확인 시뮬레이터(dummy — 실제 의사의 전문적 검증 아님, confirmer = DUMMY_SIMULATOR).

apply_decisions(packet, decisions) → (확인 뒤 packet, diff). 입력 packet 은 바꾸지 않는다(deepcopy).
 - CONFIRM_PRESENT 만 STAGE_B 양성 후보가 될 수 있고, 그때도 model_input_eligibility.stage_b 를 다시 통과해야 한다.
 - CONFIRM_ABSENT 는 '없음 확인'으로 기록만 — 음성 evidence 변환 안 함.
 - patient_state_delta 는 '모델 입력 후보'일 뿐 applied=false. 제품 PatientState 로 만들 수 있는지는 validate_candidate 가
   메모리 안에서만 확인한다(세션·서버·파일에 쓰지 않음).
 - working diagnosis 는 이 단계의 입력·출력에 없다(바꿀 수 없음)."""
from __future__ import annotations

import copy

import model_input_eligibility as ELIG
import s30_common as S

CONFIRMER = "DUMMY_SIMULATOR"
DECISIONS = ("CONFIRM_PRESENT", "CONFIRM_ABSENT", "REJECT", "DEFER")


def policy_confirm_stage_a(packet: dict) -> list[dict]:
    """현실적 dummy 정책: STAGE_A 항목만 '있음' 확인, 부정(C) 항목은 '없음' 확인, 나머지는 DEFER."""
    out = []
    for it in packet["items"]:
        if it["eligibility"]["eligible"]:
            d = "CONFIRM_PRESENT"
        elif it["category"] == "C":
            d = "CONFIRM_ABSENT"
        else:
            d = "DEFER"
        out.append({"item_id": it["item_id"], "decision": d, "confirmer": CONFIRMER,
                    "source": {"raw_span": it.get("raw_span"), "span": [it.get("span_start"), it.get("span_end")], "basis": "DUMMY_POLICY_STAGE_A"}})
    return out


def policy_confirm_everything(packet: dict) -> list[dict]:
    """적대적 dummy 정책: 모든 항목을 '있음' 확인(오클릭·과잉 확인 상황). STAGE_B 가 B·G·H·미지원 concept 을 막는지 본다."""
    return [{"item_id": it["item_id"], "decision": "CONFIRM_PRESENT", "confirmer": CONFIRMER,
             "source": {"raw_span": it.get("raw_span"), "span": [it.get("span_start"), it.get("span_end")], "basis": "DUMMY_POLICY_CONFIRM_ALL"}}
            for it in packet["items"]]


def apply_decisions(packet: dict, decisions: list[dict]) -> tuple[dict, list]:
    after = copy.deepcopy(packet)
    by_id = {it["item_id"]: it for it in after["items"]}
    diff, stage_b, delta = [], [], {}
    for step, d in enumerate(decisions):
        if d.get("decision") not in DECISIONS:
            raise ValueError(f"STEP30_UNKNOWN_DECISION:{d.get('decision')}")
        it = by_id[d["item_id"]]
        before_conf = copy.deepcopy(it["confirmation"])
        res = ELIG.stage_b(it, d)
        it["confirmation"] = {"status": {"CONFIRM_PRESENT": "CONFIRMED_PRESENT", "CONFIRM_ABSENT": "CONFIRMED_ABSENT",
                                         "REJECT": "REJECTED", "DEFER": "UNCONFIRMED"}[d["decision"]],
                              "by": d.get("confirmer"), "sim_step": step, "source": d.get("source"), "stage_b": res}
        if it["confirmation"] != before_conf:
            diff.append({"item_id": it["item_id"], "field": "confirmation.status", "before": before_conf["status"], "after": it["confirmation"]["status"],
                         "by": d.get("confirmer"), "sim_step": step})
        if res["eligible"]:
            eid = res["evidence_id"]
            if eid in delta:                                  # 같은 evidence 를 두 항목이 확인 — 한 번만 넣고 출처를 모두 남긴다
                delta[eid]["sources"].append(it["item_id"])
            else:
                delta[eid] = {"answer": "POSITIVE", "sources": [it["item_id"]], "confirmer": d.get("confirmer"),
                              "clinician_override_of_nlu_category": it["category"] if it["category"] != "A" else None}
                stage_b.append({"item_id": it["item_id"], "evidence_id": eid, "answer": "POSITIVE", "confirmer": d.get("confirmer")})
                diff.append({"item_id": it["item_id"], "field": "model_input.patient_state_delta", "before": None, "after": f"{eid}=POSITIVE(후보, applied=false)",
                             "by": d.get("confirmer"), "sim_step": step})
    sections = after["sections"]
    sections["confirmed"] = [it["item_id"] for it in after["items"] if it["confirmation"]["status"] in ("CONFIRMED_PRESENT", "CONFIRMED_ABSENT")]
    after["model_input"] = {**after["model_input"], "applied": False, "auto_input_count": 0, "stage_b_clinician_confirmed": stage_b,
                            "patient_state_delta": delta,
                            "note": "STAGE_B = dummy 의사 확인 뒤 모델 입력 후보 — 제품 PatientState·세션에 쓰지 않음(applied=false)"}
    return after, diff


def validate_candidate(delta: dict, age: int = 40, sex: str = "F") -> dict:
    """후보 delta 가 제품 PatientState·EvidenceCatalog 계약을 만족하는지 메모리 안에서만 확인(제품 코드 in-process, 저장 없음)."""
    S.product()
    from medmap.evidence import EvidenceCatalog
    from medmap.patient_state import PatientState, positive
    cat = EvidenceCatalog()
    observed = {eid: positive() for eid in sorted(delta)}
    errors = []
    for eid, ans in observed.items():
        try:
            cat.validate_answer(eid, ans)
        except Exception as e:                                 # noqa: BLE001 — 오류 코드만 기록
            errors.append(f"{eid}:{type(e).__name__}:{str(e)[:80]}")
    state = None
    try:
        state = PatientState.new(age, sex, None, observed)
        cat.encode([state])
    except Exception as e:                                     # noqa: BLE001
        errors.append(f"STATE:{type(e).__name__}:{str(e)[:80]}")
    return {"valid": not errors, "errors": errors, "n_answers": len(observed),
            "answers": {k: "POSITIVE" for k in sorted(observed)}, "persisted": False}
