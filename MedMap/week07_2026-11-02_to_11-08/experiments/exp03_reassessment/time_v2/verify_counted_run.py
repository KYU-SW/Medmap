"""EXP-MAI-003 실제 실행 사후 독립 검증(PROTOCOL_TIME_v2.md §12) — 재실행 없이 로컬에서 실행.

입력: 실행 폴더(공개 JSON·RUN_RECORD), 봉인 내부 집계, 원 parquet. 파이프라인 평가(records_v2·reassess)를 다시 돌리지 않는다.
분모는 independent_audit 로 원 parquet 에서 다시 계산한다(v3b 분류가 필요한 칸은 제외).
출력: 검사 이름별 PASS/FAIL 과 실패 칸 '이름'만(값·식별자·원문 비출력). 세션과 reviewer 는 이 파일과 공개 JSON 만 읽는다.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import pandas as pd  # noqa: E402

import disclosure_schema as DSC  # noqa: E402
import disclosure_verifier as DV  # noqa: E402
import independent_audit as IA  # noqa: E402
import run_time_policy_audit_v2 as R  # noqa: E402

PUBLIC_NAME = "time_policy_audit_v2_public.json"
DETAIL_ROOTS = ("flags_by_policy", "grades_by_policy", "C_candidates_vs_used", "categories")
ID_PATTERNS = [re.compile(p) for p in (r"\b\d{8}-(RR|AR)-\d+", r"\b21\d\d-\d\d-\d\d", r"\b(rad|lab|ecg|triage):[0-9a-f]{16}\b")]
RAW_KEYS = {"lab": ("input_rows", "missing_key_rows", "unique_keys", "dup_extra_rows", "kept_unique", "attributed", "ambiguous", "unattributed",
                    "stays_with_records", "patients_with_records"),
            "radiology": ("input_rows", "missing_key_rows", "unique_keys", "dup_extra_rows", "kept_unique", "attributed", "ambiguous", "unattributed",
                          "verified_links"),
            "ecg": ("input_rows", "missing_key_rows", "unique_keys", "dup_extra_rows", "kept_unique", "matched", "stays_with_records", "patients_with_records")}


def load_detail(path: Path, note_ids: set) -> pd.DataFrame | None:
    """radiology_detail 을 파이프라인과 별도로 읽음(연결 필드만)."""
    frames = []
    chunks = [pd.read_parquet(path)] if str(path).endswith(".parquet") else pd.read_csv(path, chunksize=500_000, dtype=str,
                                                                                         usecols=["note_id", "field_name", "field_value"])
    for ch in chunks:
        ch = ch[ch["field_name"].isin(["parent_note_id", "addendum_note_id"]) & ch["note_id"].astype(str).isin(note_ids)]
        frames.append(ch[["note_id", "field_name", "field_value"]].astype(str))
    return pd.concat(frames, ignore_index=True) if frames else None


def check_raw_denominators(src: Path, detail: Path, flat: dict) -> dict:
    co = pd.read_parquet(src / "cohort.parquet")
    labs = pd.read_parquet(src / "labs.parquet", columns=["labevent_id", "subject_id", "charttime", "storetime"])
    rad = pd.read_parquet(src / "radiology.parquet", columns=["note_id", "subject_id", "note_type", "charttime", "storetime", "exam_name"])
    ecg = pd.read_parquet(src / "ecg.parquet", columns=["study_id", "ed_stay_id", "ecg_time_ext"])
    det = load_detail(detail, set(rad["note_id"].dropna().astype(str)))
    ia = IA.IndependentAudit(co, labs, rad, ecg, det, {})              # cls 비움: 분류 의존 칸(cta_input 등)은 대조하지 않음
    bad = [f"records/{s}/{k}" for s, keys in RAW_KEYS.items() for k in keys if int(ia.recon[s][k]) != int(flat.get(f"records/{s}/{k}", -1))]
    cohort = {"stays/cohort_stays": co["stay_id"].nunique(), "stays/cohort_patients": co["subject_id"].astype(str).nunique(),
              "records/triage/rows": len(co), "stays/time_defined": len(ia.win), "stays/evaluated_stays": len(ia.win),
              "stays/evaluated_patients": ia.win["subject_id"].nunique()}
    bad += [k for k, v in cohort.items() if int(v) != int(flat.get(k, -1))]
    return {"raw_denominators_match": bad, "stay_id_unique": [] if co["stay_id"].is_unique else ["cohort.stay_id"],
            "stay_has_single_patient": [] if co.groupby("stay_id")["subject_id"].nunique().max() == 1 else ["cohort.subject_id"]}


def check_public_vs_internal(pub_path: Path, flat: dict, relations_path: Path, external: dict | None) -> dict:
    pub = json.loads(pub_path.read_text(encoding="utf-8"))
    data = DV.flatten({k: v for k, v in pub.items() if k in DV.DATA_ROOTS})
    mismatch, small, detail = [], [], []
    for k, v in data.items():
        if k in pub.get("ratio_sources", {}) or k not in flat:
            continue
        if isinstance(v, int) and not isinstance(v, bool):
            if v != flat[k]:
                mismatch.append(k)
            if 1 <= v <= 9:
                small.append(k)
        elif v == DV.SMALL_TOKEN and not 1 <= flat[k] <= 9:
            mismatch.append(k)
        elif v == DV.COMPLEMENT_TOKEN and flat[k] == 0:
            mismatch.append(k)
        if (k.split("/")[0] in DETAIL_ROOTS or "STRICT=" in k) and v != DV.WITHHELD_TOKEN:
            detail.append(k)
    rate_bad = []
    for rp, (num, den) in ((r, s) for r, s in pub.get("ratio_sources", {}).items() if len(s) == 2 and "rate_diff" not in r):
        v = data.get(rp)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            if not (isinstance(data.get(num), int) and isinstance(data.get(den), int)) or round(flat[num] / flat[den], 4) != v:
                rate_bad.append(rp)
    rel = DV.load_relations(relations_path)
    if external is not None:
        rel["external_known"] = dict(external)
    rel, counts = DV.restrict_to_truth(rel, flat)
    verdict = DV.verify_file(pub_path, rel)
    untrusted_public = [c for c in rel["_untrusted"] if isinstance(data.get(c), int) or data.get(c) in (DV.SMALL_TOKEN, DV.COMPLEMENT_TOKEN)]
    text = pub_path.read_text(encoding="utf-8")
    ids = [p.pattern for p in ID_PATTERNS if p.search(text)]
    return {"public_equals_internal": mismatch, "no_public_small_integer": small, "detail_tables_withheld": detail, "rates_recompute": rate_bad,
            "disclosure_reverified": [] if verdict["status"] == DV.VERIFIED else verdict["failed"] + verdict["not_verifiable"] + ["STATUS_" + verdict["status"]],
            "untrusted_cells_not_public": untrusted_public, "no_identifier_pattern_in_public": ids,
            "_declared_relations_false_on_real": {k: v for k, v in counts.items() if k != "n_untrusted_cells"}}


def check_declared_relations(flat: dict) -> dict:
    """§6 정의 항등식(정책별 합·분모)이 내부 정확 집계에서 성립하는지 — 칸 이름만 보고."""
    s = DSC.build_schema()
    false_eq = [e["why"] for e in s["equalities"] if any(c not in flat for c in e["cells"]) or sum(w * flat[c] for c, w in zip(e["cells"], e["coef"])) != 0]
    return {"policy_identities_hold": sorted(set(false_eq))}


def check_run_record(run_dir: Path, internal_dir: Path, code_manifest: Path) -> dict:
    rec = json.loads((run_dir / "RUN_RECORD.json").read_text(encoding="utf-8"))
    bad = []
    if R.sha(run_dir / PUBLIC_NAME) != rec["public_sha256"]:
        bad.append("public_sha256")
    for n, h in rec["internal_sha256"].items():
        if R.sha(internal_dir / n) != h:
            bad.append("internal:" + n)
    if R.sha(code_manifest) != rec["code_sha_manifest_sha256"]:
        bad.append("code_sha_manifest")
    return {"output_integrity": bad}


def check_code_input(pub: dict, src: Path, detail: Path, code_manifest: Path) -> dict:
    frozen = json.loads(code_manifest.read_text(encoding="utf-8"))
    now = R.code_sha()
    code_bad = sorted(k for k in set(frozen) | set(now) | set(pub.get("code_sha256", {})) if not (frozen.get(k) == now.get(k) == pub.get("code_sha256", {}).get(k)))
    in_bad = [n for n, h in pub.get("input_sha256", {}).items() if R.sha((src / n) if n in R.INPUTS else detail) != h]
    if not set(R.INPUTS) <= set(pub.get("input_sha256", {})):
        in_bad.append("INPUTS_MISSING")
    return {"code_sha_matches_freeze": code_bad, "input_sha_matches": in_bad,
            "protocol_version_matches": [] if pub.get("protocol_version") == R.PROTOCOL_VERSION else ["protocol_version"]}


def check_gate_and_count(root: Path, run_dir: Path, internal_dir: Path, marker: Path, code_manifest: Path) -> dict:
    out = {"gate_authorization": R.gate_authorization(root, code_manifest)}
    bad = []
    if not marker.exists():
        bad.append("MARKER_MISSING")
    else:
        m = json.loads(marker.read_text(encoding="utf-8"))
        if m.get("out_dir") != run_dir.name or m.get("internal_dir") != internal_dir.name or m.get("code_sha_manifest_sha256") != R.sha(code_manifest):
            bad.append("MARKER_DOES_NOT_NAME_THIS_RUN")
    runs = sorted(p.name for p in run_dir.parent.glob("real_run_*"))
    if runs != [run_dir.name]:
        bad.append("MORE_THAN_ONE_RUN_FOLDER")
    out["counted_run_once"] = bad
    return out


def check_frozen_artifacts(internal_dir: Path) -> dict:
    """기존 동결 산출물 보존: EXP-01 FINAL SHA, FINAL_USED·TEST_USED 표지, EXP-02 동결 코드, 봉인 권한."""
    import hashlib
    root = R.RG_ROOT
    bad = []
    sums = root / "archive/final_20261029_0925_SHA256SUMS"
    n = 0
    for line in sums.read_text(encoding="utf-8").splitlines():
        if line.strip():
            h, f = line.split(None, 1)
            n += 1
            p = root / f.strip().lstrip("*")
            if not p.exists() or hashlib.sha256(p.read_bytes()).hexdigest() != h:
                bad.append("EXP01:" + p.name)
    if n != 11:
        bad.append("EXP01_SUMS_COUNT")
    if not (root / "exp/main_ai/exp01_symptom_graph/outputs/FINAL_USED").exists():
        bad.append("FINAL_USED")
    if not (R.EXP02 / "outputs/EXT_PE_V3B_TEST_USED").exists():
        bad.append("TEST_USED")
    if not R.frozen_ok():
        bad.append("EXP02_FROZEN_SHA")
    perm = []
    if stat.S_IMODE(os.stat(R.SEALED_ROOT).st_mode) != 0o700 or stat.S_IMODE(os.stat(internal_dir).st_mode) != 0o700:
        perm.append("sealed_dir_mode")
    if stat.S_IMODE(os.stat(internal_dir / "INTERNAL_AGGREGATES.json").st_mode) != 0o600:
        perm.append("internal_file_mode")
    return {"frozen_artifacts_preserved": bad, "sealed_permissions": perm}


def verify(run_dir: Path, internal_dir: Path, src: Path, detail: Path, code_manifest: Path, root: Path | None = None, marker: Path | None = None,
           relations: Path | None = None, external: dict | None = None, skip_frozen: bool = False) -> dict:
    """반환 {status, checks: {이름: PASS|FAIL}, failed_names: {이름: [칸·항목 이름]}, info}. 값·식별자 없음."""
    checks: dict = {}
    pub = json.loads((run_dir / PUBLIC_NAME).read_text(encoding="utf-8"))
    flat = json.loads((internal_dir / "INTERNAL_AGGREGATES.json").read_text(encoding="utf-8"))["flat"]
    checks.update(check_gate_and_count(root or R.RG_ROOT, run_dir, internal_dir, marker or R.COUNTED_MARKER, code_manifest))
    checks.update(check_code_input(pub, src, detail, code_manifest))
    checks.update(check_run_record(run_dir, internal_dir, code_manifest))
    checks["run_status_done"] = [] if pub.get("status") == "DONE" else ["status"]
    checks["safety_layers_recorded_zero"] = [] if pub.get("safety_checks", {}).get("violations") == 0 else ["safety_checks"]
    checks.update(check_raw_denominators(src, detail, flat))
    checks.update(check_declared_relations(flat))
    pv = check_public_vs_internal(run_dir / PUBLIC_NAME, flat, relations or R.RELATIONS_DEFAULT, external)
    info = {"declared_relations_false_on_real": pv.pop("_declared_relations_false_on_real")}
    checks.update(pv)
    if not skip_frozen:
        checks.update(check_frozen_artifacts(internal_dir))
    failed = {k: v[:50] for k, v in checks.items() if v}
    return {"status": "PASS" if not failed else "FAIL", "checks": {k: "FAIL" if v else "PASS" for k, v in checks.items()}, "failed_names": failed, "info": info,
            "note": "재실행 없음. 시간 누출·체류 혼합 감사(계층 A·B)는 실행 중 판정이며 여기서는 기록(status·violations)만 확인. 건수·식별자 비출력."}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--internal-dir", required=True)
    ap.add_argument("--src", required=True)
    ap.add_argument("--rad-detail", required=True)
    ap.add_argument("--code-sha-manifest", required=True)
    a = ap.parse_args(argv)
    try:
        res = verify(Path(a.run_dir), Path(a.internal_dir), Path(a.src), Path(a.rad_detail), Path(a.code_sha_manifest), external=R.external_public_values())
    except Exception as e:                                             # 메시지 비출력(식별자 포함 가능)
        res = {"status": "ERROR", "type": type(e).__name__, "checks": {}, "failed_names": {}}
    res["created"] = datetime.now().isoformat(timespec="seconds")
    out = Path(a.run_dir) / f"VERIFY_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print("VERIFY", res["status"], out.name)
    sys.exit(0 if res["status"] == "PASS" else 5)


if __name__ == "__main__":
    main()
