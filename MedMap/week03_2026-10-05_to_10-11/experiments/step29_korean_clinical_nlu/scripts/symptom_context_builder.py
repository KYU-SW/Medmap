"""STEP29 mention 조립(최종 인터페이스). model_input(49질환 모델 입력 후보 — 이번 단계는 표시만, 실제 입력 안 함):
 eligible = 상태 EXISTING_CANONICAL/COMPOSITE · P5 usable_by_disease_model · assertion ∈ {PRESENT, ABSENT} · experiencer = PATIENT ·
            (PRESENT 이면 temporality ∉ {PAST, RESOLVED}) · 의미 충돌 가드 통과 → polarity POSITIVE(PRESENT)/NEGATIVE(ABSENT).
 그 외 eligible False. 원문·이유는 항상 보존."""
from __future__ import annotations

EXISTING = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")


def model_input(m: dict) -> dict:
    ok = (m["status"] in EXISTING and bool(m.get("usable_by_disease_model")) and m["assertion"] in ("PRESENT", "ABSENT")
          and m["experiencer"] == "PATIENT" and not (m["assertion"] == "PRESENT" and m["temporality"] in ("PAST", "RESOLVED")) and not m.get("guard_reasons"))
    return {"eligible": ok, "polarity": ("POSITIVE" if m["assertion"] == "PRESENT" else "NEGATIVE") if ok else None,
            "applied": False, "note": "STEP29 는 표시만 — PatientState·49질환 모델에 넣지 않음"}
