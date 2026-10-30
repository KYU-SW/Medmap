# 공식 실행 뒤 기록(2026-10-14)

- 공식 판정 = 첫 실행(FROZEN29_3 최초 실행 12:04, 후처리 12:05–12:07) 산출물. 원본 사본 `logs/first_official_run/`.
- 2회 재현(`run_twice.sh`): 결과 파일 22개 SHA_IDENTICAL(`logs/sha1.txt`·`sha2.txt`), 첫 공식 실행과도 평가 결과 파일 SHA 동일. 판정 동일.
  재현 실행의 latency.json·memory.json·판정 문서(CPU p95 값만 다름)는 `logs/twice_run_outputs/`, 공식 파일은 첫 실행본으로 복원.
- 동결 뒤 발견: FROZEN29_3 입력 3개(F0290 '목 뒤가 아파요' · F0320 '속이 화끈거려요' · F0457 '혈관성 편두통 진단을 받았어요')가 지시문 예시와 같은 문장이라
  회귀 사례·단위 테스트·개발 중 시험으로 이미 실행됨(생성기 중복 제거에 지시문 예시·회귀 목록을 넣지 않은 실수). FROZEN 은 바꾸지 않음.
  3건 제외 민감도(EXPLORATORY, `outputs/frozen_sensitivity_excluding_exposed.json`): R2 coverage 0.7375(전체 0.7397) — 결론 변화 없음.
- 동결 뒤 발견(EXPLORATORY, 규칙 변경 없음): FROZEN 남은 미연결의 주원인 = STEP29 IDEOPHONE_MISMATCH 가드가 같은 뜻 다른 의성어('빙빙'≠'뱅뱅', '벌렁벌렁'≠'콩닥콩닥')를 막음 ·
  STEP29.1 EVIDENCE_IDEOPHONE_MISSING('온몸에 기력이 없어요' → fever 차단, 차단 자체는 올바르나 fatigue 미연결) · '물 같은 변을 봐요' 사전 없음 · '목덜미가 결려요' 구문 미추출.
