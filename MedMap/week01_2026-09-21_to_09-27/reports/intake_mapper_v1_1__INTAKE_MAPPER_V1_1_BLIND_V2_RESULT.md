# Intake Mapper v1.1 — blind v2 1회 평가 (2026-09-23)

판정: **MAPPER_NEEDS_MORE_WORK** (overall P 0.9324 FAIL, NEG P 0.8267 FAIL). v2로 재튜닝 금지.

- mapper freeze: 592c4c5 (`FREEZE.json`), 평가 직전 SHA 무결 확인
- v2 fixture: 368문장 / gold 484(POS 371, NEG 113), SHA a35f9b95… (`04_…frozen_before_eval.txt`)
  - 작성 A(sonnet, 337) → v1 유사도>=0.80·내부중복 78 기계 제외(`02_v2_assembly_rule.json`, `02b_…dropped.json`) + 작성 B(opus 보충 110, 1 제외)
  - 독립 gold 검수(opus, 매퍼 비열람): 구조 PASS, 수정 32(E_53 누락 추가 20·E_201 1, OR 부분부정 NEG 제거 11), 제외 0 (`03_v2_gold_review.json`)
- 결과: `05_blind_v2_eval_result.json`

## FP 25 유형
1. OR 질문 부분 부정을 NEGATIVE로 냄 9 — E_124 "천식은 없어요"(질문=천식 또는 기관지확장제) 4, E_112 3, E_9 2. alias `allow`가 스펙 R2와 불일치
2. 부정 scope 오류 8 — '-거나' 병렬 부정 미처리(E_181 2), 도치("안나요 열은", "없어요, 열은") 2, 관용어("장난 아니게")→NEG 1, 연결어미 "아픈데"를 E_53.a4 '아픈 데'로 오매칭 1, "못 느꼈어요"(짧은 못=부정 아님 규칙)→POS 1, "나올까 봐…안 보였어요"→POS 1
3. 조건절 속 기침을 기침 mention으로 처리 4 — "기침하거나 힘줘도 더 아프지는 않아요"→E_201 NEG 2, "기침할 때도 더 아파요"→E_201 POS 2
4. 과거 표지 누락 2 — "그땐", "어제까지는"
5. E_33 implies E_53 과확장 2 — "숙이면 나아져요"에 통증 명시 없음
