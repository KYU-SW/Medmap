"""STEP29.1 동결 — 평가 전 1회(있으면 유지). data/prereg.json = 계약·전향적·검사기 v5·파이프라인 SHA."""
import datetime

import s291_common as S

P = S.DATA / "prereg.json"
if not P.exists():
    names = ["evaluative_negation.py", "resolution_temporality.py", "mention_context_validator.py", "unsupported_input_guard.py", "nlu_pipeline_v2.py",
             "contract_check_v2.py", "evaluator_v5.py", "evaluate_nlu.py", "build_report.py"]
    S.dump_json(P, {"frozen_at": datetime.datetime.now().isoformat(timespec="seconds"), "contracts_sha256": S.sha256(S.DATA / "contract_cases.json"),
                    "prospective_sha256": S.sha256(S.DATA / "prospective_synthetic_cases.json"), "evaluator_v5_sha256": S.sha256(S.STEP / "scripts/evaluator_v5.py"),
                    "frozen_scripts": {n: S.sha256(S.STEP / "scripts" / n) for n in names},
                    "note": "새 계약 개발(dev 3+회) 후 동결. 전향적 합성·pilot·SILVER·WEAKNON 결과는 동결 전 보지 않음(pilot 의 '입맛은 괜찮아요' 는 STEP29 에서 이미 봄)"})
print(S.load_json(P)["frozen_at"])
