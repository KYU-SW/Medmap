# RUN_COMMANDS (SUBAGENT D)

작업 폴더: `/home/<user>/medmap-guidelinecoordination-repro-20261118/D-baselines`
Python: `.venv/bin/python -I` (z3-solver 5.4.1.0, pydantic 2.14.3; 상세 env.txt). LLM/API 호출 없음. CPU 단일.

```bash
cd /home/<user>/medmap-guidelinecoordination-repro-20261118/D-baselines
# 0) 환경 (1회)
python3 -m venv .venv && .venv/bin/pip install z3-solver pydantic
cp -r ../upstream/GuidelineCoordination/pipeline src_copy/ && cp ../upstream/GuidelineCoordination/rules_gold.json src_copy/
# 1) 원본 analyzer 스모크 + prefix 버그 재현 (~3초)
.venv/bin/python -I code/smoke_orig.py > logs/smoke_orig.log
# 2) 변이 생성 (spec 은 실행 전 고정: mutation_spec/FROZEN_AT.txt) (~1초)
.venv/bin/python -I code/gen_mutants.py > logs/gen_mutants.log
# 3) B1/B2/B3/B5 (~5초)
.venv/bin/python -I code/eval_static.py > logs/eval_static.log
# 4) B4 gold 관계 + LSH 기본값 + prefix 버그 수정판 비교 (~48초)
.venv/bin/python -I code/eval_downstream.py gold > logs/downstream_gold.log
# 5) B4 변이 영향 (그룹당 23~37초)
.venv/bin/python -I code/eval_downstream.py mutants M01,M02,M03,M04 > logs/downstream_run1.log
.venv/bin/python -I code/eval_downstream.py mutants M05,M06,M07,M08
.venv/bin/python -I code/eval_downstream.py mutants M09,M10,M11
.venv/bin/python -I code/eval_downstream.py mutants M12,M13
# 6) 집계
.venv/bin/python -I code/summarize.py > logs/summarize.log
# 7) gold 동의어 id 병합 영향 (~24초)
.venv/bin/python -I code/gold_synonym_impact.py > logs/gold_synonym_impact.log
# 8) 제안 방법 B6 (spec v2 고정 후): dev 에서 변형 선택 -> eval 1회
.venv/bin/python -I code/b6_permission_cue.py dev  > logs/b6_dev.log
.venv/bin/python -I code/b6_permission_cue.py eval > logs/b6_eval.log
```

실행 순서 기록: spec v1 고정 10:35:21 -> 변이 생성 -> 기준선 -> 집계 -> spec v2 고정 -> B6 dev -> B6 eval (FROZEN_AT.txt 시각 참조).
