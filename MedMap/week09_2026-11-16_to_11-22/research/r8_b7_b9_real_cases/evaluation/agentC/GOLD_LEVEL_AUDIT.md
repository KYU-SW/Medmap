# 평가 정답 수준 감사 (Agent C)

작성일 2026-11-21 · 작성 Agent C(독립 평가 정답 감사·반대 검증) · 근거 표 `gold_sources.csv`

확인 수준 표기: [원문] 파일·전문 직접 확인 / [원문-부분] 일부만 확인 / [초록] 초록·서지만 확인 / [검색요약] 검색 결과 요약만 확인 / [이전보고서] 이전 회차 문서 인용 / UNKNOWN 확인 못함

## 0. 판정 요약

| 질문 | 판정 |
|---|---|
| 복합질환 + 지침 적용 + 선호에 대한 공개 C 수준(전문가 판단) 정답 | **미발견** (확인 범위 내). "없다"가 아니라 "이번 검색 범위에서 찾지 못함" |
| 복합질환 + 지침 적용에 대한 공개 정답 | **부분 존재**: MGCDS 4사례(B + 약한 C, 비독립) |
| 보류·확인 질문 정답(복합질환 지침 맥락) | **미발견** |
| 보류·질문 정답(다른 맥락) | 존재: MediQ(진단 QA), HealthBench(context seeking 루브릭), Socrates 2025(실제 응급실 사례 + selective prediction, 데이터 공개 여부 UNKNOWN) |
| 규칙 수준 전문가 합의 | 존재: STOPP/START v3(11인 Delphi, CC BY 4.0 [검색요약]). 단 **사례 수준 정답 아님** |
| D 수준(실제 환자 결과) 정답 | 공개 자료로 **불가** |
| 메인이 이번 회차에 독립 C 정답을 주장할 수 있는가 | **불가** — 독립 임상의 2인 이상 확보 전까지 |

## 1. 정답 수준 정의(이번 회차 기준)

| 수준 | 정의 | 최소 요건 | 예 |
|---|---|---|---|
| A | 수학적 정답 | 명세(규칙·효과 구간·선호 polytope)가 주어졌을 때 정확 계산(전수 열거·정확 MILP) | 이전 회차 1,261건 [이전보고서] |
| B-R | 연구자가 지침 원문을 읽고 작성한 규칙·기대 출력 | 원문 문장 인용, 버전·조항 번호 | 메인이 지침에서 규칙 인코딩 |
| B-I | 지침 원문 정합성, 독립 이중 인코딩 | 구현자와 다른 2인 인코딩 + 불일치 조정 + 일치도 | (현재 없음) |
| C-weak | 임상의가 관여했으나 독립성·합의 절차 없음 | 1인 또는 방법 개발팀 공저 임상의 | MGCDS, Wu 2025 판정 |
| C-I | 독립 임상의 판단 | 시스템 개발 비관여 임상의 ≥2, 사전 등록 루브릭, 시스템 출력 눈가림, 일치도(κ 등), 불일치 조정 절차 | (현재 없음) |
| C-panel | 전문가 패널 합의 | Delphi/명목집단, 합의 기준 사전 정의 | STOPP/START(규칙 수준) |
| D | 실제 환자 결과 | 결과 추적 자료, 인과 설계 | 없음 |

## 2. 후보 정답 자원별 감사

### 2.1 MGCDS 벤치마크 (github william-vw/MGCDS) [원문]

- 구성: Benchmark Framework(기능 목록·사례·보고 양식·평가 차원), Case 1~4, Solution Reports(6개 팀), 임상의 설문 PPT. Apache-2.0. 마지막 push 2023-02-06.
- 사례: ①TIA/십이지장궤양/골다공증 ②CKD/고혈압/심방세동 ③VTE/요로감염 ④약물용출스텐트/폐종괴 수술.
- **정답 작성자(원문 Case Studies.docx 저자 줄)**
  - Case 1: Kogan, Peleg, Tu + Allon, Khaitov, Hochberg (Technion/Rambam)
  - Case 2: W. Michalowski, Wilk, M. Michalowski + Carrier, Le Gal(Ottawa Hospital 혈액내과), Kingwell(정형외과)
  - Case 3: Van Woensel, S. Abidi, S.S.R. Abidi
  - Case 4: Edry(Rambam 급성통증) + Kogan, Peleg, Tu
- **독립성 판정: 비독립.** 사례 작성팀 = 해법 보고서 제출 방법 개발팀(GoCom/Peleg, MitPlan/Michalowski·Wilk, Van Woensel·Abidi). 임상의 공저자(Carrier, Edry, Hochberg, Kingwell)는 Van Woensel 2023 공저자 [초록·서지].
- 정답 형태: "Adverse interactions and revisions", "Revised treatment" 절에 기대 관리안 서술. Case 1은 선택지 3개(Option 1~3, 목표 충족 여부 표시). Case 2는 단일 수정안. Case 3은 단일 수정안(와파린 10% 감량, 3일째부터 INR). **Case 4 docx 2개에는 기대 관리안 절이 없음**(슬라이드 PPTX 미확인 → 확인 필요).
- 선호: Case 2만 명시 선호 1개("INR 검사 번거로움 회피 위해 DOAC") — **점 값, 완전 정보**. Case 3의 "financial considerations"는 이미 결정된 사실로 기술. **불완전 선호 없음.**
- 보류·질문: 기능 18개(A1–A7, B1–B7, C1–C4) [원문]에 "정보 부족 시 보류", "확인 질문" 기능 없음. "언급 없음"이므로 기존 방법이 못 한다는 뜻은 아님.
- 합의·일치도 통계: 없음. 임상의 설문은 "기능 목록 확인"용이며 정답 작성용 아님(README 원문).
- **수준 판정: B(지침 문구 기반 기대 관리안) + 약한 C(단일 팀 임상의 공저). C-I 아님.**
- 재사용: 개발·sanity 사례, 그리고 **원 개발팀이 직접 낸 해법 보고서를 "기존 방법의 실제 출력"으로 쓸 수 있음**(기준선 재구현 약점 완화 가능). 독립 정답으로는 사용 불가.

### 2.2 Wu et al. 2025, arXiv 2507.10911 [원문 PDF 텍스트]

- MGCDS 4사례로 LLM 단일·다중 에이전트 평가. 원문: "They included clinician-curated gold standard based on evidence-based guidelines."
- 추가 행동 판정: "we consulted with a clinical expert (coauthor IH)" → **공저자 1인 판정, 비독립**. IH(Hochberg)는 MGCDS Case 1 공저자.
- 정답 수정 흔적: "we used the benchmark case as is, but accepted correct solutions that leave the PPI" (Case 1 정답 사후 완화). Case 3 시나리오가 MGCDS 파일("recurrent VTE")과 다름("prosthetic aortic heart valve", "switch the antibiotic or ... reduced by 10-20%", "INR day 3-5") → **정답 버전 표류**. 원문 제시 데이터 링크 github.com/MGCDS/benchmarkframework는 GitHub API에서 Not Found(2026-11-21) → 현재 버전 UNKNOWN.
- 지표: Correctness=TP/(TP+FP-wrong), Completeness=TP/(TP+FN), DDI·금기·목표·약물 수 비율, 선호 option set 식별 여부. 임상의 4인 Likert(설명성·배정 합리성·효율). **보류·질문·불완전 선호 지표 없음.**
- 수준 판정: **약한 C(저자 임상의 판정)**.

### 2.3 STOPP/START v3 (2023) [검색요약]

- 11인 학계 의사, 8개국, 4라운드 Delphi, 190개 기준. 논문 CC BY 4.0(검색요약; 기준 표 자체의 별도 조건은 확인 필요).
- 판정: **규칙 수준 C-panel**. "이 환자에게 이 기준이 적용되는가"는 별도 판단 필요(Socrates 2025: LLM 오류의 54.5%가 포함·제외 조건 적용 문제). 사례 수준 정답으로 직접 쓰면 안 됨.

### 2.4 Socrates et al. 2025, JMIR Aging [초록]

- 실제 응급실 노인 100명(712개 경구약), Beers·STOPP·GEMS-Rx. 정답: "trained medical students, with discrepancies adjudicated by board-certified ED physicians".
- selective prediction(기권) 평가, 오류 원인 중 "missing information" 39.3%.
- 판정: **실제 사례 C(학생+전문의 조정)**. 데이터 공개 여부 UNKNOWN. 선호·확인 질문 없음.

### 2.5 HealthBench (2025) [검색요약]

- 262명 의사가 루브릭 작성, context seeking·hedging 주제. 2026 2차 분석: context seeking 의사 간 불일치 30.0%(최고) [검색요약].
- 판정: 일반 대화 C. 복합질환 지침 정답 아님. **"확인 질문 필요성"에 대한 의사 간 불일치가 크다는 근거**로 중요(정답 신뢰 상한).

### 2.6 MediQ (2024) [초록]

- MedQA·CRAFT-MD를 대화형으로 바꿔 질문·기권 평가. 정답은 원 시험 정답(진단). 복합질환 관리·선호 없음. 저장소 라이선스 필드 비어 있음(UNKNOWN).

### 2.7 기타

- MedAgentBench: 내과 의사 2인 작성 과제 [검색요약], MIT. 관리 판단 정답 아님.
- AWMF S3 다중질환 지침(2017): 사례 10개, 외부 일차진료의 패널이 사례 검증 [검색요약]. 사례별 기대 답 존재 여부 UNKNOWN → 원문 확인 필요(가능성 있는 후보).
- JMIR 2025 프로토콜(e63339) [원문, Europe PMC 전문]: ≥20인 합의 그룹으로 **방법론 프레임워크(결정 나무)** 를 만들 계획. 사례 정답 없음. "This study will not involve the participation of patients or the public." 시험 절차 "still under discussion".
- Wu·Peleg 2026 JBI 105072 [초록]: 평가 지침 문서. 정답 자료 아님. 본문 UNKNOWN.
- DDInter: v1 이용조건 CC BY-NC-SA 4.0 [검색요약], 2.0 미확인. 약물쌍 수준 B-like.
- Boyd 2005: 저자 구성 단일 가상 사례(B-R 성격).
- Patient Priorities Care: 실제 우선순위 도출 과정은 있으나 공개 환자 수준 "우선순위 + 결정 정답" 자료 미발견 [검색요약].
- 노인 복합질환 Delphi 합의: 규칙·원칙 수준(예: 다중질환·다약제 지침 검토 18인 합의 [검색요약])은 있으나 사례 수준 정답 세트 미발견.
- MedQA류 복합질환 문항: 이번 회차에 복합질환 + 지침 충돌 전용 문항 세트 **미발견**(검색 1회). CLIMB(2026)는 복합질환 진단 대화, 합성, 정답 작성자 UNKNOWN [초록].

## 3. 의료적 정확도 주장 가능 범위 판정표

| 확보한 정답 | 쓸 수 있는 주장 | 쓸 수 없는 주장 |
|---|---|---|
| A만 | "명세가 주어지면 정식화가 정확히 계산한다", "결합 정식화가 모듈 파이프라인보다 정보 손실이 적다(합성)" | 의학적 정확도, 지침 정합, 임상 유용성 일체 |
| A + B-R | "연구자가 인코딩한 지침 규칙 기준 일치율 X" (표기 규칙 6절 준수) | "지침과 정합한다", "임상적으로 적절" |
| A + B-I | "지침 원문 문구 기준 정합률 X(독립 이중 인코딩, κ=…)" | "임상적으로 적절", "전문가 판단과 일치" |
| C-weak (MGCDS, Wu 2025식) | "해당 사례 작성 임상의(공저) 해법과 일치(n=4, 탐색적)" | 일반화, 독립 검증, 통계적 비교 |
| C-I (독립 임상의 ≥2) | "독립 임상의 판단과의 일치도 X(95% CI), 임상의 간 일치도 Y 대비" | 환자 결과 개선, 실제 진료 우월성, 선호 반영의 환자 관점 정확성 |
| C-panel(규칙) | "합의 규칙 적용 정확도" | 사례 전체 관리 판단의 정확도 |
| 실제 환자 진술 선호 + C-I | "명시 선호가 있는 사례에서 선호 반영 판단이 임상의 판단과 일치" | "환자가 원하는 결정을 맞혔다"(환자 확인 없음) |
| D | 환자 결과 관련 주장(인과 설계 필요) | — (공개 자료로 확보 불가) |

추가 원칙
- 임상의 간 일치도보다 높은 시스템–임상의 일치도는 해석 주의(정답 상한).
- 보류·질문의 "필요성" 정답을 A 수준(정보 가치 계산)으로만 정하면 시스템 자기 모형으로 자기를 채점하는 순환이 생긴다 → 질문 필요성은 최소 B-I 또는 C-I로.

## 4. 메인이 사용할 정답 출처 권고

1. **개발 세트**: MGCDS 4사례 + 원 팀 해법 보고서(라벨: C-weak, 비독립). 지표 튜닝·디버깅에만.
2. **평가 세트**: 메인이 구조화한 실제 사례 → 동결 → 독립 임상의 ≥2가 시스템 출력 없이 정답 작성(C-I). 확보 실패 시 B-R로 강등 표기.
3. **규칙 출처**: STOPP/START v3 같은 공개 합의 기준(CC BY 확인 후)은 규칙 B/C-panel로만.
4. **금지**: 연구자(메인·Agent)가 작성한 기대 출력을 C로 표기, MGCDS를 "독립 전문가 정답"으로 표기.

## 5. 표기 규칙 (연구자 작성 정답, 비독립)

| 항목 | 규칙 |
|---|---|
| 라벨 | 모든 표·그림·본문에 `REF-R(연구자 작성, 비독립)` 표기. 지침 문구 인용이 있으면 `REF-R/B`, 없으면 `REF-R/추론` |
| 용어 | "정확도(accuracy)", "정답(gold standard)", "임상적으로 정확" 금지 → "연구자 기준 일치율(agreement with researcher-authored reference)" |
| 작성자 분리 | 정답 작성자 ≠ 시스템 구현자(같은 팀이면 그 사실 명시). 작성자 ID·역할·작성 시각 기록 |
| 동결 | 시스템 실행 전 정답 파일 동결(sha256 + 시각). 동결 후 수정은 append-only 정정 기록 + 사유, 수정 전후 점수 모두 보고 |
| 근거 | 항목마다 지침 이름·버전·조항·원문 문장 위치. 근거 없는 항목은 `추론`으로 분리 집계 |
| 불확실 항목 | 연구자도 확정 못하는 항목은 `REF-UNSURE`로 두고 주 지표에서 제외, 별도 보고 |
| 보고 문장 | "본 결과는 연구자가 작성한 비독립 기준에 대한 일치이며 의료적 정확도를 뜻하지 않는다" 를 결과 절 본문에 명시(작은 글씨 각주 금지) |
| 수준 승격 | 독립 임상의 검토를 거친 항목만 `REF-C-I`로 승격, 승격 전후 점수 분리 |
| 혼합 금지 | REF-R과 REF-C-I 항목을 합친 단일 점수 금지(층별 보고) |
| 순환 점검 | 정답 작성 시 시스템 출력·중간 결과 열람 여부 기록. 열람했다면 `REF-R(오염 가능)` |
