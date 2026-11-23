# EXP-MAI-003 1차 gate(20261103_105726_NEEDS_FIX) 지적 추적표 — time_v2

| ID(reviewer) | 지적 요지 | 반영 위치 | 확인 방법 |
|---|---|---|---|
| A-unfalsifiable-primary(design)·S-claim(stats)·M-time(medical) | 안전 4종 구조상 0 | 계층 B `independent_audit.py`(원 parquet 별도 경로 허용 집합·storetime·subject·다중 체류·행 대조), hypothesis·primary_metric 재정의 | F01·F02·F03·F04·F05·F13·X1 결함 → B 위반 ABORT |
| G-claim-overreach | claim 무조건 서술 | expected_claim 가정 명시, PROTOCOL_TIME_v2 §1 | manifest |
| F-record-denominator·S-denominator·M-unit | 기록 분모 체류 수만큼 중복 | `records_v2.prepare` 전역 1회 중복 처리·귀속, triage 행/파생 증거 분리 | test_record_units_and_reconciliation, F05 |
| F-patient-count·S-cluster | 환자 수 병기 없음 | 모든 체류 지표에 patients | test_usage·test_paired_crosstab |
| D-metric-coverage·M-proto | S1/S2 flag·PROXY/APPROX·포함률·중복 미산출 | `run.public` flags_by_policy·PROXY/APPROX·rate·dup | F06·F07·F09 |
| S-paired | 대응 교차표 없음 | paired_crosstab_vs_STRICT | F08 |
| S-metric-mismatch | 포함률 공식 미고정·누출 범위 | manifest secondary_metrics·PROTOCOL §6, 세 정책 모두 검사 명시 | manifest |
| G-repro-sha·M-repro | 코드·입력 SHA 없음 | code_sha256·input_sha256·software·--code-sha-manifest | F10a·F10b·test_code_and_input_sha |
| G-checkpoint-undefined·S-T1·M-cp | T 정의·T1=T2·결측 체류 | proposed_method·PROTOCOL §2, stays.t1_equals_t2·TIME_UNDEFINED | test_record_units(시각 불명 체류) |
| B-privacy-traceback·M-gov(로그) | 예외 메시지 식별자 | HMAC 가명 키, main 예외 → 단계·유형만, 종료 4 | F11a·F11b·test_exception_path_no_identifiers |
| B-TEST-overlap-ambiguity | Ext-PE 중복 | manifest dataset·test_population, 공개 JSON ext_pe_overlap_note | manifest |
| D-test-evidence·M-fault | 결함 주입이 run 미포함 | `fault_v2.py` 전체 경로 13종+X1·X2 | outputs/fault_v2_* ALL_DETECTED |
| MINOR logs/ 없음 | run_command 리다이렉트 실패 | time_v2/logs 생성, run_command `mkdir -p logs` | — |
| MINOR out_dir 늦은 확인 | | run 시작 시 mkdir(exist_ok=False) | test_out_dir_conflict_at_start |
| MINOR·M-rad 비CTA SYMPTOM 투입 | | 비CTA·UNKNOWN 미투입, 유형별 참고 집계 | test_record_units |
| MINOR·M-rad addendum 이중 반영 | | 양방향 연결 + 결정 분류만 대체, NO_MENTION 미투입, A_addendum_family_double_effective | F12·X2·test_alerts(대체 전 시점 불변) |
| MINOR v3b 비PE CTA | | confounder 추가 | manifest |
| MINOR PENDING 미생성 | | observed≤T<available 기술 건수·CTA 미이용 체류 수 | test_usage |
| MINOR 사후 정보 선택 | | confounder 추가 | manifest |
| MINOR·S-mask·M-gov 보완 마스킹 | | `public_v2.suppress` MASKED_COMPLEMENT·계산 불가 | test_small_and_complement |
| MINOR PROTOCOL_TIME:60 없는 파일 참조 | v1 은 보존(수정 금지) | v2 변경 기록에 정정 명시(실제 = time_v1/fault_time.py) | — |
| MINOR stays_state_changed 정의 | | T0 vs T2 / 어느 시점이든 분리 | test_alerts_addendum_and_changes |
| MINOR ECG dtype | | ed_stay_id 정수 정규화·dtype 기록·매칭/코호트 밖/키 없음 건수 | test_record_units |
| MINOR charttime 귀속 한계·S-ambig-scope·M-attr | | confounder·NOT_VERIFIABLE | manifest |
| MINOR 실행 시간·RAM | | bench_v2.py 합성 규모 시험 → manifest runtime_estimate_detail | outputs/bench_v2_* |
| S-multiplicity | 셀 전부 보고 | statistical_test·multiple_comparisons 문장 | manifest |
| S-generalize | rule-of-three 금지 | confidence_interval·PROTOCOL §1 | manifest |
| S-seed | seed 무의미 | seed 필드 | manifest |
| M 확인 필요(봉인 자료 사실) | outtime 결측·dtype·AR 수·키 중복 | 실행 시 공개 JSON 이 건수로 보고(사전 확인 안 함 — 봉인 미열람) | — |
| M 체류별 결과 출력 | 코드에 없음 | v2 에서 정식 제외(공개 집계만) | manifest expected_outputs |

# 2차 gate(20261103_115323_NEEDS_FIX) 지적 추적표 — time_v2 3차 개정

| ID(reviewer) | 지적 요지 | 반영 위치 | 확인 방법 |
|---|---|---|---|
| D-metric-coverage 잔여(design MAJOR 1)·S-diff-output | 포함률 차이 미산출 | `public()` rate_diff_vs_STRICT(반올림 전 계산) | test_usage_inclusion_proxy_approx, F14 |
| S-mask·M-gov 잔여(design MAJOR 2)·S-mask-reversible(stats MAJOR)·M-gov(medical) | 묶음 간 역산 | `public()` 전역 1회 suppress + 항등식 묶음(체류·행 대조·같은 양·flag/등급 합·pooled·상태/범주·교차표 행/열/비대각·결정 상실/획득), 체류 가림 → 환자 가림, PROTOCOL §9 묶음 목록·잔여 위험 명시 | test_cross_table_identities_not_single_masked, X5 |
| S-paired-construct(stats MAJOR) | SUPPORTED R1/R7 혼합 | 범주 = 상태+근거(8종), decisive_lost/gained, 범주 분포 | test_paired_crosstab(S1 T0 R7, S2 T2 상실 5), F08 |
| M-add-attr(medical MAJOR) | addendum 체류 넘김 | records_v2·independent_audit 가족 귀속, 건수 2종 공개 | fixture a5·a6, test_record_units, F15 |
| M-add-cls | 대체 해석 근거 | replace_pair:*·nomention_addendum_parent_class:* | test_record_units |
| M-v3b-AR·M-attr2 | confounder | manifest potential_confounders, PROTOCOL §4·§5 | manifest |
| M-unit2·S-unit-triage·S-pooled | 단위 표기 | unit_notes·denominator.definition(pooled 참고값) | — |
| 키 dtype 공통 모드(design MINOR) | 두 계층 같이 0 | B_zero_match_guard_*, input_key_dtypes | test_zero_match_guard |
| G-repro 절차·M-repro | SHA 동결 선택 인자 | --write-code-sha, 승인 실행 시 --code-sha-manifest 필수, PROTOCOL §11 | test_cli_refuses, test_code_and_input_sha(일치 시 DONE) |
| fault 추적성(design MINOR) | 발동 위반 이름 없음 | fault_v2 PROBE 로 결함별 상태·단계·위반 기록, B 부분 약화 X3·X4 | outputs/fault_v2_* |
| 계층 이름(design MINOR) | source_reference 계층 | A_source_reference_untraceable, SAFETY_A_NOTE | — |
| S-recon-scope | B 대조 범위 | SAFETY_B 목록·PROTOCOL §7 원천별 명시 | — |
| S-claim-wording | 방향 전제 | expected_claim·secondary_hypothesis 양방향 기술 | manifest |
| S2 기술 집계(design MINOR) | 정의상 0 | unit_notes.S2_note | — |
| 문구(design MINOR) | 결함 수 | validation_population 정정 | manifest |
| 실행 시간(design MINOR) | v3b 분류 시간 미반영 | bench_v2 는 v3b 분류 포함 경로(prepare 에서 classify 호출) — 단 합성 문장 3종이라 실제 길이 반영 안 됨(확인 필요 유지) | outputs/bench_v2_* |
| 새로 발견(자체) | 코드 SHA 일치 시에도 ABORT(Counter 0 키 참) | `if bad:` 가드 + 일치 시 DONE 테스트 | X6 |
| S-cluster-residual | 체류 블록 환자 수 | 미반영 — time_undefined·t1_equals_t2 는 체류 속성 집계(환자 병기 없음) 한계로 둠 | — |
| S-stayrate-wording | 체류 포함률 문구 | PROTOCOL §6 "증거 있는 체류" = T 까지 사용 증거 ≥1 체류(코드 정의 동일) | — |

# 3차 gate(20261103_152143_NEEDS_FIX) 지적 추적표 — time_v2 4차 개정

| ID(reviewer) | 지적 요지 | 반영 위치 | 확인 방법 |
|---|---|---|---|
| S-mask-differs(design MAJOR·stats MAJOR) | 비대각 묶음 ≠ 상이 체류 항등식 | SUMMARY_OF + 정확 항등식 묶음(요약 상태 다른 칸) 추가, 비대각 묶음은 과잉 포함으로 유지, docstring·§9 정정 | fixture n7(R3→무결정 비대각, 비대각 합 6 ≠ 상이 5), test_exact_identity_groups_present, X8 |
| S-mask-test-circular | 테스트가 G 재기술 | suppress 에 넘긴 묶음을 가로채 '합이 정확히 맞는 묶음' 존재 검사 | X8 은 이 테스트로만 탐지(출력 기반 테스트는 놓침 — 확인) |
| S-mask-crosseq | 정책·시점 간 같은 양 | lab 사용 세 정책·rad STRICT=S1·S1 triage T 불변·lab flag 세 정책 묶음 | X9, test_exact_identity_groups_present(같은 값 확인) |
| S-paired-fixture | R1→R7 기대값 | 그래프에 lab→PE SUGGESTS 간선 없음(HP:0410174·HP:0033106 SUGGESTS 0, 2026-11-03 확인) → S2 R7 경로는 합성으로 못 만듦, 같은 문제(요약 같고 범주 다른 칸)를 R3→무결정으로 고정 | test_paired_crosstab |
| M-unlinked-AR(medical MINOR) | 미연결 AR 단독 증거 | §5 한계 + stays_with_unlinked_AR_effective 사전 지정 | test_usage(71 만, a7 POST_ED 제외) |
| M-fam-B | 새 건수 비대조 | SAFETY_A_NOTE·§7 명시 | — |
| M-bench-path | bench 가족 경로 미통과 | runtime_estimate_detail.bench_path_note | manifest |
| S-cluster-residual | 한계 문구 없음 | unit_notes.stays_block | — |
| S-mc-list | 셀 목록 | statistical_test·multiple_comparisons 목록 보강 | manifest |
| 명칭(stats)·계층 이름(design) | B_source_reference 잔존 | manifest primary_metric·§7 B 목록 정리 | manifest·PROTOCOL |
| §5 문구·변경 기록(design) | 다른 체류 귀속 경우 소멸 | §5 정정, 변경 기록에 deviation 23 경위 | PROTOCOL |
| X1–X6 문구(design·medical) | 실제 X1–X9 | validation_population·§11 | manifest |
| lock 범위(design)·deviation 묶음(medical) | 비프로토콜 필드 추적 | metric_unit deviation 에 묶어 기록 | deviations.yaml |
| triage 과잉 포함 주석(design) | 정확 항등식 아님 | public() docstring | — |
| M-repro·G-repro 잔여 | git 미추적 | 미반영 — 커밋은 사용자 지시 시만(하드 룰). RUN 후 CODE_SHA256 생성 시 그 SHA 를 rg record 에 남길 것 | — |

# 4차 gate(20261103_153500_NEEDS_FIX) 지적 추적표 — time_v2 5차 개정

| ID(reviewer) | 지적 요지 | 반영 위치 | 확인 방법 |
|---|---|---|---|
| S-mask-equal3(design MAJOR)·S-mask-eq3(stats MAJOR)·M-eq-group(medical MINOR) | 3칸 같은 양 묶음은 보완이 2칸에서 멈춤 | 같은 양 = 2칸 사슬(eq_chain): lab 사용 세 정책·S1 triage T0–T2·lab flag 세 정책, rad STRICT=S1 쌍 유지 | test_equal_quantity_scenario_T0_rad_small(reviewer 재현 값), 출력 기반 '0 또는 전부' 단언, 3칸 묶음 금지 단언, X10 |
| S-eq-scope(stats MINOR) | lab 등급·C 입력 | lab 등급 A/B/C·C 입력 세 정책 사슬 추가 | — |
| S-dev-trace(stats MINOR) | multiple_comparisons 변경 추적 | deviation(metric_unit, 5차)에 함께 기록 | deviations.yaml |
| S-doc(stats MINOR) | public_v2 docstring | 묶음 종류(합 항등식 / 같은 양 = 2칸 사슬) 명시 | — |
| S-paired-fixture 근거(design MINOR) | S2 R7 = 0 기록 | unit_notes.categories 에 그래프상 0 명시 | — |
| G-repro·M-repro 잔여 | git 미추적 | 유지 — 커밋은 사용자 지시 시만. RUN 후 CODE_SHA256 SHA 를 rg record 에 기록 | — |

# 5차 gate(20261103_154503_NEEDS_FIX) 지적 추적표 — time_v2 6차 개정

| ID(reviewer) | 지적 요지 | 반영 위치 | 확인 방법 |
|---|---|---|---|
| S-eq-scope-rad(stats MAJOR) | rad flag 정책 간 같은 양 누락 | 개별 열거 대신 일반 규칙: 모든 원천 flag·등급·C 입력·사용·PROXY 칸 세 정책 사슬, 정책별 triage T 사슬 | test_rad_flag_equal_across_policies_scenario(reviewer 재현 값), X11 |
| S-eq3-residual(stats MINOR) | APPROX·triage·C 사용 3칸 묶음 | eq_chain 으로 교체 | test_no_three_cell_equal_groups(같은 필드 세 정책 3칸 묶음 금지) |
| S-X10-scope(stats)·S-eqchain-mutation-scope(design) | 사슬 변이 범위 | X9·X10 은 일반 사용 사슬 전체, X11 은 rad flag 사슬 | fault_v2 |
| M-graph-prov(medical MINOR) | 그래프 KB 버전 미기록 | graph_kb_sources(SHA·커밋·데이터 버전만), S2 R7 주석에 '결과가 0 아니면 그대로 보고' | 공개 JSON |
| S-eq-assumption(design MINOR) | 같은 양 가정 미확인 | 일반 규칙상 다른 값이면 더 가릴 뿐 — 실행 후 '계산 불가'·마스킹 칸 수를 보고에 포함(보고 규칙) | — |

# 6차 심사(공식 기록 없음) 및 공개 집계 보호 구조 개정 — 2026-11-03

- 6차 심사 사실: reviewer 3명(design·stats·medical)이 실행됨(design·stats NEEDS_FIX — 등급 = flag 합 필드 간 항등식 묶음 누락, medical RUN). **`rg.py record` 명령은 사용자 거부로 실행되지 않았고 공식 감사 파일·audit trail 에 없음.** 소급 기록하지 않음. 정식 gate 기록 번호는 rg 감사 파일 시각으로만 구분.
- 반복 원인: 1~5차(+6차) MAJOR 가 모두 '공개 칸 사이 합·차이·같은 양·필드 간 합 관계로 1–9 칸 역산' 한 종류. 관계를 사람이 열거하는 방식이 근본적으로 불완전.
- 개정(PROTOCOL_TIME_v2 §9-2): 내부 정확 집계 / 공개 집계 분리 · 독립 검증기(합성 자료로 발견한 정확 등식 300개·쌍별 부등식, 이번 자료에서 참인 것만, 선형계획 범위 검사) · FAILED·NOT_VERIFIABLE 표 통째 비공개 · 환자 수 1칸만 공개 · 공개 파일 재읽기 재검사.

| 지적 종류(1~6차) | 개정 후 처리 |
|---|---|
| 합 항등식 누락(행·열·전체·부분집합) | 묶음 열거 불필요 — 등식은 합성 자료 영공간(정확 분수)에서 자동 발견, LP 로 검사 |
| 같은 양 3칸 묶음·정책 간 같은 양 | 등식 발견에 포함, 사슬 규칙과 무관하게 LP 로 검사 |
| 필드 간 합(등급 = flag 합) | 등식 발견에 포함(6차 지적 경로 — test 로 확인은 attack 테스트 일반형) |
| 정책 간 차이·pooled 차이 | 등식 + test_two_policy_difference |
| 비율·반올림 | 비율 공개 규칙(분자·분모 공개 시만) + test_exact_percentage_and_rounded_ratio |
| 집단 중첩(부분집합) | 쌍별 부등식 + test_overlapping_population_inequality, 환자 수 비공개 |
| 검증 불가 관계 | NOT_VERIFIABLE → 비공개(PASS 로 바꾸지 않음) |
| 3칸 이상 부등식·비선형·정수 간극·과거 EXP-02 공개값 결합 | 미검사 — 남은 위험으로 명시 |

# 마지막 기록 gate(20261103_173120) 결함 수정 — 2026-11-03(재심 없음, 승인 아님)

사용자 결정: 7차 재심사·실제 MIMIC 실행 미승인. 수정·합성 검증 후 종료. 기존 심사 기록 무수정. 정본 = PROTOCOL_TIME_v2.md §5-1·§9-3.

| 지적 | 수정 | 탐지 테스트 / 결함 주입 |
|---|---|---|
| D-verifier-truth-restriction·S-const-blind·S-hasse-restrict(우연 관계·거짓 관계 삭제) | 관계를 disclosure_schema.py 선언으로 교체, 거짓 관계·상수 칸 NOT_VERIFIABLE | FalseRelations / D8·D9·D14·D16·D17 |
| D-verifier-fail-rule·S-range-lo0(0 포함 범위·1–9 직접) | 범위 판정식 변경, 공개 정수 1–9 FAILED | Ranges / D2·D10·D11 |
| M-pat-link(EXP-02 결합) | external_known(값은 EXP-02 공개 파일), 내부 칸 추가, 불일치 시 전부 비공개 | External·RunPath / D12·D20·D21·X5 |
| 생성기 죽은 분기·상수 칸 미분류 | 분기 수정·동점·영상 충돌·역순 addendum 추가, constant/generator_constant 분리 | Schema·coverage_report |
| M-add-order·P-pending-decision | §5-1 제외 규칙, 계층 B 독립 구현 | AddendumOrder / O1–O5 |
| G-bench-stale | 최종 코드로 bench 재실행, 관계 SHA·코드 SHA·표 목록 기록 | outputs/bench_v2_20261103_183134 |
| D-scope-honesty·M-scope-count | LIMITS·§9-3 정정, 공개 건수 = 선언 수 | test_protect_withholds_tables_of_false_relation |
| I-overwrite·M-int-perm·M-recheck-window·M-int-path·G-rel-provenance·P-doc·S-oou·D-roots | 덮어쓰기 거부·600·임시 이름 재검사·동결 폴더 거부·code_files 확장·토큰/최상위 항목 NOT_VERIFIABLE | RunPath / D18·D19 |

남긴 지적(수정 안 함, §9-3 남은 위험): S-lp-gap(정수 간극) · S-percell(칸에 없는 작은 합) · 실행 후 검증 경로 미정.

결과(합성만): 관계 파일 relations_v3_schema.json(SHA 80a9516c…, 합성 1,998개 대조, 등식 487·쌍별 258·다항 8·정의상 0 60칸, 생성기 미도달 516칸, 빈틈 관계 3건 → 공개 금지 13칸, 선언 설명 안 되는 합성 쌍별 부등식 27,452/31,279 — 규칙으로 쓰지 않음, 전수 검토 안 함). 전체 테스트 93 OK(logs/tests_final_*). 결함 주입: 전체 54종 중 52 탐지·2 생존(D3, X5, fault_v2_20261103_185423) → 새 규칙이 기존 시험 입력을 가려 탐지력을 잃은 것으로 확인, 테스트 2건 추가 후 해당 2종 재실행 탐지(fault_v2_20261103_185940). 그 뒤 전체 54종을 다시 돌리지는 않음(테스트 추가만, 코드 변경 없음). 규모 시험 25.1초·1,128MB, 공개 45표·비공개 32표(합성값 — 실제 결과 아님). 이후 PROTOCOL §11 문서 한 줄만 추가(코드 SHA 는 동결 때 새로 계산).
기존 테스트 변경 1건: test_overlapping_population_inequality 의 입력 b=2 → 0. 이 입력은 공개 정수 2 를 VERIFIED 로 기대해 지적된 결함을 고정하고 있었음.
이전 숫자 철회: '63/76 공개'(bench_164157)는 최종 검증기 전 값 + 폐기된 관계 방식 — 인용 금지. EXP-MAI-003 실제 공개 파일은 존재한 적 없음(실제 실행 없음). EXP-02·시간 감사 기존 공개 파일 무수정.


# 남은 결함 일괄 수정·동결 — 2026-11-04(사용자 지시: gate 1회, 통과 시 실제 실행 1회)
시작 상태: NEEDS_FIX·UNLOCKED, 테스트 93 OK, 결함 54종 전체 재실행 미완료. 수정: 실행 관문(gate_authorization, deviation 비참조)·1회 사용 표지·사후 검증(verify_counted_run.py)·기록/체류/환자 단위 분리·정수 재확인·시간 감사 대조·문자열 시각 입력 대응·생성기 구성비 다양화 → 관계 파일 재생성(이전 판 superseded/ 보존). b=2 사례 복원(기대값 FAILED·사유 칸 고정) + 범위 통과 의도는 독립 검사로 분리.
검증: 테스트 123 OK, 결함 69종(기존 54 + 신규 15) 전체 탐지·대조 OK, 회귀 110 OK. 그 뒤 코드 변경 없이 동결. 실패 시도: test_counted_run 의 cls.run 이 unittest run 을 덮어써 1차 전체 테스트가 중단 → 이름 변경 후 재실행.

정식 gate(20261104_114848): NEEDS_FIX(설계 RUN, 통계 NEEDS_FIX, 의료 NEEDS_FIX, CRITICAL 0). MAJOR = S-undeclared-struct(알림 합집합·영상 대기 구조 관계 미선언), M-audit-link(시간 감사 lab 조인 수 결합). 지시대로 수정·재심·실제 실행 없이 종료. §9-3 (b) '대부분 우연' 서술은 이 gate 에서 반증됨(동결 문서라 고치지 않음, 다음 개정 때 정정).
