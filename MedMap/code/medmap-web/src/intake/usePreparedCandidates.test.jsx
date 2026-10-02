import { act, renderHook } from '@testing-library/react'
import { usePreparedCandidates } from './usePreparedCandidates'

const cand = (id) => ({ evidence_id: id, status: 'POSITIVE', label_ko: id, matched_text: id, initial_eligible: true })

function deferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}

test('prepare → pending → prepared(text, candidates); takeIfSame only for the same (trimmed) text', async () => {
  const d = deferred()
  const extract = vi.fn(() => d.promise)
  const { result } = renderHook(() => usePreparedCandidates({ extract }))
  act(() => result.current.prepare('  기침이 나요 '))
  expect(extract).toHaveBeenCalledWith('기침이 나요')
  expect(result.current.pending).toBe(true)
  await act(async () => d.resolve([cand('E_201')]))
  expect(result.current.pending).toBe(false)
  expect(result.current.prepared).toEqual({ text: '기침이 나요', candidates: [cand('E_201')] })
  expect(result.current.takeIfSame('기침이 나요')).toEqual([cand('E_201')])
  expect(result.current.takeIfSame('기침이 나요 열도')).toBeNull()
})

test('two prepares: the first response arriving late is discarded (request generation)', async () => {
  const first = deferred()
  const second = deferred()
  const extract = vi.fn().mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
  const { result } = renderHook(() => usePreparedCandidates({ extract }))
  act(() => result.current.prepare('기침'))
  act(() => result.current.prepare('기침 열'))
  await act(async () => second.resolve([cand('E_91')]))
  await act(async () => first.resolve([cand('E_201')]))
  expect(result.current.prepared).toEqual({ text: '기침 열', candidates: [cand('E_91')] })
})

test('invalidate drops the prepared result and ignores the in-flight response', async () => {
  const d = deferred()
  const { result } = renderHook(() => usePreparedCandidates({ extract: () => d.promise }))
  act(() => result.current.prepare('기침'))
  act(() => result.current.invalidate())
  await act(async () => d.resolve([cand('E_201')]))
  expect(result.current.prepared).toBeNull()
  expect(result.current.pending).toBe(false)
  expect(result.current.takeIfSame('기침')).toBeNull()
})

test('extract failure is silent: nothing prepared, no throw (확인하기 falls back to the normal extract)', async () => {
  const d = deferred()
  const { result } = renderHook(() => usePreparedCandidates({ extract: () => d.promise }))
  act(() => result.current.prepare('기침'))
  await act(async () => d.reject(new Error('down')))
  expect(result.current.prepared).toBeNull()
  expect(result.current.pending).toBe(false)
})

test('empty text is not sent', () => {
  const extract = vi.fn()
  const { result } = renderHook(() => usePreparedCandidates({ extract }))
  act(() => result.current.prepare('   '))
  expect(extract).not.toHaveBeenCalled()
})
