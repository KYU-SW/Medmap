"""EXP-MAI-003 (EXP-03-TIME) 실제 MIMIC 시간 정책 집계 — 실행은 rg-gate RUN + 사용자 명시 승인 후에만(작성 2026-11-03, 미실행).

입력: EXP-02 봉인 추출 폴더(cohort/labs/radiology/ecg parquet) — 로컬 처리, 원문·식별자 비출력.
처리: 체류마다 원시 기록 → time_policy 3정책(STRICT·S1·S2) → reassess.assess(SIMULATED_WD = PE 가설, set_at = intime) at T0/T1/T2.
출력: 공개 집계 JSON 만(10 미만 '<10'). 중단 조건 위반 시 ABORT JSON 을 쓰고 종료 코드 3(결과 무효).
판독 분류 = EXP-02 동결 v3b(읽기 전용). 의뢰 시각은 MIMIC 에 없어 PENDING(R6)은 생성되지 않음(한계).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
EXP03 = HERE.parent
EXP02 = EXP03.parent / "exp02_mimic_graph"
for p in (str(HERE), str(EXP03), str(EXP02)):
    if p not in sys.path:
        sys.path.insert(0, p)

import mimic_adapter as MA  # noqa: E402  (EXP-02, 읽기 전용)
import time_policy as TP  # noqa: E402
from ct_bridge import classify  # noqa: E402  (v3b 동결 분류기)
from reassess import PE, assess  # noqa: E402

FROZEN = {"exp02_v3b_freeze": EXP02 / "outputs/ext_pe_v3_freeze_20261030_1802/ext_pe_v3_freeze.json"}
SMALL = 10


def cell(n):
    n = int(n)
    return n if n == 0 or n >= SMALL else f"<{SMALL}"


def minutes(x):
    return None if pd.isna(x) else pd.Timestamp(x).timestamp() / 60.0


def frozen_ok() -> bool:
    fz = json.loads(FROZEN["exp02_v3b_freeze"].read_text(encoding="utf-8"))
    return all(hashlib.sha256((EXP02 / f).read_bytes()).hexdigest() == h for f, h in fz["code_sha256"].items())


def stay_records(st: dict, labs: pd.DataFrame, rad: pd.DataFrame, ecg: pd.DataFrame) -> list:
    """원시 기록 생성 — 시각은 원 필드 그대로(대체·추정 없음)."""
    recs = []
    sid, subj = str(st["stay_id"]), str(st["subject_id"])
    for e in MA.triage_records(f"tr{sid}", st, 0.0):
        recs.append(TP.RawRecord(e.evidence_id, subj, "triage", f"ed.triage:stay={sid}", stay_id=sid,
                                 evidence_type="VITAL" if e.source_type == "triage_vital" else "SYMPTOM",
                                 evidence_status=e.status.value, concept=e.node_id))
    for r in labs.itertuples(index=False):
        item = int(r.itemid)
        if item in MA.HIV_ITEMS:
            node, status = "CONCEPT:hiv_infection", MA.hiv_status(MA.HIV_ITEMS[item], r.value).value
        else:
            node = MA.LAB_NODE[item]
            status = MA.lab_status(r.value, r.valuenum, r.ref_range_upper, getattr(r, "comments", None))[0].value
        recs.append(TP.RawRecord(f"lab{r.labevent_id}", subj, "lab", f"hosp.labevents:{r.labevent_id}",
                                 observed_at=minutes(r.charttime), charted_at=minutes(r.charttime),
                                 signed_or_stored_at=minutes(r.storetime), evidence_type="LAB", evidence_status=status, concept=node))
    for r in rad.itertuples(index=False):
        is_cta = MA.classify_exam(r.exam_name) == "CTA_CHEST"
        cls = classify(r.text, "v3b")[0] if is_cta else ""
        recs.append(TP.RawRecord(f"rad{r.note_id}", subj, "radiology", f"note.radiology:{r.note_id}",
                                 observed_at=minutes(r.charttime), charted_at=minutes(r.charttime),
                                 signed_or_stored_at=minutes(r.storetime),
                                 evidence_type="IMAGING_REPORT" if is_cta else "SYMPTOM",
                                 evidence_status={"NEGATIVE": "NEGATIVE", "UNCERTAIN": "UNCERTAIN", "NO_MENTION": "NOT_ASSESSABLE"}.get(cls, "POSITIVE") if is_cta else "NOT_ASSESSABLE",
                                 concept="CONCEPT:ctpa_filling_defect" if is_cta else "RAD:non_cta", pe_class=cls))
    for r in ecg.itertuples(index=False):
        recs.append(TP.RawRecord(f"ecg{r.study_id}", subj, "ecg_machine", f"ecg.machine_measurements:{r.study_id}", stay_id=sid,
                                 observed_at=minutes(r.ecg_time_ext), concept="ECG:machine_read"))
    return recs


def run(src: Path, out_dir: Path, limit: int | None = None) -> dict:
    co = pd.read_parquet(src / "cohort.parquet")
    labs = pd.read_parquet(src / "labs.parquet")
    rad = pd.read_parquet(src / "radiology.parquet", columns=["note_id", "subject_id", "charttime", "storetime", "text", "exam_name"])
    ecg = pd.read_parquet(src / "ecg.parquet", columns=["study_id", "ed_stay_id", "ecg_time_ext"])
    if limit:
        co = co.head(limit)
    stays_by_subj = defaultdict(list)
    for s in co.itertuples(index=False):
        stays_by_subj[str(s.subject_id)].append(TP.Stay(str(s.stay_id), str(s.subject_id), minutes(s.intime), minutes(s.outtime)))
    lab_by = dict(tuple(labs.groupby("subject_id")))
    rad_by = dict(tuple(rad.groupby("subject_id")))
    ecg_by = dict(tuple(ecg.groupby("ed_stay_id")))
    pols = list(TP.POLICIES)
    rec_counts = Counter()
    used = {p: Counter() for p in pols}
    states = {p: {k: Counter() for k in ("T0", "T1", "T2")} for p in pols}
    diff = Counter()
    stop = Counter()
    n_stays = 0
    for st in co.to_dict("records"):
        n_stays += 1
        subj = str(st["subject_id"])
        stay = next(s for s in stays_by_subj[subj] if s.stay_id == str(st["stay_id"]))
        T = (stay.intime, min(stay.intime + 180, stay.outtime), stay.outtime)
        recs = stay_records(st, lab_by.get(st["subject_id"], labs.iloc[0:0]), rad_by.get(st["subject_id"], rad.iloc[0:0]),
                            ecg_by.get(st["stay_id"], ecg.iloc[0:0]))
        per_pol = {}
        for p in pols:
            b = TP.build(stay, stays_by_subj[subj], recs, p, [("h1", PE, stay.intime)])
            if p == pols[0]:
                for k, v in b.audit.items():
                    rec_counts[k] += v
                for r in recs:
                    rec_counts[f"source:{r.source}"] += 1
            for e in b.timeline.evidence:
                if e.encounter_id != stay.stay_id:
                    stop["cross_stay_evidence"] += 1
                if not e.source_reference:
                    stop["missing_source"] += 1
            res = []
            for k, t in zip(("T0", "T1", "T2"), T):
                u = TP.used_at(b, t)
                used[p][f"{k}_used"] += len(u)
                used[p][f"{k}_stays_with_any"] += bool(u)
                if p == "STRICT_AVAILABLE_TIME":
                    stop["strict_C_used"] += sum(b.meta[i].grade == TP.C for i in u)
                a = assess(b.timeline, t)
                if a.key() != assess(b.timeline.truncated(t), t).key():
                    stop["leakage"] += 1
                states[p][k][a.summary] += 1
                res.append((a.summary, frozenset(x["rule"] for x in a.alerts)))
            used[p]["stays_state_changed_T0_T2"] += len({r[0] for r in res}) > 1
            per_pol[p] = res
        for p in pols[1:]:
            for i, k in enumerate(("T0", "T1", "T2")):
                diff[f"{p}_vs_STRICT_{k}_summary_differs"] += per_pol[p][i][0] != per_pol[pols[0]][i][0]
                diff[f"{p}_vs_STRICT_{k}_alerts_differ"] += per_pol[p][i][1] != per_pol[pols[0]][i][1]
        if any(stop.values()):
            break                                                   # 중단 조건 — 즉시 멈춤
    out_dir.mkdir(parents=True, exist_ok=False)
    res = {"created": datetime.now().isoformat(timespec="seconds"), "source": src.name, "n_stays_processed": n_stays,
           "n_patients": cell(len(stays_by_subj)), "simulated_wd": "PE 가설, set_at = ED intime, provenance SIMULATED_WD",
           "stop_conditions": dict(stop), "record_audit_STRICT": {k: cell(v) for k, v in sorted(rec_counts.items())},
           "used": {p: {k: cell(v) for k, v in c.items()} for p, c in used.items()},
           "states": {p: {k: {s: cell(n) for s, n in c.items()} for k, c in d.items()} for p, d in states.items()},
           "policy_differences(stays)": {k: cell(v) for k, v in diff.items()},
           "interpretation": "시스템 동작 기술 — 임상 정확도·오진 탐지 아님. 포함률이 높은 정책이 더 우수하다는 뜻 아님."}
    name = "ABORT_time_policy_audit.json" if any(stop.values()) else "time_policy_audit_public.json"
    (out_dir / name).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="봉인 추출 폴더(extract_v2_20261030_1139)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--i-have-user-approval", action="store_true", help="rg-gate RUN + 사용자 명시 승인 후에만")
    a = ap.parse_args()
    if not a.i_have_user_approval:
        raise SystemExit("승인 플래그 없음 — 실행하지 않음(rg-gate RUN + 사용자 명시 승인 필요)")
    if not frozen_ok():
        raise SystemExit("동결 코드 무결성 실패 — 중단")
    res = run(Path(a.src), Path(a.out))
    if any(res["stop_conditions"].values()):
        print("ABORT", res["stop_conditions"])
        sys.exit(3)
    print("DONE", a.out)


if __name__ == "__main__":
    main()
