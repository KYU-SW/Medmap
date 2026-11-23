# 실행 명령 (모두 D-k7-tests/ 에서, CPU 단일, 각 1초 내외)

```bash
cd /home/<user>/medmap-gate0-followup/D-k7-tests
# 0) 복사본 동등성 (원본 개발 사례 12건)
node --experimental-transform-types --no-warnings src/vendor_sanity.ts
# 1) 독립 반례 16사례·40질의 × 방법 5개 (사건 시점 = 추출된 onset_date)
node --experimental-transform-types --no-warnings src/run.ts
# 2) 민감도(사후 추가): 사건 시점에 상대시간 사전(어제/그저께/N일 전/지난주) 적용 — (d)(e)만 영향
VALID_TIME=lexicon node --experimental-transform-types --no-warnings src/run.ts
# 3) 층위별 집계 → results_by_layer.csv
python3 -I src/layer_summary.py
# 4) 사후 관찰(채점 제외): 한 기록 안 '현재 먼저·과거 나중' 추출
node --experimental-transform-types --no-warnings src/posthoc_extractor_check.ts
```

원본 저장소 무변경 확인: `git -C ~/medmap-team/MedMap status --short` 를 작업 전후 `logs/git_status_before.txt`·`logs/git_status_after.txt` 로 저장해 비교(동일), 원본 해시 재계산(동일).
