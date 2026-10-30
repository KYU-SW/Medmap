"""STEP29.2 §15-13·14 정책 선택·동결 — DEV + 노출 pilot 지표(outputs/dev_policy_metrics.json)만 보고 gates.select_policy 규칙으로 1회(있으면 유지).
data/policy_freeze.json = 선택 정책 · 후보별 자격·점수 · 파이프라인 코드 SHA. 이후 HOLDOUT 최초 실행. 동결 뒤 코드를 바꾸면 final 평가가 실행되지 않는다."""
import datetime

import s292_common as S
from gates import select_policy

P = S.DATA / "policy_freeze.json"
if not P.exists():
    dev = S.load_json(S.OUT / "dev_policy_metrics.json")
    sel, rows = select_policy(dev["metrics"])
    scripts = ["asr_sentence_segmenter.py", "evaluative_negation_scope.py", "temporal_resolution_linker.py", "b4_evidence_guard.py", "nlu_pipeline_v3.py",
               "benchmark_runtime.py"]
    S.dump_json(P, {"frozen_at": datetime.datetime.now().isoformat(timespec="seconds"), "SELECTED_POLICY": sel, "selection_rows": rows,
                    "dev_metrics_sha256": S.sha256(S.OUT / "dev_policy_metrics.json"),
                    "frozen_scripts": {n: S.sha256(S.STEP / "scripts" / n) for n in scripts},
                    "note": "선택은 DEV(개발 세트) + 노출 pilot 만 사용. HOLDOUT 은 이 시점까지 어떤 정책도 실행하지 않음. 개발 회차 기록 = logs/dev_r*.log"})
print(S.load_json(P)["SELECTED_POLICY"], S.load_json(P)["frozen_at"])
