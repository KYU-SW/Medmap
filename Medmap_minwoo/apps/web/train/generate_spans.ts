// Training sentences for the symptom-span model (HANDOFF 7-1-1, step C).
// A random plan of symptoms, each one of the rules' 65, a named symptom outside them, or a kind at a body site
// (vocabulary.json), goes to a local EXAONE (Ollama), which writes plain patient sentences. A second EXAONE call then
// copies, for each planned symptom, the exact words of the sentence that say it, with the status it hears (copying is
// far more reliable for a 7.8B model than marking while writing, which was tried first). A sentence is kept only when
//   1. every copied part is really in the sentence, the parts do not overlap, and each has the planned status,
//   2. EXAONE finds no other symptom the patient says they have,
//   3. the rules find no present symptom outside the copied parts.
// Run from apps/web, with `ollama serve` up:  node train/generate_spans.ts <calls> [out.jsonl] [workers]
import { appendFileSync, existsSync, readFileSync } from "node:fs";
import { extractIntake } from "../src/intake/extractor.ts";

const MODEL = "exaone3.5:7.8b";
const OLLAMA = "http://127.0.0.1:11434/api/chat";
const calls = Number(process.argv[2] ?? 20);
const out = process.argv[3] ?? "../../local-cache/intake-train/spans.jsonl";
const workers = Number(process.argv[4] ?? 4);

type Word = { name: string; words: string[] };
const vocabulary: { listed: Record<string, string>; symptoms: Word[]; kinds: Word[]; sites: Word[] } =
  JSON.parse(readFileSync(new URL("../src/intake/vocabulary.json", import.meta.url), "utf8"));
// Kinds that only make sense at some sites; the rest can be anywhere.
const SITES_FOR: Record<string, string[]> = {
  분비물: ["귀", "눈", "코", "질", "요도", "배", "항문", "유방"],
  출혈: ["잇몸", "코", "항문", "귀", "유방", "요도", "입", "피부"],
  변색: ["손발톱", "손가락", "발가락", "입술", "피부", "혀"],
  "갈라짐·벗겨짐": ["입술", "발바닥", "손", "뒤꿈치", "피부", "손가락", "혀"],
};
const STATUS_WORDS = { present: "있음", absent: "없음(환자가 없다고 말함)", uncertain: "확실하지 않음(환자가 잘 모르겠다고 말함)" };
const STYLES = [
  "공손한 존댓말", "편한 반말", "음슴체(~함, ~음)", "경상도 사투리", "전라도 사투리", "충청도 사투리",
  "'음', '그러니까', '어' 같은 군말이 많은 말", "띄어쓰기를 거의 하지 않은 글", "짧고 무뚝뚝한 말", "길고 장황한 설명",
  "어르신 말투", "20대 말투", "음성 인식이 받아 적은 것처럼 받침이 한두 군데 틀린 글",
];
const ONSETS = ["오늘 아침부터", "어제부터", "그저께부터", "사흘 전부터", "일주일쯤 전부터", "2주 전부터", "한 달 전부터", "며칠째"];
const PEOPLE = ["남편", "아내", "아이", "엄마", "아빠", "딸", "아들", "동생"];

type Status = keyof typeof STATUS_WORDS;
type Item = { label: string; hint: string; status: Status; onset?: string };
type Plan = { items: Item[]; other?: { person: string; hint: string }; extras: string[]; style: string };

// Things patients say that are not symptoms; the first model, trained without them, flagged "타이레놀을 먹었어요",
// "담배를 피워요" and "허벅지 운동을 해요" as symptoms.
const EXTRAS = [
  "먹고 있는 약 이름(예: 타이레놀, 혈압약, 아스피린, 당뇨약, 연고)", "예전에 앓은 병이나 수술(예: 고혈압, 당뇨, 천식, 맹장 수술, 폐렴 입원)",
  "약이나 음식 알레르기(예: 페니실린, 땅콩)", "담배를 피우는지", "술을 마시는지", "임신 여부", "나이와 성별",
];
const NO_SYMPTOM = [
  "몸 부위가 나오지만 증상이 아닌 일상 이야기(운동, 마사지, 제모, 화장, 옷 등)", "건강검진이나 예방접종을 받으러 왔다는 이야기",
  "예전 치료가 끝났고 지금은 괜찮다는 이야기", "약을 받으러 왔다는 이야기", "몸에 좋은 음식이나 습관 이야기",
];

const pick = <T>(items: readonly T[]) => items[Math.floor(Math.random() * items.length)];
const chance = (p: number) => Math.random() < p;

/** One symptom: a third from the rules' 65 (so the model learns those spans too), the rest from outside them. */
function symptom(): { label: string; hint: string } {
  const roll = Math.random();
  if (roll < 0.35) {
    const name = pick(Object.keys(vocabulary.listed));
    return { label: name, hint: vocabulary.listed[name] };
  }
  if (roll < 0.6) {
    const named = pick(vocabulary.symptoms);
    return { label: named.name, hint: `${named.name}(예: ${named.words[0]})` };
  }
  const kind = pick(vocabulary.kinds);
  const sites = SITES_FOR[kind.name] ? vocabulary.sites.filter((site) => SITES_FOR[kind.name].includes(site.name)) : vocabulary.sites;
  const site = pick(sites);
  return { label: `${kind.name}/${site.name}`, hint: `${pick(site.words)} 부위의 ${kind.name}` };
}

function makePlan(): Plan {
  const style = pick(STYLES);
  // One plan in ten has no symptom at all, so the model also sees sentences where nothing should be marked.
  if (chance(0.1)) return { items: [], extras: [pick(NO_SYMPTOM), ...(chance(0.5) ? [pick(EXTRAS)] : [])], style };
  const count = chance(0.45) ? 1 : chance(0.7) ? 2 : 3;
  const items: Item[] = [];
  while (items.length < count) {
    const next = symptom();
    if (items.some((item) => item.label === next.label)) continue;
    const roll = Math.random();
    const status: Status = roll < 0.7 ? "present" : roll < 0.9 ? "absent" : "uncertain";
    items.push({ ...next, status, ...(status === "present" && chance(0.4) ? { onset: pick(ONSETS) } : {}) });
  }
  return {
    items,
    ...(chance(0.15) ? { other: { person: pick(PEOPLE), hint: symptom().hint } } : {}),
    extras: chance(0.3) ? [pick(EXTRAS)] : [],
    style,
  };
}

function writerPrompt(plan: Plan): string {
  const facts = plan.items.map((item, index) =>
    `${index + 1}. ${item.hint}: ${STATUS_WORDS[item.status]}${item.onset ? `, ${item.onset}` : ""}`);
  return [
    "병원에서 환자가 의사에게 증상을 말로 설명하는 상황이다.",
    ...(plan.items.length
      ? ["아래 증상을 모두, 그리고 증상은 이것만 담은 환자의 말을 서로 다르게 5개 만들어라. 한 개는 1~3문장이다.", ...facts]
      : ["환자가 아무 증상도 말하지 않는 말을 서로 다르게 5개 만들어라. 한 개는 1~3문장이다. 아프다·불편하다 같은 말은 쓰지 마라."]),
    ...plan.extras.map((extra) => `이것도 말에 넣어라(증상이 아니다): ${extra}`),
    ...(plan.other ? [`그리고 환자 본인이 아니라 ${plan.other.person}에게 '${plan.other.hint}' 증상이 있다는 말도 넣어라(표시하지 마라).`] : []),
    `말투: ${plan.style}. 의학 용어보다 사람들이 실제로 쓰는 일상 표현을 써라.`,
    "'없음'은 없다고 분명히 말하고, '확실하지 않음'만 모르겠다고 말하라.",
    'JSON으로만 답하라: {"sentences": ["...", "..."]}',
  ].join("\n");
}

type Span = { start: number; end: number; id: number; text: string };

function judgePrompt(sentences: string[], plan: Plan): string {
  const asked = plan.items.map((item, index) => `(${index + 1}) ${item.hint}`).join(", ");
  return [
    "각 문장은 환자가 의사에게 한 말이다. 다른 사람(가족 등)의 증상은 환자 본인의 증상이 아니다.",
    `1) parts: 다음 증상마다 답하라: ${asked}`,
    "   quote: 그 증상을 말한 부분을 문장에서 글자 그대로 복사한다(부위와 증상을 말하는 말까지, 짧게). 말하지 않았으면 \"\".",
    "   status: present(있다고 함), absent(없다고 함), uncertain(있는지 잘 모르겠다고 함), none(말하지 않음)",
    "2) missed: 위 증상 말고 환자 본인이 있다고 말한 다른 증상을 글자 그대로 적어라. 없으면 [].",
    ...sentences.map((sentence, index) => `문장 ${index + 1}: ${sentence}`),
    'JSON으로만 답하라: {"results": [{"parts": [{"quote": "허벅지가 아파", "status": "present"}], "missed": []}, ...]} (문장 순서대로)',
  ].join("\n");
}

/** Where quote sits in text, ignoring spaces (the judge often copies with a space more or less), or null. */
function locate(text: string, quote: string): [number, number] | null {
  const wanted = quote.replace(/\s+/g, "");
  if (!wanted) return null;
  const kept: number[] = []; // index in text of each non-space character
  for (let index = 0; index < text.length; index += 1) if (!/\s/.test(text[index])) kept.push(index);
  const at = kept.map((index) => text[index]).join("").indexOf(wanted);
  return at < 0 ? null : [kept[at], kept[at + wanted.length - 1] + 1];
}

/** The copied parts as spans of the sentence, or why they cannot be used. */
function spansOf(text: string, parts: Array<{ quote?: string; status?: string }> | undefined, plan: Plan): Span[] | string {
  const spans: Span[] = [];
  for (const [index, item] of plan.items.entries()) {
    const part = parts?.[index];
    if (part?.status !== item.status) return `검토: ${item.status} → ${part?.status ?? "없음"}`;
    const found = locate(text, (part.quote ?? "").trim().replace(/[.,!?]+$/, ""));
    if (!found) return "복사한 말이 문장에 없음";
    // Keep spans alike: no more than one sentence, and with the body part said just before ("귀가 [따뜻해요]").
    const cut = text.slice(found[0], found[1]).search(/[.!?](\s|$)/);
    if (cut > 0) found[1] = found[0] + cut;
    const before = /([가-힣]+(?:이|가|은|는|도|에|에서)\s)$/.exec(text.slice(Math.max(0, found[0] - 12), found[0]));
    if (before) found[0] -= before[1].length;
    spans.push({ start: found[0], end: found[1], id: index + 1, text: text.slice(found[0], found[1]) });
  }
  spans.sort((a, b) => a.start - b.start);
  return spans.some((span, index) => index && span.start < spans[index - 1].end) ? "복사한 말이 겹침" : spans;
}

// A cap on the reply: now and then the model repeats itself until Ollama's repeat limit, which took most of the time.
async function ask(prompt: string, temperature: number, maxTokens: number): Promise<any> {
  const response = await fetch(OLLAMA, {
    method: "POST",
    body: JSON.stringify({
      model: MODEL, stream: false, format: "json", options: { temperature, num_predict: maxTokens },
      messages: [{ role: "user", content: prompt }],
    }),
  });
  if (!response.ok) throw new Error(`Ollama ${response.status}: ${await response.text()}`);
  return JSON.parse((await response.json()).message.content);
}

const squash = (text: string) => text.replace(/[\s.,!?~…]/g, "");
const heldOut = new Set(["intake_eval_set.jsonl", "outside_eval_set.jsonl"].flatMap((file) =>
  readFileSync(new URL(`../eval/${file}`, import.meta.url), "utf8").split("\n").filter((line) => line.trim())
    .map((line) => squash(JSON.parse(line).text))));
const seen = new Set(existsSync(out)
  ? readFileSync(out, "utf8").split("\n").filter(Boolean).map((line) => squash(JSON.parse(line).text)) : []);

let kept = 0;
let dropped = 0;
const reasons = new Map<string, number>();
const drop = (reason: string) => {
  dropped += 1;
  reasons.set(reason, (reasons.get(reason) ?? 0) + 1);
};

async function generateOnce(call: number) {
  const plan = makePlan();
  try {
    const sentences: string[] = [];
    for (const text of (await ask(writerPrompt(plan), 1.0, 600)).sentences ?? []) {
      if (typeof text !== "string" || !text.trim()) continue;
      if (heldOut.has(squash(text)) || seen.has(squash(text))) drop("겹치는 문장");
      else sentences.push(text.trim());
    }
    if (!sentences.length) return;
    const judged = (await ask(judgePrompt(sentences, plan), 0, 800)).results ?? [];
    sentences.forEach((text, index) => {
      const verdict = judged[index] ?? {};
      const spans = spansOf(text, verdict.parts, plan);
      if (typeof spans === "string") return drop(spans);
      // The judge often repeats a planned symptom in other words; only a missed part elsewhere in the sentence counts.
      const missed = (Array.isArray(verdict.missed) ? verdict.missed : []).filter((quote: unknown) => {
        const at = typeof quote === "string" ? locate(text, quote) : null;
        return at && !spans.some((span) => span.start < at[1] && at[0] < span.end);
      });
      if (missed.length) return drop("검토: 표시 안 된 증상");
      const row = { text, spans };
      const outside = extractIntake(row.text).symptoms.filter((found) => found.status === "present")
        .filter((found) => {
          const at = row.text.indexOf(found.source_text);
          return at < 0 || !row.spans.some((span) => span.start < at + found.source_text.length && at < span.end);
        });
      if (outside.length) return drop("규칙: 표시 밖 증상");
      seen.add(squash(row.text));
      kept += 1;
      appendFileSync(out, `${JSON.stringify({
        text: row.text,
        spans: row.spans.map((span) => ({
          start: span.start, end: span.end, text: span.text,
          status: plan.items[span.id - 1].status, label: plan.items[span.id - 1].label,
        })),
        other: plan.other ?? null, extras: plan.extras, style: plan.style,
      })}\n`);
    });
  } catch (error) {
    console.error(`call ${call}:`, error instanceof Error ? error.message : error);
  }
}

let started = 0;
let finished = 0;
async function worker() {
  while (started < calls) {
    started += 1;
    await generateOnce(started);
    finished += 1;
    if (finished % 10 === 0 || finished === calls) console.log(`${finished}/${calls} 호출, 남김 ${kept}, 버림 ${dropped}`);
  }
}
await Promise.all(Array.from({ length: workers }, worker));
console.log("버린 이유:", Object.fromEntries([...reasons].sort((a, b) => b[1] - a[1])));
