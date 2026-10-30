"""STEP29 증상 주체. 규칙(사전 고정, 절 단위):
 타인 = 가족·지인 명사(엄마·아빠·어머니·아버지·아이·애·남편·아내·딸·아들·친구·동생·언니·오빠·형·누나·할머니·할아버지·부모(님)·가족·식구·아기·남동생·여동생·동료 …)
 환자 = 1인칭 대명사 NP(저·제·나·내)
 MULTIPLE = 가족·식구 + 들/모두/다/전부 · 우리 가족 · 같은 절에 1인칭과 타인이 함께
 같은 문장 안에서 표지 없는 절은 앞 절의 명시 주체를 이어받음(INHERITED) · 문장이 바뀌면 이어받지 않음
 표지 없음 → PATIENT(basis ASSUMED_INTAKE_DEFAULT: 환자 문진 입력 전제 — 불확실성 표시)."""
from __future__ import annotations

KIN = {"엄마", "아빠", "어머니", "아버지", "아이", "애", "남편", "아내", "와이프", "딸", "아들", "친구", "동생", "언니", "오빠", "형", "누나", "할머니", "할아버지",
       "부모", "부모님", "가족", "식구", "아기", "남동생", "여동생", "동료", "어머님", "아버님", "시어머니", "장모님", "손자", "손녀", "삼촌", "이모", "고모"}
SELF = {"저", "제", "나", "내"}


def explicit(toks) -> tuple[str | None, str]:
    forms = [t.form for t in toks]
    kin = [t.form for t in toks if t.tag.startswith("NN") and t.form in KIN]
    me = [t.form for t in toks if t.tag == "NP" and t.form in SELF]
    multi = any(f in ("가족", "식구") for f in kin) and any(f in ("들", "모두", "다", "전부") for f in forms)
    if multi or (kin and me) or ("우리" in forms and any(f in ("가족", "식구") for f in kin)):
        return "MULTIPLE", "EXPLICIT:" + "+".join(kin + me)
    if kin:
        return "OTHER_PERSON", "EXPLICIT:" + kin[0]
    if me:
        return "PATIENT", "EXPLICIT:" + me[0]
    return None, ""
