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
R_PURPOSE = re.compile(r"\b(rule out|r/o|to exclude|evaluate for|evaluation for|evaluation of|assess for|concern for|concerning for|screen for|workup for|work-up for|investigate for|differential (?:diagnosis )?(?:includes?|of)|ddx|to look for)\b", re.I)
R_ORDER = re.compile(r"\b(ordered|was requested|were requested|requested|will obtain|will order|planned|scheduled|to be performed|recommend(?:ed)?)\b", re.I)
R_PEND = re.compile(r"\b(pending|awaiting|awaited|not yet (?:available|resulted|reported)|in progress)\b", re.I)
R_HIST = re.compile(r"\b(history of|hx of|h/o|prior|previous|previously|past|former|known chronic|chronic|resolved|old|remote|years? ago|months? ago)\b", re.I)
R_UNC = re.compile(r"\b(preliminar\w*|risk (?:for|of)|score[sd]?|criteria|possible|possibly|probable|probably|suspected|suspicious|suspect|may represent|might|could|likely|unlikely|cannot be excluded|cannot be ruled out|can't be excluded|cannot exclude|not (?:be )?excluded|not (?:be )?ruled out|equivocal|indeterminate|questionable|presumed|presumptive|limited|suboptimal|motion artifact|nondiagnostic|non-diagnostic|ruling out|mimicking|mimic|masquerading|misdiagnosed|mistaken)\b", re.I)
R_NEG_PRE = re.compile(r"\b(no|not|without|denies|denied|negative for|absence of|free of|free from|excluded|ruled out|no evidence of|no signs? of)\b", re.I)
R_NEG_POST = re.compile(r"\b(was|were|is|are)?\s*(not (?:seen|identified|found|detected|present|shown|demonstrated|observed)|absent|excluded|ruled out|negative|resolved)\b", re.I)
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
    if R_ORDER.search(t):
        return ORDERED, "ORDER_CUE"
    if re.search(r"\b(ruled out|excluded|no evidence of|negative for)\s+(?:\w+\s+){0,1}$", before, re.I):
        return NEGATED, "NEG_ADJACENT"
    if c.section in HISTORY_SECTIONS or R_HIST.search(before) or re.match(r"\s*(?:was )?(?:resolved|in the past)\b", after, re.I):
        return HISTORICAL, "HISTORY_CUE"
    if R_UNC.search(t):
        return UNCERTAIN, "UNCERTAIN_CUE"
    negs = list(R_NEG_PRE.finditer(before))
    if negs and not R_BREAK.search(before[negs[-1].end():]):
        return NEGATED, "NEG_PRE:" + negs[-1].group(0).lower()
    if re.match(r"^[\s,:]*" + R_NEG_POST.pattern, after, re.I):
        return NEGATED, "NEG_POST"
    return PRESENT, "NO_MODIFIER"
