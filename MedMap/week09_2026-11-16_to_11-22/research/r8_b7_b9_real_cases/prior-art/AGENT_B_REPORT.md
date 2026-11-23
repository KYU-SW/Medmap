# AGENT_B_REPORT — 강력한 기존 방법 감사 결과

- 작성: 2026-11-21, Agent B · 쓰기 범위: `prior-art/`, `baselines/agentB/`만
- 결론 한 줄: **기존 단일 방법으로는 (a)~(g)를 동시에 처리하지 못하지만, 기존 방법을 결합하면 계산 문제는 해결된다. 새 알고리즘은 필요하지 않다**(R5 결론 유지). 이번에 새로 확인한 것은 질문 우선순위 연결 경로와 공개 코드·자료의 라이선스 상태다.

## 1. 기능 매트릭스 핵심 (31개 방법 × 8기능, 248칸)

상태 분포: YES 56 · PARTIAL 48 · NO_MENTION 115 · UNKNOWN 29. "NO_MENTION"은 "못 함"이 아니다.

| 방법 | a 상호작용 | b 선호 | c 불완전 선호 | d 부담 | e 정보 부족 보류 | f 확인 우선순위 | g 근거 범위 | h 동시 |
|---|---|---|---|---|---|---|---|---|
| MitPlan 2.0 [원문 보고서] | Y | Y(점) | – | Y | – | – | – | P |
| Wilk 2017 [초록] | Y | ? | ? | ? | ?("possible patient states") | ? | – | ? |
| GoCom | P | P | – | – | P(실행 정지) | – | – | – |
| MGCDS 다른 4팀 | Y | –~P | – | –~P | – | – | – | – |
| Čyras ABA+G | Y | Y | P(preorder) | – | – | – | – | P |
| ROR / SMAA / Boutilier MMR | –/–/P | Y | Y | P | P/P/– | –/–/P | – | P |
| Trial Score / Seneviratne / 전이가능성 | – | – | – | – | – | – | Y | – |
| FHIR R5 Evidence | – | – | – | – | – | – | P(표현) | – |
| ATLAS [원문+코드] | Y | – | – | – | Y | Y | P | P |
| Gate0 C 질문 정책(VOI·EC2·hitting set) [코드] | – | P | P | – | Y | Y | – | P |
| **R5 결합 정식화 B** [코드][합성] | Y | Y | Y | Y | Y | – | Y | Y |
| R5 C 정식화(P/K/Q) [코드][합성] | Y | Y | Y | Y | Y | P | Y | Y |

- 공개 문헌에서 가장 넓은 것: MitPlan 2.0(a+b+d, 점 선호, 계획 1개), ATLAS(a+e+f).
- 이번 정정: ATLAS (g)를 R5의 "근거 등급 미사용"에서 **PARTIAL**로 올림(코드에서 권고 수준 표지를 caution에 사용, 환자별 적용 범위는 아님).
- MitPlan 2.0 보고서 전문에 unknown/missing/incomplete/uncertain/evidence 0건 → (e)(f)(g) NO_MENTION [원문].

## 2. 원본 코드·평가 자료

| 대상 | 공개 | 라이선스 | 이번 판단 |
|---|---|---|---|
| MitPlan(전 계열) | 코드 비공개 | – | 원본 실행 불가 |
| MGCDS 벤치마크 2개 저장소 | 자료만 | Apache-2.0 | 4사례 서술형 기대 출력(Case 2·3 1개, Case 1 옵션 3개, Case 4 확인 필요). 환자 값 전부 확정, 선호 1문장, 정답 지표 없음. Case 2 작성자 = MitPlan 팀 |
| ATLAS | 코드 공개 | **없음(재배포 금지)** | 동결 추론은 순수 Python으로 보임. 클론·실행은 승인 후 |
| Xie & Du | 코드 공개 | 없음 | 규칙 변환에 유료 LLM 필요 |
| SMAA(R) | 공개 | GPL-3 | R 미설치 |
| GoCom / GLARE / Trial Score | 미발견·미확인 | – | 독자 구현만 가능 |
| R5 B·C, Gate0 C | 로컬 | 내부 | 복사본으로 손 사례 11/11 정답 일치 확인 |

받은 것: `baselines/agentB/upstream/`(MGCDS 소형 파일 1.1 MB, 모두 Apache-2.0). 라이선스 없는 코드는 받지 않았다.

## 3. 비교 방법 A~D (원본/독자 구분)

| 슬롯 | 방법 | 구분 | 코드 |
|---|---|---|---|
| A | **MitPlan식 독자 구현(원본 미재현)**: 폐쇄 세계, 점 선호, 근거 무시, 계획 1개 | 독자 구현 | `weak.run_A` 그대로 |
| A′(선택) | ATLAS 동결 추론: (e)(f) 원본 비교용 | 원본 코드, 재배포 금지, 실행은 승인 후 | 외부 |
| B | **이전 R5 결합 정식화**(상태공간 + LP, 단일 MILP 대조) + 질문 래퍼 B-Q(변수 고정 재실행, 기존 기법) | 이전 R5 기존 결합 | `strong.run_B`, `b_milp.run_Bmilp`, C 정식화 `categorize`, Gate0 C `hitting_set_milp` |
| C | **순차 파이프라인**: 3값 규칙 엔진 → 점 가중합 → 근거 표지 후처리 | 독자 구현(새 래퍼 필요) | `weak` 보조 + `strong._in_hull_lp`. 대조 C′ = R5 B′ `run_Bp` |
| D | **MitPlan식 확장**: 시나리오 열거 + W 꼭짓점 재계획 + 근거 표지 보류 + 변수 고정 질문 | 독자 구현(새 래퍼 필요) | `run_A` 로직 사본 + `strong._states/_in_hull_lp/_final` |

D와 B의 예상 차이(측정 대상): 꼭짓점 재계획의 가능 최적 누락, ∃w∀s 혼합 양화, 계산량.

## 4. R5 코드 재사용 방법

1. `sys.path`에 `baselines/agentB/reuse/r5_D_experiments/methods`와 `.../r5_D_experiments` 추가 → `from strong import run_B, run_Bp`, `from b_milp import run_Bmilp`, `from weak import run_A, run_C`, `from ground_truth import solve`.
2. 사례 JSON을 R5 D 인스턴스 스키마로 변환: `obs`(T/F/U), `deps`, `guidelines[{app, options}]`, `actions[{id, effect, pills, visits, trial}]`, `rules[{a, b, cond, type}]`, `patient_cov{x0, x1_base, x1_delta, x1_var}`, `W{center, r}`.
3. 출력: `final`(10범주), `per_state`, `ewas`/`fsew`, `app`, `rules`.
4. D 스키마에 없는 것(중복·보완·미확인 상호작용, 부담 상한 불명, 선호 부분 순서, 출처 상충, 효과 구간, B10 다섯 태그)은 `reuse/r5_C_formalization/integrated_model.py`(`categorize`, `judge`, `W_matrices`)를 병행한다.
5. 알려진 제약: 공유 변수 1개·2차원 공변량·기준 3개·점 효과. 확장은 새 파일로 복사 후 수정(원본 수정 금지).
6. `evaluate.py`는 복사본 폴더에서 동결 해시·입력 파일이 없어 그대로는 돌지 않는다. 실제 사례에는 `run_*`을 직접 부른다.

## 5. 결합 해결 판정 요약

| 하위 과제 | 판정 |
|---|---|
| 실제/조건부 충돌, 적용 조건 미확인 보류 | 가능 |
| 중복·보완 | 가능(C 정식화 표현) |
| 불완전 선호·치료 부담 | 가능 |
| 근거 적용 범위, 정보 부족 vs 근거 부족 구분 | 가능(계산) |
| 세 요소 동시(공유 숨은 변수) | 결합 정식화로만 가능(모듈 순차는 손실) |
| 확인 질문 우선순위 | 조건부 가능(기존 정책 연결, 어댑터 미구현) |
| 지침 인코딩 충실도·선호 범위 도출·조합별 근거·임상 정답 | 결합으로 해결 불가(지식·데이터·평가 문제) |

## 6. 한 일 / 안 한 일

- 한 일: 이전 4개 보고서 재사용, MitPlan 보고서·MGCDS·FHIR·ATLAS·CRAN 원문/메타 재확인, R5·Gate0 코드 15개 파일 복사(SHA 15/15 일치), 복사본 손 사례 11건 stdout 실행.
- 안 한 일: 유료 API·LLM 호출, 저자 연락, 접근 제한 우회, ATLAS·Xie&Du 클론·실행, R 설치, git 작업, 지정 폴더 밖 쓰기. 기존 `~/medmap*` 폴더는 읽기만 했다.
- 총 다운로드: MGCDS 소형 파일 약 1.1 MB + ATLAS HTML 0.5 MB·코드 1개(scratchpad, 재배포 안 함).

## 7. 산출물

- `prior-art/PRIOR_ART_REVIEW.md` · `prior-art/PRIOR_ART_CAPABILITY_MATRIX.csv` · `prior-art/sources.csv` · `prior-art/AGENT_B_REPORT.md`
- `baselines/agentB/METHOD_SPECS.md` · `baselines/agentB/REUSE_MAP.md` · `baselines/agentB/reuse/`(복사본 + `SHA256_MANIFEST.txt`) · `baselines/agentB/upstream/`(MGCDS Apache-2.0 소형 파일)
