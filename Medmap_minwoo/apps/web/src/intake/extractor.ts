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
  // What makes it worse or better, where it spreads, how long one bout lasts, whether it comes and goes:
  // "누우면 심해짐", "왼팔까지 퍼짐", "한 번에 5분쯤", "오락가락함" (2026-11-27). Only there when said.
  details?: string[];
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
    // "손발은 분명 차가운데", "입맛이 확실히 없어졌어요", "예전보다 많이 차가워졌어요" (2026-11-21, training dev half)
    String.raw`확실히|분명히?|예전보다|전보다|평소보다|어제보다|딱|` +
    // "소변을 보면 매번 피가", "가슴이 묵직하게 아프더니", "숨이 꽉 막히는", "입이 얼마나 마르던지" (2026-11-22, training dev half)
    String.raw`매번|묵직하게|힘들게|꽉|얼마나|` +
    // "허리가 더 아파요", "배가 훨씬 아파요" (2026-11-27: all four were missed), and dialect "억수로 아파예", "쪼매 아파요".
    // 더 only as a word of its own: not 더부룩.
    String.raw`더(?=\s)|훨씬|억수로|억수|쪼매|쫌|간헐적으로|` +
    // More dialect for "very" and "a little": "배가 겁나게 아파요", "무릎이 징하게 쑤셔", "머리가 디게 아파", "배가 싸르르 아파요" (2026-11-28)
    String.raw`디게|겁나게|겁나|엄청시리|징하게|쪼까|째까|솔찬히|허벌나게|오지게|싸르르|살살살|` +
    // How often or how much, said between the body part and the verb: "머리가 꽤 아프네요", "배가 은근히 아파요" (2026-11-06).
    String.raw`꽤|은근히|상당히|무척|몹시|굉장히|엄청나게|너무나|진짜로|정말로|조금씩|약간씩|살짝살짝|` +
    String.raw`가끔씩|가끔|자주|종종|때때로|간혹|이따금|갑자기|점점|여전히|아직도|계속해서|하루\s*종일|항상|늘|부쩍|확|` +
    // How long it has been there: "배는 원래 아파요", "허리가 평소에 좀 아파요" (2026-11-11 user request).
    String.raw`원래(?:는|부터)?|평소(?:에도|에는|에)?|예전부터|옛날부터|전부터|오래전부터|` +
    String.raw`요즘(?:은|에는|에)?|최근(?:에는|에|엔)?|아직(?:은|까지)?|지금(?:은|도)?|이제(?:는)?|현재(?:는)?|` +
    // Said with another symptom: "머리가 아파요 배도 같이 아팠어요" (2026-11-11 phone test).
    String.raw`같이|함께|덩달아|동시에|역시|또|또다시|다시|마찬가지로|` +
    String.raw`살살|콕콕|쿡쿡|꾹꾹|구구|찌릿찌릿|찌릿|욱신욱신|욱신|지끈지끈|지끈|따끔따끔|뻐근하게|찌르듯이?|` +
    // How bad it is, said between the body part and the verb: "배가 참을 만하게 아파요".
    String.raw`데굴데굴|참을\s*만하게|견딜\s*만하게|죽을\s*(?:것\s*)?같이|미칠\s*(?:것\s*)?같이|` +
    String.raw`(?:참을\s*만한|견딜\s*만한|구를|죽을|미칠|못\s*참을|잠을\s*못\s*잘)\s*(?:정도로|만큼)|` +
    // "머리가 깨질 것처럼 아파요", "허리가 끊어질 듯이 아파요", "배가 보통 정도로 아파요" (2026-11-21, 360 set odd half).
    String.raw`(?:깨질|터질|쪼개질|빠개질|끊어질|찢어질|부서질|으스러질|뽑힐|타는|찌르는)\s*(?:것\s*)?(?:처럼|같이|듯이?)|` +
    String.raw`(?:보통|중간|적당한|어느|그럭저럭)\s*정도로|` +
    String.raw`심하(?:지는|진|지)\s*않(?:은데|지만|고))`
);
const INTENSITY_PHRASE = String.raw`(?:${INTENSITY_WORD}\s*)*`;
const IMPROVEMENT_PHRASE = (
    String.raw`(?:(?:조금|좀|많이|전보다)\s*)?` +
    String.raw`(?:괜찮아졌|나아졌|호전됐|좋아졌|덜해졌|줄었)`
);
// "배가 좀 나아졌어요", "머리가 더 심해졌어": a body part with how it changed names the pain there.
// What brings a symptom on or eases it (OPQRST, 2026-11-27; see attachDetails). Also keeps "누우면 더 아파요" from
// reading as a trend.
const DETAIL_CONDITION = (
    String.raw`누우면|누워\s*있으면|앉아\s*있으면|앉으면|(?:아침에\s*)?(?:일어나면|일어날\s*때)|일어설\s*때|자세를\s*바꾸면|자세를\s*바꿀\s*때|움직이면|움직일\s*때|걸으면|걸을\s*때|뛰면|` +
    String.raw`계단(?:을)?\s*(?:오를\s*때|오르면)|운동하면|운동할\s*때|숨(?:을)?\s*(?:크게\s*)?(?:쉴\s*때|들이쉬면)|기침할\s*때|기침하면|` +
    // "물을 많이 마시면" (2026-11-28): how much may sit between the thing and the verb.
    String.raw`(?:[가-힣]{1,6}\s+(?:걸|것을|거)|[가-힣A-Za-z0-9]{1,10}(?:을|를)?)\s*(?:(?:많이|너무|급하게|빨리)\s*)*` +
    String.raw`(?:먹(?:으면|고\s*나면|은\s*뒤에?|을\s*때)|마시면|마시고\s*나면|마신\s*뒤에?|마실\s*때)|식사\s*후에?|식후에?|공복에|배고플\s*때|(?:(?:배|복부|명치|아랫배|윗배|가슴|허리|머리)(?:를|을)\s*)?(?:누르면|만지면)|` +
    String.raw`(?:허리를\s*)?숙이면|구부리면|고개를\s*돌리면|찬\s*바람(?:을)?\s*쐬면|추우면|스트레스(?:를)?\s*받으면|` +
    String.raw`(?:소변|대변)(?:을)?\s*볼\s*때|쉬면|쉬고\s*나면|자고\s*나면|따뜻하게\s*하면|찜질하면`
);
const CHANGE_PHRASE = (
    String.raw`(?:${IMPROVEMENT_PHRASE}|(?:(?:더|점점|많이|훨씬)\s*)?(?:심해졌|악화됐|나빠졌))`
);
const RESOLVED_STATE = (
    String.raw`(?:(?:완전히\s*)?(?:사라졌|없어졌|멈췄|가라앉았)|` +
    String.raw`(?:다|완전히)\s*(?:나았|괜찮아졌|좋아졌))`
);
// Said between the part and "없어요 / 안 아파요": "배는 원래 안 아파요", "머리는 요즘 별로 안 아파요" (2026-11-11, matrix of
// parts × modifiers × endings; before this only 이제는·지금은 fitted there).
const NOW_ADVERB = (
    String.raw`(?:(?:이제는?|이젠|지금은|현재는|요즘(?:은|에는)?|최근(?:에는|엔)?|아직(?:은|까지는?)?|원래(?:는)?|` +
    String.raw`평소(?:에는|에도|에)?|별로|딱히|그렇게|그다지|크게|많이|좀|자주|가끔|전혀|하나도|조금도|같이|함께|역시|또|` +
    // "가슴 통증은 확실히 없어요", "기침은 진짜 없어요": read as present before (2026-11-28 check of item 4).
    String.raw`확실히|분명히?|정말(?:로)?|진짜(?:로)?|절대(?:로)?|완전히|아예)\s*)*`
);
const PARTICLE = String.raw`(?:은|는|이|가|도|을|를)?`;
const JOINT_PART = String.raw`무릎|어깨|발목|손목|팔꿈치|고관절|골반|손가락\s*관절|손가락|발가락|턱관절|턱|관절`;
const ABSENT_ENDING = String.raw`${NOW_ADVERB}(?:없|${RESOLVED_STATE})`;
// "전혀 아프지 않아요", "하나도 안 아파요": none at all is still "not painful" (2026-11-06).
const NOT_PAINFUL = String.raw`(?:(?:전혀|하나도|조금도)\s*)?(?:(?:더\s*이상\s*)?안\s*(?:아프|아파|아픈)|아프지(?:는|도)?\s*않|아프진\s*않)`;
const INLINE_ONSET = (
    String.raw`(?<![가-힣A-Za-z0-9])(?:어젯밤(?:부터)?|처음(?:엔|에는|에)|(?:지난|저번|이번)\s*(?:주말|주|달)(?:부터|쯤)?|며칠\s*(?:전부터|전|째)|` +
    String.raw`(?:오늘|어제|그제|그저께|엊그제)\s*` +
    String.raw`(?:아침|점심|저녁|밤|새벽)(?:부터)?|` +
    String.raw`(?:오늘|어제|그제|그저께|엊그제)(?:부터)?|` +
    String.raw`(?:하루|이틀|사흘|나흘|닷새|엿새|이레|여드레|아흐레|열흘)` +
    String.raw`(?:\s*(?:전부터|전|동안|째))?|` +
    String.raw`(?:\d+|일|이|삼|사|오|육|칠|팔|구|십)\s*` +
    String.raw`(?:시간|일|주|개월|달)(?:\s*(?:전부터|전|동안|째))?)`
);


// Pain words from Korean pain-vocabulary studies (K-CPAT cancer-pain words, 2003; pain pictogram study, AODR) said of a
// listed part: "배가 쥐어짜는 것 같아요", "허리가 끊어질 것 같아요", "가슴이 뜨끔해요" (2026-11-27).
const PAIN_DESCRIPTOR = String.raw`아리|아려|아렸|얼얼|쥐어짜|후벼|도려|뜨끔|짓누르|짓눌|꼬집듯|뻗치듯|` +
    String.raw`(?:끊어질|찢어질|터질|빠개질|쪼개질|깨질|뒤집어질)\s*(?:것|듯)`;

// A cramp in one muscle is 근육 경련, not the danger sign 경련 (a seizure): "햄스트링 부위가 간헐적으로 경련이 오는데",
// "종아리에 경련이 났어요" (2026-11-28). The whole body ("온몸에", "팔다리가") stays 경련.
const MUSCLE_CRAMP_BEFORE = String.raw`(?<![가-힣])(?:햄스트링|종아리|장딴지|허벅지|다리|발바닥|발가락|발|손가락|손|팔뚝|팔|눈꺼풀|눈\s*밑|입가|볼|옆구리|등|어깨|허리|목|근육)` +
    String.raw`(?:\s*(?:근육|부위|쪽))?(?:이|가|에|도|에서)?(?![가-힣])\s*(?:[가-힣]+\s+){0,2}?`;

const RULES: Rule[] = [
    rule(
        "두통",
        pat(
            String.raw`머리(?:랑|와|하고)\s*(?:배|복부|속)(?:가|는|도)?\s*` +
            String.raw`(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}(?:아프|아파|아팠|아픈)|` +
            // "머리에 약간의 통증이 있어요", "머리 아픔은 어제부터" (2026-11-22)
            String.raw`두통|머리(?:에)?\s*(?:${INTENSITY_PHRASE}|약간의\s*)통증|머리(?:가|는|도|야)?\s*(?:${INLINE_ONSET}\s*)?` +
            String.raw`(?:같이\s*|함께\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|아픔|지끈|욱신|띵|조이|조여|${PAIN_DESCRIPTOR})|` +
            // "골이 아파요", "뒤통수가 지끈거려요" (119 emergency-call expressions, 2016)
            // "뒷골이 땡겨요" (뒷머리, 2026-11-28 check of item 6)
            String.raw`(?<![가-힣])뒷머리(?:가|도)?\s*${INTENSITY_PHRASE}(?:당기|당겨|땡기|땡겨)|` +
            String.raw`(?:(?<![가-힣])골|(?<![가-힣])대가리|뒤통수|정수리)(?:이|가|도)?\s*${INTENSITY_PHRASE}(?:아프|아파|아팠|아픈|지끈|욱신|띵|${PAIN_DESCRIPTOR})|` +
            String.raw`(?:두통|머리)(?:이|가|은|는|도)?\s*${CHANGE_PHRASE}`
        ),
        pat(
            String.raw`(?:두통|머리\s*통증)(?:은|이|도)?\s*${NOW_ADVERB}(?:없|아니)|` +
            String.raw`머리(?:가|는|도)?\s*${NOW_ADVERB}${NOT_PAINFUL}|` +
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
            // "열이 받쳐서" is anger, not fever.
            String.raw`(?<![가-힣])열(?!(?:이|을)?\s*(?:받[치쳐혀]|뻗치))(?=\s*$|이|은|도|과|이랑|랑|하고|까지|감|나|났|있|오르|올라|\s+(?:나|났|있|오르|올라|조금|좀|많이))` +
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
            // "숨이 좀 턱까지 차서", "숨이 좀 힘들게 쉬어지네요", "숨 쉬기가 너무 힘들어졌어요" (2026-11-22)
            String.raw`숨(?:이|은|도)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}(?:턱(?:까지|끝까지)\s*)?(?:차|찬|찼|가빠|가쁘|가쁜|막혀|막히)|` +
            String.raw`숨(?:이)?\s*${INTENSITY_PHRASE}힘들게\s*쉬어|` +
            String.raw`숨(?:을)?\s*(?:헐떡|몰아\s*쉬)|숨(?:이|소리가)?\s*${INTENSITY_PHRASE}거칠|` +
            String.raw`호흡(?:이)?\s*${INTENSITY_PHRASE}(?:가빠|가쁘|가파르|힘들|급하|급해)|호흡이\s*${INTENSITY_PHRASE}곤란|` +
            String.raw`숨(?:을)?\s*쉬기(?:가)?\s*(?:${INTENSITY_PHRASE}(?:힘들|어렵|어려)|${IMPROVEMENT_PHRASE})|` +
            // "숨 쉬는 게 좀 힘들어졌어", "숨 쉴 때 좀 힘들어요" (2026-11-06)
            String.raw`숨\s*(?:쉬는\s*(?:게|것이?|것도)|쉴\s*때(?:마다)?)\s*${INTENSITY_PHRASE}(?:힘들|어렵|어려|불편|답답)|` +
            String.raw`숨쉬기가\s*(?:전보다\s*)?편해졌|` +
            String.raw`호흡곤란(?:이|은|도)?\s*(?:${IMPROVEMENT_PHRASE})?|` +
            String.raw`숨찬\s*증상(?:이|은|도)?\s*${IMPROVEMENT_PHRASE}`
        ),
        pat(
            String.raw`숨(?:은|이|도)?\s*${NOW_ADVERB}(?:안\s*차|차지\s*않)|` +
            String.raw`숨\s*(?:쉬는\s*(?:것|건|거|데)|쉬기)(?:은|는|도|가|에)?\s*${NOW_ADVERB}(?:괜찮(?!아졌)|문제\s*없|불편하지\s*않)|` +
            String.raw`(?:호흡곤란|숨찬\s*증상)(?:은|이|도)?\s*${NOW_ADVERB}(?:없|${RESOLVED_STATE})`
        ),
    ),
    rule(
        "가슴 답답함",
        pat(
            String.raw`가슴(?:이|은|만|도)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:답답|조이|조여|눌리)|흉부(?:가|는|만|도)?\s*(?:답답|압박)|` +
            // "답답해요" with no part of its own, after the chest was named a sentence or so before: "기지개를 펴면 가슴에서
            // 소리가 나요. 원래는 답답한데..." (2026-11-11 phone test). Not 속·코·마음·숨 답답, or 답답해서 (frustrated).
            String.raw`(?<=가슴[^가-힣]?[가-힣\s.,]{0,60})(?<![가-힣])(?<!(?:속|코|마음|맘|숨|배|목|명치|가슴)(?:이|가|은|는|도|만)?\s*)` +
            String.raw`답답(?:하|해|한|함)(?!서)`
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
            String.raw`(?:배|복부|(?<![가-힣])속|명치|옆구리|배꼽\s*(?:아래|밑|위|주변|주위|근처)|갈비(?:뼈)?\s*(?:밑|아래))(?:\s*쪽)?(?:이|가|는|도|야|를)?\s*(?:${INLINE_ONSET}\s*)?` +
            String.raw`${INTENSITY_PHRASE}(?:아프|아파|아팠|아픈|쑤시|쑤셔|쑤신|뒤틀|꼬여|꼬이|${PAIN_DESCRIPTOR})(?<!터질\s*(?:것|듯))|` +
            // "폭통": on-device STT's usual spelling of "복통".
            String.raw`복통|폭통|(?:배|복부|명치|옆구리)\s*통증|배탈|위경련|위통|(?<![가-힣])(?:배|복부|명치|아랫배|윗배)(?:를|을)\s*(?:${INTENSITY_PHRASE})?(?:누르면|만지면)\s*${INTENSITY_PHRASE}(?:아프|아파|아팠|아픈)`
        ),
        pat(
            String.raw`(?:배|복부|(?<![가-힣])속|명치|옆구리)(?:이|가|은|는|도)?\s*${NOW_ADVERB}${NOT_PAINFUL}|` +
            String.raw`복통(?:은|이|도)?\s*${NOW_ADVERB}(?:없|${RESOLVED_STATE})|` +
            String.raw`(?:배|복부|속)\s*통증(?:은|이|도)?\s*${NOW_ADVERB}(?:없|${RESOLVED_STATE})`
        ),
        "복부",
    ),
    rule(
        "구토",
        pat(
            String.raw`구토\s*횟수(?:가|는|도)?[^,.!?。]{0,20}(?:줄었|늘었)|` +
            String.raw`구토|토(?:를|가)?\s*(?:했|해|하|했었)|오바이트|게워|게웠`
        ),
        pat(
            String.raw`구토(?:는|가|도|를)?\s*${NOW_ADVERB}(?:없|안\s*(?:했|해|하)|하지\s*않|${RESOLVED_STATE})|` +
            String.raw`토(?:는|를|도)?\s*${NOW_ADVERB}(?:안\s*했|하지\s*않)|` +
            String.raw`토한\s*적(?:은|도|이)?\s*없|` +
            String.raw`구토\s*증상(?:은|이|도)?\s*${NOW_ADVERB}${RESOLVED_STATE}`
        ),
    ),
    rule(
        "흉통",
        pat(
            String.raw`흉통|(?:가슴|흉부)(?:에)?\s*통증|가슴(?:\s*(?:밑|아래)(?:\s*쪽)?)?(?:이|은|도|을)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            // Not "가슴이 터질 것 같이 기뻐요", "가슴이 찢어질 것 같아요": as often a feeling as a pain.
            String.raw`(?:아프|아파|아팠|아픈|찌르|찌릿|콕콕|쑤시|쑤셔|쥐어짜|${PAIN_DESCRIPTOR})(?<!(?:터질|찢어질)\s*(?:것|듯))`
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
            // 목 as a word of its own (2026-11-06): 뒷목·손목 are not the throat. 목구멍 is.
            String.raw`인후통|(?<![가-힣])목\s*통증|목감기|(?<![가-힣])(?:목구멍|목)(?:이|은|도)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|따끔|따끈|따가|따갑|칼칼|부었|부어|붓)|` +
            String.raw`(?:인후통|(?<![가-힣])목)(?:이|은|도)?\s*${CHANGE_PHRASE}|` +
            String.raw`침(?:을)?\s*삼키기(?:가)?\s*(?:힘들|어렵|아프)|침(?:을)?\s*삼킬\s*때(?:마다)?\s*(?:아프|아파|따끔)`
        ),
        pat(
            String.raw`인후통${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`(?<![가-힣])(?:목구멍|목)(?:은|이|도)?\s*${NOW_ADVERB}${NOT_PAINFUL}`
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
        // "코가 좀 답답해요", "콧속이 꽉 막히신지", "코 속이 왜 이렇게 답답한지" (2026-11-22)
        pat(String.raw`코\s*막힘|콧\s*막힘|코마킹|코마킨|(?<![가-힣])(?:코|콧속|코\s*속)(?:가|이|는|도)?\s*${INTENSITY_PHRASE}(?:왜\s*이렇게\s*)?(?:[막박](?:혀|히|혔|힌)|답답)`),
        pat(
            String.raw`코\s*막힘${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`(?<![가-힣])(?:코|콧속)(?:는|가|도)?\s*${NOW_ADVERB}(?:안\s*막|막히지\s*않|안\s*답답|답답하지\s*않)`
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
        pat(String.raw`오한|으슬으슬|오슬오슬|한기|춥고\s*떨|몸이\s*(?:덜덜\s*)?떨`),
        pat(String.raw`(?:오한|한기)${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "근육통",
        pat(
            // 몸 as a word of its own (2026-11-06): 잇몸 is the gums.
            // "전신이 쑤시는 느낌", "몸 전체가 묵직하게 아픈", "여기저기 쑤시는 느낌" (2026-11-22)
            String.raw`근육통|몸살|(?<![가-힣])(?:(?:온\s*)?삭신|온몸|몸\s*전체|몸|전신|근육|팔다리)(?:이|가|은|도)?\s*(?:다\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:쑤시|쑤셔|쑤신|결리|결려|아프|아파|아픈)|(?<![가-힣])(?:몸\s*)?여기저기(?:가)?\s*${INTENSITY_PHRASE}(?:쑤시|쑤셔|쑤신|결리|결려)`
        ),
        pat(
            String.raw`(?:근육통|몸살)${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`(?<![가-힣])(?:온몸|몸|근육)(?:은|이|도)?\s*${NOW_ADVERB}(?:${NOT_PAINFUL}|안\s*쑤|쑤시지\s*않)`
        ),
    ),
    rule(
        "요통",
        pat(
            String.raw`(?:요통|허리)(?:가|는|도)?\s*${CHANGE_PHRASE}|` +
            String.raw`요통|허리\s*통증|허리(?:\s*(?:아래|위|밑)\s*쪽?(?:이|은|도|에)?)?(?:가|는|도)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|쑤시|쑤셔|결리|결려|뻐근|당기|당겨|땅기|땅겨|삐끗|${PAIN_DESCRIPTOR})`
        ),
        pat(
            String.raw`(?:요통|허리\s*통증)${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`허리(?:는|가|도)?\s*${NOW_ADVERB}${NOT_PAINFUL}`
        ),
        "허리",
    ),
    rule(
        "어지러움",
        pat(String.raw`어지러|어지럽|어지럼|어질어질|어찔|현기증|핑\s*(?:돌|돈)|(?:빙빙|빙글빙글)\s*(?:돌|돈)`),
        pat(
            String.raw`(?:어지럼증?|어지러움|현기증)${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`${NOW_ADVERB}안\s*어지러|어지럽지\s*않|` +
            // "어질어질한 건 없어요" (2026-11-28 check of item 5)
            String.raw`어질어질(?:한\s*(?:건|것은|거는|느낌은?)\s*${ABSENT_ENDING}|하지(?:는|도)?\s*않)`
        ),
    ),
    rule(
        "메스꺼움",
        // "메스 거예요", "매스 꺼워요": turbo's split spellings of 메스꺼워요 (2026-11-11 phone test).
        pat(String.raw`[메매]스\s[꺼거](?:워|웠|운|요|예요|에요)|[메매]스거(?:워|웠|운|요|예요|에요)|[메매]스꺼|[메매]스껍|메슥|미식거|미식미식|울렁|구역질|구역감|헛구역|토할\s*(?:것\s*)?같|니글|느글`),
        pat(
            String.raw`(?:메스꺼움|구역감|구역질|울렁거림)${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`메스껍지\s*않|안\s*메스꺼|울렁거리지\s*않`
        ),
    ),
    rule(
        "설사",
        // "술사도 세번 했어요", "설싸": STT spellings of 설사, only with a count or 했/해 so 술 (alcohol) is not read.
        pat(String.raw`설사|(?<![가-힣])(?:술사|설싸|썰사)(?:를|도|가|는)?\s*(?:(?:\d+|한|두|세|네|다섯|여러)\s*번\s*)?(?:했|해|하|나)|` +
          String.raw`(?<!소)(?:대변|변)(?:이|을|도)?\s*(?:묽|물\s*같)|물\s*같은\s*변`),
        pat(
            String.raw`설사${PARTICLE}\s*${NOW_ADVERB}(?:없|안\s*(?:했|해|하)|하지\s*않|멈췄|${RESOLVED_STATE})|` +
            String.raw`설사(?:를\s*)?한\s*적(?:은|도|이)?\s*없`
        ),
    ),
    rule(
        "변비",
        pat(String.raw`변비|(?<!소)(?:대변|변)(?:을|이|도)?\s*(?:잘\s*)?(?:못\s*(?:봤|봐|보|본)|안\s*나와|안\s*나오)|` +
          // "대변도 전혀 안 나오고", "대변은 전혀 못 보는", "변 보는 게 진짜 어렵고" (2026-11-06)
          String.raw`(?<![가-힣])(?:대변|배변|변)(?:을|이|도|은)?\s*(?:(?:${INTENSITY_WORD}|전혀|아예|딱히)\s*)*` +
          String.raw`(?:못\s*(?:봤|봐|보|본)|안\s*나와|안\s*나오|나오지\s*않)|` +
          String.raw`(?<![가-힣])(?:대변|배변|변)(?:을)?\s*보(?:는\s*(?:게|것이?)|기(?:가)?)\s*${INTENSITY_PHRASE}(?:거의\s*)?(?:어렵|어려|힘들|안\s*되)|` +
          // "대변도 딱히 나오는 게 없어요", "화장실 가는 게 완전히 막혔어" (training dev half, 2026-11-27)
          String.raw`(?<![가-힣])(?:대변|변)(?:이|도)?\s*(?:딱히\s*|전혀\s*)?나오는\s*(?:게|것이?)\s*없|` +
          String.raw`화장실\s*(?:가는\s*(?:게|것이?)|가기가)\s*${INTENSITY_PHRASE}(?:완전히\s*)?막혔`),
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
            // "기운이 정말 없어요" (2026-11-28)
            String.raw`피곤|피로|기운(?:이|도)?\s*${INTENSITY_PHRASE}(?:하나도\s*|전혀\s*)?없|(?:몸에|온몸에)\s*힘(?:이)?\s*${INTENSITY_PHRASE}없|기력(?:이|도)?\s*${INTENSITY_PHRASE}없|무기력|나른|` +
            String.raw`몸(?:이)?\s*(?:천근만근|무거|무겁)|녹초|지쳐|지친다|기진맥진|탈진`
        ),
        pat(
            String.raw`(?:피로감?|피곤함)${PARTICLE}\s*${ABSENT_ENDING}|` +
            String.raw`안\s*피곤|피곤하지\s*않`
        ),
    ),
    rule(
        "두근거림",
        pat(
            String.raw`두근|벌렁|심계항진|심장(?:이|도)?\s*(?:자꾸|막|마구|너무|세게|쿵쾅쿵쾅)\s*뛰|심장(?:이|도|은)?\s*${INTENSITY_PHRASE}(?:빨리|빠르게|불규칙하게|쿵쾅|펄떡)`
        ),
        pat(
            String.raw`(?:두근거림|심계항진)${PARTICLE}\s*${ABSENT_ENDING}|안\s*두근|두근거리지\s*않`
        ),
        "가슴",
    ),
    rule(
        "저림",
        pat(String.raw`저려|저리|저림|저린|저릿|감각(?:이)?\s*(?:없|둔하|둔해|무뎌)`),
        pat(String.raw`저림${PARTICLE}\s*${ABSENT_ENDING}|저리지\s*않|안\s*저려|안\s*저리`),
    ),
    rule(
        "소화불량",
        pat(
            String.raw`소화\s*불량|소화(?:가)?\s*${INTENSITY_PHRASE}(?:잘\s*)?안\s*(?:돼|되|된|됐)|체했|체한|체기|체해|급체|얹혔|얹힌|얹혀|` +
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
            String.raw`속쓰림|(?:속|가슴|명치|윗배|위)(?:이|가|도|까지)?\s*${INTENSITY_PHRASE}(?:쓰려|쓰리|쓰린|쓰림|쓰라|타는)|` +
            // "명치가 쓰기로": turbo's "쓰리고" (2026-11-11 phone test), only right after 명치/속.
            String.raw`(?<![가-힣])(?:명치|속)(?:이|가|도)?\s*쓰기(?:로|고)|` +
            // "속이 따갑고", "속이 화끈거려요", "속에서 불이 나는 것 같아요" (2026-11-06)
            String.raw`(?<![가-힣])속(?:이|도)?\s*${INTENSITY_PHRASE}(?:따갑|따가|화끈)|(?<![가-힣])속에서\s*불|` +
            String.raw`신물(?:이)?\s*(?:올라|넘어)|위산\s*역류|` +
            // "위가 많이 불편하고 쓰린 느낌이" (training dev half, 2026-11-27): a few words between 위/속 and 쓰린.
            // Not "속이 안 좋아서 상처가 쓰려요", where another part is what stings.
            String.raw`(?<![가-힣])(?:위|속)(?:가|이)\s*(?:[가-힣]+\s+){1,3}?` +
            String.raw`(?<!(?:상처|피부|목|눈|입|혀|손|발|다리|무릎|팔|코)(?:가|이|도)?\s*)(?:쓰린|쓰려|쓰리|쓰림)`
        ),
        pat(
            String.raw`속쓰림${PARTICLE}\s*${ABSENT_ENDING}|(?:속|위)(?:은|이|는|도)?\s*${NOW_ADVERB}(?:안\s*쓰려|쓰리지\s*않)`
        ),
        "복부",
    ),
    rule(
        "식욕부진",
        pat(
            // "입맛이 전혀 없어요", "식욕도 확 줄었어요", "밥맛이 아예 없다", "밥 생각이 없어요" (2026-11-06)
            String.raw`식욕부진|(?:식욕|입맛|밥\s*맛)(?:이|도)?\s*(?:(?:${INTENSITY_WORD}|전혀|아예|완전히|통|별로|하나도|조금도|영)\s*)*(?:없|떨어|뚝|줄었|제로)|` +
            String.raw`밥\s*생각(?:이|도)?\s*(?:(?:전혀|별로|통)\s*)?없|` +
            // "먹는 게 별로 흥미가 없어졌어요", "식사하고 싶은 마음이 전혀 없네요" (2026-11-22)
            String.raw`먹는\s*(?:게|것에|거에)\s*(?:별로\s*)?흥미(?:가)?\s*없|(?:식사|밥\s*먹고|먹고)(?:하고)?\s*싶은\s*마음(?:이|도)?\s*(?:(?:전혀|별로)\s*)?없|` +
            // "목이 막힌 것처럼 밥이 안 넘어가요" is trouble swallowing (삼킴 곤란), not appetite (2026-11-09 phone test).
            String.raw`밥(?:을|이)?\s*(?:잘\s*)?(?:못\s*먹|먹기\s*싫)|` +
            String.raw`(?<!목[가-힣\s]{0,6}(?:막|걸)[가-힣\s]{0,12})밥(?:을|이)?\s*(?:잘\s*)?안\s*넘어가`
        ),
        pat(
            String.raw`(?:식욕|입맛)(?:은|이|도)?\s*${NOW_ADVERB}(?:괜찮|있|좋|돌아)|식욕부진${PARTICLE}\s*${ABSENT_ENDING}`
        ),
    ),
    rule(
        "불면",
        pat(
            String.raw`불면|잠(?:을|이|은|도)?\s*(?:잘\s*)?(?:못\s*(?:자|잤|잔|들)|안\s*(?:와|온|오)|설쳐|설쳤)|` +
            // "잠이 제대로 오지 않아요", "잠 못 이루고", "잠을 설치고" (2026-11-06)
            String.raw`(?<![가-힣])잠(?:을|이|은|도)?\s*(?:(?:${INTENSITY_WORD}|전혀|제대로|잘)\s*)*` +
            String.raw`(?:못\s*(?:자|잤|잔|들|이루)|안\s*(?:와|온|오)|오지\s*않|이루지\s*못|설치|설쳐|설쳤)|` +
            String.raw`자다가\s*(?:자꾸\s*|계속\s*)?깨`
        ),
        pat(String.raw`잠(?:은|을|도)?\s*${NOW_ADVERB}잘\s*(?:자|잤|자요)|불면${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "부종",
        pat(
            String.raw`부종|붓기|부기(?=가|는|도|\s|$)|(?<![가-힣])(?:다리|발|발목|얼굴|손|손가락|눈두덩|눈|입술|몸)(?:이|가|은|는|도)?\s*${INTENSITY_PHRASE}(?:퉁퉁\s*)?` +
            String.raw`(?:부었|부어|붓|부은)`
        ),
        pat(String.raw`(?:부종|붓기|부기)${PARTICLE}\s*${NOW_ADVERB}(?:없|빠졌|가라앉았|${RESOLVED_STATE})|` +
            String.raw`(?<![가-힣])(?:다리|발|발목|얼굴|손|손가락|눈두덩|눈|입술|몸)(?:이|가|은|는|도)?\s*${NOW_ADVERB}(?:안\s*(?:부었|부어|붓)|붓지\s*않)`),
    ),
    rule(
        "귀 통증",
        pat(
            String.raw`귀(?:가|는|도)?\s*${CHANGE_PHRASE}|` +
            String.raw`귀(?:에|도)?\s*통증|귀(?:가|는|도)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|아픔|찌르|욱신)`
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
            // "왼쪽 윗니가 찌르듯 아프네요", "이가 왼쪽에 좀 아프고", "이빨 하나가 심하게", "치아에 통증이" (2026-11-22)
            String.raw`치통|(?:(?<![가-힣])이|이빨|치아|잇몸|어금니|윗니|아랫니|앞니)(?:\s*하나)?(?:가|이|는|도)?\s*(?:(?:왼|오른)쪽(?:에)?\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|시려|시리|시큰|욱신|쑤셔)|(?:치아|이빨|어금니|윗니|아랫니|잇몸)(?:에|가|도)?\s*통증`
        ),
        pat(
            String.raw`치통${PARTICLE}\s*${ABSENT_ENDING}|(?:(?<![가-힣])이|이빨|치아|잇몸)(?:가|은|이|는|도)?\s*${NOW_ADVERB}${NOT_PAINFUL}`
        ),
        "치아",
    ),
    rule(
        "식은땀",
        pat(String.raw`식은땀|진땀|(?<![가-힣])땀(?:이|을|도)?\s*(?:나|났|흘|흐르)`),
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
            String.raw`수전증|(?:손|팔|다리|손발|입술|턱|몸)(?:이|가|도)?\s*(?:덜덜\s*|부들부들\s*|${INTENSITY_WORD}\s*)*` +
            String.raw`(?:떨려|떨리|떨림|떨린)`
        ),
        pat(String.raw`떨림${PARTICLE}\s*${ABSENT_ENDING}|(?:안\s*떨|떨리지\s*않)`),
    ),
    rule(
        "이명",
        // "귀에서 가끔 이상한 소리도 들리네요", "귀에서 계속 잡음이 들려요" (2026-11-06)
        pat(String.raw`이명|귀(?:에서)?\s*(?:삐|윙|웅웅|소리(?:가)?\s*(?:나|들려))|귀(?:가)?\s*울려|귀(?:가)?\s*울리|` +
          String.raw`귀(?:에서|에)(?:는|도)?\s*${INTENSITY_PHRASE}(?:뭔가\s*)?(?:이상한\s*)?(?:소리|잡음)(?:가|도|이)?\s*${INTENSITY_PHRASE}(?:나|들려|들리)`),
        pat(String.raw`이명${PARTICLE}\s*${ABSENT_ENDING}`),
        "귀",
    ),
    rule(
        "코피",
        // "코에서 조금씩 피가 나는", "피가 코에서 자주 나와요" (2026-11-22)
        pat(String.raw`코피|코에서\s*${INTENSITY_PHRASE}피|피(?:가)?\s*코에서`),
        pat(String.raw`코피${PARTICLE}\s*${NOW_ADVERB}(?:없|안\s*나|멈췄|${RESOLVED_STATE})`),
        "코",
    ),
    rule(
        "객혈",
        pat(
            String.raw`객혈|각혈|(?:기침|가래)(?:할\s*때|하면|에|에서)?\s*(?:피|핏덩이)(?:가|도)?\s*(?:섞|나|묻)|` +
            // "기침할 때마다 피가 나와", "기침할 때 가끔씩 피가 섞여", "기침하면서 피가 나오긴" (2026-11-06)
            String.raw`기침(?:할\s*때(?:마다)?|하면(?:서)?|하면서)\s*${INTENSITY_PHRASE}(?:피|핏덩이|핏방울)(?:가|도|이)?\s*${INTENSITY_PHRASE}(?:섞|나|묻)|` +
            String.raw`피(?:가)?\s*섞인\s*(?:가래|기침)|피기침|(?:목|목구멍)에서\s*피(?:가)?\s*(?:올라|넘어)`
        ),
        pat(String.raw`(?:객혈|각혈)${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "토혈",
        // "피를 토한 것 같기도 해요" (2026-11-27): unsure, but a danger symptom to keep.
        pat(String.raw`토혈|피(?:를)?\s*토했|피(?:를)?\s*토해|피(?:를)?\s*토한|토(?:에|한\s*것에)\s*피|피가\s*섞인\s*구토|토할\s*때\s*피|` +
          // "구토할 때마다 피가 섞여", "피 섞인 구토" (2026-11-06)
          String.raw`구토(?:할\s*때(?:마다)?|하면서)\s*${INTENSITY_PHRASE}피|피\s*섞인\s*구토`),
        pat(String.raw`토혈${PARTICLE}\s*${ABSENT_ENDING}|피(?:는|를|도)?\s*(?:안\s*토(?:했|해)|토하지\s*않)`),
    ),
    rule(
        "혈변",
        pat(
            String.raw`혈변|(?:대변|(?<!소)변)(?:에|에서)\s*피|피(?:가)?\s*섞인\s*(?:대변|(?<!소)변)|` +
            // "변에 약간의 피 같은 것이", "변에 까만 색 피가" — blood said, not only a color (2026-11-06)
            String.raw`(?:대변|(?<![가-힣])변)(?:에|에서)\s*(?:약간의?\s*|조금\s*|까만\s*색?\s*|검은\s*색?\s*|빨간\s*색?\s*)?피|` +
            String.raw`(?:검은|까만|짜장\s*같은)\s*(?:색\s*)?(?:대변|변)|피똥|(?:대변|변)(?:이)?\s*(?:검게|까맣게)|` +
            // Red said alone: "변에 붉은색이 섞여", "변을 보면 빨간 색이 있긴 한데" (training dev half). Read since 혈변
            // left the red 119 notice (user decision, 2026-11-27); the patient confirms it. Not 소변.
            String.raw`(?<![가-힣])(?:대변|변)(?:에|에서|을\s*보면|을?\s*볼\s*때)\s*${INTENSITY_PHRASE}(?:가끔\s*)?(?:빨간|붉은|시뻘건|새빨간)\s*(?:색|게|것|빛)?|` +
            String.raw`(?<![가-힣])(?:대변|변)(?:이|도)?\s*${INTENSITY_PHRASE}(?:빨개|빨갛|붉어|붉게)`
        ),
        pat(String.raw`혈변${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "혈뇨",
        // "소변 볼 때 피가 좀 섞여", "소변을 보면 매번 피가", "소변 볼 때마다 빨갛게", "소변에 빨간 흔적이" (2026-11-22)
        // "소변이 빨개요", "소변 색이 좀 빨개졌어요" (user request, 2026-11-27)
        pat(String.raw`혈뇨|피오줌|(?:소변|오줌)(?:에|에서|이)?\s*(?:피|빨갛|붉|빨간)|` +
          String.raw`(?:소변|오줌)(?:\s*색)?(?:이|도)?\s*${INTENSITY_PHRASE}(?:빨개|새빨|시뻘|붉어|붉게)|` +
          String.raw`(?:소변|오줌)(?:을)?\s*(?:볼\s*때(?:마다)?|보면|보는\s*동안)\s*${INTENSITY_PHRASE}(?:피(?:가|도)|빨갛게|빨간\s*(?:게|피))`),
        pat(String.raw`혈뇨${PARTICLE}\s*${ABSENT_ENDING}|(?:소변|오줌)(?:\s*색)?(?:은|는|이|도)?\s*(?:안\s*빨개|안\s*붉|빨갛지\s*않|괜찮|정상|맑)`),
    ),
    rule(
        "배뇨통",
        pat(
            // "소변 볼 때마다 통증이 있어요", "소변 볼 때도 조금 아프네요" (2026-11-06)
            String.raw`배뇨통|(?:소변|오줌)(?:을)?\s*(?:볼|눌)\s*때\s*(?:마다|도)?\s*${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아픔|통증|따끔|따가|따갑|찌릿|화끈|쓰라|쓰려|쓰리)|` +
            // "소변을 보는 것도 아픔이 있어요" (2026-11-22)
            String.raw`(?:소변|오줌)(?:을)?\s*보는\s*(?:게|것도?|것이)\s*${INTENSITY_PHRASE}(?:아프|아파|아픔|따끔|따가|따갑)`
        ),
        pat(String.raw`배뇨통${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "빈뇨",
        // "화장실을 진짜 자주 가게 돼요" (training dev half, 2026-11-27)
        pat(String.raw`빈뇨|(?:소변|오줌)(?:을|이|도)?\s*${INTENSITY_PHRASE}자주|화장실(?:을|에)?\s*${INTENSITY_PHRASE}자주\s*가|` +
          // "소변 보는 횟수가 부쩍 늘었어요", "소변 보는 게 너무 자주 돼요", "자주 마려운데" (2026-11-06)
          String.raw`(?:소변|오줌)\s*(?:보는\s*)?(?:횟수|빈도)(?:가|도)?\s*${INTENSITY_PHRASE}(?:늘|많아|잦)|` +
          String.raw`(?:소변|오줌)\s*보는\s*(?:게|거)\s*${INTENSITY_PHRASE}자주|자주\s*마려`),
        pat(String.raw`빈뇨${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "기절",
        pat(String.raw`기절|실신|까무러|의식(?:이)?\s*없|정신(?:을)?\s*잃|의식(?:을)?\s*잃|쓰러졌|쓰러진\s*적`),
        pat(String.raw`(?:기절|실신)(?:한\s*적)?${PARTICLE}\s*${ABSENT_ENDING}|쓰러진\s*적(?:은|도)?\s*없`),
    ),
    rule(
        "마비",
        pat(
            String.raw`마비|(?:팔|다리|한쪽|얼굴|손|발|팔다리)(?:이|에|가|도)?\s*(?:갑자기\s*)?` +
            String.raw`(?:힘이\s*(?:빠|없|안\s*들)|안\s*움직|움직이지\s*않)|얼굴(?:이)?\s*(?:한쪽으로\s*)?(?:처졌|돌아갔|비뚤어)|` +
            // "얼굴 한쪽이 처진 것 같기도 해요", "입이 한쪽으로 돌아갔어요" (2026-11-28 check of item 4)
            String.raw`(?:얼굴|입)(?:\s*(?:한쪽|한\s*쪽|반쪽))?(?:이|가)?\s*(?:한쪽으로\s*)?${INTENSITY_PHRASE}(?:처졌|처진|처져|처지|돌아갔|돌아간|비뚤어|비뚤|일그러)`
        ),
        pat(String.raw`마비${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "말 어눌함",
        // 말 as a word of its own: "정말 이상해요" and "정말 괜찮아요" say nothing about speech.
        // "말이 좀 꼬이는 것 같고", "말이 엉키고", "말하는 게 약간 어눌하고" (2026-11-21, training dev half)
        pat(String.raw`(?<![가-힣])(?:말|발음)(?:이|을|도)?\s*${INTENSITY_PHRASE}(?:잘\s*)?(?:어눌|꼬여|꼬이|엉키|엉켜|안\s*나와|이상해|이상한가|이상하게\s*나|흐려|부정확|엉뚱하게\s*나)|` +
          // "혀가 무거워서 말이 잘 안 나와요", "혀가 꼬여요" (training dev half, 2026-11-27)
          String.raw`(?<![가-힣])혀(?:가|도)?\s*${INTENSITY_PHRASE}(?:무거|꼬여|꼬이|굳|잘\s*안\s*돌)|` +
          String.raw`(?<![가-힣])말(?:하는\s*(?:게|것이?|것도)|할\s*때)\s*${INTENSITY_PHRASE}(?:자꾸\s*)?(?:어눌|꼬여|꼬이|엉키|부정확|불명확|끊어지|끊어져|끊기|끊겨|잘\s*안\s*나)|` +
          String.raw`(?<![가-힣])말하기(?:가)?\s*${INTENSITY_PHRASE}힘들`),
        pat(String.raw`(?<![가-힣])(?:말|발음)(?:은|도)?\s*(?:괜찮|정상|또렷)`),
    ),
    rule(
        "쉰 목소리",
        pat(
            String.raw`쉰\s*목소리|쉬는\s*목소리|목(?:이)?\s*쉬었|목(?:이)?\s*쉬어|목(?:이)?\s*잠겼|` +
            // "목소리가 좀 이상해진 거 같아요", "목소리가 좀 편하게 안 나오긴 해요", "목소리가 달라진 것 같긴 한데" (2026-11-22)
            String.raw`목소리(?:가|도)?\s*${INTENSITY_PHRASE}(?:쉬|변했|변해|변한|달라|이상해|이상하|(?:편하게\s*|제대로\s*|잘\s*)?안\s*나|갈라|거칠|잠겼)`
        ),
        pat(String.raw`목소리(?:는|도)?\s*(?:괜찮|정상)`),
        "목",
    ),
    rule(
        "체중 감소",
        pat(
            String.raw`체중(?:이)?\s*(?:줄|빠졌|감소)|몸무게(?:가)?\s*(?:줄|빠졌)|살(?:이)?\s*(?:많이\s*|갑자기\s*)?빠졌|` +
            // "살이 3킬로 정도 빠졌어요", "몸무게가 요즘 5kg 넘게 줄었어요" (2026-11-11 long-sentence check).
            String.raw`(?:체중|몸무게|(?<![가-힣])살)(?:이|가|도|은|는)?\s*${INTENSITY_PHRASE}` +
            String.raw`(?:\d+\s*(?:킬로|키로|kg)(?:\s*(?:정도|쯤|가량|넘게|이상|이나|나))?\s*)?(?:줄었|줄어|빠졌|빠져|빠진)|` +
            String.raw`\d+\s*(?:킬로|키로|kg)(?:가|나|이)?(?:\s*(?:정도|쯤|가량|넘게|이상))?\s*(?:빠졌|줄었)`
        ),
        pat(String.raw`(?:체중|몸무게)(?:은|는|도)?\s*(?:그대로|변화\s*없|안\s*빠졌)`),
    ),
    rule(
        "경련",
        // "경기를 했어요", "거품을 물었어요", "눈이 뒤집혔어요" (119 emergency-call expressions); not a match (축구 경기).
        pat(String.raw`(?<!(?:축구|야구|농구|배구|게임|시합|운동|테니스|골프)\s*)(?<![가-힣])경기(?:를|가)?\s*(?:했|해|하더|하면서|일으|나서|났)|` +
          String.raw`(?:입에\s*)?거품(?:을)?\s*물|눈(?:이)?\s*뒤집|(?<!위|근육\s*)(?<!${MUSCLE_CRAMP_BEFORE})경련|발작|(?:몸|팔|다리)(?:이|가)?\s*(?:뻣뻣해지|뒤틀리)`),
        pat(String.raw`(?:경련|발작)${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "관절 통증",
        pat(
            String.raw`(?:관절통|${JOINT_PART})(?:이|가|은|는|도)?\s*${CHANGE_PHRASE}|` +
            String.raw`관절통|(?:${JOINT_PART})(?:이|가|은|는|도)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|쑤시|쑤셔|시큰|시려|결려|결리|붓|부었)|` +
            String.raw`(?:${JOINT_PART})\s*통증`
        ),
        pat(
            String.raw`관절통${PARTICLE}\s*${ABSENT_ENDING}|(?:${JOINT_PART})(?:이|가|은|는|도)?\s*${NOW_ADVERB}${NOT_PAINFUL}`
        ),
        "관절",
    ),
    rule(
        "입안 통증",
        pat(
            // 입·혀 as words of their own (2026-11-06): the 혀 in 전혀 is not the tongue.
            String.raw`구내염|입병|(?<![가-힣])(?:입안|입\s*안|혀|입천장)(?:이|가|은|는|도|에)?\s*(?:${INLINE_ONSET}\s*)?${INTENSITY_PHRASE}` +
            String.raw`(?:아프|아파|아팠|아픈|따가|따갑|쓰라|헐었|헐어|헌\s|헐|뭐가\s*났)`
        ),
        pat(
            String.raw`(?:구내염|입병)${PARTICLE}\s*${ABSENT_ENDING}|(?<![가-힣])(?:입안|혀)(?:은|는|도|이|가)?\s*${NOW_ADVERB}${NOT_PAINFUL}`
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
            String.raw`보기(?:가)?\s*(?:힘들|어렵)|찔끔|시원하게\s*안)|(?:오줌통|방광)(?:이)?\s*터질|` +
            // "소변이 잘 나오지 않고", "소변 보는 게 정말 힘들어요" (2026-11-06)
            String.raw`(?:소변|오줌)(?:이|도)?\s*${INTENSITY_PHRASE}잘\s*(?:안\s*나|나오지\s*않)|` +
            String.raw`(?:소변|오줌)(?:을)?\s*보는\s*(?:게|것도?)\s*${INTENSITY_PHRASE}(?:힘들|어렵|어려)`
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
        // "생리할 때마다 배랑 허리가 좀 아파요", "생리 아픔도 계속 있어요" (2026-11-06)
        pat(String.raw`생리통|(?:생리|월경)\s*(?:할\s*때(?:마다)?|때(?:마다)?|기간\s*동안|중에?|때문에)?\s*` +
          String.raw`(?:(?:배|허리|아랫배)(?:가|랑|도|와|하고)?\s*){0,2}${INTENSITY_PHRASE}(?:아프|아파|아팠|아픔|통증)`),
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
        pat(String.raw`눈곱|눈물(?:이)?\s*(?:계속|자꾸|많이)\s*(?:나|흘러|흘)|` +
          // "눈물이 줄줄 흐를 때가", "눈물도 자꾸 나서" (2026-11-06)
          String.raw`눈물(?:이|도)?\s*(?:(?:${INTENSITY_WORD}|줄줄)\s*)+(?:나|흘러|흘|흐르|나와|나오)|눈(?:가|에)?\s*분비물`),
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
        pat(String.raw`수족냉증|(?<![가-힣])(?:오른|왼|양)?(?:손발|손|발)(?:이|가|도|은|는)?\s*${INTENSITY_PHRASE}(?:(?:예전보다|전보다|더)\s*)*${INTENSITY_PHRASE}(?:차가워|차가운|차갑|차요|차서|시려|시리|얼음|냉)`),
        pat(String.raw`수족냉증${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "우울감",
        // "기분이 좀 처지더라고요", "요즘 기분이 많이 안 좋아요", "기분이 정말 별로예요", "기분도 많이 흐려졌어요" (2026-11-22)
        pat(String.raw`우울(?!증)|의욕(?:이)?\s*없|아무것도\s*하기\s*싫|(?<![가-힣])기분(?:이|도)?\s*${INTENSITY_PHRASE}(?:가라앉|처져|처지|다운|안\s*좋|별로|흐려)`),
        pat(String.raw`우울(?:감|증)?${PARTICLE}\s*${ABSENT_ENDING}|우울하지\s*않`),
    ),
    rule(
        "불안감",
        pat(String.raw`불안(?!정)|초조|조마조마`),
        pat(String.raw`불안(?:감)?${PARTICLE}\s*${ABSENT_ENDING}|불안하지\s*않`),
    ),
    rule(
        "청력 저하",
        pat(String.raw`청력|난청|(?<![가-힣])잘\s*안\s*들(?:려|리)|(?:귀|소리|말)(?:가|이|도)?\s*(?:잘\s*)?안\s*들려|(?:귀|소리|말)(?:가|이|도)?\s*잘\s*안\s*들리|` +
          // "귀가 좀 안 들리고", "소리가 분명하게 안 들리는 것 같아" (2026-11-06)
          String.raw`(?:귀|소리)(?:가|이|도)?\s*(?:${INTENSITY_PHRASE}|분명하게\s*|잘\s*)+안\s*들(?:려|리)|` +
          // "귀가 먹먹해요" is the ear feeling blocked, not pain (360 set B128, 2026-11-27)
          String.raw`귀(?:가|는|도)?\s*${INTENSITY_PHRASE}(?:먹먹|멍멍|멍해|막힌\s*(?:것|듯)|멀어)`),
        pat(String.raw`(?:청력\s*저하|난청)${PARTICLE}\s*${ABSENT_ENDING}|(?:귀|소리)(?:는|도)?\s*잘\s*들려`),
        "귀",
    ),
    rule(
        "입마름",
        pat(String.raw`입마름|구갈|갈증|(?<![가-힣])(?:입|입안|목)(?:이|가|도)?\s*(?:${INTENSITY_WORD}\s*|바짝\s*|너무나\s*)*(?:말라|마르|마른|건조)`),
        pat(String.raw`(?:입마름|갈증)${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    // 2026-11-08: symptoms the span model used to name from outside the list, now read by the rules themselves.
    rule(
        "삼킴 곤란",
        // "침 삼키기가 힘들어요" is a sore throat (인후통), not trouble swallowing food.
        pat(String.raw`삼킴\s*곤란|연하\s*곤란|음식이\s*(?:잘\s*)?안\s*넘어|` +
          // "목이 막힌 것처럼 밥이 안 넘어가요", "밥이 목에 걸려요" (2026-11-09 phone test)
          String.raw`목[가-힣\s]{0,6}(?:막|걸)[가-힣\s]{0,12}(?:밥|음식|물)(?:을|이)?\s*(?:잘\s*)?안\s*넘어|` +
          String.raw`(?:밥|음식)(?:이|을|도)?\s*(?:자꾸\s*)?목에\s*(?:걸|막)|` +
          String.raw`(?<!침(?:을)?\s*)(?:삼키|넘기)(?:기(?:가|도|는)?|는\s*(?:게|것이?|것도|거|데|건))\s*` +
          // Up to three words between, not a denial: "삼키기도 전과 비교해서 훨씬 어렵게", "여간 힘든 게 아니네요" (2026-11-21).
          String.raw`(?:(?!(?:안|못|별로|전혀|하나도|그다지|딱히)\s)[가-힣]+\s+){0,3}?(?:힘들|힘든|어렵|어려|불편|곤란)`),
        pat(String.raw`삼킴\s*곤란${PARTICLE}\s*${ABSENT_ENDING}|(?:삼키|넘기)(?:는\s*(?:건|것은|거|것도)|기(?:는|도))\s*${NOW_ADVERB}(?:괜찮|문제\s*없|편하)`),
    ),
    rule(
        "혼란",
        // Not "마음이 혼란스러워요" (feelings), "혼란스러워 보일까 봐" (how one seems) or "정신이 없어요" (busy).
        // "마음이 좀 혼란스럽긴 한데": a word or two may sit between (2026-11-11 long-sentence check).
        pat(String.raw`(?<!(?:마음|생각|기분|머릿속|감정)(?:이|가|은|는|도)?\s*(?:[가-힣]+\s+){0,2})혼란스(?:러|럽)(?!워?\s*보)|의식(?:이)?\s*(?:혼미|희미|흐려|흐릿)|` +
          String.raw`정신(?:이)?\s*${INTENSITY_PHRASE}(?:오락가락|왔다\s*갔다|흐릿|흐려)|사람(?:을|도)?\s*(?:잘\s*)?못\s*알아|` +
          String.raw`(?:여기가|지금이)\s*(?:어디|언제)인지\s*(?:잘\s*)?모르`),
        pat(String.raw`혼란${PARTICLE}\s*${ABSENT_ENDING}|정신(?:은|도)?\s*(?:멀쩡|또렷|맑)`),
    ),
    rule(
        "림프절 부음",
        // Only where lymph nodes are: a lump in the breast, on the lip or on the gums is something else.
        pat(String.raw`(?:림프절|림프샘|임파선)(?:이|가|도)?\s*${INTENSITY_PHRASE}(?:부었|부어|붓|부은|커졌|커진|만져)|` +
          String.raw`(?<![가-힣])(?:목|턱\s*밑|귀\s*뒤|겨드랑이|사타구니)\s*(?:옆|주변|양옆|쪽)?(?:에|이|가)?\s*${INTENSITY_PHRASE}(?:멍울|몽우리|혹|볼록)|` +
          String.raw`(?<![가-힣])목\s*(?:옆|주변|양옆)(?:이|에|가)?\s*${INTENSITY_PHRASE}(?:부어|부었|붓)`),
        pat(String.raw`(?:멍울|몽우리)(?:\s*같은\s*(?:건|것은|거))?(?:은|는|도)?\s*(?:안\s*만져|만져지지\s*않|${ABSENT_ENDING})|` +
          String.raw`(?:림프절|임파선)${PARTICLE}\s*(?:${ABSENT_ENDING}|안\s*부)`),
    ),
    rule(
        "황달",
        pat(String.raw`황달|(?:눈\s*흰자위?|흰자위?|눈|피부|얼굴|몸)(?:이|가|도|색이)?\s*${INTENSITY_PHRASE}(?:노랗|노래|누렇|누래)`),
        pat(String.raw`황달${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "체중 증가",
        pat(String.raw`체중(?:이|도)?\s*${INTENSITY_PHRASE}(?:확실히\s*)?(?:늘|증가|불었)|몸무게(?:가|도)?\s*${INTENSITY_PHRASE}(?:늘|불었)|` +
          String.raw`(?<![가-힣])살(?:이|도)?\s*${INTENSITY_PHRASE}(?:쪘|찌|찐|붙)|\d+\s*(?:킬로|kg)(?:가|나|이)?\s*(?:늘었|쪘|불었)`),
        pat(String.raw`(?:체중|몸무게|살)(?:은|는|도)?\s*안\s*(?:늘|쪘|불)|(?:늘|찌)지\s*않`),
    ),
    rule(
        "땀 과다",
        // How much ("땀이 비 오듯 나요"); 식은땀 and a plain "땀이 나요" stay 식은땀.
        pat(String.raw`다한증|(?<![가-힣])땀(?:이|을|도)?\s*` +
          String.raw`(?:${INTENSITY_WORD}\s*|평소보다\s*|평상시보다\s*|훨씬\s*|(?:비|물)\s*(?:오|흐르)듯(?:이)?\s*|줄줄\s*|폭포처럼\s*|뻘뻘\s*|지나치게\s*|끊임없이\s*)+(?:나|났|흘|흐르|많)|` +
          String.raw`(?<![가-힣])땀(?:이)?\s*(?:왜\s*이렇게\s*)?많(?:아|이|은|다)|(?<![가-힣])땀(?:이)?\s*${INTENSITY_PHRASE}(?:넘쳐|넘치)`),
        pat(String.raw`(?<![가-힣])땀(?:이|은|도)?\s*많이\s*나는\s*편(?:은|이)?\s*아니|다한증${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "근육 경련",
        // 쥐 is a cramp, not numbness (저림); a cramp is not a seizure (경련).
        pat(String.raw`근육\s*경련|${MUSCLE_CRAMP_BEFORE}경련|(?<![가-힣])쥐(?:가|도)?\s*${INTENSITY_PHRASE}(?:잘\s*)?(?:나|났|난)|` +
          String.raw`(?:눈\s*밑|눈꺼풀|근육)(?:이|가|도)?\s*${INTENSITY_PHRASE}(?:떨려|떨리|떨린|파르르|씰룩)|` +
          // "근육이 갑자기 꽉 조여져요", "종아리가 갑자기 굳어요" (training dev half, 2026-11-27); a stiff whole body is 경련.
          String.raw`(?:근육|종아리|허벅지|다리|팔)(?:이|가|도)?\s*${INTENSITY_PHRASE}(?:갑자기\s*)?(?:경직|굳어|굳는|꽉\s*조여)`),
        pat(String.raw`(?:근육\s*경련|(?<![가-힣])쥐)${PARTICLE}\s*(?:${ABSENT_ENDING}|안\s*나)`),
    ),
    rule(
        "후각 상실",
        // "입 냄새가 안 나요", "몸에서 냄새가 안 나요" are about a smell, not about smelling.
        pat(String.raw`후각|(?<!(?:에서|입|몸|발)\s*)(?<![가-힣])냄새(?:를|가|도)?\s*(?:${INTENSITY_WORD}\s*|전혀\s*|잘\s*|거의\s*|아예\s*|완전히\s*)*` +
          String.raw`(?:못\s*맡|맡지\s*못|안\s*(?:나|맡)|모르겠|사라)|` +
          String.raw`냄새(?:를)?\s*맡는\s*(?:게|거|것이?)\s*(?:${INTENSITY_WORD}\s*|전혀\s*|거의\s*|요즘은?\s*|완전히\s*)*(?:안\s*되|힘들|어렵|없)|` +
          String.raw`냄새\s*(?:감지|감각)(?:이|가|도)?\s*(?:${INTENSITY_WORD}\s*|전혀\s*|완전히\s*)*(?:안\s*되|사라|없)|(?<![가-힣])냄새(?:가)?\s*싹\s*사라|` +
          // "커피 향이 전혀 안 느껴져요" (training dev half, 2026-11-27)
          String.raw`(?<![가-힣])향(?:이|을|도)?\s*(?:전혀\s*|잘\s*|거의\s*|하나도\s*)*(?:안\s*느껴|못\s*느끼|느껴지지\s*않)`),
        pat(String.raw`냄새(?:는|도)?\s*잘\s*맡|후각${PARTICLE}\s*(?:${ABSENT_ENDING}|정상|괜찮)`),
    ),
    rule(
        "미각 이상",
        // 입맛이 없어요 and 밥맛이 없어요 are 식욕부진.
        pat(String.raw`미각|(?<![가-힣]|밥\s*)맛(?:을|이|도|에)?\s*(?:${INTENSITY_WORD}\s*|전혀\s*|잘\s*|거의\s*|아예\s*|제대로\s*|완전히\s*)*` +
          String.raw`(?:못\s*느끼|느끼지\s*못|안\s*느껴|느껴지지\s*않|안\s*나|이상|모르겠|달라)|` +
          String.raw`(?<![가-힣]|밥\s*)맛(?:이|도)?\s*(?:전혀|아예|하나도)\s*없`),
        pat(String.raw`(?<![가-힣])맛(?:은|도)?\s*잘\s*느껴|미각${PARTICLE}\s*(?:${ABSENT_ENDING}|정상|괜찮)`),
    ),
    rule(
        "멍",
        // 멍 as a word of its own: 멍울 is a lump.
        pat(String.raw`(?<![가-힣])멍(?:이|도)?\s*(?:${INTENSITY_WORD}\s*|잘\s*|쉽게\s*|바로\s*)*(?:들|든|생|잡)`),
        pat(String.raw`(?<![가-힣])멍${PARTICLE}\s*(?:잘\s*)?(?:안\s*(?:들|생)|${ABSENT_ENDING})`),
    ),
    rule(
        "잇몸 출혈",
        pat(String.raw`잇몸\s*출혈|잇몸(?:에서|이|에|도)?\s*${INTENSITY_PHRASE}피(?:가|도)?\s*${INTENSITY_PHRASE}(?:나|났|비쳐|비치|묻어)`),
        pat(String.raw`잇몸(?:에서|이|에|도)?\s*피(?:는|가|도)?\s*(?:안\s*나|나지\s*않)`),
    ),
    rule(
        "코골이",
        pat(String.raw`코골이|코\s*(?:골이|골음)|코\s*고는|코(?:를|도)?\s*(?:${INTENSITY_WORD}\s*|심히\s*|시끄럽게\s*)*(?:골아|골았|골고|곤다|곤대|골더)`),
        pat(String.raw`코(?:는|를|도)?\s*안\s*골|코골이${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "수면 무호흡",
        pat(String.raw`무호흡|(?:자다가|잘\s*때|자는\s*동안|잠자는\s*동안|잠자다가|밤에)\s*숨(?:이|을)?\s*${INTENSITY_PHRASE}(?:멈|멎|안\s*쉬|끊)|` +
          String.raw`숨\s*(?:쉬는\s*(?:게|걸|것이?)|쉴\s*때)\s*(?:${INTENSITY_WORD}\s*|잠깐\s*|간헐적으로\s*)*(?:멈|끊|스톱)`),
        pat(String.raw`무호흡${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "딸꾹질",
        pat(String.raw`딸꾹`),
        pat(String.raw`딸꾹질${PARTICLE}\s*(?:전혀\s*)?${ABSENT_ENDING}`),
    ),
    rule(
        "입냄새",
        pat(String.raw`입\s*냄새|구취|입(?:에서|안에서)\s*${INTENSITY_PHRASE}(?:냄새|악취)`),
        pat(String.raw`(?:입\s*냄새|구취)${PARTICLE}\s*(?:${ABSENT_ENDING}|안\s*나)`),
    ),
    rule(
        "탈모",
        // Not "머리가 빠개질 것 같아요" (a headache).
        pat(String.raw`탈모|(?:머리카락|머리털|머리)(?:이|가|도)?\s*(?:${INTENSITY_WORD}\s*|한\s*움큼씩\s*|뭉텅뭉텅\s*|요즘\s*|허전하게\s*)*(?:빠져|빠지|빠진|빠졌)`),
        pat(String.raw`(?:머리카락|머리)(?:은|는|도)?\s*안\s*빠|탈모${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    // 2026-11-27: six more the span model named from outside the list (vocabulary.json symptoms, outside_eval_set).
    rule(
        "창백함",
        // "창백하진 않아요" is read as a denial right after the mention. A yellow face (누렇) is 황달.
        pat(String.raw`창백(?:하|해|한)?|(?:얼굴|안색|낯빛|입술)(?:이|가|도)?\s*${INTENSITY_PHRASE}(?:하얗|하얘|허옇|허얘)|` +
          String.raw`(?:피부색|얼굴색|안색)(?:이|가|도)?\s*${INTENSITY_PHRASE}(?:옅어|하얘|하얗)|` +
          String.raw`(?:얼굴|안색)?(?:에)?\s*핏기(?:가|도)?\s*(?:${INTENSITY_WORD}\s*|하나도\s*|전혀\s*)*없`),
        pat(String.raw`창백함${PARTICLE}\s*${ABSENT_ENDING}|안색(?:은|도)?\s*(?:괜찮|좋)`),
    ),
    rule(
        "안면 홍조",
        // Heat in the face; a red rash on it stays 발진, and "열이 올라" stays 발열.
        // "얼굴이 쉽게 빨개져요", "안면이 갑자기 붉게 변해요" (training dev half); "빨갛게 올라왔어요" (a rash) stays 발진.
        pat(String.raw`홍조|(?:얼굴|안면|볼|뺨)(?:이|가|도)?\s*` +
          String.raw`(?:${INTENSITY_WORD}\s*|쉽게\s*|자주\s*|종종\s*|갑자기\s*|가끔\s*|확\s*|왜\s*그런지\s*|계속\s*|어제부터\s*|뜨겁게\s*)*` +
          String.raw`(?:화끈|달아오르|달아올라|달아올랐|빨개지|빨개져|빨개졌|빨개진|붉어지|붉어져|붉어졌|붉어진|(?:빨갛게|붉게)\s*(?:변하|변해|변했|변한|되))`),
        pat(String.raw`홍조${PARTICLE}\s*${ABSENT_ENDING}|(?:얼굴|볼)(?:은|는|도)?\s*안\s*(?:화끈|달아)`),
    ),
    rule(
        "질 분비물",
        // 냉 as a word of its own: not 냉장고, 냉면 or 냉찜질.
        pat(String.raw`질\s*분비물|(?<![가-힣])냉(?:이|도)?\s*${INTENSITY_PHRASE}(?:많|늘|나와|나오|비치|비쳐|섞|냄새|있)|` +
          String.raw`(?:밑|질)(?:에서|으로)\s*${INTENSITY_PHRASE}(?:분비물|냉)`),
        pat(String.raw`(?<![가-힣])냉(?:은|도)?\s*(?:안\s*(?:나|비)|없)|질\s*분비물${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "월경 이상",
        // The period itself (late, irregular, heavy); pain with it stays 생리통.
        pat(String.raw`생리\s*불순|월경\s*(?:불순|과다|이상)|` +
          String.raw`(?:생리|월경)(?:\s*양|량)?(?:이|가|도|를)?\s*${INTENSITY_PHRASE}` +
          String.raw`(?:(?:\d+|한|두|세|몇)\s*(?:달|개월)(?:째|이나|동안|넘게)?\s*)?` +
          String.raw`(?:불규칙|들쭉날쭉|끊겼|끊긴|멈췄|늦어|늦게|늦네|건너뛰|많아|많이\s*나|너무\s*많|줄었|적어|안\s*(?:나와|와|해|하|했|있))`),
        pat(String.raw`(?:생리|월경)(?:는|은|도)?\s*(?:규칙적|일정|정상|제때)|(?:생리\s*불순|월경\s*이상)${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "기억력 저하",
        // Not "언제부터인지 기억이 안 나요" (the onset), nor a single "깜빡하고" (forgot once), nor blinking eyes.
        pat(String.raw`건망증|기억력(?:이|도)?\s*${INTENSITY_PHRASE}(?:떨어|나빠|안\s*좋|감퇴|흐려|예전\s*같지)|` +
          String.raw`(?<!눈(?:이|을)?\s*)(?:깜빡깜빡|깜박깜박)|(?:자꾸|자주)\s*(?:뭘\s*|잘\s*)?(?:깜빡|깜박)(?:해|하|거려|거리)`),
        pat(String.raw`건망증${PARTICLE}\s*${ABSENT_ENDING}|기억력(?:은|도)?\s*(?:괜찮|좋|멀쩡|정상)`),
    ),
    rule(
        "질 출혈",
        // Bleeding from below outside a period (하혈, 119 calls). A period said as such is 월경 이상 or nothing.
        pat(String.raw`하혈|부정\s*출혈|질\s*출혈|(?:밑|질)(?:에서|으로)\s*${INTENSITY_PHRASE}피|생리\s*(?:때|기간)?(?:가|도)?\s*아닌데\s*피`),
        pat(String.raw`(?:하혈|부정\s*출혈|질\s*출혈)${PARTICLE}\s*${ABSENT_ENDING}`),
    ),
    rule(
        "청색증",
        // Blue lips or fingertips (청색증이 오다, 119 calls).
        pat(String.raw`청색증|(?:입술|손끝|손톱|얼굴)(?:이|가|도)?\s*${INTENSITY_PHRASE}(?:파래|파랗|퍼래|퍼렇|새파래|새파랗|보라색)`),
        pat(String.raw`청색증${PARTICLE}\s*${ABSENT_ENDING}|입술(?:은|도)?\s*안\s*파래`),
    ),
    rule(
        "항문 통증",
        pat(String.raw`(?:항문|똥꼬)(?:이|가|도|쪽이|에)?\s*${INTENSITY_PHRASE}(?:아프|아파|아팠|아픈|아픔|따끔|따가|따갑|쓰라|쓰려|욱신|통증)`),
        pat(String.raw`(?:항문|똥꼬)(?:은|는|도)?\s*(?:안\s*아프|안\s*아파|아프지\s*않|괜찮)`),
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
    // "지난주부터", "지난달 말부터", "며칠 전부터", "세 시간 전부터" (2026-11-11 onset matrix).
    String.raw`(?:지난|저번|이번)\s*(?:주말|주|달)(?:\s*(?:초|중순|말))?(?:부터|쯤)?|며칠\s*(?:전부터|전|째|동안)|` +
    String.raw`(?:한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|몇)\s*(?:시간|주|달)\s*(?:전부터|전|째|동안)|` +
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
    // "열이 어제보다 좀 내렸어요", "점점 심해지고 있어요", "갈수록 심해져요" (2026-11-21, 360 set odd half).
    String.raw`(?:괜찮아졌|나아졌|호전됐|좋아졌|덜해졌|줄었|완화됐|편해졌|내렸|떨어졌|나아지고|좋아지고))|` +
    String.raw`(?<worsening>(?:(?:더|훨씬|점점|많이|(?:날이\s*)?갈수록)\s*)?` +
    String.raw`(?:심해졌|심해져|심해지(?:고|네|는)|악화됐|나빠졌|나빠지고|(?<!(?:${DETAIL_CONDITION})[^.!?。]{0,20})더\s*(?:아프|아파|아팠)|잦아졌|늘었))|` +
    String.raw`(?<unchanged>(?:그대로|비슷|여전|변화\s*없))`
);
const GENERIC_MEDICINE_FORMS = ["연고", "물파스", "파스", "안약", "가글", "흡입기", "패치"];
const MEDICATION_NAME_PATTERN = pat(
    String.raw`((?:(?:알레르기|감기|비염|혈압|당뇨|진통|해열|소화|위장|고지혈증|콜레스테롤|갑상선|천식|수면|우울증)\s*약)|` +
    String.raw`(?:[가-힣A-Za-z0-9-]{2,20}(?:약|제))|` +
    // "연고를 발랐어요", "파스를 붙였어요" (2026-11-21, 360 set odd half)
    String.raw`(?<![가-힣])(?:${GENERIC_MEDICINE_FORMS.join("|")}))` +
    String.raw`(?=(?:과|와|을|를|도|은|는)?(?:\s|$))`
);
const KNOWN_MEDICATION_PATTERN = pat(
    String.raw`타이레놀|아세트아미노펜|이부프로펜|애드빌|게보린|판피린|판콜(?:에이|에스)?|펜잘|부루펜|탁센|낙센|` +
    String.raw`아스피린|아목시실린|오구멘틴|세파클러|클래리스로마이신|지르텍|알레그라|코대원|시네츄라|` +
    String.raw`베아제|훼스탈|겔포스|개비스콘|스멕타|로페라마이드|넥시움|메트포르민|리피토|노바스크|` +
    String.raw`와파린|엘리퀴스|씬지로이드|신지로이드|프레드니솔론|인슐린|벤토린|심비코트|` +
    String.raw`테라플루|화이투벤|콜대원|이지엔6|까스활명수|활명수|후시딘|마데카솔|` +
    // 2026-11-27: more names patients say, chosen to not sit inside everyday words.
    String.raw`맥시부펜|써스펜|나프록센|쎄레브렉스|세레브렉스|울트라셋|트라마돌|타미플루|클라리틴|페니라민|` +
    String.raw`뮤코펙트|코푸시럽|화콜|가스모틴|무코스타|알마겔|스토가|둘코락스|마그밀|메디락|비오플|정로환|` +
    String.raw`판토록|우루사|이가탄|인사돌|케토톱|쌍화탕|아모잘탄|트윈스타|엑스포지|자누비아|자누메트|` +
    String.raw`다이아벡스|아마릴|트라젠타|포시가|자디앙|크레스토|아토젯|플라빅스|자렐토|졸피뎀|스틸녹스|` +
    String.raw`자낙스|렉사프로`
);
// Generic drug name endings, e.g. 세팔렉신 is not listed but 아지트로마이신 ends in 마이신.
const DRUG_NAME_PATTERN = pat(
    String.raw`(?<![가-힣])[가-힣]{2,10}(?:마이신|실린|프로펜|스타틴|사르탄|프라졸|디핀|세핀|파린|플록사신|` +
    // 시타글립틴, 다파글리플로진, 파모티딘, 디아제팜, 알프라졸람, 디클로페낙, 프로프라놀롤, 아시클로비르 (2026-11-27)
    String.raw`글립틴|글리플로진|티딘|제팜|졸람|페낙|놀롤|클로비르|미비르)`
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
    String.raw`먹|복용|처방|투여|맞았|맞고|흡입|뿌리|뿌려|바르|발라|발랐|붙이|붙여|붙였|마셨|마시|마셔|넣고|넣어|넣었`
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
  // By sound (2026-11-11 phone test): "펜이실린" is 페니실린 split differently, "메트프로민"/"매트포르민" are 메트포르민
  // with two letters swapped or ㅐ for ㅔ. Compared letter by letter inside the syllables, the silent ㅇ and ㅐ/ㅔ
  // set aside, at most two letters apart.
  const heard = soundOf(name);
  for (const known of KNOWN_SPELLINGS) {
    if (Math.abs(known.length - name.length) <= 1 && known.length >= 4 && letterDistance(heard, soundOf(known)) <= 2) return known;
  }
  return name;
}

const soundOf = (word: string) => [...word.normalize("NFD").replace(/ᄋ/g, "").replace(/ᅢ/g, "ᅦ")];

function letterDistance(a: string[], b: string[]): number {
  let row = Array.from({ length: b.length + 1 }, (_, index) => index);
  for (let i = 1; i <= a.length; i += 1) {
    const next = [i];
    for (let j = 1; j <= b.length; j += 1) {
      next[j] = Math.min(row[j] + 1, next[j - 1] + 1, row[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    row = next;
  }
  return row[b.length];
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
    String.raw`불편|이상하|이상해|이상했|이상한|혹이|혹\s*같|덩어리|부르트|부르텄|들려|말라|마르|갈증|` +
    // Symptom words the rules did not read and did not show either, so the patient never got to fix them (2026-11-28
    // check of item 5, training dev half): "씹을 때마다 아픔이", "입안이 따끔거려요", "배가 심상치 않음", "붉은 반점이",
    // "배가 자꾸 멀미하는 것 같고", "속이 휘청거려요", "글씨가 잘 안 보이네", "목에 뭔가 걸린 것 같아요".
    String.raw`아픔|따끔|심상치|볼록|팽팽|불어\s*오르|반점|붉|빨갛|빨개|털이|빠지|빠져|잘\s*안\s*보|안\s*보이|들리지|` +
    String.raw`걸린\s*(?:것|듯)|걸려|끼어|분비물|눈물|(?<![가-힣])냉(?:이|도)\s|냄새(?:가|도)?\s*(?:좀\s*|많이\s*|자꾸\s*|심하게\s*)?(?:나|심해|심하|이상)|몸이\s*(?:좀\s*)?(?:뜨거|따뜻|가벼워)|부은|멀미|끈적|휘청|어질|` +
    String.raw`정신이?\s*없|혼란|정신이\s*(?:잠깐\s*)?나갔|맛이|맛을|배가\s*고프지|피\s*묻|섞여|재기|당기|땡기|움직이지|나올\s*기미|` +
    // Left after the first pass (2026-11-28): "속이 뒤집힐 것 같아요", "배가 불어 오른 것 같아요", "속이 꽉 막힌 것 같아요",
    // "씹히는 것 같은 소리가 나요", "먹는 게 전혀 없어요", "귀소리".
    String.raw`뒤집힐|뒤집힌|뒤집어|불어\s*오|불어올|막힌\s*(?:것|듯)|씹히는|소리가\s*(?:좀\s*|자꾸\s*)?(?:나|들)|먹는\s*게\s*(?:전혀\s*|거의\s*)?없|귀소리`
);
const UNCERTAIN_PATTERN = pat(
    // "발음이 이상한가 싶기도 해요", "아픈가 싶어요", "피가 있나 싶은데" (2026-11-28 check of item 4): only right after the
    // symptom's own word. Not a cause in doubt ("빈혈인가 싶기도", "그런 건가 싶어") nor "먹고 싶어요".
    String.raw`모르겠|잘\s*모르|확실(?:하지|치|하진)\s*않|헷갈|긴가민가|애매|같기도|(?:픈|운|한|른|진|난)가\s*싶|있나\s*싶|` +
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
    // "많이 먹으면 배가 아파요", "오래 걸을 때": the word says how much of something else, not how bad (2026-11-28).
    if (found.pattern === SEVERITY_PATTERN
        && matchStart(String.raw`\s*(?:[가-힣A-Za-z0-9]{1,10}(?:을|를)\s*)?(?:(?:많이|너무|좀|오래|조금|자주|급하게)\s*)*` +
          String.raw`[가-힣]{1,5}(?:으면|면|을\s*때|ㄹ\s*때|할\s*때|고\s*나면|은\s*뒤)(?=\s|$)`, text.slice(found.end))) {
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
  // "하루에 설사를 다섯 번": 하루 said before the symptom (2026-11-21, 360 set odd half).
  if (!frequency.startsWith("하루") && chosen.start >= end && search(String.raw`하루(?:에|에도|에만)?\s*$`, text.slice(0, start))) {
    frequency = `하루 ${frequency}`;
  }
  const now =FREQUENCY_NOW_PATTERN.search(beforeFirst(SENTENCE_SPLIT_PATTERN, text.slice(chosen.end)));
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

// "페니실린 알레르기", "아스피린에 알레르기가 있어서 못 먹어요" (2026-11-21): an allergy, not a medicine being taken.
const ALLERGY_AFTER_NAME = String.raw`(?:에|에는|에도|에\s*대한)?\s*,?\s*알레르기`;

/** Medication lines for the record ("타이레놀 500mg 하루 2회") and the bare names. */
function extractMedications(text: string): [string[], string[]] {
  const names: string[] = [];
  const lines: string[] = [];
  for (const clause of MEDICINE_CLAUSE_BOUNDARY.split(text)) {
    if (!MEDICATION_VERB_PATTERN.search(clause)) continue;
    let found: Array<[number, string]> = [];
    for (const name of MEDICATION_NAME_PATTERN.finditer(clause)) {
      // "조영제 알레르기" is an allergy
      if (!matchStart(ALLERGY_AFTER_NAME, clause.slice(name.end))) {
        found.push([name.start, name.groups[1]!.replace(/\s+/g, "")]);
      }
    }
    for (const pattern of [KNOWN_MEDICATION_PATTERN, DRUG_NAME_PATTERN, TYLENOL_SOUNDALIKE_PATTERN]) {
      for (const name of pattern.finditer(clause)) {
        // "페니실린 알레르기" is an allergy, not a medicine being taken.
        if (!matchStart(ALLERGY_AFTER_NAME, clause.slice(name.end))) found.push([name.start, name.text]);
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
    // "매트포르민을 먹고 있어요": a name the patient takes, misheard, with no dose said (2026-11-11 phone test).
    // Speech recognition may split the name ("매트 포르민을", 2026-11-17 phone test).
    for (const name of pat(String.raw`(?<![가-힣])((?:[가-힣]{2,}\s)?[가-힣]{2,})(?:을|를)\s*(?:먹|복용|드시|챙겨)`).finditer(clause)) {
      // The word before may not be part of the name ("있어서 매트포르민을"): then the last word alone.
      for (const heard of [name.groups[1]!, name.groups[1]!.split(" ").at(-1)!]) {
        const word = heard.replace(/\s/g, "");
        const known = knownSpelling(word);
        if (word.length < 4 || (known === word && (heard === word || !KNOWN_SPELLINGS.includes(known)))) continue;
        const start = name.start + name.groups[1]!.length - heard.length;
        if (!found.some(([at]) => at === start)) found.push([start, heard]);
        break;
      }
    }
    // "타이레놀" is both a known name and a sound-alike match
    found = [...new Map(found.map((item) => [`${item[0]}\u0000${item[1]}`, item])).values()]
      .sort((a, b) => a[0] - b[0] || (a[1] < b[1] ? -1 : a[1] > b[1] ? 1 : 0));
    // "벤토린 흡입기", "후시딘 연고": the form right after a name is that medicine, not another one.
    found = found.filter(([position, heard], index) => !(GENERIC_MEDICINE_FORMS.includes(heard)
      && found.slice(0, index).some(([start, other]) => position - (start + other.length) <= 1)));
    found.forEach(([position, heard], index) => {
      const name = knownSpelling(heard.replace(/\s/g, "")); // may differ in length from what was heard: the dose tail below uses heard
      if (names.includes(name) || names.some((other) => other.includes(name) || name.includes(other))) return;
      names.push(name);
      // Dose and timing said right after the name, before the next medicine, belong to it.
      const nextPosition = index + 1 < found.length ? found[index + 1][0] : clause.length;
      const tail = clause.slice(position + heard.length, Math.min(nextPosition, position + heard.length + 30));
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

function firstSymptomMatch(pattern: Pat, text: string, keep: (found: Match) => boolean = () => true): Match | null {
  // "두통약", "기침약", "설사약" name a medicine, not a symptom the patient has now.
  return pattern.finditer(text).find((found) => !MEDICINE_SUFFIX_PATTERN.match(text, found.end) && keep(found)) ?? null;
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

// Dialect and blunt words for body parts and forms, read as the standard ones the rules know (2026-11-28 check of item 6):
// "가심이 아파요", "배때기가 아파요", "무르팍이 쑤셔요", "뒷골이 땡겨요", "똥이 안 나와요", "배가 아퍼유", "머리빡이 지끈혀요".
const DIALECT_WORDS: Array<[Pat, string]> = [
  [pat(String.raw`(?<![가-힣])가심(?=이|은|도|에|을|이랑|과|\s|$)`), "가슴"],
  // 머리 ends in a vowel: "머리빡이" is "머리가", "뒷골이" is "뒷머리가".
  [pat(String.raw`(?<![가-힣])(?:머리빡|대갈통|대갈빡|대갈)이(?=\s)`), "머리가"],
  [pat(String.raw`(?<![가-힣])(?:머리빡|대갈통|대갈빡|대갈)은(?=\s)`), "머리는"],
  [pat(String.raw`(?<![가-힣])뒷골이(?=\s)`), "뒷머리가"],
  [pat(String.raw`(?<![가-힣])(?:머리빡|대갈통|대갈빡|대갈)(?=도|가|에|\s|$)`), "머리"],
  [pat(String.raw`(?<![가-힣])배때기`), "배"],
  [pat(String.raw`(?<![가-힣])등짝`), "등"],
  [pat(String.raw`(?<![가-힣])(?:무르팍|무릎팍)`), "무릎"],
  [pat(String.raw`(?<![가-힣])뒷골`), "뒷머리"],
  [pat(String.raw`(?<![가-힣])똥(?=이|을|도|은|\s)`), "대변"],
  [pat(String.raw`아퍼(?=요|유|서|도|\s|$|[.!?])`), "아파"],
  [pat(String.raw`(지끈|욱신|띵|답답|어질어질|화끈|따끔|뻐근|시큰|거북|피곤|이상)혀(?=요|유|서|\s|$|[.!?])`), "$1해"],
];

function dialectWords(text: string): string {
  return DIALECT_WORDS.reduce((current, [pattern, word]) => pattern.sub(current, word), text);
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

// "어지럽진 않아요", "토하지는 않았는데", "가렵지도 않고": the verb itself denied right after the evidence (2026-11-21).
// "살이 빠진 건 아니에요", "기분이 안 좋은 건 아니에요" (2026-11-22), not "…건 아니라 …" (it is something else instead).
const DENIED_RIGHT_AFTER_PATTERN = pat(String.raw`(?:지는|진|지도|지)\s*않(?!을까|나\s*싶|았으면)|[은는]?\s*(?:건|것은|거는)\s*아니(?!라)`);

function isNegatedInList(text: string, evidence: Evidence): boolean {
  const after = text.slice(evidence.end);
  if (DENIED_RIGHT_AFTER_PATTERN.match(after)) return true;
  // "열이나" already took the connector
  if (search(`${LIST_CONNECTOR}$`, evidence.text)) return Boolean(matchStart(NEGATION_LATER_IN_CLAUSE, after));
  let listed = LISTED_BEFORE_NEGATION_PATTERN.match(after);
  if (listed && HADA_ROOT_PATTERN.search(evidence.text) && matchStart(String.raw`\s*하고`, after)) listed = null;
  return Boolean(listed || GONE_NOW_PATTERN.match(after));
}

type Found = { rule: Rule; evidence: Evidence; absent: boolean };

/** Read the patient's words. referenceDate is the patient's local date ("2026-10-09"), for onsets like "어제부터". */
// The P, R and T of the OPQRST pain history, which pick-from-a-list symptom checkers ask one by one and free speech
// often holds already (2026-11-27): what brings it on or eases it, where it spreads, how long a bout lasts, and
// whether it comes and goes. Times of day ("밤에") are left to the onset.
const DETAIL_TRIGGER_PATTERN = pat(
    String.raw`(?<![가-힣])(${DETAIL_CONDITION})[^.!?。]{0,20}?` +
    String.raw`(?:(나아|괜찮아|편해|편안해|덜\s*아|가라앉|좋아지|좋아져|사라|(?:열|체온)(?:이|도)?\s*(?:내려|떨어))|(더\s*(?:심해|아파|아프|힘들|나빠|쓰려|쓰리)|심해|나빠|악화)|` +
    // "우유를 먹으면 설사를 해요", "기름진 걸 먹으면 토해요" (2026-11-28 check of item 2)
    String.raw`(아파|아프|아픈|쓰려|쓰리|쓰린|쑤시|쑤셔|저려|저리|결려|결리|찌릿|콕콕|따끔|답답|차요|차고|어지러|생기|생겨|시작|` +
    String.raw`설사|토(?:를)?\s*(?:해|했|하)|토해|토했|가려|부어|부었|붓|기침(?:이|을)?\s*(?:나|해)))`
);
const RADIATION_PART = String.raw`(?:왼|오른|양)?(?:쪽\s*)?(?:팔|어깨|등|턱|목|뒷목|다리|허벅지|엉덩이|옆구리|아랫배|사타구니|가슴|머리|발|손|손가락|발가락|허리|명치|배꼽(?:\s*(?:주위|주변|근처))?)`;
// Not "왼팔로 퍼지진 않아요" (2026-11-27 check of item 1).
const NOT_DENIED_AFTER = String.raw`(?![가-힣]*\s*(?:않|안\s))`;
const RADIATION_PATTERN = pat(
    String.raw`(?<![가-힣])(${RADIATION_PART})(?:\s*쪽)?(?:으로|로|까지)\s*${INTENSITY_PHRASE}` +
    // "오른쪽 아랫배로 옮겨갔어요": a pain that moved (appendicitis is the classic), named as such.
    String.raw`(뻗|퍼지|퍼져|퍼졌|번지|번져|번졌|내려가|내려와|내려갔|올라가|올라와|올라갔|타고|당겨|땡겨|이어|옮겨|옮겼|옮아)` + NOT_DENIED_AFTER
);
// From one part to another: "엉덩이에서 다리까지 저려요" (sciatica), "목에서 어깨로 뻗쳐요" (2026-11-28 check of item 1).
const RADIATION_SPAN_PATTERN = pat(
    String.raw`(?<![가-힣])(${RADIATION_PART})(?:\s*쪽)?(?:에서|부터)\s*(${RADIATION_PART})(?:\s*쪽)?(?:까지|으로|로)\s*${INTENSITY_PHRASE}` +
    String.raw`(?:아프|아파|아팠|저려|저리|저렸|쑤셔|쑤시|찌릿|당겨|땡겨|뻗|퍼|번|내려|올라|이어)` + NOT_DENIED_AFTER
);
const DURATION = String.raw`(?:\d+|한|두|세|네|다섯|몇|십|이십|삼십|한두|두세|몇십)\s*(?:초|분|시간)`;
const EPISODE_PATTERN = pat(
    String.raw`한\s*번\s*(?:아프면|오면|시작하면|생기면|그러면|에)?\s*(${DURATION}(?:\s*(?:쯤|정도|가량|이상|넘게))?)|` +
    String.raw`(${DURATION}(?:\s*(?:쯤|정도|가량|넘게|이상))?)\s*(?:씩\s*)?(?:가요|가고|갔|가다가|지속|계속돼|계속되|이어지|아프다가|그러다가)|` +
    // "배가 아프다가 30분쯤 지나면 괜찮아져요" (2026-11-28 check of item 3); not after a medicine ("약을 먹고 30분쯤").
    String.raw`(?<!먹고\s*)(${DURATION}(?:\s*(?:쯤|정도|가량))?)\s*(?:지나면|있으면|있다가)\s*(?:괜찮아|나아|가라앉|사라|멈|없어)`
);
// Not "정신이 오락가락해요" (혼란), "생각이 왔다 갔다", "병원을 왔다 갔다 했어요".
const COMES_AND_GOES_PATTERN = pat(
    String.raw`(?<!(?:정신|생각|마음|기분)(?:이|도)?\s*(?:[가-힣]+\s+)?)(?<!(?:을|를)\s*)(?:아팠다\s*(?:가\s*)?안\s*아팠다|괜찮았다\s*(?:가\s*)?(?:아팠|심해|안\s*좋)|` +
    String.raw`(?:아팠다|심했다)\s*(?:가\s*)?(?:괜찮|나았|덜)|오락가락|왔다\s*갔다|들쑥날쑥|간헐적|생겼다\s*(?:가\s*)?(?:없어|사라)|` +
    // "기침이 났다 안 났다 해요", "열이 오르락내리락해요" (2026-11-28 check of item 3)
    String.raw`(?:났|나왔|생겼)다\s*(?:가\s*)?안\s*(?:났|나왔|생겼)다|오르락\s*내리락)`
);
// How often it comes, for symptoms other than 구토·설사 (which have their own count): "하루에 세 번 정도 머리가 아파요".
// Not a medicine's schedule ("하루 세 번 먹어요").
const HOW_OFTEN_PATTERN = pat(
    String.raw`(?<![가-힣])((?:하루|일주일|한\s*주|한\s*달)(?:에)?\s*(?:\d+|한|두|세|네|다섯|여섯|일곱|여덟|아홉|열|여러|몇)\s*(?:번|차례|회)(?:\s*(?:쯤|정도|씩))*)` +
    String.raw`(?!\s*(?:정도\s*|씩\s*)?(?:[가-힣]+(?:을|를)\s*)?(?:먹|복용|마시|바르|뿌리|넣|맞))`
);

/** Each detail said goes to the present symptom in its own sentence nearest to it, else to the last one before it
 * ("가슴이 아파요. 누우면 더 아파요."). Returns the spans used, which then do not count as unread words. */
function attachDetails(text: string, placed: Array<[number, SymptomObservation]>): Span[] {
  const present = placed.filter(([, item]) => item.status === "present");
  if (present.length === 0) return [];
  // [start, end, detail, where the symptom it speaks of is said, the owner when already settled]: for
  // "기침할 때 가슴이 아파요" the point is the pain at the end (흉통), not the cough named in the condition.
  type Owner = [number, SymptomObservation];
  const found: Array<[number, number, string, number, Owner?]> = [];
  const covering = (point: number) =>
    present.filter(([at, item]) => at <= point && point <= at + item.source_text.length + 2);
  for (const match of DETAIL_TRIGGER_PATTERN.finditer(text)) {
    const condition = match.groups[1]!.replace(/\s+/g, " ");
    const effect = (match.groups[2] ?? match.groups[3] ?? match.groups[4])!;
    const effectStart = match.end - effect.length;
    const between = text.slice(match.start + match.groups[1]!.length, effectStart);
    // Checked over the whole training and eval sentences (2026-11-28): not across a clause ("소변 볼 때 좀 불편하고요, 머리
    // 아픔도 심해지는", "기침할 때 피가 나오고 숨이 차요"), nor a denial ("소변 볼 때 딱히 아프거나 그런 건 아니에요").
    if (/[,，]|(?:고|고요|지만|는데|면서|며|어서|아서|해서)\s/.test(between)) continue;
    const after = text.slice(match.end);
    if (/^[가-힣]{0,3}\s*(?:그런\s*)?(?:건|것은|거는)\s*아니/.test(after)) continue;
    // "누우면 안 아파요", "누우면 아프지 않아요": lying down eases it; "누우면 안 나아져요" keeps nothing (2026-11-28).
    const negated = /(?:안|못)\s*$/.test(between) || /^[가-힣]{0,2}\s*(?:지는?|진)\s*않/.test(after);
    if (negated && match.groups[2]) continue;
    const change = negated || match.groups[2] ? "나아짐" : match.groups[3] ? "심해짐" : "나타남";
    // The symptom whose own words hold the effect ("기침할 때 가슴이 아파요" → 흉통). With none there, a bare
    // "누우면 더 아파요" goes to the symptom just before, but not when another subject sits in between ("기침할 때 피가
    // 나오기 시작했고") or the condition is set against something ("숨 쉴 때는 괜찮아요").
    const holders = covering(effectStart);
    if (holders.length > 0) {
      found.push([match.start, match.end, `${condition} ${change}`, effectStart, holders[holders.length - 1]]);
    } else if (!/[가-힣]+(?:이|가)\s/.test(between) && !/^\s*(?:는|도|은)/.test(between)) {
      found.push([match.start, match.end, `${condition} ${change}`, effectStart]);
    }
  }
  const part = (word: string) => word.replace(/\s+/g, " ");
  const spans = RADIATION_SPAN_PATTERN.finditer(text);
  for (const match of spans) {
    // Owned by the symptom said at its verb: in "허리가 아프고 엉덩이에서 다리까지 저려요" the 저림, not the 요통.
    found.push([match.start, match.end, `${part(match.groups[1]!)}에서 ${part(match.groups[2]!)}까지 퍼짐`, match.end]);
  }
  for (const match of RADIATION_PATTERN.finditer(text)) {
    // The "다리까지 저려요" inside "엉덩이에서 다리까지 저려요" is already said in full.
    if (spans.some((span) => span.start <= match.start && match.start < span.end)) continue;
    found.push([match.start, match.end, match.groups[2]!.startsWith("옮")
      ? `${part(match.groups[1]!)} 쪽으로 옮겨감` : `${part(match.groups[1]!)}까지 퍼짐`, match.end]);
  }
  for (const match of EPISODE_PATTERN.finditer(text)) {
    found.push([match.start, match.end, `한 번에 ${(match.groups[1] ?? match.groups[2] ?? match.groups[3])!.replace(/\s+/g, " ")}`, match.start]);
  }
  for (const match of COMES_AND_GOES_PATTERN.finditer(text)) found.push([match.start, match.end, "오락가락함", match.start]);
  for (const match of HOW_OFTEN_PATTERN.finditer(text)) {
    found.push([match.start, match.end, match.groups[1]!.replace(/\s+/g, " "), match.end]);
  }
  // How far a point is from a symptom's evidence (0 when inside it).
  const away = ([at, item]: [number, SymptomObservation], point: number) =>
    point < at ? at - point : Math.max(0, point - (at + item.source_text.length));
  const used: Span[] = [];
  for (const [start, end, detail, point, settled] of found) {
    // "남편은 가슴이 아픈데 왼팔로 뻗친대요": someone else's, not the patient's (2026-11-27 check of item 1).
    if (otherPersonFor(text, start) !== null) continue;
    const sentenceStart = Math.max(0, ...SENTENCE_SPLIT_PATTERN.finditer(text, 0, start).map((split) => split.end));
    const nextSplit = SENTENCE_SPLIT_PATTERN.search(text.slice(end));
    const sentenceEnd = nextSplit ? end + nextSplit.start : text.length;
    const inSentence = present.filter(([at]) => sentenceStart <= at && at < sentenceEnd);
    const before = present.filter(([at]) => at < start);
    const owner = settled ?? (inSentence.length > 0
      ? inSentence.reduce((best, item) => away(item, point) < away(best, point) ? item : best)
      : before[before.length - 1]);
    if (!owner) continue;
    // How long, how often, comes and goes: only within the owner's own clause (2026-11-28 check of item 3): not
    // "간헐적으로 떨리는 느낌이 있고, 함께 기침도", "살이 빠진 것 같아요, 하루에 몇 번씩 체중계를".
    if (!settled && (/^(?:오락가락함|한 번에 )/.test(detail) || HOW_OFTEN_PATTERN.fullmatch(detail))) {
      const ownerEnd = owner[0] + owner[1].source_text.length;
      const gap = owner[0] >= end ? text.slice(end, owner[0]) : text.slice(Math.min(ownerEnd, start), start);
      if (/[,，]|(?:고|는데|지만|면서|며)\s/.test(gap)) continue;
    }
    used.push([start, end]);
    // "소변 볼 때 따끔해요" is 배뇨통 itself: a condition inside the symptom's own evidence adds nothing.
    // Only for a condition: "머리가 아팠다 안 아팠다 해요" is said inside 두통's words and still kept (2026-11-28).
    if (start >= owner[0] && start < owner[0] + owner[1].source_text.length
        && /(?:나타남|심해짐|나아짐)$/.test(detail) && !/누르면|만지면/.test(detail)) continue;
    const item = owner[1];
    // 구토·설사 keep their count in its own field.
    if (FREQUENCY_SYMPTOMS.has(item.name) && HOW_OFTEN_PATTERN.fullmatch(detail)) continue;
    if (!item.details?.includes(detail)) item.details = [...(item.details ?? []), detail];
  }
  return used;
}

export function extractIntake(input: string, referenceDate: string | null = null): IntakeExtraction {
  const normalized = spokenTemperatureToDigits(spaceGluedWords(politeEndings(dialectWords(knownSoundalikes(
    input.split(/\s+/).filter(Boolean).join(" "),
  )))));
  let matches: Found[] = [];
  // The patient's own words come first: in "아이는 열이 없어요. 저는 열이 나요." the child's "없어요" must not settle
  // the patient's fever. Someone else's words are used only when the patient said nothing of that symptom.
  const own = (found: Match) => otherPersonFor(normalized, found.start) === null;
  for (const symptomRule of RULES) {
    const ownMention = firstSymptomMatch(symptomRule.mention, normalized, own);
    const ownAbsent = firstSymptomMatch(symptomRule.absent, normalized, own);
    const [mention, absent] = ownMention || ownAbsent
      ? [ownMention, ownAbsent]
      : [firstSymptomMatch(symptomRule.mention, normalized), firstSymptomMatch(symptomRule.absent, normalized)];
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
    // "배는 원래 아파요": long-standing, said in the evidence itself. That is its onset, so another symptom's
    // "어제부터" is not carried over to it.
    const longStanding = onset === null ? search(String.raw`원래|평소|예전부터|옛날부터|오래전부터|(?<![가-힣])전부터`, evidence.text) : null;
    if (longStanding) onset = longStanding.text === "원래" ? "원래부터" : longStanding.text === "평소" ? "평소에도" : longStanding.text;
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
        // "어제부터 기침을 하고(,| 그리고)? 복통이", "하고요", "하구" and "기침이랑 복통이" share the onset too
        // (2026-11-11 phone test: the comma STT put in cut it off). A new sentence ("해요. 복통도") does not.
        && (fullmatch(String.raw`(?:(?:(?!요\s)[가-힣 ]){0,8}?(?:고요?|구요?|며|면서|데)|이?랑|하고|과|와)\s*,?\s*(?:(?:그리고|또|또한|게다가|그리고\s*또)\s+)?` +
          String.raw`(?:[가-힣]+(?:이|가|은|는|도)\s+)?`, joined)
          // "머리가 아파요. 배도 같이 아팠어요": "together" says it came with the one before, even in a new sentence.
          || (search(String.raw`같이|함께|덩달아|동시에`, item.source_text) !== null && joined.length <= 30))) {
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
  const detailSpans = attachDetails(normalized, symptomPositions.filter(([, item]) => symptoms.includes(item)));
  // One evidence is chosen per symptom, so "기침은 없어요. 아내도 기침을 해요." settled 기침 on the patient's words
  // and lost the wife's. Another mention said of someone else, and not in a negation, is kept for them too.
  for (const { rule: symptomRule } of matches) {
    const negated = symptomRule.absent.finditer(normalized).map((found): Span => [found.start, found.end]);
    for (const found of symptomRule.mention.finditer(normalized)) {
      const person = otherPersonFor(normalized, found.start);
      if (person === null || negated.some(([start, end]) => start < found.end && found.start < end)) continue;
      if (othersSymptoms.some((other) => other.person === person && other.symptom === symptomRule.name)) continue;
      othersSymptoms.push({ person, symptom: symptomRule.name, source_text: found.text });
    }
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
    ...detailSpans,
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
    // A name read through knownSpelling ("펜이실린" as 페니실린) counts too, by the word as heard.
    const heardAs = fragment.split(/\s+/).map((word) => knownSpelling(word.replace(/(?:이|가|은|는|을|를|도|에)$/, "")));
    // A clause with any word read counts as read. Showing what is left of it instead was tried on 2026-11-28 and
    // dropped: one fewer silent miss in the test half, 143 more prompts in the dev half, and broken leftovers
    // ("섞여 나오는 같아요").
    const recognized = evidenceSpans.some(([spanStart, spanEnd]) => spanStart < end && spanEnd > start)
      || medicationNames.some((name) => fragment.replace(/\s+/g, "").includes(name) || heardAs.includes(name))
      || allergies.some((allergen) => fragment.includes(allergen) || heardAs.includes(allergen));
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
export function otherPersonFor(text: string, evidenceStart: number): string | null {
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
