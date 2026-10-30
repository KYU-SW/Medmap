"""STEP29.3 §6 한국어 형태 정규화(kiwipiepy 로컬). 원문은 바꾸지 않고 '검색 질의'만 만든다.

 mask_time(sub) → (masked, phrases): 시점 표현을 같은 길이 공백으로 가린 문자열(오프셋 보존) + 가린 구(원문·위치). 검색기(P5)가 '지난주에'를 '지나+ㄴ' 으로 잘라
   비증상 조각을 만들고 뒤 증상을 잃는 구문 경계 오류(SPAN_BOUNDARY_ERROR)를 막는다. 가린 정보는 mention 의 onset_text·시점으로 되돌린다.
   대상: 지난주·지난달·지난번·지난밤·지난 주말·어젯밤·어제·그저께·그제·오늘·아까·지금·이제·요즘·요새·며칠/사흘/이틀/N일·주·시간 전 (+에/에는/부터/은/는/도).
   '밤마다'처럼 빈도 표현은 가리지 않는다.
 canonical_query(unit, keep_modifiers) → 표준 질의: 부정(안·못·-지 (는/도) 않/못하) 제거 · 주제 조사 은/는 → 이/가 · 시제(EP)·마지막 술어 뒤 어미 제거 후 '-어요' 결합.
   keep_modifiers=False(N1): 부사(MAG) 모두 제거 — STEP28.8 nkey 처럼 의성어·부사 정보를 잃는다.
   keep_modifiers=True(N2 이상): 반복형 의성·의태어와 감각 부사(살살·콕콕·핑 등)는 남기고 시간·정도 부사만 제거.
 lemma_info(unit) → original_phrase · lemma_candidates(술어 어간) · core_predicate · anatomical_site · symptom_modifiers · negation(정규화 근거 기록용)."""
from __future__ import annotations

import re

import s293_common  # noqa: F401  (경로)
from evaluative_negation_scope import body
from extract_symptom_spans import kiwi
from semantic_conflict_guard import REDUP

TIME = re.compile(r"(?<![가-힣])(지난\s?(주말|주|달|번|밤|해)|어젯밤|어제|그저께|그제|오늘|아까|지금|이제|요즘|요새|(며칠|사흘|이틀|[0-9]+\s?(일|주|시간|달))\s?전)"
                  r"(에는|에|부터|은|는|도)?(?![가-힣])")
TIME_ADV = {"계속", "자꾸", "좀", "많이", "너무", "정말", "진짜", "아주", "또", "다시", "아직", "조금", "약간", "늘", "항상", "가끔", "자주", "이제", "벌써", "매일", "되게", "엄청", "다"}
SENSE_ADV = {"살살", "콕콕", "핑", "욱신", "찌릿", "덜덜", "부들부들", "바들바들", "펄펄", "턱턱", "빙빙", "빙글빙글", "왈칵", "주르륵", "울렁울렁", "화끈화끈", "지끈지끈", "쿡쿡"}
PRED = ("VV", "VA", "XSV", "XSA")


def mask_time(sub: str) -> tuple[str, list[dict]]:
    out, phr = sub, []
    for m in TIME.finditer(sub):
        a, b = m.span()
        out = out[:a] + " " * (b - a) + out[b:]
        phr.append({"text": m.group(0), "start": a, "end": b, "ongoing": (m.group(5) == "부터")})
    return out, phr


def _neg_strip(toks):
    out, i = [], 0
    while i < len(toks):
        t = toks[i]
        if (t.form, t.tag) in (("안", "MAG"), ("못", "MAG")):
            i += 1
            continue
        if t.form == "지" and t.tag == "EC":
            j = i + 1
            if j < len(toks) and toks[j].tag == "JX" and toks[j].form in ("는", "도"):
                j += 1
            if j < len(toks) and toks[j].form in ("않", "못하") and toks[j].tag.startswith("VX"):
                i = j + 1
                continue
        out.append(t)
        i += 1
    return out


def _josa(prev_form: str) -> str:
    ch = prev_form[-1]
    return "이" if "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 else "가"


def canonical_query(unit: str, keep_modifiers: bool) -> str | None:
    toks = _neg_strip(kiwi().tokenize(unit or ""))
    idx = [i for i, t in enumerate(toks) if t.tag.startswith(PRED) or (t.tag.startswith("VX") and t.form in ("있",))]
    if not idx:
        return None
    toks = toks[:idx[-1] + 1]
    keep = []
    for i, t in enumerate(toks):
        if t.tag in ("SF", "SP", "SS", "SE", "SO", "SW", "EP", "EF", "IC", "MAJ"):
            continue
        if t.tag == "MAG":
            if not keep_modifiers or t.form in TIME_ADV:
                continue
            if not (REDUP.fullmatch(t.form) or t.form in SENSE_ADV):
                continue
        if t.tag == "JX" and t.form in ("은", "는") and keep and keep[-1][1].startswith("NN"):
            keep.append((_josa(keep[-1][0]), "JKS"))
            continue
        keep.append((t.form, t.tag))
    if not keep or not keep[-1][1].startswith(PRED + ("VX",)):
        return None
    try:
        q = kiwi().join(keep + [("어요", "EF")])
    except Exception:  # noqa: BLE001  결합 실패 시 질의 없음(원문 결과 유지)
        return None
    return q if q and q.replace(" ", "") != (unit or "").replace(" ", "") else None


def lemma_info(unit: str) -> dict:
    toks = kiwi().tokenize(unit or "")
    preds = [t.form for t in toks if t.tag.startswith(PRED)]
    nouns = [t.form for t in toks if t.tag.startswith("NN") and t.tag != "NNB"]
    return {"original_phrase": unit, "lemma_candidates": preds, "core_predicate": preds[-1] if preds else None,
            "anatomical_site": [n for n in nouns if n in body()], "symptom_modifiers": [t.form for t in toks if t.tag == "MAG" and (REDUP.fullmatch(t.form) or t.form in SENSE_ADV)],
            "negation": any((t.form, t.tag) in (("안", "MAG"), ("못", "MAG")) or (t.form == "않" and t.tag.startswith("VX")) for t in toks)}
