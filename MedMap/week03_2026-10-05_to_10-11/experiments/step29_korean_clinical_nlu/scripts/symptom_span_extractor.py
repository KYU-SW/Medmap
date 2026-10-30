"""STEP29 절 → 증상 언급 단위(unit). 규칙(사전 고정):
 1 관계절 분리: 관형형 ETM 바로 뒤가 일반 명사(NNG/NNP, 의존명사 것·건·수·듯 제외)이고 ETM 앞(같은 단위)에 명사와 용언이 모두 있으면
   ETM 까지 = ASSOCIATED(세부·동반, 예 '누런 가래가 나오는') · 나머지 = PRIMARY(예 '기침을 해요'). 형용사 하나 + ETM(누런)은 속성으로 남김.
 2 병렬 명사 분리: 명사 사이 접속조사 JC(과·와·이나·나·랑·하고) → 앞 명사구는 COORDINATED 단위(술어는 절의 것을 공유).
 3 그 외 = SINGLE. 단위 text = source_text[start:end].
 4 P5 질의 시작(q_start, NLU 전처리 — P5 는 그대로): 단위 앞쪽의 주체 명사(가족·1인칭)·시점어·숫자·시간 단위·빈도/정도 부사(계속·가끔·너무 …)와
   그 조사, 명사 앞 형용사 수식어(용언+ETM, 예 '누런' — 속성으로 따로 보존)는 질의에서 뺀다. 최소 1 토큰은 남긴다. 질의 = source_text[q_start:end].
 5 대체 질의(fallback_queries): P5 결과에 concept 이 없을 때만 순서대로 시도 — (a) 첫 명사 묶음(+조사)까지 (b) 첫 부정 표지 앞까지(뒤쪽 의존명사·조사 제외).
   대체 질의 결과는 EXISTING·SUBTYPE·NEW 일 때만 채택(아니면 원 질의 결과 유지). 모두 원문 부분 문자열."""
from __future__ import annotations

NOUN = {"NNG", "NNP", "XR", "SL", "NR"}
PRED = {"VV", "VA", "VA-I", "VV-I", "VV-R", "VA-R", "VX", "VCP", "VCN"}
BOUND = {"것", "건", "수", "듯", "적", "데", "때", "줄", "만큼"}


import re

from experiencer_analyzer import KIN, SELF

TIME_W = re.compile(r"^(어제|오늘|그제|그저께|요즘|최근|아까|지난|어젯밤|아침|저녁|밤|새벽|며칠|일주일|한달|작년|올해|예전|전|동안|지금|현재|이번|주말|오전|오후|방금|째|일|주|달|년|시간|개월|주일)$")
LEAD_MAG = {"계속", "가끔", "자주", "잠깐", "아까", "지금", "요즘", "너무", "좀", "많이", "정말", "진짜", "또", "다시", "늘", "항상", "매일", "갑자기", "요새", "자꾸", "조금", "살짝", "엄청"}


def query_start(toks) -> int:
    i = 0
    while i < len(toks) - 1:
        t = toks[i]
        if ((t.tag.startswith("NN") and (t.form in KIN or TIME_W.match(t.form))) or t.tag in ("SN", "NR") or (t.tag == "NP" and t.form in SELF)
                or (t.tag == "MAG" and t.form in LEAD_MAG) or (i > 0 and t.tag in ("JX", "JKS", "JKB", "JKG", "XSN"))):
            i += 1
            continue
        if t.tag.startswith("VA") and i + 2 < len(toks) and toks[i + 1].tag == "ETM" and toks[i + 2].tag in ("NNG", "NNP"):
            i += 2
            continue
        break
    return toks[i].start


NEGM = {("없", "VA"), ("않", "VX"), ("안", "MAG"), ("못", "MAG"), ("못하", "VX"), ("아니", "VCN")}


def fallback_queries(text, toks, q):
    rest = [t for t in toks if t.start >= q]
    out = []
    i = 0
    while i < len(rest) and rest[i].tag in NOUN:
        i += 1
    if i:
        j = i
        while j < len(rest) and rest[j].tag.startswith("J"):
            j += 1
        out.append((q, rest[j - 1].start + rest[j - 1].len))
    k = next((n for n, t in enumerate(rest) if (t.form, t.tag) in NEGM), None)
    if k:
        pre = rest[:k]
        while pre and (pre[-1].tag in ("NNB", "EC", "ETM") or pre[-1].tag.startswith("J")):
            pre = pre[:-1]
        if pre:
            out.append((q, max(t.start + t.len for t in pre)))
    return [(a, b, text[a:b]) for a, b in dict.fromkeys(out) if b > a]


def _u(text, toks, role, shared=None):
    s, e = min(t.start for t in toks), max(t.start + t.len for t in toks)
    q = query_start(toks)
    return {"tokens": toks, "start": s, "end": e, "text": text[s:e], "q_start": q, "query": text[q:e], "role": role, "pred_tokens": shared or toks,
            "fallbacks": fallback_queries(text, toks, q)}


def units(text: str, clause: dict) -> list[dict]:
    toks = clause["tokens"]
    if not toks:
        return []
    out, body = [], toks
    for i, t in enumerate(toks):
        if t.tag == "ETM" and i + 1 < len(toks) and toks[i + 1].tag in ("NNG", "NNP") and toks[i + 1].form not in BOUND:
            before = toks[:i]
            if any(x.tag in NOUN for x in before) and any(x.tag in PRED - {"VX", "VCP", "VCN"} for x in before):
                out.append(_u(text, toks[:i + 1], "ASSOCIATED"))
                body = toks[i + 1:]
                break
    groups, cur = [], []
    for t in body:
        if t.tag == "JC" and cur and any(x.tag in NOUN for x in cur):
            groups.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        groups.append(cur)
    role_last = "PRIMARY" if out else ("SINGLE" if len(groups) == 1 else "COORDINATED")
    for g in groups[:-1]:
        out.append(_u(text, g, "COORDINATED", shared=body))
    if groups and groups[-1]:
        out.append(_u(text, groups[-1], role_last, shared=body))
    return out
