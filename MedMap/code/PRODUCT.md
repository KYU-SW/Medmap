# MedMap — Product truth

> 개정 2026-10-02(v5 정렬). 근거: 개인 기획 문서 `MedMap_최종방향_v5.md`(비공개, 이 저장소에 미포함) + 저장소 master 코드에서 확인된 사실.
> 이전 판(2026-09-23, 환자용 IG 앱 기준)은 git 이력에 보존. 시각 방향은 여기 담지 않는다.

## Identity (최상위 목표)
**MedMap is a doctor-facing diagnostic safety net that continuously checks whether a working diagnosis remains consistent
with the patient's symptoms, history, temporal changes, and recovery trajectory.**

환자가 제공한 증상과 시간에 따른 변화를 축적하고, 진료 전·중·후 정보를 연결해, 의사가 세운 현재 진단(Working Diagnosis, WD)이
환자 소견을 계속 충분히 설명하는지 확인하고, 설명되지 않는 소견이나 충돌이 있을 때만 재검토를 돕는 **의사용 진단 안전망**.

- 환자용 자가진단 앱이 아니다. 환자 쪽 기능은 Doctor MedMap에 정보를 공급하는 **intake / companion**.
- **위 목표의 핵심(WD가 소견을 설명하는지 판단)은 아직 구현·검증되지 않았다**(아래 "미구현·미검증").

## Users and jobs
- 주 사용자: **의사**(Doctor 화면 `#/doctor`). 환자 정보를 받아 현재 진단을 먼저 입력(또는 건너뜀)한 뒤 독립 모델의 감별 후보와
  후보를 구분할 추가 정보(질문 최대 3개)를 본다.
- 환자(intake/companion): 자유 텍스트 또는 음성으로 증상 입력 → 매퍼 후보 확인 → 시작 질문 → 요약 → 의사에게 인계.
  **환자 화면에는 진단 후보·확률을 보이지 않는다**(2026-10-01, master `08cbbd3`).
- 범위 밖: EMR 연동, 계정·로그인, 진료예약, 채팅, 치료·약 추천, 응급도 판정.

## 구현됨 (master `08cbbd3` 기준, 기반 인프라)
| 영역 | 내용 | 근거 |
|---|---|---|
| 환자 intake | 자연어 매퍼(v1.2) → 확인 → exact-k3 시작 → IG 질문 ≤3 → 요약(새로고침 복원) | `/v1/intake/extract`, `/v1/session/{start,answer,resume,summary}` |
| 음성 입력 | 기존 녹음 STT(`/v1/stt/transcribe`, 로컬 Whisper) + 스트리밍 STT(로컬 CT2 worker, 플래그 `MEDMAP_STT_STREAMING`) | M1 PASS(T_partial WS p95 ≤600 ms), 오프라인 release gate OK |
| 인계 | 같은 브라우저 `#/handoff` → `#/doctor`, 8자리·15분·1회용 번호(서버 메모리만, 플래그 `MEDMAP_HANDOFF_CODES`), JSON 불러오기 | `/v1/handoff/{status,codes,claim}` |
| Doctor 화면 | blind WD 게이트(WD 입력 전 후보 비공개) · 확률 없는 감별 후보 5/8 · 의사가 답하는 IG 질문 ≤3 → 재계산 · 환자 요약 · "준비 중" 6개 슬롯 | `/v1/doctor/{diagnoses,view,answer}` |
| 품질 | 한국어 표시(영어 노출 0) · 성능 회귀 gate(`scripts/perf_gate.py`) · 네트워크 차단 release gate · 통합 QA(2026-10-01) | e2e 전종 |
| 엔진 | 49질환 모델(DDXPlus 합성 데이터, k3/k5/k10) · 내부 정보이득(IG) 다음 질문 | `medmap/` |

## 미구현·미검증 (구현된 것처럼 쓰지 않는다)
| 기능 | 상태 |
|---|---|
| Working Diagnosis Validation(WD가 소견을 설명하는가) | **미구현·미검증**. Doctor 화면은 WD와 후보의 일치 여부를 판단하지 않는다 |
| Diagnosis Coverage | 미구현(질환별 근거 지식 없음) |
| Unexplained Finding Detection | 미구현 |
| Missed Alternative Detection | 미구현(중증도 지식 없음) |
| Recovery Deviation / Timeline / 진료 후 추적 | 미구현(환자 정보 영속 저장 금지 결정) |
| Disease Knowledge Layer | 설계만(검수자 부재로 보류, 브랜치 `design/disease-knowledge-layer`) |

## 연구 결과의 의미 (혼동 금지)
- **STEP13B 외부 지식 verifier = NO_GO**(AUROC 0.478, 판정 가능 오답 23 %). "외부 지식으로 틀린 진단을 잡는다"는 아직 성립하지 않았다.
- **STEP16B IG = GO**의 의미: 합성 환자(내부 holdout)에서 **모델 top1 오답이 IG 질문 답을 공개한 뒤 정답으로 회복된 비율**
  (1문항 0.459 vs RANDOM 0.053). 의사 오진 탐지가 아니며 외부·임상 검증이 아니다.
- 실험 A(S2 AUROC 0.917)는 같은 데이터로 학습한 두 모델의 일치도이지 탐지 상한이 아니다(RG 심사 C2).

## 주장 금지
- 오진 감소·환자 안전 개선·임상 진단 정확도 향상(검증 없음). "오진입니다", "진단이 틀렸습니다", "최종/확정 진단" 표현 금지.
- 모델 top1 ≠ 의사 WD 를 "의사 진단 오류"로 해석하지 않는다.
- 합성 데이터(DDXPlus) 결과를 실제 환자 성능으로 표현하지 않는다.

## Hard constraints (현재 계약)
- 추가 질문 최대 3개(`MAX_QUESTIONS`). `/v1/session/start`는 exact-k 상태만(k3 = 초기 evidence 1 + 추가 관측 정확히 3).
- 세션 source of truth = `PatientState`(`medmap-session-v1`). 확률·다음 질문·IG는 매번 다시 계산되는 파생값.
- intake에서 확인했지만 start에 들어가지 못한 답(cache)은 **자동 적용하지 않는다**(IG가 그 질문을 고를 때만 확인 후 반영).
- 수집 정보: age, sex, 임상 답변. 이름·연락처 등 PHI 저장 금지. 인계 번호는 서버 메모리 ≤15분, 디스크·로그 저장 없음.
- OFFLINE_ON_PREM_FIRST: 런타임 외부 호출·다운로드·telemetry 0. REALTIME_FIRST: 지연은 end-to-end p50/p95로 측정, 목표 하향 금지.
- 모델은 런타임에 재학습하지 않으며 `model_context`는 자동 전환하지 않는다.

## 현재 우선순위 (2026-10-02)
1. 문서 정렬(이 문서) · Doctor 화면에 환자가 확인한 소견 전체 표시(표시만, 모델 입력 불변)
2. STEP13B 실패 분석 정리 → **작은 범위 Diagnostic Safety Net 실험 사전등록**(흉통군 후보, Research Guardian)
3. 보류: 녹음 키트·Adaptive Endpoint·추가 STT 최적화·웨어러블·회복 추적·Timeline·데모 편의 기능 (코드·문서는 보존)

## Stack
React 19 + Vite(`medmap-web/`) · FastAPI(`medmap/api*.py`) · 로컬 Whisper(HF) + CT2 worker(`~/stt_ct2_env`).

## Terminology (화면 문구)
- 금지: "최종 진단", "AI가 진단했습니다", "오진", 순위 "1위/2위". 내부 오류 코드(`MEDMAP_*`) 화면 노출 금지.
- 의사 화면: "현재 정보에서 독립 모델이 고려한 감별 후보", "목록에 없는 질환이 배제됐다는 뜻이 아닙니다".
