"""STEP29 부정·확신(assertion) — 단위의 술어 토큰 범위에만 적용(문장 전체 아님). 규칙(사전 고정):
 부정 표지 = 없(VA)·않(VX)·안(MAG)·못(MAG)·못하(VX)·아니(VCN). 관용 '안 좋다'(안 + 좋) 의 '안' 은 부정 아님(불편 호소 = PRESENT).
 이중 부정(표지 ≥2 이고 마지막이 '아니') → POSSIBLE · 추정(현재·과거 관형형 '는/ㄴ/은' + 것 + 같 · 듯 · 모르 · 아마 · 혹시 · 같기도) → POSSIBLE
 ('…ㄹ 것 같다' 는 다가오는 감각 표현 — 추정 아님, 예 '토할 것 같아요' = 오심 PRESENT)
 표지 ≥1 → ABSENT · 없음 → PRESENT. 같은 문장의 뒤 절이 증상 없이 '모르겠' 류면 앞 단위 PRESENT → POSSIBLE(sentence_hedge)."""
from __future__ import annotations

NEG = {("없", "VA"), ("않", "VX"), ("안", "MAG"), ("못", "MAG"), ("못하", "VX"), ("아니", "VCN")}
HEDGE_WORDS = {"듯", "모르", "아마", "혹시"}


def assertion(toks) -> tuple[str, str]:
    forms = [(t.form, t.tag) for t in toks]
    negs = []
    for i, ft in enumerate(forms):
        if ft in NEG:
            if ft == ("안", "MAG") and i + 1 < len(forms) and forms[i + 1][0] == "좋":
                continue
            negs.append(ft[0])
    hedge = any(f in HEDGE_WORDS for f, _ in forms)
    for i in range(1, len(forms) - 1):
        if forms[i][0] in ("것", "거", "건") and forms[i + 1][0] == "같" and forms[i - 1][1] == "ETM" and forms[i - 1][0] in ("는", "ᆫ", "은", "던"):
            hedge = True
    if any(f == "같" for f, _ in forms) and any(f == "기" for f, _ in forms):
        hedge = True
    if len(negs) >= 2 and negs[-1] == "아니":
        return "POSSIBLE", "DOUBLE_NEGATION:" + "+".join(negs)
    if hedge:
        return "POSSIBLE", "HEDGE"
    if negs:
        return "ABSENT", "NEG:" + "+".join(negs)
    return "PRESENT", "NO_NEGATION_MARKER"


def sentence_hedge(clause_text: str) -> bool:
    return any(w in clause_text for w in ("모르겠", "모르겠어", "잘 몰라", "확실하지"))
