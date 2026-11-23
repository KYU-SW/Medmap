"""평면표 기준선: 같은 추출 결과를 행 목록으로 두고 필드 필터로 에피소드 입력을 모은다. 평가·분류는 graphs.evaluate_common 그대로.
기능을 일부러 빼지 않는다(시간 공개·정정·에피소드·출처 모두 같은 규칙)."""
from __future__ import annotations

from . import observations as OB
from .graphs import UNRES, evaluate_common


def rows_of(pg) -> dict:
    n = pg.g.nodes.values()
    return {"evidence": [v for v in n if v["kind"] == "EVIDENCE"], "ecg": [v for v in n if v["kind"] == "ECG_FINDING"], "obs": list(pg.obs), "records": list(pg.records),
            "candidates": [v for v in n if v["kind"] == "AI_DIAGNOSIS_CANDIDATE_V5"]}


def evaluate_flat(pg, as_of: float, legacy: dict | None = None) -> dict:
    R = rows_of(pg)
    vis = set(pg.visible_records(as_of))
    inputs = {}
    for ep in {h.episode_id for h in pg.hyps5}:
        recs = [r for r in R["records"] if r["episode_id"] == ep and r["record_id"] in vis]
        inputs[ep] = {"evidence": [e for e in R["evidence"] if e["diagnosis_episode_id"] == ep and e["source_record_id"] in vis],
                      "ecg": [f for f in R["ecg"] if f["episode_id"] == ep and f["source_record_id"] in vis],
                      "obs": [o for o in OB.visible([o for o in R["obs"] if o.episode_id == ep], as_of) if o.source_record_id in vis or o.source_type == "STRUCTURED_LAB"],
                      "records": [{"record_id": r["record_id"], "text": r["text"], "unstructured_ecg": r["unstructured_ecg"]} for r in recs],
                      "unresolved": sorted([e["evidence_id"] for e in R["evidence"] if e["diagnosis_episode_id"] == UNRES and e["source_record_id"] in vis]
                                           + [f["finding_id"] for f in R["ecg"] if f["episode_id"] == UNRES and f["source_record_id"] in vis]
                                           + [o.obs_id for o in OB.visible([o for o in R["obs"] if o.episode_id == UNRES], as_of) if o.source_record_id in vis or o.source_type == "STRUCTURED_LAB"]),
                      "candidates": [c for c in R["candidates"] if c["source_record_id"] in {r["record_id"] for r in recs}]}
    return evaluate_common(pg.hyps5, legacy or {}, inputs, pg.sex, as_of, "flat")
