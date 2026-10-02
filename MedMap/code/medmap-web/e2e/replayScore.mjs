// VAD replay 채점(순수 함수). stt-vad-replay.e2e.mjs 와 replayScore.check.mjs(node --test) 가 쓴다.
const TOL = Number(process.env.BOUNDARY_TOL ?? 2)

export const norm = (t) => t.replace(/[\s.,!?·~"'“”‘’()\-…]/g, '')
export const pct = (xs, q) => {
  if (!xs.length) return null
  const s = [...xs].sort((a, b) => a - b)
  const i = (s.length - 1) * q
  const lo = Math.floor(i); const hi = Math.ceil(i)
  return Math.round((s[lo] + (s[hi] - s[lo]) * (i - lo)) * 10) / 10
}

// 정답(ref) ↔ 가설(hyp) 편집거리 정렬. hyp 위치 j 마다 정렬 경로가 지나는 ref 위치 범위 [lo, hi] 를 돌려준다.
export function align(ref, hyp) {
  const a = [...ref]; const b = [...hyp]
  const n = a.length; const m = b.length
  const d = Array.from({ length: n + 1 }, (_, i) => { const r = new Array(m + 1).fill(0); r[0] = i; return r })
  for (let j = 0; j <= m; j++) d[0][j] = j
  for (let i = 1; i <= n; i++) for (let j = 1; j <= m; j++) {
    d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1))
  }
  let i = n; let j = m; let del = 0; let ins = 0; let sub = 0
  const range = Array.from({ length: m + 1 }, () => [Infinity, -Infinity])
  const mark = (ii, jj) => { range[jj][0] = Math.min(range[jj][0], ii); range[jj][1] = Math.max(range[jj][1], ii) }
  mark(i, j)
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && d[i][j] === d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)) {
      if (a[i - 1] !== b[j - 1]) sub++
      i--; j--
    } else if (i > 0 && d[i][j] === d[i - 1][j] + 1) { del++; i-- } else { ins++; j-- }
    mark(i, j)
  }
  return { dist: d[n][m], del, ins, sub, range }
}

export function score(rec, segments) {
  const sentences = rec.sentences.map(norm)
  const ref = sentences.join('')
  const ends = []
  let acc = 0
  for (const s of sentences.slice(0, -1)) { acc += s.length; ends.push(acc) }
  const texts = segments.map((s) => norm(s.text)).filter(Boolean)
  const kept = segments.filter((s) => norm(s.text))
  const hyp = texts.join('')
  const al = align(ref, hyp)
  const near = ([lo, hi], e) => e >= lo - TOL && e <= hi + TOL
  const boundaries = []
  let pos = 0
  for (let k = 0; k < texts.length - 1; k++) {
    pos += texts[k].length
    boundaries.push({ range: al.range[pos], reason: kept[k].reason })
  }
  const falseEndpoints = boundaries.filter((b) => b.reason !== 'manual' && !ends.some((e) => near(b.range, e))).length
  const missed = ends.filter((e) => !boundaries.some((b) => near(b.range, e))).length
  const dup = texts.some((t, k) => t.length >= 4 && texts.some((u, l) => l !== k && u === t))
  const numbers = rec.numbers ?? []
  // 숫자 분리: FINAL 경계가 숫자 표현(span) 안쪽에 떨어짐("삼십팔 점" | "오 도") — 임상 숫자 안전 문제로 따로 센다
  const sentStart = []
  let off = 0
  for (const s of sentences) { sentStart.push(off); off += s.length }
  let numericSplit = 0
  for (const n of numbers) {
    if (!n.span) continue
    const at = sentences[n.sentence].indexOf(norm(n.span))
    if (at < 0) continue
    const a = sentStart[n.sentence] + at
    const b = a + norm(n.span).length
    if (boundaries.some(({ range: [lo, hi] }) => hi > a && lo < b)) numericSplit++
  }
  const numericPass = numbers.filter((n) => n.accept.some((v) => hyp.includes(norm(v)))).length
  return {
    n_text_finals: texts.length, boundaries: boundaries.length, false_endpoints: falseEndpoints,
    internal_sentence_ends: ends.length, missed_endpoints: missed,
    delayed_end: kept.length > 0 && kept[kept.length - 1].reason === 'manual',
    cer: Math.round((al.dist / Math.max(1, ref.length)) * 1000) / 1000, del: al.del, ins: al.ins, sub: al.sub, dup,
    numeric_pass: numericPass, numeric_total: numbers.length, numeric_split: numericSplit,
  }
}


// T_partial 표본(패킷 캡처 → 그 오디오를 덮는 첫 partial 표시). VAD 음성 구간 안·첫 300 ms 이후 패킷만.
// 발화 안 쉼(서버 FINAL srv_ms.pauses_ms) 동안의 패킷은 뺀다: 쉼에는 새 글자가 없고 후보 계산 중에는 partial 을 멈추므로
// 다음 말이 나올 때까지의 대기가 T_partial 로 잘못 잡힌다(1500 ms census 에서 p95 1245 로 부풀려졌던 원인).
export function tPartialSamples(packets, partials, spans, pauses) {
  const values = []
  let excludedPause = 0
  for (const p of packets) {
    if (p.audio_ms < 300 || !spans.some(([a, b]) => p.audio_ms >= a && p.audio_ms <= b)) continue
    if (pauses.some(([a, b]) => p.audio_ms > a && p.audio_ms <= b)) { excludedPause++; continue }
    const shown = partials.find((x) => x.audio_ms >= p.audio_ms && x.t >= p.t)
    if (shown) values.push(Math.round((shown.t - p.t) * 10) / 10)
  }
  return { values, excluded_pause: excludedPause }
}
