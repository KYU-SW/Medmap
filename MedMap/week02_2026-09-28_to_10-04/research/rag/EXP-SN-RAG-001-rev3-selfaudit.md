# EXP-SN-RAG-001 rev3 자체 점검 (RG 재심사 전, 2026-10-02)

| 점검 | 결과 |
|---|---|
| 기존 동결 자산(corpus·COVERAGE 400·분할·gt-v0.1·PRB-v0·rev2 freeze) 변경 | 0 — 해시 재대조 OK, 새 파일만 추가 |
| SN-PRB 작성·검토·검증 중 검색 결과 열람 | 0 (검색 시스템 미존재) |
| SN-PRB 크기 | 102 → 채점 97 (DEV 36 / EVAL 61), 형식별 KO 적격 TEMPLATE 61 · NATURAL 54 ≥ 30 |
| corpus 전체 정답 | A ∩ X(같은 문서 독립 일치) + B 판정(385 단위), 관련 출처 2개 이상 44/61 |
| 형식별 퇴화 차단 | G-R2b·c 형식별 PASS 필수, τ 비퇴화 형식별 |
| 구절 단위·우연 초과 | G-R2 = passage_hit@5_e2e, G-R2d = 형식별 무작위 기대값(0.6607/0.6583) 초과 |
| 출처 집중 | SRC-0001 38% → G-R2e(비SRC-0001 38/34 항목) |
| BM25 전처리 | BM25-PRE-v1 결정적, LLM 재작성 0, Kiwi 제외 근거 |
| 판정 순서·수치 규칙 | 8단계·첫 비PASS 결정, float64·연산자·Wilson z·bootstrap 10,000·PCG64·seed 규칙·분위수·빈 층 처리 |
| CI 역할 | Wilson(독립) + 군집 bootstrap(의존) 동시 / 단일 단위 Gate 는 Wilson 만 / CP 는 bootstrap + Tango |
| 사람 감사 | 99 전수 팩·지침·도구 v2 동결, **PENDING**(Claude 미기입), UNSURE → 제외, 검색 전 완료·봉인 |
| 번역 | SN 206쌍 중 205 SAME(템플릿 라벨 포함), 1 질문 KO 제외 |
| 프롬프트 | 실행 전 파일·SHA·시각 |
| DEV/EVAL 분리 | splits/*-dev.jsonl·*-eval.jsonl, DEV 코드 assert |
| 임계 | PROVISIONAL_METHOD_THRESHOLD(사용자 승인), 판정 특성 공개 |
| master·EXP-SN-001·제품 | 변경 0 |
| 남은 위험 | 판정자 전부 Claude 계열 · 독해식 작성 · G-R1 은 TEMPLATE 만 · corpus 범위 한계 · 사람 감사 미실시 |
