"""STEP29 G7 — 기존 연구(exp/step20–28.8, P5 원본 포함)·격리 작업 폴더·제품 저장소 무변경 확인(STEP28.8 protect_check 복사본). snapshot / compare.

대상: exp/step20–step28_6 의 모든 파일(logs/·__pycache__ 제외) · ~/medmap_step28_6_ws/out · 제품 저장소 ~/medmap 의 HEAD·git status(읽기만).
출력: logs/protected_before.json · outputs/protected_check.json
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import s29_common as S
S.WS = S.S288.S287.WS

DIRS = sorted(p for p in (S.REPO / "exp").iterdir() if p.is_dir() and p.name.startswith("step2") and p.name != S.STEP.name)


def snapshot() -> dict:
    files = {}
    for d in DIRS + [S.WS / "out"]:
        for f in sorted(d.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and "logs" not in f.relative_to(d).parts:
                files[str(f)] = S.sha256(f)
    main = Path.home() / "medmap"
    head = subprocess.run(["git", "-C", str(main), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    st = subprocess.run(["git", "-C", str(main), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
    return {"n_files": len(files), "files": files, "product_head": head, "product_status": st}


def main():
    mode = sys.argv[1]
    before = S.LOGS / "protected_before.json"
    if mode == "snapshot":
        if not before.exists():
            S.dump_json(before, snapshot())
        print("snapshot", S.load_json(before)["n_files"])
        return
    b, a = S.load_json(before), snapshot()
    changed = sorted(k for k in b["files"] if a["files"].get(k) != b["files"][k])
    added = sorted(set(a["files"]) - set(b["files"]))
    res = {"G10": "PASS" if not changed and not added and a["product_head"] == b["product_head"] and a["product_status"] == b["product_status"] else "FAIL",
           "n_files": b["n_files"], "changed": changed[:50], "added": added[:50], "product_head_before": b["product_head"], "product_head_after": a["product_head"],
           "product_status_same": a["product_status"] == b["product_status"]}
    S.dump_json(S.OUT / "protected_check.json", res)
    print(S.dumps({k: res[k] for k in ("G10", "n_files", "product_status_same")}), len(changed), len(added))


if __name__ == "__main__":
    main()
