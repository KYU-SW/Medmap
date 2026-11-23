# 정답 정정 메모 (expected_v1.json 은 수정하지 않음)

결과를 본 뒤 정답 값을 바꾼 항목: **없음**.

해석 여지가 있는 정답(값은 유지, 판단 근거만 기록):
- N14.q1 (기대 false): MedMap 은 '확인 필요'로만 표시하고 '서로 다른 시점일 수 있음'을 덧붙인다. 보수적 표시를 허용하는 관점에서는 오류가 아닐 수 있어 dangerous 로 두지 않았다(MISS 로만 계산).
- N16.q1 (기대 hearsay): 의사가 환자 전언을 옮긴 검사 결과. 'resulted' 를 위험으로 본 것은 작성자 해석이며 의료 전문가 확인 없음.
- N12.q2: MedMap 어휘에 'other' 가 없어 'family' 도 허용으로 두었다.
- N09.q2: '할 예정' 은 어휘에 없어 not_done 또는 result_uncertain 을 허용.

하네스 수정(정답 아님): v1 실행에서 (d)(e)의 patient_current 질의가 질의 시각=FAR 와 txTo=FAR 가 같아 항상 '__none__' 이 되는 하네스 버그 → NOW_Q 로 수정(v2). (c) MedMap 값은 v1·v2 동일. v1 코드: `../logs/run_v1_before_harness_fix.ts.txt`, v1 로그: `../logs/run_20261117_202330.log`.
