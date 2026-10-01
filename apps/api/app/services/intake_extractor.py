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
NOW_ADVERB = r"(?:(?:이제는?|이젠|지금은|현재는)\s*)?"
PARTICLE = r"(?:은|는|이|가|도)?"
ABSENT_ENDING = rf"{NOW_ADVERB}(?:없|{RESOLVED_STATE})"
NOT_PAINFUL = r"(?:(?:더\s*이상\s*)?안\s*(?:아프|아파|아픈)|아프지\s*않)"
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
            rf"두통(?:은|이|도)?\s*{NOW_ADVERB}(?:없|아니)|"
            rf"머리(?:가|는|도)?\s*{NOW_ADVERB}(?:(?:더\s*이상\s*)?안\s*(?:아프|아파|아픈)|아프지\s*않)|"
            rf"(?:두통|머리\s*통증)(?:은|이|가|는|도)?\s*{NOW_ADVERB}{RESOLVED_STATE}"
        ),
        "머리",
    ),
    SymptomRule(
        "발열",
        re.compile(
            r"고열|미열|발열|"
            r"(?<![가-힣])열(?=\s*$|이|은|도|까지|감|나|났|있|오르|올라|\s+(?:나|났|있|오르|올라|조금|좀|많이))"
            r"(?:이|은|도)?\s*(?:나|났|오르|있)?"
        ),
        re.compile(
            rf"(?:고열|미열|발열|열)(?:은|이|도)?\s*{NOW_ADVERB}(?:없|안\s*나|나지\s*않|내렸|{RESOLVED_STATE})"
        ),
    ),
    SymptomRule(
        "기침",
        re.compile(r"기침(?:이|을|은|도)?\s*(?:나|났|해|했|하|심하|심했|계속)?"),
        re.compile(
            rf"기침(?:은|이|도)?\s*{NOW_ADVERB}(?:없|안\s*(?:나|해|하)|나지\s*않|하지\s*않|{RESOLVED_STATE})"
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
            rf"숨(?:은|이)?\s*{NOW_ADVERB}(?:안\s*차|차지\s*않)|"
            rf"(?:호흡곤란|숨찬\s*증상)(?:은|이|도)?\s*{NOW_ADVERB}(?:없|{RESOLVED_STATE})"
        ),
    ),
    SymptomRule(
        "가슴 답답함",
        re.compile(
            rf"가슴(?:이|은|만|도)?\s*(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}"
            r"(?:답답|조이|조여|눌리)|흉부(?:가|는|만|도)?\s*(?:답답|압박)"
        ),
        re.compile(
            rf"가슴(?:이|은)?\s*{NOW_ADVERB}(?:안\s*답답|답답하지\s*않)|"
            rf"(?:가슴\s*답답함|흉부\s*압박)(?:은|이|도)?\s*{NOW_ADVERB}{RESOLVED_STATE}"
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
            rf"(?:배|복부|속)(?:이|가|는|도)?\s*{NOW_ADVERB}(?:(?:더\s*이상\s*)?안\s*(?:아프|아파|아픈)|아프지\s*않)|"
            rf"복통(?:은|이|도)?\s*{NOW_ADVERB}(?:없|{RESOLVED_STATE})|"
            rf"(?:배|복부|속)\s*통증(?:은|이|도)?\s*{NOW_ADVERB}{RESOLVED_STATE}"
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
            rf"구토(?:는|가|도)?\s*{NOW_ADVERB}(?:없|{RESOLVED_STATE})|"
            rf"토(?:는|를)?\s*{NOW_ADVERB}(?:안\s*했|하지\s*않)|"
            rf"구토\s*증상(?:은|이|도)?\s*{NOW_ADVERB}{RESOLVED_STATE}"
        ),
    ),
    SymptomRule(
        "흉통",
        re.compile(
            rf"흉통|가슴(?:이|은|도)?\s*(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}"
            r"(?:아프|아파|아팠|아픈|찌르|찌릿|콕콕)"
        ),
        re.compile(
            rf"흉통{PARTICLE}\s*{ABSENT_ENDING}|"
            rf"가슴(?:은|이|도)?\s*{NOW_ADVERB}{NOT_PAINFUL}"
        ),
        "가슴",
    ),
    SymptomRule(
        "인후통",
        re.compile(
            rf"인후통|목\s*통증|목(?:이|은|도)?\s*(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}"
            r"(?:아프|아파|아팠|아픈|따끔|칼칼|부었|부어|붓)|"
            rf"(?:인후통|목)(?:이|은|도)?\s*{IMPROVEMENT_PHRASE}|"
            r"침(?:을)?\s*삼키기(?:가)?\s*(?:힘들|어렵|아프)"
        ),
        re.compile(
            rf"인후통{PARTICLE}\s*{ABSENT_ENDING}|"
            rf"목(?:은|이|도)?\s*{NOW_ADVERB}{NOT_PAINFUL}"
        ),
        "목",
    ),
    SymptomRule(
        "콧물",
        re.compile(r"콧물|코(?:를|가)?\s*(?:훌쩍|흘러)"),
        re.compile(
            rf"콧물{PARTICLE}\s*{NOW_ADVERB}(?:없|안\s*나|나지\s*않|멈췄|{RESOLVED_STATE})"
        ),
        "코",
    ),
    SymptomRule(
        "코막힘",
        re.compile(r"코막힘|코(?:가|도)?\s*(?:꽉\s*)?막(?:혀|히|혔|힌)"),
        re.compile(
            rf"코막힘{PARTICLE}\s*{ABSENT_ENDING}|"
            rf"코(?:는|가|도)?\s*{NOW_ADVERB}(?:안\s*막|막히지\s*않)"
        ),
        "코",
    ),
    SymptomRule(
        "가래",
        re.compile(r"가래"),
        re.compile(
            rf"가래{PARTICLE}\s*{NOW_ADVERB}(?:없|안\s*(?:나|끓)|나오지\s*않|{RESOLVED_STATE})"
        ),
    ),
    SymptomRule(
        "오한",
        re.compile(r"오한|으슬으슬|한기|춥고\s*떨|몸이\s*(?:덜덜\s*)?떨"),
        re.compile(rf"(?:오한|한기){PARTICLE}\s*{ABSENT_ENDING}"),
    ),
    SymptomRule(
        "근육통",
        re.compile(
            rf"근육통|몸살|(?:온몸|몸|근육|팔다리)(?:이|가|은|도)?\s*{INTENSITY_PHRASE}"
            r"(?:쑤시|쑤셔|쑤신|결리|결려|아프|아파|아픈)"
        ),
        re.compile(
            rf"(?:근육통|몸살){PARTICLE}\s*{ABSENT_ENDING}|"
            rf"(?:온몸|몸|근육)(?:은|이|도)?\s*{NOW_ADVERB}(?:{NOT_PAINFUL}|안\s*쑤|쑤시지\s*않)"
        ),
    ),
    SymptomRule(
        "요통",
        re.compile(
            rf"요통|허리(?:가|는|도)?\s*(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}"
            r"(?:아프|아파|아팠|아픈|쑤시|쑤셔|결리|결려)"
        ),
        re.compile(
            rf"요통{PARTICLE}\s*{ABSENT_ENDING}|"
            rf"허리(?:는|가|도)?\s*{NOW_ADVERB}{NOT_PAINFUL}"
        ),
        "허리",
    ),
    SymptomRule(
        "어지러움",
        re.compile(r"어지러|어지럽|어지럼|현기증|핑\s*(?:돌|돈)|빙빙\s*(?:돌|돈)"),
        re.compile(
            rf"(?:어지럼증?|현기증){PARTICLE}\s*{ABSENT_ENDING}|"
            rf"{NOW_ADVERB}안\s*어지러|어지럽지\s*않"
        ),
    ),
    SymptomRule(
        "메스꺼움",
        re.compile(r"메스꺼|메스껍|메슥|미식거|울렁|구역질|구역감|헛구역|토할\s*(?:것\s*)?같"),
        re.compile(
            rf"(?:메스꺼움|구역감|구역질|울렁거림){PARTICLE}\s*{ABSENT_ENDING}|"
            r"메스껍지\s*않|안\s*메스꺼|울렁거리지\s*않"
        ),
    ),
    SymptomRule(
        "설사",
        re.compile(r"설사|(?:대변|변)(?:이|을|도)?\s*(?:묽|물\s*같)|물\s*같은\s*변"),
        re.compile(
            rf"설사{PARTICLE}\s*{NOW_ADVERB}(?:없|안\s*(?:했|해|하)|하지\s*않|멈췄|{RESOLVED_STATE})"
        ),
    ),
    SymptomRule(
        "변비",
        re.compile(r"변비|(?:대변|변)(?:을|이|도)?\s*(?:잘\s*)?(?:못\s*(?:봤|봐|보|본)|안\s*나와|안\s*나오)"),
        re.compile(rf"변비{PARTICLE}\s*{ABSENT_ENDING}"),
    ),
    SymptomRule(
        "발진",
        re.compile(
            r"발진|두드러기|피부(?:가|에|도)?\s*(?:\S+\s*)?(?:가렵|가려|빨갛|붉|오돌토돌|뭐가\s*(?:났|올라))|"
            r"(?:몸|피부|팔|다리|얼굴)(?:이|가|에)?\s*(?:빨갛게|붉게)\s*(?:올라|돋)"
        ),
        re.compile(rf"(?:발진|두드러기){PARTICLE}\s*{ABSENT_ENDING}"),
        "피부",
    ),
    SymptomRule(
        "피로",
        re.compile(r"피곤|피로|기운(?:이|도)?\s*없|기력(?:이|도)?\s*없|무기력|나른"),
        re.compile(
            rf"(?:피로감?|피곤함){PARTICLE}\s*{ABSENT_ENDING}|"
            r"안\s*피곤|피곤하지\s*않"
        ),
    ),
)
FREQUENCY_SYMPTOMS = {"구토", "설사"}

ONSET_PATTERN = re.compile(
    r"(?<![가-힣A-Za-z0-9])(?:어젯밤(?:부터)?|"
    r"(?:오늘|어제|그제|그저께|엊그제)\s*"
    r"(?:아침|점심|저녁|밤|새벽)(?:부터)?|"
    r"(?:오늘|어제|그제|그저께|엊그제|방금|아침|점심|저녁|밤|새벽)(?:부터)?|"
    r"(?:하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘)"
    r"(?!\s*에|\s*(?:\d+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*(?:번|회|차례))"
    r"(?:\s*(?:전부터|전|동안|째))?|"
    r"(?:일주일|한\s*주|두\s*주|한\s*달|두\s*달)(?!\s*에)"
    r"(?:\s*(?:전부터|전|동안|째))?|"
    r"(?:\d+|일|이|삼|사|오|육|칠|팔|구|십)\s*"
    r"(?:시간|일|주(?!일)|개월|달)(?!\s*에)(?:\s*(?:전부터|전|동안|째))?)"
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
TEMPERATURE_PATTERN = re.compile(r"(?<![\d.])(3[5-9]|4[0-2])(?:\.(\d))?\s*(?:도|℃)")
KNOWN_CONDITION = (
    r"고혈압|저혈압|당뇨병?|고지혈증|이상지질혈증|천식|만성\s*폐쇄성\s*폐질환|결핵|"
    r"갑상선\s*(?:기능\s*(?:저하증|항진증)|질환)|심부전|부정맥|협심증|심근경색|심장병|"
    r"뇌졸중|뇌경색|간염|지방간|간경화|신부전|만성\s*신장\s*질환|신장\s*질환|"
    r"위염|위궤양|역류성\s*식도염|과민성\s*대장\s*증후군|비염|축농증|아토피|"
    r"우울증|공황장애|불면증|빈혈|통풍|관절염|디스크|골다공증|암"
)
MEDICAL_HISTORY_PATTERN = re.compile(
    rf"(?<![가-힣])({KNOWN_CONDITION})(?:이|가|은|는|도)?\s*"
    r"(?:있|진단|앓|걸렸|걸린|치료|투병|병력)"
)
MEDICAL_HISTORY_ABSENT_PATTERN = re.compile(
    rf"(?<![가-힣])({KNOWN_CONDITION})(?:은|는|이|가|도)?\s*(?:없|아니)"
)
SURGERY_PATTERN = re.compile(r"([가-힣]{1,10}?)\s*수술(?:을|도)?\s*(?:받았|받은|했|한\s*적)")
MEDICAL_SIGNAL_PATTERN = re.compile(
    r"아프|아파|통증|열|기침|숨|호흡|답답|구토|토했|어지|설사|메스꺼|오한|"
    r"콧물|발진|붓|저리|저려|마비|출혈|두근|약|알레르기|가래|막혀|가렵|가려|"
    r"두드러기|변비|피곤|쑤시|쑤셔|울렁|몸살|현기증|침침|이명|수술|진단"
)
CLAUSE_SPLIT_PATTERN = re.compile(r"[.!?。]|(?:\s+)(?:그리고|추가로|하지만|그러나|또한)(?:\s+)")
SUBCLAUSE_SPLIT_PATTERN = re.compile(
    r"[.!?。,]|\s+(?:그리고|추가로|하지만|그러나|또한)\s+|"
    r"(?<=[가-힣])(?:고|며|면서|는데|지만)\s+"
)


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
        if rule.name == "발열":
            temperature = _nearest_value(
                TEMPERATURE_PATTERN, normalized, evidence.start(), evidence.end()
            )
            if temperature:
                severity = re.sub(r"\s*(?:도|℃)$", "℃", temperature)
        frequency = (
            _frequency_for_symptom(normalized, evidence.start(), evidence.end(), positions)
            if rule.name in FREQUENCY_SYMPTOMS
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
    medical_history = _extract_medical_history(normalized)
    evidence_spans = [(evidence.start(), evidence.end()) for _, evidence, _ in matches]
    evidence_spans += [
        (match.start(), match.end())
        for pattern in (
            MEDICAL_HISTORY_PATTERN, MEDICAL_HISTORY_ABSENT_PATTERN, SURGERY_PATTERN, TEMPERATURE_PATTERN
        )
        for match in pattern.finditer(normalized)
    ]
    unrecognized_fragments: list[str] = []
    for start, end in _subclause_spans(normalized):
        fragment = normalized[start:end].strip()
        if not fragment or not MEDICAL_SIGNAL_PATTERN.search(fragment):
            continue
        recognized = any(span_start < end and span_end > start for span_start, span_end in evidence_spans)
        recognized = recognized or any(medication in re.sub(r"\s+", "", fragment) for medication in medications)
        recognized = recognized or any(allergen in fragment for allergen in allergies)
        if not recognized:
            unrecognized_fragments.append(fragment)
    return IntakeExtractionResponse(
        symptoms=symptoms,
        medications=medications,
        allergies=allergies,
        medical_history=medical_history,
        unrecognized_fragments=unrecognized_fragments,
    )


def _subclause_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for boundary in SUBCLAUSE_SPLIT_PATTERN.finditer(text):
        # Keep the connective ending (e.g. "아프고") with the clause it belongs to.
        spans.append((start, boundary.start() + len(boundary.group(0).rstrip())))
        start = boundary.end()
    spans.append((start, len(text)))
    return spans


def _extract_medical_history(text: str) -> list[str]:
    denied = {re.sub(r"\s+", " ", value) for value in MEDICAL_HISTORY_ABSENT_PATTERN.findall(text)}
    history: list[str] = []
    for value in MEDICAL_HISTORY_PATTERN.findall(text):
        condition = re.sub(r"\s+", " ", value)
        if condition not in denied and condition not in history:
            history.append(condition)
    for value in SURGERY_PATTERN.findall(text):
        surgery = f"{value} 수술"
        if surgery not in history:
            history.append(surgery)
    return history
