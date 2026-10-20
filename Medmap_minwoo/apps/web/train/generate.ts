// Synthetic training sentences for the symptom model (HANDOFF 7-1, step 2).
// A random set of facts (symptoms with a status, maybe someone else's symptom, a medicine or a past illness) goes to
// a local EXAONE (Ollama) that writes patient sentences in a random speaking style. A sentence is kept only when
// EXAONE, reading it back without the plan, finds exactly the planned symptoms with the planned status.
// The rules do not judge the planned symptoms: sentences they misread are the ones the model should learn (their
// reading is kept as rules_wrong). They only drop a sentence where they find an unplanned symptom present.
// Run from apps/web, with `ollama serve` up:  node train/generate.ts <calls> [out.jsonl] [workers]
// Workers send calls at once; start the server with OLLAMA_NUM_PARALLEL at least that many so the GPU batches them.
import { appendFileSync, existsSync, readFileSync } from "node:fs";
import { extractIntake } from "../src/intake/extractor.ts";

const MODEL = "exaone3.5:7.8b";
const OLLAMA = "http://127.0.0.1:11434/api/chat";
const calls = Number(process.argv[2] ?? 20);
const out = process.argv[3] ?? "../../local-cache/intake-train/generated.jsonl";
const workers = Number(process.argv[4] ?? 4);

// The rules' 65 symptoms, with a plain hint so the writer knows what each one means.
const SYMPTOMS: Record<string, string> = {
  두통: "머리가 아픔", 발열: "열이 남", 기침: "기침", 호흡곤란: "숨이 참", "가슴 답답함": "가슴이 답답함",
  복통: "배가 아픔", 구토: "토함", 흉통: "가슴이 아픔", 인후통: "목구멍이 아픔", 콧물: "콧물", 코막힘: "코가 막힘",
  가래: "가래", 오한: "춥고 떨림", 근육통: "몸살, 온몸이 쑤심", 요통: "허리가 아픔", 어지러움: "어지러움",
  메스꺼움: "속이 울렁거림", 설사: "설사", 변비: "변을 못 봄", 발진: "피부에 붉은 것이나 두드러기가 남",
  피로: "피곤하고 기운이 없음", 두근거림: "심장이 두근거림", 저림: "손발이나 팔다리가 저림", 소화불량: "체함, 더부룩함",
  속쓰림: "속이 쓰림", 식욕부진: "입맛이 없음", 불면: "잠을 못 잠", 부종: "몸이 부음", "귀 통증": "귀가 아픔",
  "눈 통증": "눈이 아픔", 치통: "이가 아픔", 식은땀: "식은땀", 가려움: "가려움", "시야 이상": "눈이 침침하거나 흐리거나 겹쳐 보임",
  떨림: "손이 떨림", 이명: "귀에서 소리가 남", 코피: "코피", 객혈: "기침할 때 피가 나옴", 토혈: "피를 토함",
  혈변: "변에 피가 섞이거나 변이 까맘", 혈뇨: "소변에 피가 섞임", 배뇨통: "소변 볼 때 아픔", 빈뇨: "소변을 자주 봄",
  기절: "쓰러지거나 정신을 잃음", 마비: "한쪽 팔다리에 힘이 빠지거나 얼굴이 처짐", "말 어눌함": "말이 어눌함",
  "쉰 목소리": "목소리가 쉼", "체중 감소": "살이 빠짐", 경련: "경련, 발작", "관절 통증": "무릎·어깨·발목 같은 관절이 아픔",
  "입안 통증": "입안이나 혀가 헐거나 아픔", 재채기: "재채기", 쌕쌕거림: "숨 쉴 때 쌕쌕 소리", "배뇨 곤란": "소변이 잘 안 나옴",
  "눈 충혈": "눈이 빨개짐", 생리통: "생리할 때 아픔", "복부 팽만": "배에 가스가 차고 빵빵함", "목 이물감": "목에 뭐가 걸린 느낌",
  "눈 분비물": "눈곱이나 눈물이 많이 남", "목 결림": "뒷목이 당기거나 뻐근함", "손발 차가움": "손발이 차가움",
  우울감: "기분이 처지고 우울함", 불안감: "불안하고 초조함", "청력 저하": "귀가 잘 안 들림", 입마름: "입이 마름",
};
const NAMES = Object.keys(SYMPTOMS);
const STATUS_WORDS = { present: "있음", absent: "없음(환자가 없다고 말함)", uncertain: "확실하지 않음(환자가 잘 모르겠다고 말함)" };
const STYLES = [
  "공손한 존댓말", "편한 반말", "음슴체(~함, ~음)", "경상도 사투리", "전라도 사투리", "충청도 사투리",
  "'음', '그러니까', '어' 같은 군말이 많은 말", "띄어쓰기를 거의 하지 않은 글", "짧고 무뚝뚝한 말", "길고 장황한 설명",
  "어르신 말투", "20대 말투", "음성 인식이 받아 적은 것처럼 받침이 한두 군데 틀린 글",
];
const ONSETS = ["오늘 아침부터", "어제부터", "그저께부터", "사흘 전부터", "일주일쯤 전부터", "2주 전부터", "한 달 전부터", "며칠째"];
const DETAILS = ["아주 심함", "참을 만함", "10점 중 7점", "점점 심해짐", "조금 나아짐", "하루에 서너 번"];
const PEOPLE = ["남편", "아내", "아이", "엄마", "아빠", "딸", "아들", "동생"];
const MEDICINES = ["타이레놀", "아스피린", "혈압약", "감기약", "소화제", "진통제", "당뇨약"];
const HISTORY = ["고혈압", "당뇨", "천식", "위염", "갑상선 질환", "맹장 수술"];

type Status = keyof typeof STATUS_WORDS;
type Plan = {
  symptoms: Array<{ name: string; status: Status; onset?: string; detail?: string }>;
  other?: { person: string; symptom: string };
  medicine?: string;
  history?: string;
  style: string;
};

const pick = <T>(items: readonly T[]) => items[Math.floor(Math.random() * items.length)];
const chance = (p: number) => Math.random() < p;

function makePlan(): Plan {
  const count = chance(0.4) ? 1 : chance(0.67) ? 2 : 3;
  const names = new Set<string>();
  while (names.size < count) names.add(pick(NAMES));
  const symptoms = [...names].map((name) => {
    const roll = Math.random();
    const status: Status = roll < 0.7 ? "present" : roll < 0.9 ? "absent" : "uncertain";
    return {
      name, status,
      ...(status === "present" && chance(0.5) ? { onset: pick(ONSETS) } : {}),
      ...(status === "present" && chance(0.3) ? { detail: pick(DETAILS) } : {}),
    };
  });
  const others = NAMES.filter((name) => !names.has(name));
  return {
    symptoms,
    ...(chance(0.15) ? { other: { person: pick(PEOPLE), symptom: pick(others) } } : {}),
    ...(chance(0.15) ? { medicine: pick(MEDICINES) } : {}),
    ...(chance(0.1) ? { history: pick(HISTORY) } : {}),
    style: pick(STYLES),
  };
}

function writerPrompt(plan: Plan): string {
  const facts = plan.symptoms.map(({ name, status, onset, detail }) =>
    `- ${SYMPTOMS[name]}: ${STATUS_WORDS[status]}${onset ? `, ${onset}` : ""}${detail ? `, ${detail}` : ""}`);
  if (plan.other) facts.push(`- 환자 본인이 아니라 ${plan.other.person}에게 '${SYMPTOMS[plan.other.symptom]}' 증상이 있음`);
  if (plan.medicine) facts.push(`- ${plan.medicine}을(를) 먹고 있음`);
  if (plan.history) facts.push(`- 예전에 ${plan.history} 진단(또는 수술)을 받음`);
  return [
    "병원에서 환자가 의사에게 증상을 말로 설명하는 상황이다.",
    "아래 사실을 모두, 그리고 이것만 담은 환자의 말을 서로 다르게 5개 만들어라. 한 개는 1~3문장이다.",
    ...facts,
    `말투: ${plan.style}.`,
    "의학 용어보다 사람들이 실제로 쓰는 일상 표현을 써라. 사실에 없는 증상을 덧붙이지 마라.",
    "'없음'인 증상은 없다고 분명히 말하고, '확실하지 않음'인 증상만 모르겠다고 말하라. '있음'인 증상에는 모르겠다는 말을 붙이지 마라.",
    'JSON으로만 답하라: {"sentences": ["...", "..."]}',
  ].join("\n");
}

// The judge is asked about the planned symptoms one by one (a 7.8B model drops "absent" ones when asked to list
// everything), and separately for any other symptom the patient says they have.
function judgePrompt(sentences: string[], plan: Plan): string {
  const asked = plan.symptoms.map(({ name }) => `${name}(${SYMPTOMS[name]})`).join(", ");
  return [
    "각 문장은 환자가 의사에게 한 말이다. 다른 사람(가족 등)의 증상, 약, 예전에 앓은 병은 환자 본인의 증상이 아니다.",
    `1) checked: 다음 증상마다 환자 본인이 어떻게 말했는지 답하라: ${asked}`,
    "   present(있다고 함), absent(없다고 함), uncertain(있는지 잘 모르겠다고 함), none(말하지 않음)",
    "2) other: 1)의 증상 말고 환자 본인이 있다고 말한 증상을 아래 목록 이름으로 적어라. 없으면 [].",
    `   목록: ${NAMES.filter((name) => !plan.symptoms.some((symptom) => symptom.name === name)).join(", ")}`,
    ...sentences.map((sentence, index) => `문장 ${index + 1}: ${sentence}`),
    'JSON으로만 답하라: {"results": [{"checked": {"증상 이름": "present"}, "other": []}, ...]} (문장 순서대로)',
  ].join("\n");
}

async function ask(prompt: string, temperature: number): Promise<any> {
  const response = await fetch(OLLAMA, {
    method: "POST",
    body: JSON.stringify({
      model: MODEL, stream: false, format: "json", options: { temperature },
      messages: [{ role: "user", content: prompt }],
    }),
  });
  if (!response.ok) throw new Error(`Ollama ${response.status}: ${await response.text()}`);
  return JSON.parse((await response.json()).message.content);
}

const squash = (text: string) => text.replace(/[\s.,!?~…]/g, "");
const evalTexts = new Set(
  readFileSync(new URL("../eval/intake_eval_set.jsonl", import.meta.url), "utf8")
    .split("\n").filter((line) => line.trim()).map((line) => squash(JSON.parse(line).text)),
);
const seen = new Set(
  existsSync(out) ? readFileSync(out, "utf8").split("\n").filter(Boolean).map((line) => squash(JSON.parse(line).text)) : [],
);

function judgeDisagrees(judged: { checked?: Record<string, string>; other?: string[] } | undefined, plan: Plan): string | null {
  for (const { name, status } of plan.symptoms) {
    const got = judged?.checked?.[name] ?? "none";
    if (got !== status) return `검토: ${status} → ${got}`;
  }
  const extra = (judged?.other ?? []).filter((name) => NAMES.includes(name));
  return extra.length ? "검토: 계획 밖 증상" : null;
}

let kept = 0;
let dropped = 0;
const reasons = new Map<string, number>();
const drop = (reason: string) => {
  dropped += 1;
  reasons.set(reason, (reasons.get(reason) ?? 0) + 1);
};

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

async function generateOnce(call: number) {
  const plan = makePlan();
  try {
    const sentences: string[] = ((await ask(writerPrompt(plan), 1.0)).sentences ?? [])
      .filter((text: unknown): text is string => typeof text === "string" && text.trim().length > 0)
      .filter((text) => !evalTexts.has(squash(text)) && !seen.has(squash(text)));
    if (!sentences.length) return;
    const judged = (await ask(judgePrompt(sentences, plan), 0)).results ?? [];
    sentences.forEach((text, index) => {
      const reason = judgeDisagrees(judged[index], plan);
      if (reason) return drop(reason);
      const rules = new Map(extractIntake(text).symptoms.map((symptom) => [symptom.name, symptom.status]));
      // The writer sometimes adds a symptom and the judge misses it; the rules rarely invent a present one.
      const planned = new Set(plan.symptoms.map(({ name }) => name));
      if ([...rules].some(([name, status]) => !planned.has(name) && status === "present")) return drop("규칙: 계획 밖 증상 있음");
      seen.add(squash(text));
      kept += 1;
      appendFileSync(out, `${JSON.stringify({
        text,
        symptoms: plan.symptoms.map(({ name, status }) => ({ name, status })),
        // Where the rules read this sentence differently from its label: the cases the model should add.
        rules_wrong: [
          ...plan.symptoms.filter(({ name, status }) => rules.get(name) !== status)
            .map(({ name }) => `${name}:${rules.get(name) ?? "missed"}`),
          ...[...rules.keys()].filter((name) => !plan.symptoms.some((symptom) => symptom.name === name))
            .map((name) => `${name}:extra`),
        ],
        other: plan.other ?? null, medicine: plan.medicine ?? null, history: plan.history ?? null, style: plan.style,
      })}\n`);
    });
  } catch (error) {
    console.error(`call ${call}:`, error instanceof Error ? error.message : error);
  }
}
