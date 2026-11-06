// Names a symptom the span model found outside the rules (HANDOFF 7-1-1, step E):
// (1) a named symptom, (2) "kind/site", (3) "기타". The caller first tries the rules on the part alone, so a part that
// is one of the 65 said in words the rules know keeps that name.
import vocabulary from "./vocabulary.json" with { type: "json" };

type Word = { name: string; words: string[] };
// Compared as letters (NFD), so "숨을 안 쉬" also matches "숨을 안 쉰대" where 쉬 and ㄴ share a syllable.
const squash = (text: string) => text.replace(/\s+/g, "").normalize("NFD");

// "삼키기 힘들" also matches "삼키기가 힘들어": a particle (up to two syllables) may sit where the word has a space.
const patterns = new Map<string, RegExp>();
const pattern = (word: string) =>
  patterns.get(word) ?? patterns.set(word, new RegExp(word.trim().split(/\s+/).map(squash).join(".{0,6}"))).get(word)!;

// A one-syllable word ("질", "입", "배") counts only on its own, maybe with a particle: not in 딸꾹질, 입원 or 배고파.
const alone = (word: string) => patterns.get(`1:${word}`) ?? patterns.set(`1:${word}`,
  new RegExp(`(?<![가-힣])${word}(?=$|[^가-힣]|이|가|은|는|을|를|에|도|과|와|랑|쪽|만|까지|부터|의)`)).get(`1:${word}`)!;

/** The entry whose longest word is in the part (the longer word wins: "손목" over "목"), or null. */
function longest(entries: Word[], part: string): Word | null {
  const text = squash(part);
  // A word with no space in it is looked for within the words as written, not across a space: "색이 빨개요" has no
  // "이빨" (teeth) in it, though "색이빨개요" does.
  const spaced = part.normalize("NFD");
  const found = (word: string) => (/^[가-힣]$/.test(word) ? alone(word).test(part)
    : /\s/.test(word.trim()) ? pattern(word).test(text) : spaced.includes(squash(word)));
  let best: Word | null = null;
  let size = 0;
  for (const entry of entries) {
    for (const word of entry.words) {
      const wanted = squash(word);
      if (wanted.length > size && found(word)) {
        best = entry;
        size = wanted.length;
      }
    }
  }
  return best;
}

// A kind at a site the rules' 65 already name ("65 + body site = on the list", HANDOFF 7-1-1): 부종/종아리 is 부종.
const LISTED_KIND: Record<string, string> = { 부종: "부종", "저림·감각 이상": "저림", 가려움: "가려움", "발진·붉어짐": "발진" };
const LISTED_PAIN: Record<string, string> = {
  머리: "두통", 뒷머리: "두통", 정수리: "두통", 관자놀이: "두통", 이마: "두통", 배: "복통", 명치: "복통", 허리뼈: "요통",
  무릎: "관절 통증", 어깨: "관절 통증", 발목: "관절 통증", 팔꿈치: "관절 통증", 고관절: "관절 통증", 턱: "관절 통증",
  귀: "귀 통증", 눈: "눈 통증", 이: "치통", 아랫니: "치통", 윗니: "치통", 목구멍: "인후통", 가슴: "흉통",
  입: "입안 통증", 혀: "입안 통증",
};
// The same for other kinds at a site the 65 name: 출혈/코 is 코피, 시림·차가움/손 is 손발 차가움.
const LISTED_AT_SITE: Record<string, string> = {
  "출혈/코": "코피", "분비물/눈": "눈 분비물", "통증/온몸": "근육통", "경련·떨림/손": "떨림",
  "시림·차가움/손": "손발 차가움", "시림·차가움/발": "손발 차가움", "시림·차가움/손가락": "손발 차가움",
  "시림·차가움/발가락": "손발 차가움", "결림·뻐근함/목": "목 결림", "결림·뻐근함/뒷목": "목 결림",
};

export function nameSymptom(part: string): string {
  // Named symptoms beyond the list and the list's own words for what its rules missed (listedWords), longest first.
  const named = longest([...vocabulary.symptoms, ...vocabulary.listedWords], part);
  if (named) return named.name;
  const kind = longest(vocabulary.kinds, part);
  const site = longest(vocabulary.sites, part);
  if (!kind || !site) return "기타";
  return LISTED_KIND[kind.name] ?? (kind.name === "통증" ? LISTED_PAIN[site.name] : undefined)
    ?? LISTED_AT_SITE[`${kind.name}/${site.name}`] ?? `${kind.name}/${site.name}`;
}

export const isListed = (name: string) => name in vocabulary.listed;

/** The body site said in the part ("관자놀이도 욱신거려" → 관자놀이), or null. */
export const siteOf = (part: string) => longest(vocabulary.sites, part)?.name ?? null;
