"""EXP-03 결함 주입: 대조 사본 + 7개 변이를 임시 폴더에 복사해 테스트 실행 → 테스트가 결함을 검출(FAILED)해야 함.
결과 = outputs/fault_injection_<시각>/fault_injection.json. 원본 파일은 수정하지 않는다."""
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
MUTANTS = {
    "CONTROL": ("reassess.py", "PE = ", "PE = "),
    "F1_future_result_into_past": ("reassess.py", "    return e.available_at <= T\n", "    return (e.observed_at if e.observed_at is not None else e.available_at) <= T\n"),
    "F2_pending_to_negative": ("reassess.py", 'return ("PENDING", "R6") if dx == PE', 'return ("CONFLICTS", "R2") if dx == PE'),
    "F3_source_id_removed": ("reassess.py", '"evidence_type": r[3], "source_reference": r[4],', '"evidence_type": r[3], "source_reference": "",'),
    "F4_hypothesis_history_ignored": ("reassess.py", "hs = sorted((h for h in tl.hypotheses if h.set_at <= T), key=lambda h: h.set_at)",
                                      "hs = sorted(tl.hypotheses, key=lambda h: h.set_at)"),
    "F5_chronic_as_acute": ("reassess.py", '"CHRONIC_OR_PERSISTENT": ("NOT_CONFIRM_ACUTE", "R3")', '"CHRONIC_OR_PERSISTENT": ("SUPPORTS", "R1")'),
    "F6_correction_ignored": ("reassess.py", "    eff = [e for e in use if e.event_id not in superseded]", "    eff = list(use)"),
    "F7_cross_encounter_allowed": ("reassess.py", "        if e.encounter_id != self.encounter_id:\n            raise", "        if False:\n            raise"),
}


def main():
    env = dict(os.environ, EXP03_ENGINE=str(HERE.parent / "exp01b_graph_engine"), EXP03_EXP02=str(HERE.parent / "exp02_mimic_graph"))
    res = {}
    with tempfile.TemporaryDirectory() as tmp:
        for name, (f, old, new) in MUTANTS.items():
            d = Path(tmp) / name
            shutil.copytree(HERE, d, ignore=shutil.ignore_patterns("outputs", "logs", "__pycache__"))
            src = (d / f).read_text(encoding="utf-8")
            assert old in src, name
            (d / f).write_text(src.replace(old, new, 1), encoding="utf-8")
            p = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests"], cwd=d, env=env,
                               capture_output=True, text=True, timeout=300)
            last = [l for l in p.stderr.splitlines() if l.startswith(("OK", "FAILED"))]
            res[name] = last[-1] if last else f"ERROR rc={p.returncode}"
    ok = res["CONTROL"].startswith("OK") and all(v.startswith("FAILED") for k, v in res.items() if k != "CONTROL")
    out = HERE / "outputs" / f"fault_injection_{datetime.now():%Y%m%d_%H%M}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "fault_injection.json").write_text(json.dumps({"results": res, "all_detected_with_control_ok": ok}, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1), "\nALL_DETECTED", ok)


if __name__ == "__main__":
    main()
