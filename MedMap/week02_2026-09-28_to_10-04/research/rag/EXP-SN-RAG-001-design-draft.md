# EXP-SN-RAG-001 설계 초안 rev0 — Frozen Local Medical RAG (별도 병렬 연구 트랙)

- 작성 2026-10-02 · 브랜치 `research/safety-net-rag` · worktree `~/medmap-worktrees/safety-net-rag` · 시작점 `1605d67`(= `research/safety-net-min` HEAD)
- 상태: **설계 초안만.** 구현·설치·다운로드·corpus 수집·RG gate·환자 평가·holdout 접근·성능 확인 **0**
- 관련 문서(이 폴더): `EXP-SN-RAG-001-source-license-audit.md`(출처·라이선스 조사) · `EXP-SN-RAG-001-local-stack-candidates.md`(로컬 기술 후보) · `corpus_manifest.schema.yaml`(manifest 스키마) · `EXP-SN-RAG-001-prereg-plan.md`(RG 사전등록 초안 계획)

---

## 0. 원칙 (PRESERVE_EXISTING_MEDMAP)

| 항목 | 이 트랙에서 |
|---|---|
| master · Doctor UI · API · 버튼 · 제품 화면 | 변경 0, RAG 결과 노출 0 |
| Diagnosis / IG 엔진 · PatientState · exact-k3 · Natural Intake · Streaming STT · Handoff · 확인 소견 표시 | 변경 0 |
| EXP-SN-001 prereg rev2 · knowledge protocol · literature review · manifest · RG gate 기록 | 변경 0(해시 대조로 확인, §1) |
| structured knowledge 설계 · Disease Knowledge Layer 설계 | 보존. RAG는 대체가 아니라 비교 대상 |
| 기존 실험 결과 | 덮어쓰기 0. RAG 산출물은 새 경로(`exp/rag_*`, `data_local/rag_corpus/`) 예정 |
| RAG의 역할 | **근거 검색만.** 진단 결정·"WD가 틀렸다" 판정 금지 |
| 근거 없음 | `UNKNOWN`. LLM 내부 의료지식으로 보충 금지 |

---

## 1. 현재 저장소·동결 상태 (2026-10-02 확인값)

| 대상 | 값 | 판정 |
|---|---|---|
| master | `fb2d7f0`, 미커밋 31줄(인수인계·메모리·`exp/step17a_intake_start_validation/`) | 손대지 않음 |
| `research/safety-net-min` | `1605d67`, worktree 깨끗(0줄) | 손대지 않음 |
| EXP-SN-001 rev2 해시 | `EXP-SN-001-rev2.sha256` 4개 파일 `sha256sum -c` 전부 OK | **동결 유지 확인** |
| EXP-SN-001 RG | rev0 심사 BLOCK(`20261002_013458_BLOCK.md`), 재심사 없음 | 그대로 |
| 새 브랜치 | `research/safety-net-rag` ← `1605d67` | 생성 완료 |
| 새 worktree | `~/medmap-worktrees/safety-net-rag` | 생성 완료, 기존 worktree 11개와 이름 충돌 없음 |

- 시작점을 `research/safety-net-min`으로 둔 이유: EXP-SN-001 문서를 같은 트리에서 읽기 전용으로 참조(비교 설계 A/B/C). 이 브랜치에서 EXP-SN-001 파일 수정 금지 — 커밋 전 `sha256sum -c docs/research/EXP-SN-001-rev2.sha256` 확인 규칙
- 이 브랜치의 `.research-guardian/current` = `EXP-SN-001`(상속값). RAG RG 등록 시 이 브랜치 안에서만 바뀜(브랜치 로컬 파일)
- `git reset --hard`·`git stash` 사용 0

---

## 2. EXP-SN-001과의 관계

| | EXP-SN-001 | EXP-SN-RAG-001 |
|---|---|---|
| 지식 형태 | Structured KB(사실 행 + relation type, 사람/LLM 작성 후 동결) | Frozen corpus 원문 chunk + 로컬 검색 |
| 지식 생산 | 저자 A → 검증자 B → 매핑 C(K0–K6) | C0–C6(수집 → 라이선스 → 승인 → 해시 → chunk/index → 동결) |
| 판단 위치 | K 점수(정수표) | RAG는 근거만. 판단은 별도 reasoning layer |
| 공통 관문 | 출처 라이선스(B-LIC) | 같은 관문 + 더 엄격(원문 전체를 저장·임베딩) |
| 상태 | rev2, BLOCK, 동결 | rev0 설계 초안 |

- 두 트랙 모두 아직 상대를 대체하지 않음. 최종 비교 A(K only) / B(R only) / C(K+R)는 §8
- **공유 가능 자산(제안)**: 이 트랙의 C1 라이선스 감사 결과는 EXP-SN-001 B-LIC 선택지 (b) "재사용 허용 출처로 재조사"의 입력으로 쓸 수 있음. 단 EXP-SN-001 문서 수정은 하지 않음(사용자 결정 사항)

---

## 3. 연구 질문 (2단계 분리)

### Stage R — RAG 검색 자체 (이번 사전등록 대상 후보)
- **RQ-R1 검색 재현율**: 승인·동결된 흉통 corpus에서, (WD, 환자 소견) 질의에 대해 관련 출처·관련 구절을 상위 k 안에 가져오는가(source recall@k, passage recall@k)
- **RQ-R2 근거 없음 처리**: corpus에 근거가 없는 질의에서 억지 근거를 가져오지 않고 `UNKNOWN`을 내는가(unsupported retrieval rate, abstention precision/recall)
- **RQ-R3 출처 추적**: 반환 구절마다 source_id·위치·chunk_id·corpus_version이 원문 해시와 일치하는가(provenance accuracy)
- **RQ-R4 운영 조건**: 완전 오프라인·결정적 반복·지연시간(CPU, RTX 4060 Ti 8 GB) 조건을 만족하는가
- **RQ-R5 정보 종류 구분**: 반환 근거를 "질문으로 확인 가능 / 진찰 / 심전도 / 혈액검사 / 영상 / 기타 측정" 범주로 구분할 수 있는가(Next-Best-Information 2.0 연결 — 구분 가능성만 평가, 구현 없음)

### Stage S — Safety-Net 가치 (별도 사전등록, Stage R 통과 후에만)
- **RQ-S1**: R 유래 근거로 만든 재검토 신호가 B0·B1·K 대비 틀린 WD를 더 잡는가(EXP-SN-001과 같은 판정 틀)
- **RQ-S2**: K+R hybrid가 K 단독 대비 지식 공백(K=0 사례)을 줄이는가
- Stage S는 이번에 설계 방향만. 실행·데이터 접근 0

---

## 4. Approved Medical Corpus 기준

### 4.1 입장 조건 (모두 충족)
1. 정식 출처 원본: 공식 HTML · 공식 PDF · 출판사 open-access 전문 · PMC OA 전문. **비공식 PDF 사본·검색 snippet·블로그 재인용·요약 경유 금지**
2. 라이선스 원문을 실제 페이지에서 확인(라이선스 URL·인용·확인일 기록). "무료 열람" ≠ 재사용 허용
3. reuse_status ∈ {`PRODUCTION_ALLOWED`, `RESEARCH_ALLOWED_ONLY`} — 후자는 연구 corpus에만, `production_eligible=false` 표시
4. `LICENSE_UNCLEAR` · `PERMISSION_REQUIRED` · `NOT_ALLOWED` → 제외(서면 허가 기록이 생기면 재심사)
5. 제3자 저작물(그림·표 별도 저작권 표시) → 해당 부분 제외 또는 문서 제외
6. medical_authority Tier 기록(입장 조건 아님, 메타데이터). 권위 낮아도 재사용 명확·근거 정리 양호하면 후보
7. 언어: 영어·한국어

### 4.2 두 축 분리
- **A. Medical Authority**: TIER1 공식 지침·정부·학회 / TIER2 체계적 문헌고찰·메타분석·주요 리뷰 / TIER3 개별 연구 / TIER4 환자 교육·백과
- **B. Reuse Status**: `PRODUCTION_ALLOWED` / `RESEARCH_ALLOWED_ONLY` / `PERMISSION_REQUIRED` / `LICENSE_UNCLEAR` / `NOT_ALLOWED`
- 예: ESC 2023 ACS = TIER1 + NOT_ALLOWED(서면 라이선스 전). 두 축 혼동 금지

### 4.3 라이선스별 기본 정책 (법률 판단 아님 — `LEGAL_QUESTION` 표시 후 사용자 결정)
| 라이선스 | reuse_status 기본 | corpus 입장 | 비고 |
|---|---|---|---|
| CC0 · Public Domain(미국 연방 저작물) | PRODUCTION_ALLOWED | 가능 | 페이지 내 제3자 자료 확인 |
| CC BY 4.0 | PRODUCTION_ALLOWED | 가능 | 출처 표시 의무 → provenance로 충족 |
| CC BY-SA | PRODUCTION_ALLOWED | 가능 | 파생물 동일 라이선스 — 색인·chunk가 파생물인지 **LEGAL_QUESTION** |
| 공공누리 1유형 | PRODUCTION_ALLOWED | 가능 | 페이지별 유형 확인 |
| CC BY-NC(-SA) · 공공누리 2유형 | RESEARCH_ALLOWED_ONLY | 연구 corpus만 | 병원 상용 배포 시 재검토 |
| CC BY-ND / CC BY-NC-ND · 공공누리 3·4유형 | **보류** | 사용자 결정 전 제외 | chunk·임베딩이 "변경"인지 **LEGAL_QUESTION** |
| 출판사 user license(비상업 TDM만) | RESEARCH_ALLOWED_ONLY 또는 UNCLEAR | 문구별 판단 | |
| All rights reserved · AI 금지 명시 | NOT_ALLOWED | 불가 | ESC·NICE(해외)·APA |

### 4.4 Corpus 동결 순서 C0–C6
`C0` 후보 목록 → `C1` 라이선스 감사 → `C2` 출처 승인(사용자) → `C3` 로컬 확보(정식 URL에서, 확보일 기록) → `C4` 원문 SHA-256 → `C5` chunk·색인(파라미터 동결) → `C6` corpus manifest 동결(`corpus_version`, manifest SHA)

- C6 이후 평가 결과를 보고 문서를 추가·삭제·재chunk하면 그 iteration = **exploratory**. confirmatory 평가는 새 freeze version + 새 평가 질의 집합 필요
- 원문 파일은 git에 넣지 않음(`data_local/rag_corpus/<corpus_version>/`, `.gitignore`). git에는 manifest·해시·라이선스 증거만
- 공개 저장소(`~/medmap-github`) 반영 금지(인용 모음·원문 재배포 문제)

### 4.5 첫 범위
- 흉통 관련: ACS(불안정형 협심증·NSTEMI·STEMI) · 안정형 협심증 · 폐색전증 · 심낭염(심근염 관련) · 기흉 · GERD/비심장성 흉통 · 공황·불안 관련 흉통
- out-of-scope 고위험 원인: **기존 목록 복사 금지.** 승인 출처의 제목·목차에 실제 등장하는 이름만 기록(출처·위치 동반)
- 후보 출처 결과: `EXP-SN-RAG-001-source-license-audit.md`

---

## 5. RAG 입출력 계약 (후보)

### 5.1 질의
```yaml
query_id: q-000123
working_diagnosis: {code: ddx49:<id> | free_text, label_ko, label_en}
findings:            # 환자 소견(관측값만, 확률 없음)
  - {finding_id: E_xx[:value], label_ko, label_en, status: present|absent}
intent: support | unexplained | conflict | alternative | next_information
corpus_version: rag-chestpain-c6-v1
```
- 질의 문장 생성 = **결정적 템플릿**(WD 이름 + 소견 문구, 한·영 병기). LLM 질의 재작성 사용 안 함(1차)
- 용어 정규화: MedMap 기존 한국어 용어(master 정본)와 DDXPlus 질문 사전(CC BY, 질환 연결 없음)만. UMLS·SNOMED 사용 시 라이선스 별도 검토

### 5.2 결과
```yaml
query_id: q-000123
status: EVIDENCE_FOUND | UNKNOWN
results:
  - rank: 1
    source_id: SRC-0007
    document_title: ...
    location: {section: "...", heading_path: [...], page: 12 | null}
    chunk_id: SRC-0007#c0042
    chunk_sha256: ...
    passage: "<원문 구절 그대로>"
    matched_terms: [ ... ]          # lexical 일치어(결정적)
    retrieval: {bm25: 12.3, dense: 0.71, fused_rank: 1, retriever: hybrid-rrf}
    finding_ref: E_xx
    relation_hint: null              # Stage R에서는 항상 null — 판단은 reasoning layer
    info_type_hint: null | history | exam | ecg | lab | imaging | measurement   # RQ-R5 평가용 후보
corpus_version: rag-chestpain-c6-v1
index_sha256: ...
retriever_config_sha256: ...
```
- `relation_hint`(지지/충돌/설명 부족)를 RAG가 채우지 않음. "ACS가 틀렸다" 같은 문장 생성 0
- `UNKNOWN` 조건(후보): ① 상위 점수 < τ_abstain(R-DEV 질의로 고정) ② 상위 구절에 WD·소견 개념이 함께 나오지 않음 ③ 승인 corpus 범위 밖 질환
- 모든 RAG 유래 문장은 `source_id + location + chunk_id + corpus_version` 없이는 출력 금지

---

## 6. 검색 파이프라인 후보 (기술은 아직 고정 안 함)

| 후보 | 구성 | 장점 | 위험 |
|---|---|---|---|
| **P1 lexical** | 질의 템플릿 → BM25(한·영 토큰화) → 상위 k | 완전 결정적, 가벼움, 의학 약어 강함 | 동의어·한영 교차 약함 |
| **P2 dense** | 질의 → 로컬 임베딩 → exact 내적 검색 | 동의어·한영 교차 | 임베딩 모델 의존, GPU 비결정성 |
| **P3 hybrid** | P1 + P2 → RRF 결합(정수 순위 기반, 결정적) → (선택) 로컬 reranker | 두 장점 결합 | 구성요소 증가 |
| **P4 hybrid → verified cache** | P3로 근거 발견 → 사람(또는 검증 절차)이 사실 추출 → 동결 cache를 런타임 입력 | 런타임 안정, K와 같은 형태로 비교 가능 | 사람 작업량(B-AUTH와 같은 문제) |

- LLM 불필요 경로 우선: 질의 구성 → 검색 → (reranker) → provenance 출력까지 LLM 0
- 로컬 LLM은 Stage S의 relation 판단 후보 중 하나로만 검토(로컬·오프라인·버전 고정·결정적 설정·provenance 강제). 이번 단계 도입 0
- 결정성 규칙(후보): CPU 추론 또는 GPU 임베딩 사전 계산 후 저장 → 색인은 저장된 벡터만 사용 / exact search(근사 색인 금지 또는 seed·파라미터 고정) / 동점 처리 = (score desc, chunk_id asc)
- 구체 후보: `EXP-SN-RAG-001-local-stack-candidates.md`

---

## 7. Stage R 평가 계획 (환자 데이터 미사용)

### 7.1 평가 질의 집합 (corpus ≠ 환자 데이터)
- 질의 = (WD, 소견, intent) 조합. 출처: §4.5 질환 목록 × EXP-SN-001 C7 관측 가능 소견 목록(질문 사전 기준, 질환 연결 없음)
- **DDXPlus 환자 행·STEP17A 사례·STEP13B 오답·평가 결과 사용 0**
- 세 종류: ① answerable(corpus에 근거 있음) ② **unanswerable**(근거 없음 — 억지 검색 검사) ③ conflicting(출처 간 서술 차이)
- 분할: R-DEV(임계 τ_abstain·k·fusion 고정) / R-TEST(1회). 질의 ID 해시로 분할, 동결 후 검색 실행
- gold 판정: pooling(P1·P2·P3 상위 20 합집합) 구절에 대해 **사람 판정자** 관련/무관 표시. 판정자 = 확인 필요(EXP-SN-001 B-AUTH와 같은 문제 → `B-AUTH-R`)

### 7.2 지표
| 지표 | 정의 | 판정 사용 |
|---|---|---|
| source recall@k (k=5,10) | answerable 질의 중 gold 출처가 상위 k에 있는 비율 | primary 후보 |
| passage recall@k · nDCG@10 · MRR | gold 구절 기준 | secondary |
| unsupported retrieval rate | unanswerable 질의 중 `EVIDENCE_FOUND` 비율 | primary 후보(낮을수록 좋음) |
| abstention precision / recall | `UNKNOWN`의 정답 여부 | secondary |
| contradictory handling | conflicting 질의에서 상충 출처 둘 다 상위 k에 반환한 비율 | secondary |
| provenance accuracy | 반환 구절 == 원문[chunk 범위] 바이트 일치 + 해시 일치 | **gate(100% 요구)** |
| determinism | 같은 질의 5회 · 프로세스 재시작 3회에서 순위·점수 동일 | **gate(100% 요구)** |
| offline operation | 네트워크 차단 실행 성공 + 외부 연결 시도 0 | **gate** |
| latency | 질의당 p50·p95(CPU, GPU 각각), warm/cold 분리 | 보고(REALTIME_FIRST 참고치) |

- 통계 단위 = 질의. bootstrap(질의 단위) 95% CI. 기준치(예: recall@10 ≥ 0.8)는 사전등록에서 결과 전 고정 — **이번 문서에서 수치 미정**

---

## 8. Structured(K) vs RAG(R) vs Hybrid(K+R) 비교 설계 (Stage S, 방향만)

| 팔 | 근거 | 점수화 |
|---|---|---|
| B0 | 모델 top1 ≠ WD | EXP-SN-001 정의 그대로 |
| B1 | 1 − P(WD) | 그대로 |
| K | Structured KB | EXP-SN-001 s(f,d) 정수표 |
| R | RAG 근거 | relation 판단 방식 결정 필요(아래) |
| K+R | K + R 공백 보완 | K 우선, K 공백(K=0)에서만 R |

- **R 팔의 relation 판단 = 핵심 미결정**. 후보: (R-a) P4 verified cache → K와 같은 정수표 / (R-b) 로컬 NLI·분류 모델 / (R-c) 로컬 LLM 제약 출력. (R-a)는 사람 작업, (R-b)(R-c)는 새 모델 검증 필요
- **같은 환자 쌍대 비교 필요** → K·R·K+R을 동시 동결 후 같은 EVAL에서 1회 평가하는 공동 사전등록이 원칙. EXP-SN-001 EVAL을 먼저 열면 R 팔 평가는 blind가 아님 → 새 salt의 별도 EVAL 구간 또는 공동 평가 중 선택(사용자 결정, `D-EVAL`)
- RAG corpus 출처 선택도 EXP-SN-001 blind 목록(평가 행·혼동·STEP13B·시뮬레이터 질환→소견 정의 열람 금지)을 그대로 따름

---

## 9. OFFLINE_ON_PREM_FIRST 검증 방법 (계획)

| 단계 | 방법 |
|---|---|
| 빌드 시점(인터넷 허용, 사용자 승인) | 모델 가중치·corpus 원문 확보 → SHA-256 기록 → 이후 런타임은 로컬 경로만 |
| 런타임 환경 | `HF_HUB_OFFLINE=1` · `TRANSFORMERS_OFFLINE=1` · `HF_DATASETS_OFFLINE=1` · `trust_remote_code=False` · 라이브러리 telemetry 끔(예: `ANONYMIZED_TELEMETRY=False` 해당 시) · 기존 `scripts/offline_env.sh` 패턴 재사용 후보 |
| 시작 시 자산 검사 | 모델·색인·manifest SHA 대조, 불일치 시 시작 거부(`offline_assets_check.py` 패턴 후보) |
| 네트워크 차단 시험 | `unshare -rn`(루트 없이) 네트워크 없는 namespace에서 질의 N개 실행 → 성공 + **양성 대조**(같은 환경에서 외부 연결 시도 코드가 실패하는지) |
| 연결 시도 감시 | 블랙홀 프록시/`ss`·`strace -e connect` 기록 → 외부 연결 시도 0 |
| 네이티브 telemetry | import 시 외부 연결 여부까지 검사(onnxruntime 사례 — 전역 메모리) |
| 클라우드 벡터 DB · 외부 API · 외부 LLM | 의존성 목록에서 제외(설계 단계 차단) |

- master의 `release_offline_check.sh`는 수정하지 않음. RAG 전용 검사 스크립트를 이 브랜치에 별도로(구현 단계에서, 승인 후)

---

## 10. 새 의존성·자원 요구 (추정 — 설치 전 실측 필요)

- 전용 가상환경 별도 생성(예: `~/rag_env`). **`~/ai_env` 변경 금지**
- 디스크: corpus(수십 문서) 수십~수백 MB 이하 예상 · 임베딩 모델 1개 수백 MB~2 GB대 · 색인 수십 MB(수천 chunk 기준) — 실제 값은 후보 확정 후 계산
- GPU: 임베딩 사전 계산만 GPU 사용 후보(VRAM 여유 확인, `wait_for_resources.sh --check`), 질의 시점은 CPU 가능 구성 우선. 현재 GPU 76%·5.9/8.2 GB 사용 중(다른 프로젝트)
- 비용: 오픈 라이선스 모델·라이브러리만 → 계정 과금 0 예상. 다운로드 자체는 무료지만 네트워크 작업이므로 **설치·다운로드는 사용자 승인 후**
- 세부 후보·라이선스: `EXP-SN-RAG-001-local-stack-candidates.md`

---

## 11. 기존 제품·연구와 충돌 점검

| 점검 | 결과 |
|---|---|
| master 파일 변경 | 0 (worktree 생성만, master 미커밋 31줄 그대로) |
| `research/safety-net-min` 변경 | 0 (worktree 깨끗) |
| EXP-SN-001 문서·manifest | 해시 OK, 이 브랜치에서도 수정 0 |
| 제품 계약(PatientState·exact-k3·posterior·IG 3Q·cache 표시) | 무관(코드 변경 0) |
| 평가 데이터·holdout | 접근 0 |
| 금지 출처(ESC·NICE·APA·AHA·BTS·ACG 원문) AI 재투입 | 0 — 조사 에이전트에 라이선스 메타데이터만 열람 지시 |
| `.research-guardian` | EXP-SN-001 기록 변경 0. 새 ID 등록 전 |
| 보류 항목(STT·Timeline·데모 등) | 무관 |

---

## 12. 사용자 결정이 필요한 항목

| ID | 내용 | 막는 단계 |
|---|---|---|
| D-LIC-ND | ND·SA 라이선스 출처를 chunk·임베딩해도 되는가(법률 판단 필요 여부 포함) | C2 |
| D-LIC-NC | NC 출처를 연구 corpus에 넣고 `production_eligible=false`로 둘지 | C2 |
| B-AUTH-R | Stage R gold 판정자(사람 판정자 / 독립 세션 / 미정) | Stage R 평가 |
| D-EVAL | Stage S 비교를 EXP-SN-001과 공동 EVAL로 할지, 새 salt 별도 EVAL로 할지 | Stage S |
| D-REL | R 팔 relation 판단 방식(R-a cache / R-b NLI / R-c 로컬 LLM) | Stage S |
| D-INSTALL | 전용 venv·모델 다운로드 승인 | 구현 |
