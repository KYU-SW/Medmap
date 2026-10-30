"""STEP29.2 §4 문장 분리(마침표 없는 ASR 전사 지원, kiwipiepy 로컬 — 신규 설치 없음). sentences(text) → [{start, end, text, basis, kiwi_agrees}].

경계 규칙(형태소 태그 기준, 띄어쓰기·조사 하나만으로 자르지 않음):
 B1 SF(. ? !)                         → 그 뒤 경계. 문장 구간에는 '?' 만 포함(질문 판정용), '.'·'!' 는 제외 — 마침표 유무 쌍이 같은 하위 문장을 갖도록.
 B2 종결어미 EF + 뒤에 내용 토큰       → 경계. 단 인용·전달 연속(EF 다·냐·자·라·래 + 인용 조사 JKQ 또는 하·그러·그렇 용언)은 경계 아님.
                                        EF 바로 뒤가 '요'(JX·MM·IC)면 '요' 뒤를 경계로.
 B3 연결어미 EC 또는 접속조사 JC + '요'(JX·MM·IC) + 뒤에 내용 토큰 → '요' 뒤 경계('나고요 열도 나요'·'어지러워서요 누워 있었어요').
 연결어미 EC 단독('-고'·'-는데'·'-서')은 문장 경계가 아님(절 경계는 STEP29 clause_segmenter 가 문장 안에서 처리).
 kiwi split_into_sents 결과는 비교 기록(kiwi_agrees)만 하고 경계 결정에 쓰지 않는다.
 body_start = 문장 앞 감탄사(IC: 음·어)·접속부사(MAJ: 그리고·근데·그래서)를 건너뛴 분석 시작 위치(문장 구간 start 는 그대로, 채움말은 lead_filler 로 보존).
오프셋 = 원문 code point(kiwi 토큰 start/len). 문장 text 는 항상 text[start:end]."""
from __future__ import annotations

import s292_common  # noqa: F401  (경로)
from extract_symptom_spans import kiwi

PUNCT = {"SF", "SP", "SS", "SE", "SO", "SW", "SH"}
QUOTE_EF = {"다", "냐", "자", "라", "래", "니"}
QUOTE_NEXT = {"하", "그러", "그렇", "말하"}
YO_TAGS = {"JX", "MM", "IC"}
LEAD_TAGS = {"IC", "MAJ"}   # 문장 앞 감탄사(음·어)·접속부사(그리고·근데·그래서) — 분석 구간(body_start)에서 제외


def _boundaries(toks) -> list[tuple[int, str]]:
    """경계가 되는 토큰 index(그 토큰까지가 한 문장)와 근거."""
    out = []
    n = len(toks)
    content = lambda i: i < n and toks[i].tag not in PUNCT  # noqa: E731
    for i, t in enumerate(toks):
        if t.tag == "SF":
            out.append((i, "SF"))
            continue
        nxt = toks[i + 1] if i + 1 < n else None
        if t.tag == "EF" and nxt is not None and content(i + 1):
            if nxt.form == "요" and nxt.tag in YO_TAGS:
                continue   # '요' 뒤에서 판단
            if t.form in QUOTE_EF and (nxt.tag == "JKQ" or (nxt.form in QUOTE_NEXT and nxt.tag.startswith(("VV", "VA")))):
                continue
            out.append((i, "EF"))
        elif t.form == "요" and t.tag in YO_TAGS and i > 0 and toks[i - 1].tag in ("EC", "JC", "EF") and content(i + 1):
            out.append((i, "EC+요" if toks[i - 1].tag != "EF" else "EF+요"))
    return out


def sentences(text: str) -> list[dict]:
    toks = kiwi().tokenize(text or "")
    bnd = _boundaries(toks)
    cuts = [b for b, _ in bnd]
    basis = {b: r for b, r in bnd}
    groups, start = [], 0
    for b in cuts:
        groups.append((toks[start:b + 1], basis[b]))
        start = b + 1
    if start < len(toks):
        groups.append((toks[start:], "END"))
    out = []
    for g, why in groups:
        body = [t for t in g if t.tag not in PUNCT or (t.tag == "SF" and t.form == "?")]
        if not [t for t in body if t.tag not in PUNCT]:
            continue
        s = min(t.start for t in body)
        e = max(t.start + t.len for t in body)
        lead = [t for t in body if t.tag not in PUNCT]
        k = 0
        while k < len(lead) - 1 and lead[k].tag in LEAD_TAGS:
            k += 1
        bs = lead[k].start if k else s
        out.append({"start": s, "end": e, "text": text[s:e], "basis": why, "body_start": bs, "lead_filler": text[s:bs].strip()})
    try:
        ks = {(x.start, x.end) for x in kiwi().split_into_sents(text or "")}
        kstarts = {a for a, _ in ks}
        for o in out:
            o["kiwi_agrees"] = o["start"] in kstarts or o["start"] == 0
    except Exception:  # noqa: BLE001  비교 기록만 — 경계 결정에 영향 없음
        for o in out:
            o["kiwi_agrees"] = None
    return out


def spans(text: str) -> list[tuple[int, int]]:
    return [(o["start"], o["end"]) for o in sentences(text)]


if __name__ == "__main__":
    import sys
    for t in sys.argv[1:]:
        print(t, [(o["text"], o["basis"], o["kiwi_agrees"]) for o in sentences(t)])
