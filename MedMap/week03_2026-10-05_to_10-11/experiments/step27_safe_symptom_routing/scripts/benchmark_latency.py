"""STEP27 latency·메모리(CPU, single message, STEP26 과 같은 입력·방법). 입력 = EXT_EVAL 앞 300 단위 + INT_REGRESSION_CORE 109(순서 고정), warm-up 20.
경로: STEP26_SAFE_NORMALIZER_B4(= POLICY_A 경로) · STEP27_ROUTER_<BEST>(특징 + 라우팅 전체).
일관성: live 라우터 상태 == routing_decisions.csv BEST 상태(입력 409 전부, assert).
smoke: 지시문 §10 문장(데이터 밖, 지표·조정 미사용) → outputs/illustrative_smoke.json.
peak memory = ru_maxrss(MiB), 모델 적재 전후 RSS.
출력: outputs/latency.json · outputs/illustrative_smoke.json
"""
import resource
import statistics
import time

import s27_common as S
from safe_symptom_router import SafeSymptomRouter

SMOKE = ["고혈압", "결핵", "코피가 나요", "숨이 차요", "기침이 나요", "토했어요", "열이 나요"]


def rss_mib():
    for ln in open("/proc/self/status"):
        if ln.startswith("VmRSS:"):
            return round(int(ln.split()[1]) / 1024, 1)
    return None


def stats(xs):
    xs = sorted(xs)
    return {"n": len(xs), "mean_ms": round(statistics.mean(xs), 3), "p50_ms": round(xs[len(xs) // 2], 3),
            "p95_ms": round(xs[int(round(0.95 * (len(xs) - 1)))], 3), "max_ms": round(xs[-1], 3)}


def main():
    rss0 = rss_mib()
    router = SafeSymptomRouter()
    rss1 = rss_mib()
    dec = S.read_csv(S.OUT / "routing_decisions.csv")
    texts = [d["text"] for d in dec if d["set"] == "EXT_EVAL"][:300] + [d["text"] for d in dec if d["set"] == "INT_REGRESSION_CORE"]
    res = {}
    for name, fn in (("STEP26_SAFE_NORMALIZER_B4(POLICY_A)", router.sn), (f"STEP27_ROUTER_{router.policy}", router)):
        for t in texts[:20]:
            fn(t)
        ms = []
        for t in texts:
            t0 = time.perf_counter()
            fn(t)
            ms.append((time.perf_counter() - t0) * 1000)
        res[name] = stats(ms)
    ref = {}
    for d in dec:
        ref.setdefault(d["text"], d[f"{router.policy}_status"])
    mism = [t for t in texts if router(t)["status"] != ref[t]]
    assert not mism, f"live 라우터 ≠ routing_decisions ({len(mism)}): {mism[:3]}"
    smoke = {t: router(t) for t in SMOKE}
    S.dump_json(S.OUT / "illustrative_smoke.json", {"note": "데이터 밖 예시(지시문 §10). 지표·임계값 조정에 쓰지 않음. 탐색적.", "policy": router.policy,
                                                     "results": smoke})
    out = {"single_message_cpu": res, "n_inputs": len(texts), "rss_before_load_mib": rss0, "rss_after_load_mib": rss1,
           "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
           "status_consistency_with_routing_decisions": f"PASS(0 mismatch / {len(texts)})", "device": "cpu", "omp_num_threads": __import__("os").environ.get("OMP_NUM_THREADS"),
           "note": "STEP27 경로 = STEP26 경로(Linear+KoE+difflib 학습 유사도+비증상 점수) + 어휘 단서 정규식 + 후보 3개 bigram 유사도"}
    S.dump_json(S.OUT / "latency.json", out)
    print(S.dumps(out))
    for t, o in smoke.items():
        print(t, o["status"], o["decision"], o["candidate_ids"], o["reason_codes"])


if __name__ == "__main__":
    main()
