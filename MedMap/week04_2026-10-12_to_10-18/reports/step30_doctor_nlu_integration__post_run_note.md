# 공식 실행 뒤 기록(2026-10-14)

- 공식 = run_twice.sh 1회차 산출물(outputs/). 2회 재현: 결정적 산출물 13개 SHA_IDENTICAL(logs/repro_check.json), 판정 동일.
  run1·run2 사본 logs/run1_outputs·run2_outputs.
- 공식 판정 REGRESSION 원인 = G10 검사기 오탐(R10 '손이 떨려요' NLU 원본의 증상 concept 후보 키 'candidates'). 질환 정보 노출 아님.
  검사기를 NLU 원본 스키마와 대조하지 않고 SHA 고정한 실수. 공식 판정 변경 없음 — EXPLORATORY 재확인은 outputs/exploratory_g10_v2.json.
- 공식 실행 뒤 Preview(build_preview.py)만 수정: 렌더링 확인에서 발견한 F 표 열 꺾임·같은 상태 diff 행·확인 항목 중복 표시·모바일 표 첫 열 좁음.
  판정·평가 산출물과 무관. 렌더링 증거 logs/render_check/*.png(1280·375). 이후 license_scan·protect_check 재실행 PASS.
- 공식 실행 전 dev 모드(data/dev_cases.json, 출력 logs/dev_outputs)로만 디버깅. 공식 평가 문장은 실행 전 이전 단계 data 와 중복 검사 후 3개 교체(data/integration_contract_cases.json replaced_before_run).
