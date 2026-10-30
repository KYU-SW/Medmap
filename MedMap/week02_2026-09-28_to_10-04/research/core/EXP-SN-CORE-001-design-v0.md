# EXP-SN-CORE-001 설계 초안 v0 (2026-10-02, 실행 0 · 지식 작성 0 · 평가 데이터 접근 0)

- 질문: 현재 Working Diagnosis(WD)가 환자의 확인된 소견을 충분히 설명하지 못하는 상황을, 출처 근거 구조화 지식(Core-K)으로 구별할 수 있는가
- 판정 대상 아님: 오진 판정, 임상 성능, 제품 UI
- 브랜치 `research/safety-net-core`(master `fb2d7f0` 분기), worktree `~/medmap-worktrees/safety-net-core`
- 상태: DESIGN_DRAFT · RG 미심사

## 0. 다른 트랙 상태 기록
| 트랙 | 상태 | 비고 |
|---|---|---|
| EXP-SN-RAG-001 | **STATUS = PAUSED** · REASON = HUMAN_AUDIT(99 PENDING) / RG NEEDS_FIX(MAJOR 8) · RESUME_LATER = YES | `research/safety-net-rag` `a940847` 무변경. 사람 감사 99·양성 20·rev4·임베딩/색인 설치 중단 |
| EXP-SN-001 | 보존(prereg rev2, RG BLOCK, 실행 0) | `research/safety-net-min` `1605d67` 무변경 |
| master | 무변경 | 본 트랙은 병합하지 않음 |

## 1. 런타임 의존
- RAG 검색 미사용. Frozen Corpus v0 원문을 **읽고** 필요한 사실만 구조화 fact로 추출
- 출처 풀: v0 18건(전부 CC BY, 연구 승인). 전부 `research_only = true`(제품 배포 승인 0). SRC-0014는 CC BY 버전 미기재 → 추가 표시
- 원문 위치: `~/medmap_rag_corpus/rag-chestpain-v0/`, 단위 `derived/rag-chestpain-v0.units-v1/units.jsonl`(2,487 단위, unit_id 인용)

## 2. Pilot 범위 (후보, 사용자 확정 전)
근거: corpus 단위 정규식 집계(2026-10-02, 같은 단위 동시 언급, 어휘 일치 ≠ 내용)
| 질환 | 단위 | 출처 | 비고 |
|---|---|---|---|
| ACS(NSTEMI/STEMI + 불안정형) | 286 | 11 | 가장 두꺼움. 증상 MA(SRC-0005) 포함 |
| PE | 183 | 6 | 검사·점수 중심 |
| 심낭염 | 31 | 4 | ECG 감별 중심, SRC-0010 저권위 |
| 자연 기흉 | 67 | 5 | SRC-0012 치료 중심, 병력 근거 희소 |
| 심근염 · 공황 · GERD · 안정형 | 56 · 40 · 8 · — | 4 · 2 · 3 · 0 | 제외(약함/공백) |

| 쌍 | 동시 언급 단위 | 출처 |
|---|---|---|
| ACS–PE | 22 | 5 |
| ACS–심낭염 | 12 | 3 |
| PE–기흉 | 6 | 3 |
| ACS–기흉 | 3 | 2 |

- 추천: **A안 = ACS · PE · 심낭염(쌍 ACS–PE, ACS–심낭염)**. B안 = A + 자연 기흉(쌍 PE–기흉 추가, 근거 얇음)
- **사용자 확정(2026-10-02): A안.** 주 쌍 ACS–PE, 보조 쌍 ACS–심낭염. 자연 기흉 = 제외, 후속 확장 후보. 지식 작성·평가 데이터 접근은 RG gate 통과 전 금지
- DDXPlus 클래스 대응(이름만, 정의 미열람): ACS = `Possible NSTEMI / STEMI` + `Unstable angina` — 묶음 처리 여부 사용자 결정
- **사용자 확정(2026-10-02, RG gate BLOCK 후): 주 분석 = 두 클래스를 ACS WD 범주 하나로 묶음.** 원 DDXPlus 클래스 라벨 보존. 개별 클래스 결과는 민감도 분석에서만. NSTEMI/STEMI ↔ UA 병력 구별 성능은 Core Safety-Net 실패로 계산하지 않음
- **사용자 확정(2026-10-02): Δmin = 0.02**
- **사용자 확정(2026-10-02): primary 정보 단계 = 초기 증상 + 질문 3개**(~~B1 k3 학습 분포 일치~~ — rev2에서 틀린 설명으로 폐기, §13; 제품 IG 3문항 흐름·WD 입력 시점). FULL = secondary/exploratory, 평가 시 같은 정보 상태로 학습한 별도 기준선과만 비교. 정보량이 다른 모델 간 직접 비교 금지. (~~rev1 확정 필요: 3문항 선택 = DEV_FIT IG 표 순서~~ rev2 폐기 → 고정 selector §13, B1 학습 = k3 무작위 3문항 → 분포 차이를 TUNE AUROC·calibration으로 선보고)
- 대동맥 증후군 = 모델 공간 밖 → OUT_OF_SCOPE 고지 문구만

## 3. 예상 구조적 제약 (실행 전 가설)
- 감별 근거 다수가 ECG·트로포닌·D-dimer·영상 → 병력 소견만으로 REVIEW_SUGGESTED 근거는 적을 수 있음
- 따라서 정상 출력에 NEED_ECG / NEED_BIOMARKER / NEED_IMAGING / NEED_PHYSICAL_EXAM / INSUFFICIENT_INFORMATION 포함
- DDXPlus는 시뮬레이터 → 성능 = "문헌 지식 ↔ 시뮬레이터 분포" 일치도. 실제 환자 성능 주장 불가

## 4. 지식 스키마 (fact 1행)
```yaml
fact_id: CK-0001
disease_or_pair: ACS | PE | PERI | ACS~PE | ACS~PERI
relation_type: SUPPORTING | POORLY_EXPLAINED | IMPORTANT_NEGATIVE | OVERLAPPING | DIFFERENTIATING | TEST_REQUIRED | OUT_OF_SCOPE_WARNING
finding: "<중립 사전 evidence id 또는 자유 항목>"
evidence_id: E_xx | null          # 중립 질문 사전 대응, 없으면 null
medmap_observable: true | false
requires_test: none | ECG | BIOMARKER | IMAGING | PHYSICAL_EXAM | VITALS | RECORDS
source_id: SRC-00xx
source_location: {heading_path: [...], unit_id: "SRC-00xx#u0000"}
quote: "<단위 원문 그대로, 최대 2문장>"
direction: "<원문이 말하는 방향만, 해석 추가 금지>"
research_only: true
review_status: unreviewed
```
- 원문 지지 없음 → fact 생성 안 함, 해당 칸 UNKNOWN
- 작성자 입력 허용: Pilot 질환명 · corpus 원문 · 중립 질문 사전(`release_evidences.json` 질문 문구·값). 금지: `release_conditions.json` 증상 정의, DDXPlus 데이터 행, STEP13B·STEP17A 결과, 모델 혼동, 평가 행
- 작성 = 별도 에이전트 A(작성) · B(독립 인용 검증: quote가 unit 원문에 있는지 기계 대조 + 방향 일치). 사람 검토 전 `unreviewed`

## 5. SafetyNetReview 인터페이스
```python
@dataclass
class SafetyNetReview:
    status: Literal["CONSISTENT","INSUFFICIENT_INFORMATION","REVIEW_SUGGESTED","OUT_OF_SCOPE","ABSTAIN"]
    supporting_findings: list[FindingRef]
    unexplained_findings: list[FindingRef]
    possible_conflicts: list[FindingRef]
    overlapping_alternatives: list[AltRef]        # pilot 범위 안만
    missing_information: list[InfoNeed]           # NEXT_QUESTION
    requires_test_or_measurement: list[InfoNeed]  # NEED_ECG/BIOMARKER/IMAGING/PHYSICAL_EXAM/VITALS
    abstain_reason: str | None
    provenance: list[str]                         # fact_id
    model_context: dict | None                    # 보조 신호(B1 값), 판정 근거로 단독 사용 금지
```
- 입력: confirmed findings(+/−/값) · WD · fact 표 · (선택) 모델 후보
- 규칙(초안): REVIEW_SUGGESTED는 fact_id ≥1개를 가진 이유 경로 필수(UNEXPLAINED 또는 CONFLICT + OVERLAPPING alt). 모델 신호만으로 REVIEW 금지
- WD가 pilot 밖 → OUT_OF_SCOPE · 관련 fact 0 또는 핵심 소견 미응답 → INSUFFICIENT_INFORMATION · fact 충돌 해소 불가 → ABSTAIN
- 출력 문구: "현재 진단만으로 충분히 설명되지 않음" / "다른 질환과도 일부 겹침" / "구별에 필요한 정보". "오진" 표현 금지

## 6. 평가 데이터
- 원천: STEP17A DEV(656,593)만. VALIDATION·TEST·HOLDOUT 접근 0
- 새 분할 salt `sncore01`(EXP-SN-001 `safetynet01`과 분리): `int(sha256("sncore01|"+key16)[:8],16) % 10` → 0–5 FIT(모델·IG·K_data 빈도 학습만, 규칙·fact 조정 금지) · 6–7 TUNE · 8–9 EVAL(1회, 잠금)
- 대상 행: 정답 질환 ∈ pilot. 분할·행 목록 해시 freeze 후 평가
- WD 생성: A. correct WD = 정답 / B. plausible incorrect WD = 사전 고정 쌍의 상대. ACS 환자는 primary(a=PE)·보조(a=PERI)에 각각 독립 포함(mod 배정 폐기, rev2). 모델 top2/3 사용 금지
- 정보 단계: INTAKE → START → START+1 → START+IG3(primary) → FULL. 정식 정의는 manifest 최신판(rev3)

## 7. 누출 방지
- 순서 강제: fact 표 동결(SHA) → 커밋 시각 < 평가 하네스 첫 데이터 접근
- 작성 에이전트 프롬프트·입력 파일 목록 사전 기록. 작업 폴더에 DDXPlus 데이터·`release_conditions.json` 미노출(경로 차단 확인)
- 본 세션(설계자)도 지식 동결 전 평가 행·조건 정의 미열람
- 하네스는 fact 표를 읽기 전용으로 사용, 결과 후 fact 수정 = 새 버전 + 재평가 별도 표기

## 8. 기준선
| ID | 신호 |
|---|---|
| B0 | 모델 top1 ≠ WD |
| B1 | 1 − P(WD) (49질환, 재정규화 없음), TUNE에서 correct FPR 고정 임계 |
| Core-K | 출처 근거 규칙(REVIEW_SUGGESTED) |
| B1 + Core-K | 사전 고정 결합 규칙(예: OR, 또는 B1 임계 + K 이유 필수) — prereg에서 하나로 고정 |

## 9. 지표
- Primary: ① wrong WD re-review 탐지율 ② correct WD false alert rate(분리 보고, 상한 사전 고정)
- 보조: ABSTAIN 율 · OUT_OF_SCOPE 율 · 이유 경로 coverage(REVIEW 중 fact ≥1) · test-needed 출력의 규칙 내 정답성 · B1 대비 증분(같은 FPR에서 탐지 차, 환자 단위 쌍대 bootstrap) · 환자당 경고 수 · 단계별 REVIEW vs INSUFFICIENT 비율
- 임계 = PROVISIONAL_METHOD_THRESHOLD

## 10. 실패·중단 조건 (초안)
- Core-K가 B1 대비 같은 correct FPR에서 탐지 증분 하한 ≤ 0 → feasibility 약함
- correct WD false alert > 사전 상한 → 실패
- REVIEW 중 fact 근거 없는 출력 > 0 → 구현 결함, 중단
- fact 수 부족(쌍당 DIFFERENTIATING·OVERLAPPING 관측 가능 fact 0) → 해당 쌍 평가 제외 기록
- 지식 동결 전 평가 데이터 접근 흔적 → 무효

## 11. 구현 순서
1. 사용자 결정(범위·ACS 묶음·결합 규칙) → RG 초기화 + `/rg-plan` → `/rg-gate`
2. fact 작성 프로토콜·프롬프트 고정 → 에이전트 A 작성 → B 인용 검증 → 동결
3. 중립 관측표(fact ↔ evidence id) 확정
4. 엔진 + 단위 테스트(합성 입력만)
5. 분할·WD 생성 freeze → 하네스 FIT/TUNE → EVAL 1회
6. `/rg-verify`

## 12. rev1 (2026-10-02)
- gate 20261002_172718_BLOCK 지적 반영 정본 = manifest rev1(B1-pair primary 비교, START+IG3, macro 방향 균형, ΔFPR 상한, Δmin 0.02, NOT_EVALUABLE·INCONCLUSIVE, 2단계 격리 작성, NC1·ST1·D1, 안전 지표, 문구)
- 본 문서와 manifest가 다르면 manifest 우선

## 13. rev2 (2026-10-02)
- gate 20261002_180042_NEEDS_FIX 반영. **정정**: 앞선 "START+IG3 = B1 k3 학습 분포 일치" 설명은 틀림(k3 = 무작위 3문항)
- **사용자 확정**: primary 기준선 = START+IG3 상태로 DEV_FIT 재학습한 B1-IG3. IG3 trajectory = 기존 고정 IG selector(제품 NextInformationEngine 로직 + model_k3 + IG 표, 무수정), 답마다 사후확률 재계산·순차 선택, 동점 = IG 내림차순(round 12) → evidence 번호 오름차순. B1-IG3와 Core-K는 같은 IG3 상태에서 비교. 무작위 3문항 모델 = secondary 기준선
- §8–§10 기준선·지표·실패 조건의 정본 = manifest rev2

## 14. rev3 (2026-10-02)
- gate 20261002_181214_NEEDS_FIX 반영: H2=PILOT 조건 일치(C·B1-IG3-pair FPR ≤0.12), TUNE 판정 순서(천장→C 정의 불가→C 의존 NOT_EVALUABLE, 판정 시 EVAL 미개봉), 반폭 예측식 고정, 금지 문자열 검사 범위 고정+양성 대조, status (i) 정의, TEST_REQUIRED test_type, DEV SHA assert
