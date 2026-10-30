"""G11 보호 확인(snapshot / compare). 제품·연구 원본·서버가 이번 실험 전후로 같은지.
 제품 = ~/medmap HEAD · git status(.claude/ 제외 — 인수인계 문서는 다른 세션이 갱신) · medmap/ 코드·medmap-web/src·dist·evidence JSON·k3/k5/k10 모델 pkl SHA
 연구 원본 = exp/step2*(이 단계 제외)의 모든 파일(logs/·__pycache__ 제외) · 서버 = 8010·8020·5190 LISTEN PID(상태만, 종료·재시작 없음)
출력: logs/protected_baseline.json(최초 1회) · outputs/protected_check.json"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import s30_common as S

P = S.PRODUCT
PORTS = ("8010", "8020", "5190")


def files(root: Path, pattern: str = "*", skip_logs: bool = True) -> dict:
    out = {}
    for f in sorted(root.rglob(pattern)):
        if not f.is_file() or "__pycache__" in f.parts or "node_modules" in f.parts:
            continue
        if skip_logs and "logs" in f.relative_to(root).parts:
            continue
        out[str(f)] = S.sha256(f)
    return out


def servers() -> dict:
    r = subprocess.run(["ss", "-ltnp"], capture_output=True, text=True).stdout
    out = {}
    for line in r.splitlines():
        for p in PORTS:
            if re.search(rf":{p}\s", line):
                m = re.search(r"pid=(\d+)", line)
                out[p] = m.group(1) if m else "UNKNOWN"
    return out


def snapshot() -> dict:
    g = lambda *a: subprocess.run(["git", "-C", str(P), *a], capture_output=True, text=True).stdout.strip()  # noqa: E731
    status = "\n".join(line for line in g("status", "--porcelain").splitlines() if ".claude/" not in line)
    from importlib import util  # noqa: F401
    prod = {}
    prod.update(files(P / "medmap", "*.py"))
    prod.update(files(P / "medmap", "*.json"))
    prod.update(files(P / "medmap-web/src"))
    prod.update(files(P / "medmap-web/dist"))
    prod[str(P / "data/ddxplus/en/release_evidences.json")] = S.sha256(P / "data/ddxplus/en/release_evidences.json")
    for k in ("k3", "k5", "k10"):
        f = P / f"exp/step16b_next_information_validation/model_{k}.pkl"
        prod[str(f)] = S.sha256(f)
    research = {}
    for d in sorted((S.REPO / "exp").iterdir()):
        if d.is_dir() and d.name.startswith("step2") and d.name != S.STEP.name:
            research.update(files(d))
    return {"product_head": g("rev-parse", "HEAD"), "product_branch": g("rev-parse", "--abbrev-ref", "HEAD"), "product_status_non_claude": status,
            "product_files": prod, "research_files": research, "servers": servers()}


def main():
    B = S.LOGS / "protected_baseline.json"
    if sys.argv[1] == "snapshot":
        if not B.exists():
            S.dump_json(B, snapshot())
        b = S.load_json(B)
        print("baseline product", len(b["product_files"]), "research", len(b["research_files"]), b["product_head"][:7], b["servers"])
        return
    b, a = S.load_json(B), snapshot()
    pc = sorted(k for k in set(b["product_files"]) | set(a["product_files"]) if a["product_files"].get(k) != b["product_files"].get(k))
    rc = sorted(k for k in set(b["research_files"]) | set(a["research_files"]) if a["research_files"].get(k) != b["research_files"].get(k))
    res = {"G11": "PASS" if not pc and not rc and a["product_head"] == b["product_head"] and a["product_status_non_claude"] == b["product_status_non_claude"]
           and a["servers"] == b["servers"] else "FAIL",
           "product_head_before": b["product_head"], "product_head_after": a["product_head"], "product_branch": a["product_branch"],
           "product_status_same": a["product_status_non_claude"] == b["product_status_non_claude"],
           "product_files_checked": len(b["product_files"]), "product_files_changed": pc[:30],
           "research_files_checked": len(b["research_files"]), "research_files_changed": rc[:30],
           "servers_before": b["servers"], "servers_after": a["servers"]}
    S.dump_json(S.OUT / "protected_check.json", res)
    print(S.dumps({k: res[k] for k in ("G11", "product_files_checked", "research_files_checked", "servers_after")}))


if __name__ == "__main__":
    main()
