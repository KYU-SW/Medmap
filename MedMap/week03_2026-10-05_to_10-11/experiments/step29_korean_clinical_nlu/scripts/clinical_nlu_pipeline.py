"""STEP29 Korean Clinical NLU 파이프라인(연구용). analyze(text, level) → {"source_text", "level", "mentions": [...], "context": {...}}.

단계(평가 비교군, 기능을 하나씩 추가):
 NLU_P0 = STEP28.8 P5 단독(전체 문장, P5 의 polarity/subject 그대로: NEGATIVE→ABSENT, OTHER_PERSON(…)→OTHER_PERSON, 시점 UNKNOWN)
 NLU_P1 = 절 분해 + 단위(관계절·병렬) + 단위별 P5 — assertion PRESENT · temporality UNKNOWN · experiencer PATIENT(가정) 고정
 NLU_P2 = P1 + 부정·확신(negation_scope) · NLU_P3 = P2 + 시점(temporality_analyzer) · NLU_P4 = P3 + 주체(experiencer_analyzer)
 NLU_P5 = P4 + 의미 충돌 검증(semantic_conflict_guard) + SILVER 보호
mention 보존 기준(사전 고정): P5 상태가 EXISTING_*·EXISTING_SUBTYPE·NEW·NON·UNKNOWN_SYMPTOM, 또는 UNCERTAIN 이면서 증상 단서(STEP27 SYMPTOM_CUE)나
 후보성 사유(충돌·보류·진단형·목 모호)가 있을 때. 그 외 절(예 '오늘은 괜찮아요', '잘 모르겠어요')은 문맥(해소·추정 단서)으로만 쓴다.
오프셋: (대체)질의 시작 + P5 span_start(P5 가 질의 text 에서 계산). 대체 질의 규칙 = symptom_span_extractor 5 — 원문 일치 실패 시 단위 전체 구간. raw_span 은 항상 source_text[start:end].
"""
from __future__ import annotations

import s29_common as S
from clause_segmenter import segment
from experiencer_analyzer import explicit
from negation_scope import assertion, sentence_hedge
from p5_normalizer_adapter import p5
from semantic_conflict_guard import guard, ideophones
from symptom_context_builder import model_input
from symptom_span_extractor import units
from temporality_analyzer import analyze as tanalyze
from temporality_analyzer import resolution_cue

POS = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "EXISTING_SUBTYPE", "NEW_ONTOLOGY_CANDIDATE")
LEVELS = ("NLU_P0", "NLU_P1", "NLU_P2", "NLU_P3", "NLU_P4", "NLU_P5")
KEEP = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "EXISTING_SUBTYPE", "NEW_ONTOLOGY_CANDIDATE", "NON_SYMPTOM", "UNKNOWN_SYMPTOM")
CAND_REASONS = ("KO_SILVER_CONFLICT", "AMBIGUOUS_CONCEPT_RELATION", "SILVER_HOLD", "CONCEPT_AMBIGUITY", "DIAGNOSIS_LIKE", "NECK", "SEMANTIC_CONFLICT")
P5_FIELDS = ("status", "canonical_id", "ontology_id", "relation_to_existing", "evidence_level", "isolation_status", "model_supported", "usable_by_disease_model",
             "display", "requires_confirmation", "reason", "evidence_sources", "ko_tier")


def keep(r: dict, text: str) -> bool:
    if r["status"] in KEEP:
        return True
    return r["status"] == "UNCERTAIN" and (S.S28.symptom_cue(text) or any(x in str(r.get("reason", "")) for x in CAND_REASONS) or bool(r.get("display")))


def _attrs(text, toks) -> list[str]:
    a = sorted(ideophones(text[min(t.start for t in toks):max(t.start + t.len for t in toks)])) if toks else []
    for i, t in enumerate(toks):
        if t.tag.startswith("VA") and i + 1 < len(toks) and toks[i + 1].tag == "ETM" and i + 2 < len(toks) and toks[i + 2].tag.startswith("NN"):
            a.append(text[t.start:toks[i + 1].start + toks[i + 1].len])
        if t.form in ("듯이", "듯") and i > 0 and t.tag.startswith(("EC", "NNB", "VA")):
            a.append(text[toks[i - 1].start:t.start + t.len])
    return list(dict.fromkeys(a))


def _base(text, r, s, e, sent, role, unit_text):
    m = {k: r.get(k) for k in P5_FIELDS}
    m.update(source_text=text, raw_span=text[s:e], span_start=s, span_end=e, source_sentence=sent, normalized_phrase=r.get("normalized_expression"),
             role=role, unit_text=unit_text, ko_evidence=list(r.get("ko_evidence") or [])[:3], silver="SILVER" in str(r.get("evidence_sources")),
             is_symptom=r["status"] != "NON_SYMPTOM", raw_preserved=True, context_verified=False)
    return m


def p0(text: str) -> dict:
    ms = []
    for r in p5(text):
        if not keep(r, r.get("span_text", "")):
            continue
        s, e = r.get("span_start"), r.get("span_end")
        if not (isinstance(s, int) and isinstance(e, int) and 0 <= s < e <= len(text)):
            s, e = 0, len(text)
        m = _base(text, r, s, e, text, "SINGLE", r.get("span_text", ""))
        subj = str(r.get("subject") or "")
        m.update(assertion="ABSENT" if r.get("polarity") == "NEGATIVE" else "PRESENT", assertion_basis="P5_POLARITY", temporality="UNKNOWN", onset_text=None,
                 duration_text=None, frequency_text=None, time_scope="NONE", experiencer="OTHER_PERSON" if subj.startswith("OTHER_PERSON") else "PATIENT",
                 experiencer_basis="P5_SUBJECT" if subj.startswith("OTHER_PERSON") else "ASSUMED_INTAKE_DEFAULT", attributes=[], trigger_text=None)
        m["model_input"] = model_input(m)
        ms.append(m)
    return {"source_text": text, "level": "NLU_P0", "mentions": ms, "context": {}}


def analyze(text: str, level: str = "NLU_P5") -> dict:
    if level == "NLU_P0":
        return p0(text)
    L = LEVELS.index(level)
    neg, temp, exp, grd = L >= 2, L >= 3, L >= 4, L >= 5
    clauses = segment(text)
    mentions, ctx = [], {"triggers": [], "context_clauses": []}
    sent_state: dict[int, dict] = {}
    trigger = None
    for ci, cl in enumerate(clauses):
        st = sent_state.setdefault(cl["sentence_index"], {"exp": None, "onset": None, "prev": []})
        if cl["kind"] == "TRIGGER":
            trigger = cl["text"]
            ctx["triggers"].append({"text": cl["text"], "start": cl["start"], "end": cl["end"]})
            continue
        ex, ex_basis = explicit(cl["tokens"]) if exp else (None, "")
        if ex:
            st["exp"] = (ex, ex_basis)
        clause_ms = []
        tinfo = tanalyze(cl["text"], cl["tokens"]) if temp else None
        for u in units(text, cl):
            res = [(r, u["q_start"], u["query"]) for r in p5(u["query"])]
            if not any(r["status"] in POS for r, _, _ in res):
                for fa, fb, fq in u["fallbacks"]:
                    alt = [(r, fa, fq) for r in p5(fq)]
                    if any(r["status"] in POS for r, _, _ in alt):
                        res = [(dict(r, fallback_query=fq), qa, qq) for r, qa, qq in alt]
                        break
            for r, qa, qq in res:
                if not keep(r, qq):
                    continue
                s, e = u["start"], u["end"]
                rs, re_ = r.get("span_start"), r.get("span_end")
                if isinstance(rs, int) and isinstance(re_, int) and 0 <= rs < re_ <= len(qq) and qq[rs:re_] == r.get("span_text"):
                    s, e = qa + rs, qa + re_
                m = _base(text, r, s, e, cl["source_sentence"], u["role"], u["text"])
                if neg:
                    a, ab = assertion(u["pred_tokens"])
                else:
                    a, ab = "PRESENT", "NOT_ANALYZED(P1)"
                m.update(assertion=a, assertion_basis=ab)
                if temp:
                    ut = tanalyze(u["text"], u["pred_tokens"]) if u["role"] != "COORDINATED" else tinfo
                    if not ut["onset_text"] and tinfo["onset_text"]:
                        ut = {**ut, "onset_text": tinfo["onset_text"]}
                    scope = "CLAUSE" if (ut["onset_text"] or ut["duration_text"] or ut["frequency_text"]) else ("UNCERTAIN" if st["onset"] else "NONE")
                    m.update(temporality=ut["temporality"] if ut["temporality"] != "UNKNOWN" else tinfo["temporality"], onset_text=ut["onset_text"],
                             duration_text=ut["duration_text"], frequency_text=ut["frequency_text"], time_scope=scope,
                             inherited_onset_candidate=st["onset"] if scope == "UNCERTAIN" else None)
                else:
                    m.update(temporality="UNKNOWN", onset_text=None, duration_text=None, frequency_text=None, time_scope="NONE")
                if exp:
                    if ex:
                        m.update(experiencer=ex, experiencer_basis=ex_basis)
                    elif st["exp"]:
                        m.update(experiencer=st["exp"][0], experiencer_basis="INHERITED:" + st["exp"][1])
                    else:
                        m.update(experiencer="PATIENT", experiencer_basis="ASSUMED_INTAKE_DEFAULT")
                else:
                    m.update(experiencer="PATIENT", experiencer_basis="NOT_ANALYZED(ASSUMED)")
                m["attributes"] = _attrs(text, u["tokens"])
                m["trigger_text"] = trigger
                if grd:
                    m = guard(m, u["text"], cl["source_sentence"], u["tokens"])
                clause_ms.append(m)
        if temp and tinfo and tinfo["onset_text"]:
            st["onset"] = tinfo["onset_text"]
        if not clause_ms:
            ctx["context_clauses"].append(cl["text"])
            if neg and sentence_hedge(cl["text"]):
                for pm in st["prev"]:
                    if pm["assertion"] == "PRESENT":
                        pm.update(assertion="POSSIBLE", assertion_basis="SENTENCE_HEDGE:" + cl["text"])
            if temp and resolution_cue(cl["text"]):
                for pm in st["prev"]:
                    pm.update(temporality="RESOLVED", resolution_text=cl["text"])
        else:
            st["prev"] = clause_ms
            trigger = None
        prim = [i for i, x in enumerate(clause_ms) if x["role"] == "PRIMARY"]
        for x in clause_ms:
            if x["role"] == "ASSOCIATED" and prim:
                x["detail_of_span"] = [clause_ms[prim[0]]["span_start"], clause_ms[prim[0]]["span_end"]]
        mentions += clause_ms
    for m in mentions:
        m["model_input"] = model_input(m)
        if m["status"] in ("UNCERTAIN", "UNKNOWN_SYMPTOM") and not m.get("reason") and not m.get("guard_reasons"):
            m["reason"] = "NO_SUPPORTED_LINK(원문 보존)"
    return {"source_text": text, "level": level, "mentions": mentions, "context": ctx}


if __name__ == "__main__":
    import json
    import sys
    for t in sys.argv[1:]:
        o = analyze(t)
        for m in o["mentions"]:
            print(json.dumps({k: m.get(k) for k in ("raw_span", "span_start", "span_end", "role", "status", "canonical_id", "ontology_id", "assertion", "temporality",
                                                     "onset_text", "time_scope", "experiencer", "experiencer_basis", "attributes", "guard_reasons", "model_input")},
                             ensure_ascii=False))
