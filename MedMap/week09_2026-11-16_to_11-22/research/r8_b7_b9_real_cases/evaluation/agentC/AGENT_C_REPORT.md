# Agent C 보고서 — 독립 평가 정답 감사·반대 검증

작성일 2026-11-21 · 범위: 공개 자료 조사(무료 웹 검색·공개 저장소·Europe PMC), 유료 API·저자 연락·접근 우회 없음. 의료 전문가 정답 생성 없음.

## 1. 판정 요약

| 항목 | 판정 |
|---|---|
| 복합질환 + 지침 적용 + 선호에 대한 **독립 C 수준 공개 정답** | **미발견**(확인 범위 내) |
| 복합질환 지침 사례 정답 | MGCDS 4사례 — **B + 약한 C, 비독립**(사례 작성팀 = 방법 개발팀, 임상의 공저) [원문] |
| 보류·확인 질문 정답(복합질환 지침 맥락) | **미발견** |
| 이번 회차 의료적 정확도 주장 | **불가**. 가능 범위는 A(수학) + REF-R(연구자 기준 일치)까지. 독립 임상의 ≥2 확보 시 C-I 일치도 주장 가능 |
| 선점 위험 | **중간~높음**. 세 요소 동시 평가 연구는 미발견이나 각 요소는 모두 선점. Wu·Peleg 2026 본문 미확인이 최대 변수 |
| 신규성 주장 상태 | **조건부**(조합 신규성. R1·R2·R3 해결 전 주장 불가) |

## 2. 정답 수준 감사 핵심 (GOLD_LEVEL_AUDIT.md)

- **MGCDS** [원문, 저장소 파일 직접 확인]: 사례별 저자 줄 확인 — Case 1 Peleg/Tu 팀 + Technion·Rambam 임상의, Case 2 Michalowski/Wilk 팀 + Ottawa Hospital 임상의, Case 3 Van Woensel/Abidi, Case 4 Edry + Peleg/Tu. 모두 해법 보고서를 낸 방법 개발팀. 합의 절차·일치도 통계 없음. Case 4 docx에는 기대 관리안 없음(슬라이드 미확인). 선호는 Case 2의 점 선호 1개뿐, 불완전 선호 없음. 기능 18개에 보류·질문 없음.
- **Wu et al. 2025** [원문]: MGCDS 위에서 LLM을 정량 채점. "clinician-curated gold standard", 추가 행동 판정은 "coauthor IH" 1인 → 비독립. 정답 사후 완화(PPI 유지 허용)와 Case 3 시나리오 불일치 → 정답 버전 표류. 원문 데이터 링크 저장소는 현재 Not Found.
- **STOPP/START v3**: 11인 Delphi, CC BY 4.0 [검색요약] — 규칙 수준 C, 사례 정답 아님.
- **Socrates 2025** [초록]: 실제 응급실 노인 100명, 학생 + 전문의 조정, selective prediction — 가장 가까운 "실제 사례 + 기권" C 수준 선례. 데이터 공개 UNKNOWN.
- **HealthBench**: context seeking 의사 간 불일치 30.0% [검색요약] → "질문 필요성" 정답의 신뢰 상한이 낮을 수 있음.
- 판정표(정답 수준 → 가능 주장)와 연구자 작성 정답 표기 규칙(REF-R 라벨, "정확도" 용어 금지, 동결 sha256, 작성자 분리, 층별 보고)은 GOLD_LEVEL_AUDIT 3·5절.

## 3. 선점 확인 핵심 (red-team/PREEMPTION_CHECK.md)

| 요소 | 이미 다룬 연구 |
|---|---|
| 복합질환 지침 사례 + 정량 채점 | MGCDS(정성), **Wu 2025(정량, LLM)** |
| 불완전 정보에서 기권·질문 | MediQ, ATLAS, CARE-BENCH, HealthBench |
| 실제 사례 + 기권 | Socrates 2025 |
| 실제 선호 도출 | Patient Priorities Care(평가 벤치마크 아님) |
| "모름" 3값 판정 | GuidelineForge |
| 세 요소 동시 | **미발견** |

- Van Woensel 2023: 초록상 채점 목적 아님 → 후보 1을 직접 반박하지 않음(본문 미확인).
- JMIR 2025 프로토콜 [원문]: 합의 기반 방법론 프레임워크, 소프트웨어·사례 정답 없음, 환자 참여 없음.
- Wu·Peleg 2026 JBI 105072 [초록]: 존재 확인, 초록에 선호·결측·보류 언급 없음. **본문 확인 필요**.

## 4. 핵심 반론 (red-team/RED_TEAM_OBJECTIONS.md, 16개)

CRITICAL
1. R1 조합 신규성뿐 → 검증: 완전 정보/임상 결측/선호 결측/둘 다 조건에서 방법 순위가 바뀌는지
2. R2 독립 정답 부재 → 독립 임상의 ≥2, 눈가림, 사전 루브릭
3. R3 필수 질문 정답을 정식화(VOI)로 만들면 자기 채점 순환 → 정식화와 독립인 작성자

MAJOR(일부): R4 "실제 사례"가 구성 사례, R5 실제 선호 희소·마스킹은 인위적, R6 보류 유리 지표, R7 기존 방법 재현 불가(→ **MGCDS 원 팀 해법 보고서 6건을 기존 방법 실제 출력으로 활용** 제안), R9 LLM 오염(2023년부터 공개), R10 임상의 간 불일치, R13 Wu·Peleg 2026 본문.

## 5. 지표 설계 요점 (METRIC_DESIGN.md)

- 범주: 정확 확정 CC / 잘못된 확정 WC(틀린 조치 + 성급 확정) / 적절 보류 AD / 불필요 보류 UD, 질문은 필수 확인 누락 MQ·불필요 확인 UQ.
- 주 지표: U = (CC + AD − λ_W·Σh_i(WC) − λ_U·UD)/N, λ_W > λ_U > 0 (기본 5, 1; 격자 {2,5,10}×{0.5,1,2}).
- 기술 점수 S = (U − U_ref)/(U_oracle − U_ref), U_ref = max(U(모든 보류), U(모든 확정-기본값)) → **모든 보류는 구조적으로 S=0**.
- 질문: QR = |Q∩R|/|R|, QP = |Q∩A|/|Q|, QF, 부담비 |Q|/|R|.
- 필수 보고: WCR, UDR, 커버리지, 균형 정확도(모든 보류 = 0.5), 원인 정확도, 정답 보류 기저율. "1 − WCR" 단독 금지(모든 보류 = 1.0).
- 가상 계산(설계 검증용): 모든 보류 U −0.20·S 0, 가상 시스템 U 0.66·S 0.717, 격자 전체 S 0.500~0.800.
- 퇴화 기준선 4종 실제 채점 + 변이 검사(SELECTION_BIAS_CHECKLIST D절).

## 6. 메인에게 권고 (가장 중요한 것 하나)

**독립 임상의 정답 확보 여부를 먼저 결정할 것.** 확보 못하면 이번 회차 결과는 전부 `REF-R(연구자 작성, 비독립)` 일치율로만 보고하고 의료적 정확도·임상 적절성 표현을 쓰지 않는다.

## 7. 미확인(UNKNOWN / 확인 필요)

- Wu·Peleg 2026, Van Woensel 2023, Grgurić 2024 본문
- MGCDS Case 4 기대 관리안(슬라이드), Wu 2025 정답 최신 버전 저장소 위치
- STOPP/START 기준 표 자체 재사용 조건, DDInter 2.0 라이선스, MediQ 라이선스
- AWMF S3 사례별 기대 답 존재 여부
- Socrates 2025 데이터 공개 여부

## 8. 산출물

- /home/<user>/medmap-original-b7-b9-clinical-validation/evaluation/agentC/GOLD_LEVEL_AUDIT.md
- /home/<user>/medmap-original-b7-b9-clinical-validation/evaluation/agentC/gold_sources.csv
- /home/<user>/medmap-original-b7-b9-clinical-validation/evaluation/agentC/METRIC_DESIGN.md
- /home/<user>/medmap-original-b7-b9-clinical-validation/evaluation/agentC/AGENT_C_REPORT.md
- /home/<user>/medmap-original-b7-b9-clinical-validation/red-team/PREEMPTION_CHECK.md
- /home/<user>/medmap-original-b7-b9-clinical-validation/red-team/RED_TEAM_OBJECTIONS.md
- /home/<user>/medmap-original-b7-b9-clinical-validation/red-team/SELECTION_BIAS_CHECKLIST.md
- /home/<user>/medmap-original-b7-b9-clinical-validation/red-team/sources.csv

원자료 임시 사본(MGCDS docx, 논문 텍스트)은 세션 scratchpad에만 있음: /tmp/claude-1000/-home-<user>/159b4551-4368-4d10-8c70-78d3445e5a4d/scratchpad/mgcds_dl
