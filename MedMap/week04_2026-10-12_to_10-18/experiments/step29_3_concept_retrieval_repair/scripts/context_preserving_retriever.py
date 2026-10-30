"""STEP29.3 §5–§8 검색 계층(STEP28.8 P5 원본은 호출만). mention 하나를 받아 concept 연결을 보강·검증한다. 원문·원래 결과·근거는 retrieval 필드에 모두 보존.

 모드: N1 = 표준 질의 재검색(부사 제거) · N2 = 표준 질의 재검색(의성어·감각 부사 보존) · N3 = N2 + 의미 구별 규칙(빈 연결 채우기)·SILVER 검색·비증상 문맥
       N4 = N3 + 의미 충돌 보류(검색기 결과와 의미 규칙이 다르면 UNCERTAIN)
 재검색 대상: 증상 mention 중 UNCERTAIN·UNKNOWN_SYMPTOM 이고 STEP29/29.2 의도적 보류(guard_reasons·평가형 부위 보류·평가형 부정)가 아님.
 재검색 채택: P5(표준 질의) 결과가 EXISTING·NEW·SUBTYPE 이고 KO 근거 등급이 EXACT·BOUNDARY·RULE·MODEL_B4(B4 는 이후 B4 정책이 판단) — PHRASE·NGRAM(문자열 부분 일치) 불채택.
 의미 규칙(N3): 규칙이 판단하면 재검색보다 먼저 적용 — 연결이 비었을 때만 규칙 concept 을 채운다(근거 등급 RULE). 이미 연결이 있고 규칙과 다르면
   같은 증상군의 일반↔특이(COMPAT, 예 통증↔속쓰림)는 기록만, 그 외는 N3 기록만·N4 보류(UNCERTAIN, SEMANTIC_CONFLICT_HOLD).
 재검색 조건 추가: 단위에 증상 단서 또는 신체 부위 명사가 있어야 함('밥 먹고' 제외). N2 이상은 수식어를 뺀 대체 질의 없음.
 SILVER(N3): 남은 미연결 mention 의 명사·명사형(어간+ㅁ)·명사+명사형을 STEP28.7 감사 표(KEEP_NEW_CANDIDATE → NEW_ONTOLOGY_CANDIDATE,
   MERGE_AS_EXISTING_RELATION → EXISTING_SUBTYPE, HELD·REJECTED 제외)의 표현과 정확 일치로 찾는다. 모델 입력 항상 불가.
 비증상 문맥(N3): 환경 진술('날씨가 추워요')·인식 표현('괜찮은지 헷갈려요') → 증상 mention 아님(NON_SYMPTOM, 사유 보존)."""
from __future__ import annotations

import re

import s293_common as S
import semantic_disambiguator as SD
from extract_symptom_spans import kiwi
from evaluative_negation_scope import body
from korean_morphological_normalizer import canonical_query, lemma_info
from p5_normalizer_adapter import p5

ACCEPT_TIER = ("EXACT", "BOUNDARY", "RULE", "MODEL_B4")
COPY = ("status", "canonical_id", "ontology_id", "relation_to_existing", "evidence_level", "isolation_status", "model_supported", "usable_by_disease_model",
        "display", "requires_confirmation", "reason", "evidence_sources", "ko_tier")
_SILVER = None
COMPAT = [{"pain", "heartburn"}, {"pain", "sore_throat"}, {"fatigue", "EV:E_175"}, {"dizziness", "EV:E_82"}, {"dyspnea", "EV:E_75"}, {"fatigue", "limb_weakness"}]   # 일반 ↔ 특이(같은 증상군)


def silver_table() -> dict:
    global _SILVER
    if _SILVER is None:
        _SILVER = {}
        for r in S.read_csv(S.S28_DIR.parent / "step28_7_mapping_quality_validation/data/audited_concepts.csv"):
            if r["keep_decision"] not in ("KEEP_NEW_CANDIDATE", "MERGE_AS_EXISTING_RELATION") or r["relation_to_existing"] == "EXISTING_SYNONYM":
                continue
            st = "NEW_ONTOLOGY_CANDIDATE" if r["keep_decision"] == "KEEP_NEW_CANDIDATE" else "EXISTING_SUBTYPE"
            for e in r["korean_expressions"].split("|"):
                e = re.sub(r"(이나|과|은|는|이|가|을|를|의|로|으로|까지|에)$", "", e.strip().replace(" ", ""))
                if len(e) >= 2:
                    _SILVER.setdefault(e, (r["concept_id"], st))
    return _SILVER


def _silver_lookup(unit: str):
    toks = kiwi().tokenize(unit or "")
    cands, nouns = [], []
    for t in toks:
        if t.tag.startswith("NN") and t.tag != "NNB":
            nouns.append(t.form)
            cands.append(t.form)
        if t.tag.startswith(("VV", "VA")):
            try:
                nm = kiwi().join([(t.form, t.tag), ("ㅁ", "ETN")])
            except Exception:  # noqa: BLE001
                nm = None
            if nm:
                cands.append(nm)
                cands += [n + nm for n in nouns[-1:]]
    if len(nouns) >= 2:
        cands.append("".join(nouns[-2:]))
    tab = silver_table()
    for c in cands:
        if c in tab:
            return c, tab[c]
    return None


def _requery(m: dict, keep_mod: bool) -> dict | None:
    unit = m.get("unit_text") or m["raw_span"]
    toks = kiwi().tokenize(unit)
    if not (S.S28.symptom_cue(unit) or any(t.form in body() for t in toks if t.tag.startswith("NN"))):
        return None   # 증상 단서·신체 부위가 없는 단위('밥 먹고')는 재검색하지 않는다
    q = canonical_query(unit, keep_mod)
    tried = [q] if q else []   # N2 이상은 수식어를 뺀 대체 질의를 쓰지 않는다(의성어가 의미를 담는 경우 손실)
    for qq in tried:
        rs = [r for r in p5(qq) if r["status"] in S.POS]
        if len(rs) == 1 and rs[0].get("ko_tier") in ACCEPT_TIER:
            return {"query": qq, "result": rs[0], "modifier_dropped": not keep_mod}
    return None


def apply(m: dict, mode: str) -> dict:
    if not m.get("is_symptom") or m["status"] == "NON_SYMPTOM":
        return m
    out = dict(m)
    unit = m.get("unit_text") or m["raw_span"]
    sent = m.get("source_sentence") or ""
    out["normalization"] = lemma_info(unit)
    lvl = int(mode[1])
    if lvl >= 3:
        ns = SD.non_symptom_context(unit, sent)
        if ns:
            return {**out, "status": "NON_SYMPTOM", "canonical_id": None, "display": [], "is_symptom": False, "model_supported": False,
                    "usable_by_disease_model": False, "reason": ns, "retrieval": {"via": "NON_SYMPTOM_CONTEXT", "original_status": m["status"],
                                                                                    "original_concept": m.get("canonical_id")}}
    deliberate = bool(m.get("guard_reasons")) or m.get("reason") == "EVAL_SITE_ONLY_CONCEPT_AMBIGUOUS" or str(m.get("assertion_basis", "")).startswith("EVAL")
    d = SD.decide(unit, sent) if lvl >= 3 else None
    if out["status"] in ("UNCERTAIN", "UNKNOWN_SYMPTOM") and not deliberate and not d:   # 의미 규칙이 판단하면 그 판단을 먼저(재검색은 규칙이 없을 때만)
        rq = _requery(m, keep_mod=lvl >= 2)
        if rq:
            r = rq["result"]
            out.update({k: r.get(k) for k in COPY})
            out["ko_evidence"] = list(r.get("ko_evidence") or [])[:3]
            out["retrieval"] = {"via": "MORPH_REQUERY", "query": rq["query"], "tier": r.get("ko_tier"), "modifier_dropped": rq["modifier_dropped"],
                                "original_status": m["status"], "original_reason": m.get("reason")}
    if lvl >= 3:
        if d:
            cur = out.get("canonical_id") if out["status"] in S.EXISTING else (out.get("ontology_id") if out["status"] in S.POS else None)
            want = d.get("concept") or d.get("ontology_id")
            if out["status"] not in S.POS and not deliberate:
                fill = {"status": d["status"], "canonical_id": d.get("concept"), "ontology_id": d.get("ontology_id"), "ko_tier": "RULE", "reason": "",
                        "display": [d["concept"]] if d.get("concept") else [], "requires_confirmation": d["status"] == "NEW_ONTOLOGY_CANDIDATE",
                        "model_supported": d["status"] in S.EXISTING, "usable_by_disease_model": d["status"] in S.EXISTING,
                        "evidence_level": "STEP29_3_SEMANTIC_RULE", "evidence_sources": "SILVER" if d["status"] == "NEW_ONTOLOGY_CANDIDATE" else "KO:RULE"}
                out.update(fill)
                out["retrieval"] = {**(out.get("retrieval") or {}), "via": "SEMANTIC_RULE", "basis": d["basis"], "tier": "RULE", "original_status": m["status"],
                                    "original_reason": m.get("reason")}
                if d.get("site"):
                    out["attributes"] = list(out.get("attributes") or []) + [f"부위:{d['site']}"]
            elif cur and want and cur != want and {cur, want} in COMPAT:
                out["semantic_refinement"] = {"retrieved": cur, "rule": want, "basis": d["basis"]}   # 일반 통증 ↔ 부위 특이 개념: 충돌 아님
            elif cur and want and cur != want:
                out["semantic_conflict"] = {"retrieved": cur, "rule": want, "basis": d["basis"]}
                if lvl >= 4:
                    out.update({"status": "UNCERTAIN", "guard_blocked_concept": cur, "canonical_id": None, "display": [], "requires_confirmation": True,
                                "model_supported": False, "usable_by_disease_model": False,
                                "guard_reasons": list(out.get("guard_reasons") or []) + ["SEMANTIC_CONFLICT_HOLD"]})
        if out["status"] in ("UNCERTAIN", "UNKNOWN_SYMPTOM") and not out.get("guard_reasons") and not deliberate:
            sv = _silver_lookup(unit)
            if sv:
                expr, (cid, st) = sv
                out.update({"status": st, "ontology_id": cid, "canonical_id": None, "display": [], "requires_confirmation": True, "model_supported": False,
                            "usable_by_disease_model": False, "evidence_sources": "SILVER", "evidence_level": "STEP28_7_AUDITED_SILVER", "ko_tier": "SILVER_EXACT",
                            "reason": "SILVER_CANDIDATE(사람 검증 아님)"})
                out["retrieval"] = {**(out.get("retrieval") or {}), "via": "SILVER_LOOKUP", "expression": expr, "tier": "SILVER_EXACT"}
    return out
