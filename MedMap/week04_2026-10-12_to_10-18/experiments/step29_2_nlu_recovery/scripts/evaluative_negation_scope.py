"""STEP29.2 §6 평가형 부정 범위(STEP29.1 evaluative_negation.apply 를 그대로 호출한 뒤 범위만 제한 — 원본 무수정). 하위 문장(문장 분리 뒤) 단위로 실행.
규칙:
 E1 범위 제한: 평가 술어(괜찮·멀쩡·정상이다·문제없다)가 mention 의 핵심 명사 뒤 같은 술어 사슬에 있을 때만 적용. 사이에 종결어미 EF 또는
    다른 내용 용언(VV·VA, 보조 하·있·되 제외)이 있으면 그 mention 의 assertion 은 STEP29 값 그대로(다른 절의 '괜찮다'가 넘어오지 않음).
 E2 불확실 평가: 평가 술어 뒤 '-지/-는지/-은지/-ㄴ지/건지' + 모르·헷갈·긴가민가 → ABSENT 대신 POSSIBLE + assertion_certainty LOW(EVAL_UNCERTAIN, 확인 필요).
 E3 비증상 대상 평가: concept 없는 mention 이 평가형 부정이고, 범위 명사에 신체 부위·신체 기능·증상 명사가 하나도 없으면(검사 결과·엑스레이·날씨 등)
    증상 mention 이 아니라 문맥(drop_as_context) — 증상 부정을 만들지 않음. 약물·검사·치료 명사(STEP27 NON_TYPE)가 있어도 같음.
 E4 concept 있는 평가형 부정은 concept 연결 근거가 부분 일치(PHRASE)뿐이면 assertion_certainty LOW(확인 필요).
 E6 부위만 평가형 부정: '가슴은 괜찮아요' 처럼 범위 명사가 신체 부위뿐이면 어떤 증상의 부정인지 특정할 수 없으므로 concept 을 보류(UNCERTAIN·ABSENT 유지,
    원 concept 은 eval_site_concept). 기능 명사(입맛·숨·열 등)는 concept 유지.
 E5 개선 부정 확장: '안 떨어져·안 빠져·내리지 않' 등 STEP29.1 개선 동사 목록 밖의 개선 술어 부정 → PRESENT(NEGATED_IMPROVEMENT, 지속).
 나머지(이중 부정·개선 부정·결핍 표현·개념 어휘 부정·간접 의문)는 STEP29.1 규칙 그대로."""
from __future__ import annotations

import re

import s292_common as S
import evaluative_negation as EVN
from extract_symptom_spans import kiwi

UNSURE_AFTER = re.compile(r"(괜찮|멀쩡)[가-힣\s]{0,6}?(지|건지)\s*(잘\s*)?(모르|헷갈|긴가민가)")
FUNC_N = {"몸", "속", "정신", "힘", "기운", "기력", "입맛", "식욕", "밥맛", "체온", "열", "숨", "변", "대변", "소변", "가래", "침", "땀", "컨디션", "상태", "증상",
          "기분", "느낌", "잠", "소화", "호흡", "맛"}
AUX = {"하", "있", "되", "않", "주", "보"}


def _body() -> set[str]:
    return set(S.S28.body_parts()) | {"머리", "배", "목", "가슴", "허리", "팔", "다리", "손", "발", "어깨", "등", "옆구리", "눈", "코", "귀", "입", "얼굴", "무릎",
                                      "심장", "위", "장", "목구멍", "편도", "관절", "피부", "속"}


_B = None


def body():
    global _B
    if _B is None:
        _B = _body()
    return _B


def _symptomish_noun(n: str) -> bool:
    return n in body() or n in FUNC_N or bool(S.S28.symptom_cue(n))


NEG_IMPROVE = re.compile(r"(안\s*(떨어|내려|나아|낫|나았|멈|멎|가라앉|줄|빠지|빠져)|(떨어지|내리|나아지|멈추|멎|가라앉|줄어들|빠지)\S*\s*(지는|지도|지)\s*않)")


def apply(m: dict, clause_text: str) -> dict:
    out = EVN.apply(m, clause_text)
    if out.get("assertion") == "ABSENT" and out.get("is_symptom") and NEG_IMPROVE.search(m.get("unit_text") or m["raw_span"]):
        return {**out, "assertion": "PRESENT", "assertion_basis": "NEGATED_IMPROVEMENT(지속)"}   # E5 '열이 안 떨어져요' = 지속(STEP29.1 목록에 없던 개선 동사)
    basis = str(out.get("assertion_basis") or "")
    if not basis.startswith("EVALUATIVE_NEGATION") and basis not in ("EVAL_NEGATED_COMPLAINT", "EVAL_DOUBLE_NEGATION"):
        return out
    unit = m.get("unit_text") or m["raw_span"]
    toks = kiwi().tokenize(unit)
    ei = EVN.eval_predicate(toks)
    nidx = [i for i, t in enumerate(toks[:ei] if ei is not None else toks) if t.tag.startswith(("NN", "NP")) and t.tag != "NNB"]
    # E1 범위 제한
    if ei is not None and nidx:
        between = toks[nidx[-1] + 1:ei]
        if any(t.tag == "EF" for t in between) or any(t.tag.startswith(("VV", "VA")) and t.form not in AUX for t in between):
            keep = dict(m)
            keep["eval_scope_blocked"] = True
            return keep
    # E3 비증상 대상
    nouns = [t.form for t in toks if t.tag.startswith("NN") and t.tag != "NNB"]
    if not (m.get("canonical_id") or m.get("ontology_id")) and basis.startswith("EVALUATIVE_NEGATION"):
        nt = any(S.S28.non_type(n) in ("drug", "test", "treatment", "disease") for n in nouns)
        if nouns and (nt or not any(_symptomish_noun(n) for n in nouns)):
            return {**out, "is_symptom": False, "drop_as_context": True, "context_reason": "EVAL_OF_NON_SYMPTOM_TARGET"}
    # E2 불확실 평가
    src = m.get("source_text") or ""
    after = src[m.get("span_start", 0):]
    if basis.startswith("EVALUATIVE_NEGATION") and UNSURE_AFTER.search(after):
        return {**out, "assertion": "POSSIBLE", "assertion_basis": "EVAL_UNCERTAIN", "assertion_certainty": "LOW", "requires_confirmation": True}
    # E6 부위만 평가: concept 있는 평가형 부정인데 범위 명사가 신체 부위뿐(기능 명사 아님) → 어떤 증상이 없는지 특정 불가 → concept 보류(UNCERTAIN, ABSENT 유지)
    if basis.startswith("EVALUATIVE_NEGATION") and out.get("status") in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE") and nouns and \
            all(n in body() and n not in FUNC_N for n in nouns):
        return {**out, "status": "UNCERTAIN", "eval_site_concept": out.get("canonical_id"), "canonical_id": None, "display": [], "requires_confirmation": True,
                "usable_by_disease_model": False, "model_supported": False, "reason": "EVAL_SITE_ONLY_CONCEPT_AMBIGUOUS"}
    # E4 부분 일치 근거
    if basis.startswith("EVALUATIVE_NEGATION") and m.get("ko_tier") == "PHRASE":
        return {**out, "assertion_certainty": "LOW", "requires_confirmation": True}
    return out
