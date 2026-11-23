"""평면 규칙표 기준선: 같은 추출 결과·메타데이터·검사 사건을 행 목록으로 두고 필드 필터로 입력을 모은다.
에피소드 입력 필터는 v5-1 flat.evaluate_flat 과 같은 규칙(그 함수는 입력을 밖으로 내주지 않아 같은 필터를 여기서 적용).
평가는 그래프와 같은 comparator.compare_common. 기능을 일부러 빼지 않는다."""
from __future__ import annotations

from hybrid5 import observations as OB
from hybrid5.flat import rows_of

from . import comparator as CMP
from .graphs import UNRES, legacy_v4, provenance


def collect_flat(pg, as_of: float) -> dict:
    R = rows_of(pg)
    vis = set(pg.visible_records(as_of))

    def obs_vis(ep):
        return [o for o in OB.visible([o for o in R["obs"] if o.episode_id == ep], as_of) if o.source_record_id in vis or o.source_type == "STRUCTURED_LAB"]

    eps = {}
    for ep in sorted(pg.episodes):
        recs = [r for r in R["records"] if r["episode_id"] == ep and r["record_id"] in vis]
        rec_ids = {r["record_id"] for r in recs}
        eps[ep] = {"evidence": [e for e in R["evidence"] if e["diagnosis_episode_id"] == ep and e["source_record_id"] in vis],
                   "ecg": [f for f in R["ecg"] if f["episode_id"] == ep and f["source_record_id"] in vis], "obs": obs_vis(ep),
                   "records": [{"record_id": r["record_id"], "text": r["text"], "unstructured_ecg": r["unstructured_ecg"]} for r in recs],
                   "unresolved": sorted([e["evidence_id"] for e in R["evidence"] if e["diagnosis_episode_id"] == UNRES and e["source_record_id"] in vis]
                                        + [f["finding_id"] for f in R["ecg"] if f["episode_id"] == UNRES and f["source_record_id"] in vis]
                                        + [o.obs_id for o in obs_vis(UNRES)]),
                   "candidates": [c for c in R["candidates"] if c["source_record_id"] in rec_ids],
                   "tests": sorted([{"test_id": t.test_id, "event": t.event, "at": t.at, "test_kind": pg.test_kinds.get(t.test_id, "UNKNOWN")}
                                    for e, t in pg.tests if e == ep], key=lambda t: (t["test_id"], t["at"], t["event"]))}
    unres = {"evidence": [e for e in R["evidence"] if e["diagnosis_episode_id"] == UNRES and e["source_record_id"] in vis],
             "ecg": [f for f in R["ecg"] if f["episode_id"] == UNRES and f["source_record_id"] in vis], "obs": obs_vis(UNRES),
             "records": [{"record_id": r["record_id"], "text": r["text"], "unstructured_ecg": r["unstructured_ecg"]} for r in R["records"]
                         if r["episode_id"] == UNRES and r["record_id"] in vis]}
    recs = [{"record_key": d.doc_id, "record_type": d.doc_type, "episode_id": r["episode_id"], "observation_time": d.observed_at, "available_time": d.available_at,
             "corrects": [d.supersedes] if d.supersedes else []} for r in R["records"] for d in [pg.docs[r["record_id"]]]]
    recs += [{"record_key": o.obs_id, "record_type": "STRUCTURED_LAB", "episode_id": o.episode_id, "observation_time": o.observation_time,
              "available_time": o.available_time, "corrects": [o.supersedes] if o.supersedes else []} for o in R["obs"] if o.source_type == "STRUCTURED_LAB"]
    meta = {k: m for k, m in pg.meta.items() if m.source_event_id or m.derived_from or m.exact_duplicate_of}
    vis_obs = {o.obs_id for o in OB.visible(R["obs"], as_of)}
    return {"patient_id": pg.pid, "episodes": eps, "unresolved": unres, "meta": meta, "provenance": provenance(recs, vis | vis_obs, as_of)}


def compare_flat(pg, as_of: float) -> dict:
    return CMP.compare_common(pg.specs, legacy_v4(pg, as_of, "flat"), collect_flat(pg, as_of), pg.sex, as_of, "flat")
