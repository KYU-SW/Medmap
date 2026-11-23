"""EXP-03-TIME 결함 주입(정상 테스트와 별개): exp03_reassessment 를 임시 폴더에 복사 → time_policy.py 에 결함 1개 → time_v1 정상 테스트 실행.
기대: 대조 OK, 결함마다 FAILED. 결과 outputs/fault_time_<시각>/fault_time.json. 원본 수정 없음."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
F = "time_v1/time_policy.py"
MUTANTS = {
    "CONTROL": ("A, B, C = ", "A, B, C = "),
    "TF1_future_result_into_past(charttime 사용)": ("    return TimeInfo(s, grade,", "    s = r.observed_at if r.observed_at is not None else s\n    return TimeInfo(s, grade,"),
    "TF2_strict_injects_triage_at_intime": ('"STRICT_AVAILABLE_TIME": {"grades": {A, B}, "triage_at_intime": False}',
                                            '"STRICT_AVAILABLE_TIME": {"grades": {A, B}, "triage_at_intime": True}'),
    "TF3_ecg_device_time_used": ('        return TimeInfo(None, C, "NOT_IDENTIFIABLE")', '        return TimeInfo(r.observed_at, B, "OK")'),
    "TF4_time_inversion_allowed": ("    if r.observed_at is not None and s < r.observed_at:", "    if False:"),
    "TF5_missing_storetime_filled_with_charttime": ("    s = r.signed_or_stored_at\n", "    s = r.signed_or_stored_at if r.signed_or_stored_at is not None else r.observed_at\n"),
    "TF6_stay_mixing(subject 만으로 귀속)": ("    hit = [s.stay_id for s in mine if s.intime <= r.observed_at <= s.outtime]", "    hit = [mine[0].stay_id]"),
    "TF7_no_source_accepted": ('        if not r.source_reference:\n            out.audit["REJECTED_NO_SOURCE"] += 1\n            continue',
                               '        if False:\n            pass'),
}


def main():
    env = dict(os.environ, EXP03_ENGINE=str(ROOT.parent / "exp01b_graph_engine"), EXP03_EXP02=str(ROOT.parent / "exp02_mimic_graph"))
    res = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, (old, new) in MUTANTS.items():
            d = Path(tmp) / f"m{len(res)}"
            shutil.copytree(ROOT, d, ignore=shutil.ignore_patterns("outputs", "logs", "__pycache__"))
            src = (d / F).read_text(encoding="utf-8")
            assert old in src, name
            (d / F).write_text(src.replace(old, new, 1), encoding="utf-8")
            p = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=d / "time_v1", env=env,
                               capture_output=True, text=True, timeout=300)
            last = [l for l in p.stderr.splitlines() if l.startswith(("OK", "FAILED"))]
            res[name] = last[-1] if last else f"ERROR rc={p.returncode}"
    ok = res["CONTROL"].startswith("OK") and all(v.startswith("FAILED") for k, v in res.items() if k != "CONTROL")
    out = HERE / "outputs" / f"fault_time_{datetime.now():%Y%m%d_%H%M}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "fault_time.json").write_text(json.dumps({"results": res, "all_detected_with_control_ok": ok}, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1), "\nALL_DETECTED", ok)


if __name__ == "__main__":
    main()
