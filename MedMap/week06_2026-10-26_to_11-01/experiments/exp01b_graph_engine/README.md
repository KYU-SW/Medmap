# EXP-01b 의료 관계 그래프 추론 엔진 — 최소 구현 (2026-10-29, 탐색 단계)

- 위치가 `exp/main_ai` 밖인 이유: EXP-01 실행 잠금 해시가 `exp/main_ai/**/*.py` 전체를 덮음(`lockhash.run_lock_hash`). 그 안에 .py 를 추가하면 EXP-01 코드 동결이 깨짐.
- RG 미등록: 성능 평가·주장 없음, 가상 사례 구현 검증만. 본격 비교는 별도 사전등록(rg-plan → rg-gate) 필요.
- 실제 환자 진단·성능 주장 없음. 환자는 모두 가상.

## 파일
| 파일 | 내용 |
|---|---|
| `graph_engine.py` | 그래프(MedGraph)·환자 근거(EvidenceRecord/PatientRecord)·조건 평가·infer·의사 진단 비교·재계산 세션 |
| `knowledge_real_hsdn.py` | REAL: HSDN 증상–질환 문헌 공출현(5질환·8증상·공출현 ≥10, 28간선) |
| `knowledge_toy.py` | TOY: 구조 시험용 가상 관계(AND/OR·적용 조건·범주·수치·반박·위험인자·검사·의존) |
| `report_ko.py` | 결과 객체 → 한국어 보고·JSON |
| `demo.py` | 가상 사례 시연(입력 → 비교 → 새 근거 → 재계산·재활성화) |
| `tests/test_engine.py` | 필수 테스트 23 |
| `tests/mutation_check.py` | 핵심 성질 변이 12(대조 사본 통과 확인 후) |
| `tests/exp01_main_ai_sha256_before_exp01b.txt` | 작업 전 exp/main_ai 파일 SHA(보존 확인용) |

## 재사용
`exp/main_ai/common/evidence_graph.py`(수정 없음, import): `Status` 5상태, `RuleState`, `Observation`, `PatientGraph`(append-only·`view(as_of)`).
설계 원칙은 `exp00_readiness/graph_design.md` §2·§3 그대로.

## 실행
```bash
cd ~/medmap-worktrees/main-ai/exp/exp01b_graph_engine
~/ai_env/bin/python -B -m unittest discover -s tests -v      # 23 tests
~/ai_env/bin/python -B tests/mutation_check.py <임시폴더>      # 12 mutants
~/ai_env/bin/python -B demo.py                                # outputs/demo_<시각>/
```

## 한계
- REAL 지식 = HSDN 공출현만(연관, 확률 아님). 검사·위험인자·AND/OR 진단 규칙·반박·근거 의존 관계는 실제 출처 없음 → REAL 그래프에서 충돌 판단은 "근거 부족".
- HSDN 은 흔한 증상이 5질환 대부분에 연결돼 질환 간 구분력이 약함(B-2 에서 심근경색 현재 진단 시 설명 부족 근거 0).
- 정렬 키 = 독립 지지 묶음 수. 확률·우도 결합 없음. 나이·성별은 보존만, 연결된 지식 없음.

## 34회차(2026-10-29) — 실제 의료 지식 + DDXPlus 환자 입력 연결
| 파일 | 내용 |
|---|---|
| `knowledge_real_kg.py` | `build_real_graph`(HSDN + DisMech + HPO 계층), `disease_link_audit`(DDXPlus 49 → HSDN CUI·DisMech 라벨), `load_hpo`, `load_cui2hp`(UMLS MRCONSO SAB=HPO) |
| `ddxplus_adapter.py` | `build_mapping`(223 근거 매핑 상태), `case_records`·`split_phases`·`patient_from_case`(EVIDENCES 양성만, 없는 근거는 미기록) |
| `extract_dev_cases.py` | TRAIN16(EXP-01 HOLDOUT 제외, 분할 수 STEP16B 와 일치 검증)에서 4질환 × 2 사례 |
| `demo_real.py` | 실제 그래프 × 개발 사례 시연(1단계 첫 증상+병력 → 2단계 추가 답변) |
| `tests/test_real.py` | 실제 연결 테스트 9 |
- 엔진 확장(인터페이스 유지): 관계 `IS_A`(하위 양성 ⇒ 상위 양성 유도, 같은 근거 묶음)·`EVALUATES`·`DIFFERENTIAL_OF`, `PathEval.evidence_class`, 같은 노드 쌍의 지식원별 경로 ID 분리(`#evidence_class`), 설명 부족 분류 `NARROWER_CONCEPT_LINKED`, `WDAssessment.tests_available`, `render_ko(compact=True)`.
- 선택 질환: 폐색전증·심낭염·심근염·결핵(DDXPlus–UMLS CUI–HSDN ID 일치 + DisMech MONDO 라벨 일치; MONDO 교차참조 파일은 로컬에 없음).
- 실행: `~/ai_env/bin/python -B extract_dev_cases.py --out outputs/dev_cases_<시각>` → `~/ai_env/bin/python -B demo_real.py --cases outputs/dev_cases_<시각>/dev_cases.json`
- 결과: `outputs/real_demo_20261029_151218/`(보고서·결과 JSON·kg_meta·223 매핑 CSV·질환 연결 감사 CSV).

## 35회차(2026-10-29) — 연결 정확성 개선
- `ddxplus_adapter.py`: `OVERRIDES`(사람 재판정 13, 사유 포함) · `ANTECEDENT_REVIEW`(4질환 관련 병력 8 = NO_KB_RELATION) · OR 복합·여러 개념 질문은 REVIEW · 수식어 단독은 REVIEW · `negative_ok`(같은 개념 EXACT 단일만 음성 사용, 상위 개념 연결은 양성 방향만) · 값 규칙(척도 0 = 없음, Y/N 의 N = 아니오, E_57 'nowhere' = 방사통 명시적 음성) · `answer_records`(양성·음성·불확실 답 공통 변환).
- `knowledge_real_kg.py`: `verify_quote`·`evidence_class`(DisMech 인용문 ↔ 로컬 PubMed 초록 캐시 대조 → DISMECH_QUOTE_IN_ABSTRACT / PMID_QUOTE_UNVERIFIED / NO_REF; 인용 일치 ≠ 내용 검증) · 질환 자체 개념 소견 제외(심근염 HP:0012819) · 간선 `role`(CLINICAL_FINDING / LITERATURE_COOCCURRENCE / RISK_FACTOR / TEST_INFORMATION / DIFFERENTIAL / ONTOLOGY_HIERARCHY; 진단 규칙·반박 0).
- `graph_engine.py`: `GRADE`·`DiseaseEval.group_grades`·`n_clinical`·`n_cooccurrence_only` · `Inference.ranking(key="graded")` · 추가 검토 이유에 임상/공출현 구분 · 현재 진단 자신을 추가 검토 후보에서 제외.
- `compare_runs.py`: 수정 전 모듈(보관본)과 현재 모듈로 DEV1–8 비교. `tests/test_accuracy.py`(7).
- 결과: `outputs/real_demo_20261029_1911/` · 비교 `outputs/compare_35_20261029_1911/compare_report_ko.md`. 이전 결과 `real_demo_20261029_151218/` 은 E_57 'nowhere' 오류 포함(보존).

## 36회차(2026-10-29) — 첫 소규모 성능 탐색 실험(EXPLORATORY)
- `explore1.py`(select: 사례·조건·지표·코드 SHA 고정 → run: SHA 일치 시만 계산) · `explore1_posthoc.py`(결과 확인 후 추가한 기준선·1위 쏠림 분석, POST-HOC 표시).
- 결과 `outputs/explore1_20261029_2232/{protocol.json, cases.json, rows.csv(600), summary.json, report_ko.md, pe_miss.json, posthoc.json}`.

## 37회차(2026-10-29) — 판별력 개선 1차
- 매핑: E_220 = 흡기 악화 + 흉부 부위 + 통증 성질(칼로 베는 듯·타는 듯·날카로움) → 흉막성 흉통(HP:0033771) · E_151+E_152 사지 부위 → 사지 국소 연부조직 부종(HP:6000840, Edema·DVT 로 연결 안 함) · E_54 단독 = 수식어(NO_CONCEPT) · E_33 = HPO 용어 없음(NO_CONCEPT). 음성: E_220·E_151 은 필수 성분 부재로 음성 사용.
- `discrimination.py`: spec 정렬(묶음별 1/연결 질환 수, DisMech 만 S_clin, HSDN 은 S_all) · WD 4분류(A 지지 / B 다른 질환만 연결 / C 지식 부족 / D 검증 반박) · `report_ko` 에 4분류 표시.
- `explore2.py`: 새 100명(explore1·개발 제외), 팔 3(OLD_GRADED = archive/exp01b_explore1_modules, NEW_GRADED, NEW_SPEC). 결과 `outputs/explore2_20261029_2306/`.
- 테스트 43(+ test_discrimination 3, test_accuracy 복합 1).

## 38회차(2026-10-30) — 질환 판별 의료 지식
- `knowledge_discriminators.py`: 판별 관계 10(적용 9, 미적용 1 = PE D-dimer 배제 규칙: 인용 미확인) · 새 개념 노드 9(HPO 용어 없음, 정의·출처 포함) · 인용은 DisMech references_cache 와 자동 대조.
- 엔진: 결합 `ATLEAST:k`(4 중 2 기준) · 잎 spec `negative_uninformative`(지식원이 음성 무정보 명시) · 규칙 경로에 근거 등급·rule_type 표시 · 등급 `LITERATURE_QUOTE_IN_TEXT`(3).
- `build_real_graph(discriminators=True)` 일 때만 추가(기본 꺼짐). 어댑터: E_33(+흉통 복합) → 앞으로 숙이면 완화되는 흉통, E_2 → HIV 감염.
- `kb38_report.py` → `outputs/discriminators_<시각>/{discriminator_relations.csv, summary.json, virtual_cases_ko.md}`. 테스트 49(+ test_discriminators 6).
- explore2 시점 모듈 보관: `~/medmap-worktrees/main-ai/archive/exp01b_explore2_modules/`(protocol SHA 6/6 일치).
