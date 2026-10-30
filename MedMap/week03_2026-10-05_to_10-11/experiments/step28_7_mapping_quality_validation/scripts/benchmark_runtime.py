"""STEP28.7 §12 14·15 — CPU 지연·메모리(단일 입력, warm, OMP_NUM_THREADS 고정). LLM·네트워크 없음.

대상: D(STEP28.7) · D_NO_TABLE(= STEP28.5 KO_ONLY) · C(STEP28.6 대응표 조회) — SILVER442 입력 순서대로, 앞 20 개 warm-up 제외 없이 전부 측정
(warm-up 20 회 별도). p50/p95 = 정렬 후 int(round(q·(n−1))) 위치(STEP28.6 와 같은 정의). RSS = /proc/self/status VmRSS·VmHWM.
출력: outputs/latency.json
"""
from __future__ import annotations

import os
import time

import s287_common as S
from safe_offline_retriever import PolicyC, SafeOfflineRetriever


def rss():
    d = {}
    for ln in open("/proc/self/status"):
        if ln.startswith(("VmRSS", "VmHWM")):
            d[ln.split(":")[0]] = round(int(ln.split()[1]) / 1024, 1)
    return d


def pct(ms):
    ms = sorted(ms)
    return {"n": len(ms), "p50_ms": round(ms[int(round(0.5 * (len(ms) - 1)))], 3), "p95_ms": round(ms[int(round(0.95 * (len(ms) - 1)))], 3),
            "max_ms": round(ms[-1], 3), "mean_ms": round(sum(ms) / len(ms), 3)}


def main():
    r0 = rss()
    t0 = time.perf_counter()
    D = SafeOfflineRetriever()
    load_s = time.perf_counter() - t0
    r1 = rss()
    C = PolicyC()
    sil = [r["raw_expression"] for r in S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv")]
    for t in sil[:20]:
        D.run(t)
    res = {}
    for name, fn in (("D_STEP28_7", D.run), ("C_STEP28_6_lookup", C.run)):
        ms = []
        for t in sil:
            a = time.perf_counter()
            fn(t)
            ms.append((time.perf_counter() - a) * 1000)
        res[name] = pct(ms)
    tab = D.table
    D.table = None
    ms = []
    for t in sil:
        a = time.perf_counter()
        D.run(t)
        ms.append((time.perf_counter() - a) * 1000)
    res["D_NO_TABLE(STEP28.5 KO_ONLY)"] = pct(ms)
    D.table = tab
    out = {"single_input_cpu": res, "pipeline_load_seconds": round(load_s, 2), "rss_before_mib": r0.get("VmRSS"), "rss_after_load_mib": r1.get("VmRSS"),
           "peak_rss_mib": rss().get("VmHWM"), "omp_num_threads": os.environ.get("OMP_NUM_THREADS"), "gpu": "사용 안 함(CPU)",
           "cleaned_table_bytes": (S.DATA / "cleaned_silver_mappings.csv").stat().st_size, "ontology_index_bytes": S.ONT_DB.stat().st_size,
           "note": "D 의 대부분 시간은 STEP28.5 KO 경로(STEP27 Linear+KoELECTRA 특징 포함). 대응표 조회는 dict 완전일치. 다른 세션 부하에 따라 변동."}
    S.dump_json(S.OUT / "latency.json", out)
    print(S.dumps(out))


if __name__ == "__main__":
    main()
