"""STEP29.1 P5 — P5 결과와 NLU 문맥 충돌 격리(P5 원본 무수정, 확정 대신 UNCERTAIN + requires_confirmation, 원래 concept 은 guard_blocked_concept 에 보존).
규칙(평가 전 고정):
 PAIN_PREDICATE_MISMATCH : 단위 주 술어가 통증 술어(아프·쑤시·결리·욱신·찌르·따갑·쓰리·시리)이고 P5 concept 이 통증류(pain·sore_throat·heartburn·E_38·E_205·E_144·E_9·E_206·E_175·E_14) 밖
 LEXICAL_OVERLAP_ZERO    : KO EXACT/BOUNDARY 근거 용어와 단위의 핵심 형태소(STEP28.8 core_tokens)를 형태소도, 이어붙인 글자 2-gram 도 하나도 겹치지 않음(정규화 손실 일치)
 MODEL_ONLY_NO_CUE       : 근거가 STEP27 B4 모델뿐이고 단위에 증상 단서(STEP27 SYMPTOM_CUE) 없음
 EVIDENCE_IDEOPHONE_MISSING: KO 근거 용어가 모두 반복형 의성·의태어를 담는데(예 '온몸이 후끈후끈해요') 그 반복 어근이 단위에 없음 — 의미를 의성어가 담고 있어 입력과 다름
(STEP29 가드 — 의성어 불일치·양태 구토·사지 떨림·코피·부위 단독 — 는 P1 에 이미 포함)"""
from __future__ import annotations

import s291_common as S
from repair_korean_matching import core_tokens

PAIN_PRED = ("아프", "아파", "아픈", "아팠", "쑤시", "쑤셔", "결리", "결려", "욱신", "찌르", "찌릿", "따갑", "따가", "쓰리", "쓰려", "시리", "시려")
PAIN_LIKE = {"pain", "sore_throat", "heartburn", "EV:E_38", "EV:E_205", "EV:E_144", "EV:E_9", "EV:E_206", "EV:E_175", "EV:E_14"}
EXISTING = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")


def apply(m: dict) -> dict:
    if m["status"] not in EXISTING:
        return m
    unit = m.get("unit_text") or m["raw_span"]
    reasons = []
    if any(p in unit for p in PAIN_PRED) and m["canonical_id"] not in PAIN_LIKE:
        reasons.append("PAIN_PREDICATE_MISMATCH")
    from semantic_conflict_guard import EV_RE
    terms = [mm.group(3) for e in m.get("ko_evidence") or [] for mm in [EV_RE.match(e)] if mm]
    if m.get("ko_tier") in ("EXACT", "BOUNDARY") and terms:
        bg = lambda x: {x[i:i + 2] for i in range(len(x) - 1)}  # noqa: E731  형태소 분석 차이('숨차' vs '숨+차')에 견디도록 핵심 형태소 이어붙인 글자 2-gram 비교
        Ut = set(core_tokens(unit))
        U = bg("".join(Ut and core_tokens(unit)))
        if Ut and not any((Ut & set(core_tokens(t))) or (U & bg("".join(core_tokens(t)))) for t in terms):
            reasons.append("LEXICAL_OVERLAP_ZERO")
    from semantic_conflict_guard import REDUP
    if m.get("ko_tier") in ("EXACT", "BOUNDARY") and terms:
        ide = [{x.group(1) for x in REDUP.finditer(t)} for t in terms]
        if all(ide) and not any(any(stem in unit for stem in st) for st in ide):
            reasons.append("EVIDENCE_IDEOPHONE_MISSING")
    if m.get("ko_tier") == "MODEL_B4" and not S.S28.symptom_cue(unit):
        reasons.append("MODEL_ONLY_NO_CUE")
    if not reasons:
        return m
    return {**m, "status": "UNCERTAIN", "guard_blocked_concept": m["canonical_id"], "canonical_id": None, "display": [], "requires_confirmation": True,
            "usable_by_disease_model": False, "model_supported": False, "guard_reasons": list(m.get("guard_reasons") or []) + reasons}
