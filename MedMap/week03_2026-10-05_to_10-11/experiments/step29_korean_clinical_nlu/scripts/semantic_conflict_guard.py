"""STEP29 의미 충돌 검증(NLU_P5 단계만). P5 결과를 바꾸지 않고, 문맥과 충돌하면 UNCERTAIN + requires_confirmation(+ 후보 기록). 규칙(사전 고정):
 IDEOPHONE_MISMATCH : 단위에 반복형 의성·의태어가 있고, P5 KO 근거 용어에 다른 반복형만 있으면(겹침 0) → UNCERTAIN('화끈화끈' ≠ '울렁울렁')
 MODAL_VOMIT        : 구토 단서 + '…ㄹ 것 같다/싶다/듯' 인데 vomiting → UNCERTAIN(오심 쪽 표현) · 구토 단서(양태 없음)인데 nausea 만 → UNCERTAIN
 LIMB_TREMOR        : 떨리/떨려/떨림 + 손·팔·다리·입술·눈꺼풀, 문장에 추위 단서 없음, P5 = chills → UNCERTAIN + SILVER '떨림' 후보(Tremor, 표시·모델 없음)
 EPISTAXIS          : '코피' 인데 hemoptysis·hematemesis → UNCERTAIN
 BODY_PART_ONLY     : 단위에 용언 없음 · 증상 단서 없음 · 마지막 명사가 부분/쪽/부위/근처/주위 → concept 제거(UNCERTAIN)
 SILVER 보호        : NEW_ONTOLOGY_CANDIDATE·EXISTING_SUBTYPE·SILVER 단독 근거는 model_supported·usable 강제 False(이미 P5 가 그렇게 반환 — 재확인)."""
from __future__ import annotations

import re

import s29_common as S

REDUP = re.compile(r"([가-힣]{1,3})\1")
EV_RE = re.compile(r"^(EXACT|PHRASE|BOUNDARY):(UMLS_KOR:[^:]+|TERMINOLOGY_LABEL:E_\d+|[A-Za-z0-9_]+):(.*)$")
COLD = re.compile(r"(오한|춥|추워|으슬|한기)")
LIMB = re.compile(r"(손|팔|다리|입술|눈꺼풀)")
TREMOR = re.compile(r"(떨리|떨려|떨림)")
VOMIT = re.compile(r"(토할|토하|토했|토해|구토(?![감기])|오바이트)")
MODAL = re.compile(r"(것\s*같|듯|할\s*것|싶)")
GENERIC_PLACE = {"부분", "쪽", "부위", "근처", "주위"}


def ideophones(s: str) -> set[str]:
    return {m.group(0) for m in REDUP.finditer(s or "")}


def guard(m: dict, unit_text: str, sentence: str, unit_toks) -> dict:
    st, c = m["status"], m.get("canonical_id")
    reasons = []
    if st in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE") and m.get("ko_evidence"):
        mine = ideophones(unit_text)
        terms = [mm.group(3) for e in m["ko_evidence"] for mm in [EV_RE.match(e)] if mm]
        theirs = set().union(*[ideophones(t) for t in terms]) if terms else set()
        if mine and theirs and not (mine & theirs):
            reasons.append(f"IDEOPHONE_MISMATCH({'/'.join(sorted(mine))}≠{'/'.join(sorted(theirs))})")
    x = S.nospace(unit_text)
    if VOMIT.search(x) and MODAL.search(unit_text) and c == "vomiting":
        reasons.append("MODAL_VOMIT")
    if VOMIT.search(x) and not MODAL.search(unit_text) and c == "nausea":
        reasons.append("VOMIT_AS_NAUSEA")
    cand = None
    if TREMOR.search(x) and LIMB.search(x) and not COLD.search(S.nospace(sentence)) and c == "chills":
        reasons.append("LIMB_TREMOR_NOT_CHILLS")
    if TREMOR.search(x) and LIMB.search(x) and not COLD.search(S.nospace(sentence)):
        from p5_normalizer_adapter import silver_rows
        tr = [r for r in silver_rows("떨림") if r["mapping_decision"] == "ACCEPT_NEW_CANDIDATE"]
        if tr:
            cand = {"ontology_id": tr[0]["ontology_id"], "evidence_level": tr[0]["evidence_level"], "basis": "SILVER '떨림' 행(표시·모델 없음, 후보만)"}
    if "코피" in x and c in ("hemoptysis", "hematemesis"):
        reasons.append("EPISTAXIS_NOT_BLEEDING_OTHER")
    nouns = [t.form for t in unit_toks if t.tag.startswith("NN")]
    has_pred = any(t.tag.startswith(("VV", "VA")) for t in unit_toks)
    if nouns and nouns[-1] in GENERIC_PLACE and not has_pred and not S.S28.symptom_cue(unit_text) and (c or m.get("ontology_id")):
        reasons.append("BODY_PART_ONLY")
    out = dict(m)
    if cand:
        out["candidates"] = [cand]
    if reasons:
        out.update(status="UNCERTAIN", canonical_id=None, ontology_id=None if "BODY_PART_ONLY" in reasons else m.get("ontology_id"), display=[],
                   requires_confirmation=True, usable_by_disease_model=False, model_supported=False, guard_reasons=reasons,
                   guard_blocked_concept=c or m.get("ontology_id"))
    if out["status"] in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE") or out.get("evidence_sources") == "SILVER":
        out["usable_by_disease_model"] = False
        if out["status"] in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE"):
            out["model_supported"] = False
    return out
