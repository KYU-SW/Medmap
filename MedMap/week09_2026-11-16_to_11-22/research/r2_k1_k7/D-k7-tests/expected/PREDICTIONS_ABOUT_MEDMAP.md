# 실행 전 가설: MedMap(c)이 어디서 틀릴지 (코드 읽기 근거, 2026-11-17 작성, 실행 전)

[연구 가설] 아래는 코드 읽기만으로 세운 예측이다. 실행 후 맞았는지 결과 문서에 표기한다.
- N01.q1 / N02.q1 / N03.q1: stateAsOf 가 review.reviewedAt 을 at 과 비교하지 않음(encounterLink.ts 154·160~162행) → 나중 승인/수정/거절이 과거 시점에 소급될 것.
- N04 / N05: extractCandidates 의 seen(kind:label) 중복 제거(clinicianStatement.ts 133~138행, 원본 기준) → 첫 절 상태만 남을 것.
- N06 / N07: patientCurrent·stateAsOf.patient 가 recordedAt + 문장 위치 순서만 사용, onset/onset_date 미사용 → present 로 덮일 것.
- N08: NeedsCheck 타입에 review 상태 필드가 없음 → q1 false 예상(단 제목은 '확인 필요').
- N09.q1: NOT_DONE 정규식이 '찍지 않' 조건문에도 걸림 → not_done 예상.
- N10.q1: '확진된 것은 아닙니다' 가 NOT_CONFIRMED 에 안 걸리고 RULED_OUT('아닙니다')에 걸림 → ruled_out 예상. N10.q2: CONFIRMED '확진' → confirmed 예상.
- N11.q1/q3: FAMILY 정규식의 '형' 이 '조직형'·'형태' 에 부분 일치 → family/mentioned_only 예상. N11.q5: '어머니' → family 예상.
- N12.q1: ClinicalHandoffV2 에 환자 식별자 없음 → 다른 환자 인계 자료도 수락 예상. N12.q2: '옆 병상 환자분' 은 FAMILY 에 없음 → patient 예상.
- N13.q2: stateAsOf 가 correctionOf 를 사용하지 않음 → 철회형 정정 후에도 suspected 유지 예상. q3 원본 보존은 통과 예상.
- N14: needsCheckOf 가 설명 시점 이후 환자 기록까지 비교 → 확인 필요로 표시될 것(단 '모순' 단정 문구는 아님 예상).
- N15: availableAt 사용 → 통과 예상.
- N16: 출처 '환자 전언' 표지 없음 → resulted 예상.
