// Rule-based reading of a patient's words into symptoms, medicines, allergies, history and basic information.
// Runs on the phone itself, so the app needs no server (2026-10-15). It started as a line-for-line port of the
// Python rules (apps/api/app/services/intake_extractor.py, removed after the port; see Git history) and gives the same
// result for every sentence in golden.json (intake.test.ts). The rules are changed only here.

export type SymptomObservation = {
  name: string;
  status: "present" | "absent" | "uncertain";
  body_site: string | null;
  onset: string | null;
  onset_date: string | null;
  severity: string | null;
  frequency: string | null;
  trend: "improving" | "worsening" | "unchanged" | null;
  source_text: string;
};

export type OtherPersonSymptom = { person: string; symptom: string; source_text: string };

export type PatientProfileHints = {
  age: number | null;
  sex: "female" | "male" | null;
  pregnancy: "yes" | "no" | "unknown" | null;
  smoking: "current" | "former" | "never" | null;
  drinking: "yes" | "no" | null;
};

export type IntakeExtraction = {
  symptoms: SymptomObservation[];
  medications: string[];
  allergies: string[];
  medical_history: string[];
  others_symptoms: OtherPersonSymptom[];
  profile: PatientProfileHints;
  unrecognized_fragments: string[];
  needs_user_confirmation: boolean;
};

// A small layer over RegExp with the Python re calls the rules were written with: search, match at a position,
// fullmatch, finditer over a window, findall, sub and split.
type Match = {
  text: string;
  start: number;
  end: number;
  groups: (string | undefined)[];
  named: Record<string, string | undefined>;
  pattern: Pat;
};

class Pat {
  readonly source: string;
  private readonly first: RegExp;
  private readonly sticky: RegExp;
  private readonly whole: RegExp;

  constructor(source: string) {
    this.source = source;
    this.first = new RegExp(source);
    this.sticky = new RegExp(source, "y");
    this.whole = new RegExp(`^(?:${source})$`);
  }

  private wrap(found: RegExpExecArray | null): Match | null {
    if (!found) return null;
    return {
      text: found[0],
      start: found.index,
      end: found.index + found[0].length,
      groups: [...found],
      named: found.groups ?? {},
      pattern: this,
    };
  }

  search(text: string): Match | null {
    return this.wrap(this.first.exec(text));
  }

  /** Python's pattern.match(text, pos): only at pos, though lookbehind still sees what comes before it. */
  match(text: string, pos = 0): Match | null {
    this.sticky.lastIndex = pos;
    return this.wrap(this.sticky.exec(text));
  }

  fullmatch(text: string): Match | null {
    return this.wrap(this.whole.exec(text));
  }

  /** Python's pattern.finditer(text, pos, endpos): the text ends at endpos, matches start from pos. */
  finditer(text: string, pos = 0, endpos = text.length): Match[] {
    const searched = endpos < text.length ? text.slice(0, endpos) : text;
    const every = new RegExp(this.source, "g");
    every.lastIndex = pos;
    const found: Match[] = [];
    for (let next = every.exec(searched); next; next = every.exec(searched)) {
      found.push(this.wrap(next)!);
      if (next[0] === "") every.lastIndex += 1;
    }
    return found;
  }

  /** Python's findall for a pattern with one group: that group's text ("" when it did not take part). */
  findall(text: string): string[] {
    return this.finditer(text).map((found) => (found.groups.length > 1 ? found.groups[1] ?? "" : found.text));
  }

  sub(text: string, replacement: string | ((found: Match) => string), count = 0): string {
    let done = 0;
    return text.replace(new RegExp(this.source, "g"), (...args) => {
      const offset = args.findIndex((value) => typeof value === "number");
      const whole = args[0] as string;
      if (count && done >= count) return whole;
      done += 1;
      const groups = args.slice(0, offset) as (string | undefined)[];
      // "$1" in a replacement string is that group, as "\1" is in Python.
      if (typeof replacement === "string") return replacement.replace(/\$(\d)/g, (_, index) => groups[Number(index)] ?? "");
      const named = typeof args[args.length - 1] === "object" ? args[args.length - 1] as Record<string, string> : {};
      const start = args[offset] as number;
      return replacement({ text: whole, start, end: start + whole.length, groups, named, pattern: this });
    });
  }

  split(text: string): string[] {
    return text.split(this.first);
  }
}

const compiled = new Map<string, Pat>();

function pat(source: string): Pat {
  let found = compiled.get(source);
  if (!found) {
    found = new Pat(source);
    compiled.set(source, found);
  }
  return found;
}

const search = (source: string, text: string) => pat(source).search(text);
const matchStart = (source: string, text: string) => pat(source).match(text);
const fullmatch = (source: string, text: string) => pat(source).fullmatch(text);
const sub = (source: string, replacement: string, text: string) => pat(source).sub(text, replacement);

/** The text before the first match: Python's pattern.split(text, maxsplit=1)[0]. */
function beforeFirst(pattern: Pat, text: string): string {
  const found = pattern.search(text);
  return found ? text.slice(0, found.start) : text;
}

function rstripChars(text: string, characters: string): string {
  let end = text.length;
  while (end > 0 && characters.includes(text[end - 1])) end -= 1;
  return text.slice(0, end);
}

type Span = [number, number];
const sameSpan = (a: Span, b: Span) => a[0] === b[0] && a[1] === b[1];
const compareSpans = (a: Span, b: Span) => a[0] - b[0] || a[1] - b[1];

function uniqueSortedSpans(spans: Span[]): Span[] {
  const seen = new Map(spans.map((span) => [`${span[0]},${span[1]}`, span]));
  return [...seen.values()].sort(compareSpans);
}

/** The first item with the smallest key, like Python's min(items, key=...). */
function minBy<T>(items: T[], key: (item: T) => number[]): T {
  let best = items[0];
  let bestKey = key(best);
  for (const item of items.slice(1)) {
    const itemKey = key(item);
    const index = itemKey.findIndex((value, at) => value !== bestKey[at]);
    if (index >= 0 && itemKey[index] < bestKey[index]) {
      best = item;
      bestKey = itemKey;
    }
  }
  return best;
}

/** The first item with the largest key, like Python's max(items, key=...). */
function maxBy<T>(items: T[], key: (item: T) => number): T {
  let best = items[0];
  for (const item of items.slice(1)) if (key(item) > key(best)) best = item;
  return best;
}

type Rule = { name: string; mention: Pat; absent: Pat; bodySite: string | null };

function rule(name: string, mention: Pat, absent: Pat, bodySite: string | null = null): Rule {
  return { name, mention, absent, bodySite };
}

const INTENSITY_WORD = (
    String.raw`(?:아주|매우|너무|많이|조금|약간|심하게|살짝|계속|자꾸|되게|엄청|진짜|정말|좀|막|` +
    String.raw`살살|콕콕|쿡쿡|꾹꾹|구구|찌릿찌릿|찌릿|욱신욱신|욱신|지끈지끈|지끈|따끔따끔|뻐근하게|찌르듯이?|` +
    // How bad it is, said between the body part and the verb: "배가 참을 만하게 아파요".
    String.raw`데굴데굴|참을\s*만하게|견딜\s*만하게|죽을\s*(?:것\s*)?같이|미칠\s*(?:것\s*)?같이|` +
    String.raw`(?:참을\s*만한|견딜\s*만한|구를|죽을|미칠|못\s*참을|잠을\s*못\s*잘)\s*(?:정도로|만큼)|` +
    String.raw`심하(?:지는|진|지)\s*않(?:은데|지만|고))`
);
const INTENSITY_PHRASE = String.raw`(?:${INTENSITY_WORD}\s*)*`;
const IMPROVEMENT_PHRASE = (
    String.raw`(?:(?:조금|좀|많이|전보다)\s*)?` +
    String.raw`(?:괜찮아졌|나아졌|호전됐|좋아졌|덜해졌|줄었)`
);
// "배가 좀 나아졌어요", "머리가 더 심해졌어": a body part with how it changed names the pain there.
const CHANGE_PHRASE = (
    String.raw`(?:${IMPROVEMENT_PHRASE}|(?:(?:더|점점|많이|훨씬)\s*)?(?:심해졌|악화됐|나빠졌))`
);
const RESOLVED_STATE = (
    String.raw`(?:(?:완전히\s*)?(?:사라졌|없어졌|멈췄|가라앉았)|` +
    String.raw`(?:다|완전히)\s*(?:나았|괜찮아졌|좋아졌))`
);
const NOW_ADVERB = String.raw`(?:(?:이제는?|이젠|지금은|현재는)\s*)?`;
const PARTICLE = String.raw`(?:은|는|이|가|도|을|를)?`;
const JOINT_PART = String.raw`무릎|어깨|발목|손목|팔꿈치|고관절|골반|손가락\s*관절|손가락|발가락|턱관절|턱|관절`;
const ABSENT_ENDING = String.raw`${NOW_ADVERB}(?:없|${RESOLVED_STATE})`;
const NOT_PAINFUL = String.raw`(?:(?:더\s*이상\s*)?안\s*(?:아프|아파|아픈)|아프지(?:는|도)?\s*않|아프진\s*않)`;
const INLINE_ONSET = (
    String.raw`(?<![가-힣A-Za-z0-9])(?:어젯밤(?:부터)?|처음(?:엔|에는|에)|` +
    String.raw`(?:오늘|어제|그제|그저께|엊그제)\s*` +
    String.raw`(?:아침|점심|저녁|밤|새벽)(?:부터)?|` +
    String.raw`(?:오늘|어제|그제|그저께|엊그제)(?:부터)?|` +
    String.raw`(?:하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘)` +
    String.raw`(?:\s*(?:전부터|전|동안|째))?|` +
    String.raw`(?:\d+|일|이|삼|사|오|육|칠|팔|구|십)\s*` +
    String.raw`(?:시간|일|주|개월|달)(?:\s*(?:전부터|전|동안|째))?)`
);


const RULES: Rule[] = [
    rule(
        "두통",
        pat(
            String.raw`머리(?:랑|와|하고)\s*(?:배|복부|속)(?:가|는|도)?\s*` +
            String.raw`(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}(?:아프|아파|아팠|아픈)|` +
            String.raw`두통|머리\s*통증|머리(?:가|는|도|야)?\s*(?:${INLINE_ONSET}\s*)?` +
            String.raw`(?:같이\s*|함께\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|지끈|욱신|띵)|` +
            String.raw`(?:두통|머리)(?:이|가|은|는|도)?\s*${CHANGE_PHRASE}`
        ),
        pat(
            String.raw`(?:두통|머리\s*통증)(?:은|이|도)?\s*${NOW_ADVERB}(?:없|아니)|` +
            String.raw`머리(?:가|는|도)?\s*${NOW_ADVERB}(?:(?:더\s*이상\s*)?안\s*(?:아프|아파|아픈)|아프지\s*않)|` +
            String.raw`(?:두통|머리\s*통증)(?:은|이|가|는|도)?\s*${NOW_ADVERB}${RESOLVED_STATE}`
        ),
        "머리",
    ),
    rule(
        "발열",
        pat(
            String.raw`고열|미열|발열|` +
            // Temperature alone ("체온이 38.5도까지 올랐어요"): a fever from 37.5 up. A normal temperature is not
            // turned into "no fever"; only what the patient said about fever is recorded as absent.
            String.raw`체온(?:이|은|도|가|을|를)?\s*(?:[가-힣]+\s*){0,3}(?:37\.[5-9]|3[89](?:\.\d)?|4[0-2](?:\.\d)?)\s*(?:도|度|°|℃)|` +
            String.raw`(?<![가-힣])열(?=\s*$|이|은|도|과|이랑|랑|하고|까지|감|나|났|있|오르|올라|\s+(?:나|났|있|오르|올라|조금|좀|많이))` +
            String.raw`(?:이|은|도)?\s*(?:나|났|오르|있)?`
        ),
        pat(
            String.raw`(?:고열|미열|발열|열)(?:은|이|도)?\s*${NOW_ADVERB}(?:없|안\s*나|나지\s*않|내렸|${RESOLVED_STATE})`
        ),
    ),
    rule(
        "기침",
        pat(String.raw`기침(?:이|을|은|도)?\s*(?:나|났|해|했|하|심하|심했|계속)?`),
        pat(
            String.raw`기침(?:은|이|도|을)?\s*${NOW_ADVERB}(?:없|안\s*(?:나|해|하)|나지\s*않|하지\s*않|${RESOLVED_STATE})`
        ),
    ),
    rule(
        "호흡곤란",
        pat(
            String.raw`숨(?:이|은|도)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}(?:차|가빠|가쁘|가쁜|막혀|막히)|` +
            String.raw`숨(?:을)?\s*헐떡|` +
            String.raw`숨(?:을)?\s*쉬기(?:가)?\s*(?:힘들|어렵|어려|${IMPROVEMENT_PHRASE})|` +
            String.raw`숨쉬기가\s*(?:전보다\s*)?편해졌|` +
            String.raw`호흡곤란(?:이|은|도)?\s*(?:${IMPROVEMENT_PHRASE})?|` +
            String.raw`숨찬\s*증상(?:이|은|도)?\s*${IMPROVEMENT_PHRASE}`
        ),
        pat(
            String.raw`숨(?:은|이)?\s*${NOW_ADVERB}(?:안\s*차|차지\s*않)|` +
            String.raw`숨\s*(?:쉬는\s*(?:것|건|거|데)|쉬기)(?:은|는|도|가|에)?\s*${NOW_ADVERB}(?:괜찮(?!아졌)|문제\s*없|불편하지\s*않)|` +
            String.raw`(?:호흡곤란|숨찬\s*증상)(?:은|이|도)?\s*${NOW_ADVERB}(?:없|${RESOLVED_STATE})`
        ),
    ),
    rule(
        "가슴 답답함",
        pat(
            String.raw`가슴(?:이|은|만|도)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:답답|조이|조여|눌리)|흉부(?:가|는|만|도)?\s*(?:답답|압박)`
        ),
        pat(
            String.raw`가슴(?:이|은)?\s*${NOW_ADVERB}(?:안\s*답답|답답하지\s*않)|` +
            String.raw`(?:가슴\s*답답함|흉부\s*압박)(?:은|이|도)?\s*${NOW_ADVERB}${RESOLVED_STATE}`
        ),
        "가슴",
    ),
    rule(
        "복통",
        pat(
            String.raw`머리(?:랑|와|하고)\s*(?:배|복부|속)(?:가|는|도)?\s*` +
            String.raw`(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}(?:아프|아파|아팠|아픈)|` +
            String.raw`(?:복통|(?<![가-힣])배)(?:가|는|도)?\s*${CHANGE_PHRASE}|` +
            String.raw`(?:배|복부|속)(?:랑|과|하고)\s*머리(?:가|는|도)?\s*` +
            String.raw`(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}(?:아프|아파|아팠|아픈)|` +
            String.raw`(?:배|복부|속|명치|옆구리)(?:이|가|는|도|야)?\s*(?:${INLINE_ONSET}\s*)?` +
            String.raw`${INTENSITY_PHRASE}(?:아프|아파|아팠|아픈|쑤시|쑤셔|쑤신|뒤틀|꼬여|꼬이)|` +
            // "폭통": on-device STT's usual spelling of "복통".
            String.raw`복통|폭통|(?:배|복부|명치|옆구리)\s*통증|배탈|위경련|위통`
        ),
        pat(
            String.raw`(?:배|복부|속)(?:이|가|는|도)?\s*${NOW_ADVERB}(?:(?:더\s*이상\s*)?안\s*(?:아프|아파|아픈)|아프지\s*않)|` +
            String.raw`복통(?:은|이|도)?\s*${NOW_ADVERB}(?:없|${RESOLVED_STATE})|` +
            String.raw`(?:배|복부|속)\s*통증(?:은|이|도)?\s*${NOW_ADVERB}(?:없|${RESOLVED_STATE})`
        ),
        "복부",
    ),
    rule(
        "구토",
        pat(
            String.raw`구토\s*횟수(?:가|는|도)?[^,.!?。]{0,20}(?:줄었|늘었)|` +
            String.raw`구토|토(?:를|가)?\s*(?:했|해|하|했었)`
        ),
        pat(
            String.raw`구토(?:는|가|도)?\s*${NOW_ADVERB}(?:없|${RESOLVED_STATE})|` +
            String.raw`토(?:는|를)?\s*${NOW_ADVERB}(?:안\s*했|하지\s*않)|` +
            String.raw`토한\s*적(?:은|도|이)?\s*없|` +
            String.raw`구토\s*증상(?:은|이|도)?\s*${NOW_ADVERB}${RESOLVED_STATE}`
        ),
    ),
    rule(
        "흉통",
        pat(
            String.raw`흉통|(?:가슴|흉부)\s*통증|가슴(?:이|은|도)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|찌르|찌릿|콕콕|쑤시|쑤셔|쥐어짜)`
        ),
        pat(
            String.raw`(?:흉통|(?:가슴|흉부)\s*통증)${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`가슴(?:은|이|도)?\s*${NOW_ADVERB}${NOT_PAINFUL}`
        ),
        "가슴",
    ),
    rule(
        "인후통",
        pat(
            String.raw`인후통|목\s*통증|목감기|목(?:이|은|도)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|따끔|따끈|따가|따갑|칼칼|부었|부어|붓)|` +
            String.raw`(?:인후통|목)(?:이|은|도)?\s*${CHANGE_PHRASE}|` +
            String.raw`침(?:을)?\s*삼키기(?:가)?\s*(?:힘들|어렵|아프)|침(?:을)?\s*삼킬\s*때(?:마다)?\s*(?:아프|아파|따끔)`
        ),
        pat(
            String.raw`인후통${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`목(?:은|이|도)?\s*${NOW_ADVERB}${NOT_PAINFUL}`
        ),
        "목",
    ),
    rule(
        "콧물",
        pat(String.raw`콧물|코감기|코(?:를|가)?\s*(?:훌쩍|흘러|줄줄|풀)`),
        pat(
            String.raw`콧물${PARTICLE}\s*${NOW_ADVERB}(?:없|안\s*나|나지\s*않|멈췄|${RESOLVED_STATE})`
        ),
        "코",
    ),
    rule(
        "코막힘",
        // "콧막힘", "코마킹", "코마킨드": STT spellings of "코막힘".
        pat(String.raw`코\s*막힘|콧\s*막힘|코마킹|코마킨|코(?:가|도)?\s*(?:꽉\s*)?[막박](?:혀|히|혔|힌)`),
        pat(
            String.raw`코\s*막힘${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`코(?:는|가|도)?\s*${NOW_ADVERB}(?:안\s*막|막히지\s*않)`
        ),
        "코",
    ),
    rule(
        "가래",
        pat(String.raw`가래`),
        pat(
            String.raw`가래${PARTICLE}\s*${NOW_ADVERB}(?:없|안\s*(?:나|끓)|나오지\s*않|${RESOLVED_STATE})`
        ),
    ),
    rule(
        "오한",
        pat(String.raw`오한|으슬으슬|한기|춥고\s*떨|몸이\s*(?:덜덜\s*)?떨`),
        pat(String.raw`(?:오한|한기)${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "근육통",
        pat(
            String.raw`근육통|몸살|(?:온몸|몸|근육|팔다리)(?:이|가|은|도)?\s*${INTENSITY_PHRASE}` +
            String.raw`(?:쑤시|쑤셔|쑤신|결리|결려|아프|아파|아픈)`
        ),
        pat(
            String.raw`(?:근육통|몸살)${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`(?:온몸|몸|근육)(?:은|이|도)?\s*${NOW_ADVERB}(?:${NOT_PAINFUL}|안\s*쑤|쑤시지\s*않)`
        ),
    ),
    rule(
        "요통",
        pat(
            String.raw`(?:요통|허리)(?:가|는|도)?\s*${CHANGE_PHRASE}|` +
            String.raw`요통|허리\s*통증|허리(?:\s*(?:아래|위|밑)\s*쪽?(?:이|은|도|에)?)?(?:가|는|도)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|쑤시|쑤셔|결리|결려|뻐근|당기|당겨|삐끗)`
        ),
        pat(
            String.raw`(?:요통|허리\s*통증)${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`허리(?:는|가|도)?\s*${NOW_ADVERB}${NOT_PAINFUL}`
        ),
        "허리",
    ),
    rule(
        "어지러움",
        pat(String.raw`어지러|어지럽|어지럼|현기증|핑\s*(?:돌|돈)|빙빙\s*(?:돌|돈)`),
        pat(
            String.raw`(?:어지럼증?|현기증)${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`${NOW_ADVERB}안\s*어지러|어지럽지\s*않`
        ),
    ),
    rule(
        "메스꺼움",
        pat(String.raw`[메매]스꺼|[메매]스껍|메슥|미식거|울렁|구역질|구역감|헛구역|토할\s*(?:것\s*)?같`),
        pat(
            String.raw`(?:메스꺼움|구역감|구역질|울렁거림)${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`메스껍지\s*않|안\s*메스꺼|울렁거리지\s*않`
        ),
    ),
    rule(
        "설사",
        pat(String.raw`설사|(?<!소)(?:대변|변)(?:이|을|도)?\s*(?:묽|물\s*같)|물\s*같은\s*변`),
        pat(
            String.raw`설사${PARTICLE}\s*${NOW_ADVERB}(?:없|안\s*(?:했|해|하)|하지\s*않|멈췄|${RESOLVED_STATE})|` +
            String.raw`설사(?:를\s*)?한\s*적(?:은|도|이)?\s*없`
        ),
    ),
    rule(
        "변비",
        pat(String.raw`변비|(?<!소)(?:대변|변)(?:을|이|도)?\s*(?:잘\s*)?(?:못\s*(?:봤|봐|보|본)|안\s*나와|안\s*나오)`),
        pat(String.raw`변비${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "발진",
        pat(
            String.raw`발진|두드러기|피부(?:가|에|도)?\s*(?:\S+\s*)?(?:빨갛|붉|오돌토돌|뭐가\s*(?:났|올라))|` +
            String.raw`(?:몸|피부|팔|다리|얼굴)(?:이|가|에)?\s*(?:빨갛게|붉게)\s*(?:올라|돋)`
        ),
        pat(String.raw`(?:발진|두드러기)${PARTICLE}\s*${ABSENT_ENDING}`),
        "피부",
    ),
    rule(
        "피로",
        pat(
            String.raw`피곤|피로|기운(?:이|도)?\s*없|(?:몸에|온몸에)\s*힘(?:이)?\s*없|기력(?:이|도)?\s*없|무기력|나른|` +
            String.raw`몸(?:이)?\s*(?:천근만근|무거|무겁)|녹초|지쳐|지친다`
        ),
        pat(
            String.raw`(?:피로감?|피곤함)${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`안\s*피곤|피곤하지\s*않`
        ),
    ),
    rule(
        "두근거림",
        pat(
            String.raw`두근|벌렁|심계항진|심장(?:이)?\s*(?:너무\s*)?(?:빨리|빠르게|불규칙하게|쿵쾅)`
        ),
        pat(
            String.raw`(?:두근거림|심계항진)${PARTICLE}\s*${ABSENT_ENDING}|안\s*두근|두근거리지\s*않`
        ),
        "가슴",
    ),
    rule(
        "저림",
        pat(String.raw`저려|저리|저림|저린|저릿|쥐(?:가)?\s*(?:나|났)|감각(?:이)?\s*(?:없|둔하|둔해|무뎌)`),
        pat(String.raw`저림${PARTICLE}\s*${ABSENT_ENDING}|저리지\s*않|안\s*저려|안\s*저리`),
    ),
    rule(
        "소화불량",
        pat(
            String.raw`소화불량|소화(?:가)?\s*(?:잘\s*)?안\s*(?:돼|되|된|됐)|체했|체한|체기|체해|` +
            String.raw`더부룩|트림`
        ),
        pat(
            String.raw`(?:소화불량|체기)${PARTICLE}\s*${ABSENT_ENDING}|소화(?:는|도)?\s*${NOW_ADVERB}잘\s*(?:돼|되)`
        ),
        "복부",
    ),
    rule(
        "속쓰림",
        pat(
            String.raw`속쓰림|(?:속|가슴|명치|윗배|위)(?:이|가)?\s*${INTENSITY_PHRASE}(?:쓰려|쓰리|쓰린|쓰림|타는)|` +
            String.raw`신물(?:이)?\s*(?:올라|넘어)|위산\s*역류`
        ),
        pat(
            String.raw`속쓰림${PARTICLE}\s*${ABSENT_ENDING}|(?:속|위)(?:은|이|는|도)?\s*${NOW_ADVERB}(?:안\s*쓰려|쓰리지\s*않)`
        ),
        "복부",
    ),
    rule(
        "식욕부진",
        pat(
            String.raw`식욕부진|식욕(?:이|도)?\s*(?:없|떨어|뚝)|입맛(?:이|도)?\s*(?:없|떨어|뚝|통\s*없)|` +
            String.raw`밥(?:을|이)?\s*(?:잘\s*)?(?:못\s*먹|안\s*넘어가|먹기\s*싫)`
        ),
        pat(
            String.raw`(?:식욕|입맛)(?:은|이|도)?\s*${NOW_ADVERB}(?:괜찮|있|좋|돌아)|식욕부진${PARTICLE}\s*${ABSENT_ENDING}`
        ),
    ),
    rule(
        "불면",
        pat(
            String.raw`불면|잠(?:을|이)?\s*(?:잘\s*)?(?:못\s*(?:자|잤|잔|들)|안\s*(?:와|온|오)|설쳐|설쳤)|` +
            String.raw`자다가\s*(?:자꾸\s*|계속\s*)?깨`
        ),
        pat(String.raw`잠(?:은|을|도)?\s*${NOW_ADVERB}잘\s*(?:자|잤|자요)|불면${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "부종",
        pat(
            String.raw`부종|붓기|부기(?=가|는|도|\s|$)|(?:다리|발|발목|얼굴|손|손가락|눈두덩|눈|입술|몸)(?:이|가|도)?\s*(?:퉁퉁\s*|많이\s*)?` +
            String.raw`(?:부었|부어|붓|부은)`
        ),
        pat(String.raw`(?:부종|붓기|부기)${PARTICLE}\s*${NOW_ADVERB}(?:없|빠졌|가라앉았|${RESOLVED_STATE})`),
    ),
    rule(
        "귀 통증",
        pat(
            String.raw`귀(?:가|는|도)?\s*${CHANGE_PHRASE}|` +
            String.raw`귀\s*통증|귀(?:가|는|도)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|찌르|먹먹|욱신)`
        ),
        pat(String.raw`귀(?:는|가|도)?\s*${NOW_ADVERB}${NOT_PAINFUL}|귀\s*통증${PARTICLE}\s*${ABSENT_ENDING}`),
        "귀",
    ),
    rule(
        "눈 통증",
        pat(
            String.raw`눈\s*통증|눈(?:이|은|도)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|따가|따갑|시려|시리|쑤셔)`
        ),
        pat(String.raw`눈(?:은|이|도)?\s*${NOW_ADVERB}${NOT_PAINFUL}|눈\s*통증${PARTICLE}\s*${ABSENT_ENDING}`),
        "눈",
    ),
    rule(
        "치통",
        pat(
            String.raw`(?:치통|(?<![가-힣])이|이빨|치아)(?:가|이|는|도)?\s*${CHANGE_PHRASE}|` +
            String.raw`치통|(?:(?<![가-힣])이|이빨|치아|잇몸|어금니)(?:가|이|는|도)?\s*${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|시려|시리|욱신|쑤셔)`
        ),
        pat(
            String.raw`치통${PARTICLE}\s*${ABSENT_ENDING}|(?:이빨|치아|잇몸)(?:은|이|는|도)?\s*${NOW_ADVERB}${NOT_PAINFUL}`
        ),
        "치아",
    ),
    rule(
        "식은땀",
        pat(String.raw`식은땀|(?<![가-힣])땀(?:이|을|도)?\s*(?:많이\s*|비\s*오듯\s*|줄줄\s*)?(?:나|났|흘|흐르)`),
        pat(
            String.raw`식은땀${PARTICLE}\s*${ABSENT_ENDING}|(?<![가-힣])땀(?:은|이|도)?\s*${NOW_ADVERB}(?:안\s*나|나지\s*않)`
        ),
    ),
    rule(
        "가려움",
        pat(String.raw`가려워|가렵|가려움|가려운|간지러|간지럽|간지럼|소양감`),
        pat(
            String.raw`(?:가려움|간지럼|소양감)${PARTICLE}\s*${ABSENT_ENDING}|안\s*가려|가렵지\s*않|간지럽지\s*않`
        ),
    ),
    rule(
        "시야 이상",
        pat(
            String.raw`시야|복시|(?:눈|눈앞|앞)(?:이|가)?\s*(?:자꾸\s*|좀\s*)?(?:침침|흐릿|흐려|뿌옇|뿌얘|캄캄|깜깜|번쩍)|` +
            String.raw`(?:잘\s*)?안\s*보여|겹쳐\s*보|두\s*개로\s*보|(?:[흐허]릿하게|흐리게|뿌옇게)\s*보`
        ),
        pat(
            String.raw`(?:시야\s*이상|복시)${PARTICLE}\s*${ABSENT_ENDING}|(?:눈|시력)(?:은|도)?\s*${NOW_ADVERB}(?:괜찮|잘\s*보)`
        ),
        "눈",
    ),
    rule(
        "떨림",
        pat(
            String.raw`수전증|(?:손|팔|다리|손발|입술|턱|몸)(?:이|가|도)?\s*(?:덜덜\s*|부들부들\s*|계속\s*|자꾸\s*)?` +
            String.raw`(?:떨려|떨리|떨림|떨린)`
        ),
        pat(String.raw`떨림${PARTICLE}\s*${ABSENT_ENDING}|(?:안\s*떨|떨리지\s*않)`),
    ),
    rule(
        "이명",
        pat(String.raw`이명|귀(?:에서)?\s*(?:삐|윙|웅웅|소리(?:가)?\s*(?:나|들려))|귀(?:가)?\s*울려|귀(?:가)?\s*울리`),
        pat(String.raw`이명${PARTICLE}\s*${ABSENT_ENDING}`),
        "귀",
    ),
    rule(
        "코피",
        pat(String.raw`코피|코에서\s*피`),
        pat(String.raw`코피${PARTICLE}\s*${NOW_ADVERB}(?:없|안\s*나|멈췄|${RESOLVED_STATE})`),
        "코",
    ),
    rule(
        "객혈",
        pat(
            String.raw`객혈|각혈|(?:기침|가래)(?:할\s*때|하면|에|에서)?\s*(?:피|핏덩이)(?:가|도)?\s*(?:섞|나|묻)|` +
            String.raw`피(?:가)?\s*섞인\s*(?:가래|기침)`
        ),
        pat(String.raw`(?:객혈|각혈)${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "토혈",
        pat(String.raw`토혈|피(?:를)?\s*토했|피(?:를)?\s*토해|토(?:에|한\s*것에)\s*피|피가\s*섞인\s*구토|토할\s*때\s*피`),
        pat(String.raw`토혈${PARTICLE}\s*${ABSENT_ENDING}|피(?:는|를|도)?\s*(?:안\s*토(?:했|해)|토하지\s*않)`),
    ),
    rule(
        "혈변",
        pat(
            String.raw`혈변|(?:대변|(?<!소)변)(?:에|에서)\s*피|피(?:가)?\s*섞인\s*(?:대변|(?<!소)변)|` +
            String.raw`(?:검은|까만|짜장\s*같은)\s*(?:대변|변)|(?:대변|변)(?:이)?\s*(?:검게|까맣게)`
        ),
        pat(String.raw`혈변${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "혈뇨",
        pat(String.raw`혈뇨|피오줌|(?:소변|오줌)(?:에|에서|이)?\s*(?:피|빨갛|붉)`),
        pat(String.raw`혈뇨${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "배뇨통",
        pat(
            String.raw`배뇨통|(?:소변|오줌)(?:을)?\s*(?:볼|눌)\s*때\s*(?:마다\s*)?(?:아프|아파|따끔|찌릿|화끈|쓰라)`
        ),
        pat(String.raw`배뇨통${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "빈뇨",
        pat(String.raw`빈뇨|(?:소변|오줌)(?:을|이|도)?\s*(?:너무\s*)?자주|화장실(?:을|에)?\s*(?:너무\s*)?자주\s*가`),
        pat(String.raw`빈뇨${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "기절",
        pat(String.raw`기절|실신|정신(?:을)?\s*잃|의식(?:을)?\s*잃|쓰러졌|쓰러진\s*적`),
        pat(String.raw`(?:기절|실신)(?:한\s*적)?${PARTICLE}\s*${ABSENT_ENDING}|쓰러진\s*적(?:은|도)?\s*없`),
    ),
    rule(
        "마비",
        pat(
            String.raw`마비|(?:팔|다리|한쪽|얼굴|손|발|팔다리)(?:이|에|가|도)?\s*(?:갑자기\s*)?` +
            String.raw`(?:힘이\s*(?:빠|없|안\s*들)|안\s*움직|움직이지\s*않)|얼굴(?:이)?\s*(?:한쪽으로\s*)?(?:처졌|돌아갔|비뚤어)`
        ),
        pat(String.raw`마비${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "말 어눌함",
        pat(String.raw`(?:말|발음)(?:이|을)?\s*(?:자꾸\s*|갑자기\s*)?(?:어눌|꼬여|꼬이|안\s*나와|이상해)|말하기(?:가)?\s*힘들`),
        pat(String.raw`(?:말|발음)(?:은|도)?\s*(?:괜찮|정상|또렷)`),
    ),
    rule(
        "쉰 목소리",
        pat(
            String.raw`쉰\s*목소리|목(?:이)?\s*쉬었|목(?:이)?\s*쉬어|목(?:이)?\s*잠겼|목소리(?:가)?\s*(?:쉬|변했|안\s*나|갈라)`
        ),
        pat(String.raw`목소리(?:는|도)?\s*(?:괜찮|정상)`),
        "목",
    ),
    rule(
        "체중 감소",
        pat(
            String.raw`체중(?:이)?\s*(?:줄|빠졌|감소)|몸무게(?:가)?\s*(?:줄|빠졌)|살(?:이)?\s*(?:많이\s*|갑자기\s*)?빠졌|` +
            String.raw`\d+\s*(?:킬로|kg)(?:가|나|이)?\s*(?:빠졌|줄었)`
        ),
        pat(String.raw`(?:체중|몸무게)(?:은|는|도)?\s*(?:그대로|변화\s*없|안\s*빠졌)`),
    ),
    rule(
        "경련",
        pat(String.raw`(?<!위)경련|발작|(?:몸|팔|다리)(?:이|가)?\s*(?:뻣뻣해지|뒤틀리)`),
        pat(String.raw`(?:경련|발작)${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "관절 통증",
        pat(
            String.raw`(?:관절통|${JOINT_PART})(?:이|가|은|는|도)?\s*${CHANGE_PHRASE}|` +
            String.raw`관절통|(?:${JOINT_PART})(?:이|가|은|는|도)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|쑤시|쑤셔|시큰|시려|결려|붓|부었)|` +
            String.raw`(?:${JOINT_PART})\s*통증`
        ),
        pat(
            String.raw`관절통${PARTICLE}\s*${ABSENT_ENDING}|(?:${JOINT_PART})(?:은|는|도)?\s*${NOW_ADVERB}${NOT_PAINFUL}`
        ),
        "관절",
    ),
    rule(
        "입안 통증",
        pat(
            String.raw`구내염|입병|(?:입안|입\s*안|혀|입천장)(?:이|가|은|는|도|에)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|따가|따갑|쓰라|헐었|헐어|헌\s|헐|뭐가\s*났)`
        ),
        pat(
            String.raw`(?:구내염|입병)${PARTICLE}\s*${ABSENT_ENDING}|(?:입안|혀)(?:은|는|도|이|가)?\s*${NOW_ADVERB}${NOT_PAINFUL}`
        ),
        "입안",
    ),
    rule(
        "재채기",
        pat(String.raw`재채기|채치기|재치기|채채기`),
        pat(String.raw`재채기${PARTICLE}\s*${ABSENT_ENDING}|재채기(?:는|도)?\s*안\s*(?:해|나)`),
    ),
    rule(
        "쌕쌕거림",
        // STT spells the same sound several ways ("쎅쎅" from the server model).
        pat(String.raw`쌕쌕|쎅쎅|색색\s*소리|숨(?:을)?\s*쉴\s*때\s*(?:휘파람|그르렁)\s*소리`),
        pat(String.raw`쌕쌕(?:거림|거리는\s*소리)?${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "배뇨 곤란",
        pat(
            String.raw`(?:소변|오줌)(?:이|을|도)?\s*(?:잘\s*)?(?:안\s*나와|안\s*나오|안\s*나온|못\s*(?:봤|봐|보|본)|` +
            String.raw`보기(?:가)?\s*(?:힘들|어렵)|찔끔|시원하게\s*안)`
        ),
        pat(String.raw`(?:소변|오줌)(?:은|도)?\s*(?:잘\s*)?(?:나와|나오고|봐요|보고)`),
    ),
    rule(
        "눈 충혈",
        pat(String.raw`충혈|눈(?:이|은|도)?\s*${INTENSITY_PHRASE}(?:빨개|빨갛|벌개|벌겋)`),
        pat(String.raw`충혈${PARTICLE}\s*${ABSENT_ENDING}`),
        "눈",
    ),
    rule(
        "생리통",
        pat(String.raw`생리통|(?:생리|월경)(?:할\s*때|\s*중에?|\s*때문에)?\s*(?:배가\s*)?(?:너무\s*|많이\s*|심하게\s*)?(?:아프|아파|아팠)`),
        pat(String.raw`생리통${PARTICLE}\s*${ABSENT_ENDING}`),
        "아랫배",
    ),
    rule(
        "복부 팽만",
        pat(String.raw`(?:배|아랫배)(?:가|에)?\s*(?:너무\s*|자꾸\s*)?(?:빵빵|땡땡)|가스(?:가)?\s*(?:자꾸\s*|많이\s*)?(?:차|찼|찬)|방귀(?:가|를)?\s*(?:너무\s*)?자주`),
        pat(String.raw`(?:복부\s*팽만|가스)${PARTICLE}\s*${ABSENT_ENDING}`),
        "복부",
    ),
    rule(
        "목 이물감",
        pat(String.raw`이물감|목(?:에|이)?\s*(?:뭐가|뭔가|무언가)?\s*걸린\s*(?:것|거)?\s*같|목(?:이)?\s*막힌\s*(?:것\s*)?같`),
        pat(String.raw`이물감${PARTICLE}\s*${ABSENT_ENDING}`),
        "목",
    ),
    rule(
        "눈 분비물",
        pat(String.raw`눈곱|눈물(?:이)?\s*(?:계속|자꾸|많이)\s*(?:나|흘러|흘)`),
        pat(String.raw`눈곱${PARTICLE}\s*${ABSENT_ENDING}`),
        "눈",
    ),
    rule(
        "목 결림",
        pat(String.raw`뒷목|목(?:이|덜미가)?\s*${INTENSITY_PHRASE}(?:뻐근|결려|결리|뻣뻣|안\s*돌아가)`),
        pat(String.raw`(?:뒷목|목)(?:은|도)?\s*${NOW_ADVERB}(?:괜찮|안\s*뻐근)`),
        "뒷목",
    ),
    rule(
        "손발 차가움",
        pat(String.raw`수족냉증|(?:손발|손|발)(?:이|가|도)?\s*(?:너무\s*|많이\s*|자주\s*)?(?:차가워|차가운|차요|차서|시려|시리|얼음)`),
        pat(String.raw`수족냉증${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "우울감",
        pat(String.raw`우울(?!증)|의욕(?:이)?\s*없|아무것도\s*하기\s*싫|기분(?:이)?\s*(?:계속\s*)?(?:가라앉|처져|처지|다운)`),
        pat(String.raw`우울(?:감|증)?${PARTICLE}\s*${ABSENT_ENDING}|우울하지\s*않`),
    ),
    rule(
        "불안감",
        pat(String.raw`불안(?!정)|초조|조마조마`),
        pat(String.raw`불안(?:감)?${PARTICLE}\s*${ABSENT_ENDING}|불안하지\s*않`),
    ),
    rule(
        "청력 저하",
        pat(String.raw`청력|난청|(?<![가-힣])잘\s*안\s*들(?:려|리)|(?:귀|소리|말)(?:가|이|도)?\s*(?:잘\s*)?안\s*들려|(?:귀|소리|말)(?:가|이|도)?\s*잘\s*안\s*들리`),
        pat(String.raw`(?:청력\s*저하|난청)${PARTICLE}\s*${ABSENT_ENDING}|(?:귀|소리)(?:는|도)?\s*잘\s*들려`),
        "귀",
    ),
    rule(
        "입마름",
        pat(String.raw`입마름|구갈|갈증|(?:입|입안|목)(?:이|가|도)?\s*(?:자주\s*|계속\s*|바짝\s*|너무\s*)*(?:말라|마르|마른|건조)`),
        pat(String.raw`(?:입마름|갈증)${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
];
const FREQUENCY_SYMPTOMS = new Set(["구토", "설사"]);
const SIDE_PATTERN = pat(String.raw`(오른쪽|왼쪽|양쪽|우측|좌측|오른|왼)(?:\s*편)?`);
const SIDE_NAMES: Record<string, string> = { 우측: "오른쪽", 오른: "오른쪽", 좌측: "왼쪽", 왼: "왼쪽" };
// Symptoms without a fixed body site that still happen somewhere: "왼쪽 팔이 저려요".
const PART_SYMPTOMS = new Set(["저림", "부종", "떨림", "마비", "가려움", "발진"]);
const PART_WORDS = String.raw`손발|손가락|발가락|손등|발등|손목|발목|손|발|팔다리|팔|다리|얼굴|입술|눈두덩|눈|등|온몸|몸|피부|턱|혀`;
// Words that name a narrower place than the rule's body site when they start the evidence.
const SITE_WORD_PATTERN = pat(
    String.raw`(?:아랫|윗|뒷|앞)?(?:배|머리)|명치|옆구리|${JOINT_PART}|가슴|허리|귀|눈|목`
);

const ONSET_PATTERN = pat(
    String.raw`(?<![가-힣A-Za-z0-9])(?:` +
    String.raw`(?:아까\s*)?(?:아침|점심|저녁)(?:\s*밥)?(?:을|를)?\s*먹고\s*(?:(?:나서|난\s*(?:뒤|후))(?:\s*부터)?|부터)|아까부터|` +
    String.raw`\d{1,2}\s*월\s*\d{1,2}\s*일(?:\s*(?:쯤|경))?(?:\s*부터)?|` +
    String.raw`(?:지난\s*주|저번\s*주|이번\s*주)\s*[월화수목금토일]요일(?:부터|쯤)?|` +
    String.raw`[월화수목금토일]요일(?:부터|쯤)?|` +
    String.raw`어젯밤(?:부터)?|` +
    String.raw`(?:오늘|어제|그제|그저께|엊그제)\s*` +
    String.raw`(?:아침|점심|저녁|밤|새벽)(?:부터)?|` +
    String.raw`(?:하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘|(?:\d+|일|이|삼|사|오|육|칠|팔|구|십)\s*일)` +
    String.raw`\s*전[,\s]*(?:아침|점심|저녁|밤|새벽)(?:부터)?|` +
    // "어제까지 설사했는데" says when it ended, not when it started.
    String.raw`(?:오늘|어제|그제|그저께|엊그제|방금|아침|점심|저녁|밤|새벽)(?!\s*까지)(?:부터)?|` +
    String.raw`(?:하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘)` +
    String.raw`(?!\s*에|\s*(?:\d+|한두|두세|서너|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*(?:번|회|차례))` +
    String.raw`(?:\s*(?:전부터|전|동안|째))?|` +
    String.raw`(?:일주일|한\s*주|두\s*주|한\s*달|두\s*달)(?!\s*에)` +
    String.raw`(?:\s*(?:전부터|전|동안|째))?|` +
    String.raw`(?:\d+|일|이|삼|사|오|육|칠|팔|구|십)\s*` +
    String.raw`(?:시간|일|주(?!일)|개월|달)(?!\s*에)(?:\s*(?:전부터|전|동안|째))?)`
);
const MILD_SEVERITY = (
    String.raw`참을\s*만|견딜\s*만|살짝|가볍게|약하게|그럭저럭|별로\s*안\s*심|심하(?:지는|진|지)\s*않`
);
const MODERATE_SEVERITY = String.raw`보통|중간\s*정도|적당히`;
const STRONG_SEVERITY = (
    String.raw`못\s*참|참기\s*(?:힘들|어렵)|견디기\s*(?:힘들|어렵)|죽을\s*(?:것\s*)?같|미칠\s*(?:것\s*)?같|` +
    String.raw`잠(?:을)?\s*못\s*잘\s*(?:정도|만큼)|(?:걷지도|움직이지도|아무것도)\s*못\s*할\s*(?:정도|만큼)|` +
    String.raw`데굴데굴|극심|엄청`
);
const SEVERITY_PATTERN = pat(
    String.raw`${MILD_SEVERITY}|${MODERATE_SEVERITY}|${STRONG_SEVERITY}|` +
    String.raw`매우\s*심(?:해|하|했)|너무\s*심(?:해|하|했)|심(?:해|하|했)|` +
    String.raw`아주|매우|너무|많이|조금|약간`
);
const PAIN_SCORE_PATTERN = pat(
    String.raw`(?:(?:고통(?:의\s*정도)?|통증|아픈\s*강도|아픈\s*정도|아픔|강도)(?:를|로|는|가)?\s*` +
    String.raw`(?:따지면|점수는?|정도는?)?\s*)?` +
    String.raw`(?:한\s*)?` +
    String.raw`(?:10\s*점\s*만점(?:에|에서)\s*\d{1,2}\s*점|` +
    String.raw`10\s*중(?:에|에서)?\s*\d{1,2}\s*(?:점|정도)?|` +
    String.raw`\d{1,3}\s*(?:점|정도))`
);
const FREQUENCY_PATTERN = pat(
    String.raw`(?:(?:하루(?:에)?|오늘|어제)\s*)?` +
    String.raw`(?:\d+|한두|두세|서너|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*` +
    String.raw`(?:번|회|차례)`
);
// "처음엔 하루 다섯 번 했는데 오늘은 두 번": the count now, said after the first one.
const FREQUENCY_NOW_PATTERN = pat(
    String.raw`(?:지금은|현재는|이제는?|오늘은)\s*(?:하루(?:에)?\s*)?` +
    String.raw`((?:\d+|한두|두세|서너|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*(?:번|회|차례))`
);
const TREND_PATTERN = pat(
    String.raw`(?<improving>(?:(?:조금|좀|많이|전보다|점점)\s*)?` +
    String.raw`(?:괜찮아졌|나아졌|호전됐|좋아졌|덜해졌|줄었|완화됐|편해졌))|` +
    String.raw`(?<worsening>(?:(?:더|훨씬|점점|많이)\s*)?` +
    String.raw`(?:심해졌|악화됐|나빠졌|더\s*아프|잦아졌|늘었))|` +
    String.raw`(?<unchanged>(?:그대로|비슷|여전|변화\s*없))`
);
const MEDICATION_NAME_PATTERN = pat(
    String.raw`((?:(?:알레르기|감기|비염|혈압|당뇨|진통|해열|소화|위장|고지혈증|콜레스테롤|갑상선|천식|수면|우울증)\s*약)|` +
    String.raw`(?:[가-힣A-Za-z0-9-]{2,20}(?:약|제)))` +
    String.raw`(?=(?:과|와|을|를|도|은|는)?(?:\s|$))`
);
const KNOWN_MEDICATION_PATTERN = pat(
    String.raw`타이레놀|아세트아미노펜|이부프로펜|애드빌|게보린|판피린|판콜(?:에이|에스)?|펜잘|부루펜|탁센|낙센|` +
    String.raw`아스피린|아목시실린|오구멘틴|세파클러|클래리스로마이신|지르텍|알레그라|코대원|시네츄라|` +
    String.raw`베아제|훼스탈|겔포스|개비스콘|스멕타|로페라마이드|넥시움|메트포르민|리피토|노바스크|` +
    String.raw`와파린|엘리퀴스|씬지로이드|신지로이드|프레드니솔론|인슐린|벤토린|심비코트|` +
    String.raw`테라플루|화이투벤|콜대원|이지엔6|까스활명수|활명수|후시딘|마데카솔`
);
// Generic drug name endings, e.g. 세팔렉신 is not listed but 아지트로마이신 ends in 마이신.
const DRUG_NAME_PATTERN = pat(
    String.raw`(?<![가-힣])[가-힣]{2,10}(?:마이신|실린|프로펜|스타틴|사르탄|프라졸|디핀|세핀|파린|플록사신)`
);
// A name we do not know, followed by a pill dose: "테렌을 500mg을 먹었고" (STT's "타이레놀"). Kept as said, not
// replaced by a similar-sounding medicine, so the patient can correct it on the review screen.
const UNKNOWN_DOSED_MEDICATION_PATTERN = pat(
    String.raw`(?<![가-힣A-Za-z])([가-힣A-Za-z]{2,10}?)(?:을|를|은|는|도)?\s*` +
    String.raw`(?=\d+(?:\.\d+)?\s*(?:mg|밀리그램|mcg|정(?!도)|알(?!레)|캡슐)|(?:한|두|세|네)\s*(?:정(?!도)|알(?!레)|캡슐))`
);
// STT's many spellings of "타이레놀" with no dose after them ("타이륜을 먹었어요", "타이레노 먹었어요"), kept as said.
// ponytail: Tylenol only, the one name STT kept garbling in tests; add others when recordings show them.
const TYLENOL_SOUNDALIKE_PATTERN = pat(
    String.raw`(?<![가-힣])타이(?!밍|머|어|핑|트|틀)[가-힣]{1,2}?(?=(?:을|를|은|는|도|으로|로)?(?:\s|$))`
);
const MEDICATION_VERB_PATTERN = pat(
    String.raw`먹|복용|처방|투여|맞았|맞고|흡입|뿌리|뿌려|바르|발라|발랐|붙이|붙여|붙였|마셨|마시|마셔`
);
const DOSE_PATTERN = pat(
    String.raw`\d+(?:\.\d+)?\s*(?:mg|밀리그램|밀리|mcg|g|그램|ml|cc|정(?!도)|알(?!레)|캡슐|포|봉|방울|퍼프)|` +
    String.raw`(?:한|두|세|반)\s*(?:알(?!레)|정(?!도)|포|봉|캡슐)`
);
const MEDICATION_TIMING_PATTERN = pat(
    String.raw`하루(?:에)?\s*(?:\d+|한|두|세|네)\s*(?:번|회|차례)|(?:\d+|한|두|세|네|여섯)\s*시간\s*마다|` +
    String.raw`하루(?=(?:에)?\s*(?:\d+|한|두|세|네|반)\s*(?:알(?!레)|정(?!도)|포|봉|캡슐))|` +
    String.raw`(?:아침|점심|저녁|자기\s*전|식후|식전)(?:\s*(?:,|하고|이랑)?\s*(?:아침|점심|저녁|자기\s*전))*` +
    String.raw`(?:\s*(?:에|마다|으로|로))?|(?:필요할|아플)\s*때`
);
const ALLERGY_PATTERN = pat(
    // "페니실린, 알레르기가 있어요": STT can put a comma between the name and the word.
    String.raw`([가-힣A-Za-z0-9-]{2,20}?)(?:에)?\s*,?\s*알레르기(?!\s*약)` +
    String.raw`(?:가|는|도)?\s*(?:있|있어|있습니다|예요|입니다|반응)`
);
// Names STT often gets one syllable wrong: "페니슐린", "헤니실린", "타이레농".
const KNOWN_SPELLINGS = [
  ...KNOWN_MEDICATION_PATTERN.source.split("|").filter((word) => fullmatch(String.raw`[가-힣]{4,}`, word)),
  "페니실린", "세팔로스포린", "설파제", "조영제", "꽃가루", "집먼지진드기", "고양이털",
];

/** A medicine or allergy name one syllable off a known name of 4+ syllables reads as that name.
 *
 * The review screen shows the result, so the patient can still change it. Names two or more syllables off,
 * and short names ("타이레"), are kept as heard: too many real names sit that close together. */
function knownSpelling(name: string): string {
  if (KNOWN_SPELLINGS.includes(name) || name.length < (name.endsWith("가루") ? 3 : 4)) return name;
  for (const known of KNOWN_SPELLINGS) {
    if (known.length === name.length && [...known].filter((letter, index) => letter !== name[index]).length === 1) {
      return known;
    }
  }
  return name;
}

const TEMPERATURE_PATTERN = pat(String.raw`(?<![\d.])(3[5-9]|4[0-2])(?:\.(\d))?\s*(?:도|度|℃|°)`);
const KNOWN_CONDITION = (
    String.raw`고혈압|저혈압|당뇨병?|고지혈증|이상지질혈증|천식|만성\s*폐쇄성\s*폐질환|결핵|` +
    String.raw`갑상선\s*(?:기능\s*(?:저하증|항진증)|질환)|심부전|부정맥|협심증|심근경색|심장병|` +
    String.raw`뇌졸중|뇌경색|간염|지방간|간경화|신부전|만성\s*신장\s*질환|신장\s*질환|` +
    String.raw`위염|위궤양|역류성\s*식도염|과민성\s*대장\s*증후군|비염|축농증|아토피|` +
    String.raw`우울증|공황장애|불면증|빈혈|통풍|관절염|디스크|골다공증|` +
    String.raw`녹내장|백내장|전립선\s*비대증|파킨슨병|치매|뇌전증|간질|건선|크론병|궤양성\s*대장염|` +
    String.raw`담석증?|자궁근종|대상포진|폐렴|암`
);
const DIAGNOSED_CONDITION_PATTERN = pat(
    String.raw`(?<![가-힣])([가-힣]{2,12}?)\s*(?:이라고|라고|으로|로)?\s*진단(?:을|도)?\s*(?:받|나왔)`
);
const NOT_A_CONDITION_PATTERN = pat(
    String.raw`[가-힣]*(?:에서|에게|한테|께서)|병원|의사|검사|선생님|작년|올해|예전|최근|이번|처음|정식`
);
const MEDICAL_HISTORY_PATTERN = pat(
    String.raw`(?<![가-힣])(${KNOWN_CONDITION})(?:이|가|은|는|도|을|를)?\s*` +
    String.raw`(?:있|진단|앓|걸렸|걸린|치료|투병|병력)`
);
const LISTED_HISTORY_PATTERN = pat(
    String.raw`(?<![가-힣])(${KNOWN_CONDITION})(?:이랑|랑|하고|과|와|,)\s*` +
    String.raw`(?=(?:${KNOWN_CONDITION})(?:이|가|은|는|도)?\s*(?:있|진단|앓))`
);
const MEDICAL_HISTORY_ABSENT_PATTERN = pat(
    String.raw`(?<![가-힣])(${KNOWN_CONDITION})(?:은|는|이|가|도)?\s*(?:없|아니)`
);
const SURGERY_PATTERN = pat(String.raw`([가-힣]{1,10}?)\s*(수술|시술)(?:을|도)?\s*(?:받았|받은|했|한\s*적)`);
// History said without a disease name: "혈압이 높아요", "간이 안 좋아요", "폐렴으로 입원했어요".
const HIGH_READING_PATTERN = pat(String.raw`(?<![가-힣])(혈압|혈당|콜레스테롤)(?:이|가|도)?\s*(?:좀\s*|많이\s*|조금\s*)?높(?!지\s*않|진\s*않)`);
const WEAK_ORGAN_PATTERN = pat(String.raw`(?<![가-힣])(간|신장|콩팥|심장|폐|갑상선)(?:이|가|도)?\s*(?:좀\s*|많이\s*)?안\s*좋`);
const ADMISSION_PATTERN = pat(String.raw`(?<![가-힣])([가-힣]{2,10}?)(?:으로|로)\s*입원`);
const MEDICINE_SUFFIX_PATTERN = pat(String.raw`\s*약(?!간|해|하|한|했)|제(?:를|을|도|는|은|\s|$)`);
const MEDICAL_SIGNAL_PATTERN = pat(
    String.raw`아프|아파|아픈|통증|열|기침|숨|호흡|답답|구토|토했|어지|설사|[메매]스꺼|오한|` +
    String.raw`콧물|발진|붓|부었|부어|저리|저려|마비|출혈|두근|약|알레르기|가래|막혀|가렵|가려|` +
    String.raw`두드러기|변비|피곤|쑤시|쑤셔|울렁|몸살|현기증|침침|이명|수술|진단|` +
    String.raw`감기|배탈|체했|체한|소화|입맛|식욕|잠을|잠이|쓰려|쓰리|더부룩|벌렁|땀|경련|` +
    String.raw`뻐근|결려|결리|무거|시려|시리|따가|따갑|가빠|가쁘|떨려|떨리|떨림|화끈|어둡|흐릿|흐려|토할|피가|피를|멍|` +
    String.raw`침침|간지|소변|오줌|기절|쓰러|정신을|의식|힘이|어눌|발음|쉬었|목소리|체중|몸무게|살이\s*빠|발작|헐었|헐어|` +
    String.raw`불편|혹이|혹\s*같|덩어리|부르트|부르텄|들려|말라|마르|갈증`
);
const UNCERTAIN_PATTERN = pat(
    String.raw`모르겠|잘\s*모르|확실(?:하지|치|하진)\s*않|헷갈|긴가민가|애매|같기도|` +
    String.raw`있는지\s*없는지|인지\s*아닌지|기억(?:이)?\s*(?:잘\s*)?안\s*나`
);
const AGE_PATTERN = pat(
    String.raw`(?<![\d.])(\d{1,3})\s*(?:살|세)(?!\s*때)(?:이에요|예요|입니다|이고|인데|이요|요)?|나이(?:는|가)?\s*(\d{1,3})|` +
    // "서른다섯 살": turbo writes ages in words.
    String.raw`(?<![가-힣])((?:열|스물|스무|서른|마흔|쉰|예순|일흔|여든|아흔)` +
    String.raw`(?:하나|한|둘|두|셋|세|넷|네|다섯|여섯|일곱|여덟|아홉)?)\s*살(?!\s*때)`
);
const NATIVE_TENS: Record<string, number> = {
  열: 10, 스물: 20, 스무: 20, 서른: 30, 마흔: 40, 쉰: 50, 예순: 60, 일흔: 70, 여든: 80, 아흔: 90,
};
const NATIVE_ONES: Record<string, number> = {
  하나: 1, 한: 1, 둘: 2, 두: 2, 셋: 3, 세: 3, 넷: 4, 네: 4, 다섯: 5, 여섯: 6, 일곱: 7, 여덟: 8, 아홉: 9,
};

function ageValue(word: string): number {
  if (/^\d+$/.test(word)) return Number(word);
  const tens = Object.keys(NATIVE_TENS).find((value) => word.startsWith(value))!;
  return NATIVE_TENS[tens] + (NATIVE_ONES[word.slice(tens.length)] ?? 0);
}
const SEX_PATTERN = pat(
    String.raw`(?<![가-힣])(?:(?<female>여자|여성)|남자|남성)(?=이에요|예요|입니다|이고|인데|이요|고\s|요)`
);
// Checked in order: negations first so "담배는 안 피워요" is not read as smoking.
const PREGNANCY_PATTERNS: Array<[NonNullable<PatientProfileHints["pregnancy"]>, Pat]> = [
    ["unknown", pat(String.raw`임신(?:인지|했는지|한\s*건지)\s*(?:잘\s*)?모르|임신\s*여부(?:는)?\s*(?:잘\s*)?모르`)],
    ["no", pat(String.raw`임신(?:\s*중)?(?:은|이|도)?\s*(?:아니|안\s*했|하지\s*않|아닙니다)|임신\s*가능성(?:은|이)?\s*없`)],
    ["yes", pat(String.raw`임신\s*(?:중|\d+\s*주|했|한\s*(?:것|거)\s*같|일\s*수도|가능성(?:이)?\s*있)`)],
];
const SMOKING_PATTERNS: Array<[NonNullable<PatientProfileHints["smoking"]>, Pat]> = [
    ["former", pat(String.raw`담배(?:는|를|도)?\s*(?:\S+\s+){0,3}(?:끊었|끊은|끊고)|금연(?:\s*중|했|한\s*지)|예전에\s*(?:담배를?\s*)?피웠`)],
    ["never", pat(
        String.raw`담배(?:는|를|도)?\s*(?:안\s*(?:피워|피우|펴|핍|피운)|피우지\s*않|피운\s*적(?:이|은)?\s*없)|비흡연|흡연(?:은|도)?\s*안\s*해`
    )],
    ["current", pat(String.raw`담배(?:를|는|도)?\s*(?:\S+\s+){0,3}(?:피워|피우|펴|핍|피고|태워)|흡연(?:해|하|자|\s*중)`)],
];
const DRINKING_PATTERNS: Array<[NonNullable<PatientProfileHints["drinking"]>, Pat]> = [
    ["no", pat(String.raw`술(?:은|을|도)?\s*(?:안\s*(?:마셔|마시|먹)|못\s*마셔|마시지\s*않|끊었|입에도\s*안)|금주`)],
    ["yes", pat(String.raw`(?<![가-힣])술(?:을|은|도)?\s*(?:\S+\s*)?(?:마셔|마시|마셨|먹어|먹고|먹었)|음주(?:를|는)?\s*(?:해|하|자주|가끔)`)],
];
const OTHER_PERSON = (
    String.raw`남편|아내|와이프|부인|엄마|어머니|아빠|아버지|아이|애|아기|애기|아들|딸|동생|형|누나|언니|오빠|` +
    String.raw`친구|동료|가족|할머니|할아버지|남자\s*친구|여자\s*친구|남친|여친|룸메이트|옆\s*사람|직장\s*동료`
);
const PERSON_OR_SELF_PATTERN = pat(
    String.raw`(?<![가-힣])(?:(?<person>${OTHER_PERSON})(?:들)?(?:이|가|도|는|은|께서|께서도)|` +
    String.raw`(?:저는|제가|저도|나는|내가|나도|본인은|저희\s*애가\s*아니라\s*제가))(?=\s)`
);
// A decimal point ("37.8도") does not end a sentence.
const SENTENCE_SPLIT_PATTERN = pat(String.raw`[.!?。](?!\d)|(?<=[가-힣]요)\s+`);
const CAUSE_DOUBT_PATTERN = pat(String.raw`때문|그런지|탓|원인|이유|인지는|해서인지`);
const CLAUSE_SUBJECT_PATTERN = pat(String.raw`[가-힣]+(?:이|가|은|는|도)(?=\s)`);
const NON_SUBJECT_WORD_PATTERN = pat(
    String.raw`(?:${INTENSITY_WORD}|같이|깊이|높이|함께|또|이제|지금|현재|오늘|어제|그제|요즘|` +
    String.raw`아침|점심|저녁|밤|새벽|낮|[가-힣]*부터|[가-힣]*에)(?:이|가|은|는|도)?`
);
const LEADING_ADVERB_PATTERN = pat(String.raw`(?:(?:또|같이|함께|이제는?|지금은|현재는|요즘은?)\s*)*`);
const BARE_PREDICATE_PATTERN = pat(
    String.raw`${LEADING_ADVERB_PATTERN.source}${INTENSITY_PHRASE}(?:안\s*)?` +
    String.raw`(?:아프|아파|아픈|아팠|쑤시|쑤셔|결려|결리|저려|저리|부었|부어|붓|답답|따끔|쓰려|쓰리|` +
    String.raw`가려|가렵|뻐근|욱신|지끈|화끈|막혀|막히|당기|당겨|시려|시리|따가|따갑|조이|조여|찌르|찌릿|콕콕)`
);
// Body parts that start a clause, glued to the next word without a space ("손가락" is not "손가 락").
const GLUED_BODY = String.raw`(?:머리|가슴|배|목|허리|등|어깨|무릎|다리|팔|손|발|눈|귀|코|속|몸|혀|입안|피부)(?:이|가)(?!락)`;
const GLUED_SUBJECT_PATTERN = pat(String.raw`((?:부터|째|전)(?=${GLUED_BODY})|${GLUED_BODY}(?=[가-힣]))`);
// "답답하고아파요": a connective ending glued to a bare predicate.
const GLUED_CONNECTIVE_PATTERN = pat(
    String.raw`((?<=[가-힣])(?:고|며|면서|지만))(?=` + BARE_PREDICATE_PATTERN.source.slice(LEADING_ADVERB_PATTERN.source.length) + ")"
);
const SUBCLAUSE_SPLIT_PATTERN = pat(
    String.raw`[.!?。,]|\s+(?:그리고|추가로|하지만|그러나|또한|근데|그런데|그래서)\s+|` +
    String.raw`(?<=[가-힣])(?:고|며|면서|는데|지만)\s+|` +
    // STT often drops the period: "열이 나요 기침은 ..." still ends a sentence at "요".
    String.raw`(?<=[가-힣]요)\s+`
);


function severityOf(text: string): string | null {
  const score = PAIN_SCORE_PATTERN.search(text);
  if (score) {
    const numbers = (score.text.match(/\d+/g) ?? []).map(Number);
    if ((score.text.includes("만점") || score.text.includes("중")) && numbers.length >= 2) {
      const [maximum, value] = numbers.slice(-2);
      if (value >= 0 && value <= maximum) return `${value}/${maximum}점`;
    } else if (numbers.length) {
      const value = numbers[numbers.length - 1];
      if (value >= 0 && value <= 100) return `${value}/${value <= 10 ? 10 : 100}점`;
    }
  }
  const found = SEVERITY_PATTERN.search(text);
  if (!found) return null;
  const value = found.text;
  if (fullmatch(MILD_SEVERITY, value)) return "경미함";
  if (fullmatch(MODERATE_SEVERITY, value)) return "중간";
  if (fullmatch(STRONG_SEVERITY, value)) return "심함";
  return ["심", "너무", "많이", "매우", "아주"].some((word) => value.includes(word)) ? "심함" : "경미함";
}

const DAY = 86_400_000;

function parseDay(value: string): Date {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(Date.UTC(year, month - 1, day));
}

const isoDay = (day: Date) => day.toISOString().slice(0, 10);
const addDays = (day: Date, days: number) => new Date(day.getTime() + days * DAY);
/** Monday 0 ... Sunday 6, like Python's date.weekday(). */
const weekdayOf = (day: Date) => (day.getUTCDay() + 6) % 7;

function calendarDay(year: number, month: number, day: number): Date | null {
  const value = new Date(Date.UTC(year, month - 1, day));
  return value.getUTCFullYear() === year && value.getUTCMonth() === month - 1 && value.getUTCDate() === day ? value : null;
}

/** Turn a stated onset into a calendar date when the words fix a single day.
 *
 * Vague spans ("2주 전", "한 달 동안", "엊그제") stay as words only. */
function onsetDate(onset: string | null, referenceDate: string | null): string | null {
  if (onset === null || referenceDate === null) return null;
  const reference = parseDay(referenceDate);
  const text = onset.replace(/\s+/g, "");
  const monthDay = matchStart(String.raw`(\d{1,2})월(\d{1,2})일`, text);
  if (monthDay) {
    const year = reference.getUTCFullYear();
    let day = calendarDay(year, Number(monthDay.groups[1]), Number(monthDay.groups[2]));
    if (day === null) return null;
    if (day > reference) day = calendarDay(year - 1, Number(monthDay.groups[1]), Number(monthDay.groups[2]));
    return day === null ? null : isoDay(day);
  }
  const weekdayMatch = matchStart(String.raw`(지난주|저번주|이번주)?([월화수목금토일])요일`, text);
  if (weekdayMatch) {
    const weekday = "월화수목금토일".indexOf(weekdayMatch.groups[2]!);
    const week = weekdayMatch.groups[1];
    const thisMonday = addDays(reference, -weekdayOf(reference));
    let day: Date;
    if (week === "지난주" || week === "저번주") {
      day = addDays(thisMonday, weekday - 7);
    } else if (week === "이번주") {
      day = addDays(thisMonday, weekday);
      if (day > reference) return null;
    } else {
      day = addDays(reference, -((((weekdayOf(reference) - weekday) % 7) + 7) % 7));
    }
    return isoDay(day);
  }
  if (matchStart("(?:오늘|방금|아침|점심)", text) || fullmatch(String.raw`\d+시간(?:전부터|전|째)?`, text)) {
    return isoDay(reference);
  }
  if (matchStart("(?:어제|어젯밤)", text)) return isoDay(addDays(reference, -1));
  if (matchStart("(?:그제|그저께)", text)) return isoDay(addDays(reference, -2));
  const daysAgo = fullmatch(String.raw`(\d+)일(전부터|전|째)(?:아침|점심|저녁|밤|새벽)?(?:부터)?`, text);
  if (daysAgo) {
    const count = Number(daysAgo.groups[1]);
    // "3일째" is the third day, so it started two days ago.
    return isoDay(addDays(reference, -(daysAgo.groups[2] === "째" ? count - 1 : count)));
  }
  return null;
}

function normalizeOnset(value: string | null): string | null {
  if (value === null) return null;
  // "이틀 전 저녁부터" → "2일 전 저녁부터": normalize the day count, keep the time of day.
  const withTime = fullmatch(String.raw`(.+?전)[,\s]*(아침|점심|저녁|밤|새벽)(부터)?`, value);
  if (withTime) return `${normalizeOnset(withTime.groups[1]!)} ${withTime.groups[2]}${withTime.groups[3] ?? ""}`;
  const nativeDays: Record<string, string> = {
    하루: "1일", 이틀: "2일", 사흘: "3일", 나흘: "4일", 닷새: "5일", 엿새: "6일", 이레: "7일", 여드레: "8일",
    아흐레: "9일", 열흘: "10일",
  };
  const nativeMatch = fullmatch(
    String.raw`(하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘)\s*(전부터|전|동안|째)?`, value,
  );
  if (nativeMatch) {
    const suffix = nativeMatch.groups[2];
    return nativeDays[nativeMatch.groups[1]!] + (suffix ? `${suffix === "째" ? "" : " "}${suffix}` : "");
  }
  const calendarWords: Record<string, string> = { 일주일: "1주", 한주: "1주", 두주: "2주", 한달: "1달", 두달: "2달" };
  const calendarMatch = fullmatch(String.raw`(일주일|한\s*주|두\s*주|한\s*달|두\s*달)\s*(전부터|전|동안|째)?`, value);
  if (calendarMatch) {
    const suffix = calendarMatch.groups[2];
    return calendarWords[calendarMatch.groups[1]!.replace(/\s+/g, "")] + (suffix ? `${suffix === "째" ? "" : " "}${suffix}` : "");
  }
  const numberWords: Record<string, string> = {
    일: "1", 이: "2", 삼: "3", 사: "4", 오: "5", 육: "6", 칠: "7", 팔: "8", 구: "9", 십: "10",
  };
  const found = fullmatch(
    String.raw`(\d+|일|이|삼|사|오|육|칠|팔|구|십)\s*(시간|일|주|개월|달)\s*(전부터|전|동안|째)?`, value,
  );
  if (!found) return value;
  const suffix = found.groups[3];
  return `${numberWords[found.groups[1]!] ?? found.groups[1]}${found.groups[2]}`
    + (suffix ? `${suffix === "째" ? "" : " "}${suffix}` : "");
}

function normalizeFrequency(value: string): string {
  const numberWords: Record<string, string> = {
    한: "1", 두: "2", 세: "3", 네: "4", 다섯: "5", 여섯: "6", 일곱: "7", 여덟: "8", 아홉: "9", 열: "10",
  };
  const ranges: Record<string, string> = { 한두: "1~2", 두세: "2~3", 서너: "3~4" };
  const found = search(String.raw`(\d+|한두|두세|서너|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열)\s*(?:번|회|차례)`, value);
  if (!found) return value;
  const word = found.groups[1]!;
  const count = ranges[word] ?? numberWords[word] ?? word;
  return `${search("하루(?:에)?", value) ? "하루 " : ""}${count}회`;
}

function nearestValue(pattern: Pat, text: string, start: number, end: number, maxGap = 24): string | null {
  let best: [number, string] | null = null;
  for (const found of pattern.finditer(text)) {
    const gap = found.end <= start ? start - found.end : found.start >= end ? found.start - end : 0;
    if (gap <= maxGap && (best === null || gap < best[0])) best = [gap, found.text];
  }
  return best ? best[1] : null;
}

const ONSET_BOUNDARY = pat(
  String.raw`[,;.!?。]|(?:추가로|그리고|하지만|그러나|또한)|` +
  String.raw`(?:고|며|면서|는데|지만)(?:\s|$)|` +
  // STT without periods: "기침이 심해졌어요 오늘 아침에는" — the next sentence's onset is not the cough's.
  String.raw`(?<=[가-힣])요\s`,
);

function onsetForSymptom(text: string, start: number, end: number, previousEnd: number, nextStart: number): string | null {
  const onsets = ONSET_PATTERN.finditer(text);
  const overlapping = onsets.filter((found) => found.start >= start && found.end <= end);
  if (overlapping.length) return overlapping[0].text;
  const preceding = onsets.filter((found) =>
    found.end <= start && found.end >= previousEnd && start - found.end <= 24
    && !ONSET_BOUNDARY.search(text.slice(found.end, start)));
  if (preceding.length) return preceding[preceding.length - 1].text;
  const following = onsets.filter((found) =>
    found.start >= end && found.end <= nextStart && found.start - end <= 24
    && !ONSET_BOUNDARY.search(text.slice(end, found.start)));
  return following.length ? following[0].text : null;
}

const SEVERITY_CONNECTOR = pat(String.raw`[,;]|(?:추가로|그리고|하지만|그러나|또한)|(?:고|며|면서|는데|지만)(?:\s|,|$)`);

function distanceTo(found: Match, position: Span): number {
  if (found.end <= position[0]) return position[0] - found.end;
  if (found.start >= position[1]) return found.start - position[1];
  return 0;
}

function textBetween(text: string, found: Match, start: number, end: number): string {
  if (found.end <= start) return text.slice(found.end, start);
  if (found.start >= end) return text.slice(end, found.start);
  return "";
}

function severityForSymptom(text: string, start: number, end: number, symptomPositions: Span[]): string | null {
  const ownerFor = (found: Match): Span => {
    const overlapping = symptomPositions.filter((position) => found.start < position[1] && found.end > position[0]);
    if (overlapping.length) return overlapping[0];
    const preceding = symptomPositions.filter((position) => position[1] <= found.start);
    const following = symptomPositions.filter((position) => position[0] >= found.end);
    const previous = preceding.length ? preceding[preceding.length - 1] : null;
    const next = following.length ? following[0] : null;
    if (previous && next) {
      if (SEVERITY_CONNECTOR.search(text.slice(found.end, next[0]))) return previous;
      if (SEVERITY_CONNECTOR.search(text.slice(previous[1], found.start))) return next;
    }
    const available = [previous, next].filter((position): position is Span => position !== null);
    return minBy(available, (position) => [distanceTo(found, position), position[0]]);
  };

  const candidates: Match[] = [];
  for (const found of [...SEVERITY_PATTERN.finditer(text), ...PAIN_SCORE_PATTERN.finditer(text)]) {
    if (found.pattern === SEVERITY_PATTERN
        && matchStart(String.raw`졌|\s*(?:괜찮아졌|나아졌|호전됐|좋아졌|덜해졌|줄었|완화됐|편해졌)`, text.slice(found.end))) {
      continue;
    }
    // "처음엔 7점이었는데 지금은 4점": the second score is the "now" of the first, read with it below
    // ("7/10점 → 4/10점"), not a score of its own for whatever symptom comes next.
    if (found.pattern === PAIN_SCORE_PATTERN
        && search(String.raw`\d\s*(?:점|정도)[^.!?。]{0,25}(?:지금은|현재는|이제는?)\s*(?:한\s*)?$`, text.slice(0, found.start))) {
      continue;
    }
    const owner = ownerFor(found);
    const ownerOverlapsCurrent = owner[0] < end && owner[1] > start;
    if (!sameSpan(owner, [start, end]) && !ownerOverlapsCurrent) continue;
    const between = textBetween(text, found, start, end);
    // A score often comes in the next sentence ("아팠어요 아픈 정도는 8"), so only a full stop separates,
    // unless the score names what it rates ("아파요. 아픈 정도는 7점": turbo adds the full stop).
    // Also a sentence that opens with how bad it is: "배가 아파요. 참기 힘들 정도예요", "... 처음엔 7점이었는데".
    const stops = between.split(/[.!?。]/);
    const opensNext = stops.length === 2
      && fullmatch(String.raw`\s*(?:처음(?:엔|에는)?|아까는?)?\s*`, stops[stops.length - 1])
      && !fullmatch("아주|매우|너무|많이|조금|약간", found.text);
    const refersBack = found.start >= end
      && (matchStart("(?:고통|통증|아픈|아픔|강도)", found.text) || opensNext);
    if (/[.!?。]/.test(between) && !refersBack) continue;
    candidates.push(found);
  }
  if (!candidates.length) return null;
  const latest = maxBy(candidates, (found) => found.start);
  let severity = severityOf(latest.text);
  if (severity && latest.pattern === PAIN_SCORE_PATTERN) {
    const rest = beforeFirst(SENTENCE_SPLIT_PATTERN, text.slice(latest.end));
    const scale = severity.split("/")[1];
    // "6점 아니 4점": the patient corrected themselves.
    const corrected = matchStart(String.raw`\s*,?\s*(?:이)?\s*아니(?:고|라)?\s*,?\s*(\d{1,3})\s*(?:점|정도)`, rest);
    if (corrected) severity = `${corrected.groups[1]}/${scale}`;
    const now = search(String.raw`(?:지금은|현재는|이제는?)\s*(?:한\s*)?(\d{1,3})\s*(?:점|정도)`, rest);
    if (now) severity = `${severity} → ${now.groups[1]}/${severity.split("/")[1]}`;
  }
  return severity;
}

/** Matches of a pattern owned by this symptom (the nearest one), within maxGap and the same sentence. */
function ownedMatches(
  pattern: Pat, text: string, start: number, end: number, symptomPositions: Span[], maxGap: number,
): Array<[number, Match]> {
  const candidates: Array<[number, Match]> = [];
  for (const found of pattern.finditer(text)) {
    if (!symptomPositions.length) continue;
    const [distance, owner] = minBy(
      symptomPositions.map((position): [number, Span] => [distanceTo(found, position), position]),
      (item) => [item[0], item[1][0]],
    );
    if (!sameSpan(owner, [start, end]) || distance > maxGap) continue;
    const between = textBetween(text, found, start, end);
    if (SENTENCE_SPLIT_PATTERN.search(between) || search("그리고|하지만|그러나|추가로", between)) continue;
    candidates.push([distance, found]);
  }
  return candidates;
}

function frequencyForSymptom(text: string, start: number, end: number, symptomPositions: Span[]): string | null {
  const candidates = ownedMatches(FREQUENCY_PATTERN, text, start, end, symptomPositions, 24);
  if (!candidates.length) return null;
  let chosen = minBy(candidates, (item) => [item[0]])[1];
  const earlier = candidates.map(([, found]) => found).filter((found) => found.start < chosen.start);
  if (earlier.length && FREQUENCY_NOW_PATTERN.search(text.slice(Math.max(0, chosen.start - 12), chosen.end))) {
    chosen = maxBy(earlier, (found) => found.start);
  }
  let frequency = normalizeFrequency(chosen.text);
  const now = FREQUENCY_NOW_PATTERN.search(beforeFirst(SENTENCE_SPLIT_PATTERN, text.slice(chosen.end)));
  if (now) frequency = `${frequency} → ${normalizeFrequency(now.groups[1]!)}`;
  return frequency;
}

function trendForSymptom(
  text: string, start: number, end: number, symptomPositions: Span[],
): SymptomObservation["trend"] {
  const candidates = ownedMatches(TREND_PATTERN, text, start, end, symptomPositions, 32);
  if (!candidates.length) return null;
  const found = minBy(candidates, (item) => [item[0]])[1];
  if (found.named.improving) return "improving";
  if (found.named.worsening) return "worsening";
  return "unchanged";
}

const MEDICINE_CLAUSE_BOUNDARY = pat(
  String.raw`[.!?。](?!\d)(?!\s*아니)|(?:\s+)(?:그리고|하지만|그러나|또한)(?:\s+)|(?<=[가-힣]요)\s+`,
);

function doseText(dose: string): string {
  return sub("(?<=[한두세반])(?=[알정포봉캡])", " ", sub("밀리그램|밀리", "mg", sub(String.raw`(?<=\d)\s+`, "", dose)));
}

const timingText = (timing: string) => sub(String.raw`\s*(?:에|으로|로)$`, "", timing.replace(/\s+/g, " "));

/** Medication lines for the record ("타이레놀 500mg 하루 2회") and the bare names. */
function extractMedications(text: string): [string[], string[]] {
  const names: string[] = [];
  const lines: string[] = [];
  for (const clause of MEDICINE_CLAUSE_BOUNDARY.split(text)) {
    if (!MEDICATION_VERB_PATTERN.search(clause)) continue;
    let found: Array<[number, string]> = [];
    for (const name of MEDICATION_NAME_PATTERN.finditer(clause)) {
      // "조영제 알레르기" is an allergy
      if (!matchStart(String.raw`\s*,?\s*알레르기`, clause.slice(name.end))) {
        found.push([name.start, name.groups[1]!.replace(/\s+/g, "")]);
      }
    }
    for (const pattern of [KNOWN_MEDICATION_PATTERN, DRUG_NAME_PATTERN, TYLENOL_SOUNDALIKE_PATTERN]) {
      for (const name of pattern.finditer(clause)) {
        // "페니실린 알레르기" is an allergy, not a medicine being taken.
        if (!matchStart(String.raw`\s*,?\s*알레르기`, clause.slice(name.end))) found.push([name.start, name.text]);
      }
    }
    for (const name of UNKNOWN_DOSED_MEDICATION_PATTERN.finditer(clause)) {
      // "어제 두 알", "아파서 두 알": a time, an adverb or a verb before the dose is not a medicine's name.
      const word = name.groups[1]!;
      if (NON_SUBJECT_WORD_PATTERN.fullmatch(word)
          || fullmatch("매일|하루|한번|다시|그냥|이거|그거|저거|아니", word)
          || search("(?:서|고|며|면|니까|는데|지만|마다)$", word)) {
        continue;
      }
      if (!found.some(([start, known]) => start <= name.start && name.start < start + known.length + 3)) {
        found.push([name.start, word]);
      }
    }
    // "타이레놀" is both a known name and a sound-alike match
    found = [...new Map(found.map((item) => [`${item[0]}\u0000${item[1]}`, item])).values()]
      .sort((a, b) => a[0] - b[0] || (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0));
    found.forEach(([position, heard], index) => {
      const name = knownSpelling(heard); // same length, so the dose tail below still lines up
      if (names.includes(name) || names.some((other) => other.includes(name) || name.includes(other))) return;
      names.push(name);
      // Dose and timing said right after the name, before the next medicine, belong to it.
      const nextPosition = index + 1 < found.length ? found[index + 1][0] : clause.length;
      const tail = clause.slice(position + name.length, Math.min(nextPosition, position + name.length + 30));
      let dose = DOSE_PATTERN.search(tail);
      // "한 알, 아니 두 알": the patient corrected the dose.
      const corrected = dose && matchStart(String.raw`\s*[,?]?\s*아니(?:고|라)?\s*,?\s*`, tail.slice(dose.end));
      if (dose && corrected) dose = DOSE_PATTERN.match(tail, dose.end + corrected.end) ?? dose;
      const doses = dose ? [doseText(dose.text)] : [];
      const timing = MEDICATION_TIMING_PATTERN.search(tail);
      const timings = timing
        ? [search("번|회|차례", timing.text) ? normalizeFrequency(timing.text) : timingText(timing.text)]
        : [];
      // "하루 한 알" reads timing first; "500mg 하루 2회" reads dose first.
      const details = timings.length === 1 && timings[0] === "하루" ? [...timings, ...doses] : [...doses, ...timings];
      lines.push([name, ...details].join(" "));
    });
  }
  // "자기 전에 한 알 먹어요" with no medicine named anywhere: keep that a pill is taken, for the patient to name
  // on the review screen. Not when another sentence named it ("타이레놀을 먹어요. 자기 전에 한 알").
  if (!names.length) {
    for (const clause of MEDICINE_CLAUSE_BOUNDARY.split(text)) {
      const pill = search(String.raw`(?:한|두|세|반|\d+)\s*(?:알(?!레)|정(?!도)|캡슐|포)`, clause);
      if (pill && MEDICATION_VERB_PATTERN.search(clause.slice(pill.end))) {
        const timing = MEDICATION_TIMING_PATTERN.search(clause);
        const when = timing ? [timingText(timing.text)] : [];
        lines.push(["이름 모르는 약", ...when, sub("(?<=[한두세반])(?=[알정포캡])", " ", pill.text)].join(" "));
        break;
      }
    }
  }
  return [lines, names];
}

function firstSymptomMatch(pattern: Pat, text: string): Match | null {
  // "두통약", "기침약", "설사약" name a medicine, not a symptom the patient has now.
  return pattern.finditer(text).find((found) => !MEDICINE_SUFFIX_PATTERN.match(text, found.end)) ?? null;
}

const SINO_DIGITS: Record<string, number> = { 일: 1, 이: 2, 삼: 3, 사: 4, 오: 5, 육: 6, 칠: 7, 팔: 8, 구: 9 };
// Body temperature said in words, as the phone STT model writes it: "삼십팔 도", "삼십팔 점 오 도".
const SPOKEN_TEMPERATURE_PATTERN = pat(
  String.raw`(?<![가-힣])(삼|사)십(일|이|삼|사|오|육|칠|팔|구)?(?:\s*점\s*(일|이|삼|사|오|육|칠|팔|구))?\s*도`,
);

function spokenTemperatureToDigits(text: string): string {
  return SPOKEN_TEMPERATURE_PATTERN.sub(text, (found) => {
    const value = SINO_DIGITS[found.groups[1]!] * 10 + (SINO_DIGITS[found.groups[2] ?? ""] ?? 0);
    return found.groups[3] ? `${value}.${SINO_DIGITS[found.groups[3]]}도` : `${value}도`;
  });
}

// Notes written or said in 음슴체 ("머리가 많이 아픔, 오한도 있음, 약 먹었음") read as the polite endings the rules know.
// Whole words only, except 함/됨/ㅆ음 endings: "콧막힘" is the symptom's name, "기침함" is "기침해요".
const PLAIN_ENDING_PATTERN = pat(
  String.raw`((?<=숨\s)참|(?<=숨이\s)참|(?<=못\s)잠|(?<![가-힣])(?:아픔|없음|괜찮음|남|막힘|쑤심|결림|마름|부음)|아님|피움|마심|(?<=[가-힣])임|함|됨|[가-힣]음)(?=[\s.,!?]|$)`,
);
const PLAIN_ENDINGS: Record<string, string> = {
  참: "차요", 잠: "자요", 아님: "아니에요", 피움: "피워요", 마심: "마셔요", 임: "이에요", 아픔: "아파요", 없음: "없어요",
  괜찮음: "괜찮아요", 함: "해요", 남: "나요", 막힘: "막혀요", 쑤심: "쑤셔요", 결림: "결려요", 마름: "말라요", 부음: "부어요",
  됨: "돼요",
};

function politeEndings(text: string): string {
  return PLAIN_ENDING_PATTERN.sub(text, (found) => {
    const word = found.groups[1]!;
    if (word in PLAIN_ENDINGS) return PLAIN_ENDINGS[word];
    const stem = word[0];
    // 있음, 먹었음, 아팠음: a syllable ending in ㅆ before 음 → 있어요, 먹었어요, 아팠어요.
    return (stem.charCodeAt(0) - 0xac00) % 28 === 20 ? `${stem}어요` : word;
  });
}

// Medicine names both STT engines kept hearing wrong in the same way, too far off for knownSpelling.
// ponytail: one name so far (2026-10-09, three recordings); add others only when recordings repeat them.
const SOUNDALIKE_NAMES: Array<[Pat, string]> = [[pat(String.raw`매트\s*프(?:로|롬)\s*(?:민|인|면)`), "메트포르민"]];

function knownSoundalikes(text: string): string {
  return SOUNDALIKE_NAMES.reduce((current, [pattern, name]) => pattern.sub(current, name), text);
}

/** STT and quick typing drop spaces: "가슴이답답하고아파요" → "가슴이 답답하고 아파요". */
function spaceGluedWords(text: string): string {
  return GLUED_CONNECTIVE_PATTERN.sub(GLUED_SUBJECT_PATTERN.sub(text, "$1 "), "$1 ");
}

// "배가 아프거나 토한 적은 없고", "열이나 기침은 없어요": symptoms listed before one "없다" are all absent.
const LIST_CONNECTOR = "(?:거나|이나|나|과|와|이랑|랑|하고)";
const NEGATION_LATER_IN_CLAUSE = String.raw`\s+(?:(?![.?!]|요\s|고\s|서\s).){0,25}?(?:없|않)`;
const LISTED_BEFORE_NEGATION_PATTERN = pat(String.raw`\s*${LIST_CONNECTOR}${NEGATION_LATER_IN_CLAUSE}`);
// "머리도 아팠지만 지금은 괜찮아졌어요": had it, gone now.
const GONE_NOW_PATTERN = pat(
  // "열은 났었는데 지금은 내렸어요", "어제까지 설사했는데 오늘은 안 했어요"
  String.raw`(?:(?!요\s|고\s)[^.?!,]){0,15}?(?:지만|는데)\s+(?:지금은|이제는?|이젠|현재는|오늘은)\s*` +
  String.raw`(?:괜찮|다\s*나았|나았|없어졌|안\s*아파|(?:열이\s*)?(?:다\s*)?내렸|떨어졌|멈췄|그쳤|안\s*했|안\s*해)`,
);
// "페니실린을 먹고 두드러기가 생긴 적이 있어요": a past reaction to a medicine is an allergy, not a symptom now.
// "새우를 먹으면 입술이 부어요": a reaction every time something is eaten is an allergy too.
const ALLERGIC_REACTION = String.raw`(?:두드러기|발진|가려움|가려웠|가려워|가렵|붓|부었|부어|숨이\s*막|쇼크)`;
const DRUG_REACTION_PATTERN = pat(
  // The particle may drop only before "먹으면": "아무것도 먹고 ... 아스피린을 먹고 두드러기" named 아무것도.
  String.raw`(?<![가-힣])([가-힣A-Za-z]{2,12}?)(?:(?:을|를|만)\s*` +
  String.raw`(?:먹고|먹었더니|먹은\s*(?:뒤|후)에?|맞고|맞았더니|복용하고)\s*` +
  String.raw`[^.?!]{0,20}?${ALLERGIC_REACTION}[^.?!]{0,15}?(?:적이|적도)\s*있|` +
  String.raw`(?:을|를|만)?\s*(?:먹으면|먹기만\s*하면|먹을\s*때마다|맞으면)\s*[^.?!]{0,20}?${ALLERGIC_REACTION})`,
);

// "피곤하고 입맛이 없어요": 하고 after a 하다 word ends a verb, it does not list a noun like "열하고 오한은".
const HADA_ROOT_PATTERN = pat("(?:피곤|답답|더부룩|빵빵|팽팽|뻐근|따끔|얼얼|묵직|나른|무기력|어질어질|울렁|메슥|으슬으슬|오싹)$");

/** Where a symptom was found. A carried one is a predicate whose subject is in the previous clause: its position is
 * the predicate itself, and its text shows the subject it borrowed. */
type Evidence = { start: number; end: number; text: string; carried: boolean };

const evidenceOf = (found: Match): Evidence => ({ start: found.start, end: found.end, text: found.text, carried: false });

function isNegatedInList(text: string, evidence: Evidence): boolean {
  const after = text.slice(evidence.end);
  // "열이나" already took the connector
  if (search(`${LIST_CONNECTOR}$`, evidence.text)) return Boolean(matchStart(NEGATION_LATER_IN_CLAUSE, after));
  let listed = LISTED_BEFORE_NEGATION_PATTERN.match(after);
  if (listed && HADA_ROOT_PATTERN.search(evidence.text) && matchStart(String.raw`\s*하고`, after)) listed = null;
  return Boolean(listed || GONE_NOW_PATTERN.match(after));
}

type Found = { rule: Rule; evidence: Evidence; absent: boolean };

/** Read the patient's words. referenceDate is the patient's local date ("2026-10-09"), for onsets like "어제부터". */
export function extractIntake(input: string, referenceDate: string | null = null): IntakeExtraction {
  const normalized = spokenTemperatureToDigits(spaceGluedWords(politeEndings(knownSoundalikes(
    input.split(/\s+/).filter(Boolean).join(" "),
  ))));
  let matches: Found[] = [];
  for (const symptomRule of RULES) {
    const mention = firstSymptomMatch(symptomRule.mention, normalized);
    const absent = firstSymptomMatch(symptomRule.absent, normalized);
    const evidence = absent ?? mention;
    if (evidence) matches.push({ rule: symptomRule, evidence: evidenceOf(evidence), absent: absent !== null });
  }
  const [carriedMatches, carriedSpans] = carriedSubjectMatches(normalized, matches);
  matches.push(...carriedMatches);
  // "많이 먹으면 부어요", "그거 먹으면", "아무거나 먹으면": not a thing the patient reacts to.
  const reactions = DRUG_REACTION_PATTERN.finditer(normalized).filter((reaction) =>
    !(NON_SUBJECT_WORD_PATTERN.fullmatch(reaction.groups[1]!)
      || fullmatch("이거|그거|저거|이것|그것|뭔가|뭘|뭐|뭐든지?|아무거나|아무것이나|음식|밥", reaction.groups[1]!)));
  matches = matches
    .filter(({ evidence }) => !reactions.some((reaction) => reaction.start <= evidence.start && evidence.start < reaction.end))
    .map((item) => ({ ...item, absent: item.absent || isNegatedInList(normalized, item.evidence) }));

  const positions = matches.map(({ evidence }): Span => [evidence.start, evidence.end]).sort(compareSpans);
  // Every later mention too ("배가 아픈 정도는 7점"): a score or count said there belongs to that symptom.
  const mentions = new Map<string, Span[]>(matches.map(({ rule: symptomRule, evidence }) => [symptomRule.name, [
    [evidence.start, evidence.end] as Span,
    ...symptomRule.mention.finditer(normalized)
      .filter((found) => found.start !== evidence.start && !MEDICINE_SUFFIX_PATTERN.match(normalized, found.end))
      .map((found): Span => [found.start, found.end]),
  ]]));
  const mentionPositions = uniqueSortedSpans([...mentions.values()].flat());
  const countedPositions = uniqueSortedSpans([...FREQUENCY_SYMPTOMS].flatMap((name) => mentions.get(name) ?? []));
  let symptomPositions: Array<[number, SymptomObservation]> = [];
  const onsetSpans: Array<[number, number, string | null]> = [];
  for (const { rule: symptomRule, evidence, absent } of matches) {
    let isAbsent = absent;
    const positionIndex = positions.findIndex((span) => sameSpan(span, [evidence.start, evidence.end]));
    const previousEnd = positionIndex > 0 ? positions[positionIndex - 1][1] : 0;
    const nextStart = positionIndex + 1 < positions.length ? positions[positionIndex + 1][0] : normalized.length;
    let onset = normalizeOnset(onsetForSymptom(normalized, evidence.start, evidence.end, previousEnd, nextStart));
    if (onset === null && evidence.carried) {
      // "어제부터 가슴이 답답하고 아파요": the borrowed subject brings its onset along.
      const subjectStart = evidence.end - evidence.text.length;
      onset = onsetSpans.find(([start, end]) => start <= subjectStart && subjectStart < end)?.[2] ?? null;
    }
    onsetSpans.push([evidence.start, evidence.end, onset]);
    const spans = mentions.get(symptomRule.name)!;
    let severity = spans.map(([start, end]) => severityForSymptom(normalized, start, end, mentionPositions)).find(Boolean) ?? null;
    if (symptomRule.name === "발열") {
      const temperature = nearestValue(TEMPERATURE_PATTERN, normalized, evidence.start, evidence.end);
      if (temperature) {
        severity = sub(String.raw`\s*(?:도|度|℃|°)$`, "℃", temperature);
        // "39도까지 올라서 ... 지금은 37.8도 정도로 내렸어요": the temperature now as well.
        const rest = beforeFirst(SENTENCE_SPLIT_PATTERN, normalized.slice(evidence.end));
        const now = search(
          String.raw`(?:지금은|현재는|이제는?)\s*(?:한\s*)?(3[5-9](?:\.\d)?|4[0-2](?:\.\d)?)\s*(?:도|度|℃|°)`, rest,
        );
        if (now && `${now.groups[1]}℃` !== severity) severity = `${severity} → ${now.groups[1]}℃`;
      }
    }
    const frequency = FREQUENCY_SYMPTOMS.has(symptomRule.name)
      ? spans.map(([start, end]) => frequencyForSymptom(normalized, start, end, countedPositions)).find(Boolean) ?? null
      : null;
    const trend = spans.map(([start, end]) => trendForSymptom(normalized, start, end, mentionPositions)).find(Boolean) ?? null;
    // "배는 괜찮아졌어요" says it is gone; "좀 괜찮아졌어요" says it is better, still there.
    if (search("(?<!좀 )(?<!조금 )(?<!약간 )(?<!많이 )(?<!전보다 )괜찮아졌$", evidence.text)) isAbsent = true;
    const isUncertain = isUncertainAt(normalized, evidence.start, positions);
    if (isUncertain) isAbsent = false;
    symptomPositions.push([evidence.start, {
      name: symptomRule.name,
      status: isUncertain ? "uncertain" : isAbsent ? "absent" : "present",
      body_site: bodySiteFor(normalized, evidence, symptomRule),
      onset: isAbsent ? null : onset,
      onset_date: isAbsent ? null : onsetDate(onset, referenceDate),
      severity: isAbsent ? null : severity,
      frequency: isAbsent ? null : frequency,
      trend: isAbsent ? null : trend,
      source_text: evidence.text,
    }]);
  }
  const ordered = [...symptomPositions].sort((a, b) => a[0] - b[0]);
  for (let index = 1; index < ordered.length; index += 1) {
    const [beforeStart, before] = ordered[index - 1];
    const [start, item] = ordered[index];
    const joined = normalized.slice(beforeStart + before.source_text.length, start);
    if (item.onset === null && item.status === "present" && before.onset && before.status === "present"
        && fullmatch(String.raw`(?:(?!요\s)[가-힣 ]){0,8}?고\s+(?:[가-힣]+(?:이|가|은|는|도)\s+)?`, joined)) {
      ordered[index] = [start, { ...item, onset: before.onset, onset_date: before.onset_date }];
    }
  }
  symptomPositions = ordered;
  const othersSymptoms: OtherPersonSymptom[] = [];
  const symptoms: SymptomObservation[] = [];
  for (const [start, item] of symptomPositions) {
    const person = otherPersonFor(normalized, start);
    if (person === null) symptoms.push(item);
    else if (item.status !== "absent") othersSymptoms.push({ person, symptom: item.name, source_text: item.source_text });
  }

  const [extractedMedications, medicationNames] = extractMedications(normalized);
  const reactionNames = reactions.map((reaction) => knownSpelling(reaction.groups[1]!));
  const allergies = [...new Set([...ALLERGY_PATTERN.findall(normalized).map(knownSpelling), ...reactionNames])];
  const medications = extractedMedications.filter((line) => !reactionNames.includes(line.split(/\s+/)[0]));
  const [medicalHistory, othersHistory] = extractMedicalHistory(normalized);
  othersSymptoms.push(...othersHistory);
  const evidenceSpans: Span[] = [
    ...matches.map(({ evidence }): Span => [evidence.start, evidence.end]),
    ...carriedSpans,
    ...RULES.flatMap((symptomRule) => [symptomRule.mention, symptomRule.absent])
      .flatMap((pattern) => pattern.finditer(normalized))
      .filter((found) => !MEDICINE_SUFFIX_PATTERN.match(normalized, found.end))
      .map((found): Span => [found.start, found.end]),
    ...[
      MEDICAL_HISTORY_PATTERN, MEDICAL_HISTORY_ABSENT_PATTERN, SURGERY_PATTERN, TEMPERATURE_PATTERN,
      HIGH_READING_PATTERN, WEAK_ORGAN_PATTERN, ADMISSION_PATTERN,
    ].flatMap((pattern) => pattern.finditer(normalized)).map((found): Span => [found.start, found.end]),
    ...DIAGNOSED_CONDITION_PATTERN.finditer(normalized)
      .filter((found) => !NOT_A_CONDITION_PATTERN.fullmatch(found.groups[1]!))
      .map((found): Span => [found.start, found.end]),
  ];
  const unrecognizedFragments: string[] = [];
  for (const [start, end] of subclauseSpans(normalized)) {
    const fragment = normalized.slice(start, end).trim();
    if (!fragment || !MEDICAL_SIGNAL_PATTERN.search(fragment)) continue;
    const recognized = evidenceSpans.some(([spanStart, spanEnd]) => spanStart < end && spanEnd > start)
      || medicationNames.some((name) => fragment.replace(/\s+/g, "").includes(name))
      || allergies.some((allergen) => fragment.includes(allergen));
    if (!recognized) unrecognizedFragments.push(fragment);
  }
  return {
    symptoms,
    medications,
    allergies,
    medical_history: medicalHistory,
    others_symptoms: othersSymptoms,
    profile: extractProfile(normalized),
    unrecognized_fragments: unrecognizedFragments,
    needs_user_confirmation: true,
  };
}

/** Add side and sub-site to the body site: "오른쪽 아랫배", "뒷머리", "왼쪽 무릎", "왼쪽 팔". */
function bodySiteFor(text: string, evidence: Evidence, symptomRule: Rule): string | null {
  // Carried evidence starts at the predicate; its text begins with the borrowed subject.
  const start = evidence.end - evidence.text.length;
  const clauseStart = Math.max(0, ...SUBCLAUSE_SPLIT_PATTERN.finditer(text, 0, start).map((found) => found.end));
  let site: string;
  let siteStart: number;
  if (symptomRule.bodySite === null) {
    if (!PART_SYMPTOMS.has(symptomRule.name)) return null;
    const part = matchStart(`(${PART_WORDS})`, evidence.text);
    if (part) {
      site = part.groups[1]!;
      siteStart = start;
    } else {
      const before = search(
        String.raw`(${PART_WORDS})(?:이|가|에|도|은|는)?\s*${INTENSITY_PHRASE}$`, text.slice(clauseStart, start),
      );
      if (before === null) return null;
      site = before.groups[1]!;
      siteStart = clauseStart + before.start;
    }
  } else {
    const lead = text.slice(Math.max(0, start - 2), start);
    const prefix = ["아랫", "윗", "뒷", "앞"].find((word) => lead.endsWith(word)) ?? "";
    siteStart = start - prefix.length;
    site = symptomRule.bodySite;
    const siteMatch = SITE_WORD_PATTERN.match(prefix + evidence.text);
    if (siteMatch && !["배", "머리", "가슴", "허리", "귀", "눈", "목"].includes(siteMatch.text)) {
      site = siteMatch.text.replace(/\s+/g, " ");
    }
  }
  // Only a side word right before the place counts: not "오른쪽으로 누우면 배가 아파요".
  const side = search(String.raw`${SIDE_PATTERN.source}\s*$`, text.slice(clauseStart, siteStart));
  return side ? `${SIDE_NAMES[side.groups[1]!] ?? side.groups[1]} ${site}` : site;
}

/** Who has the symptom when someone other than the patient is the subject.
 *
 * "남편도 기침을 하고 열이 나요" keeps 남편 for the whole sentence; "저는" or a new
 * sentence brings it back to the patient. */
function otherPersonFor(text: string, evidenceStart: number): string | null {
  let sentenceStart = 0;
  for (const boundary of SENTENCE_SPLIT_PATTERN.finditer(text, 0, evidenceStart)) sentenceStart = boundary.end;
  let person: string | null = null;
  for (const found of PERSON_OR_SELF_PATTERN.finditer(text, sentenceStart, evidenceStart)) {
    person = found.named.person ?? null;
  }
  return person;
}

/** True when the patient says they are not sure about this symptom.
 *
 * The hedge may sit in the symptom's own clause ("기침은 잘 모르겠어요") or in a
 * neighbouring clause that mentions no other symptom ("열이 있는 것 같기도 하고 잘
 * 모르겠어요", "확실하진 않은데 열이 있어요"). */
function isUncertainAt(text: string, evidenceStart: number, positions: Span[]): boolean {
  const spans = subclauseSpans(text);
  const index = spans.findIndex(([start, end]) => start <= evidenceStart && evidenceStart < end);
  if (index < 0) return false;
  const mentionsOtherSymptom = (start: number, end: number) =>
    positions.some(([positionStart]) => start <= positionStart && positionStart < end);
  // "이거 때문에 그런지는 모르겠는데" doubts the cause, not the symptom.
  const hedges = (start: number, end: number) => UNCERTAIN_PATTERN.finditer(text, start, end)
    .some((found) => !CAUSE_DOUBT_PATTERN.search(text.slice(Math.max(start, found.start - 12), found.start)));
  const [ownStart, ownEnd] = spans[index];
  if (hedges(ownStart, ownEnd)) return true;
  for (const neighbour of [index + 1, index - 1]) {
    if (neighbour < 0 || neighbour >= spans.length) continue;
    const [start, end] = spans[neighbour];
    // "숨이 차요 체한 건지는 모르겠어요", "기침이 나요 감기인지 모르겠어요": the next clause doubts
    // something of its own, not the symptom said plainly before it.
    const doubtsItsOwn = search(String.raw`(?:건지|인지|한지)(?:는|도)?\s*(?:잘\s*)?모르`, text.slice(start, end));
    if (!mentionsOtherSymptom(start, end) && !doubtsItsOwn && hedges(start, end)) return true;
  }
  return false;
}

/** Read "가슴이 답답하고 아파요" as "가슴이 답답" + "가슴이 아파". */
function carriedSubjectMatches(text: string, matches: Found[]): [Found[], Span[]] {
  const foundNames = new Set(matches.map(({ rule: symptomRule }) => symptomRule.name));
  const covered = matches.map(({ evidence }): Span => [evidence.start, evidence.end]);
  const carried: Found[] = [];
  const recognizedSpans: Span[] = [];
  let subjects: Array<[string, number]> = [];
  for (const [clauseStart, clauseEnd] of subclauseSpans(text)) {
    const raw = text.slice(clauseStart, clauseEnd);
    const start = clauseStart + raw.length - raw.trimStart().length;
    const clause = rstripChars(text.slice(start, clauseEnd), " ,.!?。");
    const end = start + clause.length;
    if (!clause) continue;
    const clauseSubjects = CLAUSE_SUBJECT_PATTERN.finditer(clause)
      .filter((found) => !NON_SUBJECT_WORD_PATTERN.fullmatch(found.text))
      .map((found): [string, number] => [found.text, start + found.start]);
    if (clauseSubjects.length) {
      subjects = clauseSubjects;
      continue;
    }
    if (!subjects.length || !BARE_PREDICATE_PATTERN.match(clause)) continue;
    if (covered.some(([spanStart, spanEnd]) => spanStart < end && spanEnd > start)) continue;
    const hit = ruleForBorrowedSubject(clause, subjects);
    if (hit === null) continue;
    const [symptomRule, isAbsent, subjectStart] = hit;
    recognizedSpans.push([start, end]);
    if (!foundNames.has(symptomRule.name)) {
      foundNames.add(symptomRule.name);
      carried.push({
        rule: symptomRule,
        evidence: { start, end, text: text.slice(subjectStart, end), carried: true },
        absent: isAbsent,
      });
    }
  }
  return [carried, recognizedSpans];
}

function ruleForBorrowedSubject(clause: string, subjects: Array<[string, number]>): [Rule, boolean, number] | null {
  const predicate = LEADING_ADVERB_PATTERN.sub(clause, "", 1);
  for (const [subject, subjectStart] of [...subjects].reverse()) {
    const candidate = `${subject} ${predicate}`;
    for (const symptomRule of RULES) {
      const mention = firstSymptomMatch(symptomRule.mention, candidate);
      const absent = firstSymptomMatch(symptomRule.absent, candidate);
      const evidence = absent ?? mention;
      if (evidence && evidence.start === 0 && evidence.end > subject.length + 1) {
        return [symptomRule, absent !== null, subjectStart];
      }
    }
  }
  return null;
}

function subclauseSpans(text: string): Span[] {
  const spans: Span[] = [];
  let start = 0;
  for (const boundary of SUBCLAUSE_SPLIT_PATTERN.finditer(text)) {
    // Keep the connective ending (e.g. "아프고") with the clause it belongs to.
    spans.push([start, boundary.start + boundary.text.trimEnd().length]);
    start = boundary.end;
  }
  spans.push([start, text.length]);
  return spans;
}

/** Age, sex, pregnancy, smoking and drinking the patient said about themself. */
function extractProfile(text: string): PatientProfileHints {
  // "남편이 담배를 피워요", "아이가 5살이에요" are about someone else.
  const own = (pattern: Pat) => pattern.finditer(text).find((found) => otherPersonFor(text, found.start) === null) ?? null;
  const ageMatch = own(AGE_PATTERN);
  const ageWord = ageMatch?.groups.slice(1).find(Boolean);
  const age = ageWord ? ageValue(ageWord) : null;
  const sexMatch = own(SEX_PATTERN);
  let sex: PatientProfileHints["sex"] = sexMatch === null ? null : sexMatch.named.female ? "female" : "male";
  const firstLabel = <T>(patterns: Array<[T, Pat]>): T | null =>
    patterns.find(([, pattern]) => own(pattern))?.[0] ?? null;
  const pregnancy = firstLabel(PREGNANCY_PATTERNS);
  if (pregnancy && sex === null) sex = "female";
  return {
    age: age !== null && age >= 0 && age <= 130 ? age : null,
    sex,
    pregnancy,
    smoking: firstLabel(SMOKING_PATTERNS),
    drinking: firstLabel(DRINKING_PATTERNS),
  };
}

/** The patient's history and history said about other people ("엄마가 고혈압이 있어요"). */
function extractMedicalHistory(text: string): [string[], OtherPersonSymptom[]] {
  const denied = new Set(MEDICAL_HISTORY_ABSENT_PATTERN.findall(text).map((value) => value.replace(/\s+/g, " ")));
  const history: string[] = [];
  const others: OtherPersonSymptom[] = [];
  const add = (condition: string, found: Match) => {
    const person = otherPersonFor(text, found.start);
    if (person === null) {
      if (!history.includes(condition)) history.push(condition);
    } else if (others.every((item) => item.person !== person || item.symptom !== condition)) {
      others.push({ person, symptom: condition, source_text: found.text.trim() });
    }
  };
  for (const found of [...LISTED_HISTORY_PATTERN.finditer(text), ...MEDICAL_HISTORY_PATTERN.finditer(text)]) {
    const condition = found.groups[1]!.replace(/\s+/g, " ");
    if (!denied.has(condition)) add(condition, found);
  }
  for (const found of DIAGNOSED_CONDITION_PATTERN.finditer(text)) {
    const value = found.groups[1]!;
    const known = history.filter((item) => value.startsWith(item) || item.startsWith(value));
    if (!known.length && !NOT_A_CONDITION_PATTERN.fullmatch(value)) add(value, found);
  }
  for (const found of SURGERY_PATTERN.finditer(text)) add(`${found.groups[1]} ${found.groups[2]}`, found);
  for (const found of HIGH_READING_PATTERN.finditer(text)) add(`${found.groups[1]} 높음`, found);
  for (const found of WEAK_ORGAN_PATTERN.finditer(text)) add(`${found.groups[1]} 질환`, found);
  for (const found of ADMISSION_PATTERN.finditer(text)) {
    if (!NOT_A_CONDITION_PATTERN.fullmatch(found.groups[1]!)) add(`${found.groups[1]}(입원)`, found);
  }
  return [history, others];
}
