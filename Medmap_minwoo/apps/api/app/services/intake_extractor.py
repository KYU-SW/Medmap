from dataclasses import dataclass
from datetime import date, timedelta
import re

from app.schemas.intake import (
    IntakeExtractionResponse,
    OtherPersonSymptom,
    PatientProfileHints,
    SymptomObservation,
)


@dataclass(frozen=True)
class SymptomRule:
    name: str
    mention: re.Pattern[str]
    absent: re.Pattern[str]
    body_site: str | None = None


INTENSITY_WORD = (
    r"(?:아주|매우|너무|많이|조금|약간|심하게|살짝|계속|자꾸|되게|엄청|진짜|정말|좀|막|"
    r"살살|콕콕|쿡쿡|꾹꾹|구구|찌릿찌릿|찌릿|욱신욱신|욱신|지끈지끈|지끈|따끔따끔|뻐근하게|찌르듯이?|"
    # How bad it is, said between the body part and the verb: "배가 참을 만하게 아파요".
    r"데굴데굴|참을\s*만하게|견딜\s*만하게|죽을\s*(?:것\s*)?같이|미칠\s*(?:것\s*)?같이|"
    r"(?:참을\s*만한|견딜\s*만한|구를|죽을|미칠|못\s*참을|잠을\s*못\s*잘)\s*(?:정도로|만큼)|"
    r"심하(?:지는|진|지)\s*않(?:은데|지만|고))"
)
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
PARTICLE = r"(?:은|는|이|가|도|을|를)?"
JOINT_PART = r"무릎|어깨|발목|손목|팔꿈치|고관절|골반|손가락\s*관절|손가락|발가락|턱관절|턱|관절"
ABSENT_ENDING = rf"{NOW_ADVERB}(?:없|{RESOLVED_STATE})"
NOT_PAINFUL = r"(?:(?:더\s*이상\s*)?안\s*(?:아프|아파|아픈)|아프지(?:는|도)?\s*않|아프진\s*않)"
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
            rf"두통|머리\s*통증|머리(?:가|는|도|야)?\s*(?:{INLINE_ONSET}\s*)?"
            rf"(?:같이\s*|함께\s*)?{INTENSITY_PHRASE}"
            rf"(?:아프|아파|아팠|아픈|지끈|욱신|띵)|"
            rf"(?:두통|머리)(?:이|가|은|는|도)?\s*{IMPROVEMENT_PHRASE}"
        ),
        re.compile(
            rf"(?:두통|머리\s*통증)(?:은|이|도)?\s*{NOW_ADVERB}(?:없|아니)|"
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
            rf"기침(?:은|이|도|을)?\s*{NOW_ADVERB}(?:없|안\s*(?:나|해|하)|나지\s*않|하지\s*않|{RESOLVED_STATE})"
        ),
    ),
    SymptomRule(
        "호흡곤란",
        re.compile(
            rf"숨(?:이|은|도)?\s*(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}(?:차|가빠|가쁘|가쁜|막혀|막히)|"
            r"숨(?:을)?\s*헐떡|"
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
            rf"(?:배|복부|속|명치|옆구리)(?:이|가|는|도|야)?\s*(?:{INLINE_ONSET}\s*)?"
            rf"{INTENSITY_PHRASE}(?:아프|아파|아팠|아픈|쑤시|쑤셔|쑤신|뒤틀|꼬여|꼬이)|"
            r"복통|(?:배|복부|명치|옆구리)\s*통증|배탈|위경련|위통"
        ),
        re.compile(
            rf"(?:배|복부|속)(?:이|가|는|도)?\s*{NOW_ADVERB}(?:(?:더\s*이상\s*)?안\s*(?:아프|아파|아픈)|아프지\s*않)|"
            rf"복통(?:은|이|도)?\s*{NOW_ADVERB}(?:없|{RESOLVED_STATE})|"
            rf"(?:배|복부|속)\s*통증(?:은|이|도)?\s*{NOW_ADVERB}(?:없|{RESOLVED_STATE})"
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
            rf"흉통|(?:가슴|흉부)\s*통증|가슴(?:이|은|도)?\s*(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}"
            r"(?:아프|아파|아팠|아픈|찌르|찌릿|콕콕|쑤시|쑤셔|쥐어짜)"
        ),
        re.compile(
            rf"(?:흉통|(?:가슴|흉부)\s*통증){PARTICLE}\s*{ABSENT_ENDING}|"
            rf"가슴(?:은|이|도)?\s*{NOW_ADVERB}{NOT_PAINFUL}"
        ),
        "가슴",
    ),
    SymptomRule(
        "인후통",
        re.compile(
            rf"인후통|목\s*통증|목감기|목(?:이|은|도)?\s*(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}"
            r"(?:아프|아파|아팠|아픈|따끔|따가|따갑|칼칼|부었|부어|붓)|"
            rf"(?:인후통|목)(?:이|은|도)?\s*{IMPROVEMENT_PHRASE}|"
            r"침(?:을)?\s*삼키기(?:가)?\s*(?:힘들|어렵|아프)|침(?:을)?\s*삼킬\s*때(?:마다)?\s*(?:아프|아파|따끔)"
        ),
        re.compile(
            rf"인후통{PARTICLE}\s*{ABSENT_ENDING}|"
            rf"목(?:은|이|도)?\s*{NOW_ADVERB}{NOT_PAINFUL}"
        ),
        "목",
    ),
    SymptomRule(
        "콧물",
        re.compile(r"콧물|코감기|코(?:를|가)?\s*(?:훌쩍|흘러|줄줄|풀)"),
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
            rf"요통|허리\s*통증|허리(?:가|는|도)?\s*(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}"
            r"(?:아프|아파|아팠|아픈|쑤시|쑤셔|결리|결려|뻐근|당기|당겨|삐끗)"
        ),
        re.compile(
            rf"(?:요통|허리\s*통증){PARTICLE}\s*{ABSENT_ENDING}|"
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
        re.compile(r"설사|(?<!소)(?:대변|변)(?:이|을|도)?\s*(?:묽|물\s*같)|물\s*같은\s*변"),
        re.compile(
            rf"설사{PARTICLE}\s*{NOW_ADVERB}(?:없|안\s*(?:했|해|하)|하지\s*않|멈췄|{RESOLVED_STATE})"
        ),
    ),
    SymptomRule(
        "변비",
        re.compile(r"변비|(?<!소)(?:대변|변)(?:을|이|도)?\s*(?:잘\s*)?(?:못\s*(?:봤|봐|보|본)|안\s*나와|안\s*나오)"),
        re.compile(rf"변비{PARTICLE}\s*{ABSENT_ENDING}"),
    ),
    SymptomRule(
        "발진",
        re.compile(
            r"발진|두드러기|피부(?:가|에|도)?\s*(?:\S+\s*)?(?:빨갛|붉|오돌토돌|뭐가\s*(?:났|올라))|"
            r"(?:몸|피부|팔|다리|얼굴)(?:이|가|에)?\s*(?:빨갛게|붉게)\s*(?:올라|돋)"
        ),
        re.compile(rf"(?:발진|두드러기){PARTICLE}\s*{ABSENT_ENDING}"),
        "피부",
    ),
    SymptomRule(
        "피로",
        re.compile(
            r"피곤|피로|기운(?:이|도)?\s*없|(?:몸에|온몸에)\s*힘(?:이)?\s*없|기력(?:이|도)?\s*없|무기력|나른|"
            r"몸(?:이)?\s*(?:천근만근|무거|무겁)|녹초|지쳐|지친다"
        ),
        re.compile(
            rf"(?:피로감?|피곤함){PARTICLE}\s*{ABSENT_ENDING}|"
            r"안\s*피곤|피곤하지\s*않"
        ),
    ),
    SymptomRule(
        "두근거림",
        re.compile(
            r"두근|벌렁|심계항진|심장(?:이)?\s*(?:너무\s*)?(?:빨리|빠르게|불규칙하게|쿵쾅)"
        ),
        re.compile(
            rf"(?:두근거림|심계항진){PARTICLE}\s*{ABSENT_ENDING}|안\s*두근|두근거리지\s*않"
        ),
        "가슴",
    ),
    SymptomRule(
        "저림",
        re.compile(r"저려|저리|저림|저린|저릿|쥐(?:가)?\s*(?:나|났)|감각(?:이)?\s*(?:없|둔하|둔해|무뎌)"),
        re.compile(rf"저림{PARTICLE}\s*{ABSENT_ENDING}|저리지\s*않|안\s*저려|안\s*저리"),
    ),
    SymptomRule(
        "소화불량",
        re.compile(
            r"소화불량|소화(?:가)?\s*(?:잘\s*)?안\s*(?:돼|되|된|됐)|체했|체한|체기|체해|"
            r"더부룩|트림"
        ),
        re.compile(
            rf"(?:소화불량|체기){PARTICLE}\s*{ABSENT_ENDING}|소화(?:는|도)?\s*{NOW_ADVERB}잘\s*(?:돼|되)"
        ),
        "복부",
    ),
    SymptomRule(
        "속쓰림",
        re.compile(
            rf"속쓰림|(?:속|가슴|명치|윗배|위)(?:이|가)?\s*{INTENSITY_PHRASE}(?:쓰려|쓰리|쓰린|쓰림|타는)|"
            r"신물(?:이)?\s*(?:올라|넘어)|위산\s*역류"
        ),
        re.compile(
            rf"속쓰림{PARTICLE}\s*{ABSENT_ENDING}|(?:속|위)(?:은|이|는|도)?\s*{NOW_ADVERB}(?:안\s*쓰려|쓰리지\s*않)"
        ),
        "복부",
    ),
    SymptomRule(
        "식욕부진",
        re.compile(
            r"식욕부진|식욕(?:이|도)?\s*(?:없|떨어|뚝)|입맛(?:이|도)?\s*(?:없|떨어|뚝|통\s*없)|"
            r"밥(?:을|이)?\s*(?:잘\s*)?(?:못\s*먹|안\s*넘어가|먹기\s*싫)"
        ),
        re.compile(
            rf"(?:식욕|입맛)(?:은|이|도)?\s*{NOW_ADVERB}(?:괜찮|있|좋|돌아)|식욕부진{PARTICLE}\s*{ABSENT_ENDING}"
        ),
    ),
    SymptomRule(
        "불면",
        re.compile(
            r"불면|잠(?:을|이)?\s*(?:잘\s*)?(?:못\s*(?:자|잤|잔|들)|안\s*(?:와|온|오)|설쳐|설쳤)|"
            r"자다가\s*(?:자꾸\s*|계속\s*)?깨"
        ),
        re.compile(rf"잠(?:은|을|도)?\s*{NOW_ADVERB}잘\s*(?:자|잤|자요)|불면{PARTICLE}\s*{ABSENT_ENDING}"),
    ),
    SymptomRule(
        "부종",
        re.compile(
            r"부종|붓기|부기(?=가|는|도|\s|$)|(?:다리|발|발목|얼굴|손|손가락|눈두덩|눈|입술|몸)(?:이|가|도)?\s*(?:퉁퉁\s*|많이\s*)?"
            r"(?:부었|부어|붓|부은)"
        ),
        re.compile(rf"(?:부종|붓기|부기){PARTICLE}\s*{NOW_ADVERB}(?:없|빠졌|가라앉았|{RESOLVED_STATE})"),
    ),
    SymptomRule(
        "귀 통증",
        re.compile(
            rf"귀\s*통증|귀(?:가|는|도)?\s*(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}"
            r"(?:아프|아파|아팠|아픈|찌르|먹먹|욱신)"
        ),
        re.compile(rf"귀(?:는|가|도)?\s*{NOW_ADVERB}{NOT_PAINFUL}|귀\s*통증{PARTICLE}\s*{ABSENT_ENDING}"),
        "귀",
    ),
    SymptomRule(
        "눈 통증",
        re.compile(
            rf"눈\s*통증|눈(?:이|은|도)?\s*(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}"
            r"(?:아프|아파|아팠|아픈|따가|따갑|시려|시리|쑤셔)"
        ),
        re.compile(rf"눈(?:은|이|도)?\s*{NOW_ADVERB}{NOT_PAINFUL}|눈\s*통증{PARTICLE}\s*{ABSENT_ENDING}"),
        "눈",
    ),
    SymptomRule(
        "치통",
        re.compile(
            rf"치통|(?:(?<![가-힣])이|이빨|치아|잇몸|어금니)(?:가|이|는|도)?\s*{INTENSITY_PHRASE}"
            r"(?:아프|아파|아팠|아픈|시려|시리|욱신|쑤셔)"
        ),
        re.compile(
            rf"치통{PARTICLE}\s*{ABSENT_ENDING}|(?:이빨|치아|잇몸)(?:은|이|는|도)?\s*{NOW_ADVERB}{NOT_PAINFUL}"
        ),
        "치아",
    ),
    SymptomRule(
        "식은땀",
        re.compile(r"식은땀|(?<![가-힣])땀(?:이|을|도)?\s*(?:많이\s*|비\s*오듯\s*|줄줄\s*)?(?:나|났|흘|흐르)"),
        re.compile(
            rf"식은땀{PARTICLE}\s*{ABSENT_ENDING}|(?<![가-힣])땀(?:은|이|도)?\s*{NOW_ADVERB}(?:안\s*나|나지\s*않)"
        ),
    ),
    SymptomRule(
        "가려움",
        re.compile(r"가려워|가렵|가려움|가려운|간지러|간지럽|간지럼|소양감"),
        re.compile(
            rf"(?:가려움|간지럼|소양감){PARTICLE}\s*{ABSENT_ENDING}|안\s*가려|가렵지\s*않|간지럽지\s*않"
        ),
    ),
    SymptomRule(
        "시야 이상",
        re.compile(
            r"시야|복시|(?:눈|눈앞|앞)(?:이|가)?\s*(?:자꾸\s*|좀\s*)?(?:침침|흐릿|흐려|뿌옇|뿌얘|캄캄|깜깜|번쩍)|"
            r"(?:잘\s*)?안\s*보여|겹쳐\s*보|두\s*개로\s*보"
        ),
        re.compile(
            rf"(?:시야\s*이상|복시){PARTICLE}\s*{ABSENT_ENDING}|(?:눈|시력)(?:은|도)?\s*{NOW_ADVERB}(?:괜찮|잘\s*보)"
        ),
        "눈",
    ),
    SymptomRule(
        "떨림",
        re.compile(
            r"수전증|(?:손|팔|다리|손발|입술|턱|몸)(?:이|가|도)?\s*(?:덜덜\s*|부들부들\s*|계속\s*|자꾸\s*)?"
            r"(?:떨려|떨리|떨림|떨린)"
        ),
        re.compile(rf"떨림{PARTICLE}\s*{ABSENT_ENDING}|(?:안\s*떨|떨리지\s*않)"),
    ),
    SymptomRule(
        "이명",
        re.compile(r"이명|귀(?:에서)?\s*(?:삐|윙|웅웅|소리(?:가)?\s*(?:나|들려))|귀(?:가)?\s*울려|귀(?:가)?\s*울리"),
        re.compile(rf"이명{PARTICLE}\s*{ABSENT_ENDING}"),
        "귀",
    ),
    SymptomRule(
        "코피",
        re.compile(r"코피|코에서\s*피"),
        re.compile(rf"코피{PARTICLE}\s*{NOW_ADVERB}(?:없|안\s*나|멈췄|{RESOLVED_STATE})"),
        "코",
    ),
    SymptomRule(
        "객혈",
        re.compile(
            r"객혈|각혈|(?:기침|가래)(?:할\s*때|하면|에|에서)?\s*(?:피|핏덩이)(?:가|도)?\s*(?:섞|나|묻)|"
            r"피(?:가)?\s*섞인\s*(?:가래|기침)"
        ),
        re.compile(rf"(?:객혈|각혈){PARTICLE}\s*{ABSENT_ENDING}"),
    ),
    SymptomRule(
        "토혈",
        re.compile(r"토혈|피(?:를)?\s*토했|피(?:를)?\s*토해|토(?:에|한\s*것에)\s*피|피가\s*섞인\s*구토"),
        re.compile(rf"토혈{PARTICLE}\s*{ABSENT_ENDING}"),
    ),
    SymptomRule(
        "혈변",
        re.compile(
            r"혈변|(?:대변|변)(?:에|에서)\s*피|피(?:가)?\s*섞인\s*(?:대변|변)|"
            r"(?:검은|까만|짜장\s*같은)\s*(?:대변|변)|(?:대변|변)(?:이)?\s*(?:검게|까맣게)"
        ),
        re.compile(rf"혈변{PARTICLE}\s*{ABSENT_ENDING}"),
    ),
    SymptomRule(
        "혈뇨",
        re.compile(r"혈뇨|피오줌|(?:소변|오줌)(?:에|에서|이)?\s*(?:피|빨갛|붉)"),
        re.compile(rf"혈뇨{PARTICLE}\s*{ABSENT_ENDING}"),
    ),
    SymptomRule(
        "배뇨통",
        re.compile(
            r"배뇨통|(?:소변|오줌)(?:을)?\s*(?:볼|눌)\s*때\s*(?:마다\s*)?(?:아프|아파|따끔|찌릿|화끈|쓰라)"
        ),
        re.compile(rf"배뇨통{PARTICLE}\s*{ABSENT_ENDING}"),
    ),
    SymptomRule(
        "빈뇨",
        re.compile(r"빈뇨|(?:소변|오줌)(?:을|이|도)?\s*(?:너무\s*)?자주|화장실(?:을|에)?\s*(?:너무\s*)?자주\s*가"),
        re.compile(rf"빈뇨{PARTICLE}\s*{ABSENT_ENDING}"),
    ),
    SymptomRule(
        "기절",
        re.compile(r"기절|실신|정신(?:을)?\s*잃|의식(?:을)?\s*잃|쓰러졌|쓰러진\s*적"),
        re.compile(rf"(?:기절|실신)(?:한\s*적)?{PARTICLE}\s*{ABSENT_ENDING}|쓰러진\s*적(?:은|도)?\s*없"),
    ),
    SymptomRule(
        "마비",
        re.compile(
            r"마비|(?:팔|다리|한쪽|얼굴|손|발|팔다리)(?:이|에|가|도)?\s*(?:갑자기\s*)?"
            r"(?:힘이\s*(?:빠|없|안\s*들)|안\s*움직|움직이지\s*않)|얼굴(?:이)?\s*(?:한쪽으로\s*)?(?:처졌|돌아갔|비뚤어)"
        ),
        re.compile(rf"마비{PARTICLE}\s*{ABSENT_ENDING}"),
    ),
    SymptomRule(
        "말 어눌함",
        re.compile(r"(?:말|발음)(?:이|을)?\s*(?:자꾸\s*|갑자기\s*)?(?:어눌|꼬여|꼬이|안\s*나와|이상해)|말하기(?:가)?\s*힘들"),
        re.compile(r"(?:말|발음)(?:은|도)?\s*(?:괜찮|정상|또렷)"),
    ),
    SymptomRule(
        "쉰 목소리",
        re.compile(
            r"쉰\s*목소리|목(?:이)?\s*쉬었|목(?:이)?\s*쉬어|목(?:이)?\s*잠겼|목소리(?:가)?\s*(?:쉬|변했|안\s*나|갈라)"
        ),
        re.compile(r"목소리(?:는|도)?\s*(?:괜찮|정상)"),
        "목",
    ),
    SymptomRule(
        "체중 감소",
        re.compile(
            r"체중(?:이)?\s*(?:줄|빠졌|감소)|몸무게(?:가)?\s*(?:줄|빠졌)|살(?:이)?\s*(?:많이\s*|갑자기\s*)?빠졌|"
            r"\d+\s*(?:킬로|kg)(?:가|나|이)?\s*(?:빠졌|줄었)"
        ),
        re.compile(r"(?:체중|몸무게)(?:은|는|도)?\s*(?:그대로|변화\s*없|안\s*빠졌)"),
    ),
    SymptomRule(
        "경련",
        re.compile(r"(?<!위)경련|발작|(?:몸|팔|다리)(?:이|가)?\s*(?:뻣뻣해지|뒤틀리)"),
        re.compile(rf"(?:경련|발작){PARTICLE}\s*{ABSENT_ENDING}"),
    ),
    SymptomRule(
        "관절 통증",
        re.compile(
            rf"관절통|(?:{JOINT_PART})(?:이|가|은|는|도)?\s*(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}"
            r"(?:아프|아파|아팠|아픈|쑤시|쑤셔|시큰|시려|결려|붓|부었)|"
            rf"(?:{JOINT_PART})\s*통증"
        ),
        re.compile(
            rf"관절통{PARTICLE}\s*{ABSENT_ENDING}|(?:{JOINT_PART})(?:은|는|도)?\s*{NOW_ADVERB}{NOT_PAINFUL}"
        ),
        "관절",
    ),
    SymptomRule(
        "입안 통증",
        re.compile(
            rf"구내염|입병|(?:입안|입\s*안|혀|입천장)(?:이|가|은|는|도|에)?\s*(?:{INLINE_ONSET}\s*)?{INTENSITY_PHRASE}"
            r"(?:아프|아파|아팠|아픈|따가|따갑|쓰라|헐었|헐어|헌\s|헐|뭐가\s*났)"
        ),
        re.compile(
            rf"(?:구내염|입병){PARTICLE}\s*{ABSENT_ENDING}|(?:입안|혀)(?:은|는|도|이|가)?\s*{NOW_ADVERB}{NOT_PAINFUL}"
        ),
        "입안",
    ),
    SymptomRule(
        "재채기",
        re.compile(r"재채기"),
        re.compile(rf"재채기{PARTICLE}\s*{ABSENT_ENDING}|재채기(?:는|도)?\s*안\s*(?:해|나)"),
    ),
    SymptomRule(
        "쌕쌕거림",
        # STT spells the same sound several ways ("쎅쎅" from the server model).
        re.compile(r"쌕쌕|쎅쎅|색색\s*소리|숨(?:을)?\s*쉴\s*때\s*(?:휘파람|그르렁)\s*소리"),
        re.compile(rf"쌕쌕(?:거림|거리는\s*소리)?{PARTICLE}\s*{ABSENT_ENDING}"),
    ),
    SymptomRule(
        "배뇨 곤란",
        re.compile(
            r"(?:소변|오줌)(?:이|을|도)?\s*(?:잘\s*)?(?:안\s*나와|안\s*나오|안\s*나온|못\s*(?:봤|봐|보|본)|"
            r"보기(?:가)?\s*(?:힘들|어렵)|찔끔|시원하게\s*안)"
        ),
        re.compile(r"(?:소변|오줌)(?:은|도)?\s*(?:잘\s*)?(?:나와|나오고|봐요|보고)"),
    ),
    SymptomRule(
        "눈 충혈",
        re.compile(rf"충혈|눈(?:이|은|도)?\s*{INTENSITY_PHRASE}(?:빨개|빨갛|벌개|벌겋)"),
        re.compile(rf"충혈{PARTICLE}\s*{ABSENT_ENDING}"),
        "눈",
    ),
    SymptomRule(
        "생리통",
        re.compile(r"생리통|(?:생리|월경)(?:할\s*때|\s*중에?|\s*때문에)?\s*(?:배가\s*)?(?:너무\s*|많이\s*|심하게\s*)?(?:아프|아파|아팠)"),
        re.compile(rf"생리통{PARTICLE}\s*{ABSENT_ENDING}"),
        "아랫배",
    ),
    SymptomRule(
        "복부 팽만",
        re.compile(r"(?:배|아랫배)(?:가|에)?\s*(?:너무\s*|자꾸\s*)?(?:빵빵|땡땡)|가스(?:가)?\s*(?:자꾸\s*|많이\s*)?(?:차|찼|찬)|방귀(?:가|를)?\s*(?:너무\s*)?자주"),
        re.compile(rf"(?:복부\s*팽만|가스){PARTICLE}\s*{ABSENT_ENDING}"),
        "복부",
    ),
    SymptomRule(
        "목 이물감",
        re.compile(r"이물감|목(?:에|이)?\s*(?:뭐가|뭔가|무언가)?\s*걸린\s*(?:것\s*)?같|목(?:이)?\s*막힌\s*(?:것\s*)?같"),
        re.compile(rf"이물감{PARTICLE}\s*{ABSENT_ENDING}"),
        "목",
    ),
    SymptomRule(
        "눈 분비물",
        re.compile(r"눈곱|눈물(?:이)?\s*(?:계속|자꾸|많이)\s*(?:나|흘러|흘)"),
        re.compile(rf"눈곱{PARTICLE}\s*{ABSENT_ENDING}"),
        "눈",
    ),
    SymptomRule(
        "목 결림",
        re.compile(rf"뒷목|목(?:이|덜미가)?\s*{INTENSITY_PHRASE}(?:뻐근|결려|결리|뻣뻣|안\s*돌아가)"),
        re.compile(rf"(?:뒷목|목)(?:은|도)?\s*{NOW_ADVERB}(?:괜찮|안\s*뻐근)"),
        "뒷목",
    ),
    SymptomRule(
        "손발 차가움",
        re.compile(r"수족냉증|(?:손발|손|발)(?:이|가|도)?\s*(?:너무\s*|많이\s*|자주\s*)?(?:차가워|차가운|차요|차서|시려|시리|얼음)"),
        re.compile(rf"수족냉증{PARTICLE}\s*{ABSENT_ENDING}"),
    ),
    SymptomRule(
        "우울감",
        re.compile(r"우울(?!증)|의욕(?:이)?\s*없|아무것도\s*하기\s*싫|기분(?:이)?\s*(?:계속\s*)?(?:가라앉|처져|처지|다운)"),
        re.compile(rf"우울(?:감|증)?{PARTICLE}\s*{ABSENT_ENDING}|우울하지\s*않"),
    ),
    SymptomRule(
        "불안감",
        re.compile(r"불안(?!정)|초조|조마조마"),
        re.compile(rf"불안(?:감)?{PARTICLE}\s*{ABSENT_ENDING}|불안하지\s*않"),
    ),
    SymptomRule(
        "청력 저하",
        re.compile(r"청력|난청|(?:귀|소리|말)(?:가|이|도)?\s*(?:잘\s*)?안\s*들려|(?:귀|소리|말)(?:가|이|도)?\s*잘\s*안\s*들리"),
        re.compile(rf"(?:청력\s*저하|난청){PARTICLE}\s*{ABSENT_ENDING}|(?:귀|소리)(?:는|도)?\s*잘\s*들려"),
        "귀",
    ),
    SymptomRule(
        "입마름",
        re.compile(r"입마름|구갈|갈증|(?:입|입안|목)(?:이|가|도)?\s*(?:자주\s*|계속\s*|바짝\s*|너무\s*)*(?:말라|마르|마른|건조)"),
        re.compile(rf"(?:입마름|갈증){PARTICLE}\s*{ABSENT_ENDING}"),
    ),
)
FREQUENCY_SYMPTOMS = {"구토", "설사"}
SIDE_PATTERN = re.compile(r"(오른쪽|왼쪽|양쪽|우측|좌측|오른|왼)(?:\s*편)?")
SIDE_NAMES = {"우측": "오른쪽", "오른": "오른쪽", "좌측": "왼쪽", "왼": "왼쪽"}
# Symptoms without a fixed body site that still happen somewhere: "왼쪽 팔이 저려요".
PART_SYMPTOMS = {"저림", "부종", "떨림", "마비", "가려움", "발진"}
PART_WORDS = r"손발|손가락|발가락|손등|발등|손목|발목|손|발|팔다리|팔|다리|얼굴|입술|눈두덩|눈|등|온몸|몸|피부|턱|혀"
# Words that name a narrower place than the rule's body site when they start the evidence.
SITE_WORD_PATTERN = re.compile(
    rf"(?:아랫|윗|뒷|앞)?(?:배|머리)|명치|옆구리|{JOINT_PART}|가슴|허리|귀|눈|목"
)

ONSET_PATTERN = re.compile(
    r"(?<![가-힣A-Za-z0-9])(?:"
    r"\d{1,2}\s*월\s*\d{1,2}\s*일(?:\s*(?:쯤|경))?(?:\s*부터)?|"
    r"(?:지난\s*주|저번\s*주|이번\s*주)\s*[월화수목금토일]요일(?:부터|쯤)?|"
    r"[월화수목금토일]요일(?:부터|쯤)?|"
    r"어젯밤(?:부터)?|"
    r"(?:오늘|어제|그제|그저께|엊그제)\s*"
    r"(?:아침|점심|저녁|밤|새벽)(?:부터)?|"
    r"(?:하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘|(?:\d+|일|이|삼|사|오|육|칠|팔|구|십)\s*일)"
    r"\s*전\s*(?:아침|점심|저녁|밤|새벽)(?:부터)?|"
    r"(?:오늘|어제|그제|그저께|엊그제|방금|아침|점심|저녁|밤|새벽)(?:부터)?|"
    r"(?:하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘)"
    r"(?!\s*에|\s*(?:\d+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*(?:번|회|차례))"
    r"(?:\s*(?:전부터|전|동안|째))?|"
    r"(?:일주일|한\s*주|두\s*주|한\s*달|두\s*달)(?!\s*에)"
    r"(?:\s*(?:전부터|전|동안|째))?|"
    r"(?:\d+|일|이|삼|사|오|육|칠|팔|구|십)\s*"
    r"(?:시간|일|주(?!일)|개월|달)(?!\s*에)(?:\s*(?:전부터|전|동안|째))?)"
)
MILD_SEVERITY = (
    r"참을\s*만|견딜\s*만|살짝|가볍게|약하게|그럭저럭|별로\s*안\s*심|심하(?:지는|진|지)\s*않"
)
MODERATE_SEVERITY = r"보통|중간\s*정도|적당히"
STRONG_SEVERITY = (
    r"못\s*참|참기\s*(?:힘들|어렵)|견디기\s*(?:힘들|어렵)|죽을\s*(?:것\s*)?같|미칠\s*(?:것\s*)?같|"
    r"잠(?:을)?\s*못\s*잘\s*(?:정도|만큼)|(?:걷지도|움직이지도|아무것도)\s*못\s*할\s*(?:정도|만큼)|"
    r"데굴데굴|극심|엄청"
)
SEVERITY_PATTERN = re.compile(
    rf"{MILD_SEVERITY}|{MODERATE_SEVERITY}|{STRONG_SEVERITY}|"
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
    r"((?:(?:알레르기|감기|비염|혈압|당뇨|진통|해열|소화|위장|고지혈증|콜레스테롤|갑상선|천식|수면|우울증)\s*약)|"
    r"(?:[가-힣A-Za-z0-9-]{2,20}(?:약|제)))"
    r"(?=(?:과|와|을|를|도|은|는)?(?:\s|$))"
)
KNOWN_MEDICATION_PATTERN = re.compile(
    r"타이레놀|아세트아미노펜|이부프로펜|애드빌|게보린|판피린|판콜(?:에이|에스)?|펜잘|부루펜|탁센|낙센|"
    r"아스피린|아목시실린|오구멘틴|세파클러|클래리스로마이신|지르텍|알레그라|코대원|시네츄라|"
    r"베아제|훼스탈|겔포스|개비스콘|스멕타|로페라마이드|넥시움|메트포르민|리피토|노바스크|"
    r"와파린|엘리퀴스|씬지로이드|신지로이드|프레드니솔론|인슐린|벤토린|심비코트|"
    r"테라플루|화이투벤|콜대원|이지엔6|까스활명수|활명수|후시딘|마데카솔"
)
# Generic drug name endings, e.g. 세팔렉신 is not listed but 아지트로마이신 ends in 마이신.
DRUG_NAME_PATTERN = re.compile(
    r"(?<![가-힣])[가-힣]{2,10}(?:마이신|실린|프로펜|스타틴|사르탄|프라졸|디핀|세핀|파린|플록사신)"
)
MEDICATION_VERB_PATTERN = re.compile(
    r"먹|복용|처방|투여|맞았|맞고|흡입|뿌리|뿌려|바르|발라|발랐|붙이|붙여|붙였|마셨|마시|마셔"
)
DOSE_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:mg|밀리그램|밀리|mcg|g|그램|ml|cc|정|알|캡슐|포|봉|방울|퍼프)|"
    r"(?:한|두|세|반)\s*(?:알|정|포|봉|캡슐)"
)
MEDICATION_TIMING_PATTERN = re.compile(
    r"하루(?:에)?\s*(?:\d+|한|두|세|네)\s*(?:번|회|차례)|(?:\d+|한|두|세|네|여섯)\s*시간\s*마다|"
    r"하루(?=(?:에)?\s*(?:\d+|한|두|세|네|반)\s*(?:알|정|포|봉|캡슐))|"
    r"(?:아침|점심|저녁|자기\s*전|식후|식전)(?:\s*(?:,|하고|이랑)?\s*(?:아침|점심|저녁|자기\s*전))*"
    r"(?:\s*(?:에|마다|으로|로))?|(?:필요할|아플)\s*때"
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
    r"우울증|공황장애|불면증|빈혈|통풍|관절염|디스크|골다공증|"
    r"녹내장|백내장|전립선\s*비대증|파킨슨병|치매|뇌전증|간질|건선|크론병|궤양성\s*대장염|"
    r"담석증?|자궁근종|대상포진|폐렴|암"
)
DIAGNOSED_CONDITION_PATTERN = re.compile(
    r"(?<![가-힣])([가-힣]{2,12}?)\s*(?:이라고|라고|으로|로)?\s*진단(?:을|도)?\s*(?:받|나왔)"
)
NOT_A_CONDITION_PATTERN = re.compile(
    r"[가-힣]*(?:에서|에게|한테|께서)|병원|의사|검사|선생님|작년|올해|예전|최근|이번|처음|정식"
)
MEDICAL_HISTORY_PATTERN = re.compile(
    rf"(?<![가-힣])({KNOWN_CONDITION})(?:이|가|은|는|도|을|를)?\s*"
    r"(?:있|진단|앓|걸렸|걸린|치료|투병|병력)"
)
MEDICAL_HISTORY_ABSENT_PATTERN = re.compile(
    rf"(?<![가-힣])({KNOWN_CONDITION})(?:은|는|이|가|도)?\s*(?:없|아니)"
)
SURGERY_PATTERN = re.compile(r"([가-힣]{1,10}?)\s*(수술|시술)(?:을|도)?\s*(?:받았|받은|했|한\s*적)")
# History said without a disease name: "혈압이 높아요", "간이 안 좋아요", "폐렴으로 입원했어요".
HIGH_READING_PATTERN = re.compile(r"(?<![가-힣])(혈압|혈당|콜레스테롤)(?:이|가|도)?\s*(?:좀\s*|많이\s*|조금\s*)?높(?!지\s*않|진\s*않)")
WEAK_ORGAN_PATTERN = re.compile(r"(?<![가-힣])(간|신장|콩팥|심장|폐|갑상선)(?:이|가|도)?\s*(?:좀\s*|많이\s*)?안\s*좋")
ADMISSION_PATTERN = re.compile(r"(?<![가-힣])([가-힣]{2,10}?)(?:으로|로)\s*입원")
MEDICINE_SUFFIX_PATTERN = re.compile(r"\s*약(?!간|해|하|한|했)|제(?:를|을|도|는|은|\s|$)")
MEDICAL_SIGNAL_PATTERN = re.compile(
    r"아프|아파|아픈|통증|열|기침|숨|호흡|답답|구토|토했|어지|설사|메스꺼|오한|"
    r"콧물|발진|붓|부었|부어|저리|저려|마비|출혈|두근|약|알레르기|가래|막혀|가렵|가려|"
    r"두드러기|변비|피곤|쑤시|쑤셔|울렁|몸살|현기증|침침|이명|수술|진단|"
    r"감기|배탈|체했|체한|소화|입맛|식욕|잠을|잠이|쓰려|쓰리|더부룩|벌렁|땀|경련|"
    r"뻐근|결려|결리|무거|시려|시리|따가|따갑|가빠|가쁘|떨려|떨리|떨림|화끈|어둡|흐릿|흐려|토할|피가|피를|멍|"
    r"침침|간지|소변|오줌|기절|쓰러|정신을|의식|힘이|어눌|발음|쉬었|목소리|체중|몸무게|살이\s*빠|발작|헐었|헐어|"
    r"불편|혹이|혹\s*같|덩어리|부르트|부르텄|들려|말라|마르|갈증"
)
CLAUSE_SPLIT_PATTERN = re.compile(r"[.!?。]|(?:\s+)(?:그리고|추가로|하지만|그러나|또한)(?:\s+)")
UNCERTAIN_PATTERN = re.compile(
    r"모르겠|잘\s*모르|확실(?:하지|치|하진)\s*않|헷갈|긴가민가|애매|같기도|"
    r"있는지\s*없는지|인지\s*아닌지|기억(?:이)?\s*(?:잘\s*)?안\s*나"
)
AGE_PATTERN = re.compile(
    r"(?<![\d.])(\d{1,3})\s*(?:살|세)(?!\s*때)(?:이에요|예요|입니다|이고|인데|이요|요)?|나이(?:는|가)?\s*(\d{1,3})"
)
SEX_PATTERN = re.compile(
    r"(?<![가-힣])(?:(?P<female>여자|여성)|남자|남성)(?=이에요|예요|입니다|이고|인데|이요|고\s|요)"
)
# Checked in order: negations first so "담배는 안 피워요" is not read as smoking.
PREGNANCY_PATTERNS = (
    ("unknown", re.compile(r"임신(?:인지|했는지|한\s*건지)\s*(?:잘\s*)?모르|임신\s*여부(?:는)?\s*(?:잘\s*)?모르")),
    ("no", re.compile(r"임신(?:은|이|도)?\s*(?:아니|안\s*했|하지\s*않|아닙니다)|임신\s*가능성(?:은|이)?\s*없")),
    ("yes", re.compile(r"임신\s*(?:중|\d+\s*주|했|한\s*(?:것|거)\s*같|일\s*수도|가능성(?:이)?\s*있)")),
)
SMOKING_PATTERNS = (
    ("former", re.compile(r"담배(?:는|를|도)?\s*(?:\S+\s+){0,3}(?:끊었|끊은|끊고)|금연(?:\s*중|했|한\s*지)|예전에\s*(?:담배를?\s*)?피웠")),
    ("never", re.compile(
        r"담배(?:는|를|도)?\s*(?:안\s*(?:피워|피우|펴|핍|피운)|피우지\s*않|피운\s*적(?:이|은)?\s*없)|비흡연|흡연(?:은|도)?\s*안\s*해"
    )),
    ("current", re.compile(r"담배(?:를|는|도)?\s*(?:\S+\s+){0,3}(?:피워|피우|펴|핍|피고|태워)|흡연(?:해|하|자|\s*중)")),
)
DRINKING_PATTERNS = (
    ("no", re.compile(r"술(?:은|을|도)?\s*(?:안\s*(?:마셔|마시|먹)|못\s*마셔|마시지\s*않|끊었|입에도\s*안)|금주")),
    ("yes", re.compile(r"(?<![가-힣])술(?:을|은|도)?\s*(?:\S+\s*)?(?:마셔|마시|마셨|먹어|먹고|먹었)|음주(?:를|는)?\s*(?:해|하|자주|가끔)")),
)
OTHER_PERSON = (
    r"남편|아내|와이프|부인|엄마|어머니|아빠|아버지|아이|애|아기|애기|아들|딸|동생|형|누나|언니|오빠|"
    r"친구|동료|가족|할머니|할아버지|남자\s*친구|여자\s*친구|남친|여친|룸메이트|옆\s*사람|직장\s*동료"
)
PERSON_OR_SELF_PATTERN = re.compile(
    rf"(?<![가-힣])(?:(?P<person>{OTHER_PERSON})(?:들)?(?:이|가|도|는|은|께서|께서도)|"
    r"(?:저는|제가|저도|나는|내가|나도|본인은|저희\s*애가\s*아니라\s*제가))(?=\s)"
)
SENTENCE_SPLIT_PATTERN = re.compile(r"[.!?。]|(?<=[가-힣]요)\s+")
CAUSE_DOUBT_PATTERN = re.compile(r"때문|그런지|탓|원인|이유|인지는|해서인지")
CLAUSE_SUBJECT_PATTERN = re.compile(r"[가-힣]+(?:이|가|은|는|도)(?=\s)")
NON_SUBJECT_WORD_PATTERN = re.compile(
    rf"(?:{INTENSITY_WORD}|같이|깊이|높이|함께|또|이제|지금|현재|오늘|어제|그제|요즘|"
    r"아침|점심|저녁|밤|새벽|낮|[가-힣]*부터|[가-힣]*에)(?:이|가|은|는|도)?"
)
LEADING_ADVERB_PATTERN = re.compile(r"(?:(?:또|같이|함께|이제는?|지금은|현재는|요즘은?)\s*)*")
BARE_PREDICATE_PATTERN = re.compile(
    rf"{LEADING_ADVERB_PATTERN.pattern}{INTENSITY_PHRASE}(?:안\s*)?"
    r"(?:아프|아파|아픈|아팠|쑤시|쑤셔|결려|결리|저려|저리|부었|부어|붓|답답|따끔|쓰려|쓰리|"
    r"가려|가렵|뻐근|욱신|지끈|화끈|막혀|막히|당기|당겨|시려|시리|따가|따갑|조이|조여|찌르|찌릿|콕콕)"
)
# Body parts that start a clause, glued to the next word without a space ("손가락" is not "손가 락").
GLUED_BODY = r"(?:머리|가슴|배|목|허리|등|어깨|무릎|다리|팔|손|발|눈|귀|코|속|몸|혀|입안|피부)(?:이|가)(?!락)"
GLUED_SUBJECT_PATTERN = re.compile(rf"((?:부터|째|전)(?={GLUED_BODY})|{GLUED_BODY}(?=[가-힣]))")
# "답답하고아파요": a connective ending glued to a bare predicate.
GLUED_CONNECTIVE_PATTERN = re.compile(
    r"((?<=[가-힣])(?:고|며|면서|지만))(?=" + BARE_PREDICATE_PATTERN.pattern.removeprefix(LEADING_ADVERB_PATTERN.pattern) + ")"
)
SUBCLAUSE_SPLIT_PATTERN = re.compile(
    r"[.!?。,]|\s+(?:그리고|추가로|하지만|그러나|또한|근데|그런데|그래서)\s+|"
    r"(?<=[가-힣])(?:고|며|면서|는데|지만)\s+|"
    # STT often drops the period: "열이 나요 기침은 ..." still ends a sentence at "요".
    r"(?<=[가-힣]요)\s+"
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
    if re.fullmatch(MILD_SEVERITY, value):
        return "경미함"
    if re.fullmatch(MODERATE_SEVERITY, value):
        return "중간"
    if re.fullmatch(STRONG_SEVERITY, value):
        return "심함"
    return (
        "심함"
        if "심" in value or "너무" in value or "많이" in value or "매우" in value or "아주" in value
        else "경미함"
    )


def _onset_date(onset: str | None, reference: date | None) -> str | None:
    """Turn a stated onset into a calendar date when the words fix a single day.

    Vague spans ("2주 전", "한 달 동안", "엊그제") stay as words only.
    """
    if onset is None or reference is None:
        return None
    text = re.sub(r"\s+", "", onset)
    month_day = re.match(r"(\d{1,2})월(\d{1,2})일", text)
    if month_day:
        try:
            day = date(reference.year, int(month_day.group(1)), int(month_day.group(2)))
            if day > reference:
                day = day.replace(year=reference.year - 1)
        except ValueError:
            return None
        return day.isoformat()
    weekday_match = re.match(r"(지난주|저번주|이번주)?([월화수목금토일])요일", text)
    if weekday_match:
        weekday = "월화수목금토일".index(weekday_match.group(2))
        week = weekday_match.group(1)
        this_monday = reference - timedelta(days=reference.weekday())
        if week in ("지난주", "저번주"):
            day = this_monday - timedelta(days=7) + timedelta(days=weekday)
        elif week == "이번주":
            day = this_monday + timedelta(days=weekday)
            if day > reference:
                return None
        else:
            day = reference - timedelta(days=(reference.weekday() - weekday) % 7)
        return day.isoformat()
    if re.match(r"(?:오늘|방금|아침|점심)", text) or re.fullmatch(r"\d+시간(?:전부터|전|째)?", text):
        return reference.isoformat()
    if re.match(r"(?:어제|어젯밤)", text):
        return (reference - timedelta(days=1)).isoformat()
    if re.match(r"(?:그제|그저께)", text):
        return (reference - timedelta(days=2)).isoformat()
    days_ago = re.fullmatch(r"(\d+)일(전부터|전|째)(?:아침|점심|저녁|밤|새벽)?(?:부터)?", text)
    if days_ago:
        count = int(days_ago.group(1))
        # "3일째" is the third day, so it started two days ago.
        return (reference - timedelta(days=count - 1 if days_ago.group(2) == "째" else count)).isoformat()
    return None


def _normalize_onset(value: str | None) -> str | None:
    if value is None:
        return None
    # "이틀 전 저녁부터" → "2일 전 저녁부터": normalize the day count, keep the time of day.
    with_time = re.fullmatch(r"(.+?전)\s*(아침|점심|저녁|밤|새벽)(부터)?", value)
    if with_time:
        return f"{_normalize_onset(with_time.group(1))} {with_time.group(2)}{with_time.group(3) or ''}"
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


def _extract_medications(text: str) -> tuple[list[str], list[str]]:
    """Return medication lines for the record ("타이레놀 500mg 하루 2회") and the bare names."""
    names: list[str] = []
    lines: list[str] = []
    clause_boundaries = re.compile(r"[.!?。]|(?:\s+)(?:그리고|하지만|그러나|또한)(?:\s+)|(?<=[가-힣]요)\s+")
    for clause in clause_boundaries.split(text):
        if not MEDICATION_VERB_PATTERN.search(clause):
            continue
        found: list[tuple[int, str]] = []
        for match in MEDICATION_NAME_PATTERN.finditer(clause):
            found.append((match.start(), re.sub(r"\s+", "", match.group(1))))
        for pattern in (KNOWN_MEDICATION_PATTERN, DRUG_NAME_PATTERN):
            for match in pattern.finditer(clause):
                # "페니실린 알레르기" is an allergy, not a medicine being taken.
                if not re.match(r"\s*알레르기", clause[match.end():]):
                    found.append((match.start(), match.group(0)))
        found.sort()
        for index, (position, name) in enumerate(found):
            if name in names or any(name in other or other in name for other in names):
                continue
            names.append(name)
            # Dose and timing said right after the name, before the next medicine, belong to it.
            next_position = found[index + 1][0] if index + 1 < len(found) else len(clause)
            tail = clause[position + len(name):min(next_position, position + len(name) + 30)]
            doses = [re.sub(r"(?<=\d)\s+", "", dose.group(0)) for dose in [DOSE_PATTERN.search(tail)] if dose]
            timings = [
                _normalize_frequency(timing.group(0)) if re.search(r"번|회|차례", timing.group(0))
                else re.sub(r"\s*(?:에|으로|로)$", "", re.sub(r"\s+", " ", timing.group(0)))
                for timing in [MEDICATION_TIMING_PATTERN.search(tail)] if timing
            ]
            # "하루 한 알" reads timing first; "500mg 하루 2회" reads dose first.
            details = timings + doses if timings == ["하루"] else doses + timings
            lines.append(" ".join([name, *details]))
    return lines, names


def _first_symptom_match(pattern: re.Pattern[str], text: str) -> re.Match[str] | None:
    # "두통약", "기침약", "설사약" name a medicine, not a symptom the patient has now.
    for match in pattern.finditer(text):
        if not MEDICINE_SUFFIX_PATTERN.match(text, match.end()):
            return match
    return None


SINO_DIGITS = {"일": 1, "이": 2, "삼": 3, "사": 4, "오": 5, "육": 6, "칠": 7, "팔": 8, "구": 9}
# Body temperature said in words, as the phone STT model writes it: "삼십팔 도", "삼십팔 점 오 도".
SPOKEN_TEMPERATURE_PATTERN = re.compile(
    r"(?<![가-힣])(삼|사)십(일|이|삼|사|오|육|칠|팔|구)?(?:\s*점\s*(일|이|삼|사|오|육|칠|팔|구))?\s*도"
)


def _spoken_temperature_to_digits(text: str) -> str:
    def digits(match: re.Match[str]) -> str:
        value = SINO_DIGITS[match.group(1)] * 10 + SINO_DIGITS.get(match.group(2) or "", 0)
        return f"{value}.{SINO_DIGITS[match.group(3)]}도" if match.group(3) else f"{value}도"

    return SPOKEN_TEMPERATURE_PATTERN.sub(digits, text)


def _space_glued_words(text: str) -> str:
    """STT and quick typing drop spaces: "가슴이답답하고아파요" → "가슴이 답답하고 아파요"."""
    text = GLUED_SUBJECT_PATTERN.sub(r"\1 ", text)
    return GLUED_CONNECTIVE_PATTERN.sub(r"\1 ", text)


def extract_intake(text: str, reference_date: date | None = None) -> IntakeExtractionResponse:
    normalized = _spoken_temperature_to_digits(_space_glued_words(" ".join(text.strip().split())))
    matches: list[tuple[SymptomRule, re.Match[str], bool]] = []
    for rule in RULES:
        mention = _first_symptom_match(rule.mention, normalized)
        absent = _first_symptom_match(rule.absent, normalized)
        evidence = absent or mention
        if evidence is not None:
            matches.append((rule, evidence, absent is not None))
    carried_matches, carried_spans = _carried_subject_matches(normalized, matches)
    matches += carried_matches

    positions = sorted((evidence.start(), evidence.end()) for _, evidence, _ in matches)
    symptoms: list[SymptomObservation] = []
    symptom_positions: list[tuple[int, SymptomObservation]] = []
    onset_spans: list[tuple[int, int, str | None]] = []
    for rule, evidence, is_absent in matches:
        position_index = positions.index((evidence.start(), evidence.end()))
        previous_end = positions[position_index - 1][1] if position_index > 0 else 0
        next_start = positions[position_index + 1][0] if position_index + 1 < len(positions) else len(normalized)
        onset = _normalize_onset(
            _onset_for_symptom(
                normalized, evidence.start(), evidence.end(), previous_end, next_start
            )
        )
        if onset is None and isinstance(evidence, _CarriedEvidence):
            # "어제부터 가슴이 답답하고 아파요": the borrowed subject brings its onset along.
            subject_start = evidence.end() - len(evidence.group(0))
            onset = next(
                (value for start, end, value in onset_spans if start <= subject_start < end),
                None,
            )
        onset_spans.append((evidence.start(), evidence.end(), onset))
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
        is_uncertain = _is_uncertain(normalized, evidence.start(), positions)
        if is_uncertain:
            is_absent = False
        symptom_positions.append(
            (evidence.start(), SymptomObservation(
                name=rule.name,
                status="uncertain" if is_uncertain else "absent" if is_absent else "present",
                body_site=_body_site_for(normalized, evidence, rule),
                onset=onset if not is_absent else None,
                onset_date=_onset_date(onset, reference_date) if not is_absent else None,
                severity=severity if not is_absent else None,
                frequency=frequency if not is_absent else None,
                trend=trend if not is_absent else None,
                source_text=evidence.group(0),
            ))
        )
    others_symptoms: list[OtherPersonSymptom] = []
    symptoms = []
    for start, item in sorted(symptom_positions, key=lambda pair: pair[0]):
        person = _other_person_for(normalized, start)
        if person is None:
            symptoms.append(item)
        elif item.status != "absent":
            others_symptoms.append(
                OtherPersonSymptom(person=person, symptom=item.name, source_text=item.source_text)
            )

    medications, medication_names = _extract_medications(normalized)
    allergies = list(dict.fromkeys(ALLERGY_PATTERN.findall(normalized)))
    medical_history, others_history = _extract_medical_history(normalized)
    others_symptoms += others_history
    evidence_spans = [(evidence.start(), evidence.end()) for _, evidence, _ in matches]
    evidence_spans += carried_spans
    evidence_spans += [
        (match.start(), match.end())
        for rule in RULES
        for pattern in (rule.mention, rule.absent)
        for match in pattern.finditer(normalized)
        if not MEDICINE_SUFFIX_PATTERN.match(normalized, match.end())
    ]
    evidence_spans += [
        (match.start(), match.end())
        for pattern in (
            MEDICAL_HISTORY_PATTERN, MEDICAL_HISTORY_ABSENT_PATTERN, SURGERY_PATTERN, TEMPERATURE_PATTERN,
            HIGH_READING_PATTERN, WEAK_ORGAN_PATTERN, ADMISSION_PATTERN,
        )
        for match in pattern.finditer(normalized)
    ]
    evidence_spans += [
        (match.start(), match.end())
        for match in DIAGNOSED_CONDITION_PATTERN.finditer(normalized)
        if not NOT_A_CONDITION_PATTERN.fullmatch(match.group(1))
    ]
    unrecognized_fragments: list[str] = []
    for start, end in _subclause_spans(normalized):
        fragment = normalized[start:end].strip()
        if not fragment or not MEDICAL_SIGNAL_PATTERN.search(fragment):
            continue
        recognized = any(span_start < end and span_end > start for span_start, span_end in evidence_spans)
        recognized = recognized or any(name in re.sub(r"\s+", "", fragment) for name in medication_names)
        recognized = recognized or any(allergen in fragment for allergen in allergies)
        if not recognized:
            unrecognized_fragments.append(fragment)
    return IntakeExtractionResponse(
        symptoms=symptoms,
        medications=medications,
        allergies=allergies,
        medical_history=medical_history,
        others_symptoms=others_symptoms,
        profile=_extract_profile(normalized),
        unrecognized_fragments=unrecognized_fragments,
    )


def _body_site_for(text: str, evidence, rule: SymptomRule) -> str | None:
    """Add side and sub-site to the body site: "오른쪽 아랫배", "뒷머리", "왼쪽 무릎", "왼쪽 팔"."""
    # Carried evidence starts at the predicate; its text begins with the borrowed subject.
    start = evidence.end() - len(evidence.group(0))
    clause_start = max(
        (match.end() for match in SUBCLAUSE_SPLIT_PATTERN.finditer(text, 0, start)), default=0
    )
    if rule.body_site is None:
        if rule.name not in PART_SYMPTOMS:
            return None
        part = re.match(rf"({PART_WORDS})", evidence.group(0))
        if part:
            site, site_start = part.group(1), start
        else:
            before = re.search(
                rf"({PART_WORDS})(?:이|가|에|도|은|는)?\s*{INTENSITY_PHRASE}$", text[clause_start:start]
            )
            if before is None:
                return None
            site, site_start = before.group(1), clause_start + before.start(1)
    else:
        lead = text[max(0, start - 2):start]
        prefix = next((word for word in ("아랫", "윗", "뒷", "앞") if lead.endswith(word)), "")
        site_start = start - len(prefix)
        site = rule.body_site
        site_match = SITE_WORD_PATTERN.match(prefix + evidence.group(0))
        if site_match and site_match.group(0) not in ("배", "머리", "가슴", "허리", "귀", "눈", "목"):
            site = re.sub(r"\s+", " ", site_match.group(0))
    # Only a side word right before the place counts: not "오른쪽으로 누우면 배가 아파요".
    side = re.search(rf"{SIDE_PATTERN.pattern}\s*$", text[clause_start:site_start])
    if side:
        return f"{SIDE_NAMES.get(side.group(1), side.group(1))} {site}"
    return site


def _other_person_for(text: str, evidence_start: int) -> str | None:
    """Who has the symptom when someone other than the patient is the subject.

    "남편도 기침을 하고 열이 나요" keeps 남편 for the whole sentence; "저는" or a new
    sentence brings it back to the patient.
    """
    sentence_start = 0
    for boundary in SENTENCE_SPLIT_PATTERN.finditer(text, 0, evidence_start):
        sentence_start = boundary.end()
    person: str | None = None
    for match in PERSON_OR_SELF_PATTERN.finditer(text, sentence_start, evidence_start):
        person = match.group("person")
    return person


def _is_uncertain(text: str, evidence_start: int, positions: list[tuple[int, int]]) -> bool:
    """True when the patient says they are not sure about this symptom.

    The hedge may sit in the symptom's own clause ("기침은 잘 모르겠어요") or in a
    neighbouring clause that mentions no other symptom ("열이 있는 것 같기도 하고 잘
    모르겠어요", "확실하진 않은데 열이 있어요").
    """
    spans = _subclause_spans(text)
    index = next(
        (number for number, (start, end) in enumerate(spans) if start <= evidence_start < end),
        None,
    )
    if index is None:
        return False

    def mentions_other_symptom(start: int, end: int) -> bool:
        return any(start <= position_start < end for position_start, _ in positions)

    def hedges(start: int, end: int) -> bool:
        # "이거 때문에 그런지는 모르겠는데" doubts the cause, not the symptom.
        return any(
            not CAUSE_DOUBT_PATTERN.search(text[max(start, match.start() - 12):match.start()])
            for match in UNCERTAIN_PATTERN.finditer(text, start, end)
        )

    own_start, own_end = spans[index]
    if hedges(own_start, own_end):
        return True
    for neighbour in (index + 1, index - 1):
        if 0 <= neighbour < len(spans):
            start, end = spans[neighbour]
            if not mentions_other_symptom(start, end) and hedges(start, end):
                return True
    return False


@dataclass(frozen=True)
class _CarriedEvidence:
    """Evidence for a predicate whose subject is in the previous clause.

    It quacks like re.Match so the attribute helpers can use it: the position is
    the predicate itself, and the text shows the subject it borrowed.
    """

    predicate_start: int
    predicate_end: int
    text: str

    def start(self) -> int:
        return self.predicate_start

    def end(self) -> int:
        return self.predicate_end

    def group(self, _: int = 0) -> str:
        return self.text


def _carried_subject_matches(
    text: str, matches: list[tuple[SymptomRule, re.Match[str], bool]]
) -> tuple[list[tuple[SymptomRule, _CarriedEvidence, bool]], list[tuple[int, int]]]:
    """Read "가슴이 답답하고 아파요" as "가슴이 답답" + "가슴이 아파"."""
    found_names = {rule.name for rule, _, _ in matches}
    covered = [(evidence.start(), evidence.end()) for _, evidence, _ in matches]
    carried: list[tuple[SymptomRule, _CarriedEvidence, bool]] = []
    recognized_spans: list[tuple[int, int]] = []
    subjects: list[tuple[str, int]] = []
    for clause_start, clause_end in _subclause_spans(text):
        raw = text[clause_start:clause_end]
        start = clause_start + len(raw) - len(raw.lstrip())
        clause = text[start:clause_end].rstrip(" ,.!?。")
        end = start + len(clause)
        if not clause:
            continue
        clause_subjects = [
            (match.group(0), start + match.start())
            for match in CLAUSE_SUBJECT_PATTERN.finditer(clause)
            if not NON_SUBJECT_WORD_PATTERN.fullmatch(match.group(0))
        ]
        if clause_subjects:
            subjects = clause_subjects
            continue
        if not subjects or not BARE_PREDICATE_PATTERN.match(clause):
            continue
        if any(span_start < end and span_end > start for span_start, span_end in covered):
            continue
        hit = _rule_for_borrowed_subject(clause, subjects)
        if hit is None:
            continue
        rule, is_absent, subject_start = hit
        recognized_spans.append((start, end))
        if rule.name not in found_names:
            found_names.add(rule.name)
            carried.append((rule, _CarriedEvidence(start, end, text[subject_start:end]), is_absent))
    return carried, recognized_spans


def _rule_for_borrowed_subject(
    clause: str, subjects: list[tuple[str, int]]
) -> tuple[SymptomRule, bool, int] | None:
    predicate = LEADING_ADVERB_PATTERN.sub("", clause, count=1)
    for subject, subject_start in reversed(subjects):
        candidate = f"{subject} {predicate}"
        for rule in RULES:
            mention = _first_symptom_match(rule.mention, candidate)
            absent = _first_symptom_match(rule.absent, candidate)
            evidence = absent or mention
            if evidence is not None and evidence.start() == 0 and evidence.end() > len(subject) + 1:
                return rule, absent is not None, subject_start
    return None


def _subclause_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for boundary in SUBCLAUSE_SPLIT_PATTERN.finditer(text):
        # Keep the connective ending (e.g. "아프고") with the clause it belongs to.
        spans.append((start, boundary.start() + len(boundary.group(0).rstrip())))
        start = boundary.end()
    spans.append((start, len(text)))
    return spans


def _extract_profile(text: str) -> PatientProfileHints:
    """Age, sex, pregnancy, smoking and drinking the patient said about themself."""

    def own(pattern: re.Pattern[str]) -> re.Match[str] | None:
        # "남편이 담배를 피워요", "아이가 5살이에요" are about someone else.
        return next(
            (match for match in pattern.finditer(text) if _other_person_for(text, match.start()) is None),
            None,
        )

    age_match = own(AGE_PATTERN)
    age = next((int(value) for value in age_match.groups() if value), None) if age_match else None
    sex_match = own(SEX_PATTERN)
    sex = None if sex_match is None else "female" if sex_match.group("female") else "male"

    def first_label(patterns: tuple[tuple[str, re.Pattern[str]], ...]) -> str | None:
        return next((label for label, pattern in patterns if own(pattern)), None)

    pregnancy = first_label(PREGNANCY_PATTERNS)
    if pregnancy and sex is None:
        sex = "female"
    return PatientProfileHints(
        age=age if age is not None and 0 <= age <= 130 else None,
        sex=sex,
        pregnancy=pregnancy,
        smoking=first_label(SMOKING_PATTERNS),
        drinking=first_label(DRINKING_PATTERNS),
    )


def _extract_medical_history(text: str) -> tuple[list[str], list[OtherPersonSymptom]]:
    """Return the patient's history and history said about other people ("엄마가 고혈압이 있어요")."""
    denied = {re.sub(r"\s+", " ", value) for value in MEDICAL_HISTORY_ABSENT_PATTERN.findall(text)}
    history: list[str] = []
    others: list[OtherPersonSymptom] = []

    def add(condition: str, match: re.Match[str]) -> None:
        person = _other_person_for(text, match.start())
        if person is None:
            if condition not in history:
                history.append(condition)
        elif all(item.person != person or item.symptom != condition for item in others):
            others.append(OtherPersonSymptom(person=person, symptom=condition, source_text=match.group(0).strip()))

    for match in MEDICAL_HISTORY_PATTERN.finditer(text):
        condition = re.sub(r"\s+", " ", match.group(1))
        if condition not in denied:
            add(condition, match)
    for match in DIAGNOSED_CONDITION_PATTERN.finditer(text):
        value = match.group(1)
        known = [item for item in history if value.startswith(item) or item.startswith(value)]
        if not known and not NOT_A_CONDITION_PATTERN.fullmatch(value):
            add(value, match)
    for match in SURGERY_PATTERN.finditer(text):
        add(f"{match.group(1)} {match.group(2)}", match)
    for match in HIGH_READING_PATTERN.finditer(text):
        add(f"{match.group(1)} 높음", match)
    for match in WEAK_ORGAN_PATTERN.finditer(text):
        add(f"{match.group(1)} 질환", match)
    for match in ADMISSION_PATTERN.finditer(text):
        if not NOT_A_CONDITION_PATTERN.fullmatch(match.group(1)):
            add(f"{match.group(1)}(입원)", match)
    return history, others
