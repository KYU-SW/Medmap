# EXP-SN-CORE-001 Stage 1 실행 기록 (RG RUN 20261002_191832, lock 60c3e482b7be)

## 0. 운영자 추가 점검(실행 전 기록, 9회차 MINOR 대응 — 판정을 완화하지 않고 non-CLEAN 사유만 추가하는 보수적 규칙)
각 시도 종료 후 운영자(메인 세션)가 산출물 내용을 열람하기 전에 기계 점검:
1. stdout 로그(`logs/<job>.try<k>.stdout.txt`)의 END exit 코드, `result.json` is_error·subtype 기록
2. try2 진행 조건: try1 scan verdict = INVALID AND 위반에 MODEL_MISMATCH 없음 AND try1 result is_error = false AND exit 0. 중단 대상(모델 불일치·429·CLI 오류)과 재시도 대상이 함께면 중단 우선. try1 CLEAN이면 try2 금지
3. 추가 non-CLEAN 사유(→ (2)류: 격리 후 try2 1회): 같은 출력 경로 Write ≥ 2(덮어쓰기), part30 파일 존재(용량 포화 CAPACITY_SATURATED), transcript에 `compact_boundary` 또는 `isCompactSummary` 존재(COMPACTION)
4. 비용·호출 합산 = `logs/*.result.json` ∪ `quarantine/*/*.result.json` 의 total_cost_usd·호출 수(정가 환산 추정, 청구액 아님). 호출 14·$40 초과 시 중단
5. 실행 = nohup 백그라운드, 작업 4개 병렬, 시도별 stdout 로그 파일
6. kappa 세부(통계 MINOR, 실행 전 고정): 1단계 셀 = 단일 질환 3 × relation 6(DIFFERENTIATING 제외) + 쌍 2 × {OVERLAPPING, TEST_REQUIRED, OUT_OF_SCOPE_WARNING, SUPPORTING, POORLY_EXPLAINED, IMPORTANT_NEGATIVE} 6 + 쌍 2 × DIFFERENTIATING × favors 2방향, 스키마 밖·SAMPLE20 밖 unit_id fact 제외·수 보고, "fact 불안정" = 1·2단계 중 어느 하나라도 점추정 < 0.4, bootstrap 2,000회 PCG64 20261002 원 unit_id 단위

## 1. 시도 기록
| job | try | 시작 | 종료 | exit | session | model | scan | 추가 점검 | 정가 환산 USD |
|---|---|---|---|---|---|---|---|---|---|
| A1alt | 1 | 19:18:58 | 19:21:33 | 0 | (logs) | claude-sonnet-5-5 | CLEAN, coverage 0 누락 | 덮어쓰기 0·part30 0·요약 0 | 0.78 |
| A1b3 | 1 | 19:18:58 | 19:22:50 | 0 | (logs) | claude-opus-5-5 | CLEAN, coverage 0 누락 | 덮어쓰기 0·part30 0·요약 0 | 2.37 |
| A1b2 | 1 | 19:18:58 | 19:25:42 | 0 | (quarantine) | claude-opus-5-5 | INVALID: ATTACHMENT_TYPE_NOT_ALLOWED silent_turn_reminder(5.6분) | 덮어쓰기 0·part30 0·요약 0 | 2.62 |
| A1b1 | 1 | 19:18:58 | 19:28:29 | 0 | (quarantine) | claude-opus-5-5 | INVALID: ATTACHMENT_TYPE_NOT_ALLOWED silent_turn_reminder(9.3분) | 덮어쓰기 0·part30 0·요약 0 | 3.52 |

- 19:3x 사용자 결정: 정확 일치 예외 deviation-13 + RG 재심사, try1 봉인(산출물 미열람), RUN 후 try2
- 봉인 고정(2026-10-02 19:37:38): quarantine/A1b1.try1·A1b2.try1 폴더 쓰기 금지(a-w), sha256sum -c OK. SHA256SUMS 자체 SHA:
```
84f51be5260241e7259ec14308c7d5ae55d1dc54818a67a324f59c4f4ddc7954  /home/<user>/medmap_core_kb_runner/quarantine/A1b1.try1/SHA256SUMS
aabf78eab3b26ff2c740509a48b23dfd42aaa481fbe6bc17f241ba01071565ff  /home/<user>/medmap_core_kb_runner/quarantine/A1b2.try1/SHA256SUMS
```
- 운영 메모: try2에서 reminder 문구·유형이 조금이라도 다르면 현행 규칙대로 try2 INVALID → 실험 INVALID, 추가 예외 재개방 없음
- 운영 고정(10회차 통계 MINOR, 실행 전): deviation-13이 이 실험의 마지막 사후 예외. 이후 새 attachment 유형·문구 변형은 사전 규칙대로(try1 → try2 1회, try2 → 실험 INVALID). try3 없음. A1b1·A1b2 try1 산출물은 새 검사기에서 CLEAN이 되더라도 채택·대체·병합·kappa·민감도·비교 어떤 용도로도 열람·사용 안 함, try2 실패 시 try1로 되돌아가지 않음. 채택 세션 4개 모두 검사기 034d8114로 재검사 기록. 세션별 silent_turn_reminder 주입 여부·위치(직전·직후 Write), 배치별 fact 수·kappa는 보고만
- try2 실행: `nohup bash ~/medmap_core_kb_runner/run_stage1.sh <A1b1|A1b2> 2 > ~/medmap_core_kb_runner/logs/<job>.try2.stdout.txt 2>&1 &`, 실행 직전 검사기 SHA 034d8114 확인
- A1b3·A1alt try1 검사기 034d8114 재검사: 위 출력(둘 다 CLEAN 기대)
- 10회차 RUN(20261002_193851, lock 735922d0cf50) 후 try2 전 점검(운영자 수동, guard 보완): 봉인 sha256sum -c OK·SEALED.txt 존재(A1b1·A1b2), CLI 2.1.287, 검사기 034d8114, out/A1b1·A1b2 비어 있음
- 봉인 밖 사본 처리: preflight/syn_reminder_{alttext,alttype,extrakey}.jsonl(A1b1 try1 transcript 복사본)의 Write 내용·tool 결과·텍스트를 열람 없이 기계적으로 [REDACTED] 처리 후 쓰기 금지(전후 SHA: preflight/syn_reminder_{before,after}_redact.sha256), 합성 대조 판정 불변(3종 INVALID). 원본 try1 transcript 쓰기 금지 + SHA: fca3e77f…(A1b1) e84d0882…e613, af377929…(A1b2) a41ec3f0…e25a — 열람 금지
| A1b2 | 2 | 19:39:09 | 19:46:28 | 0 | (logs) | claude-opus-5-5 | CLEAN(silent_turn_reminder 정확 일치 예외 적용), coverage 0 누락 | 덮어쓰기 0·part30 0·요약 0 | 2.77 |
| A1b1 | 2 | 19:39:09 | 19:48:56 | 0 | (logs) | claude-opus-5-5 | CLEAN(같은 예외), coverage 0 누락 | 덮어쓰기 0·part30 0·요약 0 | 3.60 |

## 2. Stage 1 완료(채택 = A1b1 try2, A1b2 try2, A1b3 try1, A1alt try1)
- 호출 6/14, 정가 환산 합계 약 $15.66(추정, 청구액 아님)
- 산출물 동결: `~/medmap_core_kb_ws/stage1/STAGE1_OUT_SHA256SUMS`(파일 읽기 전용)
- 기계 점검: A1 339 fact(A1b1 160·A1b2 123·A1b3 56), A1alt 51 — JSON 오류 0, 스키마 위반 0, unit_id 존재 100%, quote가 해당 단위 원문 부분 문자열 337/339(A1b2 2건 불일치 → 검증 B 대상)
- 1단계 kappa(사전 고정 셀 34 × SAMPLE20 509단위) = 0.659 [95% CI 0.523–0.764], 양쪽 일치 양성 셀 31(A1 54, A1alt 40). 교차 모델 재현성(입력 맥락 비대칭 포함), 판정 미사용
