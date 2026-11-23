# SUBAGENT B — 기존 강력한 통합 방법의 실제 능력 감사 (B-7 + B-9 + B-10 동시)

- 작성: 2026-11-18 · 쓰기 범위: `B-prior-art/` 만 · 서지: `sources.csv`
- 대상 문제(동시 조건): **B-7** 복합질환 지침 상호작용 + **B-9** 불완전한 환자 선호·치료 부담 + **B-10** 환자 유형별 근거 적용 범위 한계
- 태그
  - **[직접 원문 확인]**: 이번 세션에서 본문을 직접 열람함(열람 범위 표기)
  - **[이전 감사 원문]**: 이전 감사(읽기 전용 3건)에서 원문 확인된 내용을 재사용. 이번에 다시 열지 않음
  - **[초록]**: PubMed·출판사·저장소 초록과 메타데이터 / **[2차]**: 검색 요약·다른 논문의 서술
  - **[수학적 검토]**: 이번 세션의 손 계산·논증 / **[연구 가설]**: 추론 / **[미검증]**: 확인 못 함
  - [실제 코드 실행]·[합성 실험]: **이번에는 하지 않음**(공식 코드를 찾지 못했고, 새 스크립트로 결과 파일을 만드는 일은 사용자 검토 대상임)
- 원칙: "논문에 언급 없음"은 "처리 불가"가 아님. 처리 불가는 저자가 직접 쓴 한계나 측정된 실패가 있을 때만 씀

---

## 0. 판정 먼저

| 질문 | 판정 |
|---|---|
| MitPlan 계열 원문 확보 | **부분 확보.** AIIM 2021·AIME 2021(MitPlan 2.0)·JBI 2017·AIIM 2023·JBI 2024 **논문 본문은 모두 접근 실패**(ScienceDirect 403, Unpaywall `closed`, Springer `CLOSED`). 대신 **MitPlan 저자 4명(Rao, M. Michalowski, Wilk, W. Michalowski)이 직접 쓴 MitPlan 2.0 기술 보고서 27쪽**을 공개 GitHub 저장소(william-vw/MGCDS, Apache-2.0, Van Woensel 2023 JBI 벤치마크 자료)에서 확보해 전문을 읽음 [직접 원문 확인] |
| 기존 방법 하나가 B-7+B-9+B-10을 **동시에** 처리하는가 | **불가능(확인 범위).** 가장 강한 MitPlan 2.0도 B-7은 처리, B-9는 **점 선호(고정 가중치·비용)만** 처리, B-10은 표현 수단이 없음 [직접 원문 확인]. 다른 계열도 셋 중 최대 둘 |
| 기존 방법을 **결합**하면 같은 출력이 나오는가 | **조건부 가능.** 계획기(MitPlan형) + 가중치 다면체 꼭짓점 반복 또는 시나리오 minimax regret + 근거 적용 범위 표지(Trial Score·FHIR directnessMatch)를 붙이면 "강건한 계획 / 선호 질문이 필요 / 근거가 없어 안 풀림"을 구분하는 출력을 **새 알고리즘 없이** 만들 수 있음 [수학적 검토 + 연구 가설]. 막히는 곳은 알고리즘보다 **입력 지식**(질환 조합별 적용 범위, 상호작용 확실성)과 **평가 정답**임 |
| 기획 문서의 MitPlan 기술("실행 가능한 그래프, PDDL 계획, 상호작용 수정, 환자 선호와 비용 최적화") | **정확함, 단 정밀화 필요.** (1) 선호 = 미리 존재하는 대안 노드의 **비용을 낮게 두는 점 값**, (2) 다목적 = **고정 가중합**(예: 0.2·비용+0.6·부담+0.2·비순응), (3) 출력 = **한 번 실행에 계획 1개** [직접 원문 확인]. **서지 오류**: 기획 문서 [S2]가 MitPlan 저자를 "Piovesan et al."로 적었으나 실제는 **Michalowski M, Wilk S, Michalowski W, Carrier M** [초록, PubMed 33581823] |

**가장 중요한 새 발견 3가지**

1. [직접 원문 확인] **MitPlan 2.0은 선호를 범위로 받지 않는다.** "Patient preferences are handled via costs (an alternative preferred by a patient is set to be less costly in the AG-RO model)"(보고서 p.4). 목적함수는 "minimizes a weighted sum of user-identified metrics, where the weights are chosen to reflect metrics' relative importance"(p.3). 출력은 "The planner returns one plan in a single run"(C4, p.9). 대안 계획은 목적함수를 바꿔 다시 돌려야 얻는다.
2. [직접 원문 확인] **MitPlan 2.0의 환자 자료는 점 값이다.** 예: `(= (patientValue d2 eGFR HEMOGLOBIN) 25)`, 미확인 값을 표현하는 기호나 절차가 보고서 27쪽 어디에도 없음(Figure 15, p.21). 근거 확실성·근거 적용 범위도 전혀 언급되지 않음. 단, 이것은 **언급 없음**이지 저자가 "불가능"이라고 쓴 것은 아님. 선행 FOL판(Wilk 2017)의 "possibly incomplete patient information → possible patient states"가 PDDL판에 이어졌는지는 [미검증].
3. [직접 원문 확인] **분야 공동 벤치마크 자체가 B-10과 '정보 부족 vs 근거 부족'을 평가 항목에 넣지 않았다.** Van Woensel 2023 벤치마크의 기능 18개(A1–A7, B1–B7, C1–C4) 원문 목록에 미확인 환자 정보·근거 확실성·적용 범위 항목이 없음(Functional Features.docx). 6개 연구팀 해법 보고서도 이 축을 다루지 않음. 이것은 "불가능" 증거가 아니라 "평가되지 않았다"는 직접 증거.

---

## 1. MitPlan 계열 원문 확보 시도 기록

| 문헌 | 시도 경로 | 결과 | 확보 수준 |
|---|---|---|---|
| MitPlan, AIIM 112:102002 (2021) | Semantic Scholar API(DOI 미등록), Unpaywall(`is_oa:false`, `oa_status: closed`, repository copy 없음), UMN Experts(초록만, PDF 링크 없음), Europe PMC(PMCID 없음), WebSearch(PDF 없음) | **실패** | 초록 |
| MitPlan 2.0, AIME 2021 LNCS 12721:276–286 | Semantic Scholar(`openAccessPdf: CLOSED`), UMN Experts, 검색 | **실패**. 대학 프록시 미러가 검색에 나왔으나 무단 접근이라 사용 안 함 | 초록 + **저자 기술 보고서(아래)** |
| Wilk 외 2017, JBI 66:52–71 (doi 10.1016/j.jbi.2016.12.002) | Semantic Scholar가 `BRONZE` 표시(ScienceDirect PDF). WebFetch → **HTTP 403**. 브라우저 위장 다운로드는 자동 분류기가 차단 → 우회하지 않음 | **실패** | 초록(PubMed 27939413 전문 초록) |
| 그래프 재작성 2023, AIIM 140:102550 | Semantic Scholar(OA 없음), Europe PMC | **실패** | 초록 |
| 설명 구성요소 2024, JBI 156:104681 | Semantic Scholar `BRONZE`(doi 링크), ScienceDirect 403 | **실패** | 초록(구조화 초록 전문) |
| Van Woensel 외 2023 JBI 142:104395(6개 MGCDS 화이트박스 평가) | ScienceDirect 403, UJI 저장소(봇 차단 Anubis), UniUPO IRIS(403) | **논문 본문 실패**. 그러나 논문의 **공개 자료 저장소** 확보 | 초록 + 공개 자료 |
| **MitPlan 2.0 Solution Report**(저자 작성, 27쪽) | GitHub william-vw/MGCDS `Solution Reports/Martin Wojtek Szymon Malvika_Rao/MitPlanSolutionReport.pdf` (Apache-2.0) | **성공, 전문 열람** | **직접 원문**(동료심사 논문은 아님. 저자가 벤치마크 질문지에 답한 기술 문서) |
| 2013 AAAI Workshop "Procedural Approach…"(CLP 쌍 완화) | aitopics 서지 | 초록만. 2021 계열과 방법이 다름(CLP) | 초록 |
| 공식 코드 | GitHub 검색 "MitPlan"(6건, 전부 무관한 게임·이름 충돌), "multimorbidity guideline PDDL"(0건) | **없음**. 보고서는 "single domain file + one problem file per use case"라고만 씀. PDDL 일부 조각만 그림으로 실림(Fig 7, 15) | 코드 미공개 |
| 학위논문·슬라이드 | 검색 1–2회 | 찾지 못함 | — |

---

## 2. MitPlan 2.0의 실제 기능 (저자 보고서 기준, 축소 없이)

모든 항목 [직접 원문 확인, MitPlanSolutionReport.pdf]. 쪽수는 보고서 쪽.

### 2-1. 작동 원리

1. 환자 진단으로 지침 저장소에서 **actionable graph(AG)** 를 고름. AG = 행동·결정·목표 노드, 병렬 블록 포함(p.4, Fig 7).
2. 2차 지식 저장소에서 적용 가능성이 있는 **revision operator(RO)** 를 고름. RO = "triggering conditions + mitigating actions"의 논리 규칙. 대체·삭제·추가, 그리고 용량 등 노드 속성을 바꾸는 함수(B2, p.7)를 지원(p.4).
3. AG를 RO가 도입하는 노드로 확장한 **hybrid AG-RO model**을 만듦. 상호작용은 **triggering sequence**(노드 수 길이의 이진 벡터)로 표현. "An adverse interaction is present only if a particular plan includes all action nodes present in a revision sequence"(p.5). 계획기는 그 노드 조합을 모두 포함하지 않는 계획을 찾음.
4. 환자 자료·선호·계획 기간·목적함수와 함께 **PDDL 문제**로 인코딩 → **OPTIC** 계획기로 실행 → 내부 계획을 후처리해 치료 계획으로 제시(p.3).
5. 계획 목표 = 모든 관련 AG 목표 노드의 논리곱(+선택적 목적함수). 목표 노드를 중간에 두면 계획 기간을 표현(p.4).

### 2-2. 질문별 실제 기능

| 기능 | 실제 처리 방식 | 원문 근거 |
|---|---|---|
| 시간 계획 | **있음.** durative action으로 기간을 지정. 예: 와파린+박트림 72시간 후 INR 재평가(Fig 18), 스텐트 후 수술 전 클로피도그렐 120시간 전 중단·티로피반 가교(Fig 22, 8,760–16,060시간 축) | A6, B6, B7, Use case 3·4 |
| 선호: 점 vs 범위 | **점.** "alternative preferred by a patient is set to be less costly". 대안 노드가 AG에 미리 있어야 함: "if such alternatives do not exist, then it is not possible for a patient to have a preference"(p.4) | p.4, p.17 |
| 다목적·부담 | **고정 가중합.** 지표: 재정 비용, 환자 부담, 비순응 가능성(비순응을 비용으로 환산). 예 `minimize [0.2*cost + 0.6*burden + 0.2*nonadherence]`. 가중치는 진료 중 조정 가능 | p.19–20 |
| 기본 비용 | 지표가 없으면 모든 행동 노드에 "execution cost"를 주고 총비용 최소화. **RO가 넣은 노드는 원래 노드보다 비싸게** 둬서 상호작용이 있을 때만 수정이 선택되도록 함 | p.4 |
| 충돌 해결 | RO로 대체·삭제·추가·용량 조정·모니터링 추가·지연·겹침 보장(B1–B7 모두 Y). **목표 충돌은 부분**: "Without a mitigation strategy a treatment plan is not generated"(A3) | p.6–8 |
| 중복 권고 | **부분.** "the planner does not automatically reconcile the duplication of actions. Duplicate actions must be identified and removed by post-processing"(A5) | p.6–7 |
| 다중 상호작용 연쇄 | 있음(A7). 단 "assuming it knows how to mitigate them" | p.7 |
| 환자 상태 불확실성 | **보고서에 언급 없음.** 환자 자료는 결정 노드별 수치 점 값(`patientValue`). 미확인·구간·확률 표현 없음 | Fig 15 |
| 근거 확실성·권고 강도 | **언급 없음** | 전체 |
| 근거 적용 범위 | **언급 없음** | 전체 |
| 출력 형태 | **계획 1개/실행.** "The planner returns one plan in a single run. However it gives us the ability to identify and select alternative plans by changing the objective function"(C4 부분) | p.9 |
| 질환 우선순위·부분 치료 | "could use a combination of an objective function and a planning horizon to support the satisfaction of partial clinical goals" — **가능하다고 서술했으나 사례에서 시연하지 않음** | p.20 |
| 자원 최적화 | 부분. 같은 날 검사 묶기는 "outside the scope" | C2, p.9 |
| 설명 | 보고서 시점 **N**("explanations are not provided"). 이후 2024 JBI에서 사후 설명 구성요소 추가 [초록] | C3, p.9 |
| 확장성 | "flexible, scalable, and CPG agnostic"이라고 **주장**. 실행 시간·문제 크기 측정은 보고서에 없음 | p.5 |
| 평가 | 벤치마크 4사례(TIA+DU+골다공증, AF+HTN+CKD, VTE+UTI, 스텐트+폐 수술)의 계획 출력만 제시. 정답 대비 정확도 측정 없음 | Part 3 |

### 2-3. 계열 내 다른 판과의 관계

- **AIIM 2021(MitPlan 1)** [초록]: durative action, 계획 기간, 환자 선호·행동 비용·수정 비용 기준 최적화, "sequence of timed actions" 출력. 보고서의 2.0과 같은 골격으로 읽힘.
- **Wilk 2017 FOL판** [초록, 전문 초록 확인]: 입력에 "available (and possibly incomplete) patient information", 출력 management scenario에 "possible patient states", 깊이 우선 탐색으로 유효한 수정 순서 탐색, 정리 증명+모델 찾기. **"possible patient states"가 상태 열거인지, 모델 하나가 채택한 가정값인지는 본문 없이는 판단 불가 [미검증].** 이전 감사에서 2014·2015 AMIA 원문은 "시나리오에 환자 상태 가정이 포함된다" 정도였음 [이전 감사 원문].
- **2023 그래프 재작성** [초록]: task network + 그래프 재작성 규칙으로 RO를 형식화. "theory of mitigation"은 향후 과제.
- **2024 설명** [초록]: 왜 이 행동/왜 이 수정/비용·순응이 선택에 미친 영향, 의사 21명.
- [연구 가설] 보고서의 2.0 PDDL판은 FOL판의 "possible patient states" 기능을 그대로 가져왔다는 서술이 없음. 계획기 초기 상태는 PDDL 특성상 기본적으로 완전 상태(닫힌 세계)이므로, 미확인 값을 다루려면 별도 인코딩(조건부 계획·적합 계획·시나리오 반복)이 필요함. 이 판단은 PDDL 일반 지식에 근거하며 MitPlan 원문 근거는 아님.

---

## 3. 같은 벤치마크의 다른 다중지침 CDS 5개 (저자 해법 보고서, 공개 저장소)

[직접 원문 확인, MGCDS 저장소 해법 보고서. 각 팀이 자기 방법에 대해 쓴 자기 보고임]

| 방법(보고서) | 선호·부담 C1 | 자원 C2 | 불확실성 관련 서술 | B-10 관련 |
|---|---|---|---|---|
| GoCom(Kogan·Peleg 팀, Case 2) | 다중 option-set 생성 → **의사가 선택**. 자동 선호 계산 없음 | "we don't support it" | 없음 | 행동마다 "(evidence from guideline)" 출처 표기는 있음. 등급·적용 범위 아님 |
| GLARE-SSCPM(Terenziani 팀) | "no formal representation of patient's preference"; 의사가 관리 선택지·매개변수를 환자와 함께 고름 | — | **시간 불확정성**(temporal indeterminacy)으로 "probably overlap" 판정, 시간 선호·확률 확장 연구(AIME 2019, SAC 2017) | 없음 |
| SDA/SA(Riaño 팀) | 부분: 우선순위 함수로 표현 가능하나 **모든 시험에서 기본값 "take the first best"** 사용 | — | 없음 | 없음 |
| Marcos 팀(UJI, CMM) | Enquiry 과업으로 원하는 대안을 **입력받음** | N | 없음 | 없음 |
| Van Woensel·Abidi 팀(Continuous Transaction Logic + Dynamic Weighted CIG Planner) | **N**: "There does not exist a concept of 'goals' in our approach, such as reducing treatment costs or adherence to patient preferences" | — | **실행 시점 불확실성**: 어떤 과업이 실제 실행될지 모를 때도 통합 연산을 적용하고, 나중에 선택되지 않은 분기면 롤백. 시간 제약에 가중치와 퍼지 진리값 | 없음 |

**해석** [연구 가설]: 6개 팀 중 **선호를 계산으로 최적화하는 것은 MitPlan 2.0뿐**이고, 그것도 점 선호. 나머지는 의사·환자에게 선택을 넘김. 상태 불확실성을 다루는 것은 GLARE(시간)와 Van Woensel(실행 분기 롤백)인데, 둘 다 "환자 정보가 아직 없다"가 아니라 "미래 분기가 정해지지 않았다"는 유형임.

---

## 4. 방법별 11문항 감사

문항: ① 여러 질환 권고 동시 고려 ② 불완전 선호 계산 ③ 비용·부담 ④ 근거 적용 범위 ⑤ 근거 부족 vs 정보 부족 구별 ⑥ 셋 동시 처리 방식 ⑦ 표현 못 하는 요소 ⑧ 간단한 확장으로 해결? ⑨ 결합으로 같은 출력? ⑩ 계산량 문제 실제 발생 ⑪ 실험 확인 한계 vs 미언급

### 4-1. 다중지침 계획·논리 계열 (B-7 중심)

| 방법 | ① | ② | ③ | ④ | ⑤ | ⑥ | ⑦ | ⑧ | ⑨ | ⑩ | ⑪ | 확인 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **MitPlan 2.0** | 예(AG-RO, 시간 포함) | **아니오**: 점 비용 | 예: 비용·부담·비순응 고정 가중합 | 언급 없음 | 언급 없음 | 처리 안 함(B-7 + 점 B-9) | 선호 범위, 미확인 환자 값, 근거 등급, 적용 범위, 다수 계획 집합 | **부분**: 가중치 범위는 꼭짓점별 재실행으로 필연 최적 판정 가능(§6). 미확인 값은 시나리오 반복(2^m) | 예(§6 조합) | 측정 없음. "scalable" 주장만 | 저자 명시 한계: 목표 충돌은 RO 없으면 계획 없음, 중복 후처리, 설명 없음(당시), 자원 묶기 범위 밖. 나머지는 **미언급** | 직접 원문(보고서) |
| MitPlan 1(AIIM 2021) | 예 | 초록상 선호 최적화(형태 미확인) | 예: 치료비·수정 비용 | 초록 없음 | 초록 없음 | — | — | — | — | 초록 없음 | 본문 미확보 | 초록 |
| Wilk 2017 FOL | 예(다수 지침, 시간 활동) | 선호 반영(2015 원문: GRIP 가법 가치함수 → **우선순위 순서 적용**, 최적화 없음) | 아니오(2015 원문) | 없음 | **불명**: "possibly incomplete" 입력·"possible patient states" 출력 | — | 근거 등급 | ⑤가 핵심 미확인 | — | 정리 증명·모델 찾기 비용 측정 [미검증] | 본문 미확보 | 초록 + 이전 감사 원문(2014·2015) |
| 그래프 재작성 2023 | 예(task network) | 초록 없음 | 초록 없음 | 없음 | 없음 | — | — | — | — | — | "theory of mitigation" 향후 과제 | 초록 |
| GoCom | 예(목표 나무 충돌, 2종) | 아니오(옵션 제시 후 의사 선택) | 아니오 | 아니오(출처 표기만) | 결측 시 PROforma 실행 **정지** 후 입력 대기 [이전 감사 원문] | — | 근거 수준 = 저자 명시 향후 과제 | — | 부품으로 사용 가능 | 학생 실험만 | 상호작용 2종 제한 = 저자 명시 | 이전 감사 원문 + 해법 보고서 |
| TMR4I | 예(반복·모순·대안) | 아니오 | 아니오 | 아니오 | 아니오 | — | 시간·순서·근거·권고 강도 = 저자 명시 향후 과제 | — | — | — | 저자 명시 | 이전 감사 원문 |
| Čyras ABA+G 2019 | 예(TMR 위) | 선호 = preorder(부분 순서 허용), 확장으로 무모순 권고 집합 | 아니오 | 아니오 | 상호작용 확실성 □/◇ 구분(정보 부족은 아님) | — | 수치 신념 강도 = 향후 과제 | — | 예 | — | 원문의 미확인 상태 처리 미논의 | 이전 감사 원문 |
| Fdez-Olivares 2019 HTN | 예(다중 에이전트) | 정성 순위 → 정규화 가중치(점) | 예: 복용 횟수·알약·방문·기간 가중합 | 아니오 | 아니오 | — | 선호 범위·근거 | — | 예 | 사례 1건 | 지식 공학 부담 = 저자 명시 | 이전 감사 원문 |
| GLARE-SSCPM | 예(예정/후보 행동, 시간) | 아니오(의사 선택) | 정성 평가 제시 | 아니오 | 후보 행동 "일어날 수도 있음" = 미래 분기 불확실 | — | 선호 형식 표현 없음 = 저자 명시 | — | 예 | 프로토타입 | 실험 = 향후 과제(2019) | 이전 감사 원문 + 해법 보고서 |
| Riaño SDA | 예 | 우선순위 함수 가능, 시험은 기본값 | 가능(지식 베이스에 우선 부여) | 아니오 | 아니오 | — | — | — | — | — | — | 해법 보고서 |
| Van Woensel·Abidi CTL | 예(실행 시점 통합) | **N**(저자 명시) | N | 아니오 | 실행 분기 불확실 롤백 | — | 목표 개념 없음 = 저자 명시 | — | — | — | — | 해법 보고서 |
| Bowles 외 2019 SMT | 예(BPMN→Z3 최적화) | 아니오 | 약효·심각도·시간 겹침 | 아니오 | 아니오 | — | — | 최적화 SMT라 가중치 범위 확장 용이 [연구 가설] | 예 | — | — | 이전 감사 초록 |

### 4-2. 선호·강건 결정 계열 (B-9 중심)

| 방법 | ① | ② | ③ | ④ | ⑤ | ⑥ | ⑦ | ⑧ | ⑨ | ⑩ | ⑪ | 확인 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ROR-imprecise (Corrente·Greco·Słowiński 2012) | 아니오(대안 목록 전제) | **예**: 모든 호환 가치함수에서 필연·가능 관계 | 기준으로 넣으면 예 | 아니오 | 부분: 평가값 구간 × 선호 불완전의 곱. 두 불확실의 **출처 구분 출력은 없음** | — | 지침 상호작용, 시간 | 대안 집합을 계획기가 생성하면 됨 | 예 | LP 반복, 대안 수 n² | 이론 | 이전 감사 원문 |
| SMAA (Lahdelma 1998; Tervonen 2011 benefit-risk) | 아니오 | **예**: 가중치 분포(결측이면 균등), 순서 제약 가능. 출력 = 대안별 수용도 지수 | 예 | 아니오 | 아니오(기준값 불확실·가중치 불확실 모두 확률로 통합) | — | 확률 없는 최악 보장 | — | 예 | 몬테카를로 | 약물 benefit-risk 응용 있음 | 이전 감사(1998 원문·초록) + 2차(Tervonen) |
| Boutilier 2006 minimax regret | 제약 C로 상호작용 표현 가능 | **예**: 효용 다면체 위 MMR, 질의 | 예 | 아니오 | 아니오. **제약 C는 확정**(원문 Defn 1–3) | — | 상태 불확실(원문 범위 밖) | 적대자가 상태 s도 고르게 하면 시나리오 MMR MIP | 예 | MIP | 이론 | 이전 감사 원문 |
| Steimle 2021 다중모형 MDP | 혈압+콜레스테롤 공동 | 아니오 | 예 | **부분**: 상충하는 위험모형을 여러 모형으로 둠 | 아니오 | — | 선호 | — | 예 | NP-hard 증명 | 저자 증명 | 이전 감사 초록 |
| 일반 MILP 처방 최적화 | 제약으로 상호작용 표현 | 범위면 강건 MILP로 | 예 | 아니오 | 아니오 | — | — | — | 예 | 문제 크기 의존 | 다중질환+선호+상호작용을 MILP로 묶은 공개 사례는 검색 1회에서 못 찾음 [미검증] | 2차 |
| **Patient-centered prioritization (Schuttner 외, JAMA Netw Open 2025;8(12):e2549693)** = 기획 문서 [S5] | 다중질환 시나리오(당뇨·고혈압·CKD·우울 중 2개 이상)에서 **진료 과정 53개 순위** | 전문가 가중치(100점 배분) **평균값** 사용, 몬테카를로 5,000회로 순위 안정성(상·하위 15개만) | 기준에 "completion ease"(실행 용이성) 포함 | 기준에 "evidence quality" 포함(과정 수준) | 아니오 | 목표 영역별(수명·기능·증상) 순위표. **개인 환자 계산 아님** | 개인 선호, 지침 상호작용, 개인 적용 범위 | — | 부품(기준 가중치) | 해당 없음 | 저자 명시: 가상 시나리오, VHA 중심, 개인 목표가 다른 환자로의 일반화 한계 | 직접 원문(PMC 앞 100k자) |
| Patient Priorities Care(Tinetti) 계산화 | 임상 절차·시험은 있음 | 계산 알고리즘은 찾지 못함 | — | — | — | — | — | — | — | — | 이전 감사·이번 검색 모두 미발견 [미검증] | 2차 |

### 4-3. 근거 적용 범위·출처 보존 계열 (B-10 중심)

| 방법 | ① | ② | ③ | ④ | ⑤ | ⑥ | ⑦ | ⑧ | ⑨ | ⑩ | ⑪ | 확인 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Trial Score (Laffin 2019) | 아니오(단일 시험) | 아니오 | 아니오 | **예**: data-rich / limited / free 구역 | 부분: data-free = 근거 부족. 환자 공변량 결측 범주는 원문(요약 경유)에 없음 | — | 동반질환 조합, 다중 시험 | — | 부품 | — | — | 이전 감사 원문 |
| Seneviratne 2023 | 권고→인용 연구 연결 | 아니오 | 아니오 | **예**(Table 1 변수별 비교, 범위 밖 시각 표시) | 아니오 | — | 결합 지지 영역 | — | 부품 | — | — | 이전 감사 원문(앞 77%) |
| 전이가능성·positivity (Degtiar & Rose 2023 등) | 아니오 | 아니오 | 아니오 | **예**(IPD 필요) | 지지 영역 밖 = 근거 부족 | — | 집계표만 있는 시험 | — | 부품 | — | — | 이전 감사 원문/2차 |
| FHIR R5 Evidence | 표현 표준 | — | — | **표현 가능**: `certainty`, `variableDefinition.observed/intended`, `directnessMatch` | 표현 가능(판정 로직은 없음) | — | 계산 없음 | — | 부품 | — | — | 이전 감사 원문 |
| ATLAS (arXiv 2608.09443) | 예(고령 다약제, Beers·STOPP/START·FORTA 그래프) | 아니오 | 아니오 | **아니오**(근거·권고 등급 미사용) | **예(정보 축)**: 미확인을 미확인으로 유지, 결정을 바꿀 미해결 항목이 없을 때 질문 종료 | 정보 부족 + 상호작용만 | 선호, 근거 부족 | — | 예 | 휴리스틱 순위 | 저자 명시: 벤치마크만으로 배치 준비 입증 불가 | 이전 감사 원문 |
| PRISMATIC (arXiv 2610.19762, 2026-10) | 다중 에이전트 처방 조정(MIMIC-IV) | 초록에 없음 | 초록에 없음 | 초록에 없음 | 초록에 없음 | — | — | — | — | — | 초록만 | 초록 |

---

## 5. B-7 / B-9 / B-10 지원 수준과 동시 처리 수준

기호: ● 계산으로 처리(원문) · ◐ 부분 또는 표현만 · ○ 원문에 없음(불가 근거 아님) · ✕ 저자가 미지원 명시 · ? 본문 미확보

| 방법 | B-7 | B-9 불완전 선호 | B-9 부담·비용 | B-10 | 정보 부족 vs 근거 부족 구분 | 동시 처리 수준 |
|---|---|---|---|---|---|---|
| MitPlan 2.0 | ● | ○(점만) | ● | ○ | ○ | **B-7 + 점 B-9** |
| Wilk 2017 FOL | ● | ◐(우선순위) | ✕(2015 원문: 최적화 없음) | ○ | ? | B-7 + 순서 선호 (+미확인 상태 ?) |
| GoCom | ◐(2종) | ✕(의사 선택) | ✕(C2) | ◐(출처 표기) | ○ | B-7 |
| GLARE-SSCPM | ● | ✕(형식 표현 없음, 저자) | ◐(정성) | ○ | ○ | B-7 + 시간 불확정 |
| Fdez-Olivares HTN | ● | ○(점 가중치) | ● | ○ | ○ | B-7 + 점 B-9 |
| Čyras ABA+G | ● | ◐(preorder) | ○ | ○ | ◐(상호작용 확실성) | B-7 + 순서 선호 |
| Van Woensel·Abidi CTL | ● | ✕(저자) | ✕ | ○ | ○ | B-7 |
| ROR / SMAA / Boutilier MMR | ○(대안 목록 전제) | ● | ● | ○ | ○ | B-9 |
| Steimle MMDP | ◐(2개 위험요인 공동) | ○ | ● | ◐(상충 모형) | ○ | B-9 비용 + 근거 모형 불확실 |
| Schuttner 2025 MCDA | ◐(과정 순위) | ◐(평균 가중치 + 민감도) | ◐ | ◐(evidence quality 기준) | ○ | 집단 수준 순위, 개인 계산 아님 |
| Trial Score / Seneviratne / 전이가능성 | ○ | ○ | ○ | ● | ◐(근거 부족 쪽만) | B-10 |
| FHIR Evidence | — | — | — | ◐(표현) | ◐(표현) | 표현 표준 |
| ATLAS | ● | ○ | ○ | ✕(등급 미사용, 원문) | ◐(정보 축만) | B-7 + 정보 부족 |

**결론** [직접 원문 + 이전 감사 원문 기반 정리]: 확인 범위에서 **셋을 동시에 계산하는 단일 방법은 없음**. 가장 넓은 것은 MitPlan 2.0(B-7 + 점 B-9)과 Fdez-Olivares(같은 범위). B-10을 계산하는 방법은 모두 단일 시험·단일 결정 수준이고 지침 상호작용을 다루지 않음.

---

## 6. 결합으로 같은 출력을 만들 수 있는가 (⑨ 상세)

### 6-1. 구성 [수학적 검토]

목표 출력: 각 후보 계획에 대해 "모든 허용 선호·모든 가능 환자 상태에서 최선(강건)", "선호에 따라 달라짐 → 선호 질문 필요", "환자 정보에 따라 달라짐 → 정보 확인 필요", "근거 적용 범위 밖 → 근거가 없어 안 풀림"을 구분.

1. **계획 생성**: MitPlan형 AG-RO PDDL(또는 MILP/SMT)로 상호작용 없는 계획을 만든다.
2. **불완전 선호(가중치 범위 W, 다면체)**: 목적이 가중합 w·c(π)이면 두 계획 차이 w·(c(π)−c(π′))는 w에 대해 선형 → 다면체 위 최댓값은 꼭짓점에서 나온다. 따라서
   - π가 W의 **모든 꼭짓점에서 최적**이면 W 전체에서 최적(필연 최적). → **꼭짓점 수 k번 재실행으로 정확히 판정 가능.**
   - 반대로 "어떤 w에서 최적(가능 최적)"인 계획 전체를 꼭짓점 실행만으로 다 찾지는 못한다(최적 영역의 꼭짓점이 W의 꼭짓점이 아닐 수 있음). 가능 최적 집합은 계획 목록을 고정한 뒤 LP로 검사하거나 Boutilier MMR MIP로 구해야 함.
   - 전제: 계획기가 각 실행에서 진짜 최적을 반환해야 함. OPTIC은 metric 개선형 탐색으로 알려져 있어 시간 제한 안에서 최적 보장이 성립하는지는 [미검증].
3. **미확인 환자 정보(m개 이진 항목)**: 시나리오 s마다 초기 상태가 달라지므로 시나리오별 실행이 필요 → 최악 2^m × k번. 또는 시나리오를 적대자 변수로 둔 min-max regret MIP(이전 Gate 0 A의 정리) 한 번.
4. **근거 적용 범위**: RO·권고마다 FHIR `directnessMatch` 또는 Trial Score 구역 표지를 붙이고, "환자 정보를 더 얻어도 표지가 바뀌지 않는" 항목을 근거 부족으로 분리. 이 분리는 **"어떤 정보 질문에도 판정이 안 바뀌는가"를 시나리오 전체에서 검사하는 것**과 같아 3과 같은 열거 구조로 계산된다 [수학적 검토].

→ 판정: **조합으로 같은 형태의 출력이 나온다.** 새 계산 원리는 필요하지 않아 보임 [연구 가설]. 이 결론은 이전 Gate 0 A 감사(JNP·MDQ NO-GO)와 같은 방향임.

### 6-2. 조합으로도 막히는 곳

| 막힘 | 성격 | 근거 |
|---|---|---|
| 질환 조합별 근거 적용 범위 데이터가 없음(대부분 시험이 복합질환 제외) | **지식·데이터** | 이전 감사(Weiss 2014, Hanlon 2019) [이전 감사 초록] |
| RO·상호작용 지식 구축 부담 | 지식 공학 | Fdez-Olivares 저자 명시 [이전 감사 원문]; MitPlan A3·A7 "assuming it knows how to mitigate" [직접 원문] |
| 선호 범위 W를 어떻게 정하나(임의 범위 → 결과 조작 위험) | 도출·검증 | 기획 문서 질문 4와 동일. 기존 방법은 범위가 **주어졌다고 가정** |
| 독립 정답 없음 | 평가 | 벤치마크가 계획 출력만 비교, 정확도 지표 없음 [직접 원문, MGCDS] |
| 2^m 시나리오 폭발 | 계산 | [수학적 검토]. **실제 측정한 문헌은 찾지 못함** |

### 6-3. MitPlan 대비 "구체적 반례" 후보 (기획 문서 체크리스트 항목에 대한 답)

[수학적 검토, 원문 기능 기준. 실행 재현은 코드 미공개로 불가]

- **반례 A(선호 범위)**: 환자가 "부담이 비용보다 중요"라고만 말함(w_burden ≥ w_cost, 정확한 값 미확인). 두 계획 π1(와파린: 비용 낮음·부담 높음), π2(DOAC: 비용 높음·부담 낮음). MitPlan 2.0은 가중치 한 점을 넣어야 하므로 한 계획을 "최적"으로 냄. 범위 안에서 순위가 바뀌는지는 출력에 나타나지 않음. → 원문 기능상 **한 번의 실행으로는 표현 불가**, 꼭짓점 재실행으로는 판정 가능(§6-1).
- **반례 B(미확인 상태)**: eGFR 미측정. MitPlan 2.0 입력은 `patientValue` 수치가 필요(Fig 15). 값을 넣지 않으면 어떻게 동작하는지 원문에 없음 → [미검증]. 임의 기본값을 넣으면 "없음"으로 채우는 것과 같은 위험(이전 감사 GuidelineForge 207/4,304쌍 오판 사례 [이전 감사 초록]).
- **반례 C(근거 범위)**: RO "PCB→SCB 대체"(CKD+AF)의 근거가 CKD 4기 환자를 제외한 시험에서 왔을 때. MitPlan 2.0은 RO에 근거 출처·적용 범위 필드가 없음 → 출력에서 구분되지 않음.
- 주의: A는 "간단한 확장(재실행 루프)"으로 해결되므로 **신규성 근거가 되기 어려움**. B·C는 표현 확장 + 지식 입력이 필요.

---

## 7. 처리 가능 범위 / 미검증 범위 / 확보 수준

### 7-1. 기존 방법으로 처리 가능 (근거 있음)

- 다중지침 상호작용 탐지·완화(대체·삭제·추가·용량·모니터링·지연·가교), 시간 겹침 — MitPlan 2.0 [직접 원문], GLARE·TMR4I·GoCom [이전 감사 원문]
- 점 선호·부담·비용·비순응의 가중합 최적화 계획 — MitPlan 2.0 [직접 원문], Fdez-Olivares [이전 감사 원문]
- 불완전 선호의 필연·가능 판정, minimax regret, 수용도 — ROR·Boutilier [이전 감사 원문], SMAA [이전 감사 + 2차]
- 개인 환자의 시험 적용 범위 구역 판정 — Trial Score [이전 감사 원문]
- 근거 확실성·간접성 표준 표현 — FHIR R5 Evidence [이전 감사 원문]
- 미확인 정보를 미확인으로 유지하고 결정이 바뀔 때만 질문 — ATLAS [이전 감사 원문]

### 7-2. 미검증 범위

- MitPlan AIIM 2021·AIME 2021 논문 본문의 목적함수 정의, 선호 형식, 초기 상태 결측 처리(보고서와 다를 가능성)
- Wilk 2017 "possible patient states"의 의미(열거 vs 가정값)
- MitPlan에 미확인 값을 넣었을 때의 실제 동작, OPTIC 최적성 보장, 실행 시간
- 2023 그래프 재작성의 수정 규칙이 확률·근거 속성을 갖는지
- Van Woensel 2023 논문 본문의 6개 방법 비교 결론(공개 자료만 봄)
- Patient Priorities Care를 최적화 알고리즘으로 만든 연구 존재 여부(검색 1–2회)
- MILP로 다중질환+상호작용+선호를 묶은 공개 사례

### 7-3. 원문·코드·데이터 확보 수준

| 대상 | 원문 | 코드 | 데이터 |
|---|---|---|---|
| MitPlan 2.0 | **저자 기술 보고서 전문** (논문 본문 아님) | 미공개(PDDL 조각만 그림) | 벤치마크 4사례 서술·지침 PDF 공개(MGCDS) |
| MitPlan 1 / Wilk 2017 / 2023 / 2024 | 초록 | 없음 | — |
| GoCom·GLARE·Riaño·Marcos·Van Woensel 팀 | 해법 보고서(자기 보고) | Van Woensel 팀 OWL/TTL 일부 공개 | MGCDS |
| ROR·Boutilier·Golovin-Krause | 이전 감사 원문 | 일반 LP/MIP로 구현 가능 | — |
| SMAA | 2차 | JSMAA·R smaa 공개(2차 정보) [미검증] | — |
| Trial Score·Seneviratne | 이전 감사 원문 | [미검증] | — |
| ATLAS | 이전 감사 원문 | [미검증] | GeriMedBench(이전 감사) |
| Schuttner 2025 | 직접 원문(PMC 앞 100k자) | 없음 | 보충 자료 [미검증] |

---

## 8. 다른 서브에이전트에 넘길 점

- **C(정식화)**: §6-1의 "가중합 + 다면체 → 꼭짓점 재실행으로 필연 최적 정확 판정, 가능 최적은 불완전"을 기준선(baseline)으로 써야 함. 이것을 넘지 못하면 B-9 쪽 신규성 주장 불가.
- **D(실험)**: MitPlan 공식 코드가 없으므로 "MitPlan 대비"라고 쓰면 안 됨. "MitPlan 2.0 보고서의 기능 명세(AG-RO + 고정 가중합 + 점 환자 값 + 계획 1개)를 따른 재구현 기준선"으로만 표기. 벤치마크 Case 2(AF+HTN+CKD, DOAC 선호)는 공개 자료라 공통 사례로 쓸 수 있음.
- **E(레드팀)**: "MitPlan은 불확실성을 못 다룬다"고 쓰면 Wilk 2017 초록("possibly incomplete", "possible patient states")으로 반박당할 수 있음. 정확한 표현은 "MitPlan 2.0 저자 보고서에는 미확인 환자 값·선호 범위·근거 적용 범위 처리 서술이 없다".
- **기획 문서 수정**: [S2] 저자명 Piovesan → Michalowski M, Wilk S, Michalowski W, Carrier M.
