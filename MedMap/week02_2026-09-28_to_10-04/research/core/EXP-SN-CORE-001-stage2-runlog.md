# EXP-SN-CORE-001 Stage 2 실행 기록 (RG gate 13 RUN 20261002_221515, lock 276ffd99bc95)

## 0. 실행 전 기록
- 우선순위: freeze §1:16(순서)·§9:97–108(U 식·runner v3·try2 순차)이 §7·§8의 이전 문구(v2, "A2a·A2b CLEAN")보다 우선. U 셈은 deviation-14e 식 우선(manifest 14c 문구와 병존, 모순 없음). 빌더 precount.json rule 문자열의 "TUNE ③과 같은 결론"은 철회 문구 — 보고는 freeze §6 정정·고정 문구 우선
- 승인 근거: 사용자 2026-10-02 지시(위임) "A2·A2′ 질문 사전 대응과 검증 B의 prompt/script/allowlist를 먼저 동결하고 … RG 재심사에서 RUN을 받은 뒤에만 Stage 2를 실행해 …". deviation-14–14f approved_by user = 이 지시 원문 근거의 위임 승인(개별 승인 아님). 격리 CLI 과금 = 기존 승인(deviation-09) 범위·상한 14 호출/$40(정가 환산 추정, 청구액 아님)
- runner sha(실행 직전 2026-10-02 22:15:30): 1d163ce5126bcf6be665201c74f5213f4e29dc2cea15c96b0d16cd5ecab3e5ec (기대 1d163ce5…e5ec)
- STAGE2_SHA256SUMS -c: OK
- 시작 전 호출 6/14, 누적 정가 환산 $15.66(추정)
- 엔진 단계로 넘길 항목(gate 13 MINOR): 엔진 관측 가능 집합 = precount 정의(E_134·E_152 제외), §10 보고 추가 — |U| ≥ m이나 서로 다른 fact 수 < m인 REVIEW 수, fact 단위 민감도(탐색), "|U| = DDXPlus 문항 수, 독립 소견 수 아님"(fact 단위 대비 경고 증가 방향), U_neg 발동 관측값 분포(NEG/VALUE/NA), IN 뒤집힘 정규식 IGNORECASE·어휘 보강(lack, ruled out, exclude, unlikely)

## 1. 시도 기록
| job | try | 시작 | 종료 | exit | model | scan | postcheck | 정가 환산 USD |
|---|---|---|---|---|---|---|---|---|
| A2alt | 1 | 22:15:34 | 22:16:21 | 0 | claude-sonnet-5-5 | CLEAN, coverage 누락 0 | CLEAN | 0.28 |
| A2a | 1 | 22:15:34 | 22:18:08 | 0 | claude-opus-5-5 | CLEAN, coverage 누락 0 | CLEAN | 0.97 |
| A2b | 1 | 22:15:34 | 22:18:29 | 0 | claude-opus-5-5 | CLEAN, coverage 누락 0 | CLEAN | 1.09 |
| Ba | 1 | 22:19:01 | 22:22:43 | 1 | opus + `<synthetic>` | INVALID: MODEL_MISMATCH(<synthetic>) | NON_CLEAN: RESULT_IS_ERROR·EXIT_1 | 1.04 |
| Bb | 1 | 22:19:01 | 22:22:56 | 1 | opus + `<synthetic>` | INVALID: MODEL_MISMATCH(<synthetic>) | NON_CLEAN: RESULT_IS_ERROR·EXIT_1 | 1.10 |

- A2 3개 채택 = try1(A2alt 최종 postcheck 22:16:21 < binputs 22:18:55). A2 산출물 동결 `stage2/A2_OUT_SHA256SUMS`(a-w). binputs 전 `STAGE2_SHA256SUMS -c` OK(22:18:55). binputs: 대응 fact 87·대응 쌍 201·A2 기계 기각 0, B 입력 Ba 2·Bb 2조각, `B_SHA256SUMS -c` OK 후 Ba·Bb 동시 시작(호출 9→11)
- **Ba·Bb try1 원인(로그만, 산출물 미열람)**: result.json `api_error_status 429`, 결과 문구 "You've hit your session limit · resets 11:30pm (Asia/Seoul)", transcript 마지막 `<synthetic>` 메시지 isApiErrorMessage·error=rate_limit(Ba 22:22:43, Bb 22:22:55). 사전 규칙(deviation-12b) = 429 → 재실행 없이 중단·deviation·재심사 → **중단**
- 봉인(22:2x): `quarantine/Ba.try1`·`Bb.try1`(산출물 part 파일·로그, SHA256SUMS f8f79a93…·428cd999…, SEALED.txt, a-w). 열람 0. verify/out/Ba·Bb 비움 확인
- 사용자 "마저 해"(22:2x, 중단 통보 전 지시) → 사전 규칙의 재개 경로(deviation-15 + 재심사)로 진행
- 호출 11/14, 정가 환산 누적 약 $20.15(추정, 청구액 아님)
- **정정(append, gate 14 통계 MINOR)**: 봉인 실제 시각 = 23:30:59(SEALED.txt·SHA256SUMS mtime), deviation-15 기록 23:31:55 — 위의 "22:2x"·freeze §12 "22:3x"는 틀림. 메인 세션도 같은 사용량 한도로 22:23–23:30 정지, 그동안 try1 part 파일은 SHA 미고정 상태로 verify/out에 있었음(part mtime 22:21–22:22 = 세션 Write 시각, 이후 수정 흔적 없음). "열람 0"은 운영자 자기 선언(기계 확인 불가). "마저 해"는 429 중단 통보 전 지시
- **재개 운영 규칙(실행 전 고정)**: (1) try2 단계에서는 429를 포함한 모든 non-CLEAN = 실험 INVALID, 재개 deviation·try3 없음(§12가 §7 "429 → 중단·deviation·재심사"보다 우선) (2) 명령 원문 `nohup bash run_stage2.sh Ba 2 …` → Ba try2 postcheck CLEAN 확인 후에만 `… Bb 2 …`, Ba 산출물은 Bb 종료까지 열지 않음, Ba non-CLEAN이면 Bb 미실행 (3) 종료 후 result.json 총수 13·logs에 새 Ba/Bb.try1 없음 확인 기록(runner가 try3를 코드로 막지 않음) (4) 채택 B는 작업당 두 번째 시도이며 try1(Bb는 part 5개 작성 — 출력 완성 가능성)은 내용과 무관하게 폐기 — §10 보고에 공개
- 429 guard 합성 시험(23:3x, 메인): 실제 봉인본 Ba·Bb PASS_429, 변형 4종(다른 위반 추가·봉인 없음·다른 모델·429 아님) FAIL. 통계 심사관 독립 재현: 변형 6종 FAIL(+is_error false·logs 경로)
- 봉인 범위 추가(gate 14 의료 MINOR): try1 transcript 93ca8be8…·5a77261c… a-w, SHA 위 freeze §12 정정 참조. 운영 규칙: `run_stage2.sh Ba 1`·`Bb 1` 재호출 금지
- (gate 14 반영, 23:4x) 시각 확정(설계 심사관 transcript 실측): 운영 세션 한도 정지 13:23:11Z(22:23 KST), 사용자 "마저 해" 23:30:17 KST, 봉인 23:30:59, deviation-15 23:31:55. 봉인 전 구간 B part 파일 내용 읽기 tool_use 0건(운영 세션·심사관 transcript 전수, 설계 심사관 실측) — 출력된 것은 메타(verdict·위반 수·write 경로·coverage·오류 문구)뿐
- PASS_429 적용 대상 = Ba·Bb try1뿐, 두 봉인본 postcheck operator_reasons = ["RESULT_IS_ERROR","EXIT_1"](OVERWRITE·COMPACTION·CAPACITY 없음) 확인
- 재429 포함 try2 non-CLEAN = 실험 INVALID(§12 우선, deviation-12b의 재심사 경로 미적용). Ba try2 END < Bb try2 START 기록 예정
- (gate 15 RUN 23:39:07 반영) runlog 위 "(gate 14 반영, 23:4x)" 줄의 실제 기록 시각 = 커밋 917c506 23:36:44. 위 정정 줄의 라벨은 출처 = 의료 MAJOR + 통계 MINOR-4. 429 guard 합성 시험 경로: scratchpad `cf739c0f…/scratchpad/gq/`(메인), 심사관 재현 `…/scratchpad/g14b/`
- 사용자 통보: 23:3x 채팅으로 "재실행이 다시 429면 실험 전체 INVALID·되돌릴 수 없음, '마저 해'에 따라 진행, 멈추라 하면 중단" 보고(응답 없음, 지시 유지)
- try2 직전 점검(2026-10-02 23:39:21): runner sha 95a623ccc0b869f1739335e34f1e6c92a11e8e3d71e3b526ace68785477c9c4f · 봉인 디렉터리 ctime: 2026-10-02 23:30:59 /home/<user>/medmap_core_kb_runner/quarantine/Ba.try1
2026-10-02 23:30:59 /home/<user>/medmap_core_kb_runner/quarantine/Bb.try1 · claude 프로세스 수 5 · A2 채택 transcript 3개 a-w, SHA:
```
4cc93032da454413d59d4c484e20d579a42824e87c2c383f7dd4b6178e0c556d  17f6d3a6-9085-4ca8-8b9b-140d58e6ae35.jsonl
d1901598166744401e6c65ef8bb031382354cdea84f94eaced518ff0fd29b275  4b14b0a5-6837-40bf-94fb-2c03e72f0daa.jsonl
8644e14a88f242c7304cdb2f4ef3e4736ffe23de66c8ee174967b6b0a9a36fbd  ea58d984-c6a6-422f-b34e-7bdbeef07984.jsonl
```
- 실행 명령 원문: `nohup bash run_stage2.sh Ba 2 > logs/Ba.try2.stdout.txt 2>&1 &` (Ba postcheck CLEAN 확인 후에만 `… Bb 2 …`)

## 2. try2 기록·Stage 2 완료(2026-10-02)
| job | try | 시작 | 종료 | exit | model | scan | postcheck | 정가 환산 USD |
|---|---|---|---|---|---|---|---|---|
| Ba | 2 | 23:39:21 | 23:43:49 | 0 | claude-opus-5-5 | CLEAN, coverage 누락 0 | CLEAN | 1.27 |
| Bb | 2 | 23:43:58 | 23:50:10 | 0 | claude-opus-5-5 | CLEAN, coverage 누락 0 | CLEAN | 1.55 |
- guard 출력 둘 다 `TRY2_GUARD PASS_429`. Ba END 23:43:49 < Bb START 23:43:58. Ba 산출물은 Bb 종료까지 미열람
- 종료 후: result.json 총수 13(logs 9 + quarantine 4), logs에 새 Ba/Bb.try1 없음. 정가 환산 누적 약 $24.2(추정, 청구액 아님). try2 transcript 0c8d9c00·29d55191 a-w
- B 산출물 동결 `verify/B_OUT_SHA256SUMS`(a-w), ckv0 전 `B_SHA256SUMS -c` OK 23:50:40
- 채택: A2a·A2b·A2alt = try1, Ba·Bb = try2(작업당 두 번째 시도, try1은 동시 실행·429·내용 무관 폐기, try2는 순차 실행 — 실행 조건 차이는 판정 규칙과 무관)

## 3. 결과(기계 산출, `docs/research/core/ck-v0/`, SHA = CKV0_SHA256SUMS)
- ck-v0: fact 216 채택 / 339(기각 123), 행 254, 질문 대응 행 82(fact 44). 인용 기계 대조 337/339
- fact 기각 사유: B OTHER 93 · FINDING_NOT_IN_QUOTE 12(+test_type 동반 3) · WRONG_DISEASE 9 · WRONG_RELATION 4 · QUOTE_MISMATCH(+B OTHER) 2. 대응 기각: A2 기계 0, B NOT_SAME_MEANING 47(A2 대응 201 중)
- 채택 대응 relation: ACS SUPPORTING 42 · PE SUPPORTING 33 · PERI SUPPORTING 5 · **ACS POORLY_EXPLAINED 2** · PE POORLY_EXPLAINED 0 · IMPORTANT_NEGATIVE 0 · DIFFERENTIATING 0 · OVERLAPPING 0
- finding_kind(대응 행): SYMPTOM_HISTORY 58 · EXAM_SIGN 14 · RISK_FACTOR 9 · DEMOGRAPHIC 1. absent인데 POS/VALUE 채택 0. 과거력 질문 E_3·E_105·E_109 채택 0. 복합 fact(서로 다른 evidence ≥2) 5개. 표 행 quote 채택 fact 17
- IMPORTANT_NEGATIVE 11개: ck-v0 채택 7, 질문 대응 채택 0, 뒤집힘 의심(기계 기준) 10. 지정 3개: A1b1-0110(PERC) 채택·대응 없음, A1b2-0091·A1b2-0094 B 기각(A2 대응 후보 없음) — 상세 `stage2_report.json`
- **2단계 kappa(A2 opus vs A2′ sonnet, SAMPLE20 fact 60·단위 33) = 0.680 [95% CI 0.454–0.822]**, 일치 50/60, 판정 미사용(≥0.4 → "fact 불안정" 표기 없음). 1단계 0.659
- **사전 집계(precount.json)**:
  - ACS–PE, 정답 ACS·WD PE 방향: U 가능 0(PE POORLY_EXPLAINED·DIFFERENTIATING favors ACS·PE IMPORTANT_NEGATIVE 대응 행 0)
  - ACS–PE, 정답 PE·WD ACS 방향: U 가능 2 = E_220(깊이 숨 쉴 때 심해지는 통증)·E_91(발열) — ACS POORLY_EXPLAINED(A1b2-0008 pleuritic chest pain, A1b2-0013 fever) × PE SUPPORTING
  - 쌍 합계(두 방향 합집합) = 2 {E_220, E_91}
  - 보조 쌍 ACS–PERI: 정답 ACS 방향 0, 정답 PERI 방향 2 → 같은 판정
- ## **판정: primary ACS–PE = NOT_EVALUABLE (사전 집계 단계)**
  - 고정 보고 문구: **"ck-v0 구조상 해당 방향(정답 ACS, WD = PE) Core-K wrong-WD 탐지율 0 확정(음성 결과) — 이 pilot의 ACS–PE 쌍에서 출처 fact 기반 재검토 신호는 한 방향 이상에서 구조적으로 불가능"**
  - 라벨 공개(freeze §6): 쌍 합계 해석이었다면 엔진·TUNE으로 넘어가 ② NOT_FEASIBLE 또는 ③ NOT_EVALUABLE이 됐을 경로(PILOT 불가는 동일). 운영자는 Stage 1 집계를 사전 인지했음
  - 사용자 지시대로 corpus 확장·기준 완화·fact 추가·재작성·재대응으로 구제하지 않음. 엔진·split·평가 데이터 접근은 진행하지 않음(manifest 판정 순서상 중단)
