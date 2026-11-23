# EXP-03-TIME v1 — 실제 MIMIC 시간정보 이용 가능성 정책(계획·합성 단계, 2026-11-03)

- 상위 EXP-03(`../PROTOCOL.md`, `../reassess.py` 등) 무수정 — 이 폴더는 시간 정책 추가분만.
- `PROTOCOL_TIME.md`: 출처별 시간 필드 표(공식 문서 확인), 주 분석 STRICT_AVAILABLE_TIME, 민감도 S1·S2, ECG NOT_IDENTIFIABLE, 체류 귀속·정정·누출 정의, 후속 집계 계획.
- `time_policy.py`: 원시 기록 → 시간 등급(A 문서상 이용 가능 · B 보수적 대리 · C 불명/충돌)·이용 가능 시각 → 기존 reassess.Timeline. 시각 생성·대체 없음.
- `tests/test_time_policy.py`: 정상 사례 TP01–TP17 + 안전 성질(16 테스트). `fault_time.py`: 결함 주입 7종 + 대조(별도).
- `RG_PLAN_DRAFT.md`: 실제 집계용 rg-plan 입력 초안(미등록, 본실행 BLOCKED).
- 결과: `outputs/fault_time_*`. 실제 MIMIC 새 실행 없음(기존 공개 집계 `../outputs/mimic_time_audit_20261103_1013` 대조만).
