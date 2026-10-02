// 클라이언트 지연 계측(REALTIME_FIRST). 숫자·코드만 기록한다 — 전사문·오디오·evidence 는 절대 넣지 않는다.
// e2e 가 window.__medmapPerf 로 읽는다. 메모리 링버퍼(최대 500), 저장소·서버 전송 없음.
const MAX = 500
const entries = []

export function perfMark(name, fields = {}) {
  const entry = { name, t: typeof performance !== 'undefined' ? performance.now() : Date.now() }
  for (const [key, value] of Object.entries(fields)) {
    if (typeof value === 'number' || typeof value === 'boolean' || value === null) entry[key] = value
    else if (typeof value === 'string' && /^[a-z_]{1,24}$/.test(value)) entry[key] = value     // 코드성 문자열만(ws/http/legacy 등)
  }
  entries.push(entry)
  if (entries.length > MAX) entries.shift()
  return entry
}

export function perfEntries() {
  return entries.slice()
}

export function perfReset() {
  entries.length = 0
}

if (typeof window !== 'undefined') window.__medmapPerf = { entries: perfEntries, reset: perfReset }
