from dataclasses import dataclass
import re

from app.schemas.intake import IntakeExtractionResponse, SymptomObservation


@dataclass(frozen=True)
class SymptomRule:
    name: str
    mention: re.Pattern[str]
    absent: re.Pattern[str]
    body_site: str | None = None


INTENSITY_WORD = r"(?:아주|매우|너무|많이|조금|약간|심하게)"
INTENSITY_PHRASE = rf"(?:{INTENSITY_WORD}\s*)*"
IMPROVEMENT_PHRASE = (
    r"(?:(?:조금|좀|많이|전보다)\s*)?"
    r"(?:괜찮아졌|나아졌|호전됐|좋아졌|덜해졌|줄었)"
)
RESOLVED_STATE = (
    r"(?:(?:완전히\s*)?(?:사라졌|없어졌|멈췄|가라앉았)|"
    r"(?:다|완전히)\s*(?:나았|괜찮아졌|좋아졌))"
)
INLINE_ONSET = (
    r"(?<![가-힣A-Za-z0-9])(?:어젯밤(?:부터)?|"
    r"(?:오늘|어제|그제|그저께|엊그제)\s*"
    r"(?:아침|점심|저녁|밤|새벽)(?:부터)?|"
    r"(?:오늘|어제|그제|그저께|엊그제)(?:부터)?|"
    r"(?:하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘)"
    r"(?:\s*(?:전부터|전|동안|째))?|"
    r"(?:\d+|일|이|삼|사|오|육|칠|팔|구|십)\s*"
    r"(?:시간|일|주|개월|달)(?:\s*(?:전부터|전|동안|째))?)"
)


RULES = (
    SymptomRule(
        "두통",
        re.compile(
            rf"머리(?:랑|와|하고)\s*(?:배|복부|속)(?:가|는|도)?\s*"
            rf"(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}(?:아프|아파|아팠|아픈)|"
            rf"두통|머리(?:가|는|도)?\s*(?:{INLINE_ONSET}\s*)?"
            rf"(?:같이\s*|함께\s*)?{INTENSITY_PHRASE}"
            rf"(?:아프|아파|아팠|아픈|지끈|욱신)|"
            rf"(?:두통|머리)(?:이|가|은|는|도)?\s*{IMPROVEMENT_PHRASE}"
        ),
        re.compile(
            rf"두통(?:은|이|도)?\s*(?:없|아니)|"
            rf"머리(?:가|는|도)?\s*(?:(?:더\s*이상\s*)?안\s*(?:아프|아파|아픈)|아프지\s*않)|"
            rf"(?:두통|머리\s*통증)(?:은|이|가|는|도)?\s*{RESOLVED_STATE}"
        ),
        "머리",
    ),
    SymptomRule(
        "발열",
        re.compile(r"고열|발열|열(?:이|은|도)?\s*(?:나|났|오르|있)?"),
        re.compile(
            rf"(?:고열|발열|열)(?:은|이|도)?\s*(?:없|안\s*나|나지\s*않|내렸|{RESOLVED_STATE})"
        ),
    ),
    SymptomRule(
        "기침",
        re.compile(r"기침(?:이|을|은|도)?\s*(?:나|났|해|했|하|심하|심했|계속)?"),
        re.compile(
            rf"기침(?:은|이|도)?\s*(?:없|안\s*(?:나|해|하)|나지\s*않|하지\s*않|{RESOLVED_STATE})"
        ),
    ),
    SymptomRule(
        "호흡곤란",
        re.compile(
            rf"숨(?:이|은|도)?\s*(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}차|"
            rf"숨(?:을)?\s*쉬기(?:가)?\s*(?:힘들|어렵|어려|{IMPROVEMENT_PHRASE})|"
            r"숨쉬기가\s*(?:전보다\s*)?편해졌|"
            rf"호흡곤란(?:이|은|도)?\s*(?:{IMPROVEMENT_PHRASE})?|"
            rf"숨찬\s*증상(?:이|은|도)?\s*{IMPROVEMENT_PHRASE}"
        ),
        re.compile(
            rf"숨(?:은|이)?\s*(?:안\s*차|차지\s*않)|"
            rf"(?:호흡곤란|숨찬\s*증상)(?:은|이|도)?\s*(?:없|{RESOLVED_STATE})"
        ),
    ),
    SymptomRule(
        "가슴 답답함",
        re.compile(
            rf"가슴(?:이|은|만|도)?\s*(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}"
            r"(?:답답|조이|조여|눌리)|흉부(?:가|는|만|도)?\s*(?:답답|압박)"
        ),
        re.compile(
            rf"가슴(?:이|은)?\s*(?:안\s*답답|답답하지\s*않)|"
            rf"(?:가슴\s*답답함|흉부\s*압박)(?:은|이|도)?\s*{RESOLVED_STATE}"
        ),
        "가슴",
    ),
    SymptomRule(
        "복통",
        re.compile(
            rf"머리(?:랑|와|하고)\s*(?:배|복부|속)(?:가|는|도)?\s*"
            rf"(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}(?:아프|아파|아팠|아픈)|"
            rf"(?:배|복부|속)(?:랑|과|하고)\s*머리(?:가|는|도)?\s*"
            rf"(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}(?:아프|아파|아팠|아픈)|"
            rf"(?:배|복부|속)(?:이|가|는|도)?\s*(?:{INLINE_ONSET}\s*)?"
            rf"{INTENSITY_PHRASE}(?:아프|아파|아팠|아픈)|복통"
        ),
        re.compile(
            rf"(?:배|복부|속)(?:이|가|는|도)?\s*(?:(?:더\s*이상\s*)?안\s*(?:아프|아파|아픈)|아프지\s*않)|"
            rf"복통(?:은|이|도)?\s*(?:없|{RESOLVED_STATE})|"
            rf"(?:배|복부|속)\s*통증(?:은|이|도)?\s*{RESOLVED_STATE}"
        ),
        "복부",
    ),
    SymptomRule(
        "구토",
        re.compile(
            r"구토\s*횟수(?:가|는|도)?[^,.!?。]{0,20}(?:줄었|늘었)|"
            r"구토|토(?:를|가)?\s*(?:했|해|하|했었)"
        ),
        re.compile(
            rf"구토(?:는|가|도)?\s*(?:없|{RESOLVED_STATE})|"
            rf"토(?:는|를)?\s*(?:안\s*했|하지\s*않)|"
            rf"구토\s*증상(?:은|이|도)?\s*{RESOLVED_STATE}"
        ),
    ),
)

ONSET_PATTERN = re.compile(
    r"(?<![가-힣A-Za-z0-9])(?:어젯밤(?:부터)?|"
    r"(?:오늘|어제|그제|그저께|엊그제)\s*"
    r"(?:아침|점심|저녁|밤|새벽)(?:부터)?|"
    r"(?:오늘|어제|그제|그저께|엊그제|방금|아침|점심|저녁|밤|새벽)(?:부터)?|"
    r"(?:하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘)"
    r"(?:\s*(?:전부터|전|동안|째))?|"
    r"(?:일주일|한\s*주|두\s*주|한\s*달|두\s*달)"
    r"(?:\s*(?:전부터|전|동안|째))?|"
    r"(?:\d+|일|이|삼|사|오|육|칠|팔|구|십)\s*"
    r"(?:시간|일|주|개월|달)(?:\s*(?:전부터|전|동안|째))?)"
)
SEVERITY_PATTERN = re.compile(
    r"매우\s*심(?:해|하|했)|너무\s*심(?:해|하|했)|심(?:해|하|했)|"
    r"아주|매우|너무|많이|조금|약간"
)
PAIN_SCORE_PATTERN = re.compile(
    r"(?:(?:고통(?:의\s*정도)?|통증|아픈\s*강도|아픈\s*정도|아픔|강도)(?:를|로|는|가)?\s*"
    r"(?:따지면|점수는?|정도는?)?\s*)?"
    r"(?:한\s*)?"
    r"(?:10\s*점\s*만점(?:에|에서)\s*\d{1,2}\s*점|"
    r"10\s*중(?:에|에서)?\s*\d{1,2}\s*(?:점|정도)?|"
    r"\d{1,3}\s*(?:점|정도))"
)
FREQUENCY_PATTERN = re.compile(
    r"(?:(?:하루(?:에)?|오늘|어제)\s*)?"
    r"(?:\d+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*"
    r"(?:번|회|차례)"
)
TREND_PATTERN = re.compile(
    r"(?P<improving>(?:(?:조금|좀|많이|전보다|점점)\s*)?"
    r"(?:괜찮아졌|나아졌|호전됐|좋아졌|덜해졌|줄었|완화됐|편해졌))|"
    r"(?P<worsening>(?:(?:더|훨씬|점점|많이)\s*)?"
    r"(?:심해졌|악화됐|나빠졌|더\s*아프|잦아졌|늘었))|"
    r"(?P<unchanged>(?:그대로|비슷|여전|변화\s*없))"
)
MEDICATION_PATTERN = re.compile(
    r"([가-힣A-Za-z0-9-]{2,20}\s*(?:약|제))"
    r"(?:을|를|도|은|는)?\s*(?:먹|복용)"
)
MEDICATION_NAME_PATTERN = re.compile(
    r"((?:(?:알레르기|감기|비염|혈압|당뇨|진통|해열|소화|위장)\s*약)|"
    r"(?:[가-힣A-Za-z0-9-]{2,20}(?:약|제)))"
    r"(?=(?:과|와|을|를|도|은|는)?(?:\s|$))"
)
KNOWN_MEDICATION_PATTERN = re.compile(
    r"타이레놀|아세트아미노펜|이부프로펜|애드빌|게보린|판피린"
)
ALLERGY_PATTERN = re.compile(
    r"([가-힣A-Za-z0-9-]{2,20})\s*알레르기(?!\s*약)"
    r"(?:가|는|도)?\s*(?:있|있어|있습니다|예요|입니다|반응)"
)
MEDICAL_SIGNAL_PATTERN = re.compile(
    r"아프|통증|열|기침|숨|호흡|답답|구토|토했|어지|설사|메스꺼|오한|"
    r"콧물|발진|붓|저리|마비|출혈|두근|약|알레르기"
)
CLAUSE_SPLIT_PATTERN = re.compile(r"[.!?。]|(?:\s+)(?:그리고|추가로|하지만|그러나|또한)(?:\s+)")


def _severity(text: str) -> str | None:
    score_match = PAIN_SCORE_PATTERN.search(text)
    if score_match:
        numbers = [int(value) for value in re.findall(r"\d+", score_match.group(0))]
        if ("만점" in score_match.group(0) or "중" in score_match.group(0)) and len(numbers) >= 2:
            maximum, score = numbers[-2], numbers[-1]
            if 0 <= score <= maximum:
                return f"{score}/{maximum}점"
        elif numbers:
            score = numbers[-1]
            if 0 <= score <= 100:
                maximum = 10 if score <= 10 else 100
                return f"{score}/{maximum}점"

    match = SEVERITY_PATTERN.search(text)
    if not match:
        return None
    value = match.group(0)
    return (
        "심함"
        if "심" in value or "너무" in value or "많이" in value or "매우" in value or "아주" in value
        else "경미함"
    )


def _normalize_onset(value: str | None) -> str | None:
    if value is None:
        return None
    native_days = {
        "하루": "1일", "이틀": "2일", "사흘": "3일", "나흘": "4일",
        "닷새": "5일", "엿새": "6일", "이레": "7일", "여드레": "8일",
        "아흐레": "9일", "열흘": "10일",
    }
    native_match = re.fullmatch(
        r"(하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘)"
        r"\s*(전부터|전|동안|째)?",
        value,
    )
    if native_match:
        suffix = native_match.group(2)
        separator = "" if suffix == "째" else " "
        return native_days[native_match.group(1)] + (f"{separator}{suffix}" if suffix else "")

    calendar_words = {
        "일주일": "1주", "한주": "1주", "두주": "2주", "한달": "1달", "두달": "2달"
    }
    calendar_match = re.fullmatch(
        r"(일주일|한\s*주|두\s*주|한\s*달|두\s*달)\s*(전부터|전|동안|째)?",
        value,
    )
    if calendar_match:
        key = re.sub(r"\s+", "", calendar_match.group(1))
        suffix = calendar_match.group(2)
        separator = "" if suffix == "째" else " "
        return calendar_words[key] + (f"{separator}{suffix}" if suffix else "")

    number_words = {
        "일": "1", "이": "2", "삼": "3", "사": "4", "오": "5", "육": "6",
        "칠": "7", "팔": "8", "구": "9", "십": "10",
    }
    match = re.fullmatch(
        r"(\d+|일|이|삼|사|오|육|칠|팔|구|십)\s*"
        r"(시간|일|주|개월|달)\s*(전부터|전|동안|째)?",
        value,
    )
    if not match:
        return value
    number = number_words.get(match.group(1), match.group(1))
    suffix = match.group(3)
    separator = "" if suffix == "째" else " "
    return f"{number}{match.group(2)}" + (f"{separator}{suffix}" if suffix else "")


def _normalize_frequency(value: str) -> str:
    number_words = {
        "한": "1", "두": "2", "세": "3", "네": "4", "다섯": "5",
        "여섯": "6", "일곱": "7", "여덟": "8", "아홉": "9", "열": "10",
    }
    match = re.search(
        r"(\d+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*(?:번|회|차례)",
        value,
    )
    if not match:
        return value
    count = number_words.get(match.group(1), match.group(1))
    period = "하루 " if re.search(r"하루(?:에)?", value) else ""
    return f"{period}{count}회"


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


def _onset_for_symptom(
    text: str, start: int, end: int, previous_end: int, next_start: int
) -> str | None:
    boundary_pattern = re.compile(
        r"[,;.!?。]|(?:추가로|그리고|하지만|그러나|또한)|"
        r"(?:고|며|면서|는데|지만)(?:\s|$)"
    )
    overlapping = [
        match for match in ONSET_PATTERN.finditer(text)
        if match.start() >= start and match.end() <= end
    ]
    if overlapping:
        return overlapping[0].group(0)

    preceding = [
        match for match in ONSET_PATTERN.finditer(text)
        if match.end() <= start
        and match.end() >= previous_end
        and start - match.end() <= 24
        and not boundary_pattern.search(text[match.end():start])
    ]
    if preceding:
        return preceding[-1].group(0)

    following = [
        match for match in ONSET_PATTERN.finditer(text)
        if match.start() >= end
        and match.end() <= next_start
        and match.start() - end <= 24
        and not boundary_pattern.search(text[end:match.start()])
    ]
    if following:
        return following[0].group(0)

    return None


def _severity_for_symptom(
    text: str,
    start: int,
    end: int,
    symptom_positions: list[tuple[int, int]],
) -> str | None:
    def distance(match: re.Match[str], position: tuple[int, int]) -> int:
        position_start, position_end = position
        if match.end() <= position_start:
            return position_start - match.end()
        if match.start() >= position_end:
            return match.start() - position_end
        return 0

    connector_pattern = re.compile(
        r"[,;]|(?:추가로|그리고|하지만|그러나|또한)|"
        r"(?:고|며|면서|는데|지만)(?:\s|,|$)"
    )

    def owner_for(match: re.Match[str]) -> tuple[int, int]:
        overlapping = [
            position for position in symptom_positions
            if match.start() < position[1] and match.end() > position[0]
        ]
        if overlapping:
            return overlapping[0]

        preceding = [position for position in symptom_positions if position[1] <= match.start()]
        following = [position for position in symptom_positions if position[0] >= match.end()]
        previous = preceding[-1] if preceding else None
        next_position = following[0] if following else None
        if previous and next_position:
            left_text = text[previous[1]:match.start()]
            right_text = text[match.end():next_position[0]]
            if connector_pattern.search(right_text):
                return previous
            if connector_pattern.search(left_text):
                return next_position
        available = [position for position in (previous, next_position) if position]
        return min(available, key=lambda position: (distance(match, position), position[0]))

    candidates: list[re.Match[str]] = []
    for match in (
        match
        for pattern in (SEVERITY_PATTERN, PAIN_SCORE_PATTERN)
        for match in pattern.finditer(text)
    ):
        if match.re is SEVERITY_PATTERN and re.match(
            r"\s*(?:괜찮아졌|나아졌|호전됐|좋아졌|덜해졌|줄었|완화됐|편해졌)",
            text[match.end():],
        ):
            continue
        owner = owner_for(match)
        owner_overlaps_current = owner[0] < end and owner[1] > start
        if owner != (start, end) and not owner_overlaps_current:
            continue
        between = (
            text[match.end():start]
            if match.end() <= start
            else text[end:match.start()]
            if match.start() >= end
            else ""
        )
        if re.search(r"[.!?。]", between):
            continue
        candidates.append(match)
    if not candidates:
        return None
    latest = max(candidates, key=lambda match: match.start())
    return _severity(latest.group(0))


def _frequency_for_symptom(
    text: str,
    start: int,
    end: int,
    symptom_positions: list[tuple[int, int]],
) -> str | None:
    candidates: list[tuple[int, re.Match[str]]] = []
    for match in FREQUENCY_PATTERN.finditer(text):
        distances = []
        for position in symptom_positions:
            if match.end() <= position[0]:
                distance = position[0] - match.end()
            elif match.start() >= position[1]:
                distance = match.start() - position[1]
            else:
                distance = 0
            distances.append((distance, position))
        if not distances:
            continue
        distance, owner = min(distances, key=lambda item: (item[0], item[1][0]))
        if owner != (start, end) or distance > 24:
            continue
        between = (
            text[match.end():start]
            if match.end() <= start
            else text[end:match.start()]
            if match.start() >= end
            else ""
        )
        if re.search(r"[.!?。]|(?:그리고|하지만|그러나|추가로)", between):
            continue
        candidates.append((distance, match))
    if not candidates:
        return None
    return _normalize_frequency(min(candidates, key=lambda item: item[0])[1].group(0))


def _trend_for_symptom(
    text: str,
    start: int,
    end: int,
    symptom_positions: list[tuple[int, int]],
) -> str | None:
    candidates: list[tuple[int, re.Match[str]]] = []
    for match in TREND_PATTERN.finditer(text):
        distances: list[tuple[int, tuple[int, int]]] = []
        for position in symptom_positions:
            if match.end() <= position[0]:
                distance = position[0] - match.end()
            elif match.start() >= position[1]:
                distance = match.start() - position[1]
            else:
                distance = 0
            distances.append((distance, position))
        if not distances:
            continue
        distance, owner = min(distances, key=lambda item: (item[0], item[1][0]))
        if owner != (start, end) or distance > 32:
            continue
        between = (
            text[match.end():start]
            if match.end() <= start
            else text[end:match.start()]
            if match.start() >= end
            else ""
        )
        if re.search(r"[.!?。]|(?:그리고|하지만|그러나|추가로)", between):
            continue
        candidates.append((distance, match))
    if not candidates:
        return None
    match = min(candidates, key=lambda item: item[0])[1]
    if match.group("improving"):
        return "improving"
    if match.group("worsening"):
        return "worsening"
    return "unchanged"


def _extract_medications(text: str) -> list[str]:
    medications: list[str] = []
    clause_boundaries = re.compile(r"[.!?。]|(?:\s+)(?:그리고|하지만|그러나|또한)(?:\s+)")
    for clause in clause_boundaries.split(text):
        if not re.search(r"먹|복용", clause):
            continue
        for value in MEDICATION_NAME_PATTERN.findall(clause):
            normalized = re.sub(r"\s+", "", value)
            if normalized not in medications:
                medications.append(normalized)
        for value in KNOWN_MEDICATION_PATTERN.findall(clause):
            if value not in medications:
                medications.append(value)
    return medications


def extract_intake(text: str) -> IntakeExtractionResponse:
    normalized = " ".join(text.strip().split())
    matches: list[tuple[SymptomRule, re.Match[str], bool]] = []
    for rule in RULES:
        mention = rule.mention.search(normalized)
        absent = rule.absent.search(normalized)
        evidence = absent or mention
        if evidence is not None:
            matches.append((rule, evidence, absent is not None))

    positions = sorted((evidence.start(), evidence.end()) for _, evidence, _ in matches)
    symptoms: list[SymptomObservation] = []
    symptom_positions: list[tuple[int, SymptomObservation]] = []
    for rule, evidence, is_absent in matches:
        position_index = positions.index((evidence.start(), evidence.end()))
        previous_end = positions[position_index - 1][1] if position_index > 0 else 0
        next_start = positions[position_index + 1][0] if position_index + 1 < len(positions) else len(normalized)
        onset = _normalize_onset(
            _onset_for_symptom(
                normalized, evidence.start(), evidence.end(), previous_end, next_start
            )
        )
        severity = _severity_for_symptom(
            normalized, evidence.start(), evidence.end(), positions
        )
        frequency = (
            _frequency_for_symptom(normalized, evidence.start(), evidence.end(), positions)
            if rule.name == "구토"
            else None
        )
        trend = _trend_for_symptom(
            normalized, evidence.start(), evidence.end(), positions
        )
        symptom_positions.append(
            (evidence.start(), SymptomObservation(
                name=rule.name,
                status="absent" if is_absent else "present",
                body_site=rule.body_site,
                onset=onset if not is_absent else None,
                severity=severity if not is_absent else None,
                frequency=frequency if not is_absent else None,
                trend=trend if not is_absent else None,
                source_text=evidence.group(0),
            ))
        )
    symptoms = [item for _, item in sorted(symptom_positions, key=lambda pair: pair[0])]

    medications = _extract_medications(normalized)
    allergies = list(dict.fromkeys(ALLERGY_PATTERN.findall(normalized)))
    recognized_evidence = [item.source_text for item in symptoms]
    unrecognized_fragments: list[str] = []
    for fragment in CLAUSE_SPLIT_PATTERN.split(normalized):
        fragment = fragment.strip()
        if not fragment or not MEDICAL_SIGNAL_PATTERN.search(fragment):
            continue
        recognized = any(evidence in fragment for evidence in recognized_evidence)
        recognized = recognized or any(medication in re.sub(r"\s+", "", fragment) for medication in medications)
        recognized = recognized or any(allergen in fragment for allergen in allergies)
        if not recognized:
            unrecognized_fragments.append(fragment)
    return IntakeExtractionResponse(
        symptoms=symptoms,
        medications=medications,
        allergies=allergies,
        unrecognized_fragments=unrecognized_fragments,
    )
