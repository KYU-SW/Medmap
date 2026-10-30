"""§5 Doctor Integration Adapter(연구용) — STEP29.3 R2 NLU 결과 → 의사 검토용 packet(step30-doctor-review-v0).

원칙
 - NLU 원본 mention 을 고치지 않는다: 각 item 의 nlu_original 에 원본 전체(deepcopy)를 그대로 둔다.
 - 범주 A–H 로 나누되, 어느 범주도 '확정 증상'이 아니다(confirmation.status = UNCONFIRMED).
 - STAGE_A 는 표시만, model_input.applied = false, stage_b·patient_state_delta 는 의사 확인 전 항상 비어 있다.
 - 질환 이름·점수·순위는 packet 에 넣지 않는다(블라인드 단계 보존).
범주 우선순위: G(비증상) > E(다른 사람) > F(주체 MULTIPLE) > C(부정) > D(과거·해소) > H(표준화 실패) > F(불확실) > B(신규·하위 SILVER) > A(기존 지원) / 그 밖 F."""
from __future__ import annotations

import copy
import time

import model_input_eligibility as ELIG
import s30_common as S

CATEGORY_NAMES = {"A": "SUPPORTED_SYMPTOM", "B": "NEW_SYMPTOM_CANDIDATE", "C": "NEGATED_SYMPTOM", "D": "HISTORICAL_SYMPTOM",
                  "E": "OTHER_PERSON_SYMPTOM", "F": "UNCERTAIN_SYMPTOM", "G": "NON_SYMPTOM_CONTEXT", "H": "UNKNOWN_EXPRESSION"}
SECTION_OF = {"A": "ai_candidates", "B": "new_standard_candidates", "C": "negated", "D": "historical", "E": "other_person",
              "F": "needs_confirmation", "H": "needs_confirmation", "G": "non_symptom_context"}
SECTIONS = ("patient_said", "confirmed", "ai_candidates", "negated", "historical", "other_person", "new_standard_candidates",
            "needs_confirmation", "non_symptom_context")
KO_LABEL = {"chills": "오한", "confusion": "혼돈·지남력 저하", "cough": "기침", "decreased_appetite": "식욕 저하", "diarrhea": "설사",
            "dizziness": "어지러움", "dyspnea": "숨참", "fatigue": "피로", "fever": "발열", "heartburn": "속쓰림", "hematemesis": "토혈",
            "hemoptysis": "객혈", "limb_weakness": "팔다리 힘 빠짐", "loc": "의식 소실", "nausea": "메스꺼움", "pain": "통증",
            "palpitations": "두근거림", "sore_throat": "목 아픔(인후통)", "swelling": "부종", "vomiting": "구토"}
REQUIRED_FIELDS = ("source_text", "raw_span", "span_start", "span_end", "normalized_phrase", "canonical_id", "ontology_id", "assertion",
                   "temporality", "experiencer", "model_supported", "evidence_level", "requires_confirmation", "mapping_status",
                   "provenance", "uncertainty_reason")
_POLICY_SHA = None


def policy_sha() -> str:
    global _POLICY_SHA
    if _POLICY_SHA is None:
        _POLICY_SHA = S.sha256(S.S293_DIR / "data/policy_freeze.json")
    return _POLICY_SHA


def categorize(m: dict) -> tuple[str, list]:
    st, why = m.get("status"), []
    exp = m.get("experiencer")
    if st == "NON_SYMPTOM" or m.get("is_symptom") is False and st not in ("UNKNOWN_SYMPTOM", "UNCERTAIN"):
        return "G", ["NON_SYMPTOM"]
    if exp == "OTHER_PERSON":
        return "E", [f"EXPERIENCER:{exp}:{m.get('experiencer_basis')}"]
    if exp not in ("PATIENT", None):
        return "F", [f"EXPERIENCER:{exp}"]
    if m.get("assertion") == "ABSENT":
        return "C", [f"ASSERTION:ABSENT:{m.get('assertion_basis')}"]
    if m.get("temporality") == "PAST" or m.get("current_status") == "RESOLVED":
        return "D", [f"TEMPORALITY:{m.get('temporality')}", f"CURRENT_STATUS:{m.get('current_status')}"]
    if st == "UNKNOWN_SYMPTOM":
        return "H", ["UNKNOWN_SYMPTOM"]
    if m.get("assertion") in ("POSSIBLE", "UNKNOWN"):
        why.append(f"ASSERTION:{m.get('assertion')}")
    if m.get("assertion_certainty") == "LOW":
        why.append("CERTAINTY_LOW")
    if st == "UNCERTAIN":
        why.append("STATUS_UNCERTAIN")
    if m.get("guard_reasons"):
        why.append("GUARD:" + "+".join(map(str, m["guard_reasons"])))
    if m.get("semantic_conflict"):
        why.append("SEMANTIC_CONFLICT")
    if m.get("temporality") == "UNKNOWN":
        why.append("TEMPORALITY_UNKNOWN")
    if m.get("current_status") == "IMPROVING":
        why.append("CURRENT_STATUS_IMPROVING")
    if why:
        return "F", why
    if st in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE"):
        return "B", [f"STATUS:{st}", f"RELATION:{m.get('relation_to_existing')}"]
    if st in ELIG.EXISTING and m.get("model_supported"):
        if m.get("requires_confirmation") or m.get("ko_tier") == "PHRASE":
            return "F", ["REQUIRES_CONFIRMATION" if m.get("requires_confirmation") else "KO_PARTIAL_MATCH"]
        return "A", []
    if st in ELIG.EXISTING:
        return "B", ["EXISTING_STATUS_BUT_NOT_MODEL_SUPPORTED"]
    return "F", [f"UNHANDLED_STATUS:{st}"]


def label_ko(m: dict) -> str:
    cid = m.get("canonical_id")
    inv = S_INV()
    if m.get("status") in ELIG.EXISTING and cid in KO_LABEL:
        lab = KO_LABEL[cid]
    elif m.get("status") in ELIG.EXISTING and cid in inv:
        lab = inv[cid]["evidence_label_ko"]
    elif m.get("status") in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE"):
        lab = f"새 표준 증상 후보({m.get('ontology_id') or cid})"
    else:
        lab = "표준화하지 못한 표현"
    site = ((m.get("normalization") or {}).get("anatomical_site") or [])
    if cid == "pain" and site:
        lab += f"(부위 표현: {'·'.join(site)})"
    return lab


_INV = None


def S_INV() -> dict:
    global _INV
    if _INV is None:
        _INV = S.inventory()
    return _INV


def uncertainty_reason(m: dict, cat_why: list) -> list:
    out = list(cat_why)
    for k in ("guard_reasons",):
        for g in m.get(k) or []:
            if f"GUARD:{g}" not in out:
                out.append(f"GUARD:{g}")
    if m.get("reason"):
        out.append(f"NLU_REASON:{m['reason']}")
    if m.get("semantic_conflict"):
        out.append(f"SEMANTIC_CONFLICT:{m['semantic_conflict']}")
    return out


def build_item(m: dict, idx: int, text_sha: str) -> dict:
    cat, why = categorize(m)
    elig = ELIG.stage_a(m)
    if cat != "A" and elig["eligible"]:            # 이중 안전장치: A 가 아닌 범주는 STAGE_A 가 될 수 없다
        elig = {**elig, "eligible": False, "stage": "NOT_ELIGIBLE", "target_evidence": None, "target_answer": None,
                "blocking_reasons": elig["blocking_reasons"] + [f"CATEGORY:{cat}"]}
    prov = {"nlu_entry": "exp/step29_3_concept_retrieval_repair/scripts/step29_2_adapter.analyze", "nlu_policy": S.NLU_POLICY,
            "policy_freeze_sha256": policy_sha(), "evidence_sources": m.get("evidence_sources"), "ko_tier": m.get("ko_tier"),
            "ko_evidence": m.get("ko_evidence"), "retrieval": m.get("retrieval"), "b4_path": m.get("b4_path"), "b4_evidence": m.get("b4_evidence"),
            "assertion_basis": m.get("assertion_basis"), "experiencer_basis": m.get("experiencer_basis"), "relation_to_existing": m.get("relation_to_existing"),
            "isolation_status": m.get("isolation_status"), "silver": m.get("silver")}
    return {
        "item_id": f"{text_sha[:8]}:{m['span_start']}-{m['span_end']}:{idx}",
        "category": cat, "category_name": CATEGORY_NAMES[cat], "category_reasons": why, "section": SECTION_OF[cat],
        "source_text": m["source_text"], "raw_span": m["raw_span"], "span_start": m["span_start"], "span_end": m["span_end"],
        "source_sentence": m.get("source_sentence"), "sentence_index": m.get("sentence_index"),
        "normalized_phrase": m.get("normalized_phrase"), "canonical_id": m.get("canonical_id"), "ontology_id": m.get("ontology_id"),
        "label_ko": label_ko(m), "assertion": m.get("assertion"), "assertion_certainty": m.get("assertion_certainty"),
        "temporality": m.get("temporality"), "onset_text": m.get("onset_text"), "time_scope": m.get("time_scope"),
        "current_status": m.get("current_status"), "experiencer": m.get("experiencer"),
        "model_supported": m.get("model_supported"), "evidence_level": m.get("evidence_level"),
        "requires_confirmation": True,                     # 의사 화면에서는 모든 AI 추출 항목이 확인 대상
        "nlu_requires_confirmation": m.get("requires_confirmation"),
        "mapping_status": m.get("status"), "provenance": prov, "uncertainty_reason": uncertainty_reason(m, why),
        "eligibility": elig, "confirmation": {"status": "UNCONFIRMED", "by": None},
        "display_ko": f"환자 표현 '{m['raw_span']}' → {label_ko(m)} · AI 추출 · 미확인",
        "nlu_original": copy.deepcopy(m),
    }


def context_items(ctx: dict, text: str, text_sha: str, start_idx: int) -> list:
    """NLU 가 증상 아님으로 돌린 구문(context.dropped_context) → 범주 G item(원문 위치 포함). 모델 입력 대상 아님."""
    out = []
    for j, d in enumerate(ctx.get("dropped_context") or []):
        s = d.get("start")
        e = s + len(d["raw_span"]) if s is not None else None
        out.append({"item_id": f"{text_sha[:8]}:{s}-{e}:ctx{j}", "category": "G", "category_name": CATEGORY_NAMES["G"],
                    "category_reasons": ["NLU_DROPPED_CONTEXT:" + str(d.get("reason"))], "section": "non_symptom_context",
                    "source_text": text, "raw_span": d["raw_span"], "span_start": s, "span_end": e, "label_ko": "증상 아닌 문맥",
                    "mapping_status": "DROPPED_CONTEXT", "canonical_id": None, "ontology_id": None, "requires_confirmation": True,
                    "provenance": {"nlu_entry": "context.dropped_context", "nlu_policy": S.NLU_POLICY, "policy_freeze_sha256": policy_sha()},
                    "uncertainty_reason": [str(d.get("reason"))],
                    "eligibility": {"stage": "NOT_ELIGIBLE", "eligible": False, "target_evidence": None, "target_answer": None,
                                    "candidate_target_if_confirmed": None, "blocking_reasons": ["NON_SYMPTOM_CONTEXT"], "auto_apply": False, "negative_evidence": None},
                    "confirmation": {"status": "UNCONFIRMED", "by": None},
                    "display_ko": f"환자 표현 '{d['raw_span']}' → 증상 아닌 문맥", "nlu_original": copy.deepcopy(d)})
    return out


def build_packet(text: str, nlu_out: dict) -> dict:
    tsha = S.sha_text(text)
    items = [build_item(m, i, tsha) for i, m in enumerate(nlu_out["mentions"])]
    items += context_items(nlu_out.get("context") or {}, text, tsha, len(items))
    sections = {k: [] for k in SECTIONS}
    sections["patient_said"] = {"source_text": text, "sentences": [{k: s.get(k) for k in ("start", "end", "text")}
                                                                    for s in (nlu_out.get("context") or {}).get("sentences", [])]}
    for it in items:
        sections[it["section"]].append(it["item_id"])
    stage_a = [{"item_id": it["item_id"], "evidence_id": it["eligibility"]["target_evidence"], "answer": "POSITIVE"}
               for it in items if it["eligibility"]["eligible"]]
    return {"schema_version": S.SCHEMA_VERSION, **S.RESEARCH_BANNER, "source_text": text, "nlu_level": nlu_out.get("level"),
            "items": items, "sections": sections,
            "model_input": {"applied": False, "auto_input_count": 0, "stage_a_technically_eligible": stage_a,
                            "stage_b_clinician_confirmed": [], "patient_state_delta": {},
                            "note": "STAGE_A 는 표시만 — 의사 확인(STAGE_B) 전 모델 입력 없음, 제품 PatientState 에 쓰지 않음"},
            "nlu_context": copy.deepcopy(nlu_out.get("context"))}


def analyze(text: str, timings: dict | None = None) -> dict:
    """원문 → (NLU R2) → packet. timings 를 주면 단계별 초를 채운다(NLU+검색 = analyze 전체, 어댑터 = build_packet)."""
    A = S.nlu()
    t0 = time.perf_counter()
    out = A.analyze(text, S.NLU_POLICY)
    t1 = time.perf_counter()
    pkt = build_packet(text, out)
    t2 = time.perf_counter()
    if timings is not None:
        timings.update(nlu_total=t1 - t0, adapter=t2 - t1)
    return pkt


if __name__ == "__main__":
    import sys
    for t in sys.argv[1:]:
        p = analyze(t)
        print("==", t)
        for it in p["items"]:
            print(it["category"], it["raw_span"], it["canonical_id"], it["assertion"], it["temporality"], it["experiencer"],
                  "STAGE_A" if it["eligibility"]["eligible"] else "-", it["eligibility"]["target_evidence"], it["category_reasons"][:2])
