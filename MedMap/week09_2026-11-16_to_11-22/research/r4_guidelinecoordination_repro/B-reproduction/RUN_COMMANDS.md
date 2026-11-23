# RUN_COMMANDS (SUBAGENT B)

원본: `upstream/GuidelineCoordination` commit `deb4ae34bdb055f93301bd93ed640d8c77e0ee5e` (읽기 전용).
사본: `B-reproduction/src_copy/` (pipeline/ + rules_gold.json, SHA256 일치 확인: `src_copy/UPSTREAM_SHA256.txt`, 차이: `src_copy/DIFF_vs_upstream.diff` = 실행 시 생긴 `__pycache__` 뿐, 코드 수정 없음).

모든 명령은 `B=/home/<user>/medmap-guidelinecoordination-repro-20261118/B-reproduction` 기준.

## 1. 환경
```bash
python3 -m venv $B/.venv
$B/.venv/bin/pip install z3-solver pydantic        # 결과 버전: env.txt
$B/.venv/bin/pip freeze > $B/env.txt
```
langchain / langgraph / langchain_openai / rapidfuzz 는 설치하지 않음(LLM 단계 import 차단 목적).

## 2. 사본 생성
```bash
U=/home/<user>/medmap-guidelinecoordination-repro-20261118/upstream/GuidelineCoordination
cp -r $U/pipeline $U/rules_gold.json $U/README.md $B/src_copy/
sha256sum $U/rules_gold.json $U/pipeline/*.py > $B/src_copy/UPSTREAM_SHA256.txt
```

## 3. 실험1 대상 데이터 통계 (LLM 미사용)
```bash
cd $B && .venv/bin/python -I scripts/rules_gold_stats.py > logs/rules_gold_stats.log 2>&1
```
출력: `results/rules_gold_stats.json`

## 4. 실험2 결정적 단계 (원본 ConflictResolver.generate_report)
`scripts/run_exp2.py` 는 `pipeline/__init__.py`(langgraph import) 를 건너뛰고 `pipeline.analyzer` 만 로드, socket 연결을 차단한다.
```bash
cd $B
timeout 115 .venv/bin/python -I scripts/run_exp2.py --mode faithful_lsh        > logs/exp2_faithful_lsh.log 2>&1
timeout 115 .venv/bin/python -I scripts/run_exp2.py --mode faithful_exhaustive > logs/exp2_faithful_exhaustive.log 2>&1
timeout 110 .venv/bin/python -I scripts/run_exp2.py --mode atom_lsh            > logs/exp2_atom_lsh.log 2>&1
# 실측 255 s -> 백그라운드 + 완료 파일
nohup ~/scripts/run_with_done_marker.sh $B/logs/exp2_atom_exhaustive.done $B/logs/exp2_atom_exhaustive.log -- \
  $B/.venv/bin/python -I $B/scripts/run_exp2.py --mode atom_exhaustive > /dev/null 2>&1 &
```
모드별 출력(results/): `exp2_<mode>_pairs.csv`, `exp2_<mode>_summary.json`, `exp2_<mode>_upstream_report.json`(원본 export_report 형식).

| mode | predicates 입력 | 후보 쌍 | 원본 여부 |
|---|---|---|---|
| faithful_lsh | [] (predicates.json 미공개) | 원본 기본값 LSH(20 band×5 row, 임계 0.3) + 전이 폐포 | 원본 코드·원본 기본값 그대로 |
| faithful_exhaustive | [] | 전 쌍 158,203 (use_lsh_filter=False, use_bucket_filter=False) | 원본 코드, 인자만 변경 |
| atom_lsh | 합성: 각 pred.X → `$ Has(atom.X) $` (독립 Bool) | 원본 기본값 LSH | **추가 변형(원본 아님)** |
| atom_exhaustive | 합성(위와 동일) | 전 쌍 | **추가 변형(원본 아님)** |

## 5. 실행하지 않은 것
- `create_pipeline(...).run(...)`, `graph.py`/`graph_api.py` 의 모든 함수: OpenRouter(유료) ChatOpenAI 호출 → 과금 승인 없음, NOT_RUN.
