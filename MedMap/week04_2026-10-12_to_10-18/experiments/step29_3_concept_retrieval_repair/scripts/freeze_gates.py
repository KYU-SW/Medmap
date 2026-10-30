"""STEP29.3 §18-8 게이트 사전 고정 — 검색기 구현·실행 전 1회(있으면 유지). data/prereg_gates.json = 평가 데이터·회귀 사례·채점·지표·선택·판정 코드 SHA.
고정 시점까지 실행한 것: 이전 정책(R0 = STEP29.2 V3_B0 · R1 = V3_B3)을 DEV29_3·회귀 사례·STEP29.2 HOLDOUT 에만 실행(지표 코드 시험). FROZEN29_3 미실행.
검사기 = STEP29.2 evaluator_v6(재사용, SHA 기록)."""
import datetime

import s293_common as S
from evaluator_v6 import evaluator_sha

P = S.DATA / "prereg_gates.json"
if not P.exists():
    scripts = ["s293_common.py", "generate_eval_cases.py", "make_regression_cases.py", "evaluate_retrieval.py", "gates293.py", "protect_check.py"]
    data = ["development_cases.json", "frozen_evaluation_cases.json", "regression_cases.json", "evaluation_manifest.csv"]
    S.dump_json(P, {"frozen_at": datetime.datetime.now().isoformat(timespec="seconds"), "frozen_scripts": {n: S.sha256(S.STEP / "scripts" / n) for n in scripts},
                    "frozen_data": {n: S.sha256(S.DATA / n) for n in data}, "evaluator_v6_sha256": evaluator_sha(), "note": __doc__})
print(S.load_json(P)["frozen_at"], S.sha256(P)[:16])
