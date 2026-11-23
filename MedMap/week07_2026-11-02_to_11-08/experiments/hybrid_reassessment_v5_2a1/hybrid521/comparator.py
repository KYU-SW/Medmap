"""v5-2A 비교 결과 위에 근거 그룹 계층을 붙인다(그래프·평면표 공용 규칙).
입력 수집만 모드별: 그래프 = v5-2A 그래프 비교 + 그래프 순회 선언, 평면표 = v5-2A 평면 비교 + meta_log 행. 이후 규칙은 이 파일 하나."""
from __future__ import annotations

from hybrid52 import evidence_linker as EL
from hybrid52.flat import collect_flat, compare_flat

from . import conflict as CF, grouping as GP, lineage as LN, report as RP

EPS = 1e-6


def _v52(pg, t, mode):
    return (pg.compare(t), pg.collect(t)) if mode == "graph" else (compare_flat(pg, t), collect_flat(pg, t))


def _decl(pg, mode):
    if mode == "graph":
        return pg.declarations_graph()
    from .flat import declarations_flat
    return declarations_flat(pg)


def _group(v52, bundle, decl, known):
    cats = [EL.catalog(bundle["episodes"][e]) for e in sorted(bundle["episodes"])] + [EL.catalog(bundle["unresolved"])]
    vis = {p["record_key"] for p in bundle["provenance"] if p["status_at_as_of"] == "VISIBLE"}
    return GP.build_groups(GP.raw_uses(v52), GP.item_index(cats), vis, decl, known)


def compare521(pg, as_of: float, mode: str) -> dict:
    v52, bundle = _v52(pg, as_of, mode)
    rows, known = _decl(pg, mode)
    decl = LN.declarations(rows)
    raw, groups = _group(v52, bundle, decl, known)
    conflicts = CF.mark_conflicts(groups)
    CF.annotate_corrections(groups, bundle["provenance"])
    sup_groups, sup_raw, skipped = [], [], []
    for rec, info in sorted(CF.corrected_records(bundle["provenance"]).items()):
        th = info["superseded_at"] - EPS
        if not isinstance(info["available_time"], (int, float)) or th < info["available_time"]:
            skipped.append({"record_key": rec, "reason": "정정본과 같은 시각 이전에 공개된 적 없음 — 이전 판단 시점 없음"})
            continue
        vh, bh = _v52(pg, th, mode)
        rh, gh = _group(vh, bh, decl, known)
        sup_groups += CF.superseded_groups(gh, rh, rec, info, th)
        sup_raw += [{**r, "status": GP.SUPERSEDED, "observed_at_as_of": th} for r in rh if r["source_record_id"] == rec]
    allg = groups + sup_groups
    hyps = sorted({r["hypothesis_id"] for r in raw + sup_raw})
    per_hyp = {h: {"directional": GP.counts([r for r in raw + sup_raw if r["hypothesis_id"] == h], [g for g in allg if g["hypothesis_id"] == h], GP.DIRECTIONAL),
                   "criterion_input": GP.counts([r for r in raw if r["hypothesis_id"] == h], [g for g in groups if g["hypothesis_id"] == h], GP.CRITERION)}
               for h in hyps}
    lineage = [{**LN.resolve(k, decl, known), "declared": decl.get(k)} for k in sorted(known)]
    unres_ep = sorted(p["record_key"] for p in bundle["provenance"] if p["status_at_as_of"] == "VISIBLE" and p["episode_id"] == "UNRESOLVED_EPISODE_LINK")
    grouping = {"raw_judgments": raw, "superseded_raw_judgments": sup_raw, "groups": allg, "conflicts": conflicts, "superseded_skipped": skipped,
                "counts_by_hypothesis": per_hyp, "record_lineage": lineage, "declarations": decl,
                "unresolved_episode_records": [{"record_key": k, "lineage": next(x for x in lineage if x["record_key"] == k),
                                                "note": "에피소드 불명 — 어느 가설의 판단·그룹에도 쓰지 않음"} for k in unres_ep if k in known],
                "statements": RP.statements(raw + sup_raw, allg), "active_direction_relations_v5_2a1": 0, "clinical_validation_status": "NOT_EVALUATED"}
    return {"patient_id": pg.pid, "as_of": as_of, "mode": mode, "v5_2a": v52, "evidence_grouping": grouping}
