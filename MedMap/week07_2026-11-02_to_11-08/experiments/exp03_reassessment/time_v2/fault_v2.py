"""EXP-03-TIME v2 결함 주입(PROTOCOL_TIME_v2.md §11) — run 스크립트 포함 전체 경로.

exp03_reassessment 를 임시 폴더에 복사 → time_v2 파일 하나에 결함 1개 → time_v2 정상 테스트 실행.
통과 = CONTROL 'OK' + 모든 결함 'FAILED'(또는 오류). 결함마다 합성 fixture 실행의 상태·중단 단계·발동 위반 이름도 기록(어느 검사가 잡았는지). 결과 outputs/fault_v2_<시각>/fault_v2.json. 원본 수정 없음. 실제 MIMIC 없음.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RV, RUN, IA = "time_v2/records_v2.py", "time_v2/run_time_policy_audit_v2.py", "time_v2/independent_audit.py"
DSF, DVF = "time_v2/disclosure_v2.py", "time_v2/disclosure_verifier.py"
VCF = "time_v2/verify_counted_run.py"

MUTANTS = {
    "CONTROL": (RV, "DECISIVE = {", "DECISIVE = {"),
    "F01_future_info(lab available_at=charttime)": (
        RV, 'signed_or_stored_at=minutes(r.storetime), evidence_type="LAB"', 'signed_or_stored_at=minutes(r.charttime), evidence_type="LAB"'),
    "F02_STRICT_includes_C(triage at intime)": (
        RUN, "b = TP.build(stay, [stay], recs, p, ", "b = TP.build(stay, [stay], recs, S1 if p == STRICT else p, "),
    "F03_untraceable_source_accepted": (RV, 'f"hosp.labevents:{rid}"', '"hosp.labevents"'),
    "F04_cross_stay_mixing(subject 첫 체류로 귀속)": (
        RV, "return TP.attribute(r, by_subj.get(subj, []))",
        "return by_subj[subj][0].stay_id if (stay_key is None and by_subj.get(subj)) else TP.attribute(r, by_subj.get(subj, []))"),
    "F05_duplicate_source_counted": (RV, '.drop_duplicates(key, keep="first")', ""),
    "F06_PROXY_missing": (RUN, "E.proxy[p][k] += ti.proxy", "E.proxy[p][k] += 0"),
    "F07_APPROX_missing": (RUN, "E.approx[p][k] += ti.approx", "E.approx[p][k] += 0"),
    "F08_crosstab_transposed": (RUN, "E.xtab[px][k][(a0[2], ax[2])].add(sid)", "E.xtab[px][k][(ax[2], a0[2])].add(sid)"),
    "F09_inclusion_denominator(체류 수)": (
        RUN, "else round(X[num] / X[den], 4)", "else round(X[num] / n_eval, 4)"),
    "F10a_code_sha_file_missing": (RUN, '    fs["reassess.py"] = EXP03 / "reassess.py"\n', ""),
    "F10b_input_sha_wrong_file": (RUN, "in_sha = {n: sha(src / n) for n in INPUTS}", "in_sha = {n: sha(src / INPUTS[0]) for n in INPUTS}"),
    "F11a_exception_log_prints_message": (
        RUN, "print(f\"ABORT stage={STAGE['name']} type={type(e).__name__}\")",
        "print(f\"ABORT stage={STAGE['name']} type={type(e).__name__} msg={e}\")"),
    "F11b_native_id_in_event_id": (RV, 'rid = P("rad", nid)', 'rid = P("rad", nid) + nid'),
    "F12_addendum_double_reflection(대체 없음)": (
        RV, 'sup = P("rad", sup_of[nid]) if sup_of.get(nid) else None', "sup = None"),
    "F13_nonCTA_as_CTA(CT CHEST 포함)": (
        RV, 'return "CTA" if MA.classify_exam(exam_name) == "CTA_CHEST" else "OTHER"',
        'return "CTA" if MA.classify_exam(exam_name) in ("CTA_CHEST", "CT_CHEST") else "OTHER"'),
    "F14_rate_diff_sign_flipped": (RUN, "round(a - b, 4)", "round(b - a, 4)"),
    "F15_addendum_own_time_attribution(가족 귀속 제거)": (RV, "            sid = psid\n", ""),
    "X1_layer_B_disabled": (IA, "        v = Counter()\n        want =", "        return Counter()\n        want ="),
    "X3_layer_B_allowed_not_used_removed": (IA, '        v["B_allowed_not_used"] += len(want - got)\n', ""),
    "X4_layer_B_tolerance_widened": (IA, "TOL = 1e-6", "TOL = 1e12"),
    "X5_patient_mask_with_stays_disabled": (DSF, "            pub[pp] = PB.COMPLEMENT", "            pass"),
    "D1_verifier_ratio_rule_disabled": (DVF, "                failed.append(rp)                                      # 분자·분모",
                                        "                pass  # failed.append(rp)                                      # 분자·분모"),
    "D2_verifier_range_check_disabled": (DVF, "            if hi >= 1 and lo <= 9 and hi - max(lo, 1) + 1 < MIN_CANDIDATES:",
                                         "            if False:"),
    "D3_verifier_inequalities_ignored": (DVF, '    ineq = rel.get("inequalities", [])', "    ineq = []"),
    "D4_protector_no_withholding": (DSF, "            for t in cand:\n                for k in tables[t]:\n                    pub[k] = WITHHELD",
                                    "            for t in cand:\n                for k in []:\n                    pub[k] = WITHHELD"),
    "D5_patient_policy_disabled": (DSF, '        if (k[-1] == "patients" and k not in PATIENT_WHITELIST) or k in PATIENT_INTERNAL_ONLY:', "        if False:"),
    "D6_published_file_recheck_disabled": (RUN, "    if re[\"status\"] != DV.VERIFIED:", "    if False:"),
    "D7_min_candidates_1": (DVF, "MIN_CANDIDATES = 5", "MIN_CANDIDATES = 1"),
    # 2026-11-03 개정 결함(§5-1·§9-3) — 원래 결함을 되살림
    "D8_false_equality_silently_dropped": (DVF, '            eqs.append(e)\n        else:\n            untrusted.update(e["cells"])',
                                           '            eqs.append(e)'),
    "D9_constant_mismatch_on_masked_ignored": (DVF, 'if is_token and (k in const or k in gen_const or k not in idx):', 'if is_token and k not in idx:'),
    "D10_direct_small_integer_not_checked": (DVF, "            if 1 <= v <= 9 and k not in external:", "            if False:"),
    "D11_old_range_rule_requires_lo_ge_1": (DVF, "            if hi >= 1 and lo <= 9 and hi - max(lo, 1) + 1 < MIN_CANDIDATES:",
                                            "            if lo >= 1 and hi <= 9 and hi - lo + 1 < MIN_CANDIDATES:"),
    "D12_external_values_ignored": (DVF, '    external = rel.get("external_known", {})', "    external = {}"),
    "D13_detail_tier_published": (DSF, "PUBLISH_TIERS = (1, 2)", "PUBLISH_TIERS = (1, 2, 3)"),
    "D14_generator_constant_trusted_as_knowledge": (DVF, '        if truth.get(c, 0) != v:\n            untrusted.add(c)\n            n_gen_false += 1',
                                                    '        if truth.get(c, 0) != v:\n            n_gen_false += 1'),
    "D15_general_inequalities_ignored": (DVF, '    gen_ineq = rel.get("inequalities_general", [])', "    gen_ineq = []"),
    "D16_untrusted_cells_published": (DVF, "        if k in untrusted and (_is_count(v) or is_token):", "        if False:"),
    "D17_false_inequality_silently_dropped": (DVF, '            ineq.append(x)\n        else:\n            untrusted.update(x)', "            ineq.append(x)"),
    "D18_internal_overwrite_allowed": (RUN, '    if (d / "INTERNAL_AGGREGATES.json").exists():', "    if False:"),
    "D19_unchecked_public_file_left": (RUN, "    tmp_file.replace(pub_file)", '    import shutil as _s; _s.copy(tmp_file, pub_file)'),
    "D20_external_mismatch_not_withheld": (RUN, "withhold_all=withhold_all or ext_mismatch)", "withhold_all=withhold_all)"),
    "D21_patient_table_not_separate": (DSF, 'return ("stays_patients", 1) if "patients" in str(path[1]) else ("stays", 1)', 'return "stays", 1'),
    "O1_addendum_order_rule_disabled": (RV, "        if reason:\n            ra[reason] += 1\n            order_excl.add(nid)", "        if False:\n            pass"),
    "O2_order_rule_only_storetime(기록 시각 무시)": (RV, 'elif nid in eligible and cc < pc:', "elif False:"),
    "O3_order_parent_unknown_not_excluded": (RV, "if ps is None or pc is None or ps < pc:", "if False:"),
    "O4_layer_B_order_rule_missing": (IA, "        drop |= order\n", ""),
    "O5_excluded_addendum_still_supersedes": (RV, "sorted((c for c in chs if c in store_of and c not in skip and c not in order_excl),", "sorted((c for c in chs if c in store_of and c not in skip),"),
    # 2026-11-04 추가 — 실행 관문·1회 실행·정수 재확인·단위 분리·사후 검증
    "G1_cli_gate_guard_removed": (RUN, "    authorize_counted_run(a)                                          # gate RUN", "    pass  # gate RUN"),
    "G2_review_status_ignored": (RUN, '    if m.get("review_status") != "RUN":', "    if False:"),
    "G3_last_gate_verdict_ignored": (RUN, '    if not gates or gates[-1].get("verdict") != "RUN":', "    if False:"),
    "G4_used_marker_check_removed": (RUN, "    if COUNTED_MARKER.exists():", "    if False:"),
    "G5_marker_not_exclusive": (RUN, "os.O_CREAT | os.O_EXCL | os.O_WRONLY", "os.O_CREAT | os.O_WRONLY"),
    "G6_unreviewed_code_manifest_accepted": (RUN, "    if not frozen or not Path(code_manifest).exists() or sha(Path(code_manifest)) != frozen:", "    if False:"),
    "G7_deviation_treated_as_authorization": (RUN, "    return why\n\n\ndef claim_counted_run", '    return [] if (exp / "deviations.yaml").exists() else why\n\n\ndef claim_counted_run'),
    "G8_protocol_lock_ignored": (RUN, '        if q.returncode != 0 or q.stdout.strip() != "OK":', "        if False:"),
    "I1_integer_recheck_disabled": (DVF, "            elif integer_check and hi >= 1 and lo <= 9 and hi <= INTEGER_RECHECK_HI:", "            elif False:"),
    "U1_stays_counted_as_records": (RV, '        A[name]["stays_with_records"] = len(sids)', '        A[name]["stays_with_records"] = sum(len(per_stay[s]) for s in sids)'),
    "V1_public_internal_compare_removed": (VCF, "            if v != flat[k]:", "            if False:"),
    "V2_output_integrity_removed": (VCF, '    if R.sha(run_dir / PUBLIC_NAME) != rec["public_sha256"]:', "    if False:"),
    "V3_raw_denominator_compare_removed": (VCF, 'if int(ia.recon[s][k]) != int(flat.get(f"records/{s}/{k}", -1))]', "if False]"),
    "V4_second_run_folder_ignored": (VCF, "    if runs != [run_dir.name]:", "    if False:"),
    "V5_policy_identity_check_removed": (VCF, '    false_eq = [e["why"] for e in s["equalities"] if any(c not in flat for c in e["cells"]) or sum(w * flat[c] for c, w in zip(e["cells"], e["coef"])) != 0]', "    false_eq = []"),
    "X6_code_sha_zero_key_aborts_valid_run": (RUN, "        if bad:                                                        # 0 건을",
                                              "        if True:                                                       # 0 건을"),
    "X7_cross_subject_addendum_link_allowed": (RV, "if subj_of is not None and subj_of.get(ch) != subj_of.get(pa):", "if False:"),
    "X8_exact_differs_identity_group_removed": (RUN, "            G.append([(\"paired_crosstab_vs_STRICT\", px, k, \"differs\", \"summary\", \"stays\")] +             # 정확한 항등식",
                                                "            G.append([] +             # 정확한 항등식"),
    "X9_cross_policy_equal_groups_removed": (RUN, '            G.extend(eq_chain([("usage", p, k, "used", s_) for p in POLS]))', "            pass"),
    "X10_equal_quantity_as_one_3cell_group": (RUN, '            G.extend(eq_chain([("usage", p, k, "used", s_) for p in POLS]))',
                                              '            G.append([("usage", p, k, "used", s_) for p in POLS])'),
    "X11_rad_flag_chain_missing(lab 만 사슬)": (RUN, '            G.extend(eq_chain([("flags_by_policy", p, f"{s_}:{f}") for p in POLS]))',
                                              '            G.extend(eq_chain([("flags_by_policy", p, f"{s_}:{f}") for p in POLS]) if s_ == "lab" else [])'),
    "X2_NO_MENTION_addendum_replaces": (RV, "if nid in links and cls[nid] not in DECISIVE:", "if False:"),
}


PROBE = """
import sys, tempfile; from pathlib import Path
sys.path.insert(0, '.'); sys.path.insert(0, 'tests')
import fixture_v2 as FX, run_time_policy_audit_v2 as R
t = Path(tempfile.mkdtemp()); s = FX.write(t / 'src')
try:
    r = R.run(s, t / 'o', s / 'radiology_detail.parquet', expected_code_sha=R.code_sha(), withhold_all=True)
    print(r['status'], r.get('stage'), sorted(r.get('violations', {})))
except Exception as e:
    print('EXCEPTION', type(e).__name__)
"""


FAST_TESTS = ["tests.test_disclosure_v3.FalseRelations", "tests.test_disclosure_v3.Ranges", "tests.test_disclosure_v3.External", "tests.test_disclosure_v3.Scope",
              "tests.test_disclosure_v3.Schema", "tests.test_disclosure_v3.AddendumOrder", "tests.test_disclosure_v2.Attacks", "tests.test_disclosure_v2.Protect", "tests.test_v2",
              "tests.test_counted_run.GateGuard", "tests.test_counted_run.OneShot", "tests.test_counted_run.RecordUnits", "tests.test_counted_run.IntegerGap",
              "tests.test_counted_run.RealInputDtypes"]


def one(args):
    """결함 1개: 빠른 테스트 → (살아남으면) 전체 테스트. 어느 단계에서 잡혔는지 기록. CONTROL 은 항상 전체."""
    i, name, f, old, new, tmp, env = args
    d = Path(tmp) / f"m{i}"
    shutil.copytree(ROOT, d, ignore=shutil.ignore_patterns("outputs", "logs", "__pycache__"))
    src = (d / f).read_text(encoding="utf-8")
    assert src.count(old) == 1, name
    (d / f).write_text(src.replace(old, new, 1), encoding="utf-8")
    cmds = [[sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"]] if name == "CONTROL" else \
        [[sys.executable, "-B", "-m", "unittest", *FAST_TESTS], [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"]]
    last, failing, stage, rc = [], [], None, 0
    for k, cmd in enumerate(cmds):
        p = subprocess.run(cmd, cwd=d / "time_v2", env=env, capture_output=True, text=True, timeout=3000)
        rc = p.returncode
        last = [ln for ln in p.stderr.splitlines() if ln.startswith(("OK", "FAILED"))]
        failing = sorted({ln.split("(")[0].replace("FAIL: ", "").replace("ERROR: ", "").strip()
                          for ln in p.stderr.splitlines() if ln.startswith(("FAIL:", "ERROR:"))})
        stage = "fast" if len(cmds) == 2 and k == 0 else "full"
        if not (last and last[-1].startswith("OK")):
            break
    q = subprocess.run([sys.executable, "-B", "-c", PROBE], cwd=d / "time_v2", env=env, capture_output=True, text=True, timeout=1200)
    shutil.rmtree(d, ignore_errors=True)
    print(name, last[-1] if last else f"ERROR rc={rc}", stage, flush=True)
    return name, {"result": last[-1] if last else f"ERROR rc={rc}", "stage": stage, "failing_tests": failing,
                  "fixture_run(status·stage·violations)": (q.stdout.strip().splitlines() or [f"rc={q.returncode}"])[-1]}


def main():
    env = dict(os.environ, EXP03_ENGINE=str(ROOT.parent / "exp01b_graph_engine"), EXP03_EXP02=str(ROOT.parent / "exp02_mimic_graph"), EXP03_RG_ROOT=str(ROOT.parents[1]),
               OMP_NUM_THREADS="1", OPENBLAS_NUM_THREADS="1", MKL_NUM_THREADS="1")
    res = {}
    with tempfile.TemporaryDirectory() as tmp:
        only = set(filter(None, os.environ.get("FAULT_ONLY", "").split(",")))   # 선택 재실행(대조 항상 포함)
        jobs = [(i, name, f, old, new, tmp, env) for i, (name, (f, old, new)) in enumerate(MUTANTS.items())
                if not (only and name != "CONTROL" and not any(name.startswith(o) for o in only))]
        for j in jobs:                                                  # 대상 문자열 사전 확인 — 조용히 건너뛰지 않음
            assert (ROOT / j[2]).read_text(encoding="utf-8").count(j[3]) == 1, j[1]
        with ThreadPoolExecutor(max_workers=int(os.environ.get("FAULT_WORKERS", "4"))) as ex:
            res = dict(ex.map(one, jobs))
    survived = sorted(k for k, v in res.items() if k != "CONTROL" and v["result"].startswith("OK"))
    ok = res["CONTROL"]["result"].startswith("OK") and not survived
    out = HERE / "outputs" / f"fault_v2_{datetime.now():%Y%m%d_%H%M%S}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "fault_v2.json").write_text(json.dumps({"created": datetime.now().isoformat(timespec="seconds"), "results": res,
                                                   "all_detected_with_control_ok": ok, "survived": survived, "n_mutants": len(res) - 1}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("ALL_DETECTED", ok, "survived", survived, out.name)


if __name__ == "__main__":
    main()
