# EXP-MAI-001 gate 1 (NEEDS_FIX) 대응표 — manifest rev2 (2026-10-26)

gate 1 원문: `.research-guardian/audits/EXP-MAI-001/gate/20261026_192453_NEEDS_FIX.md` (설계·통계·의료 3명 모두 NEEDS_FIX, CRITICAL 0 · BLOCK 0)
rev1 백업: scratchpad `manifest_rev1_backup.yaml`(세션 임시). RG 관리 필드(review_status·reviewer_findings·audit_trail)는 수정하지 않음 — 대조 스크립트로 확인.

| 지적 | 출처 | rev2 조치 | 상태 |
|---|---|---|---|
| 비열등 p 값이 0 기준(부호 반전×2) | 설계 M4 · 통계 S-test · 의료 m-stat | 비교별 경계 b_j·단측 p 식·Holm 단측 α 0.025·IUT 동시 조건 명시 | 해결 |
| 효과 크기 하한(MID) 없음 | 통계 S-effect | MID_H1 = +0.01 절대(2026-10-27 사용자 확정, rev3) | 해결 |
| margin 근거 없음 | 통계 S-margin · 의료 | "합성 연구용 임의 사전 고정값" 명시 + SELECT 기준 대비 상대 크기 사전 보고 + margin 판정표(기술 통계) | 해결 |
| 미기록 불변성 검사가 미기록→음성 오류를 못 잡음 | 설계 M1 | 이름 변경(숨은 기록 누출 검사) + 근거 집합 일치 assert 와 변이 테스트 추가, A·B 포함 | 해결(설계) |
| PB "조건 가지치기" 명칭이 실제와 다름 | 설계 M2 | "사후확률 비율 기반 확인 질문 우선순위 하향"으로 재정의, 부모-자식 규칙은 공통 규칙이라 명시, 하위 작업 정의·발동률 보고 | 해결 |
| 노드 수 기준이 구현 의존 | 설계 M3 · 통계 S-adopt | 그래프 계열 공통 계수 함수 정의, PB/PB_REL 비 기하평균 CI 상한 < 0.90 | 해결 |
| 탐색기 입력 차단 장치 없음 | 설계 M5 | `reset(initial_evidence, age, sex, wd)` 인터페이스, 금지 키 assert, PATHOLOGY 주입 변이 테스트 | 해결(설계) |
| severity 읽는 경로·17질환 미고정 | 설계 M6 · 의료 m-sev-use | 17질환 이름 고정, conditions SHA 고정, 평가 모듈만 로드, 정적 검사, 사용 범위(평가+τ 선택) 정정 | 해결 |
| PC 이득 조건 없음·WD_CORRECT 오라클 표기 | 설계 M7 · 의료 M-wd | H3c(WD_MODEL Top-5 비열등) 추가, WD_CORRECT = ORACLE, *_WRONG = 스트레스 조건, "앵커링" → "질문 예산 재배분" | 해결 |
| WD_MODEL 의 k 미지정 | 설계 M8 | MODEL_k3 고정 | 해결 |
| 그래프 모델은 AGE·SEX 미사용 | 설계 M9 | 명시 + A 비교 문구 "원인 미분리"로 수정 | 해결 |
| Baseline B·범주형 처리 미정 | 설계 M10 | B 전역 트리 규칙 고정, 그래프 계열은 이진 질문만 선택·범주형 답은 ig_table 그대로 우도, PB_REL 점수식(가중치 없음) 고정 | 해결 |
| 음성 시뮬레이터 무잡음 → H1 자명 | 의료 M-sim-neg · 설계 m9 | 가설·주장에 "무잡음 폐쇄세계" 한정어, 응답 잡음 민감도(기술 통계) 추가 | 해결 |
| 중요 누락률 명칭·질환별 집계 | 의료 M-crit-def · 통계 S-subset | "중증 정답 사례 누락률(데이터셋 주석)", 질환별 n·누락률·사전확률 사분위, 질환별 악화 > +2%p 시 채택 보류 | 해결 |
| H1 동시 조건 수준 | 통계 S-copri | IUT 단측 α 0.025 | 해결 |
| τ 선택 실패 처리 | 통계 S-tau · 설계 m5 | Q=5, 두 안전 조건, 실패 시 H2b 기각 안 함·H3 기준 PB_REL | 해결 |
| FINAL 재사용 충돌 | 통계 S-final-reuse · 설계 m1 | 검사 통과를 FINAL 잠금 전제로, FINAL 에서 INVALID 이후는 EXPLORATORY. FinalGuard 에 config SHA 대조·환경 실패 1회 재시도 규칙 구현(테스트 9개, 변이 4/4 추가 검출) | 해결(코드) |
| H3b seed 1개 | 통계 S-seed | seed 42·43·44 모두 충족(최대 p), 결정론적 모델 명시 | 해결 |
| A 와의 사후 비교 | 통계 S-posthoc · S-wording | 사전 지정 1개 모델, 기술 통계 | 해결 |
| bootstrap 2,000 | 통계 S-B | 10,000, 같은 인덱스, 500회 분할 | 해결 |
| 입력 SHA 미고정 | 설계 m2 | train·evidences·conditions SHA 고정 | 해결 |
| pkl 재현 대조 | 설계 m3 | SELECT_SMOKE 에서 STEP16B 02_holdout_initial_predictions.csv 대조 | 해결(절차) |
| 누출 검사 뒤집기 대상 | 설계 m4 | 자식 없는 이진 근거로 제한, UNSAFE = INVALID | 해결 |
| FINAL_NOVEL 프로필 | 설계 m6 | INITIAL_EVIDENCE 포함 | 해결 |
| k 기호 혼동 | 설계 m7 | 후보 표시 수 = m | 해결 |
| 순환·간선 일치율 | 의료 m-circ | graph_stats.json(평가 전용) 추가, confounder 명시 | 해결 |
| 스펙트럼 | 의료 m-spectrum | confounder·주장 한정어·질환별 n | 해결 |
| 제목 범위 | 의료 m-title | 제목 변경 | 해결 |
| HOLDOUT 이력 → A 유리 가능성 | 의료 m-holdout · 설계 확인 필요 | STEP16B prereg §2·§5 인용(HOLDOUT 잠금, 성능 본 뒤 변경 금지), 다른 worktree grep 결과 기록 | 해결 |
| severity 방향 1차 출처 | 의료 확인 필요 | 파일 값 분포로 확인, 논문 인용은 확인 필요로 남김 | 일부 |
| n_samples | 통계 S-n | split 실행 시 기록(실데이터 미실행) | 실행 단계 |

---

# gate 2 (NEEDS_FIX, rev3) 대응 — manifest rev4 (2026-10-27)

gate 2 원문: `.research-guardian/audits/EXP-MAI-001/gate/20261027_014721_NEEDS_FIX.md` (설계 MAJOR 3 · 통계 MAJOR 1 · 의료 MAJOR 1, CRITICAL 0)
사용자 지시(2026-10-27): 단측 검정·Holm·비열등 기준 임의 변경 금지 → Holm family m=6·경계·α 그대로.

| 지적 | 출처 | rev4 조치 |
|---|---|---|
| 판정표에 이름 없는 상태, 보류/불가 충돌 | 설계 G-H1-verdict-gap · 통계 S-label-gap · 의료 M-safety-rule(c) | 순서표 INVALID > SAFETY_FAIL > SAFETY_HOLD > 유의×MID 4칸(SUCCESS / SIGNIFICANT_BELOW_MID / ABOVE_MID_NOT_SIGNIFICANT / FAILURE). 모두 '채택 안 함' 으로 통일 |
| 채택 사슬 순차/독립 모호 | 설계 G-chain-order | 순차 채택(C→PA→PB_REL→PB→PC, 첫 미채택에서 멈춤, 없으면 C). PA = H1 SUCCESS. Holm·IUT 는 사슬과 무관하게 전부 계산, 비교 대상은 SELECT 종료 시 고정 |
| 계산 수 구현 의존 | 설계 F-count-formula | 닫힌 식 Σ[|D_cand|×|Q_elig|×s + 49×a], 동점 처리 점수도 D8∩Act 기준 |
| IUT 와 Holm family FWER | 통계 S-iut-fwer | **B안**(사용자 지시 준수): FWER 0.025 는 Holm 6개에만, IUT 8개(안전 7 + 효율 1) 각 α 0.025, 합집합 상한 0.225 를 명시·보고 |
| PB_REL·H3c 안전 경계 없음 | 의료 M-safety-rule(a)(b) | H2a 중증 누락 IUT(+0.5%p), PC 중증 누락@WD_MODEL IUT(+0.5%p), PC 잘못된 분기 종료 IUT 3조건 추가(Holm 밖) |
| 질환별 규칙 정의 | 의료(d) · 통계 S-disease-rule · 설계 F-perdisease-noise | 점추정 > +2%p, FINAL n≥100, 의도된 보수 규칙 명시, n·SE 보고, PC 적용 조건(WD_CORRECT 제외, seed 3개), n≥100 질환 수 FINAL 잠금 전 rg record |
| MID 근거·주장 문구 | 의료 m-mid-basis · 통계 S-mid-claim | '합성 연구용 사용자 사전 고정값, 임상 근거 없음', P*(Δ*≥0.01) 보고, '통계적 입증' 문구 금지, 정수 비교 |
| 인구집단 부분집합 | 의료 m-demo | AGE 구간·SEX·macro Top-5 기술 통계 + subgroups.csv |
| B 학습 인코딩 | 의료 m-B-encoding | 기재 1 / 미기재 0 명시 |
| 순위 동점 | 설계 E-tie-rank | 비관적 동점 처리(정답을 동점 집단 맨 뒤) 공통 |
| 자식 근거 결합확률 | 설계 B-child-lik | confounder 추가 |
| FINAL 재시도 범위·잠금 범위 | 설계 D-final-retry · G-lock-scope | 출력 폴더 실제 검사, 로그에 지표 미출력, 잠금 해시 = config + 코드 SHA 목록 + 모델 SHA |
| HOLDOUT csv 필터 | 설계 B-holdout-csv | SELECT_SMOKE 행만 읽음 |
| prereg 인용 위치·문구 | 설계 A-prereg-cite | §6(42행), 'STEP16B 사본 외 없음' |
| assert 자기보고 의존 | 설계 E-assert-instr | 독립 참조 점수기 수치 대조 + INVALID 조건 |
| τ 가상 판정·실패 처리 | 설계 D-tau-virtual · 통계 S-tau-p | 같은 τ 로 PB_REL 가상 판정, 실패 시 p_H2b:=1 |
| H3b 보고 | 통계 S-h3b-report | seed 별 Δ·평균±std·하한 3개 |
| SELECT 문구 | 통계 S-select-wording | τ 는 SELECT 전체(SMOKE 포함), 코드 변경 diff·전후 지표 기록 |
| 표본 수·최소 검출 차 | 통계 S-n | FINAL 잠금 전 rg record(실행 단계) |
| research_question 태그·대응표 MID 행 | 의료 m-doc | rev4 태그, MID 행 갱신 |
| split_rules docstring 3-tuple | 설계 m6 잔여 | 4-tuple 로 수정(테스트 9 OK) |
| severity 1차 인용 | 의료 m-sev-cite | 논문 작성 전 요건으로 명시(실행 전 요건 아님) |
