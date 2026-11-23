# PRIOR_ART_REVIEW — B7+B9(+B10) 직접 경쟁·강한 기존 방법 감사

- 작성: 2026-11-21, Agent B (강력한 기존 방법 담당)
- 연구 질문: 복합질환 환자에게 여러 지침을 적용할 때 환자 정보·선호가 불완전하면 무엇을 확정/보류하고 무엇을 먼저 확인할지
- 방식: 이전 4개 보고서(R5 통합 검증, 복합질환 심층, Gate0, GuidelineCoordination 재현)의 선행연구 표를 재사용하고, 직접 비교에 필요한 원문·코드만 이번에 추가 확인했다.
- 태그: **[원문]** 이번 세션 원문 직접 확인 · **[초록]** · **[2차]** 이전 감사·요약 경유(괄호에 출처) · **[코드]** 코드 직접 확인/실행 · **[합성]** 합성 실험
- 상태 어휘: YES / PARTIAL / NO_MENTION(원문에 서술 없음, "못 함"이 아님) / UNKNOWN(본문 미확보). 저자가 직접 미지원이라고 쓴 경우는 CSV `author_stated_limit` 열에 따로 적었다.
- 서지: `sources.csv`(P01–P39). 칸별 근거 위치: `PRIOR_ART_CAPABILITY_MATRIX.csv`(31개 방법 × 8기능 = 248행)

---

## 0. 판정 먼저

| 질문 | 판정 |
|---|---|
| 기존 단일 방법이 (a)~(g)를 동시에 처리하는가 | **불가능(확인 범위)**. 공개 문헌 방법 중 가장 넓은 것은 MitPlan 2.0·Fdez-Olivares(a+b+d, 점 선호), ATLAS(a+e+f), ROR/SMAA/minimax regret(b+c). (e) 정보 부족 보류와 (g) 근거 적용 범위를 지침 상호작용과 한 판정에 넣은 공개 방법은 찾지 못함 |
| 기존 방법을 결합하면 해결되는가 | **계산 수준에서는 가능.** 이전 R5 결합 정식화 B(상태공간 + LP/MILP)가 (a)(b)(c)(d)(e)(g)(h)를 합성 1,261건에서 정답과 일치시켰다 [코드][합성]. (f) 확인 정보 우선순위는 B에 없고 Gate0 C의 기존 정책(hitting set·EC2·VOI)이나 변수 고정 재실행으로 붙는다. **새 알고리즘은 필요하지 않다** |
| 해결 안 되는 것 | 실제 지침 인코딩 충실도, 선호 범위 도출, 질환 조합별 근거 데이터, 독립 임상 정답. 모두 지식·데이터·평가 문제 |
| 직접 경쟁 방법 원본 실행 | **불가(MitPlan 코드 비공개)** → A는 "MitPlan식 독자 구현(원본 미재현)". ATLAS는 원본 코드가 공개됐으나 LICENSE 없음·스키마 다름 → 선택적 A′ |
| 공개 평가 자료 | MGCDS 4사례(Apache-2.0)에 서술형 기대 출력이 있으나(Case 2·3 "Revised treatment", Case 1 Option 1–3), 환자 값이 모두 확정이고 선호는 한 문장, 기계 판독 정답·정확도 지표 없음. Case 2 작성자 = MitPlan 팀(독립 정답 아님) |

## 1. 이번에 새로 확인한 것 (재사용 표와의 차이)

1. **[원문] MitPlan 2.0 보고서 재확인**(MGCDS commit 718e8dfb, 27쪽): 핵심 문장 위치 p.3, p.4, p.6, p.7, p.9, p.20, p.21 그대로 확인. 전문에서 `unknown`·`missing`·`incomplete`·`uncertain`·`evidence` 문자열 0건 → (e)(f)(g)는 **NO_MENTION**. 관찰: Fig 15의 eGFR 값 25와 Case 2 설명의 eGFR 35가 다르다(의미 확인 필요, 결론에 쓰지 않음).
2. **[원문] MGCDS 저장소 2곳 라이선스·내용**: 둘 다 Apache-2.0. `william-vw/MGCDS`(약 40 MB, 대부분 지침·논문 PDF) / `MGCDS/benchmark-framework`(파일 3개). 실행 코드 없음. 소형 파일만 `baselines/agentB/upstream/`에 받음(1.1 MB). 지침·논문 PDF는 제3자 저작물이라 받지 않음.
3. **[원문] 기능 18개 원문 재확인**: A1–A7 상호작용, B1–B7 완화, C1 선호·부담, C2 자원, C3 설명, C4 대안. 미확인 환자 정보·불완전 선호·근거 적용 범위 항목 없음.
4. **[원문][코드] ATLAS**: 논문 HTML에 코드 링크(`HKUSTGZ-ML4Health-Lab/ATLAS`) 있음. GitHub API license=None. 동결 추론 진입점은 규칙표 + 순수 Python 오케스트레이터. 코드에서 규칙 edge `level`(UNKNOWN→C)을 caution 표지로, `margin_for_abstention`으로 보류 → R5 표의 "근거 등급 미사용"을 **(g) PARTIAL**로 정정(환자별 적용 범위 판정은 아님).
5. **[원문] FHIR R5 Evidence 정의**: `variableDefinition.directnessMatch` = low|moderate|high|exact, `intended`/`observed`, `certainty`. 표현 표준이며 판정 로직 없음 → (g) PARTIAL.
6. **[원문:CRAN] SMAA 구현**: R `smaa` 0.3-4·`hitandrun` 0.5-6 모두 GPL-3. 로컬 R 미설치.
7. **GoCom 공개 코드**: GitHub 저장소 검색 0건 → 미발견.
8. **[코드] R5 코드 복사본 실행 확인**: 손 사례 11/11 정답 일치(REUSE_MAP).

## 2. 기능 매트릭스 (요약)

Y=YES, P=PARTIAL, –=NO_MENTION, ?=UNKNOWN. a 상호작용 · b 선호 · c 불완전 선호 · d 치료 부담 · e 정보 부족 보류 · f 확인 우선순위 · g 근거 적용 범위 · h 동시 처리. 칸별 근거 위치는 CSV.

|---|---|---|---|---|---|---|---|---|---|
| M01 | MitPlan 2.0 (저자 기술 보고서) | Y | Y | – | Y | – | – | – | P |
| M02 | MitPlan 1 (AIIM 2021) | Y | Y | ? | P | ? | ? | ? | P |
| M03 | Wilk 2017 FOL 완화 프레임워크 | Y | ? | ? | ? | ? | ? | – | ? |
| M04 | Michalowski 2015 FOL + 환자 선호 | Y | Y | ? | – | ? | – | – | P |
| M05 | MitPlan 그래프 재작성 (AIIM 2023) | Y | ? | ? | ? | ? | ? | ? | ? |
| M06 | MitPlan 설명 구성요소 (JBI 2024) | Y | P | ? | P | ? | ? | ? | ? |
| M07 | GoCom (Kogan·Peleg) | P | P | – | – | P | – | – | – |
| M08 | GLARE-SSCPM (Terenziani 팀) | Y | – | – | P | – | – | – | – |
| M09 | SDA/SA (Riaño 팀) | Y | P | – | P | – | – | – | – |
| M10 | CMM (Marcos 팀) | Y | P | – | – | – | – | – | – |
| M11 | CTL / Dynamic Weighted CIG Planner (Van Woensel·Abidi) | Y | – | – | – | – | – | – | – |
| M12 | TMR4I (Zamborlini) | Y | – | – | – | – | – | – | – |
| M13 | ABA+G 논증 (Čyras 2019) | Y | Y | P | – | – | – | – | P |
| M14 | 다중 에이전트 HTN (Fdez-Olivares 2019) | Y | Y | – | Y | – | – | – | P |
| M15 | SMT 다약제 CDS (Redeker·Bowles 2020) | Y | P | ? | P | ? | ? | ? | ? |
| M16 | ROR-imprecise (Corrente·Greco·Słowiński 2012) | – | Y | Y | P | P | – | – | P |
| M17 | SMAA (Lahdelma 1998; Tervonen 2011) | – | Y | Y | P | P | – | – | P |
| M18 | Minimax regret (Boutilier 2006) | P | Y | Y | P | – | P | – | P |
| M19 | 다중모형 MDP (Steimle 2021) | P | – | – | Y | – | – | P | P |
| M20 | Patient-centered prioritization MCDA (Schuttner 2025) | P | P | P | P | – | – | P | P |
| M21 | R5 결합 정식화 B (상태공간 + LP, B_milp 포함) | Y | Y | Y | Y | Y | – | Y | Y |
| M22 | R5 C 정식화 (P/K/Q 양화 질의) | Y | Y | Y | Y | Y | P | Y | Y |
| M23 | Trial Score (Laffin 2019) | – | – | – | – | – | – | Y | – |
| M24 | Seneviratne 2023 의미 기반 CDS | – | – | – | – | – | – | Y | – |
| M25 | FHIR R5 Evidence | – | – | – | – | – | – | P | – |
| M26 | 전이가능성·positivity (Degtiar & Rose 2023 등) | – | – | – | – | – | – | Y | – |
| M27 | ATLAS (arXiv 2608.09443) | Y | – | – | – | Y | Y | P | P |
| M28 | VOI·EC2 질문 정책 (Golovin-Krause; Gate0 C pol_voi/pol_ec2) | – | P | P | – | Y | Y | – | P |
| M29 | 최소 hitting set / 최악 결정나무 (Gate0 C MDQ) | – | P | P | – | Y | Y | – | P |
| M30 | Neuro-symbolic guideline coordination (Xie & Du 2026) | Y | – | – | – | P | – | – | – |
| M31 | MGCDS 벤치마크 (Van Woensel 2023) - 평가 틀 | Y | Y | – | Y | – | – | – | – |

**읽는 법**
- M21·M22는 우리 이전 R5의 **결합 계산**(기존 기법 조합)이다. 문헌 방법과 같은 줄에 둔 것은 비교용이며 신규 방법이라는 뜻이 아니다. 근거는 합성 실험뿐이고 임상 성능은 NOT_EVALUATED.
- "–"는 원문에 서술이 없다는 뜻이다. 저자가 직접 미지원이라고 쓴 칸(예: CTL C1 N, GLARE 선호 형식 표현 없음, GoCom C2, TMR4I 근거 강도)은 CSV `author_stated_limit`에 있다.
- MitPlan 계열 5편 중 4편은 본문 미확보라 "?"가 많다. Wilk 2017의 "possible patient states"는 (e)를 처리했을 가능성이 있어 "못 함"으로 쓰면 안 된다.

## 3. 기능별 가장 강한 기존 방법

| 기능 | 가장 강한 기존 방법 | 근거 수준 | 남는 공백(언급 없음 기준) |
|---|---|---|---|
| (a) 상호작용 | MitPlan 2.0(A1–A7 + B1–B7 완화, 시간), GLARE(시간), Xie&Du(Z3 7종) | [원문] | 목표 충돌은 완화 연산자 없으면 계획 없음(MitPlan 저자 명시) |
| (b)(c) 선호·불완전 선호 | ROR-imprecise, SMAA, Boutilier MMR | [2차:이전 감사 원문] | 대안 목록 전제, 지침 상호작용·환자 상태 미결합 |
| (d) 치료 부담 | MitPlan 2.0, Fdez-Olivares(고정 가중합) | [원문]/[2차] | 부담 상한 불명·부담 선호 범위 미서술 |
| (e) 정보 부족 보류 | ATLAS(미확인 유지·보류), GoCom(실행 정지) | [원문][코드]/[2차] | 선호·근거 범위와 결합한 보류 사유 구분 없음 |
| (f) 확인 우선순위 | ATLAS(질문 순위·정지 규칙), EC2·VOI·hitting set | [원문]/[코드] | 선호 질문과 임상 질문을 함께 비교하는 임상 CDS 사례는 확인 못 함 |
| (g) 근거 적용 범위 | Trial Score, Seneviratne, 전이가능성; FHIR(표현) | [2차]/[원문] | 다중지침 상호작용과 결합한 사례 없음 |
| (h) 동시 처리 | 문헌: MitPlan 2.0(a+b+d), ATLAS(a+e+f). 결합: R5 B | [원문]/[코드][합성] | 문헌 단일 방법으로 (a)~(g) 동시 처리 사례 없음 |

## 4. 원본 코드·평가 자료 가용성

| 방법 | 공식 구현 | 라이선스 | 실행 가능성(이번 세션 판단, 실행 안 함) | 평가 자료 |
|---|---|---|---|---|
| MitPlan 1·2.0·2023·2024 | **비공개**(R5 GitHub 검색 0건 관련, 보고서는 PDDL 조각만) | – | **원본 실행 불가** → 독자 구현만 | MGCDS 4사례 서술(정답 지표 없음) |
| OPTIC 계획기 | 공개 여부·라이선스 확인 필요 | 확인 필요 | 확인 필요 | – |
| MGCDS 벤치마크 | 자료만(코드 없음) | Apache-2.0(두 저장소) | 해당 없음 | Case 1–4 docx·pptx, 기능 18개, 보고 양식, 6팀 해법 보고서. 기대 출력 = 사례 작성자 서술 1개(Case 2·3), 옵션 3개(Case 1), Case 4 설명에 없음(슬라이드 확인 필요). 지침 PDF는 제3자 저작물 → 재배포 금지로 취급 |
| Van Woensel·Abidi CTL | OWL/TTL 5개(MGCDS 안) | Apache-2.0 | 추론기 코드 없음 → 불가 | Case 1·3 |
| GoCom | 미발견(GitHub 검색 0건) | – | 불가 | MGCDS Case 1–3 해법 보고서 |
| GLARE-SSCPM | 확인 못 함 | – | 확인 필요 | 해법 보고서 |
| ATLAS | **공개**(HEAD 160dd376, 약 11 MB) | **없음 → 재배포 금지** | 조건부: 동결 추론은 순수 Python으로 보임(일부 파일만 확인). 클론·실행은 사용자 승인 후. LLM 기준선은 유료 API 가능성 → 실행 안 함 | 개발 39건·테스트 201건 입력 JSON, GeriMedBench 76, 정답 `dev_gold.json` 공개. 단 자체 스키마(선호·부담·근거 범위 없음) |
| Xie & Du 2026 | 공개(이전 재현 회차) | **없음** | 규칙 변환에 LLM(OpenRouter, 유료) 필요 → 변환 단계 실행 안 함. Z3 판정부는 이전 회차에서 실행 | `rules_gold.json` 563규칙(쌍 정답 미공개) |
| ROR-imprecise | 공식 구현 확인 안 함 | – | scipy LP로 구현 가능(R5 B가 같은 판정) | 이론 |
| SMAA | R `smaa`, `hitandrun` | GPL-3 | R 미설치 → 설치 필요(사용자 승인). Python LP로 대체 가능 | – |
| Boutilier MMR | 공식 구현 없음 | – | scipy milp로 구현 가능 | – |
| Trial Score | 확인 못 함 | – | 정의가 단순(구역 판정) → 독자 구현 가능 | – |
| FHIR R5 Evidence | 표준 문서 | HL7 FHIR 라이선스(CC0로 알려짐, 확인 필요) | 표현만 | – |
| R5 결합 정식화 B / C 정식화 / Gate0 C 질문 정책 | 로컬 내부 코드 | 내부 | **가능**(복사본 손 사례 11/11 확인) | R5 합성 1,261건 + 동결 정답(합성) |

`baselines/agentB/upstream/`에 받은 것: MGCDS 두 저장소의 README·LICENSE·기능/사례/평가 docx·MitPlan 보고서 PDF·CTL OWL/TTL 5개(모두 Apache-2.0). ATLAS·Xie&Du 코드는 라이선스가 없어 받지 않았다.

## 5. 기존 방법 결합으로 해결 가능한가 — 판정표

| 하위 과제 | 결합 구성(모두 기존 기법) | 판정 | 근거 |
|---|---|---|---|
| B7 실제/조건부 충돌 구분 | 규칙 엔진 + 미확인 상태 열거 | **가능** | R5 B `_components` REAL/CONDITIONAL, E1·E10 정답 1.0 [코드][합성] |
| B7 중복·보완 | 규칙 종류 추가(C 정식화 DUPLICATE·synergy) | **가능(표현)** | C 정식화 코드 [코드]. D 스키마에는 없음 → 실제 사례에서 C 정식화 병행 |
| B7 적용 조건 미확인 보류 | 3값 적용 + 상태별 판정 | **가능** | CONDITIONAL_APPLY + INFO_HOLD [코드][합성] |
| B9 불완전 선호 | W polytope + LP(필연/가능 최적), ∃w∀s 결합 LP 또는 MILP+CEGAR | **가능** | R5 E2·E6 1.0 [코드][합성]; ROR·MMR [2차] |
| B9 치료 부담 | 부담을 기준으로, 상한 불명은 부담 상한 시나리오 | **가능** | R5 B(pills/visits), C(bcap_options) [코드] |
| B10 근거 적용 범위 | 볼록 껍질/참가 조건 상자 지지 + OK/OUT/NOENTRY | **가능(계산)** | R5 E3·E7 [코드][합성]. 실제 시험 경계는 CT.gov로 입력 가능(R5 A) |
| 정보 부족 vs 근거 부족 구분 | 상태 열거 후 "어떤 상태에서도 근거 공백" 검사 | **가능** | R5 gap_distinction 1.0 [코드][합성] |
| 세 요소 동시(공유 숨은 변수) | **결합** 상태공간(모듈 순차 연결은 손실) | **가능(결합 정식화만)** | R5 E4: B 1.0, B′ 0.793 [코드][합성] |
| 확인 질문 우선순위 | 변수 고정 재실행(결정 관련성) / hitting set MILP / EC2·VOI | **가능(조건부)** | Gate0 C 코드 [코드], ATLAS [원문]. R5 B와의 연결 어댑터는 미구현 → METHOD_SPECS B-Q |
| 계산량 | 상태 열거 지수적, 단일 MILP | **실질 병목 증거 없음** | R5 n=10 15.3 s vs B_milp n=20 0.29 s 이하 [코드][합성] |
| 지침 원문 충실 인코딩 | – | **결합으로 해결 불가(지식 문제)** | Xie&Du 19.9% 오류, GuidelineForge 207/4,304 [2차] |
| 선호 범위 도출 | – | **결합으로 해결 불가(도출 문제)** | Fried 2011 재질문 신뢰도 fair~poor [초록, R5 A] |
| 질환 조합별 근거 | – | **불가(데이터 문제)** | 시험 배제(R5 A: CT.gov 17건) |
| 임상 정답 | – | **불가(평가 문제)** | 독립 임상의 2인 이상 필요 |

**종합**: 계산 문제는 기존 방법 결합으로 해결된다(R5 결론 유지). 이번 감사로 추가된 것은 (f)의 연결 경로(Gate0 C 정책·ATLAS)와 공개 자료·코드 라이선스 상태다. 결합 계산을 새 알고리즘으로 주장할 근거는 없다.

## 6. 비교 실험 방법 선정 (상세는 `baselines/agentB/METHOD_SPECS.md`)

| 슬롯 | 방법 | 원본/독자 |
|---|---|---|
| A | MitPlan식 독자 구현(원본 미재현) — `weak.run_A` | 독자 구현 |
| A′ | ATLAS 동결 추론(선택, 승인 후) — (e)(f) 원본 비교 | 원본 코드(재배포 금지) |
| B | R5 결합 정식화 `run_B` + `run_Bmilp` + 질문 래퍼 B-Q | 이전 R5 기존 결합 |
| C | 규칙 엔진 → 점 가중합 → 근거 표지 순차 파이프라인 (+C′ = R5 B′) | 독자 구현 |
| D | MitPlan식 + 시나리오 열거 + 꼭짓점 재계획 + 근거 표지 보류 + 변수 고정 질문 | 독자 구현 |

## 7. 한계

- MitPlan 동료심사 논문 4편, Wilk 2017, Van Woensel 2023 본문 미확보(이번에도 재시도하지 않음; R5에서 403·closed 확인).
- ATLAS는 HTML 키워드·일부 코드 파일만 확인. 전체 코드 정적 분석·실행 안 함.
- 이전 감사 원문을 [2차]로 재사용한 칸(ROR, SMAA, MMR, Trial Score, Seneviratne, TMR4I, Čyras, Fdez-Olivares)은 이번에 다시 열지 않았다.
- MGCDS Case 4 기대 출력 위치(슬라이드)는 확인하지 않았다.
- 기능 매트릭스 판정은 사람이 근거 위치를 보고 적은 값이다. 독립 재검토 대상.
