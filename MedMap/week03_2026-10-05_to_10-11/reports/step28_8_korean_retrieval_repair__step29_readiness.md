# STEP29 진입 판단(STEP28.8)

판정·수치 정본: `outputs/step28_8_verdict.json` · `docs/step28_8_report.md`.

- **STEP29_READINESS = CONDITIONAL_GO**(사전 규칙: hard 게이트 G1·G2·G3·G3b·G7·G9·G10 PASS + HELD_PRECEDENCE PASS + G5 PASS).
- GO_FOR_RESEARCH 가 아닌 이유: STEP28_8_RESULT 가 QUALITY_IMPROVED 가 아님(G4 FAIL, 부분 문자열 오매칭 0 아님) · G6_STRICT(precision ≥ 0.95) FAIL.
- 의미: 연구용 NLU 개발 입력으로 쓸 정도로 인터페이스(원문 보존·구별 위반 0·보류 상태·모델 미사용 표시)가 안정적이고, 남은 오류가 목록화돼 있다. 실서비스·임상 검증 아님.

## STEP29 가 함께 안고 가야 할 결함(격리해서 사용)

1. 술어 정규화 키(nkey) 손실 일치 — 의성어·부사·위치 명사 소실('속이 화끈화끈해요' → nausea). 제거만 하면 precision 이 떨어짐(탐색 P5x).
2. 경계 일치에서 부사 소실로 신체 부위 단독화('심장 부분' → palpitations), 신체 부위 목록 불완전('심장').
3. 다구문 문장의 첫 구문 선택(예 '누런 가래가 나오는 기침' → E_182 가 먼저) — STEP29 구문 이해 범위.
4. STEP27 B4 모델 오연결('양쪽 팔을들어' → limb_weakness).
5. 검사기 v3 빈틈('토할 것 같아요' → vomiting 미탐지).
6. 부정·시점·주체는 STEP28.5 규칙 추출값 전달만(검증 0). PILOT_EXTRA106 의 연결 불가(should_link False) 입력 중 auto 7.

## 시작 조건

- STEP29 는 자동 실행하지 않는다(사용자 지시 필요).
- 신규·하위·SILVER 단독 결과는 49질환 모델 입력 금지 유지.
