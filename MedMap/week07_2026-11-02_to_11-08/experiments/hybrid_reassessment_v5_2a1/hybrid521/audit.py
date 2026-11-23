"""v5-2A 가 보고한 '레거시 중복 9건'을 v5-2A 결과 파일만 읽어(읽기 전용) 다시 분류한다. 9건을 모두 실제 중복으로 가정하지 않는다."""
from __future__ import annotations

import json
from pathlib import Path

from . import lineage as LN

CLASSES = ("CONFIRMED_SAME_EVENT", "CONFIRMED_DISTINCT_EVENT", "DEPENDENCY_UNKNOWN", "CONFLICTING_EVENT_EVIDENCE")


def audit(v52_out: Path) -> dict:
    cases = json.loads((v52_out / "v5_2a_cases.json").read_text())
    val = json.loads((v52_out / "v5_2a_validation.json").read_text())
    reported = [tuple(x) for x in val["legacy_v4_items_in_duplicate_groups"]]
    rows = []
    for case, c in cases.items():
        if "results" not in c:
            continue
        rec_rows = [{"record_key": r["record_id"], **{k: v for k, v in (r.get("meta") or {}).items() if k != "record_key"}} for r in c["records"]]
        rec_rows += [{"record_key": o["obs_id"], **{k: v for k, v in (o.get("meta") or {}).items() if k != "record_key"}} for o in c["structured_observations"]]
        decl = LN.declarations(rec_rows)
        known = {r["record_key"] for r in rec_rows}
        for res in c["results"]:
            cmp = res["comparison"]
            for h in cmp["hypotheses"]:
                for i in (h.get("legacy_v4") or {}).get("items", []):
                    if not i.get("duplicate_group_id"):
                        continue
                    dep = cmp["dependency_items"][i["evidence_id"]]
                    dg = next(d for d in cmp["duplicate_evidence_groups"] if d["duplicate_group_id"] == i["duplicate_group_id"])
                    rv = LN.resolve(dep["source_record_id"], decl, known)
                    rows.append({"case": case, "as_of": res["as_of"], "raw_judgment_id": f"RAW:{h['hypothesis_id']}:{i['relation_id']}:{i['evidence_id']}",
                                 "patient_id": cmp["patient_id"], "episode_id": h["diagnosis_episode_id"], "hypothesis_id": h["hypothesis_id"],
                                 "evidence_id": i["evidence_id"], "source_record_id": dep["source_record_id"], "declared_source_event_id": dep["source_event_id"],
                                 "derived_from": dep["derived_from"], "resolved_event_id": rv["event_id"], "lineage_basis": rv["basis"], "lineage_issues": rv["issues"],
                                 "relation_id": i["relation_id"], "legacy_direction": i["direction"], "finding_id": dg["finding_key"],
                                 "available_time": dep["available_time"], "v5_2a_duplicate_group_id": i["duplicate_group_id"]})
    for r in rows:
        peers = [x for x in rows if (x["case"], x["as_of"], x["hypothesis_id"], x["relation_id"], x["v5_2a_duplicate_group_id"]) ==
                 (r["case"], r["as_of"], r["hypothesis_id"], r["relation_id"], r["v5_2a_duplicate_group_id"]) and x is not r]
        if not r["resolved_event_id"]:
            cls = "DEPENDENCY_UNKNOWN"
        elif any(p["resolved_event_id"] == r["resolved_event_id"] and p["finding_id"] != r["finding_id"] for p in peers):
            cls = "CONFLICTING_EVENT_EVIDENCE"
        elif peers and all(p["resolved_event_id"] == r["resolved_event_id"] for p in peers):
            cls = "CONFIRMED_SAME_EVENT"
        elif peers:
            cls = "CONFIRMED_DISTINCT_EVENT"
        else:
            cls = "DEPENDENCY_UNKNOWN"
        r["audit_class"] = cls
        r["confirmable_from_metadata"] = cls in ("CONFIRMED_SAME_EVENT", "CONFIRMED_DISTINCT_EVENT")
    uniq = sorted({(r["case"], r["raw_judgment_id"]) for r in rows})
    grp = sorted({(r["case"], r["resolved_event_id"], r["relation_id"]) for r in rows if r["resolved_event_id"]})
    return {"reported_by_v5_2a": len(reported), "rows_reconstructed": len(rows), "rows_match_report": sorted((r["case"], r["evidence_id"]) for r in rows) == sorted((a, b) for a, b, _ in reported),
            "count_unit_note": "v5-2A 의 9 는 (사례 × 평가 시점 × 레거시 항목) 행 수 — 같은 판단이 여러 평가 시점에서 반복 집계됨",
            "unique_raw_judgments": len(uniq), "unique_raw_judgment_ids": [list(u) for u in uniq], "unique_same_event_groups": len(grp), "groups": [list(g) for g in grp],
            "class_counts": {c: sum(r["audit_class"] == c for r in rows) for c in CLASSES}, "rows": rows,
            "source_files": ["hybrid_reassessment_v5_2a/outputs/v5_2a_cases.json", "hybrid_reassessment_v5_2a/outputs/v5_2a_validation.json"], "read_only": True}
