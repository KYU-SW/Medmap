"""§6 모델 입력 자격 — STAGE_A(TECHNICALLY_ELIGIBLE, 표시만) / STAGE_B(CLINICIAN_CONFIRMED, 의사 확인 뒤 후보).

STAGE_A 는 '기술적으로 옮길 수 있음'을 보여 줄 뿐 모델 입력이 아니다(auto_apply 항상 False).
STAGE_B 도 PatientState·제품 세션에 쓰지 않는다 — 별도 '모델 입력 후보' 목록으로만 만든다.
음성(ABSENT) → NEGATIVE evidence 변환은 이번 단계에서 허용하지 않는다(모델 스키마·의사 확인 정책 미검증)."""
from __future__ import annotations

import json
from functools import lru_cache

import s30_common as S

EXISTING = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")
OK_TEMPORALITY = ("CURRENT", "ONGOING")
OK_CURRENT_STATUS = ("UNSPECIFIED", "PERSISTING")
NEGATIVE_POLICY = "NEGATIVE_EVIDENCE_POLICY_UNVERIFIED"


@lru_cache(maxsize=1)
def mapping() -> dict:
    """canonical → 허용 변환 행(conversion_allowed=True 인 것만). 하나의 concept 에 허용 행이 둘 이상이면 오류(G8)."""
    allowed: dict[str, dict] = {}
    for r in S.read_csv(S.DATA / "evidence_mapping_candidates.csv"):
        if r["conversion_allowed"] == "True":
            if r["nlu_concept_id"] in allowed:
                raise ValueError(f"STEP30_MAPPING_MULTIPLE_TARGETS:{r['nlu_concept_id']}")
            allowed[r["nlu_concept_id"]] = r
    return allowed


@lru_cache(maxsize=1)
def mapping_reasons() -> dict:
    """canonical → 변환 안 되는 이유(허용 행이 없을 때 표시용)."""
    out: dict[str, list] = {}
    for r in S.read_csv(S.DATA / "evidence_mapping_candidates.csv"):
        if r["conversion_allowed"] != "True":
            out.setdefault(r["nlu_concept_id"], []).append(f"{r['ddxplus_evidence_id']}:{r['conversion_reason'].split(' | ')[0]}")
    return out


@lru_cache(maxsize=1)
def catalog() -> dict:
    S.product()
    from medmap import config
    raw = json.loads(config.EVIDENCES_JSON.read_text())
    return {"raw": raw, "excluded": frozenset(config.EXCLUDED_QUESTIONS)}


def evidence_ok(eid: str) -> list[str]:
    c = catalog()
    ev = c["raw"].get(eid)
    if ev is None:
        return ["EVIDENCE_NOT_IN_CATALOG"]
    bad = []
    if ev["data_type"] != "B":
        bad.append("EVIDENCE_NOT_BINARY")
    if ev["code_question"] != eid:
        bad.append("EVIDENCE_HAS_PARENT")
    if eid in c["excluded"]:
        bad.append("EVIDENCE_EXCLUDED")
    return bad


def stage_a(m: dict) -> dict:
    """NLU 원본 mention → STAGE_A 판정. 막는 이유를 모두 남긴다(하나만 아님)."""
    why = []
    status = m.get("status")
    if status not in EXISTING:
        why.append(f"STATUS:{status}")
    if not m.get("model_supported"):
        why.append("NOT_MODEL_SUPPORTED")
    if not m.get("is_symptom", True):
        why.append("NOT_SYMPTOM")
    if (m.get("evidence_sources") or "") == "SILVER":
        why.append("SILVER_ONLY_EVIDENCE")
    if m.get("experiencer") != "PATIENT":
        why.append(f"EXPERIENCER:{m.get('experiencer')}")
    if m.get("assertion") != "PRESENT":
        why.append(f"ASSERTION:{m.get('assertion')}")
    if m.get("assertion_certainty") == "LOW":
        why.append("CERTAINTY_LOW")
    if m.get("temporality") not in OK_TEMPORALITY:
        why.append(f"TEMPORALITY:{m.get('temporality')}")
    if (m.get("current_status") or "UNSPECIFIED") not in OK_CURRENT_STATUS:
        why.append(f"CURRENT_STATUS:{m.get('current_status')}")
    if m.get("requires_confirmation"):
        why.append("REQUIRES_CONFIRMATION")
    if m.get("guard_reasons"):
        why.append("GUARD:" + "+".join(map(str, m["guard_reasons"])))
    if m.get("semantic_conflict"):
        why.append("SEMANTIC_CONFLICT")
    if m.get("ko_tier") == "PHRASE":
        why.append("KO_PARTIAL_MATCH")
    if not (m.get("model_input") or {}).get("eligible"):
        why.append("NLU_MODEL_INPUT_INELIGIBLE")
    elif (m.get("model_input") or {}).get("polarity") != "POSITIVE":     # NLU 는 ABSENT 를 eligible·NEGATIVE 로 준다 — 양성만 STAGE_A
        why.append(f"NLU_POLARITY:{(m.get('model_input') or {}).get('polarity')}")
    cid = m.get("canonical_id")
    row = mapping().get(cid) if cid else None
    target = None
    if row is None:
        why.append("NO_CONVERSION_RULE" + (":" + ",".join(mapping_reasons().get(cid, [])) if cid else ""))
    else:
        target = row["ddxplus_evidence_id"]
        why += evidence_ok(target)
    eligible = not why
    return {"stage": "STAGE_A_TECHNICALLY_ELIGIBLE" if eligible else "NOT_ELIGIBLE", "eligible": eligible,
            "target_evidence": target if eligible else None, "target_answer": "POSITIVE" if eligible else None,
            "candidate_target_if_confirmed": target, "blocking_reasons": why, "auto_apply": False,
            "negative_evidence": ({"target": target, "allowed": False, "reason": NEGATIVE_POLICY}
                                  if m.get("assertion") == "ABSENT" and target else None)}


def stage_b(item: dict, decision: dict) -> dict:
    """의사(시뮬레이터) 결정 → STAGE_B 모델 입력 후보 판정. item = 어댑터 item, decision = {decision, evidence_id?, confirmer, source}.
    결정 종류: CONFIRM_PRESENT · CONFIRM_ABSENT · REJECT · DEFER. CONFIRM_PRESENT 만 양성 후보가 될 수 있다."""
    why = []
    kind = decision.get("decision")
    eid = decision.get("evidence_id") or (item.get("eligibility") or {}).get("candidate_target_if_confirmed")
    if kind != "CONFIRM_PRESENT":
        why.append(f"DECISION:{kind}")
    if not decision.get("confirmer"):
        why.append("NO_CONFIRMER")
    if not decision.get("source"):
        why.append("NO_SOURCE_RECORDED")
    if not eid:
        why.append("NO_TARGET_EVIDENCE")
    else:
        why += evidence_ok(eid)
        allowed_targets = {r["ddxplus_evidence_id"] for r in mapping().values()}
        if eid not in allowed_targets:
            why.append("TARGET_NOT_IN_APPROVED_CONVERSION")
        cid = item.get("canonical_id")
        row = mapping().get(cid) if cid else None
        if row is None or row["ddxplus_evidence_id"] != eid:
            why.append("CONCEPT_TARGET_MISMATCH_OR_UNSUPPORTED")
    if item.get("category") in ("B", "G", "H"):
        why.append(f"CATEGORY_NOT_MODEL_FEATURE:{item.get('category')}")
    # 부정·과거·다른 사람·불확실 항목을 '있음'으로 바꾸려면 의사의 명시적 재분류 사유가 필요(한 번 클릭·일괄 확인으로는 안 됨)
    if item.get("category") in ("C", "D", "E", "F") and kind == "CONFIRM_PRESENT" and not decision.get("override_reason"):
        why.append(f"OVERRIDE_REASON_REQUIRED:{item.get('category')}")
    ok = not why
    neg = None
    if kind == "CONFIRM_ABSENT":
        neg = {"target": eid, "allowed": False, "reason": NEGATIVE_POLICY}
    return {"stage": "STAGE_B_CLINICIAN_CONFIRMED" if ok else "NOT_MODEL_INPUT", "eligible": ok,
            "evidence_id": eid if ok else None, "answer": "POSITIVE" if ok else None, "blocking_reasons": why,
            "negative_evidence": neg, "applied_to_product": False}
