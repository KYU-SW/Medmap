"""문장·절 분리와 언급 상태 판정(규칙). 판단은 하지 않는다. 언급 상태를 구분할 뿐이다."""
from __future__ import annotations

import re
from dataclasses import dataclass

PRESENT, NEGATED, UNCERTAIN = "PRESENT", "NEGATED", "UNCERTAIN"
HISTORICAL, OTHER_PERSON, PURPOSE = "HISTORICAL", "OTHER_PERSON", "PURPOSE_OR_DIFFERENTIAL"
ORDERED, PENDING, CONDITIONAL = "ORDERED_NOT_RESULTED", "RESULT_PENDING", "CONDITIONAL"
PURPOSE_SECTIONS = {"indication", "reason for exam", "reason for study", "clinical indication", "clinical information", "clinical question", "reason"}
HISTORY_SECTIONS = {"history", "past medical history", "pmh", "family history"}
_SEC = re.compile(r"^\s*([A-Za-z][A-Za-z /]{2,30}):\s*(.*)$")
_CLAUSE = re.compile(r";|\bbut\b|\bhowever\b|\balthough\b|\bexcept\b|\bwhile\b", re.I)
_ABBR = re.compile(r"\b(e\.g|i\.e|dr|vs|fig|no)\.$", re.I)

R_OTHER = re.compile(r"\b(mother|father|sister|brother|sibling|son|daughter|family history|family member|relative|aunt|uncle|grandmother|grandfather|wife|husband|roommate)\b", re.I)
R_COND = re.compile(r"\b(if|unless|should .* develop|in case of|would suggest)\b", re.I)
R_PURPOSE = re.compile(r"\b(rule out|r/o|to exclude|evaluate for|evaluation for|evaluation of|assess for|concern for|concerning for|screen for|workup for|work-up for|investigate for|to investigate|to confirm|differential (?:diagnosis )?(?:includes?|of)|ddx|to look for)\b", re.I)
R_ORDER = re.compile(r"\b(ordered|was requested|were requested|requested|will obtain|will order|planned|scheduled|to be performed|recommend(?:ed)?|(?:decision (?:was made )?to|decided to)\s+(?:proceed with|perform|obtain|order|get)|to proceed with)\b", re.I)
R_PEND = re.compile(r"\b(pending|awaiting|awaited|not yet (?:available|resulted|reported)|in progress)\b", re.I)
R_HIST = re.compile(r"\b(history of|hx of|h/o|prior|previous|previously|past|former|known chronic|chronic|resolved|old|remote|years? ago|months? ago)\b", re.I)
R_UNC = re.compile(r"\b(preliminar\w*|risk (?:for|of)|score[sd]?|criteria|possible|possibly|probable|probably|suspected|suspicious|suspect|may represent|might|could|likely|unlikely|cannot be excluded|cannot be ruled out|can't be excluded|cannot exclude|not (?:be )?excluded|not (?:be )?ruled out|equivocal|indeterminate|questionable|presumed|presumptive|limited|suboptimal|motion artifact|nondiagnostic|non-diagnostic|ruling out|mimicking|mimic|masquerading|misdiagnosed|mistaken)\b", re.I)
R_NEG_PRE = re.compile(r"\b(no|not|without|denies|denied|negative for|absence of|free of|free from|excluded|ruled out|no evidence of|no signs? of)\b", re.I)
_ADV = r"(?:(?:again|also|then|later|subsequently|therefore|thus|finally|definitively|effectively|eventually|successfully)\s+){0,2}"
R_NEG_POST = re.compile(r"\b(was|were|is|are|has been|had been|have been)?\s*" + _ADV + r"(not (?:seen|identified|found|detected|present|shown|demonstrated|observed)|absent|excluded|ruled out|negative|resolved)\b", re.I)
R_NEG_POST_TEST = re.compile(r"^\s*\)?\s*(?:\([^)]*\)\s*)?(?:scans?|stud(?:y|ies)|tests?|ultrasound|ultrasonography|doppler|duplex|imaging|work-?up|screen(?:ing)?)\s+(?:was|were|is|are|came back|returned)\s+(?:\w+\s+)?(?:negative|normal|unremarkable)\b", re.I)   # P1: 'DVT scan was negative' 의 부정 대상은 검사 소견
R_PRIOR_EXCLUSION = re.compile(r"\b(?:previously|earlier|initially|formerly)\s+(?:been\s+)?(?:excluded|ruled out)\b|\b(?:excluded|ruled out)\s+(?:\w+\s+){0,3}?(?:previously|earlier|initially|before)\b", re.I)   # P1: 과거 시점의 배제. 현재 음성·과거력 어느 쪽도 아님
R_RESULT_AFTER_ORDER = re.compile(r"(?<!to )\b(?:returned|came back|resulted|showed|revealed|demonstrated|ruled out|excluded|confirmed)\b", re.I)   # P1: 주문 뒤 같은 절의 결과 표현
R_NEG_SCOPE_END = re.compile(r"\b(?:confirmed|diagnos\w+|proven|documented|established)\b", re.I)   # P1: 언급이 속한 접속 항 안의 긍정 술어
R_BREAK = re.compile(r"\b(but|however|although|with|and evidence|shows?|showed|demonstrates?|revealed?|reveals)\b", re.I)


@dataclass(frozen=True)
class Clause:
    text: str
    sentence: str
    section: str
    sentence_index: int


def split_clauses(text: str) -> list:
    out = []
    section = ""
    n = 0
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        m = _SEC.match(line)
        if m and m.group(1).lower().strip() in PURPOSE_SECTIONS | HISTORY_SECTIONS | {"findings", "impression", "conclusion", "comparison", "technique", "result", "results", "exam", "examination", "report"}:
            section, line = m.group(1).lower().strip(), m.group(2).strip()
            if not line:
                continue
        pieces, buf = [], ""
        for part in re.split(r"(?<=[.!?])\s+", line):
            buf = f"{buf} {part}".strip()
            if not _ABBR.search(buf):
                pieces.append(buf)
                buf = ""
        if buf:
            pieces.append(buf)
        for s in pieces:
            n += 1
            start = 0
            for m2 in _CLAUSE.finditer(s):
                c = s[start:m2.start()].strip(" ,")
                if c:
                    out.append(Clause(c, s, section, n))
                start = m2.start()
            c = s[start:].strip(" ,")
            if c:
                out.append(Clause(c, s, section, n))
    return out


def _neg_scope(scope: str) -> str:
    """P1: 부정 신호와 언급 사이가 쉼표·접속사로 나뉘면 범위를 확인한다. 'NEGATED'·'ENDED'·'UNCLEAR'.
    '... 없음, 그리고 확진된 X' 처럼 언급의 접속 항에 긍정 술어가 있으면 범위 종료. 'A, B, or X' 나열은 부정 유지. 그 외 긴 항은 불명확."""
    seps = list(re.finditer(r",|\b(?:and|or|nor)\b", scope, re.I))
    if not seps:
        return "NEGATED"
    conj = [x for x in re.split(r",|\b(?:and|or|nor)\b", scope, flags=re.I) if x.strip()]
    if not conj:
        return "NEGATED"
    if any(m.group(0).lower() in ("or", "nor") for m in seps):
        return "NEGATED"
    if R_NEG_SCOPE_END.search(conj[-1]):
        return "ENDED"
    return "NEGATED" if all(len(x.split()) <= 4 for x in conj) else "UNCLEAR"


def classify_assertion(c: Clause, start: int, end: int) -> tuple:
    """(상태, 근거 신호). 우선순위: 타인 > 조건 > 검사 목적 > 주문·대기 > 과거 > 불확실 > 부정 > 있음."""
    t = c.text
    before, after = t[:start], t[end:]
    if c.section == "family history" or R_OTHER.search(t):
        return OTHER_PERSON, "OTHER_PERSON_CUE"
    if R_COND.search(before):
        return CONDITIONAL, "CONDITIONAL_CUE"
    if R_UNC.search(t) and re.search(r"\b(cannot|can't|not)\b[^.]{0,20}\b(exclud|rul)", t, re.I):
        return UNCERTAIN, "CANNOT_EXCLUDE"
    if c.section in PURPOSE_SECTIONS or R_PURPOSE.search(before):
        return PURPOSE, "PURPOSE_SECTION" if c.section in PURPOSE_SECTIONS else "PURPOSE_CUE"
    if R_PEND.search(t):
        return PENDING, "PENDING_CUE"
    m_order = R_ORDER.search(t)
    if m_order and not R_RESULT_AFTER_ORDER.search(t[m_order.end():]):
        return ORDERED, "ORDER_CUE"
    if R_PRIOR_EXCLUSION.search(t):
        return UNCERTAIN, "PRIOR_EXCLUSION_TIME_UNCLEAR"
    if re.search(r"\b(ruled out|excluded|no evidence of|negative for)\s+(?:\w+\s+){0,1}$", before, re.I):
        return NEGATED, "NEG_ADJACENT"
    if c.section in HISTORY_SECTIONS or R_HIST.search(before) or re.match(r"\s*(?:was )?(?:resolved|in the past)\b", after, re.I):
        return HISTORICAL, "HISTORY_CUE"
    if R_UNC.search(t):
        return UNCERTAIN, "UNCERTAIN_CUE"
    negs = list(R_NEG_PRE.finditer(before))
    if negs and not R_BREAK.search(before[negs[-1].end():]):
        scope = _neg_scope(before[negs[-1].end():])
        if scope == "NEGATED":
            return NEGATED, "NEG_PRE:" + negs[-1].group(0).lower()
        if scope == "UNCLEAR":
            return UNCERTAIN, "NEG_SCOPE_UNCLEAR"
        return PRESENT, "NEG_SCOPE_ENDED"
    if re.match(r"^[\s,:]*" + R_NEG_POST.pattern, after, re.I):
        return NEGATED, "NEG_POST"
    if R_NEG_POST_TEST.match(after):
        return NEGATED, "NEG_POST_TEST_RESULT"
    return PRESENT, "NO_MODIFIER"
