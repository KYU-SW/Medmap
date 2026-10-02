// 내부 ID → 한국어 표시명 조회(presentation only). 정본: medmap/data/terminology_ko.json
// 생성물 ../generated/terminology_ko.json 은 scripts/export_web_terminology.py 가 만든다(직접 편집 금지, ok 항목만 포함).
// 없는 항목은 내부 이름/원문 fallback — 세션·API 요청에는 항상 내부 ID 를 쓴다.
import terms from '../generated/terminology_ko.json'

function lookup(section, key) {
  const table = terms[section]
  return typeof key === 'string' && Object.hasOwn(table, key) ? table[key] : null
}

/** 모델 질환 class 이름 → 한국어 표시명. review_needed·미등록이면 이름 그대로. */
export function diseaseLabel(name) {
  return lookup('diseases', name) ?? name
}

/** evidence ID → 짧은 한국어 표시명(명사구). 없으면 null. */
export function evidenceShortLabel(evidenceId) {
  return lookup('evidence_short', evidenceId)
}

/** value code → 한국어 표시명. 없으면 null. */
export function valueLabel(code) {
  return lookup('values', code)
}

/** evidence ID → 한국어 질문 전문. 없으면(제외 질문·미등록) null. */
export function questionText(evidenceId) {
  return lookup('questions', evidenceId)
}

/** 요약 이력용 질문 문구: 한국어 질문은 그대로, 영문 fallback 질문은 짧은 표시명(없으면 원문). */
export function historyQuestionLabel(question) {
  if (!question.is_fallback) return question.question_ko
  return evidenceShortLabel(question.question_id) ?? question.question_ko
}
