"""STEP29 코드 동결 — 평가 전 1회 실행(이미 있으면 덮어쓰지 않음). data/prereg.json = 계약·검사기·파이프라인 스크립트 SHA + 시각."""
import datetime

import s29_common as S

P = S.DATA / "prereg.json"
if not P.exists():
    names = ["clause_segmenter.py", "symptom_span_extractor.py", "negation_scope.py", "temporality_analyzer.py", "experiencer_analyzer.py", "p5_normalizer_adapter.py",
             "semantic_conflict_guard.py", "symptom_context_builder.py", "clinical_nlu_pipeline.py", "contract_check.py", "metamorphic.py", "evaluator_v4.py",
             "evaluate_nlu.py", "build_report.py"]
    S.dump_json(P, {"frozen_at": datetime.datetime.now().isoformat(timespec="seconds"), "contracts_sha256": S.sha256(S.DATA / "synthetic_nlu_contracts.json"),
                    "evaluator_v4_sha256": S.sha256(S.STEP / "scripts/evaluator_v4.py"),
                    "frozen_scripts": {n: S.sha256(S.STEP / "scripts" / n) for n in names},
                    "note": "계약 개발(dev_contracts 3회) 후 동결. pilot_gold·SILVER·WEAKNON 결과는 동결 전 보지 않음"})
print(S.load_json(P)["frozen_at"])
