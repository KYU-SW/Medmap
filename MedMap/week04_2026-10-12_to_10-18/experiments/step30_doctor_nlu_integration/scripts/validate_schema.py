"""§4 NLU 출력 계약 + §5 packet 계약 검사. 입력 = (원문, NLU 원본 출력, packet). 결과 = 위반 목록(없으면 통과).
필수 필드 중 NLU 가 직접 주는 것과 어댑터가 만든 것을 구분해 기록한다."""
from __future__ import annotations

import doctor_integration_adapter as AD
import s30_common as S

NLU_NATIVE = ("source_text", "raw_span", "span_start", "span_end", "normalized_phrase", "canonical_id", "ontology_id", "assertion",
              "temporality", "experiencer", "model_supported", "evidence_level", "requires_confirmation")
ADAPTER_DERIVED = {"mapping_status": "= NLU status", "provenance": "= NLU 출처 필드 묶음 + 정책 SHA", "uncertainty_reason": "= 범주 사유 + guard_reasons + reason + semantic_conflict"}
CATS = set(AD.CATEGORY_NAMES)


def nlu_field_presence(nlu_out: dict) -> dict:
    out = {}
    for f in AD.REQUIRED_FIELDS:
        n = sum(1 for m in nlu_out["mentions"] if f in m)
        out[f] = {"present_in_nlu": n, "mentions": len(nlu_out["mentions"]), "source": "NLU" if f in NLU_NATIVE else "ADAPTER"}
    return out


def check(text: str, nlu_out: dict, packet: dict) -> list[str]:
    v = []
    if packet.get("source_text") != text:
        v.append("G1:PACKET_SOURCE_TEXT")
    if packet.get("schema_version") != S.SCHEMA_VERSION:
        v.append("SCHEMA_VERSION")
    for k, val in S.RESEARCH_BANNER.items():
        if packet.get(k) != val:
            v.append(f"G14:BANNER:{k}")
    mentions = nlu_out["mentions"]
    nlu_items = [it for it in packet["items"] if it.get("mapping_status") != "DROPPED_CONTEXT"]
    if len(nlu_items) != len(mentions):
        v.append(f"G13:ITEM_COUNT:{len(nlu_items)}!={len(mentions)}")
    ids = [it["item_id"] for it in packet["items"]]
    if len(set(ids)) != len(ids):
        v.append("ITEM_ID_DUPLICATE")
    for i, it in enumerate(packet["items"]):
        tag = f"{it.get('item_id')}"
        s, e = it.get("span_start"), it.get("span_end")
        if it.get("source_text") != text:
            v.append(f"G1:ITEM_SOURCE_TEXT:{tag}")
        if not (isinstance(s, int) and isinstance(e, int) and 0 <= s < e <= len(text)):
            v.append(f"G2:OFFSET_RANGE:{tag}")
        elif it.get("raw_span") != text[s:e]:
            v.append(f"G1:RAW_SPAN_MISMATCH:{tag}")
        for f in AD.REQUIRED_FIELDS:
            if f not in it:
                v.append(f"SCHEMA_MISSING:{f}:{tag}")
        if it.get("category") not in CATS:
            v.append(f"CATEGORY_INVALID:{tag}")
        if it.get("confirmation", {}).get("status") != "UNCONFIRMED":
            v.append(f"G9:PRECONFIRMED:{tag}")
        if it.get("eligibility", {}).get("auto_apply") is not False:
            v.append(f"G9:AUTO_APPLY:{tag}")
        if not isinstance(it.get("uncertainty_reason"), list) or not isinstance(it.get("provenance"), dict):
            v.append(f"G13:PROVENANCE_OR_UNCERTAINTY_TYPE:{tag}")
        if it.get("mapping_status") != "DROPPED_CONTEXT":
            m = mentions[i]
            if it.get("nlu_original") != m:
                v.append(f"G13:NLU_ORIGINAL_CHANGED:{tag}")
            if (s, e, it.get("raw_span")) != (m["span_start"], m["span_end"], m["raw_span"]):
                v.append(f"G2:OFFSET_DIFFERS_FROM_NLU:{tag}")
            for f in ("guard_reasons",):
                for g in m.get(f) or []:
                    if not any(str(g) in r for r in it["uncertainty_reason"]):
                        v.append(f"G13:GUARD_REASON_LOST:{g}:{tag}")
        if it["eligibility"]["eligible"] and it["category"] != "A":
            v.append(f"STAGE_A_NON_A:{tag}")
    mi = packet["model_input"]
    if mi.get("applied") is not False or mi.get("auto_input_count") != 0 or mi.get("stage_b_clinician_confirmed") or mi.get("patient_state_delta"):
        v.append("G9:MODEL_INPUT_BEFORE_CONFIRMATION")
    if packet["sections"].get("confirmed"):
        v.append("G9:CONFIRMED_BEFORE_CONFIRMATION")
    sec_ids = sorted(x for k, val in packet["sections"].items() if isinstance(val, list) for x in val)
    if sec_ids != sorted(ids):
        v.append("SECTION_ITEM_MISMATCH")
    return v
