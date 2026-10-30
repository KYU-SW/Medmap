"""STEP29.3 §9 B4 후보 사용 정책(STEP29.2 b4_evidence_guard 원본 호출만). 모델 기반(B4) 연결과 용어 사전 기반 연결을 구분해 기록한다(b4_path).
 B0  = STEP29.2 V3_B0(B4 단독 규칙 없음, STEP29.1 가드 + '점점' 보정)
 B3C = B0 + B4 단독 연결의 의미 충돌 보류(STEP29.2 b4_evidence_guard.conflict 규칙 — 어지럼↔혼동, 오심↔구토, 사지 떨림↔오한, 코피↔객혈·토혈, 목 부위↔통증)
 B23 = STEP29.2 V3_B3(증상 근거 선택 수락 + 의미 충돌 보류)
B4 가 confidence 만으로 확정되지 않도록 B23 은 술어·논항·비증상 명사·모델 일치 근거를 함께 본다(STEP29.2 정의 그대로)."""
from __future__ import annotations

import s293_common  # noqa: F401  (경로)
import b4_evidence_guard as B4G


def apply(m: dict, mode: str) -> dict:
    path = "MODEL_B4" if m.get("ko_tier") == "MODEL_B4" else ("LEXICON_OR_RULE" if m.get("status") in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE") else None)
    if mode == "B23":
        out = B4G.apply(m, "V3_B3")
    else:
        out = B4G.apply(m, "V3_B0")
        if mode == "B3C" and out.get("status") in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE") and out.get("ko_tier") == "MODEL_B4":
            cf = B4G.conflict(out)
            if cf:
                out = {**B4G._block(out, ["B4_SEMANTIC_CONFLICT"]), "b4_guard_detail": cf}
    return {**out, "b4_path": path}
