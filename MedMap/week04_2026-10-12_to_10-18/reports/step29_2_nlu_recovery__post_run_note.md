# 공식 실행 뒤 기록(2026-10-13)

- 공식 판정 = 첫 실행(HOLDOUT 최초 실행, 05:41–05:46) 산출물. 원본 사본: `logs/first_official_run/`.
- 그 뒤 사용자 별도 요청으로 Doctor 화면 디자인을 master 에 병합(05:5x, `fb2d7f0` → `977877f`, push 없음). STEP29.2 작업과 무관.
- 그래서 이후 `run_twice.sh` 의 보호 확인(G8)이 master HEAD 변경으로 FAIL → 재현 실행 판정 파일은 REGRESSION 으로 기록됨.
  보호 대상 기존 연구 파일 737개는 변경 0·추가 0(`logs/twice_run_outputs/protected_check.json`).
- 재현: 2회 실행 결과 파일 21개 SHA_IDENTICAL(`logs/sha1.txt`·`sha2.txt`), 첫 공식 실행과도 평가 결과 파일 SHA 동일.
- 공식 판정 파일(`outputs/step29_2_verdict.json`·`protected_check.json`·`latency.json`·`manifest.json`, docs 보고서 3개)은 첫 실행본으로 복원. 재현 실행본은 `logs/twice_run_outputs/`.
- 지연 측정 때 다른 세션의 CPU 작업(학습·추출)이 함께 돌았다(부하 높음) — p95 는 보수적 값.
