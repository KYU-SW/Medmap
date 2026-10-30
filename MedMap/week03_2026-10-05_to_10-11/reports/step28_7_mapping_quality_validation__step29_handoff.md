# STEP28.7 → STEP29 인수인계(연구용)

수치·판정은 `outputs/step28_7_verdict.json`(공식) · `outputs/exploratory_v2.json`(탐색, 공식 아님) · `docs/step28_7_report.md` 에서 읽는다.

## 바로 쓸 것

- 검색기: `scripts/safe_offline_retriever.py` `SafeOfflineRetriever().run(text)` — CPU·오프라인, 구문 단위 출력(`docs/step29_interface.md`).
- 정제 대응표: `data/cleaned_silver_mappings.csv`(SILVER, LEVEL_0–3, LEVEL_4 = 0). 신규·하위는 49질환 모델 입력 금지.
- concept 분류: `data/audited_concepts.csv`(A–F, 분류자 = Claude 세션, 비인간·비독립).

## 알려진 문제(STEP29 전에 판단 필요)

1. 공식 판정이 REGRESSION 인 이유는 STEP28.7 구별 검사기 결함('토할'·'떨려' 패턴)이다. 다음 단계 검사기는 STEP28.6 원형 + 명사 '떨림' 규칙(v2)을 **사전에** 고정해서 쓴다.
2. G6(regression 자동 처리 정밀도) FAIL — 원인은 STEP28.5 한국어 경로(KO): 다구문 입력의 첫 구문 선택, PHRASE 부분 일치, 1글자 핵어 완전일치('근' ← '가슴 두근'), 일반 명사('주위'·'이상'), 오바이트→nausea 등.
   STEP29 구문 이해가 이 경로를 그대로 쓰면 같은 오류를 물려받는다. 고칠 때는 새 실험 버전으로, 이미 본 regression 세트를 독립 테스트라고 부르지 않는다.
3. '흉통' 계열을 KO 경로가 연결하지 못함(NO_KOREAN_MATCH) — 77 지원 증상의 누락.
4. 부정·시점·주체·불확실성은 STEP28.5 규칙 추출값을 전달만 한다(검증 0).
5. 77 밖 신규 증상은 대응표(사전) 기반 — 처음 보는 표현은 처리 못 함. 대응표 확장은 오프라인 LLM 작성(과금 승인) + 인간 검토 필요.
6. 격리 FAIL 조각(A_c03·A_c04·B_c04, WEAKNON903 입력만)은 양성 연결에 쓰지 않는다. 재작성은 과금 승인 대상.

## 사람 검토가 필요한 최소 범위(선택지 — 사용자에게 대량 라벨링 요청 금지)

- 독립 신규 후보 16 · 기존 하위 6 · 우선 보류(무기력·묽은변·빈맥·식은땀) — concept 수준 수십 개.
- 검토 결과가 생기기 전까지 HUMAN_VERIFIED_GOLD = 0, 임상 정확도 주장 없음.

## 금지 유지

추가 LLM·외부 API·다운로드 사전 승인 · MDRKOR·KCD5 금지 · SNOMED/UMLS 문자열 외부 전송·공개 금지(LOCAL_ONLY 파일은 `.gitignore`) · 제품·PatientState·49질환 모델 변경 금지 · commit/push 는 사용자 지시 시.
