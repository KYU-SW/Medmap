"""STEP29.2 의미 구별 검사기 v6(새 파일 — STEP29.1 v5·STEP29 v4·STEP28.8 v3 은 그대로). NLU 정책 구현 전 validate_evaluator_v6.py 로 정답 대조 후 SHA 고정.

검사 단위 = mention. 범위(scope) = 그 mention 의 unit_text(없으면 raw_span). 다른 구문(같은 문장의 질환·약물·검사 단어)은 이 mention 판정에 쓰지 않는다.
문장 문맥은 추위 단서(오한 vs 떨림)에만 쓴다. assertion 규칙은 mention 에 assertion 키가 있을 때만 적용.
 SPAN_INVALID            : 0 ≤ start < end ≤ len, raw_span == source_text[start:end] 위반
 EPISTAXIS_AS_BLEEDING   : 범위에 '코피' + concept ∈ {hemoptysis, hematemesis}
 BLOOD_ROUTE_MISMATCH    : 범위에 명사 '피' + '기침' → hematemesis 면 위반 · 범위에 '피' + 구토 단서(기침 없음) → hemoptysis 면 위반
 VOMIT_AS_NAUSEA         : 범위에 구토 단서(구토(감·기 제외)·토하·토했·토해·게워·오바이트), 양태 없음 + concept nausea(vomiting 없음)
 MODAL_VOMIT_AS_VOMITING : 범위에 구토 단서(+'토할') + 양태(것(만) 같·듯·할 것·싶) + concept vomiting(nausea 없음)
 NAUSEA_AS_VOMITING      : 범위에 메스꺼·메스껍·오심·구역(헛구역 제외 — 기존 정답이 헛구역질을 vomiting 으로 둠) + concept vomiting(nausea 없음)
 TREMOR_AS_CHILLS        : 범위에 명사 '떨림' 또는 (떨리·떨려 + 손·손가락·팔·다리·입술·눈꺼풀), 문장에 추위 단서 없음 + concept chills
 BODY_PART_ONLY          : 범위에 용언·증상 단서가 없고 마지막 명사가 부분·쪽·부위·근처·주위 + concept 있음
 DRUG_OR_TREATMENT_TERM  : 범위의 핵어 명사구가 약물·치료·검사(STEP27 NON_TYPE_CUE)이고, 그 구를 뺀 범위에 증상 단서 없음 + 증상 concept
 DISEASE_TERM            : 핵어 명사구(접두 포함 이어붙임)가 질환(NON_TYPE disease 또는 질환 어휘 DISEASE_LEX 포함)이고 그 구를 뺀 범위에 증상 단서 없음 + 증상 concept.
                           v5 와 다른 점: 'X성' 수식어는 핵어가 증상 명사(SYMPTOM_HEAD 또는 STEP27 증상 단서)이면 증상 성질·양상(박동성 두통·회전성 어지럼증)으로
                           보고 위반 아님. 핵어가 증상 명사가 아닌 'X성 …'(알레르기성 비염)만 질환형.
 UNCERTAIN_AUTO_ACCEPT   : EXISTING 자동 수락인데 가드 사유가 있거나 KO 근거가 PHRASE(부분 일치)
 NEGATION_MISSED         : 범위 술어에 명시 부정(안·못 MAG, 않 VX, 증상 명사 뒤 없 VA)이 있는데 assertion PRESENT.
                           예외: 이중 부정(건/게 아니·지 않은 건) · 개선 술어 부정(안 내려·안 떨어져·안 멈춰·안 멎·안 나아·안 낫·안 가라앉) ·
                           결핍 표현(힘·기운·기력·입맛·식욕·밥맛 + 없) · concept 의 한국어 표준 표현에 부정이 들어 있음(예 냄새를 못 맡음) · 양태(것 같) 동반
 SPURIOUS_NEGATION       : assertion ABSENT 인데 범위에 부정·평가형(괜찮·멀쩡·정상·문제 없)·개선/해소 술어가 하나도 없음(다른 절의 부정·해소가 전파된 경우)
concept = EXISTING_CANONICAL/COMPOSITE 의 canonical_id + 표시 후보. 규칙은 알려진 사례에서 나왔고 일반화 성능 주장 없음.
"""
from __future__ import annotations

import re
from pathlib import Path

import s292_common as S
from extract_symptom_spans import kiwi

EVALUATOR_VERSION = "v6"
VOMIT = re.compile(r"(구토(?![감기])|토하|토했|토해|게워|오바이트)")
VOMIT_M = re.compile(r"(토할|토하|토해|구토(?![감기])|게워|오바이트)")
MODAL = re.compile(r"(것\s*만?\s*같|듯|할\s*것|싶)")
NAUSEA = re.compile(r"(메스꺼|메스껍|오심|(?<!헛)구역)")   # 헛구역질 = 기존 정답(pilot·STEP23) 관례상 구토 쪽 → 제외(v5 와 같음)
COLD = re.compile(r"(오한|춥|추워|으슬|한기)")
LIMB = re.compile(r"(손|팔|다리|입술|눈꺼풀)")
GENERIC_PLACE = {"부분", "쪽", "부위", "근처", "주위"}
EXISTING = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")
DISEASE_LEX = {"고혈압", "당뇨", "당뇨병", "천식", "위염", "장염", "비염", "통풍", "편두통", "감기", "독감", "폐렴", "기관지염", "부비동염", "역류성식도염", "식도염"}
SYMPTOM_HEAD = {"두통", "복통", "흉통", "요통", "치통", "어지럼증", "어지럼", "현기증", "통증", "기침", "마른기침", "가래", "설사", "구토", "오심", "구역", "구역질", "발열", "열",
                "오한", "피로", "피로감", "부종", "붓기", "호흡곤란", "메스꺼움", "속쓰림", "두근거림", "경련", "마비", "저림", "근육통", "몸살", "인후통", "가려움", "발진"}
NEG_IMPROVE = re.compile(r"안\s*(내려|떨어|멈|멎|나아|낫|나았|가라앉|없어지|사라지|줄)")
DOUBLE_NEG = re.compile(r"(건|게|것은|것이)\s*아니|지\s*않은\s*건|않은\s*건\s*아니")
FUNC = {"힘", "기운", "기력", "입맛", "식욕", "밥맛", "의욕"}
EVAL_OR_RESOLVE = re.compile(r"(괜찮|멀쩡|정상|문제\s*없|나았|나아|낫|좋아지|좋아졌|없어지|없어졌|사라지|사라졌|멈췄|멎었|가라앉)")
_LEXNEG = None


def lexicalized_negation_concepts() -> set[str]:
    """concept 의 한국어 표준 표현(STEP28 inventory evidence_label_ko)에 부정어가 들어 있으면 부정형이 곧 증상(예 E_103 냄새를 못 맡음)."""
    global _LEXNEG
    if _LEXNEG is None:
        _LEXNEG = {r["canonical_id"] for r in S.read_csv(S.S28.DATA / "existing_concept_inventory.csv")
                   if re.search(r"(못|안\s|않|없)", r.get("evidence_label_ko") or "")}
    return _LEXNEG


def _head(toks, scope):
    idx = [i for i, k in enumerate(toks) if k.tag.startswith("NN") and k.tag != "NNB"]
    comp = []
    if idx:
        j = idx[-1]
        comp = [j]
        while comp[0] - 1 >= 0 and toks[comp[0] - 1].tag.startswith(("NN", "XSN", "XPN")) and toks[comp[0] - 1].tag != "NNB":
            comp.insert(0, comp[0] - 1)
        if j + 1 < len(toks) and toks[j + 1].tag == "XSN":
            comp.append(j + 1)
    words = []
    for i in comp:
        if toks[i].tag == "XSN" and words:
            words[-1] += toks[i].form
        else:
            words.append(toks[i].form)
    rest = "".join(scope[k.start:k.start + k.len] for i, k in enumerate(toks) if i not in comp)
    return comp, words, rest


def _is_symptom_head(w: str) -> bool:
    return w in SYMPTOM_HEAD or any(w.endswith(x) for x in ("통", "통증", "어지럼증")) or bool(S.S28.symptom_cue(w))


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
    toks = kiwi().tokenize(scope)
    if "코피" in x and cs & {"hemoptysis", "hematemesis"}:
        v.append("EPISTAXIS_AS_BLEEDING")
    blood = any(k.form == "피" and k.tag.startswith("NN") for k in toks) and "코피" not in x
    if blood and "기침" in x and "hematemesis" in cs and "hemoptysis" not in cs:
        v.append("BLOOD_ROUTE_MISMATCH")
    if blood and VOMIT.search(x) and "기침" not in x and "hemoptysis" in cs and "hematemesis" not in cs:
        v.append("BLOOD_ROUTE_MISMATCH")
    if VOMIT.search(x) and not MODAL.search(scope) and "nausea" in cs and "vomiting" not in cs:
        v.append("VOMIT_AS_NAUSEA")
    if VOMIT_M.search(x) and MODAL.search(scope) and "vomiting" in cs and "nausea" not in cs:
        v.append("MODAL_VOMIT_AS_VOMITING")
    if NAUSEA.search(x) and "vomiting" in cs and "nausea" not in cs:
        v.append("NAUSEA_AS_VOMITING")
    if ("떨림" in x or (re.search(r"(떨리|떨려)", x) and LIMB.search(x))) and not COLD.search(sent) and "chills" in cs:
        v.append("TREMOR_AS_CHILLS")
    nouns = [k.form for k in toks if k.tag.startswith("NN") and k.tag != "NNB"]
    has_pred = any(k.tag.startswith(("VV", "VA", "XSV", "XSA")) for k in toks)
    if nouns and not has_pred and not S.S28.symptom_cue(scope) and nouns[-1] in GENERIC_PLACE:
        v.append("BODY_PART_ONLY")
    comp, words, rest = _head(toks, scope)
    rest_cue = S.S28.symptom_cue(rest)
    last = words[-1] if words else ""
    nt = S.S28.non_type(last) if last else ""
    if nt in ("drug", "treatment", "test") and not rest_cue:
        v.append("DRUG_OR_TREATMENT_TERM")
    head_sym = bool(last) and _is_symptom_head(last) and last not in DISEASE_LEX
    headstr = "".join(toks[i].form for i in comp)   # 접두(XPN '고'+혈압)까지 이어붙인 핵어 명사구
    disease = nt == "disease" or last in DISEASE_LEX or any(d in headstr for d in DISEASE_LEX) or \
        (any(w.endswith("성") and len(w) >= 2 for w in words[:-1]) and not head_sym)
    if disease and not head_sym and not rest_cue:
        v.append("DISEASE_TERM")
    if m.get("status") in EXISTING and (m.get("guard_reasons") or m.get("ko_tier") == "PHRASE"):
        v.append("UNCERTAIN_AUTO_ACCEPT")
    a = m.get("assertion")
    if a and m.get("status") in EXISTING:
        neg = []
        for i, k in enumerate(toks):
            if (k.form, k.tag) in (("안", "MAG"), ("못", "MAG")) or (k.form == "않" and k.tag == "VX"):
                neg.append(i)
            elif k.form == "없" and k.tag.startswith("VA"):
                prev = [p.form for p in toks[:i] if p.tag.startswith("NN") and p.tag != "NNB"]
                if not (prev and prev[-1] in FUNC):
                    neg.append(i)
        lexneg = m.get("canonical_id") in lexicalized_negation_concepts()
        if a == "PRESENT" and neg and not lexneg and not DOUBLE_NEG.search(scope) and not NEG_IMPROVE.search(scope) and not MODAL.search(scope):
            v.append("NEGATION_MISSED")
        if a == "ABSENT" and not neg and not EVAL_OR_RESOLVE.search(scope) and not any(k.form == "없" for k in toks):
            v.append("SPURIOUS_NEGATION")
    return v


def evaluate(output: dict) -> list[dict]:
    return [{"raw_span": m.get("raw_span"), "span_start": m.get("span_start"), "concept": m.get("canonical_id"), "violation": x}
            for m in output.get("mentions", []) for x in mention_violations(m)]


def evaluator_sha() -> str:
    import hashlib
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
