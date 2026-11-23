"""임상 단계 판정(Safety Patch P1). 진단 관계의 적용 범위 확인에만 쓴다.
검사 수치는 읽지 않는다. 문장의 명시 표현·입력 맥락·가설 상태·같은 사례의 이미 공개된 문서만 본다.
정해지지 않으면 UNKNOWN_CONTEXT. 확률을 만들지 않는다."""
from __future__ import annotations

import re

SUSPECTED = "SUSPECTED_ACUTE_PE_EVALUATION"
CONFIRMED = "CONFIRMED_PE"
UNDER_TREATMENT = "UNDER_TREATMENT"
POST_TREATMENT = "POST_TREATMENT_FOLLOWUP"
RECURRENCE = "RECURRENCE_EVALUATION"
UNKNOWN = "UNKNOWN_CONTEXT"
PHASES = {SUSPECTED, CONFIRMED, UNDER_TREATMENT, POST_TREATMENT, RECURRENCE, UNKNOWN}
NON_DIAGNOSTIC_ORDER = (RECURRENCE, POST_TREATMENT, UNDER_TREATMENT, CONFIRMED)   # 여러 신호가 있을 때 우선순위

_PE = r"(?:(?i:pulmonary (?:thrombo)?embol\w*|pulmonary artery embolism|venous thromboembolism)|\bPE\b|\bVTE\b)"   # 약어만 대소문자 구분
R_PE = re.compile(_PE)
_TX = r"(?:anti-?coagul\w*|DOACs?|NOACs?|apixaban|rivaroxaban|dabigatran|edoxaban|warfarin|heparin|LMWH|enoxaparin|fondaparinux|thromboly\w+|alteplase)"
R_TX = re.compile(_TX, re.I)
R_TX_NOT_GIVEN_BEFORE = re.compile(r"\b(?:no|not|without|off|never|before|prior to|pending|withheld|held|avoid\w*|contraindicat\w*|consider\w*|if|unless)\b[^.;,]{0,30}$", re.I)
R_TX_NOT_GIVEN_AFTER = re.compile(r"^[^.;,]{0,25}\b(?:contraindicated|was held|withheld|planned|recommended|was not|were not|not started|not given)\b", re.I)
R_FOLLOWUP = re.compile(r"\bfollow(?:ed)?[- ]?up\b", re.I)
R_POST_TX = re.compile(r"\bpost-?treatment\b|\b(?:after|following)\s+(?:the\s+)?(?:completing|completion of|stopping|discontinu\w+(?: of)?|cessation of)\s+(?:\w+\s+){0,2}(?:anti-?coagul\w*|treatment|therapy)\b", re.I)
R_RECUR = re.compile(r"\brecurr\w*\b", re.I)
R_RECUR_ABSENT = re.compile(r"\b(?:no|not|without|free of|absence of)\b[^.;,]{0,25}\brecurr\w*\b", re.I)
R_CONFIRM_BEFORE = re.compile(r"\b(?:diagnos\w+ (?:of|with)|confirmed|established|proven|known)\b[^.;,]{0,40}" + _PE)
R_CONFIRM_AFTER = re.compile(_PE + r"[^.;,]{0,20}\b(?:was|were|is|had been|has been)\s+(?:\w+\s+)?(?:confirmed|diagnosed)\b")
R_NOT_CONFIRMED = re.compile(r"\b(?:to confirm|not confirmed|unconfirmed|no|not|without|suspect\w*|possible|probable|presumed|rule out|ruled out|exclud\w*)\b[^.;,]{0,30}$", re.I)
R_POC = re.compile(r"\b(?:point[- ]of[- ]care|bedside|on-the-spot)\b[^.;,]{0,25}\bd-?\s?dimers?\b|\bd-?\s?dimers?\b[^.;,]{0,25}\b(?:point[- ]of[- ]care|bedside|on-the-spot)\b", re.I)   # D-dimer 검사법을 가리킬 때만


def _tx_given(s: str) -> bool:
    return any(not R_TX_NOT_GIVEN_BEFORE.search(s[:m.start()]) and not R_TX_NOT_GIVEN_AFTER.search(s[m.end():]) for m in R_TX.finditer(s))


def _confirmed(s: str) -> bool:
    for pat in (R_CONFIRM_BEFORE, R_CONFIRM_AFTER):
        for m in pat.finditer(s):
            if not R_NOT_CONFIRMED.search(s[:m.start()]):
                return True
    return False


def sentence_signals(s: str) -> dict:
    """문장의 명시 표현에서 단계 신호. phase=None 이면 문장만으로 단계를 정하지 않는다.
    inconclusive=True 는 '의심 평가'로 단정할 수 없는 치료·추적 표현이 있다는 뜻."""
    pe, tx, fu = bool(R_PE.search(s)), _tx_given(s), bool(R_FOLLOWUP.search(s))
    recur = bool(pe and R_RECUR.search(s) and not R_RECUR_ABSENT.search(s))
    post, conf = bool(R_POST_TX.search(s)), _confirmed(s)
    signals = [k for k, v in (("RECURRENCE", recur), ("POST_TREATMENT", post), ("TREATMENT", tx), ("FOLLOWUP", fu), ("PE_MENTION", pe), ("CONFIRMED", conf)) if v]
    phase = None
    if recur:
        phase = RECURRENCE
    elif post:
        phase = POST_TREATMENT
    elif tx and (fu or pe):
        phase = UNDER_TREATMENT
    elif fu and pe:
        phase = POST_TREATMENT
    elif conf:
        phase = CONFIRMED
    return {"phase": phase, "signals": signals, "inconclusive": phase is None and (tx or fu)}


def resolve(sentence: str, hypothesis_status: str, ctx: dict) -> dict:
    """우선순위: 문장 명시 > 입력 비의심 단계 > 가설 확진 상태 > 공개된 사례 문서 신호 > 불명확 표현 > 입력 의심."""
    sig = sentence_signals(sentence)
    given = ctx.get("clinical_phase")
    if given is not None and given not in PHASES:
        raise ValueError(f"알 수 없는 clinical_phase: {given}")
    suspected_input = given == SUSPECTED or (given is None and ctx.get("suspected") is True)
    case = [p for p in NON_DIAGNOSTIC_ORDER if p in (ctx.get("case_phase_signals") or ())]
    if sig["phase"]:
        phase, basis = sig["phase"], "SENTENCE_TEXT"
    elif given in (RECURRENCE, POST_TREATMENT, UNDER_TREATMENT, CONFIRMED):
        phase, basis = given, "INPUT_CONTEXT"
    elif hypothesis_status == "CONFIRMED_DIAGNOSIS":
        phase, basis = CONFIRMED, "HYPOTHESIS_STATUS"
    elif case:
        phase, basis = case[0], "PRIOR_VISIBLE_DOCUMENT"
    elif sig["inconclusive"]:
        phase, basis = UNKNOWN, "TREATMENT_OR_FOLLOWUP_TEXT_UNRESOLVED"
    elif suspected_input:
        phase, basis = SUSPECTED, "INPUT_CONTEXT"
    else:
        phase, basis = UNKNOWN, "NOT_STATED"
    return {"phase": phase, "basis": basis, "signals": sig["signals"], "context_conflict": suspected_input and phase != SUSPECTED,
            "assay": "POINT_OF_CARE" if R_POC.search(sentence) else None}
