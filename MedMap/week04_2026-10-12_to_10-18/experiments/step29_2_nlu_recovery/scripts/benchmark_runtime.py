"""STEP29.2 CPU 지연·메모리 — 단일 입력, 모든 메모(P5·v3 core·B4 특징) 끔, pilot_gold 274(STEP29.1 과 같은 입력) + HOLDOUT 마침표 없는 BASE 입력.
warm-up 20. 출력: outputs/latency.json(정책별 p50·p95·max, 최대 RSS)."""
import os
import json
import time

import s292_common as S
import b4_evidence_guard as B4G
import p5_normalizer_adapter as A
import nlu_pipeline_v3 as N


def rss():
    for ln in open("/proc/self/status"):
        if ln.startswith("VmHWM"):
            return round(int(ln.split()[1]) / 1024, 1)


def main():
    A.USE_CACHE = False
    N.USE_CACHE = False
    B4G.USE_CACHE = False
    A.engine()
    pf = S.load_json(S.DATA / "policy_freeze.json")
    sel = pf["SELECTED_POLICY"]
    texts = [r["text_ko"] for r in S.read_csv(S.S21_DIR / "data/pilot_gold.csv")]
    hold = [c["text"] for c in json.loads((S.DATA / "frozen_holdout_pairs.json").read_text(encoding="utf-8"))["cases"] if c["punct"] == "N" and c["variant"] == "BASE"]
    for t in texts[:20]:
        N.analyze(t, sel)
    res = {}
    for name, ts in (("pilot274", texts), ("holdout_no_period", hold)):
        for P in ("S29", "S291", sel):
            ms = []
            for t in ts:
                a = time.perf_counter()
                N.analyze(t, P)
                ms.append((time.perf_counter() - a) * 1000)
            ms.sort()
            q = lambda x: round(ms[int(round(x * (len(ms) - 1)))], 3)  # noqa: E731
            res.setdefault(name, {})[P] = {"n": len(ms), "p50_ms": q(0.5), "p95_ms": q(0.95), "max_ms": round(ms[-1], 3)}
    out = {"single_input_cpu": res["pilot274"], "by_input_set": res, "selected_policy": sel, "peak_rss_mib": rss(),
           "omp_num_threads": os.environ.get("OMP_NUM_THREADS"), "gpu": "사용 안 함", "note": "판정 R8 = pilot274 단일 입력 p95(STEP29.1 과 같은 입력)"}
    S.dump_json(S.OUT / "latency.json", out)
    print(S.dumps(out))


if __name__ == "__main__":
    main()
