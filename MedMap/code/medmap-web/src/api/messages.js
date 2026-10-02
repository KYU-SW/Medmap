const RESTART = { body: '처음부터 다시 시작해 주세요.', action: 'restart' }

export function userMessage(error) {
  const code = error?.code ?? 'UNKNOWN_ERROR'
  if (error) console.error('[medmap]', code, error.message)   // 내부 코드는 콘솔에만

  if (code === 'NETWORK_ERROR') {
    return { title: '연결하지 못했습니다.', body: '네트워크 상태를 확인한 뒤 다시 시도해 주세요.', action: 'retry' }
  }
  if (code === 'ENGINE_NOT_READY' || error?.status === 503) {
    return { title: '준비 중입니다. 잠시 후 다시 시도해 주세요.', body: '', action: 'retry' }
  }
  if (code === 'MEDMAP_UNSUPPORTED_SESSION_SHAPE') {
    return { title: '이 기록으로는 추가 확인을 이어갈 수 없습니다.', ...RESTART }
  }
  if (code === 'MEDMAP_ALREADY_ASKED' || code === 'MEDMAP_UNEXPECTED_ANSWER') {
    return { title: '이미 확인한 항목입니다.', ...RESTART }
  }
  if (error?.status === 409) {
    return { title: '지금 상태에서는 답할 수 없는 항목입니다.', ...RESTART }
  }
  if (error?.status >= 500) {
    return { title: '잠시 문제가 있었습니다.', body: '잠시 후 다시 시도해 주세요.', action: 'retry' }
  }
  return { title: '입력을 다시 확인해 주세요.', body: '', action: 'none' }
}
