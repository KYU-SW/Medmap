# EXP-SN-RAG-001 rev2 자체 점검 (RG 재심사 전, 2026-10-02)

| 점검 | 결과 |
|---|---|
| 기존 400 세트(queries-v0·split·gt-v0.1) 변경 | 0 (SHA 재대조 OK) — 한국어 평가 문구만 별도 파일 coverage-xling-v1 |
| PRB 작성·검증 중 검색 결과 열람 | 0 (검색 시스템 미존재) |
| PRB 크기 | 작성 102 → 채점 89 (DEV_POSITIVE 33 / EVAL_POSITIVE 56) ≥ 최소 40 |
| PRB 범주 15 / 출처 분산 | EVAL 15 범주 전부, 17 출처, 최대 20%(SRC-0001) |
| 비퇴화 | Gate B = end-to-end(기권 = 실패) + τ 비퇴화 제약(DEV TPR ≥ 0.50) |
| CI 가 판정에 사용 | Gate A 상한·Gate B 하한(군집 bootstrap + Wilson 동시) |
| 군집 | COVERAGE finding_id(34) · PRB source_id(17) · 2,000회 · seed 20261002 |
| τ 알고리즘 빈칸 | 점수 정의·조율 모집단(대조 제외)·후보·동점·언어 공유·정규화 없음·중립 처리 명시 |
| KO/EN 동등성 | 152 쌍 중 151 SAME, 1 쌍 KO 분석 제외. COVERAGE 템플릿 라벨 미검증(공개) |
| 사람 감사 | 표본 40 동결, 범위 제한(UNREVIEWED), EVAL 전 완료 필수, **미실시** |
| 독립성 한계 | 모두 Claude 계열 — prereg §16-1 |
| 프롬프트 기록 | PRB·번역·C 실행 전 파일·SHA, gt-v0.1 복원본 |
| 임계 분리 | Hard(고정) / CP-1·CP-2 비교(우선) / Gate A·B 절대(PROVISIONAL) |
| 사후 결정 공개 | prereg §16-3 (정답 분포·B 판정 분포 확인 후 결정 5건) |
| master·EXP-SN-001·제품 코드 | 변경 0 |
| 남은 위험 | 인용 정정 13건이 EVAL 에 포함(민감도 n=43) · PRB 재현율 과소(다른 묶음 근거 미검토) · 사람 감사 미실시 · 판정자 독립성 |
