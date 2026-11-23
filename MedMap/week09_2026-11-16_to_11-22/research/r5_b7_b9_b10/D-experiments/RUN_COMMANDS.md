# RUN_COMMANDS — SUBAGENT D 재현 명령

[합성] 형식 검증용. 의학적 사실과 무관. CPU 단일, 외부 API·유료 서비스 없음.

```bash
cd /home/<user>/medmap-integrated-b7-b9-b10-validation/D-experiments
P="/home/<user>/ai_env/bin/python -I"

# 0) (이미 수행·동결됨) 입력 생성 + 정답 생성 — 다시 돌리면 같은 sha 가 나와야 함
$P gen_instances.py                      # -> inputs/instances.json (1291개)
$P ground_truth.py                       # -> frozen/ground_truth.json
sha256sum frozen/SPEC.md frozen/ground_truth.json inputs/instances.json   # FREEZE_MANIFEST.json 과 대조

# 1) 기준선 채점 (약 2~4분, 백그라운드)
nohup ~/scripts/run_with_done_marker.sh logs/eval.done logs/eval_$(date +%Y%m%d_%H%M).log -- $P evaluate.py --mem > /dev/null 2>&1 &

# 2) B_milp 대조 + E8b 확장성 (백그라운드)
nohup ~/scripts/run_with_done_marker.sh logs/milp.done logs/milp_$(date +%Y%m%d_%H%M).log -- $P run_milp_check.py ab > /dev/null 2>&1 &

# 3) 보고서 표 생성
$P make_tables.py                        # -> report_tables.md
```

evaluate.py 는 시작 시 FREEZE_MANIFEST.json 의 sha256 을 검사하고, 불일치하면 중단한다.

```bash
# 4) 추가 확인(B vs B' 차이 원인 검증, E6 선호 효과, B' 최장 시간 원인)
$P extra_checks.py                       # -> results_extra_checks.json
# 5) 보조 실험 E6b (사후 추가, 사전 동결 정답 아님 — 정답은 동결 GT 코드로 계산)
$P supp_e6b.py                           # -> results_supp_e6b.csv, inputs/supp_e6b_instances.json
```
