# EXP-04 Evidence-Based Diagnostic Reassessment Evaluation (2026-11-04)

탐색적 예비실험, RG gate 없음(사용자 지시), 임상 성능 주장 없음. 정본 `PROTOCOL_EXP04.md`, 결과 `outputs/`.

- `data/raw/` SCT-Bench 공개 174문항(MIT, 커밋·SHA 기록) · `data/annot/` 패널 가린 주석 · `analyze_sct.py` 문항 분석
- `cases/` Europe PMC CC BY 증례 본문 · `replay_cases.py` 동결 엔진·v3b 로 재현(질적)

실행: `~/ai_env/bin/python -B replay_cases.py` / `~/ai_env/bin/python -B analyze_sct.py <sctpublic/data/output 경로>`
