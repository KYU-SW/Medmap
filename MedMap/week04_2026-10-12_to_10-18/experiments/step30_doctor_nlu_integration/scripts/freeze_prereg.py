"""G15 사전 고정. `rules` = 사례·게이트·변환표 SHA(평가 전), `code` = 어댑터·자격·평가 코드 SHA(공식 평가 직전). 이미 있으면 덮어쓰지 않는다.
`verify` = 현재 파일이 고정 SHA 와 같은지 확인(다르면 종료 코드 1). 출력: data/prereg_freeze.json"""
from __future__ import annotations

import sys
import time

import s30_common as S

RULES = ("data/integration_contract_cases.json", "data/prereg_gates.json", "data/evidence_mapping_candidates.csv")
CODE = ("scripts/doctor_integration_adapter.py", "scripts/model_input_eligibility.py", "scripts/evaluate_integration.py",
        "scripts/clinician_confirmation_simulator.py", "scripts/blind_workflow_simulator.py", "scripts/validate_schema.py", "scripts/finalize_verdict.py")
F = S.DATA / "prereg_freeze.json"


def main():
    mode = sys.argv[1]
    cur = S.load_json(F) if F.exists() else {}
    if mode in ("rules", "code"):
        key = mode
        if key in cur:
            print("already frozen", key, cur[key]["frozen_at"])
            return
        cur[key] = {"frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "sha256": {p: S.sha256(S.STEP / p) for p in (RULES if key == "rules" else CODE)}}
        S.dump_json(F, cur)
        print("frozen", key, len(cur[key]["sha256"]))
        return
    bad = [p for k in ("rules", "code") if k in cur for p, h in cur[k]["sha256"].items() if S.sha256(S.STEP / p) != h]
    missing = [k for k in ("rules", "code") if k not in cur]
    print(S.dumps({"verify": "PASS" if not bad and not missing else "FAIL", "changed": bad, "missing": missing}))
    sys.exit(0 if not bad and not missing else 1)


if __name__ == "__main__":
    main()
