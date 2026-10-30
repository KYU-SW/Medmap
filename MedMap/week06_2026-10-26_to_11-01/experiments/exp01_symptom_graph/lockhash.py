"""실행 잠금 해시(manifest rev5 test_population (e) + gate4 설계 MINOR: medmap/__init__.py 포함, porcelain 은 경로 한정)."""
from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

MEDMAP = Path("/home/<user>/medmap")
EXTERNAL = [MEDMAP / "medmap" / f for f in ("__init__.py", "config.py", "diagnosis.py", "next_information.py",
                                              "evidence.py", "eligibility.py", "patient_state.py")] + \
           [MEDMAP / "exp/step16b_next_information_validation/s16b_core.py"]
MODELS = [MEDMAP / "exp/step16b_next_information_validation" / f for f in
          ("ig_table_step16b_train.npz", "model_k3.pkl", "model_k5.pkl", "model_k10.pkl")]


def sha_file(p) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def external_clean() -> bool:
    """외부 코드 경로만 한정해 미커밋 변경이 없는지(저장소 전체가 아님)."""
    rel = [str(p.relative_to(MEDMAP)) for p in EXTERNAL]
    out = subprocess.run(["git", "-C", str(MEDMAP), "status", "--porcelain", "--", *rel],
                         capture_output=True, text=True, check=True).stdout
    return out.strip() == ""


def run_lock_hash(config_path, code_dir) -> dict:
    """code_dir = exp/main_ai (manifest test_population (e) 'exp/main_ai/**/*.py' — 독립 감사 MINOR 로 범위 일치)."""
    code = sorted(Path(code_dir).rglob("*.py"))
    parts = {"config": sha_file(config_path),
             "code": [(str(p.relative_to(code_dir)), sha_file(p)) for p in code if "__pycache__" not in p.parts],
             "external": [(str(p), sha_file(p)) for p in EXTERNAL],
             "models": [(p.name, sha_file(p)) for p in MODELS],
             "medmap_head": subprocess.run(["git", "-C", str(MEDMAP), "rev-parse", "HEAD"], capture_output=True,
                                           text=True, check=True).stdout.strip()}
    blob = repr(parts).encode()
    return {"lock_sha256": hashlib.sha256(blob).hexdigest(), "parts": parts, "external_clean": external_clean()}
