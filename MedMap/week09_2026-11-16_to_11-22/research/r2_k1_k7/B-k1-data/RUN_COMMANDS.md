# RUN_COMMANDS (SUBAGENT B, 2026-11-17)

모든 명령은 CPU 단일 프로세스, 각 1분 이내 종료. 외부 LLM API·설치 없음.

1. ClinicalTrials.gov v2 조회(13건, 무인증 공개 API)
   `curl -s -m 30 "https://clinicaltrials.gov/api/v2/studies/<NCT>?fields=protocolSection.identificationModule,protocolSection.eligibilityModule,protocolSection.designModule.enrollmentInfo,hasResults" -o data/ctgov/<NCT>.json`
   로그: logs/ctgov_fetch_*.log, logs/ctgov_eligibility_dump.log
2. 정답 동결(실험 전): gold/patients_synthetic.csv, gold/gold_criteria.json, gold/gold_manual_spotcheck.csv
   `date -Iseconds; sha256sum ...` → gold/FROZEN_AT.txt (2026-11-17T20:19:36+09:00), logs/gold_frozen.log
3. 기준선 코드 동결(실행 전): logs/baseline_frozen.log (code/regex_baseline.py, code/run_k1_experiment.py sha256)
4. 실험: `/home/<user>/ai_env/bin/python -I code/run_k1_experiment.py > logs/run_k1_experiment.log 2>&1`
   출력: results_pairs.csv, results_summary.csv, results_confusion.csv, results_per_trial.csv, results_spotcheck.csv, results_regex_extracted_criteria.json
5. 기준 문장 유형 감사: `/home/<user>/ai_env/bin/python -I code/criteria_text_audit.py > logs/criteria_text_audit.log 2>&1`
   출력: results_criteria_text_audit.csv
6. 폐암 시험 신기능 조건 grep: logs/lung_renal_grep.log

재현: 위 4·5만 다시 실행하면 같은 결과(결정적, 난수 없음). data/ctgov/*.json 은 2026-11-17 조회본.
