# MedMap Phase A — Illness Episode (설계 rev2, 2026-10-01)

상태: **rev2 · 결정 6개 완료 · 구현 없음(착수는 사용자 승인 후)**. 이번 범위 = §0-A(S1 기기 간 인계). §1–§15 는 영속 Episode(S2) 참고용.

## 0. 결정 반영(rev1)

- **D1 = S1 인계만 임시 저장**(사용자, 2026-10-01). 영속 Episode(S2: 재방문·타임라인·WD 이력·Observation 저장)는 **보류** — §4·§9·§10 저장·보존·암호화 내용은 후속(S2 결정 시) 참고용으로만 남긴다.
- Phase A 이번 범위 = **기기 간 인계(환자 휴대폰 → 의사 PC)**. PHI 원칙: "저장 금지" 유지 + 예외 1개 — 인계 대기 중인 세션을 **서버 메모리에만 최대 30분**, 의사가 열면 즉시 삭제(디스크·DB·로그 0).
- S1 구현 윤곽:
  - 저장소 = 프로세스 메모리 dict(서버 재시작 시 대기 인계 소멸 — 의도). 파일·SQLite·암호화 키 없음
  - 내용 = 지금 `#/handoff` 가 sessionStorage 에 두는 것과 같음: `medmap-session-v1` + 확인된 cache(sanitizeCache). 원문 자유 텍스트·전사문 없음
  - 코드 = 6자리 숫자, TTL 30분, 1회용(열면 삭제), 만료·오입력 응답 동일, claim 속도 제한(전역·IP)
  - 동시 대기 상한(예: 50) — 메모리 상한
  - 기존 같은 브라우저 인계·JSON 가져오기 유지, 플래그 `MEDMAP_HANDOFF_CODES=1` 일 때만 활성
- 결정(사용자, 2026-10-01): **D1 S1** · D2 코드만(식별자 없음) · D3 원문·전사문 저장 안 함 · **D4 로그인 없음(코드만)** · **D5 8자리·15분** + 서버 전체 실패 20회 → 5분 잠금 · **D6 코드만(QR 후속)**.
- 정정(2026-10-01): D4 질문의 "무작위로 맞힐 확률 약 0.03%"는 대기 코드 1개 기준. 대기 N개면 약 N배 → 8자리·15분·전체 실패 잠금으로 보완(대기 50개·잠금 없이 분당 10회 가정 시 6자리 30분 ≈ 1.5% → 8자리(1억 가지)·15분·전체 실패 20회 잠금이면 15분 시도 ≈ 40회 → 대기 50개 ≈ 0.002%, 대기 1개 ≈ 0.00004%, 추정. rev2 첫 기록 "0.0005% 미만"은 과소평가였음).

## 0-A. S1 기기 간 인계 설계(이번 구현 범위)

### 서버 — 새 파일만(`medmap/handoff_codes.py`, `medmap/api_handoff.py`), `api.py` 는 include_router 1줄
- `HandoffStore`(메모리): 코드 8자리(`secrets.randbelow`, 대기 중 중복 없음) → {session, cache, expires_at}. TTL 900 s · 대기 상한 50 · **claim 시 즉시 삭제(1회용)** · 만료 항목은 매 호출 정리 · 서버 전체 실패 20회/5분 창 → 5분 잠금 · 시계 주입(테스트)
- 플래그 `MEDMAP_HANDOFF_CODES=1` 일 때만 라우터 활성(아니면 404, 현재 동작 그대로)
- `GET /v1/handoff/status` → {enabled, ttl_s}
- `POST /v1/handoff/codes` {session(medmap-session-v1), cache} → 201 {code, expires_in_s}. session 은 기존 `deserialize_session` 으로 검증(무효 → 400), cache 는 서버에서도 evidence_id·status 만 남김(sanitize), 본문 크기 상한. 대기 상한 초과 → 503 `HANDOFF_CAPACITY`
- `POST /v1/handoff/claim` {code} → 200 {session, cache} 후 삭제 · 잘못됨·만료·사용됨 **모두 같은 404** `HANDOFF_CODE_INVALID` · 잠금 중 429 `HANDOFF_LOCKED`
- 로그·응답 헤더에 코드·세션 내용 없음(이벤트·개수만). 디스크 쓰기 0

### 프론트
- 환자 인계 완료 화면(`#/handoff`, `handoff-done`): [다른 기기(진료실)로 보내기] → 코드 "1234-5678" + 남은 시간 + [새 번호 받기]. 코드는 화면에만(저장소 쓰기 없음). 기존 [의사 화면 열기](같은 브라우저) 유지
- Doctor 불러오기 화면: "환자 번호로 불러오기" 8자리 입력(하이픈 자동) → claim → 기존 가져오기와 같은 경로로 열기(새 사본, cache 포함). 오류 문구 한국어: 번호 확인 / 잠시 후 다시
- `useDoctorSession` 에 `importPayload({session, cache})` 추가(기존 `importSession` 동작 불변)

### 검증
- 단위: 저장소(1회용·만료·상한·중복 없음·잠금·해제) · API(플래그 off 404, 무효 세션 400, 잘못/만료/사용 동일 404, 잠금 429, 로그 무기록 대조군)
- 프론트: 코드 표시·새 번호·오류, Doctor 번호 입력 → 열림(cache 포함) · 저장소 쓰기 0
- e2e: **두 브라우저 컨텍스트**(환자 휴대폰 390 → 의사 PC 1280) 번호 인계 → blind → 후보 → IG, 같은 번호 두 번째 사용 404, 영어 0, 기존 e2e 전종 회귀
- 성능: codes·claim 서버 p95 ≤ 20 ms(목표, 실측) · 오프라인: release gate(새 의존성 0이지만 새 endpoint 포함 재실행) · Doctor T_next 회귀 gate 선행 문서: Doctor Mode Foundation spec rev4 §12 Roadmap(Phase A).
브랜치: `design/illness-episode`(master `f39a60f` 기준). master 병합·구현 착수는 사용자 승인 후.

## 0-B. 구현 결과(2026-10-01, 브랜치 `feat/handoff-codes`, master 미병합)

- 서버 `ed982c1`: `medmap/handoff_codes.py`(메모리 저장소) · `medmap/api_handoff.py`(status·codes·claim) · `api.py` include 1줄. 테스트 19(저장소 9 + API 10), mutation 4건(1회용·잠금·cache 정리·플래그) 모두 검출
- 프론트 `b29690b`: `api/handoffClient.js`(새 파일, client.js 불변) · `handoff/SendToDevice.jsx` · `doctor/sections/HandoffCodeImport.jsx` · HandoffApp·DoctorApp 에 배치. 테스트 +9
- **계획 대비 변경**: `useDoctorSession.importPayload` 추가 안 함 — 기존 `importSession` 이 `{session, cache}` JSON 을 이미 받으므로 그대로 재사용(useDoctorSession 무변경)
- e2e `handoff-code.e2e.mjs`(휴대폰 390 → PC 1280 별도 컨텍스트): 잘못된 번호 안내 → 번호 인계 → blind 유지 → 건너뛰기 → 후보 5 → IG 1 답(환자 cache "환자가 이미 말한 내용" 전달) → 다른 PC 재사용 거부 · 저장소에 번호 없음 · 영어 0 · 넘침 없음 → `HANDOFF_CODE_E2E_OK`. 서버 처리(Resource Timing) codes 2 ms · claim 1.7–1.8 ms(목표 ≤ 20)
- 플래그 ON 서버로 기존 e2e 5종 회귀: E2E_OK · FLOW · SUMMARY · ENGLISH_AUDIT(0) · DOCTOR 전부 통과. backend 286(skip 3) · vitest 247 · build
- 미실행: release gate(GPU 필요 — 다른 세션 GPU 우선권 기간), 실기기(휴대폰↔PC 같은 Wi-Fi, `--lan` 은 사용자 실행)
- 독립 리뷰(code-reviewer): **APPROVE**, CRITICAL·HIGH 0. 반영 `213c11c`: MEDIUM 세션 크기 상한 32 KB(메모리 15분 보관 → 대량 요청으로 메모리 채우기 방지, 413 `HANDOFF_TOO_LARGE`) · LOW 저장소 첫 생성 잠금(테스트가 느린 생성자로 경합을 실제로 만들어야 검출 — 처음 테스트는 검출력 없었음). backend 288
- **알려진 절충(사용자 확인 필요)**: 전체 실패 잠금은 로그인 없는 구조에서 추측을 막지만, 같은 병원망의 누구든 실패 20회로 인계를 5분씩 반복해 막을 수 있다(서비스 방해). 대안: IP별 잠금 병행(추측 방어 약화) · 의사 로그인(D4 재검토) · 현 상태 유지(내부망 전제)
- **절충 처리(2026-10-01, 사용자 "알아서 문제없게" 위임)**: 전체 잠금(20회/5분)은 **그대로 두고** 기기(접속 주소)별 잠금을 앞에 추가 — 한 기기 실패 5회/5분 → 그 기기만 5분 잠금, 잠긴 기기의 시도는 전체 실패에 세지 않음. 결과: 기기 1대로는 전체 인계를 막을 수 없음(최소 4대 필요), 추측 상한(전체 20회/5분)은 불변(추측 방어 약화 없음). 주소는 메모리만·로그 없음. uvicorn 기본(proxy_headers=True)은 루프백 접속의 X-Forwarded-For 로 주소를 바꾸므로(WSL localhost 전달·portproxy 경유 시 위조로 기기별 잠금 우회 — 리뷰 MEDIUM, 실서버 대조 확인: 플래그 없음 200 / 있음 429) `demo_serve.sh`는 `--no-proxy-headers`로 띄움. 한계: 역방향 프록시 뒤에서는 모두 같은 주소 → 기기별 잠금이 사실상 5회 전체 잠금이 됨(현 demo_serve는 프록시 없음). 브랜치 `feat/handoff-client-lock`

## 1. 배경 — 지금 구조

- 서버 무상태(stateless). 세션 원본 = 클라이언트가 보내는 `medmap-session-v1`(나이·성별·model_context·initial·answers·asked_question_ids).
- 환자 → 의사 인계 = **같은 브라우저 sessionStorage**(`medmap.handoff.*`) 또는 JSON 붙여넣기·파일.
- 기존 결정: 시작 전 입력 브라우저 저장 금지(PHI 저장 금지, 2026-09-27) · 서버 임시 저장(코드/QR) 보류(2026-09-29, "저장소·보존·인증 설계 필요").
- 한계:
  - 다른 기기(환자 휴대폰 → 진료실 PC) 인계 불가
  - 시간축 없음(언제 말했는지, 재방문 없음)
  - 답의 출처 구분 없음(환자 보고 vs 의사 확인 — 프론트 표시에만 존재)
  - 기본 환자 흐름 세션 식별자 없음(같은 입력 반복 시 Doctor 사본 재사용)
  - WD 이력·공개 시점 기록 없음(Phase H 선행 조건)

## 2. 목표 / 비목표

목표(Phase A):
- **Illness Episode**: 한 번의 아픈 경험 단위 기록, 병원 내부 서버 보관
- 기기 간 인계: 환자 휴대폰 → 의사 PC(짧은 코드, 선택적 QR)
- 관측의 **출처·시각·확정 상태** 보존(Observation)
- 의사 인증·권한(환자 기록 열람 제한)
- 보존 기간·삭제·감사 기록
- Timeline(B)·Blind 2nd opinion(H)·Turning point(K)·Visit(L)의 데이터 기반

비목표(Phase A):
- 타임라인 화면·시간 추론(B·C)
- EMR 연동·HL7/FHIR 교환(용어만 참고)
- 병원 SSO·조직 계정 체계
- 진단 로직·IG·매퍼·모델 변경
- 환자 화면 재설계(P)

## 3. 원칙 적용

| 원칙 | 이 설계에서 |
|---|---|
| OFFLINE_ON_PREM_FIRST | 저장 = 병원 내부 서버 로컬 파일(SQLite). 외부 DB·클라우드·CDN 0. 새 의존성 0(sqlite3·cryptography·hashlib 기존). release gate 재실행 |
| REALTIME_FIRST | 저장 쓰기 p95 ≤ 20 ms(목표, 실측 필요). Doctor T_next 영향 ≤ +20 ms. 쓰기는 응답 경로 밖 불가 → 동기, 대신 작은 트랜잭션 |
| PARTIAL ≠ FINAL ≠ CONFIRMED | **CONFIRMED 만 저장**. PARTIAL·FINAL 전사문·음성 저장 금지. 매퍼 후보(확인 대기)도 저장 안 함 |
| PHI 최소화 | 이름·주민번호·연락처 저장 금지. 무작위 ID. 원문 자유 텍스트 저장 여부 = 결정 D3 |
| Blind WD | WD 입력·공개 시점을 사건으로 기록(H 대비). 현재 blind 게이트 동작 불변 |
| 기존 흐름 불변 | `medmap-session-v1`·7 endpoint·Doctor 3 endpoint 의미 불변. Episode 는 추가 경로. sessionStorage 인계는 fallback 으로 유지 |

## 4. 개념 모델

```
Episode(아픈 경험 1건, 무작위 id, 상태 OPEN|CLOSED, created_at, closed_at, retention_until)
 ├─ Encounter(접촉 1회: PATIENT_INTAKE | DOCTOR_REVIEW, started_at, actor)
 │   └─ Observation(사실 1건, append-only)
 │        evidence_id · status(POSITIVE|NEGATIVE|VALUE|NOT_APPLICABLE|UNKNOWN) · value
 │        source: PATIENT_INTAKE_CONFIRMED | PATIENT_BOOTSTRAP | DOCTOR_CONFIRMED_PATIENT_SAID | DOCTOR_ANSWERED
 │        recorded_at · encounter_id · supersedes(정정 시 이전 observation id)
 ├─ WorkingDiagnosisEvent(의사 WD 입력·건너뛰기·변경, at, 공개 전/후 표시) ← H 대비
 ├─ SessionSnapshot(`medmap-session-v1` 그대로, 버전·at) ← 기존 엔진 입력, 재현용
 └─ AuditEvent(누가·언제·무엇을 열람/기록 — 내용 없음)
```
- PatientState = Observation 의 **투영**(현재 규칙 그대로). 엔진은 지금처럼 session-v1 을 받는다(서버가 Observation → session-v1 조립).
- 정정은 덮어쓰기 금지, `supersedes` 로 새 Observation 추가(이력 보존).
- 시각은 서버 시계(UTC 저장, 표시는 KST).

## 5. 저장 방식 — 선택지(결정 D1)

| 안 | 내용 | Episode | PHI 위험 | 비고 |
|---|---|---|---|---|
| S0 현행 유지 | 서버 저장 없음, 같은 브라우저·파일 인계 | 불가 | 최소 | Phase A 불가 |
| S1 인계 전용 임시 저장 | 서버가 세션을 **최대 30분** 보관, 코드로 1회 전달 후 삭제 | 불가(인계만) | 낮음 | 기기 간 인계만 해결 |
| **S2 병원 내부 영속 저장(추천)** | SQLite 파일(내부 서버), 필드 암호화, 보존 기간 후 자동 삭제 | 가능 | 중간(통제) | PHI 원칙을 "저장 금지" → "최소·암호화·기한 저장"으로 **개정 필요** |
| S3 EMR 연동 | 병원 EMR 에 기록 | 가능 | 병원 체계 | 범위 밖(기관 협의) |

추천 이유: B·H·K·L 모두 서버 저장 전제. S1 은 S2 의 부분집합으로 먼저 구현 가능(단계 A-2).

## 6. 식별(결정 D2)

- Episode id: 128-bit 무작위(URL 안전). 순번·날짜 기반 금지(추측 방지)
- 인계 코드: 6자리 숫자 또는 4+4 문자, **TTL 30분·1회용·시도 5회 제한**, 의사 로그인 상태에서만 사용
- 표시용 식별: "45세 남성 · 10:32 접수" 수준. 실명·등록번호 없음
- 병원 등록번호 연결: 선택 필드(기본 꺼짐) — 결정 D2

## 7. 인증·권한(결정 D4)

| 역할 | 할 수 있는 일 | 인증 |
|---|---|---|
| 환자(휴대폰) | 자기 intake 로 Episode 생성·확정 답 추가(생성 직후 창 안에서만) | 없음 — 생성 응답의 **episode write token**(TTL 짧음)만 |
| 의사 | 코드로 Episode 열기·조회·확인·답·WD 기록·종료·삭제 | 로컬 계정(아이디·비밀번호, `hashlib.scrypt`), 세션 쿠키(HttpOnly·Secure·SameSite=Strict), 8시간 만료 |
| 관리자 | 의사 계정 추가·잠금, 보존 설정 | CLI 스크립트(웹 화면 없음) |

- 다른 의사의 Episode 열람: 기본 허용(같은 병원) vs 코드로 연 의사만 — 결정 D4
- 병원 SSO·LDAP: 후속(Phase A 범위 밖)

## 8. 인계 흐름(S2 기준)

```
환자 휴대폰: intake → 확인 → start → [의사에게 보내기]
   → POST /v1/episodes {session, confirmed_cache}  → {episode_id, handoff_code, write_token}
   → 화면: "진료실에서 이 번호를 알려 주세요: 482 913" (+ 선택 QR)
의사 PC(로그인): [환자 코드 입력] 482913 → POST /v1/handoff/claim → Episode 열림
   → 기존 Doctor 화면(blind WD → 후보 → IG 답) — 답·확인은 Observation(source 구분)으로 저장
```
- 코드 사용 후 즉시 무효. 만료 코드·잘못된 코드 응답 구분 없음(추측 방지)
- 기존 같은 브라우저 인계(`#/handoff`)는 그대로 유지(서버 저장 끔 설정에서도 동작)

## 9. 보존·삭제·감사(결정 D5)

- 보존 기간 기본값 후보: 7일 / 30일 / 90일 — 결정 D5. 기간 후 자동 삭제(행 삭제 + VACUUM)
- 의사 수동 삭제(즉시), 삭제도 감사 기록(내용 없음)
- 감사 기록: actor id·동작·episode id·시각만. 증상·답·WD 내용 없음
- 백업: 기본 없음(병원 IT 정책 따름) — 문서화

## 10. 보안

- 전송: 내부망 TLS(현 자체서명 → 병원 내부 CA 권장). 평문 HTTP 는 로컬 개발만
- 저장: Observation·Snapshot·WD 자유 텍스트 필드 **AES-GCM**(cryptography, 이미 설치) — 키는 서버 파일(0600) 또는 환경변수, DB 와 분리. 디스크 전체 암호화는 병원 IT 영역(권장)
- 로그: episode id 해시·동작·ms·코드만(현 원칙 유지). **`medmap.*` 로거 기본 handler 없음 확인(2026-10-01)** — 감사 기록은 DB 테이블로(로그 의존 금지)
- 요청 제한: 코드 claim 분당 제한, 로그인 실패 잠금
- CSRF: same-origin + SameSite=Strict + JSON only

## 11. API 초안(추가만, 기존 불변)

| 메서드·경로 | 역할 | 비고 |
|---|---|---|
| POST `/v1/episodes` | 환자 intake·start 결과로 Episode 생성 | 입력 = 현재 session-v1 + 확인된 cache. 응답 code·write_token |
| POST `/v1/handoff/claim` | 의사가 코드로 Episode 열기 | 의사 인증 필요 |
| GET `/v1/episodes/{id}` | Episode 요약(투영) | 의사 |
| POST `/v1/episodes/{id}/doctor/view` · `/answer` | 기존 Doctor view/answer 와 같은 계약 + 저장 | 내부는 기존 `run_session` 재사용 |
| POST `/v1/episodes/{id}/wd` | WD 사건 기록 | H 대비 |
| POST `/v1/episodes/{id}/close` · DELETE | 종료·삭제 | 의사 |
| POST `/v1/auth/login` · `/logout` | 의사 세션 | 로컬 계정 |

기능 플래그 `MEDMAP_EPISODES=1` 일 때만 활성(기본 꺼짐 → 현재 동작 그대로).

## 12. 사용자 결정 목록(하나씩 확인)

| # | 결정 | 추천 | 이유 |
|---|---|---|---|
| D1 | 서버 저장 허용·범위(S0/S1/S2) + PHI 원칙 개정 | **S2**, 단 A-2 에서 S1 부터 | Phase A 목적 자체가 저장 |
| D2 | 식별: 무작위 id + 코드만 / 병원 등록번호 연결 허용 | 무작위 + 코드만 | PHI 최소, 등록번호는 EMR 협의 후 |
| D3 | 환자 원문 자유 텍스트 저장 | **저장 안 함**(확정 Observation 만) | 원문 = 가장 식별 가능성 큰 PHI |
| D4 | 의사 인증 방식·열람 범위 | 로컬 계정 · 같은 병원 의사 모두 열람 | 단일 장비 시연 규모 |
| D5 | 보존 기간 | 30일 | 재방문 추적 최소 기간(확인 필요: 병원 정책) |
| D6 | QR 표시(새 의존성: JS QR 생성 라이브러리) | 코드만 먼저, QR 은 후속 | 의존성 0 유지 |

## 13. 단계(구현 계획 전 윤곽)

- A-1 결정 D1–D6 확정 → spec rev1
- A-2 저장소·암호화·보존 삭제(API 없음, 단위 테스트) + S1 인계 코드
- A-3 의사 인증 + claim + 환자 [의사에게 보내기] UI(390/1280, 한국어, 영어 0)
- A-4 Doctor 화면을 Episode 로(Observation 출처 표시, WD 사건)
- A-5 감사·보존 스케줄·관리 CLI · release gate · 보안 테스트
- 각 단계 TDD, 기존 e2e 전종 + 새 e2e(휴대폰→PC 코드 인계, 만료·오입력·타 계정)

## 14. 검증 기준(초안)

- 기능: 인계 성공·만료·1회용·시도 제한·권한 없는 열람 403·삭제 후 조회 불가·보존 만료 삭제
- 경계: PARTIAL·FINAL·매퍼 후보가 DB 에 0건(스키마·테스트로 보장), 원문 저장 0(D3=저장 안 함 시)
- 성능: 저장 쓰기 p95, Doctor T_next 회귀 gate(`perf_gate.py`) 통과
- 오프라인: `release_offline_check.sh` RELEASE_OFFLINE_OK
- 보안: 로그·감사에 증상·답·WD 내용 0(대조군 포함), DB 파일에서 평문 증상 0(암호화 확인)

## 15. 위험

- PHI 원칙 개정 자체가 가장 큰 결정 — 병원 개인정보 정책·IRB 와 맞는지 **확인 필요**(이 설계로 판단 불가)
- 로컬 계정 비밀번호 관리 부담(초기 비밀번호·분실)
- 키 분실 = 데이터 복구 불가(설계상 의도, 운영 문서 필요)
- SQLite 동시성: 단일 장비·소수 사용자 가정. 다중 서버는 범위 밖
- 기존 기본 흐름 세션 식별자 문제는 Episode 경로에서만 해결(기본 흐름 `useMedmapSession` 은 불변)
