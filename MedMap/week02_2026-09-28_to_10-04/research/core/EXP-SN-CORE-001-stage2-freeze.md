# EXP-SN-CORE-001 Stage 2 고정 기록 (deviation-14, 2026-10-02 22:0x KST, 실행 전)

사용자 지시(2026-10-02 21:4x): "A2·A2′ 질문 사전 대응과 검증 B의 prompt/script/allowlist를 먼저 동결하고, Stage 1 결과나 evaluability를 유리하게 만들기 위한 규칙 변경은 하지 마. RG 재심사에서 RUN을 받은 뒤에만 Stage 2를 실행해. Stage 2 후 사전 규칙상 ACS–PE가 NOT_EVALUABLE이면 그대로 판정하고, corpus 확장·기준 완화·fact 추가로 구제하지 마."

이 문서의 모든 값은 Stage 2 첫 호출 전에 고정한다. RUN 후 바꾸려면 새 deviation + 재심사.

## 1. 작업과 순서
| 작업 | 모델(기대 ID) | 입력(작업별 Read 허용) | 출력(Write 허용) | 대상 |
|---|---|---|---|---|
| A2a | opus `claude-opus-5-5` | EVQ.c01–c04 + FACTS_A2a.c01 | `stage2/out/A2a/A2a.part01–30.jsonl` | A1b1 대응 대상 fact 119 |
| A2b | opus | EVQ.c01–c04 + FACTS_A2b.c01–c02 | `stage2/out/A2b/…` | A1b2·A1b3 대응 대상 fact 143 |
| A2alt (A2′) | sonnet `claude-sonnet-5-5` | EVQ.c01–c04 + FACTS_A2alt.c01 | `stage2/out/A2alt/…` | SAMPLE20 단위의 대응 대상 fact 60 |
| Ba | opus | B_Ba.cNN(빌더가 A2 후 생성) | `verify/out/Ba/…` | A1b1 fact 160 전부 |
| Bb | opus | B_Bb.cNN | `verify/out/Bb/…` | A1b2·A1b3 fact 179 전부 |

- 순서: A2a·A2b·A2alt 동시 시작 → **A2 3개 모두(A2alt 포함) 최종 상태 확정**(채택 CLEAN, 또는 try2까지 non-CLEAN이면 실험 INVALID로 즉시 종료 — B·binputs 미실행) → `stage2_build.py binputs`(운영자가 A2alt 포함 3개 postcheck CLEAN 확인 후에만 실행, runner v3가 B 시작 전 A2a·A2b·A2alt CLEAN 기계 확인) → Ba·Bb 병렬 → `ckv0` → `kappa2` → `precount`(사전 집계 판정) → 사용자 보고·멈춤
- 호출 계획 = 기준 9(A1 3·A1alt 1·A2 2·A2′ 1·B 2)와 동일(A2 2 = A2a·A2b, B 2 = Ba·Bb). 현재 6/14 사용, Stage 2 기본 5 → 11/14, 재실행 여유 3. 누적 정가 환산은 runner가 **각 시도 시작 전** ≤ $40인지 확인(실행 중 세션 비용은 완료 후 합산, 병렬 시작분은 초과 가능 — 초과 확인 시 이후 호출 중단·재보고; 추정치, 청구액 아님). 호출 수는 진행 중 세션(빈 result.json)도 세어 14 초과 시작 불가
- "A2′ = 동결 A1 fact의 같은 20% 표본"(manifest) = SAMPLE20 단위(509, Stage 1 kappa와 같은 표본)에 속한 A1 fact 중 대응 대상 relation 60개

## 2. 입력 구성(빌더 `scripts/core/stage2_build.py inputs`)
- Stage 1 채택 산출물(A1b1 try2·A1b2 try2·A1b3 try1, `STAGE1_OUT_SHA256SUMS` 검증) 병합 → `docs/research/core/ck-v0/stage1_facts.jsonl`(339, fact_id 유지). quarantine try1 미사용
- **질문 발췌본 EVQ**(release_evidences.json SHA 281c78b0…e0c0, 223 evidence): manifest 발췌 규칙대로 question_en·data_type·possible-values·value_meaning(en)만. 줄 = 질문 1행 + 선택형 값 1행씩(923줄, 4조각, 최장 671자). 의미 없는 숫자 척도(C형, value_meaning 없음)는 "not mappable" 표기. AGE·SEX 의사 id 2행(manifest "AGE·SEX 위험인자는 의사 id AGE/SEX + 구간·값"). 질환→소견 정보 없음(육안: 과거력 질문 중 pilot 질환명 포함 3줄 E_3 pericarditis 과거력·E_105 heart attack/angina 과거력·E_109 DVT 과거력 — 질문 문구일 뿐 질환 조건표 아님). code_question(부모)·is_antecedent·default_value·question_fr는 넣지 않음(발췌 규칙 밖). release_conditions.json 미열람
- **A2 fact 입력**: 대응 대상 relation = SUPPORTING·POORLY_EXPLAINED·IMPORTANT_NEGATIVE·OVERLAPPING·DIFFERENTIATING(262). TEST_REQUIRED(55)·OUT_OF_SCOPE_WARNING(22)는 evidence_id = null(manifest)이라 A2 입력 제외. 행 필드 = fact_id·relation·finding_kind·finding_text·finding_value·quote. **질환·favors·direction·출처는 A2에 주지 않음**(질환 조건부 대응·시뮬레이터 기억 개입 억제; quote 안 질환명은 원문이라 남음 — 한계). relation은 IMPORTANT_NEGATIVE 대응 규칙 때문에 제공
- 조각 규칙(deviation-12 유지): ≤45,000바이트·≤250줄·줄 ≤1,900자

## 3. A2 대응 규칙(프롬프트 `stage2/prompts/A2.template.txt` → A2a·A2b·A2alt 렌더)
- evidence_value 문법(manifest): B형 POS|NEG · 선택형 VALUE::값ID · AGE RANGE::lo-hi(정수 0–120, 양끝 포함) · SEX VALUE::M|F
- 서술 상태 그대로: present/구체 값 → 있는 상태, absent → B형 NEG만(선택형 absent 대응 없음)
- IMPORTANT_NEGATIVE = "보통 있어야 하는 소견" 정의이므로 finding_value와 무관하게 있는 상태로 대응(엔진 U_neg의 "w에서 기대되는 값")
- 같은 뜻일 때만, 의학 지식 추론 금지, 같은 뜻 값 여러 개면 모두, 숫자 척도 대응 금지(근거 없는 임계 방지), AGE는 숫자 명시 시만
- 출력 1 fact 1행, part ≤40행·≤30파일·덮어쓰기 금지

## 4. 검증 B 규칙(템플릿 `verify/prompts/B.template.txt` SHA f24454ec…2b95, 렌더는 `binputs`)
- B 입력 = fact 전 필드(질환·relation·favors·quote 포함) + 기계 검증 통과 A2 대응(질문 문구·값 뜻 인라인). A2의 reason 문장은 주지 않음. EVQ 전체·A1 원본·단위 원문은 주지 않음(인용 대조는 기계)
- 판정: fact_verdict(quote가 질환·relation·favors·소견·값을 직접 말하는가), test_type_verdict(TEST_REQUIRED만), mapping_verdicts(MAP별 같은 뜻인가, IMPORTANT_NEGATIVE는 있는 상태가 정답). 추가·수정 금지
- 렌더 변수 3개(작업명·입력 파일 목록·출력 파일 예시)만 치환, 렌더 결과·B 입력 SHA = `verify/B_SHA256SUMS`(runner가 실행 전 `sha256sum -c` + 템플릿 SHA 대조)

## 5. 기계 처리 규칙(빌더 고정, A2·B 산출물을 보기 전)
- A2 기계 기각: 목록에 없는 evidence_id(UNKNOWN_EVIDENCE_ID), 허용 값 밖(BAD_VALUE), 숫자 척도(SCALE_NO_ANCHOR), AGE 범위 형식 오류, 입력에 없는 fact_id·JSON 오류, 같은 fact 중복 행(그 fact 전부 기각, A2_DUPLICATE_ROW), 누락 행(A2_MISSING_ROW → 대응 없음)
- ck-v0 채택 = 인용 기계 대조 일치(part 표식 제거·공백 정규화 후 단위 v2 본문 연속 부분 문자열) ∧ 스키마 유효 ∧ B fact ACCEPT(∧ TEST_REQUIRED면 test_type ACCEPT). B 행 누락·중복 → 기각
- 대응 행 = A2 기계 통과 ∧ B MAP ACCEPT. IMPORTANT_NEGATIVE의 NEG 기대값은 기각(IN_EXPECTED_NEG). 채택 fact 중 채택 대응 0이면 evidence_id = null(mapped=false, 엔진 match 불가)
- 기각 전부 `rejected.jsonl`, 인용 대조 `citation_check.json`, A2 원 대응 `stage2_mapping_a2.jsonl`
- kappa 2단계(사전 고정, 판정 미사용): SAMPLE20 대응 대상 fact 60, 범주 = (evidence_id, 값) 집합 완전 일치(NONE 포함) Cohen, 단위 bootstrap 2,000 PCG64 20261002. **A2alt도 다른 작업과 같은 위반 규칙**(deviation-14c, gate 11 MAJOR 2): try2까지 non-CLEAN이면 실험 INVALID(manifest failure_criterion "작성 transcript 허용 목록 위반 = INVALID", deviation-11b·12b와 동일). kappa만 빼고 진행하는 완화 없음. ck-v0에는 A2alt 미사용

## 6. 사전 집계 규칙(`precount`, manifest "[사전 집계] U 가능 evidence 0 → NOT_EVALUABLE"의 계산 정의)
- 방향 = 정답 범주 a, WD w = 쌍 상대. 관측 가능 evidence = DDXPlus evidence(E_134·E_152 제외) + AGE·SEX
- U_pos 가능 e: e에 (POORLY_EXPLAINED(w) ∨ DIFFERENTIATING favors=a) fact와 a-support(SUPPORTING(a) ∨ OVERLAPPING(쌍) ∨ DIFFERENTIATING favors=a) fact가 있고 같은 관측에서 함께 match 가능(B·단일 선택 = 같은 값, 다중 선택 M = 항상, AGE = 구간 겹침)
- U_neg 가능 e: IMPORTANT_NEGATIVE(w) fact가 e에 있고 관측값이 기대값과 다를 수 있음 ∧ 쌍에 a-support fact ≥1(사례 수준 조건의 필요조건)
- **해석 고정(모호성 해소)**: 쌍·방향별로 센다. **어느 한 방향이라도 0이면 primary NOT_EVALUABLE.** m 후보 = {1,2,3} ∩ ≤ 두 방향 최소. AGE·SEX만으로 된 U 가능 수는 별도 표기
- **효과(정정, gate 11 MAJOR 1)**: PILOT_SIGNAL_PRESENT 가능성은 두 해석(방향별 / 쌍 합계)에서 같다(0인 방향은 Core-K 경고 구조적 0). 그러나 **판정 라벨은 같지 않다**: 쌍 합계 해석이었다면 TUNE ②(C 정의 불가 → NOT_FEASIBLE)가 ③보다 먼저 성립할 수 있는데(0인 방향 FPR 구조적 0, 남은 방향 FPR > 0.20), 방향별 해석은 그 NOT_FEASIBLE 가능성을 사전 집계 NOT_EVALUABLE로 미리 막는다. 반대로 m 상한(≤ 두 방향 최소)은 일부 경계 사례를 ③ NOT_EVALUABLE에서 ② NOT_FEASIBLE로 옮긴다. 이전 문구 "판정 결과는 두 해석에서 동일"은 틀렸으므로 철회
- **보고 문구 고정**: 사전 집계 NOT_EVALUABLE이면 "판단 보류"가 아니라 **"ck-v0 구조상 해당 방향 Core-K wrong-WD 탐지율 0 확정(음성 결과) — 이 pilot의 ACS–PE 쌍에서 출처 fact 기반 재검토 신호는 한 방향 이상에서 구조적으로 불가능"**으로 쓴다
- **운영자 사전 인지 공개**: 이 해석을 정한 운영자(메인 세션)는 Stage 1 기계 집계를 이미 알고 있었다 — HANDOFF v11 §1·§5-11(`~/medmap/.claude/handoff/HANDOFF_MASTER.md`): ACS~PE 쌍 fact 7 중 병력 1(OVERLAPPING), 병력 DIFFERENTIATING 0, PE POORLY_EXPLAINED 병력 0, ACS POORLY_EXPLAINED 병력 4. Stage 2 대응 결과는 모름
- 사전 집계는 엔진 U보다 넓게 세는 상한(필요조건)이다(can_differ: M형 항상 참, 부모 질문 조건 미반영). 실질 판정은 TUNE ③. 엔진 동결 시 "엔진 U ⊆ precount U 가능 집합" 단위 테스트 필수
- 판정은 Stage 2 산출물 그대로 1회 계산. NOT_EVALUABLE이면 그대로 보고·멈춤. corpus 확장·기준 완화·fact 추가·재작성·재대응·규칙 변경으로 구제하지 않음(사용자 지시)

## 7. 실행·검사(runner `~/medmap_core_kb_runner/run_stage2.sh`)
- 격리 CLI 명령·환경 = Stage 1과 동일(`ENABLE_CLAUDEAI_MCP_SERVERS=false claude -p --restricted --strict-mcp-config --tools Read,Write --permission-mode acceptEdits --model <m> --output-format json`)
- 실행 전 runner 기계 확인: 검사기 SHA 034d8114…a22b(변경 없음, deviation-13 정확 일치 예외 포함) · 빌더 SHA · `stage2/STAGE2_SHA256SUMS`(입력 8조각 + 프롬프트 4 + 템플릿) · B는 `B_SHA256SUMS`·템플릿 SHA·A2a·A2b CLEAN · 호출 < 14 ∧ 누적 정가 환산 ≤ $40(Stage 1 포함 전 시도) · out 폴더 비움
- 실행 직후: transcript 검사(작업별 허용 목록·기대 모델) + `postcheck`(Stage 1 runlog §0-3 운영자 점검의 기계화: 같은 경로 Write ≥2·part30 존재·compaction·result is_error·exit ≠ 0) → 최종 CLEAN일 때만 산출물 열람
- 위반 처리(deviation-12b·13 유지): MODEL_MISMATCH·429·CLI 오류 → 중단·deviation·재심사 / 그 밖 non-CLEAN → 미열람 격리(quarantine/<job>.try1, SHA·쓰기 금지) 후 try2 1회 / try2 non-CLEAN → 실험 INVALID. try3 없음. 새 attachment 유형·문구 변형 사후 허용 없음
- 합성 대조(`~/medmap_core_kb_runner/syn_stage2.py`, 결과 `~/medmap_core_kb_preflight/stage2_syn/result.txt`): 음성 5(작업별 전체 완독·자기 출력) 전부 CLEAN, 양성 9(다른 작업 입력 읽기·Stage 1 산출물 읽기·부분 Read·다른 작업 출력 쓰기·part31·B가 A2 원 출력/EVQ 읽기·모델 불일치·작업 폴더 밖) 전부 INVALID → ALL_PASS. 빌더 합성 시험(scratchpad, 실제 산출물 미생성): A2 누락·척도·B 기각·IMPORTANT_NEGATIVE NEG·kappa·precount 경로 동작, postcheck 5종 기대대로

## 8. 고정 SHA(2026-10-02)
```
daec2177a2443b79aa80ca208c6850ae67c93e9b97d195c98e4417c53e542bb3  scripts/core/stage2_build.py
034d811402234672d7fd7a93a21ac21040507d4174e8c7e7713c57ff1147a22b  scripts/core/transcript_scan.py
24804999d249e3144e6fff83d75abdbcdd7efdfea5e4fc8a813c90f6075c3cb2  docs/research/core/ck-v0/stage1_facts.jsonl
9b088b9b2259e71f9ecc3ace819d4093fa1a69767c7bda59190c95e06bc584f6  ~/medmap_core_kb_ws/stage2/STAGE2_SHA256SUMS
f24454ec80ee10f80914f3dda2546120b81cd0b281dc26024611ec3ed47f2b95  ~/medmap_core_kb_ws/verify/prompts/B.template.txt
b8874d43a2afa87756be8352eef0f7509e1e31521337b9a38fde5eb0971b9ea9  ~/medmap_core_kb_runner/jobs_stage2.json
fb75ef945e20750b0e71a468321ee3ef9e5ad2266d2eef997457035921c5b60e  ~/medmap_core_kb_runner/run_stage2.sh (v1, deviation-14c로 대체)
e4d21032110d6e6a566973f0e8d9d7561d4e8d2d534a27523f38e67ad9e67b50  ~/medmap_core_kb_runner/run_stage2.sh (v2, 현행)
281c78b044ae60514e28ecc9052d08a8225dd3e2db3f00f8788b99c47b05e0c0  ~/medmap/data/ddxplus/en/release_evidences.json
```
STAGE2_SHA256SUMS 내용:
```
47eefcdd22571c87806796a2d66433ef9d7a3386cc09d3651a04bda03d7650a5  input/EVQ.c01.txt
ac43c133267814302e65d31ac84bd2566aceff0ad9ad97294bbc20eb24cb0885  input/EVQ.c02.txt
9a66a4423579796c066c39037b0fb6ebb9a784ae8d030770af29026b8acb529b  input/EVQ.c03.txt
6d8617c89b163a36bf29c91ffc151bb61c8ea21aaf061495ea45be8a2a9b8eea  input/EVQ.c04.txt
3765ea34896631e44c203df7392222b97aac7644c07c8aa8830f3f272abd0d4f  input/FACTS_A2a.c01.txt
9683f049c78d3eeb5d8ae0965dbb2d0aa2d3ea37449817cad01c4d323d470dc2  input/FACTS_A2alt.c01.txt
1f19030ccaaef258767156c261c3d994cccf686ba7992295216cd620039bd29e  input/FACTS_A2b.c01.txt
8cc9ab91948d6278617f19ce3a92e146f03a95163f7b4442074a0dcf3b5d9346  input/FACTS_A2b.c02.txt
720f176d1188b22a88d637757dcbd4ad09decfe41e93eeed2baf2db33cde0780  prompts/A2.template.txt
efc0a6e3ff5e11006c221105e36916d293c10c3a570b35068b82097e1c77765d  prompts/A2a.prompt.txt
434e3d50dac8c694a7f2beaec35296104170bcbba2370d706dac18ee14665902  prompts/A2alt.prompt.txt
1428a311b78a99807f6934fd9142d667c0c1c7c1a43e74782bbbda4a97217c83  prompts/A2b.prompt.txt
```
(첫 생성본은 빌더 표기 수정 전 생성 → `~/medmap_core_kb_preflight/stage2_v0_superseded/`로 이동, 고정 빌더로 재생성한 결과 SHA 동일 확인)

## 9. 추가 고정(deviation-14c, gate 11 반영, 실행 전)
- runner v2(`run_stage2.sh` e4d21032…7b50, v1 fb75ef94 보존 `~/medmap_core_kb_preflight/run_stage2.v1_fb75ef94.sh`): (1) 상한 검사가 진행 중 세션의 빈 result.json에서 오류로 멈추던 문제 → 빈 파일도 호출로 세고 비용은 읽히는 것만 (2) try2 조건 판정을 try1 격리 이동 **전**에 수행(CLEAN try1이 봉인되는 실수 방지) (3) A2 허용 목록 파일 SHA b8874d43 확인, B 허용 목록은 모든 경로가 존재하고 B_SHA256SUMS에 있는지 확인. 빌더·검사기 무변경
- 입력·프롬프트·템플릿·허용 목록 파일 쓰기 금지(`chmod a-w`, SHA 불변). binputs 전 `sha256sum -c STAGE2_SHA256SUMS`, ckv0 전 `sha256sum -c B_SHA256SUMS` 수동 확인 기록
- 병렬 실행: A2 3개·B 2개를 한 명령으로 동시에 띄운다
- 검증 B는 TEST_REQUIRED에도 fact_verdict ACCEPT를 요구(manifest "quote 대조·test_type 도출만"보다 엄격, 판정 미사용 항목)
- **엔진 규칙 명확화(ck-v0 열람 전 고정, deviation-14e 식)**: 행 = ck-v0 대응 행 (fact f, e, v). match(행, view) = v ∈ view[e](manifest match 정의). 대안 a·WD w·사례 view에 대해
  - a-support(e) = ∃ a-support fact(SUPPORTING(a)·OVERLAPPING(쌍)·DIFFERENTIATING favors=a)의 행 (e, v) 중 match
  - U_pos = { e : ∃ POORLY_EXPLAINED(w) 또는 DIFFERENTIATING favors=a fact의 행 (e, v) match ∧ a-support(e) }(같은 e)
  - U_neg = { e : ∃ IMPORTANT_NEGATIVE(w) fact f의 행이 e에 있음 ∧ view[e] 관측 ∧ f의 어느 행도 match 안 함 }, 사례에 a-support(e′) 참인 e′ ≥ 1일 때만
  - U = U_pos ∪ U_neg, **|U| = 서로 다른 evidence_id 수**(manifest "evidence_id 중복 제거" 그대로; 같은 fact 유래 evidence가 여럿 관측·불일치면 그 수만큼 — 같은 e에 fact 여럿이어도 1)
  - 효과(공개): 행 단위보다 엄격 → Core-K 경고·FPR 감소, ③ NOT_EVALUABLE 쪽·② NOT_FEASIBLE 반대쪽, ΔTPR 방향 사전 미정. 사전 집계(빌더, 행 단위 상한)는 무영향
  - 엔진 단위 테스트 필수: 사례 U ⊆ precount 방향별 U 가능 집합, 사례 |U| ≤ 방향별 n_U_possible, 다중 대응 IN fact(같은 뜻 2값) 한 값 관측 시 U_neg 미발동, 일부 evidence UNKNOWN·일부 관측 불일치 시 발동(부분 관측 — 건수 보고)
- K_data(exploratory) m 후보 = {1,2,3} ∩ ≤ K_data 자체 표의 방향별 U 가능 최소(같은 precount 정의)
- B 합성 음성 대조는 가상 입력이라 완독 검사 미시험 → binputs 후 jobs_stage2b.json 경로 존재·완독 대상 확인을 runner가 기계 확인(위 (3))
- **try2는 하나씩 순차 시작**(상한 검사 비원자성). runner v3 `run_stage2.sh` 1d163ce5…e5ec(v2 e4d21032 보존 `~/medmap_core_kb_preflight/run_stage2.v2_e4d21032.sh`, 차이 = B 시작 조건에 A2alt 추가·주석), 파일 a-w, 실행 직전 sha256sum을 runlog에 기록
- 빌더 precount.json `rule` 문자열의 "TUNE ③과 같은 결론"은 철회된 문구(빌더 동결로 미수정) — runlog·보고는 §6 정정 문구·고정 보고 문구가 우선
- 상한 도달: 14번째 호출 후 추가 호출 필요하면 중단·재심사(우선순위 재배분 없음, 상한 상향은 산출물 미열람 상태 deviation으로만)

## 10. 실행 후 보고 항목(판정 미사용, gate 11 MINOR)
- relation별·finding_kind별 대응 채택률, A2 기계 기각·B 기각 사유 분포, finding_value absent인데 POS·VALUE로 채택된 수, EXAM_SIGN·TEST_RESULT 채택 대응
- 서로 다른 evidence_id ≥2 대응 fact(복합·조건부 소견) 목록과, 그 fact를 뺀 사전 집계 민감도
- 채택된 IMPORTANT_NEGATIVE 대응 전체 표(fact 문구 포함). 뒤집힘 의심 표기 = 기계 기준(finding_value = absent 또는 finding_text·quote에 정규식 `\b(no|not|absence|absent|without|normal|negative|below)\b`), A1b2-0091·A1b2-0094·A1b1-0110(PERC)은 채택 여부와 함께 반드시 표에 포함
- 복합 fact(서로 다른 evidence_id ≥2) 유래 대응이 엔진 단계 REVIEW 경고에 기여한 사례 수, U_neg 부분 관측 발동 건수(엔진 단계, 판정 미사용)
- precount 방향별 수와 쌍 합계(두 방향 합집합) 수 병기
- 표 행 quote fact 수(출처 근거 약함 표기), 과거력 질문 E_3·E_105·E_109 채택 대응
- kappa2: NONE 사유별(실제 대응 없음·전부 기계 기각·누락·중복) 평가자별 수, bootstrap NaN 폐기 수, 입력 맥락 비대칭(A2 119/143 vs A2alt 60), B 이전 대응 기준
- 세션별 검사·postcheck, 시도·호출 수, 정가 환산 추정(청구액 아님), silent_turn_reminder 위치

## 11. 한계(기록)
- A2·B·A1이 같은 회사 모델, B와 A1·A2 모두 opus → 맹점 공유 가능
- quote 안 질환명은 A2에 노출됨. DDXPlus 질문 목록 자체를 모델이 기억할 수 있음(시뮬레이터 순환은 EVAL 후 순환도 감사 대상)
- 숫자 척도 대응 금지로 강도·발현 속도 소견은 대응 불가(근거 없는 임계 생성 방지의 대가)
- 실행 기록·결과는 `EXP-SN-CORE-001-stage2-runlog.md`(실행 후 작성)

## 12. deviation-15(429 재개, 2026-10-02 22:3x, B 산출물 미열람)
- 사건: Ba·Bb try1이 계정 사용량 한도(429 session limit, 리셋 23:30 KST)로 약 3.5분 시점 종료. 사전 규칙상 중단 → 이 deviation + 재심사로만 재개
- 재개 규칙: try1 산출물·transcript 내용 미열람 봉인 유지(사용 금지, try2 실패 시 되돌아가지 않음). B 작업당 try2 1회. runner v4 `run_stage2.sh` 95a623cc…c4f(v3 1d163ce5 보존 `~/medmap_core_kb_preflight/run_stage2.v3_1d163ce5.sh`), 차이 = try2 guard에 429 분기 하나: try1 최종 NON_CLEAN ∧ result api_error_status 429 ∧ is_error ∧ 위반이 MODEL_MISMATCH 하나뿐 ∧ 모델 = {`<synthetic>`, 기대 모델} ∧ 봉인 SEALED.txt 존재. 합성 시험: 실제 봉인본 2개 PASS_429, 다른 위반 추가·봉인 없음·다른 모델·429 아님 4종 FAIL
- 시작 조건: 리셋(23:30 KST) 이후, Ba → Bb 순차(try2 하나씩 규칙), 호출 11 → 13/14(남은 1 = 재429 등 대비 없음: try2가 다시 non-CLEAN이면 실험 INVALID, try3 없음)
- 입력·프롬프트·B 입력·빌더·검사기·판정 규칙 전부 무변경. evaluability와 무관한 플랫폼 중단 복구만
- **정정(append, gate 14 의료 MAJOR)**: 위 "22:3x"는 틀림 — 봉인 실제 시각 2026-10-02 23:30:59(SEALED.txt·SHA256SUMS·verify/out 폴더 mtime), deviation-15 기록 23:31:55. try1 part 파일은 22:22:56–23:30:59 약 68분 미봉인·쓰기 가능 상태로 verify/out에 있었고, "열람 0"은 운영자 진술(파일 증거로 확인 불가). 메인 세션도 같은 사용량 한도로 이 사이 정지(운영자 진술)
- 봉인 범위 추가: try1 transcript 2개 a-w(23:3x), SHA = 봉인 scan.json 기록값과 일치
```
5e6c9fecbf3c17cdd5e832a936c185b86fb18ef7585c6a3cb12c7bfb66a1710e  /home/<user>/.claude/projects/-home-<user>-medmap-core-kb-ws/93ca8be8-4c22-49c3-b527-daf674d1163e.jsonl
eef9e16f22fcce0c888203607414f107c5237c57c21073014d1625c6df654377  /home/<user>/.claude/projects/-home-<user>-medmap-core-kb-ws/5a77261c-6bb6-4672-bb39-de4b0e42d64b.jsonl
```
- try1 재호출 금지(runner가 `Ba 1` 재실행을 코드로 막지 않음 — 운영 규칙), Ba→Bb 순차·try3 없음도 운영 규칙(runlog §재개 운영 규칙)
