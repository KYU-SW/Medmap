"""STEP26 latency·메모리(CPU, single message). 입력 = EXT_EVAL 앞 300 단위 + INT_REGRESSION_CORE 109 문장(순서 고정), warm-up 20.
경로: LINEAR_ONLY(Linear 만) · HYBRID_B(Linear + 필요 시 KoE) · SAFE_NORMALIZER(BEST_POLICY + 상태 분류 전체).
peak memory = 프로세스 ru_maxrss(MiB). KoE 호출률 = 실제 KoE forward 를 부른 비율.
출력: outputs/latency.json
"""
import resource
import statistics
import time

import numpy as np

import s26_common as S
from safe_normalizer import SafeNormalizer


def stats(xs):
    xs = sorted(xs)
    return {"n": len(xs), "mean_ms": round(statistics.mean(xs), 3), "p50_ms": round(xs[len(xs) // 2], 3),
            "p95_ms": round(xs[int(round(0.95 * (len(xs) - 1)))], 3), "max_ms": round(xs[-1], 3)}


def main():
    sn = SafeNormalizer()
    fin = S.read_csv(S.OUT / "final_decisions.csv")
    texts = [f["text"] for f in fin if f["set"] == "EXT_EVAL"][:300] + [f["text"] for f in fin if f["set"] == "INT_REGRESSION_CORE"]

    def lin_only(t):
        s = sn.lin.decision_function([S.norm(t)])[0]
        return s.argmax()

    def koe(t):
        b = sn.tok([S.norm(t)], truncation=True, max_length=sn.max_len, return_tensors="pt")
        return int(sn.koe(**b).logits.argmax(-1).item())

    calls = {"HYBRID_B": 0}

    def hyb(t):
        s = np.sort(sn.lin.decision_function([S.norm(t)])[0])
        if s[-1] - s[-2] >= S.T_LIN:
            return None
        calls["HYBRID_B"] += 1
        return koe(t)

    res = {}
    for name, f in (("LINEAR_ONLY", lin_only), ("HYBRID_B", hyb), ("SAFE_NORMALIZER_" + sn.policy, sn)):
        for t in texts[:20]:
            f(t)
        calls["HYBRID_B"] = 0
        ms = []
        for t in texts:
            t0 = time.perf_counter()
            f(t)
            ms.append((time.perf_counter() - t0) * 1000)
        res[name] = stats(ms)
        if name == "HYBRID_B":
            hyb_rate = calls["HYBRID_B"] / len(texts)
    pred = {}
    for f in S.read_csv(S.OUT / "predictions.csv"):
        pred.setdefault(f["text"], f["status"])
    mism = sum(sn(t)["status"] != pred[t] for t in texts)
    assert mism == 0, f"SafeNormalizer 와 predictions.csv 상태 불일치 {mism}"
    koe_rate_safe = sum(not S.complex_flags(t) for t in texts) / len(texts)
    out = {"single_message_cpu": res, "n_inputs": len(texts), "koe_call_rate": {"HYBRID_B": S.rnd(hyb_rate),
                                                                                "SAFE_NORMALIZER": S.rnd(koe_rate_safe), "LINEAR_ONLY": 0.0},
           "peak_rss_mib": round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1),
           "status_consistency_with_predictions_csv": "PASS(0 mismatch)", "note": "SAFE_NORMALIZER 는 COMPLEX 가 아니면 항상 KoE 실행(B2–B4 는 동의 판정 필요) + 학습 표현 1,119개와 difflib 유사도 계산 포함"}
    S.dump_json(S.OUT / "latency.json", out)
    print(out)


if __name__ == "__main__":
    main()
