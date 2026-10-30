"""STEP29.1 P3 — 평가형 부정·문맥 assertion(단위 범위, 키워드 치환 아님 — 그 mention 단위의 주 술어일 때만). 규칙(평가 전 고정):
 평가 술어 = 괜찮(VA) · 멀쩡(XR/VA) · 정상(NNG)+이다 · 문제(NNG)+없 — mention 단위 안에서 mention 명사 뒤에 올 때
   부정 0 → ABSENT(EVALUATIVE_NEGATION) · 추정(것 같·듯) 동반 → ABSENT + assertion_certainty LOW(확인 필요) · 뒤 부정 1(괜찮지 않) → PRESENT(불편 호소) ·
   뒤 부정 ≥2(괜찮지 않은 건 아니) → POSSIBLE
 개선 술어 부정(안 내려·안 나아·안 멈춰·없어지지 않 …) → PRESENT(NEGATED_IMPROVEMENT, 지속)
 개념 어휘에 부정이 들어 있음(P5 근거 용어가 '없·못·안·않' 포함, 예 '입맛이 없음'·'냄새를 못 맡음') + 질의에도 같은 부정 → PRESENT(NEGATION_LEXICALIZED_IN_CONCEPT)
 같은 절에 '모르겠·헷갈·긴가민가' → PRESENT 를 POSSIBLE(UNSURE_IN_CLAUSE)
 결핍 표현: 단위 명사가 기능 명사(힘·기운·기력·입맛·식욕·의욕)이고 부정이 '없' 하나뿐 → PRESENT(DEFICIT_EXPRESSION, 예 '힘이 없어요' = 기운 저하 호소)
 간접 의문('…건지·는지·은지·인지' 로 끝나는 단위) + 같은 문장 뒤에 모르·헷갈 → POSSIBLE(INDIRECT_QUESTION_UNSURE)
 단위가 불확실 동사(모르·헷갈)뿐이고 개념 없는 mention → is_symptom False(문맥, drop_as_context)"""
from __future__ import annotations

import s291_common  # noqa: F401  (경로)

import re

from extract_symptom_spans import kiwi

IMPROVE = {"나아지", "낫", "좋아지", "없어지", "사라지", "멈추", "멎", "내리", "가라앉"}
NEGW = {("않", "VX"), ("아니", "VCN"), ("안", "MAG"), ("못", "MAG")}
EV_RE = re.compile(r"^(EXACT|PHRASE|BOUNDARY):(UMLS_KOR:[^:]+|TERMINOLOGY_LABEL:E_\d+|[A-Za-z0-9_]+):(.*)$")
NEG_IN_TERM = re.compile(r"(없|못\s|못하|안\s|않)")
UNSURE = re.compile(r"(모르겠|모르겟|헷갈|긴가민가)")


def eval_predicate(toks):
    for i, t in enumerate(toks):
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        if (t.form == "괜찮" and t.tag.startswith("VA")) or (t.form.startswith("멀쩡")) or (t.form == "정상" and nxt is not None and nxt.tag == "VCP") \
                or (t.form == "문제" and nxt is not None and nxt.form == "없"):
            return i
    return None


def improve_predicate(toks):
    for i, t in enumerate(toks):
        if t.tag.startswith("VV") and (t.form in IMPROVE or any(t.form.startswith(w) for w in ("나아", "좋아지", "없어지", "사라지"))):
            return i
    return None


def apply(m: dict, clause_text: str) -> dict:
    if not m.get("is_symptom") or m["status"] == "NON_SYMPTOM":
        return m
    toks = kiwi().tokenize(m.get("unit_text") or m["raw_span"])
    out = dict(m)
    ei = eval_predicate(toks)
    if ei is not None:
        after = toks[ei + 1:]
        negs = [t for t in after if (t.form, t.tag) in NEGW]
        hedge = any(t.form in ("듯",) for t in after) or any(a.form in ("것", "거", "건") and b.form == "같" for a, b in zip(after, after[1:]))
        if len(negs) >= 2:
            out.update(assertion="POSSIBLE", assertion_basis="EVAL_DOUBLE_NEGATION")
        elif len(negs) == 1:
            out.update(assertion="PRESENT", assertion_basis="EVAL_NEGATED_COMPLAINT")
        elif hedge:
            out.update(assertion="ABSENT", assertion_basis="EVALUATIVE_NEGATION_HEDGED", assertion_certainty="LOW", requires_confirmation=True)
        else:
            out.update(assertion="ABSENT", assertion_basis="EVALUATIVE_NEGATION")
        return out
    ii = improve_predicate(toks)
    if ii is not None:
        before = toks[max(0, ii - 2):ii] + toks[ii + 1:ii + 3]
        if any((t.form, t.tag) in NEGW for t in before) and m["assertion"] in ("ABSENT", "POSSIBLE"):
            out.update(assertion="PRESENT", assertion_basis="NEGATED_IMPROVEMENT(지속)")
            return out
    FUNC = {"힘", "기운", "기력", "입맛", "식욕", "의욕"}
    nn = [t.form for t in toks if t.tag.startswith("NN") and t.tag != "NNB"]
    negforms = [t.form for t in toks if (t.form, t.tag) in NEGW or (t.form == "없" and t.tag.startswith("VA"))]
    if m["assertion"] == "ABSENT" and nn and nn[-1] in FUNC and negforms == ["없"]:
        out.update(assertion="PRESENT", assertion_basis="DEFICIT_EXPRESSION")
        return out
    if m["assertion"] == "ABSENT":
        terms = [mm.group(3) for e in m.get("ko_evidence") or [] for mm in [EV_RE.match(e)] if mm]
        q = m.get("unit_text") or m["raw_span"]
        if terms and any(NEG_IN_TERM.search(x) for x in terms) and NEG_IN_TERM.search(q):
            out.update(assertion="PRESENT", assertion_basis="NEGATION_LEXICALIZED_IN_CONCEPT")
            return out
    if m["assertion"] == "PRESENT" and UNSURE.search(clause_text or ""):
        out.update(assertion="POSSIBLE", assertion_basis="UNSURE_IN_CLAUSE")
    q = m.get("unit_text") or m["raw_span"]
    if out["assertion"] == "PRESENT" and re.search(r"(건지|는지|은지|인지|ㄴ지)\s*$", q) and UNSURE.search(m["source_text"][m["span_start"]:]):
        out.update(assertion="POSSIBLE", assertion_basis="INDIRECT_QUESTION_UNSURE")
    if not (m.get("canonical_id") or m.get("ontology_id")) and UNSURE.search(q) and not [t for t in toks if t.tag.startswith("NN") and t.tag != "NNB"]:
        out.update(is_symptom=False, drop_as_context=True)
    return out
