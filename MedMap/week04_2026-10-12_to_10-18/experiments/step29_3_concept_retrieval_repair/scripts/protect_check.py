"""STEP29.3 G7 — 보호 확인(snapshot / compare). 이번 실험 시작 시점 baseline 을 새로 기록하고, 연구 원본과 제품 상태를 따로 판정한다.
 연구 원본 = exp/step20–step29_2 의 모든 파일(logs/·__pycache__ 제외) + ~/medmap_step28_6_ws/out
 제품 = ~/medmap HEAD · git status --porcelain · medmap-web/dist(8010 서빙) 파일 SHA. 과거(STEP29.2 이후 디자인 병합)로 생긴 차이는 baseline 에 이미 포함.
출력: logs/protected_baseline.json(최초 1회) · outputs/protected_check.json"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import s293_common as S

WS = S.S292.S291.S29.S288.S287.WS
MAIN = Path.home() / "medmap"
DIRS = sorted(p for p in (S.REPO / "exp").iterdir() if p.is_dir() and p.name.startswith("step2") and p.name != S.STEP.name)


def files(dirs):
    out = {}
    for d in dirs:
        for f in sorted(d.rglob("*")):
            if f.is_file() and "__pycache__" not in f.parts and "logs" not in f.relative_to(d).parts:
                out[str(f)] = S.sha256(f)
    return out


def snapshot() -> dict:
    g = lambda *a: subprocess.run(["git", "-C", str(MAIN), *a], capture_output=True, text=True).stdout.strip()  # noqa: E731
    return {"research": files(DIRS + [WS / "out"]), "product_head": g("rev-parse", "HEAD"), "product_status": g("status", "--porcelain"),
            "product_dist": files([MAIN / "medmap-web/dist"])}


def main():
    B = S.LOGS / "protected_baseline.json"
    if sys.argv[1] == "snapshot":
        if not B.exists():
            S.dump_json(B, snapshot())
        b = S.load_json(B)
        print("baseline research", len(b["research"]), "dist", len(b["product_dist"]), b["product_head"][:7])
        return
    b, a = S.load_json(B), snapshot()
    rc = sorted(k for k in b["research"] if a["research"].get(k) != b["research"][k])
    ra = sorted(set(a["research"]) - set(b["research"]))
    pd = sorted(k for k in set(b["product_dist"]) | set(a["product_dist"]) if a["product_dist"].get(k) != b["product_dist"].get(k))
    prod_ok = a["product_head"] == b["product_head"] and a["product_status"] == b["product_status"] and not pd
    res = {"G7": "PASS" if not rc and not ra and prod_ok else "FAIL", "research_ok": not rc and not ra, "product_ok": prod_ok,
           "research_files": len(b["research"]), "research_changed": rc[:50], "research_added": ra[:50],
           "product_head_before": b["product_head"], "product_head_after": a["product_head"], "product_status_same": a["product_status"] == b["product_status"],
           "product_dist_changed": pd[:20]}
    S.dump_json(S.OUT / "protected_check.json", res)
    print(S.dumps({k: res[k] for k in ("G7", "research_ok", "product_ok", "research_files")}))


if __name__ == "__main__":
    main()
