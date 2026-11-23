"""EXP-MAI-009 시연 시나리오 실행: 합성 환자 SYN-001 의 시연 단계별 연구용 모델 점수와 변경 이력을 기존 D 모델(겹 0, 읽기 전용)로 계산해 저장.
같은 계산을 2회 반복해 일치 확인. 사용: python run_demo.py <RUN_ID>
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from medmap_demo.assess import assess, counterfactual, diff, kg_status, provenance_graph  # noqa: E402
from medmap_demo.events import EventStore  # noqa: E402
from medmap_demo.model_adapter import DModel  # noqa: E402
from medmap_demo.replay import replay  # noqa: E402
from medmap_demo.scenarios import demo_case  # noqa: E402


def compute(model):
    """시연 단계별 평가 + 성공 기준 불리언(1차 심사 반영: 육안 판독 대신 계산)."""
    case, raws, steps = demo_case()
    s = EventStore().extend(raws)
    out, prev = [], None
    for name, t in steps:
        ts = datetime.fromisoformat(t)
        a = assess(replay(s, case, ts), model)
        out.append({"step": name, "as_of": t, "assessment": a, "diff_from_previous_step": diff(prev, a) if prev else []})
        prev = a
    t_cf = datetime.fromisoformat(steps[3][1])
    past = [o for o in out if o["step"].startswith("과거 시점 재생")][0]
    then = [o for o in out if o["step"] == "CT 예비 판독"][0]
    crit = {"past_replay_equals_then": past["assessment"] == then["assessment"],
            "no_score_on_non_usable": all(r["assessment"]["status"] == "NOT_ASSESSED" for o in out for r in o["assessment"]["rows"] if r["state"] != "USABLE"),
            "model_loaded": getattr(model, "status", None) == "LOADED",
            "all_usable_scored": all(r["assessment"]["status"] == "SCORED" for o in out for r in o["assessment"]["rows"] if r["state"] == "USABLE")}
    return {"criteria": crit, "case": {"patient_id": case.patient_id, "hypothesis": case.hypothesis_text, "synthetic": True}, "steps": out,
            "counterfactual_exclude_DD-R1_at_CT_prelim": counterfactual(s, case, t_cf, model, "DD-R1"),
            "provenance_graph_stats_final": provenance_graph(replay(s, case, datetime.fromisoformat(steps[5][1])))["stats"],
            "ingest_log_summary": {k: sum(1 for x in s.log if x["action"] == k) for k in ("APPENDED", "REJECTED", "IGNORED_IDEMPOTENT_RESEND")}}


def main(run_id: str):
    out = ROOT / "outputs" / f"demo_{run_id}"
    if out.exists():
        raise SystemExit("이미 있는 실행 식별자 — 덮어쓰지 않음")
    out.mkdir(parents=True)
    t0 = time.time()
    model = DModel().load()
    r1, r2 = compute(model), compute(model)
    sys.path.insert(0, str(ROOT / "src"))
    from run_compare import code_hashes
    res = {"run_id": run_id, "code_sha256": code_hashes(), "experiment": "EXP-MAI-009", "model_status": model.status, "model_id": model.model_id if model.pipe else None,
           "model_error": model.error, "repeat_identical": r1 == r2, "kg_relation_status": kg_status(),
           "label": "합성 환자. 점수는 ER-REASON 전문가 점수 예측 연구 모델 출력 — 임상 판단 아님, 근거별 독립 점수(합산·평균 없음)", **r1,
           "elapsed_sec": round(time.time() - t0, 1)}
    (out / "demo_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(model.status, "repeat_identical", res["repeat_identical"], "criteria", r1["criteria"], "->", out)
    for st in r1["steps"]:
        print(st["step"], [(r["lineage_id"], r["state"], r["assessment"].get("score", r["assessment"]["status"])) for r in st["assessment"]["rows"] if r["state"] == "USABLE"])


if __name__ == "__main__":
    main(sys.argv[1])
