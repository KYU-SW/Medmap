# EXP-00 메인 AI 그래프·트리 구조 설계

표기: **[사실]** 파일·코드로 확인 · **[문헌]** 논문·데이터 문서 근거 · **[가설]** 연구 가설 · **[제안]** 미검증 제안

## 1. 후보 구조 비교

| 안 | 구조 | 장점 | 한계 | 판정 |
|---|---|---|---|---|
| A | 증상 루트 동적 트리 | 문진 흐름과 같음, 설명 쉬움 | 같은 질환이 여러 가지에 복제됨. 경로 재사용 없음. 깊이가 확률처럼 오해됨 | 단독 채택 안 함. **질문 순서 표현용 뷰**로만 사용 |
| B | 질환 루트 평가 트리 | 질환별 필수 조건·아형·병기 표현 쉬움 | 초기 증상만 있을 때 시작점이 없음 | 규칙 층(rule layer)으로 사용 |
| C | 환자별 관계 KG | 관측·출처·시간 보존, 갱신 쉬움 | 단독으로는 질환 지식이 없음 | **필수 구성요소** |
| D | 질환별 관계 KG | 증상·검사·아형 공유, 관계 유형 표현 | 지식원 품질·순환(아래 3절)에 좌우 | **필수 구성요소** |
| E | 트리 + 그래프 혼합 | A·B 의 탐색 뷰 + C·D 의 공유 노드 | 구현 복잡도 | **추천** |
| F | 하이퍼그래프 | 다중 조건(AND) 1급 표현 | 도구·데이터 부족, 디버깅 어려움 | 보류. E 의 `Condition(AND/OR)` 로 대체 후 필요시 재검토 |

## 2. 추천: E = "공유 그래프 + 규칙 층 + 탐색 뷰"

```
[질환 지식 그래프 D]  증상·과거력·질환·아형·검사·소견 노드(각 1개, 공유)
        │  관계: SUGGESTS / ARGUES_AGAINST / EVALUATED_BY / YIELDS / SUBTYPE_OF / PARENT_QUESTION
        ▼
[규칙 층 B]  Rule(disease, subtype, stage, applicability=AND/OR 조건, subtasks)
        │  상태: SATISFIED / UNMET(명시적 불충족) / INDETERMINATE
        ▼
[환자 그래프 C]  Observation(node, status, source_id, observed_at, recorded_at, provenance)  — append-only
        │  상태 5종: POSITIVE / NEGATIVE / UNCERTAIN / NOT_TESTED / NOT_RECORDED
        ▼
[추론 층]  (a) 근거 충족도(규칙별 leaf 충족 비율)  (b) 질환 확률(베이즈·모델) — 서로 다른 값
        ▼
[탐색 뷰 A]  상향식(증상→후보) · 하향식(WD/후보→확인 질문·검사) — 동적 트리는 화면·로그용 투영
```

조건별 처리:

| 요구 조건 | 처리 방식 | 구현 위치 |
|---|---|---|
| 같은 질환이 여러 증상 경로에 등장 | 질환 노드 1개 공유, 경로는 간선 | `KnowledgeGraph.add_node` 유형 충돌 거부 **[사실: 테스트]** |
| 같은 검사가 여러 질환에 관련 | 검사 노드 1개 + `EVALUATED_BY` 간선 여러 개 | 동일 |
| 아형·병기·평가 단계 | `SUBTYPE` 노드 + `Rule.subtype_id/stage` | 스키마만 **[제안]** |
| 관계 유형 | `Rel` 열거형 | 스키마 |
| AND/OR | `Condition(op, items)` 재귀 | `evaluate` **[사실: 테스트]** |
| 양성·음성·불확실·미검사·미기록 | `Status` 5종. 뒤 3종은 절대 음성 아님 | **[사실: 테스트·변이 검사]** |
| 출처·시간 보존 | `source_id`, `observed_at`, `recorded_at`, `provenance`(원문 위치만) | 스키마 |
| 새 검사 결과로 갱신 | append-only + `view(as_of)` 재계산 | **[사실: 테스트]** |
| 탐색 경로 재사용 | 규칙 평가 결과를 (rule_id, 관측 버전) 키로 캐시 | **[제안]** 미구현 |
| 안전한 가지치기·재활성화 | UNMET 일 때 하위 작업만 비활성, 새 관측 시 재평가 | **[사실: 테스트]** |

## 3. 핵심 원칙(EXP 전체 고정)

1. **트리 깊이 ≠ 질환 확률.** 근거 충족도(`RuleResult.satisfaction`)와 확률은 다른 필드다. 충족도는 확률로 보고하지 않는다.
2. **부정 증상으로 질환을 삭제하지 않는다.** 부정 소견은 확률 갱신(우도)에만 쓴다. 후보 집합에서의 제외는 "우선순위 하향(재활성 가능)"만 허용한다.
3. **가지치기 = 평가 규칙의 하위 작업 비활성화.** 필수 적용 조건이 *명시적 NEGATIVE* 일 때만. UNCERTAIN·NOT_TESTED·NOT_RECORDED 는 INDETERMINATE.
4. **같은 source_id = 독립 근거 1개.** 판독지 1건에서 나온 소견 여러 개, 같은 검체의 파생 수치를 중복 계산하지 않는다(우도 결합 시 source 단위 묶음).
5. **시간 누출 금지.** 판단 시점 t 에는 `recorded_at ≤ t` 관측만 사용(MIMIC: lab=storetime, 판독=storetime; NBI B0d 의 STUDY/REPORT 두 층 규칙과 동일).
6. **WD 는 탐색 기준, 정답 아님.** WD 는 후보 순서를 앞당기고 확인 질문을 우선하지만 다른 후보를 지우지 않는다. 오답 WD 상황의 누락률을 반드시 따로 평가한다.
7. **지식원 순환 금지.** DDXPlus `release_conditions.json` 은 환자 생성기에 쓰인 지식표다 **[문헌: DDXPlus 논문]**. 이것을 질환 그래프로 쓰면 평가가 순환한다 → 주 실험에서는 train 분할에서 추정한 통계 그래프와 외부 지식(HSDN·HPO)만 사용, conditions.json 그래프는 "시뮬레이터 상한(oracle)" 보조 팔로만.
8. **검사 미시행은 결과가 아니다.** MIMIC 에서 검사를 안 했으면 NOT_TESTED. 가상 결과를 정답처럼 쓰지 않는다. 검사 시행 자체가 질환과 연관됨 **[사실: B1S 측정 선택 AUROC pooled 0.64 — NBI-B1S VERIFIED 공개 산출물]** → 시행 여부를 특징으로 쓰면 선택 편향·누출 위험.

## 4. 데이터별 매핑

| 개념 | DDXPlus | MIMIC-IV(보유분) |
|---|---|---|
| 증상·과거력 노드 | evidences 223 | ED triage `chiefcomplaint`(짧은 원문) — 구조화 필요 |
| 상태 | POSITIVE/VALUE = 기재, NEGATIVE = 물었고 미기재(시뮬레이터 규약), NOT_APPLICABLE = 부모 음성 | 검사 시행=값, 미시행=NOT_TESTED, 원문 부정 표현=NEGATIVE(NLU 필요) |
| 질환 노드 | PATHOLOGY 49 | ED `diagnosis` ICD, ECG-ext `all_diag_hosp`, cardiac-ext `heart_diagnoses_all` |
| 검사·소견 | 없음 | labevents(itemid), radiology 판독(원문), ECG machine_measurements |
| source_id | 질문 1회 | `specimen_id`, `note_id`, ECG `study_id` |
| 시간 | 없음(정적) | charttime/storetime, edstays intime/outtime |
| 정답 | PATHOLOGY + DIFFERENTIAL_DIAGNOSIS | 퇴원·ED ICD 코드(코딩 라벨 — 임상 Gold 아님) |
