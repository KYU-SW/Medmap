# Intake Mapper v1.2 — 최종 blind v3 1회 평가 (2026-09-24)

판정: **MAPPER_V1_PRODUCT_CANDIDATE** (overall P 0.9630 PASS, NEG P 0.9583 PASS). 참고: POS P 0.9645 PASS, recall 0.6107 FAIL.
v3 재튜닝 금지. 규칙 기반 v1 계열 blind gate는 이것으로 종료.

- freeze: 2372e2f (`FREEZE.json`), 평가 직전 SHA 무결 + HEAD 대비 medmap/intake 무변경 확인
- v3: 497문장 / gold 596(POS 398, NEG 198), SHA a1bc1b82…
  - 작성 A(opus, 중장년 존댓말) 260 + B(sonnet, 채팅체) 260 → v1/v2/v3 유사도>=0.80 제외 23 (`01_v3_assembly_rule.json` 사전 등록, `01b_…dropped.json`)
  - 독립 gold 검수(opus, 매퍼·정책 비열람): 구조 PASS, 수정 28(E_53 추가 18 등, R2 부분부정 NEG 제거 7), 제외 0 (`02_v3_gold_review.json`)
- 결과: `04_blind_v3_eval_result.json`

## 여유와 한계
- precision 95% Wilson CI: overall [0.9388, 0.9778], NEG [0.8977, 0.9837] — NEG는 예측 96건, FP 4건. 1건만 더 틀려도 0.948.
- NEG recall 0.4646: gate 통과는 unsafe 18개 evidence의 NEGATIVE를 반환하지 않는(ABSTAIN) 정책 덕분. 빠진 NEGATIVE는 사용자 확인 질문 몫.
- 작성자별: A P 0.9592 / NEG P 0.9245, B P 0.9670 / NEG P 1.0 — A(긴 존댓말)에서 NEG 오류 집중.

## FP 14 유형
1. 지속·부정 변형 미처리 4: "멈추질 않아요", "안 끊기고"→NEG, "토할 것 같진 않아요"(부분 부정)→NEG, "누런 콧물이나 퍼런 콧물은 안 나와요"→POS('이나' 병렬)
2. "움직여도 통증은 똑같아요"→E_216 POS (gold NEG) 3
3. 타인·과거 표지 누락 5: 손주/손녀, "저번엔", "3주 전"(E_116 2주 창), "과음도 그렇고" 
4. 기타 2: "열은 안 재 봐서 모르겠어요"→NEG, "심장 두근"(저번엔) 
