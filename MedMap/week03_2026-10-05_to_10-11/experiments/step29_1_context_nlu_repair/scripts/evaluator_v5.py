"""STEP29.1 의미 구별 검사기 v5(새 파일 — STEP28.8 v3·STEP29 v4 는 그대로). 정책 평가 전 validate_evaluator_v5.py 로 정답 대조 후 SHA 고정.

검사 단위 = mention(문장 → 절·단위 → mention). 규칙은 그 mention 의 범위(scope = unit_text, 없으면 raw_span)와 그 mention 의 concept 에만 적용하고,
추위 단서처럼 문장 문맥이 필요한 것만 source_sentence 를 본다. 다른 구문의 질환·약물·검사 단어는 이 mention 판정에 쓰지 않는다.
 SPAN_INVALID           : 0 ≤ start < end ≤ len, raw_span == source_text[start:end] 위반
 EPISTAXIS_AS_BLEEDING  : 범위에 '코피' + concept ∈ {hemoptysis, hematemesis}
 VOMIT_AS_NAUSEA        : 범위에 구토 단서(구토(감·기 제외)·토하·토했·토해·오바이트), 양태 없음 + concept = nausea
 MODAL_VOMIT_AS_VOMITING: 범위에 구토 단서(+'토할') + 양태(것 같·듯·할 것·싶) + concept = vomiting
 NAUSEA_AS_VOMITING     : 범위에 메스꺼·메스껍·오심·구역(헛구역 제외) + concept = vomiting
 TREMOR_AS_CHILLS       : 범위에 명사 '떨림' 또는 (떨리·떨려 + 손·팔·다리·입술·눈꺼풀), 문장에 추위 단서 없음 + concept = chills
 BODY_PART_ONLY         : 범위에 용언·증상 단서가 없고 마지막 명사가 부분·쪽·부위·근처·주위 + concept 있음(정답 대조 후 '모든 명사가 신체 부위' 조건 제외 — '목 따끔'·'얼굴' 사전 표현)
 DRUG_OR_TREATMENT_TERM : 범위의 핵어 명사구(마지막 명사 + 앞에 붙은 명사)가 약물·치료·검사 접미(STEP27 NON_TYPE_CUE)이고, 그 구를 뺀 범위에 증상 단서가 없음 + 증상 concept
 DISEASE_TERM           : 핵어 명사구가 질환 접미 · 'X성' 진단형 수식어(경과 수식어 제외) · '고혈압' 이고, 그 구를 뺀 범위에 증상 단서 없음 + 증상 concept
 UNCERTAIN_AUTO_ACCEPT  : EXISTING 자동 수락인데 가드 사유가 있거나 KO 근거가 PHRASE(부분 일치)
concept = EXISTING_CANONICAL/COMPOSITE 의 canonical_id + 표시 후보. 일반화 성능 주장 없음(규칙이 알려진 사례에서 나옴).
"""
from __future__ import annotations

import re
from pathlib import Path

import s291_common as S
from extract_symptom_spans import kiwi

EVALUATOR_VERSION = "v5"
VOMIT = re.compile(r"(구토(?![감기])|토하|토했|토해|오바이트)")
VOMIT_M = re.compile(r"(토할|토하|토해|구토(?![감기])|오바이트)")
MODAL = re.compile(r"(것\s*같|듯|할\s*것|싶)")
NAUSEA = re.compile(r"(메스꺼|메스껍|오심|(?<!헛)구역)")
COLD = re.compile(r"(오한|춥|추워|으슬|한기)")
LIMB = re.compile(r"(손|팔|다리|입술|눈꺼풀)")
COURSE = {"만성", "급성", "아급성", "반복성", "지속성", "간헐성", "일과성", "재발성", "진행성", "돌발성", "습관성"}
GENERIC_PLACE = {"부분", "쪽", "부위", "근처", "주위"}
EXISTING = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")
_BODY = None


def body():
    global _BODY
    if _BODY is None:
        _BODY = set(S.S28.body_parts()) | {"심장", "가슴", "머리", "배", "목", "허리", "팔", "다리", "손", "발", "어깨", "등", "옆구리", "눈", "코", "귀", "입", "얼굴", "무릎"}
    return _BODY


def mention_violations(m: dict) -> list[str]:
    v = []
    t = m.get("source_text", "")
    s, e = m.get("span_start"), m.get("span_end")
    if not (isinstance(s, int) and isinstance(e, int) and 0 <= s < e <= len(t) and t[s:e] == m.get("raw_span")):
        v.append("SPAN_INVALID")
    cs = set(([m["canonical_id"]] if m.get("status") in EXISTING and m.get("canonical_id") else []) + list(m.get("display") or []))
    if not cs:
        return v
    scope = m.get("unit_text") or m.get("raw_span") or ""
    x = re.sub(r"\s+", "", scope)
    sent = re.sub(r"\s+", "", m.get("source_sentence") or t)
    if "코피" in x and cs & {"hemoptysis", "hematemesis"}:
        v.append("EPISTAXIS_AS_BLEEDING")
    if VOMIT.search(x) and not MODAL.search(scope) and "nausea" in cs and "vomiting" not in cs:
        v.append("VOMIT_AS_NAUSEA")
    if VOMIT_M.search(x) and MODAL.search(scope) and "vomiting" in cs and "nausea" not in cs:
        v.append("MODAL_VOMIT_AS_VOMITING")
    if NAUSEA.search(x) and "vomiting" in cs and "nausea" not in cs:
        v.append("NAUSEA_AS_VOMITING")
    if ("떨림" in x or (re.search(r"(떨리|떨려)", x) and LIMB.search(x))) and not COLD.search(sent) and "chills" in cs:
        v.append("TREMOR_AS_CHILLS")
    toks = kiwi().tokenize(scope)
    nouns = [k.form for k in toks if k.tag.startswith("NN") and k.tag != "NNB"]
    has_pred = any(k.tag.startswith(("VV", "VA", "XSV", "XSA")) for k in toks)
    if nouns and not has_pred and not S.S28.symptom_cue(scope) and nouns[-1] in GENERIC_PLACE:
        v.append("BODY_PART_ONLY")
    # 핵어 명사구 = 마지막 일반 명사 + 바로 앞에 붙은 명사들(XSN 결합). 그 구를 뺀 나머지 범위에 증상 단서가 없을 때만 약물·질환 판정
    idx = [i for i, k in enumerate(toks) if k.tag.startswith("NN") and k.tag != "NNB"]
    comp = []
    if idx:
        j = idx[-1]
        comp = [j]
        while comp[0] - 1 >= 0 and toks[comp[0] - 1].tag.startswith(("NN", "XSN", "XPN")) and toks[comp[0] - 1].tag != "NNB":
            comp.insert(0, comp[0] - 1)
        if j + 1 < len(toks) and toks[j + 1].tag == "XSN":
            comp.append(j + 1)
    head = "".join(toks[i].form for i in comp if toks[i].tag.startswith(("NN", "XSN", "XPN"))) if comp else ""
    words = []
    for i in comp:
        if toks[i].tag == "XSN" and words:
            words[-1] += toks[i].form
        else:
            words.append(toks[i].form)
    rest = "".join(scope[k.start:k.start + k.len] for i, k in enumerate(toks) if i not in comp)
    rest_cue = S.S28.symptom_cue(rest)
    last = words[-1] if words else ""
    nt = S.S28.non_type(last) if last else ""
    if nt in ("drug", "treatment", "test") and not rest_cue:
        v.append("DRUG_OR_TREATMENT_TERM")
    if (nt == "disease" or any(w.endswith("성") and len(w) >= 2 and w not in COURSE for w in words) or "고혈압" in head) and not rest_cue:
        v.append("DISEASE_TERM")
    if m.get("status") in EXISTING and (m.get("guard_reasons") or m.get("ko_tier") == "PHRASE"):
        v.append("UNCERTAIN_AUTO_ACCEPT")
    return v


def evaluate(output: dict) -> list[dict]:
    return [{"raw_span": m.get("raw_span"), "span_start": m.get("span_start"), "concept": m.get("canonical_id"), "violation": x}
            for m in output.get("mentions", []) for x in mention_violations(m)]


def evaluator_sha() -> str:
    import hashlib
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
