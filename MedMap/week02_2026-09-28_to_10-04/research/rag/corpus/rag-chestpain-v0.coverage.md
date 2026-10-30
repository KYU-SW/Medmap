# rag-chestpain-v0 Coverage Matrix (2026-10-02)

- 입력: 동결 corpus `rag-chestpain-v0`(18문서, manifest SHA `40f0b0b5…56a1af`)
- 방법: `scripts/rag/coverage_matrix_v0.py` — 범위별 영어 정규식, 본문(`<body>`)만, 결과 전 규칙 고정. 원자료 `rag-chestpain-v0.coverage.csv`(SHA `339684f6…5f75e9`)
- 문서 등급: TITLE(제목) > SECTION(절 제목 ≥1) > MENTIONED(본문 ≥5) > TRACE(1–4) > NONE
- 범위 판정(사전 규칙): COVERED = TIER1이 TITLE/SECTION · PARTIAL = TIER2만 · COVERAGE_GAP = TITLE/SECTION 문서 0
- **한계**: 어휘 일치 ≠ 근거 내용·품질. 병력 근거인지 검사 근거인지 구분 없음. 포르투갈어 미집계

## 1. 범위별 판정
| 범위 | 사전 규칙 판정 | TIER1 근거(절 제목) | TIER2 | 해석 주석(사후, 판정 변경 아님) | 보고 판정 |
|---|---|---|---|---|---|
| ACS(UA·NSTEMI·STEMI) | COVERED | SRC-0001(ACS 진단 정의·UA 기준·ECG 분류·위험 점수), SRC-0002(ACS 위험 분류·STEMI/NSTEMI) | SRC-0005(증상·징후 MA), SRC-0006, SRC-0010 | 가장 두꺼움 | **COVERED** |
| 안정형 협심증 | COVERAGE_GAP | — | —(SRC-0004 본문 언급만) | 전용 출처 없음 | **COVERAGE_GAP** |
| 폐색전증 | COVERED | SRC-0001(4.2.3 PE 임상 점수), SRC-0007(V/Q 영상 지침) | SRC-0008, SRC-0009 | TIER1 둘 다 감별 점수·영상 쪽. PE 임상 진단 지침 전체는 없음 | **COVERED(검사·점수 중심)** |
| 심낭염 | COVERED | SRC-0002(심근심낭염 추정 경로 절 1개) | SRC-0010(저권위 서술 리뷰) | 경로 절 1개 + 약한 리뷰 | **PARTIAL_WEAK** |
| 심근염 | COVERED | SRC-0001(4.4.5.3), SRC-0002(위와 같은 절) | SRC-0011(SCD MA) | 진단 근거는 얇음 | **PARTIAL_WEAK** |
| 기흉 | COVERED | SRC-0012(원발성 자연 기흉 지침) | — | 긴장성·이차성 기흉 제목 없음 | **COVERED(원발성 자연 기흉만)** |
| GERD · 비심장성 흉통 | COVERED | SRC-0002("비심장성 흉통 추정" 경로 절 1개) | — | **GERD 자체 제목·절 0**(본문 언급 SRC-0002 3회, SRC-0014 19회) | **NCCP: PARTIAL_WEAK / GERD: COVERAGE_GAP** |
| 공황·불안 | PARTIAL | — | SRC-0014(절 "Medical event versus panic attack") | 서술 리뷰 1건 | **PARTIAL_WEAK** |
| 급성 대동맥 증후군(OOS) | COVERED | SRC-0001(4.2.2 AAS 임상 점수) | SRC-0015~0018 | 바이오마커·점수 중심 | **COVERED** |
| 식도 파열(OOS) | COVERED | SRC-0013(식도 천공 절) | — | | **COVERED** |

- `PARTIAL_WEAK`·GERD 분리는 사전 규칙 이후의 해석이다. 사전 규칙 판정 열은 그대로 보존한다
- 공백을 다른 출처로 채우지 않았다(사용자 조건)

## 2. 문서 × 범위 등급
| src | Tier | ACS | 안정형 | PE | 심낭염 | 심근염 | 기흉 | GERD/NCCP | 공황 | 대동맥 | 식도 파열 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| SRC-0001 | T1 | SECT | TRAC | SECT | MENT | SECT | MENT | TRAC | TRAC | SECT | MENT |
| SRC-0002 | T1 | SECT | NONE | MENT | SECT | SECT | TRAC | SECT | TRAC | MENT | NONE |
| SRC-0003 | T2 | TRAC | NONE | NONE | NONE | NONE | NONE | NONE | NONE | NONE | NONE |
| SRC-0004 | T2 | MENT | MENT | NONE | NONE | NONE | NONE | NONE | NONE | NONE | NONE |
| SRC-0005 | T2 | TITL | NONE | NONE | NONE | NONE | NONE | NONE | NONE | NONE | NONE |
| SRC-0006 | T2 | SECT | NONE | TRAC | NONE | NONE | NONE | NONE | NONE | NONE | NONE |
| SRC-0007 | T1 | TRAC | NONE | TITL | NONE | NONE | TRAC | NONE | NONE | TRAC | NONE |
| SRC-0008 | T2 | TRAC | NONE | TITL | NONE | NONE | NONE | NONE | NONE | NONE | NONE |
| SRC-0009 | T2 | NONE | NONE | TITL | NONE | NONE | NONE | NONE | NONE | NONE | NONE |
| SRC-0010 | T2 | TITL | NONE | NONE | TITL | TRAC | NONE | NONE | NONE | NONE | NONE |
| SRC-0011 | T2 | NONE | NONE | NONE | NONE | TITL | NONE | NONE | NONE | NONE | NONE |
| SRC-0012 | T1 | NONE | NONE | TRAC | NONE | NONE | TITL | NONE | TRAC | NONE | NONE |
| SRC-0013 | T1 | NONE | NONE | NONE | NONE | NONE | TRAC | NONE | NONE | TRAC | SECT |
| SRC-0014 | T2 | TRAC | TRAC | TRAC | TRAC | NONE | NONE | MENT | TITL | TRAC | NONE |
| SRC-0015 | T2 | TRAC | NONE | NONE | NONE | NONE | NONE | NONE | NONE | TITL | NONE |
| SRC-0016 | T2 | NONE | NONE | NONE | NONE | NONE | NONE | NONE | NONE | TITL | NONE |
| SRC-0017 | T2 | TRAC | NONE | NONE | NONE | NONE | NONE | NONE | NONE | TITL | NONE |
| SRC-0018 | T2 | TRAC | NONE | NONE | NONE | NONE | NONE | NONE | NONE | TITL | NONE |

## 3. 구조적 편향 (평가 해석 시 주의)
- SRC-0001·SRC-0002 두 문서가 거의 모든 범위의 TIER1 근거 → 검색 결과가 두 문서에 몰릴 가능성
- 대동맥 증후군 문서 5개(OOS)가 안정형 협심증(0)·GERD(0)보다 많음 → 범위 간 불균형
- PE·대동맥 근거는 검사·점수 중심 → "질문만으로 구별 가능한가" 근거는 상대적으로 적을 수 있음(내용 확인 전, 추정)
