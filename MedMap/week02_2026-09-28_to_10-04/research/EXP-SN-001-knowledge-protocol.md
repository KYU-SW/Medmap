# EXP-SN-001 질환 지식(KB) blind 작성 프로토콜 · 출처·라이선스 정책 — rev2

- rev1 2026-10-02 → **rev2 2026-10-02**: 역할 분리(작성자 A / 검증자 B / 매핑 C), LLM 기록 항목, 동결 순서 K0–K6, 라이선스 관문을 추가했다.
- 상태: **절차만 정의.** 실제 출처 번들 구성, 사실 작성, 매핑은 시작하지 않았다. **B-LIC·B-AUTH(prereg §10)가 풀리기 전에는 K0 이후 단계를 진행하지 않는다.**
- 이 KB는 연구용이다. 임상 검수가 아니며 모든 사실은 `review_status = unreviewed`로 둔다. 제품 UI에는 쓰지 않는다.

## 1. 라이선스 관문 (K0보다 먼저)
- 출처마다 `source_authority, access_url, publication/update date, copyright holder, license type, research use allowed, software/AI incorporation allowed, redistribution allowed, attribution requirement, production_allowed(YES/NO/UNCLEAR), research_only, permission_needed`를 기록한다. 현재 감사 결과는 literature §4에 있다.
- 출처를 K0 번들에 넣는 조건:
  - (a) 공식 정책이 연구 목적 열람과 짧은 인용을 허용하고,
  - (b) **AI가 그 원문을 읽는 방식(LLM 저자)을 쓸 경우** 그 사용을 허용하거나, 서면 허가를 받은 경우
  - (b)가 UNCLEAR이거나 NO이면, 그 출처는 **사람 저자만** 읽을 수 있다. 사람 저자도 없으면 그 출처는 쓰지 않는다.
- `LICENSE_UNCLEAR`는 허용으로 보지 않는다.
- 원문 파일은 저장소에 커밋하지 않는다. 경로·SHA·접근일만 기록한다. KB에는 짧은 근거 구간 또는 요지와 위치만 남긴다.

## 2. Blind — 저자 A·검증자 B·매핑 C가 보면 안 되는 것
평가 환자 행과 라벨·결과, 모델 혼동 행렬, top2·top3, 확신도·사후확률·순위, STEP13B 개별 오답, STEP17A 사례 출력, 임계 결과, 지식 추가 후 지표 변화, DDXPlus 시뮬레이터의 질환→소견 정의(`release_conditions.json`, `DIFFERENTIAL_DIAGNOSIS`), 저장소의 파생 판별표(`exp/step14*/04_*`, `exp/step15_v2_evaluation*`, failure-analysis §5 D4), `.claude/memory`, HANDOFF.

## 3. 허용 입력
1. prereg에서 미리 동결한 질환명과 쌍 목록(K1)
2. 승인된 외부 출처 번들(K0, §1 관문 통과분)
3. 중립 DDXPlus 질문 사전(질문 문구·값 코드만, 질환 연결 없음) — **매핑 C 단계에서만**

## 4. 역할
| 역할 | 하는 일 | 보는 것 |
|---|---|---|
| **AUTHOR A**(별도 독립 세션) | 출처에서 임상 사실을 추출한다. 근거 구간(span)·위치와 relation type을 기록한다. 확신도가 아니라 **출처 강도(Tier·근거 등급 원문)**를 기록한다. review_status = unreviewed | K0 번들 + K1 목록 |
| **VERIFIER B**(독립 세션, A와 다른 모델 또는 최소한 독립 context) | A의 결과를 원문과 대조해 `supported / unsupported / overclaimed / ambiguous`로 표시한다. 정식판 대조도 한다(사본·요약 경유 근거 해소) | A 산출물 + K0 원문 |
| **MAPPING C**(독립 세션) | B를 통과한 사실만 중립 질문 사전에 매핑한다. 매핑할 수 없으면 `UNOBSERVABLE`(clinical_importance는 유지) | 통과 사실 + 질문 사전 |

- 같은 모델·같은 세션을 A와 B로 쓰지 않는다(권장). 2차 일치도(B와 A의 relation 일치, kappa)를 보고한다.

## 5. Relation type (허용 목록)
`strongly_supports_A`, `weakly_supports_A`, `supports_B`, `conflicts_with_A`, `important_negative_for_A`, `more_typical_of_B`, `uncommon_for_A`, **`cannot_distinguish_without_test`**

- `cannot_distinguish_without_test`는 출처가 "병력만으로 불충분 / 검사 필요"라고 말한 경우에 쓴다(예: G1 §1.4.2, S1 §4.1, S6). 이 관계는 K 점수에서 0으로 두고, 해당 쌍의 `history_discriminable` 판정과 abstention(prereg §3.5)의 근거로 쓴다.
- 출처가 말하지 않은 "A보다 B에 특이적", "고위험", "이 질문으로 구별 가능" 같은 문장은 쓰지 않는다. 근거가 없으면 `UNSUPPORTED`나 `UNKNOWN`으로 둔다.
- prereg §4의 역할 점수표(strong/weak/conflicting/uncommon/important_negative)와의 대응은 K4에서 정해진 규칙으로만 한다. 규칙은 K1 동결 문서에 미리 포함한다.

## 6. 사실 최소 형식
`fact_id, disease_or_pair, finding, relation, source_id, exact_source_location, short_evidence_span_or_paraphrase, publication_update_year, authority_tier, license_status, clinical_importance(supported/UNKNOWN), medmap_observable(true/false/UNOBSERVABLE), ddxplus_evidence_id/value_code(C 단계, 없으면 공란), verifier_status, review_status=unreviewed, author_id/model_id, fact_version`

## 7. LLM 사용 시 manifest 기록
`provider, exact model, model version/date, system prompt hash, author prompt hash, source bundle hash, temperature/deterministic setting, output hash, author role, verifier role, mapping role, 세션 ID`. 이 기록은 임상 검수가 아님을 명시한다.

## 8. 동결 순서
K0 출처 번들 동결(라이선스 관문 통과분, SHA) → K1 질환·쌍 목록과 relation→점수 규칙 동결 → K2 저자 A 추출 → K3 검증자 B → K4 매핑 C → K5 KB manifest·hash 동결 → K6 Research Guardian 점검

- **K5 이후** 평가 결과(TUNE 포함)를 보고 사실을 고치면, 그 버전은 **exploratory revision**이다. 다시 confirmatory로 쓰려면 아직 쓰지 않은 새 평가 split(새 salt)과 재사전등록이 필요하다.
- K5 이후 시뮬레이터 정의와의 일치율(순환 정도)은 별도 단계에서 보고만 한다. KB는 수정하지 않는다.

## 9. 출처 Tier (rev1 그대로)
- T1: 정부·학회 진료지침, consensus, 근거 기반 지침
- T2: 체계적 문헌고찰·메타분석, 주요 peer-reviewed 리뷰, 학술 의학 참고서
- T3: 개별 연구(T1·T2 보충용만)
- 사용 금지: 블로그, 환자 커뮤니티, 출처 불명 페이지, snippet만, LLM 자체 지식, DDXPlus 정의, STEP13B 사례, 평가 결과를 보고 고른 사실
