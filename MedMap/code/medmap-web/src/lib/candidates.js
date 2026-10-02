/** 확률을 소수 한 자리 퍼센트 문자열로. IEEE754 표현 오차를 그대로 반영한다(0.2435 → '24.3'). */
export function formatPercent(probability) {
  return (probability * 100).toFixed(1)
}

export function toCandidateRows(turn) {
  const before = new Map((turn.diagnoses_before ?? []).map((d) => [d.name, d.probability]))
  return turn.diagnoses.map((d) => {
    const previous = before.has(d.name) ? before.get(d.name) : null
    let direction = 'same'
    if (previous !== null) {
      if (d.probability > previous) direction = 'up'
      else if (d.probability < previous) direction = 'down'
    }
    return { name: d.name, probability: d.probability, previous, direction }
  })
}
