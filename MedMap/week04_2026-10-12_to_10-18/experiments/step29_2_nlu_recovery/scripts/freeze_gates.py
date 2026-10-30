"""STEP29.2 §3-6·7 게이트 사전 고정 — NLU v3 구현·실행 전 1회(있으면 유지). data/prereg_gates.json = 평가 데이터·검사기 v6·채점·지표·판정 코드 SHA.
고정 시점까지 실행한 것: 이전 정책(S29·S291)을 DEV·노출 세트에만 실행(지표 코드 시험 — logs/smoke_eval_dev.log). HOLDOUT 은 어떤 정책도 실행하지 않음."""
import datetime

import s292_common as S

P = S.DATA / "prereg_gates.json"
if not P.exists():
    scripts = ["s292_common.py", "generate_eval_pairs.py", "evaluator_v6.py", "validate_evaluator_v6.py", "contract_check_v3.py", "evaluate_nlu.py", "gates.py"]
    data = ["dev_pairs.json", "frozen_holdout_pairs.json", "evaluation_manifest.csv"]
    S.dump_json(P, {"frozen_at": datetime.datetime.now().isoformat(timespec="seconds"), "frozen_scripts": {n: S.sha256(S.STEP / "scripts" / n) for n in scripts},
                    "frozen_data": {n: S.sha256(S.DATA / n) for n in data}, "evaluator_v6_sha256": S.sha256(S.STEP / "scripts/evaluator_v6.py"),
                    "evaluator_validation_sha256": S.sha256(S.OUT / "evaluator_validation.json"),
                    "evaluator_validation": {k: S.load_json(S.OUT / "evaluator_validation.json")[k] for k in ("EVALUATOR_V6", "known_correct_mentions",
                                                                                                             "EVALUATOR_FALSE_POSITIVES", "known_bad", "EVALUATOR_FALSE_NEGATIVES")},
                    "note": __doc__})
print(S.load_json(P)["frozen_at"], S.sha256(P)[:16])
