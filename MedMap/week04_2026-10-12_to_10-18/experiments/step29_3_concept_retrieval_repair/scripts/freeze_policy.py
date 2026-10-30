"""STEP29.3 §18-15 정책 선택·동결 — DEV29_3 + 노출 자료 지표(outputs/dev_policy_metrics.json)만으로 gates293.select_policy 규칙 1회(있으면 유지).
data/policy_freeze.json = 선택 정책 · 후보별 안전·하한·F1 · 검색 계층 코드 SHA. 이후 FROZEN29_3 최초 실행."""
import datetime

import s293_common as S
from gates293 import select_policy

P = S.DATA / "policy_freeze.json"
if not P.exists():
    dev = S.load_json(S.OUT / "dev_policy_metrics.json")
    sel, rows = select_policy(dev["metrics"])
    scripts = ["korean_morphological_normalizer.py", "semantic_disambiguator.py", "context_preserving_retriever.py", "b4_evidence_policy.py", "step29_2_adapter.py",
               "benchmark_runtime.py"]
    S.dump_json(P, {"frozen_at": datetime.datetime.now().isoformat(timespec="seconds"), "SELECTED_POLICY": sel, "selection_rows": rows,
                    "dev_metrics_sha256": S.sha256(S.OUT / "dev_policy_metrics.json"), "frozen_scripts": {n: S.sha256(S.STEP / "scripts" / n) for n in scripts},
                    "note": "선택은 DEV29_3 + 노출 자료만. FROZEN29_3 은 이 시점까지 어떤 정책도 실행하지 않음. 개발 회차 = logs/dev_r*.log"})
print(S.load_json(P)["SELECTED_POLICY"], S.load_json(P)["frozen_at"])
