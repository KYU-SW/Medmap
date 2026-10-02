import { useCallback, useRef, useState } from 'react'
import { extractIntake } from '../api/client.js'
import { perfMark } from '../voice/perf.js'

// M4: 음성 FINAL 이 입력칸에 붙으면 매퍼 후보를 미리 계산해 둔다('확인 대기'). speculative compute 일 뿐이다:
// - 세션·PatientState·앱 pending/오류 상태를 건드리지 않는다(session.extract 가 아니라 상태 없는 extractIntake 를 직접 부른다).
// - 저장소 쓰기 없음. 결과는 이 hook 메모리에만 있고, [확인하기] 때 같은 텍스트면 그대로 확인 단계에 쓰인다(확인은 여전히 사용자 몫).
// - 요청 세대 번호로 최신 요청의 응답만 채택한다(늦게 온 이전 응답·invalidate 이후 응답은 버림).
const defaultExtract = async (text) => (await extractIntake(text)).candidates

export function usePreparedCandidates({ extract = defaultExtract, now = () => performance.now() } = {}) {
  const [prepared, setPrepared] = useState(null)       // { text, candidates } | null
  const [pending, setPending] = useState(false)
  const generation = useRef(0)
  const preparedRef = useRef(null)

  const prepare = useCallback((raw) => {
    const text = (raw ?? '').trim()
    const mine = ++generation.current
    preparedRef.current = null
    setPrepared(null)
    if (!text) { setPending(false); return }
    setPending(true)
    const startedAt = now()
    perfMark('prep_request', {})
    let request
    try { request = Promise.resolve(extract(text)) } catch (err) { request = Promise.reject(err) }
    request
      .then((candidates) => {
        if (mine !== generation.current || !Array.isArray(candidates)) return
        const value = { text, candidates }
        preparedRef.current = value
        setPrepared(value)
        perfMark('prep_ready', { t_prep_request: now() - startedAt, n: candidates.length })
      })
      .catch(() => {})                                  // 실패는 조용히: [확인하기]가 평소처럼 extract 한다
      .finally(() => { if (mine === generation.current) setPending(false) })
  }, [extract, now])

  const invalidate = useCallback(() => {
    generation.current += 1
    preparedRef.current = null
    setPrepared(null)
    setPending(false)
  }, [])

  const takeIfSame = useCallback((raw) => {
    const value = preparedRef.current
    return value && value.text === (raw ?? '').trim() ? value.candidates : null
  }, [])

  return { prepared, pending, prepare, invalidate, takeIfSame }
}
