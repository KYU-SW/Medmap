# MedMap Disease Knowledge Layer (Phase D) — 설계 rev0

- 작성 2026-10-01 · 상태: **초안, K1 결정됨(검수자 없음 → 개발 모드 전용), D1 착수 보류(설계만), K2~K4 대기(§10)** · 구현 0
- 상위: `2026-09-29-medmap-doctor-mode-foundation.md` §9·§12(Phase D, 선행: 별도 연구 트랙)
- 원칙: OFFLINE_ON_PREM_FIRST · 근거 없는 임상 판단 금지(HANDOFF §2 2026-09-29) · 외부지식 부재 ≠ 음성(open-world) · LLM 작성 지식의 production fact 사용 금지

## 0. 한 줄 정의

질환 49개 각각에 대해 **출처 원문 인용 + 사람 검수 승인**이 붙은 사실(fact)만 담는 오프라인 지식 저장소. Doctor의 진단 검증(E)·설명 범위(F)·놓친 위험 질환(I)의 유일한 근거 층.

## 1. 하지 않는 것

- 다음 질문 선택기 역할: STEP13B verifier NO_GO(AUROC 0.478), STEP16A·16B 프로필 selector NO_GO(Profile−IG −0.0875 / −0.2171) → **질문 선택은 내부 IG 유지**, 이 층은 관여 안 함
- 확률·점수 합산: HSDN TF-IDF·공출현·빈도를 확률로 부르거나 합산 금지(기존 규칙 승계)
- 부재 해석: 지식에 없는 증상 = "알 수 없음". "없으니 아니다" 판정 금지
- 검수 전 사실의 화면 노출(개발 모드 제외, §6)
- 동결 파일 수정: `exp/step15_v2_blind_profile/00~08`, `PROFILE_FREEZE_V2.json` — 읽기·복사만
- 런타임 외부 조회·다운로드·LLM 호출

## 2. 이미 있는 자산 (재사용)

| 자산 | 내용 | 상태 |
|---|---|---|
| `exp/step15_v2_blind_profile/` | 10질환 · fact 367 · 출처 34(Tier1 22) · 인용문 원문 대조 367/367 · 충돌 그룹 8 · 스키마(dataclass 검증) | 동결, **사람 검수 0/367**, 매핑 review 큐 237 |
| `06_HUMAN_REVIEW_SHEET.csv` | approve / corrected_value / reviewer_note 열 | 공란 |
| `07_scaleup_estimate.csv` | 49질환 추정: 출처 ≈167 · fact ≈1,798 · 검수 필요 ≈1,000 · 수동 확보 문서 ≈49 | 선형 외삽(추정) |
| `data/` | UMLS 2026AA·SNOMED·HPO·HSDN·MedlinePlus·DisMech·Wikidata | 개념 매핑 보조만(사실 출처 아님) |
| `medmap/data/terminology_ko.json` | 49질환 한국어 표시명 | 정본 |

## 3. 사실(fact) 형식 — v2 스키마 확장

v2 열 전부 유지 + 추가:

| 추가 열 | 의미 |
|---|---|
| `evidence_id` / `value_id` | DDXPlus 질문(E_…)·값(V_…) 매핑. 없으면 공란(질문에 없는 정보 = 화면 설명용만) |
| `mapping_level` | EXACT / PARTIAL / NONE (PARTIAL은 검수 필수) |
| `role` | core / supporting / important_negative / red_flag / severity / course |
| `review_status` | unreviewed / approved / corrected / rejected |
| `reviewer_id` · `reviewed_at` | 검수자 식별(이름 대신 코드)·날짜 |
| `kb_version` | 동결 버전(SHA 고정) |

- 질환 단위 표(49행): `urgency_class`(즉시 위험 / 당일 평가 / 일반) + 출처 인용 + 검수 상태 → Phase I 근거
- 충돌: 평균 금지, 행 분리 + `conflict_group_id` 유지(v2 방식)

## 4. 만드는 과정

1. 출처 확보(개발 중 다운로드 허용 범위): Tier1(정부·학회 가이드라인) 우선, 원본 파일 + SHA256 + 접근일 + 라이선스 기록. 차단 문서는 수동 확보 요청 목록
2. 추출: 원문에서 사실 행 작성 + **인용문 원문 문자열 대조 자동 검사**(불일치 = 빌드 실패). 작성 보조에 Claude 세션 사용 가능하나 결과는 `unreviewed`로만 들어감
3. 매핑: evidence_id·value_id 후보 자동 제안(UMLS·용어) → PARTIAL·NONE 표시
4. **사람 검수**: 검수 시트(CSV 또는 로컬 검수 화면) → approve / corrected / rejected. 승인 전 사실은 production 미사용
5. 동결: `kb_version` + SHA256 목록 → `medmap/data/knowledge/`에 오프라인 번들
6. 검사(자동): 출처 없는 fact 0 · 인용 대조 100% · 스키마 오류 0 · 질환별 독립 기관 ≥2 · 승인 fact 비율 표

## 5. 단계 (각 단계 끝에 사용자 확인)

| 단계 | 범위 | 산출 | 사람 검수 필요량(추정) |
|---|---|---|---|
| D1 | **질환 위험도 표 49행**(urgency_class + 출처) | Phase I(놓친 위험 질환) 최소 근거 | 49행 |
| D2 | v2 10질환 → 새 스키마 이관 + evidence 매핑 | Phase E 시범(10질환) | 367 fact 중 review 표시분 ≈204 + 매핑 PARTIAL |
| D3 | 나머지 39질환 수집·추출 | 49질환 전체 | ≈800 |
| D4 | Doctor 연결(E·F·I) | 각 Phase 별도 spec | — |

## 6. Doctor 화면 사용 규칙(D4에서 확정)

- `approved`·`corrected`만 사용. 화면에 출처 기관·연도 표시, 원문 인용은 펼쳐 보기
- 문구: 판정형 금지("이 진단이 틀립니다" 금지) → "이 진단의 출처상 흔한 소견 중 아직 확인 안 된 것: …" 같은 **확인 권유형**
- blind 원칙 유지: 의사 WD 입력 전 지식 기반 비교 표시 안 함
- 개발 모드(`MEDMAP_KB_DEV=1`)에서만 unreviewed 표시, "검수 전" 배지 필수

## 7. 평가(연구 트랙, 주장 범위)

- 측정 가능: 지식 coverage(49질환 × DDXPlus evidence 중 승인 fact로 덮인 비율) · 승인률 · 출처 Tier 분포 · 매핑 EXACT 비율
- **주장 금지**: 임상 정확도·진단 성능 향상(별도 사전등록·fresh split·검수 완료 전)
- E·F·I의 효과 검증은 각 Phase에서 Research Guardian 절차(rg-plan → rg-gate)

## 8. 위험

| 위험 | 대응 |
|---|---|
| 검수자 부재 → 승인 0 → 화면 기능 0 | §10 K1 결정. 검수 없이는 D4 진행 불가 |
| 가이드라인 원문 차단(협심증·PSVT 등 v2 사례) | 수동 확보 요청, 정부 페이지 보완, Tier 표시 |
| DDXPlus 시뮬레이터 순환(질환 프로필에서 생성된 데이터) | 지식 출처는 외부만, DDXPlus `release_conditions.json` 사용 금지(기존 규칙) |
| 라이선스(교과서·유료 가이드라인) | 사실 요약 + 짧은 인용만, 원문 재배포 안 함, `license_status` 기록 |
| 범위 폭증(≈1,800 fact) | D1(49행) → D2(10질환) 순으로 작게 시작 |

## 9. 무변경 계약

- 매퍼·엔진·IG·session 스키마·Doctor 루프·기존 endpoint 불변. 지식층은 새 파일(`medmap/knowledge/**`, `medmap/data/knowledge/**`)만 추가
- PHI 없음(질환 지식만)

## 10-0. 결정 기록

- **K1(2026-10-01, 사용자): 검수자 당분간 없음** → 지식층은 **개발 모드 전용 연구 자산**. 모든 fact `unreviewed`, 제품 화면(D4) 사용 금지, 개발 모드(`MEDMAP_KB_DEV=1`)에서만 "검수 전" 배지와 함께 표시. 검수자 확보 시 §4-4부터 재개(형식·시트는 지금부터 검수 가능한 상태로 유지)
- **(2026-10-01, 사용자) D1 착수 보류 — 설계만 보존.** 검수자 확보 또는 사용자 재지시 시 D1부터

## 10. 사용자 결정 필요

| ID | 질문 | 추천 | 이유 |
|---|---|---|---|
| K1 | 사람 검수자 | 의사(또는 임상 전공자) 1인 이상 확보 | 승인 없으면 화면 사용 0. 불가 시 "개발 모드 전용 연구 자산"으로 범위 축소 |
| K2 | 첫 단계 | D1 위험도 표 49행 | 검수량 최소(49행), Phase I 근거 |
| K3 | 출처 범위 | Tier1(정부·학회) 우선 + Tier3 교과서는 보조 표시 | v2 방식, 신뢰도 표시 |
| K4 | 검수 도구 | CSV 시트(기존 06 형식) | 추가 개발 0. 검수 화면은 검수 규모 커지면 |
