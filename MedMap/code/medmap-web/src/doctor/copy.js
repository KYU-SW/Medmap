// Doctor Mode 화면 문구(한 곳). 질환·질문·값 표시명은 여기 두지 않는다 — 서버 응답(terminology 정본)만 쓴다.
// 금지: 오진·틀린 진단·확정/최종 진단·불일치 판정 표현(spec §10). copy.test.js 가 검사한다.
export const COPY = {
  title: '의사 화면',
  prototypeNotice: '합성 데이터로 학습한 연구용 프로토타입입니다. 실제 환자 데이터로 검증되지 않았으며 진단 결과가 아닙니다.',

  loadTitle: '불러올 상담이 없습니다',
  loadBody: '같은 브라우저에서 환자 입력을 마친 뒤 이 화면을 열거나, 상담 기록(JSON)을 붙여 넣거나 파일로 불러오세요.',
  loadPasteLabel: '상담 기록(JSON) 붙여넣기',
  loadPasteSubmit: '불러오기',
  loadFileLabel: '파일로 불러오기',
  loadInvalid: '상담 기록 형식이 올바르지 않습니다.',
  loading: '상담 정보를 불러오는 중입니다.',
  restart: '다른 상담 불러오기',

  summaryTitle: '환자 요약',
  sex: { M: '남성', F: '여성' },
  chiefComplaint: '주 증상',
  positive: '있다고 확인한 증상',
  negative: '없다고 확인한 증상',
  values: '선택한 값',
  unknown: '잘 모르겠다고 답한 질문',
  notApplicable: '해당 없음',
  // 2026-10-02 Phase 2a: 환자가 확인한 소견 전체 표시(표시만 — 모델 입력·cache 의미 불변)
  appliedTitle: '감별 후보 계산에 반영된 정보',
  unappliedTitle: '환자가 확인했지만 감별 후보 계산에 반영되지 않은 정보',
  unappliedNote: '시작 질문 수 제한으로 모델 입력에 들어가지 않은 환자 확인 내용입니다. 추가 질문으로 이 항목이 선택돼 확인되면 그때 반영됩니다.',
  unappliedPositive: '있다고 확인함',
  unappliedNegative: '없다고 확인함',
  unknownTitle: '확인되지 않은 정보',
  answeredCount: (n) => `답한 질문 ${n}개`,

  wdTitle: '현재 생각하는 진단',
  wdHint: '현재 생각하는 진단을 먼저 입력하거나 건너뛰면, 독립 모델의 감별 후보와 추가로 확인할 정보가 열립니다.',
  wdSearchLabel: '진단 검색(모델이 아는 49개 질환)',
  wdNoMatch: '일치하는 질환이 없습니다. 아래에 직접 입력할 수 있습니다.',
  wdFreeLabel: '목록에 없는 진단 직접 입력',
  wdFreeSubmit: '직접 입력',
  wdSkip: '건너뛰기',
  wdChange: '진단 바꾸기',
  wdSkipped: '입력하지 않음',
  wdOutOfScope: '모델 지원 범위 밖이라 비교하지 않습니다.',

  candidatesTitle: '현재 정보에서 독립 모델이 고려한 감별 후보',
  candidatesNotExcluded: '목록에 없는 질환이 배제됐다는 뜻이 아닙니다.',
  candidatesNoCompare: '현재 생각하는 진단과의 일치 여부는 판단하지 않습니다.',
  more: '더 보기',
  less: '접기',

  nextTitle: '후보를 구분하기 위해 추가로 확인할 정보',
  nextCounter: (used, max) => `질문 ${used} / ${max}`,
  patientSaid: '환자가 이미 말한 내용',
  confirmPatient: '이 답으로 확인',
  patientAnswer: { POSITIVE: '예', NEGATIVE: '아니요' },
  budgetReached: '추가 질문 한도에 도달했습니다. 감별 후보는 지금까지 확인된 정보로 계산한 것입니다.',
  noneEligible: '더 확인할 수 있는 질문이 없습니다.',
  unsupported: '이 상담 형태에서는 추가 질문을 고르지 않습니다.',
  answering: '답을 반영하는 중입니다.',

  comingSoonTitle: '준비 중인 기능',
  comingSoonReason: '아직 지원하지 않습니다(근거 데이터 준비 중).',
  comingSoon: {
    timeline: '증상 타임라인',
    diagnosis_coverage: '현재 진단이 설명하는 정보',
    unexplained_findings: '현재 진단으로 설명이 부족한 정보',
    alternatives: '놓치기 쉬운 대안 진단',
    visit: '진료 정보',
    recovery: '회복 경과',
  },

  errorTitle: '요청을 처리하지 못했습니다.',
  retry: '다시 시도',
}

// 금지 표현(spec §10). 문구 검사와 e2e 감사가 같은 목록을 쓴다.
export const FORBIDDEN_CLAIMS = ['오진', '틀렸', '틀린 진단', '확실합니다', '최종 진단', '확정 진단', '불일치', '진단 오류', '예방합니다', '진단했습니다']
