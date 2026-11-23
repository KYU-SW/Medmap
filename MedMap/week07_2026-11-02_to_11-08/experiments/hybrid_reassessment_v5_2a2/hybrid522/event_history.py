"""검사 사건별 판독 이력. 사건 식별은 v5-2A.1 lineage(명시 사건 ID·파생) + 명시 supersedes 만 사용한다.
버전마다 '그 기록에 직접 귀속되는 원시 판단'만 담는다 — 다른 사건·다른 기록의 판단은 넣지 않는다.
버전의 판단은 유효 구간(공개~정정 공개) 안의 실제 as_of 시점별 관측으로 기록하고, 구간 안에서 판단이 바뀌면 원인(문맥 변화 등)을 표시한다."""
from __future__ import annotations

from hybrid521 import lineage as LN

from . import attribution as AT


def _correction_issues(recs: dict) -> dict:
    issues = {k: [] for k in recs}
    for k in recs:
        seen, cur = [], k
        while True:
            nxt = recs[cur]["corrects"]
            if not nxt:
                break
            p = nxt[0]
            if p not in recs:
                issues[k].append(f"CORRECTION_PARENT_MISSING({p})")
                break
            if p in seen or p == k:
                for x in seen + [k]:
                    if "CORRECTION_CYCLE" not in issues[x]:
                        issues[x].append("CORRECTION_CYCLE")
                break
            seen.append(cur)
            cur = p
    return issues


def resolve_events(decl: dict, known: set, prov_all: list) -> dict:
    recs = {p["record_key"]: p for p in prov_all}
    res = {k: LN.resolve(k, decl, known) for k in recs}
    cor = _correction_issues(recs)
    ev = {k: (r["event_id"] if not cor[k] else None) for k, r in res.items()}
    basis = {k: r["basis"] for k, r in res.items()}
    changed = True
    while changed:                                                        # 명시 supersedes 로 사건 상속(사건 ID 없는 정정본)
        changed = False
        for k, p in recs.items():
            if ev[k] is None and not res[k]["issues"] and not cor[k] and p["corrects"]:
                par = p["corrects"][0]
                if ev.get(par):
                    ev[k], basis[k], changed = ev[par], "SUPERSEDES_CHAIN", True
    out = {}
    for k, p in recs.items():
        issues = res[k]["issues"] + cor[k]
        for c in p["corrects"]:
            if c in recs and ev.get(c) and ev[k] and ev[c] != ev[k]:
                issues.append(f"CROSS_EVENT_CORRECTION({c}:{ev[c]})")
        ek = f"{ev[k]}@{p['episode_id']}" if ev[k] and not issues else None
        out[k] = {"record_key": k, "event_key": ek, "event_id": ev[k] if ek else None, "episode_id": p["episode_id"], "basis": basis[k], "issues": issues,
                  "version_id": None}
    return out


def build(decl: dict, known: set, prov_all: list, snaps: list) -> dict:
    recs = {p["record_key"]: p for p in prov_all}
    eor = resolve_events(decl, known, prov_all)
    held = {k for k, p in recs.items() if any(i == "CORRECTION_CYCLE" for i in _correction_issues(recs)[k])}
    events = {}
    for k, e in eor.items():
        if e["event_key"]:
            events.setdefault(e["event_key"], []).append(k)
    out = []
    for ek in sorted(events):
        members = sorted(events[ek], key=lambda k: (recs[k]["available_time"] if isinstance(recs[k]["available_time"], (int, float)) else float("inf"), k))
        comp = {m: m for m in members}

        def root(x):
            while comp[x] != x:
                x = comp[x]
            return x
        for m in members:
            for c in recs[m]["corrects"]:
                if c in comp:
                    comp[root(m)] = root(c)
        comps = {}
        for m in members:
            comps.setdefault(root(m), []).append(m)
        versions = []
        for ci, (_, ms) in enumerate(sorted(comps.items(), key=lambda kv: members.index(kv[1][0])), start=1):
            for vi, m in enumerate(ms, start=1):
                vid = f"{ek}:C{ci}:V{vi}"
                eor[m]["version_id"] = vid
                p = recs[m]
                cts = [recs[c]["available_time"] for c in p["corrected_by"] if c in recs and isinstance(recs[c]["available_time"], (int, float))]
                versions.append({"version_id": vid, "chain_index": ci, "version_index": vi, "source_record_id": m, "episode_id": p["episode_id"],
                                 "record_type": p["record_type"], "observation_time": p["observation_time"], "available_time": p["available_time"],
                                 "supersedes": p["corrects"], "superseded_by": p["corrected_by"], "correction_time": min(cts) if cts else None,
                                 "lineage_basis": eor[m]["basis"], "status_timeline": [], "direct_judgment_observations": []})
        for s in snaps:
            for v in versions:
                st = s["record_status"].get(v["source_record_id"], "UNKNOWN")
                st = "CORRECTION_CYCLE_HOLD" if v["source_record_id"] in held else {"VISIBLE": "ACTIVE", "SUPERSEDED": "SUPERSEDED", "NOT_YET_AVAILABLE": "NOT_YET_AVAILABLE"}.get(
                    st, "SUPERSEDED" if st == "NOT_VISIBLE" and v["superseded_by"] else st)
                v["status_timeline"].append({"as_of": s["as_of"], "version_status": st})
                if st == "ACTIVE":
                    for r in s["raw_judgments"]:
                        if r["source_record_id"] == v["source_record_id"]:
                            v["direct_judgment_observations"].append({"as_of": s["as_of"], **{k: r[k] for k in ("raw_id", "raw_kind", "hypothesis_id", "relation_id", "finding_key",
                                                                                                                  "directional_result", "hold_reason", "context_record_ids")},
                                                                      "attribution": AT.judgment_attribution(r, eor)})
        for v in versions:
            summ = {}
            for o in v["direct_judgment_observations"]:
                d = summ.setdefault(o["raw_id"], {"raw_id": o["raw_id"], "raw_kind": o["raw_kind"], "relation_id": o["relation_id"], "first_observed_as_of": o["as_of"],
                                                  "first_observed_result": [o["directional_result"], o["hold_reason"]], "results_over_validity": [], "context_record_ids": set()})
                if [o["directional_result"], o["hold_reason"]] not in d["results_over_validity"]:
                    d["results_over_validity"].append([o["directional_result"], o["hold_reason"]])
                d["context_record_ids"] |= set(o["context_record_ids"])
            for d in summ.values():
                d["context_record_ids"] = sorted(d["context_record_ids"])
                d["stable_within_validity"] = len(d["results_over_validity"]) == 1
                d["note"] = "유효 구간 안에서 판단 일정" if d["stable_within_validity"] else \
                    "같은 판독 버전인데 구간 안에서 판단이 바뀜 — 다른 기록의 문맥 변화 영향(patient_history 원인 참조). 사건 단독 판단으로 보지 않음"
            v["direct_judgment_summary"] = [summ[k] for k in sorted(summ)]
        state = []
        for s in snaps:
            act = [v for v in versions if next(x["version_status"] for x in v["status_timeline"] if x["as_of"] == s["as_of"]) == "ACTIVE"]
            eid = ek.split("@")[0]
            conf = [c for c in s["v5_2a1_conflicts"] if c["source_event_id"] == eid and c["episode_id"] == ek.split("@", 1)[1]]
            if any(v["source_record_id"] in held for v in versions):
                es = "HOLD_CORRECTION_CYCLE"
            elif conf:
                es = "CONFLICTING_EVENT_EVIDENCE_HOLD"
            elif len({v["chain_index"] for v in act}) > 1:
                es = "MULTIPLE_PARALLEL_REPORTS"
            elif act:
                es = "SINGLE_ACTIVE_VERSION"
            else:
                es = "NO_ACTIVE_VERSION"
            state.append({"as_of": s["as_of"], "event_state": es, "active_version_ids": [v["version_id"] for v in act], "conflicts": conf})
        out.append({"history_type": "EVENT_VERSION_HISTORY", "event_key": ek, "source_event_id": ek.split("@")[0], "episode_id": ek.split("@", 1)[1],
                    "versions": versions, "state_timeline": state, "patient_id": None})
    unres = []
    for k, e in sorted(eor.items()):
        if e["event_key"]:
            continue
        obs = [{"as_of": s["as_of"], "raw_id": r["raw_id"], "directional_result": r["directional_result"], "hold_reason": r["hold_reason"],
                "attribution": AT.judgment_attribution(r, eor)} for s in snaps for r in s["raw_judgments"] if r["source_record_id"] == k]
        unres.append({"record_key": k, "status": "UNRESOLVED_EVENT_LINK" if not e["issues"] else "INVALID_EVENT_METADATA", "issues": e["issues"],
                      "episode_id": e["episode_id"], "judgment_observations": obs})
    return {"events": out, "unresolved_event_links": unres, "event_of_record": eor, "held_records": sorted(held)}


def active_versions_fn(hist: dict):
    def f(s):
        return {e["event_key"]: next(x["active_version_ids"] for x in e["state_timeline"] if x["as_of"] == s["as_of"]) for e in hist["events"]}
    return f
