# EXP-SN-RAG-001 로컬 검색 기술 후보 — rev0 (2026-10-02)

- 상태: **조사만.** 설치·다운로드·실행 0. 수치는 model card·저장소 기준(에이전트 조사), 로컬 실측 아님
- 조건: 완전 로컬 · 오프라인 · 재현 가능 · 한국어+영어 · version freeze · 결정적 검색 · RTX 4060 Ti 8 GB(공유) 또는 CPU · 병원 배포 가능 라이선스

## 1. 임베딩 모델
| 모델 | 라이선스 | 크기·차원·최대 토큰 | 한국어 | 의료 | trust_remote_code | 판정 |
|---|---|---|---|---|---|---|
| BAAI/bge-m3 | MIT | ~568M · 1024(+sparse) · 8192 | 다국어 주장(ko 개별 수치 확인 필요) | 없음 | 불필요 | 후보 |
| nlpai-lab/KURE-v1 | MIT | ~0.6B(bge-m3 미세조정) · 1024 · 8192 | 한국어 특화 | 공중보건 QA 평가 주장(**확인 필요**) | 불필요 | **1순위 후보** |
| intfloat/multilingual-e5-large | MIT | ~560M · 1024 · 512 | Mr.TyDi ko | 없음 | 불필요 | 후보(512 토큰 제한) |
| intfloat/multilingual-e5-small | MIT | 소형 · 384 · 512 | ko 지원 | 없음 | 불필요 | CPU 대조군 |
| ncbi/MedCPT | 미국 정부 저작물 | ~100M×2 · 768 · 질의 64 | 영어만 | PubMed 학습 | 불필요 | 영어 보조만 |
| Snowflake arctic-embed-l-v2.0 | Apache-2.0 | ~568M · 1024 · 8192 | ko 명시 | 없음 | 확인 필요 | 예비 |
| Alibaba gte-multilingual-base | Apache-2.0 | 305M · 768 · 8192 | 확인 필요 | 없음 | **필요** | 제외(원격 코드) |
| jina-embeddings-v3 | CC BY-NC 4.0 | — | — | — | — | **제외(상업 불가)** |

## 2. Reranker (선택)
| 모델 | 라이선스 | 크기 | 판정 |
|---|---|---|---|
| BAAI/bge-reranker-v2-m3 | Apache-2.0 | 0.6B, ~1.2 GB fp16 | 후보 |
| bge-reranker-v2-gemma | Apache-2.0(기반 모델 Gemma 이용약관 **확인 필요**) | 3B, ~6 GB | 제외(8 GB 공유) |
| jina-reranker-v2-base-multilingual | CC BY-NC 4.0 | — | 제외 |

## 3. Lexical 검색
| 옵션 | 라이선스 | 결정성 | 한국어 | 판정 |
|---|---|---|---|---|
| SQLite FTS5 | Public Domain | BM25 고정 | trigram 내장 또는 외부 토큰화 | **1순위**(로컬 FTS5 컴파일 여부 확인 필요) |
| Kiwi(kiwipiepy) | 0.24.0 이상 Apache-2.0, 이전 LGPL — **확인 필요**(인수인계 문서에 "Kiwi LGPL 조건" 기록 있음) | 결정적 | 형태소 분석 | 토큰화 후보 |
| MeCab-ko | 엔진 GPL/LGPL/BSD 택1, 사전 Apache-2.0 | 결정적 | 형태소 분석 | 대안 |
| rank_bm25 | Apache-2.0 | 결정적 | 사전 토큰화 필요 | 유지보수 중단 — 고정 시만 |
| Tantivy | MIT | 결정적 | 한국어 없음 | 예비 |
| Pyserini/Lucene | Apache-2.0 | 결정적 | — | 제외(JVM, 규모 과함) |

## 4. 벡터 색인
| 옵션 | 라이선스 | 검색 | 결정성 | telemetry | 판정 |
|---|---|---|---|---|---|
| FAISS CPU IndexFlatIP | MIT | exact | 예 | 없음 | **1순위**(CPU 빌드) |
| sqlite-vec | MIT/Apache-2.0 | exact | 예 | 없음 | 소규모 대안(FTS5와 한 파일), 성숙도 확인 필요 |
| usearch | Apache-2.0 | exact 옵션 | exact 시 예 | 확인 필요 | 예비 |
| hnswlib | Apache-2.0 | 근사 | 아니오 | 없음 | 제외(결정성) |
| Chroma | Apache-2.0 | — | — | **기본 ON** | 제외 |
| Qdrant 임베디드 · LanceDB | Apache-2.0 | — | — | 확인 필요 | 제외(확인 전) |

- 수천~수만 chunk 규모 → exact 내적 검색으로 충분(근사 색인 불필요)

## 5. 후보 조합
| 조합 | 구성 | 용도 |
|---|---|---|
| **S1** | SQLite FTS5 BM25(trigram 또는 Kiwi) | 기준선 P1, 완전 결정적 |
| **S2** | S1 + KURE-v1 dense(CPU 사전 계산 벡터 저장) + FAISS FlatIP + RRF | 주 후보 P3 |
| **S3** | S2 + bge-reranker-v2-m3 | reranker ablation |
| 대조 | KURE-v1 대신 multilingual-e5-large | 임베딩 민감도 |

- 결정성 규칙 후보: 벡터는 빌드 시 1회 계산·저장·해시 → 질의 임베딩은 CPU fp32 · 동점 = (score desc, chunk_id asc) · FAISS GPU 빌드 미사용

## 6. 오프라인 설정 후보 (import 전에 설정)
`HF_HUB_OFFLINE=1` · `TRANSFORMERS_OFFLINE=1` · `HF_DATASETS_OFFLINE=1` · `HF_HUB_DISABLE_TELEMETRY=1` · `DO_NOT_TRACK=1` · 모델은 로컬 경로 로드 · `trust_remote_code=False` → 그래도 `unshare -rn` 차단 실측 필수

## 7. 자원 추정 (설치 전, 실측 아님)
- 디스크: KURE-v1 또는 bge-m3 가중치 약 2 GB대(fp32 safetensors 기준 추정, 확인 필요) · reranker 약 2 GB대 · 색인 수십 MB
- VRAM: 임베딩 사전 계산 시 약 1~2 GB(fp16) — 다른 프로젝트 GPU 사용 중이면 CPU로 대체 가능
- RAM: 수 GB 이내 예상
- 새 venv(`~/rag_env` 후보), `~/ai_env` 변경 0
- 비용: 전부 오픈 라이선스 → 계정 과금 0 예상. 다운로드는 사용자 승인 후

## 8. 미확인
KURE-v1 의료 평가 근거 원문 · bge-m3 한국어 개별 수치 · Kiwi 버전별 라이선스 · arctic-embed trust_remote_code · sqlite-vec 현 버전 · 로컬 Python FTS5 활성 · 가중치 실제 크기
