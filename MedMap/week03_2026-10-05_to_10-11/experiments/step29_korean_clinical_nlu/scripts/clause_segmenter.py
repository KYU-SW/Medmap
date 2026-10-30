"""STEP29 문장·절 분해(kiwipiepy, 로컬). 오프셋 = Python 문자열 code point(kiwi 토큰 start/len 은 원문 위치 — 축약형은 토큰 구간이 겹치므로 구간 합집합으로 자른다).
규칙(사전 고정): 문장 = SF 토큰 경계 · 절 = 연결어미 EC 뒤(STEP28.5 NO_CUT_EC 어·아·게·지·여·고서 제외) + 관형형 ETM + 의존명사 '데'(kiwi 가 '-는데' 를 이렇게 분석) 뒤 ·
 트리거 절 = '…ㄹ/는 때(마다|에|면)' 까지(관형형 ETM + '때') — 증상 언급이 아니라 상황 문맥(예 '숨 쉴 때마다')으로 다음 절에 붙인다.
절 text 는 항상 source_text[start:end](정규화 문자열로 오프셋을 계산하지 않는다)."""
from __future__ import annotations

import re

from extract_symptom_spans import NO_CUT_EC, kiwi

PUNCT = {"SF", "SP", "SS", "SE", "SO", "SW", "SH"}


def _span(toks):
    toks = [t for t in toks if t.tag not in PUNCT]
    if not toks:
        return None
    return min(t.start for t in toks), max(t.start + t.len for t in toks)


def segment(text: str) -> list[dict]:
    toks = kiwi().tokenize(text or "")
    sents, cur = [], []
    for t in toks:
        cur.append(t)
        if t.tag == "SF":
            sents.append(cur)
            cur = []
    if cur:
        sents.append(cur)
    out = []
    for si, st in enumerate(sents):
        clauses, cur = [], []
        for j, t in enumerate(st):
            cur.append(t)
            nxt = st[j + 1] if j + 1 < len(st) else None
            if (t.tag == "EC" and not NO_CUT_EC.match(t.form)) or (t.form == "데" and t.tag == "NNB" and j > 0 and st[j - 1].tag == "ETM"):
                clauses.append(("NORMAL", cur))
                cur = []
            elif t.form == "때" and t.tag.startswith("NN") and j > 0 and st[j - 1].tag == "ETM":
                if nxt is not None and nxt.form in ("마다", "에", "면", "는", "에는"):
                    continue
                clauses.append(("TRIGGER", cur))
                cur = []
            elif j > 0 and st[j - 1].form == "때" and t.form in ("마다", "에", "면", "는", "에는") and j > 1 and st[j - 2].tag == "ETM":
                clauses.append(("TRIGGER", cur))
                cur = []
        if cur:
            clauses.append(("NORMAL", cur))
        ss = _span(st)
        for ci, (kind, ct) in enumerate(clauses):
            sp = _span(ct)
            if not sp:
                continue
            out.append({"sentence_index": si, "clause_index": ci, "kind": kind, "tokens": [t for t in ct if t.tag not in PUNCT],
                        "start": sp[0], "end": sp[1], "text": text[sp[0]:sp[1]], "sentence_start": ss[0] if ss else sp[0],
                        "sentence_end": ss[1] if ss else sp[1], "source_sentence": text[ss[0]:ss[1]] if ss else text[sp[0]:sp[1]]})
    return out
