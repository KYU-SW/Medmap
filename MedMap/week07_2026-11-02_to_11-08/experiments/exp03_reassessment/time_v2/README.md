# EXP-03-TIME v2 — 정본은 PROTOCOL_TIME_v2.md, 진행 기록은 TRACKING_GATE1.md(아래 초기 설명은 2026-11-03 기준)

- 정본 `PROTOCOL_TIME_v2.md`. v1(`../time_v1/`)·EXP-03·EXP-02 무수정, `time_v1/time_policy.py` 그대로 import.
- `records_v2.py` 고유 키 중복 처리·전역 1회 귀속·CTA/addendum 규칙·HMAC 가명 · `independent_audit.py` 계층 B · `public_v2.py` 보완 마스킹 · `run_time_policy_audit_v2.py` 실행(승인 플래그 필수).
- `tests/` 합성 parquet 18 테스트 · `fault_v2.py` 결함 주입 13종+2 · `bench_v2.py` 합성 규모 시간·RAM.
- 지적별 반영 = `TRACKING_GATE1.md`.
