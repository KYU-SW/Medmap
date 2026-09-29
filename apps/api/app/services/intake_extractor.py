from dataclasses import dataclass
import re

from app.schemas.intake import IntakeExtractionResponse, SymptomObservation


@dataclass(frozen=True)
class SymptomRule:
    name: str
    mention: re.Pattern[str]
    absent: re.Pattern[str]
    body_site: str | None = None


RULES = (
    SymptomRule(
        "두통",
        re.compile(
            r"두통|머리(?:가|는|도)?\s*(?:(?:매우|너무|조금|약간|심하게)\s*)?(?:아프|지끈|욱신)"
        ),
        re.compile(r"두통(?:은|이|도)?\s*(?:없|아니)|머리(?:가|는|도)?\s*(?:안\s*아프|아프지\s*않)"),
        "머리",
    ),
    SymptomRule(
        "발열",
        re.compile(r"발열|열(?:이|은|도|이s*나)?"),
        re.compile(r"(?:발열|열)(?:은|이|도)?\s*(?:없|안\s*나|나지\s*않)"),
    ),
    SymptomRule(
        "기침",
        re.compile(r"기침"),
        re.compile(r"기침(?:은|이|도)?\s*(?:없|안\s*나|나지\s*않)"),
    ),
    SymptomRule(
        "호흡곤란",
        re.compile(r"숨(?:쉬기가|을\s*쉬기가)?\s*(?:차|힘들|어렵)|호흡곤란"),
        re.compile(r"숨(?:은|이)?\s*(?:안\s*차|차지\s*않)|호흡곤란(?:은|이)?\s*없"),
    ),
    SymptomRule(
        "가슴 답답함",
        re.compile(r"가슴(?:이|은)?\s*답답"),
        re.compile(r"가슴(?:이|은)?\s*(?:안\s*답답|답답하지\s*않)"),
        "가슴",
    ),
    SymptomRule(
        "복통",
        re.compile(r"(?:배|복부)(?:가|는|도)?\s*아프|복통"),
        re.compile(r"(?:배|복부)(?:가|는|도)?\s*(?:안\s*아프|아프지\s*않)|복통(?:은|이)?\s*없"),
        "복부",
    ),
    SymptomRule(
        "구토",
        re.compile(r"구토|토(?:를|가)?\s*(?:했|해|하)"),
        re.compile(r"구토(?:는|가|도)?\s*없|토(?:는|를)?\s*(?:안\s*했|하지\s*않)"),
    ),
)

ONSET_PATTERN = re.compile(
    r"(?:오늘|어제|그제|방금|아침|점심|저녁|밤|새벽)(?:부터)?|"
    r"\d+\s*(?:시간|일|주|개월|달)\s*(?:전부터|전|동안|째)"
)
SEVERITY_PATTERN = re.compile(r"매우\s*심(?:해|하)|너무\s*심(?:해|하)|심(?:해|하)|조금|약간")
MEDICATION_PATTERN = re.compile(
    r"([가-힣A-Za-z0-9-]{2,20}(?:약|제))(?:을|를|도|은|는)?\s*(?:먹|복용)"
)
ALLERGY_PATTERN = re.compile(
    r"([가-힣A-Za-z0-9-]{2,20})\s*알레르기(?!약)"
)


def _severity(text: str) -> str | None:
    match = SEVERITY_PATTERN.search(text)
    if not match:
        return None
    value = match.group(0)
    return "심함" if "심" in value or "너무" in value else "경미함"


def _nearest_value(
    pattern: re.Pattern[str], text: str, start: int, end: int, max_gap: int = 24
) -> str | None:
    candidates: list[tuple[int, str]] = []
    for match in pattern.finditer(text):
        if match.end() <= start:
            gap = start - match.end()
        elif match.start() >= end:
            gap = match.start() - end
        else:
            gap = 0
        if gap <= max_gap:
            candidates.append((gap, match.group(0)))
    return min(candidates, default=(0, None), key=lambda item: item[0])[1]


def _onset_for_symptom(text: str, start: int, end: int) -> str | None:
    preceding = [
        match for match in ONSET_PATTERN.finditer(text)
        if match.end() <= start and start - match.end() <= 24
    ]
    if preceding:
        return preceding[-1].group(0)

    following = [
        match for match in ONSET_PATTERN.finditer(text)
        if match.start() >= end and match.start() - end <= 12
    ]
    return following[0].group(0) if following else None


def extract_intake(text: str) -> IntakeExtractionResponse:
    normalized = " ".join(text.strip().split())
    symptoms: list[SymptomObservation] = []
    for rule in RULES:
        mention = rule.mention.search(normalized)
        absent = rule.absent.search(normalized)
        if not mention and not absent:
            continue
        evidence = absent or mention
        assert evidence is not None
        onset = _onset_for_symptom(normalized, evidence.start(), evidence.end())
        severity_text = _nearest_value(
            SEVERITY_PATTERN, normalized, evidence.start(), evidence.end(), max_gap=12
        )
        severity = _severity(severity_text or "")
        symptoms.append(
            SymptomObservation(
                name=rule.name,
                status="absent" if absent else "present",
                body_site=rule.body_site,
                onset=onset if not absent else None,
                severity=severity if not absent else None,
                source_text=evidence.group(0),
            )
        )

    medications = list(dict.fromkeys(MEDICATION_PATTERN.findall(normalized)))
    allergies = list(dict.fromkeys(ALLERGY_PATTERN.findall(normalized)))
    return IntakeExtractionResponse(
        symptoms=symptoms,
        medications=medications,
        allergies=allergies,
    )
