"""STEP24 latency·VRAM 실측(single-message 우선, batch 별도). GPU 경합이 없을 때(wait_for_resources 래퍼) 실행한다.

- 입력 = core test 109 문장을 순서대로 반복(문장 1개 = 호출 1회), warm-up 20회 후 측정 N=327(109×3)
- 측정 구간 = 원문 → norm → 모델 → top1 (STT 제외). time.perf_counter, GPU 는 매 호출 torch.cuda.synchronize()
- 경로: LINEAR_CHAR(CPU) · KOELECTRA_GPU · KOELECTRA_CPU(참고, 같은 모델을 cpu 장치로) · HYBRID_A/HYBRID_C(둘 다 실행, GPU)
        · HYBRID_B(Linear 먼저, margin < T_lin 일 때만 KoELECTRA GPU)
- batch: KoELECTRA GPU batch=109 1회 처리 시간(문장당 환산) 참고
- VRAM: 추론 peak(torch.cuda.max_memory_allocated/reserved) + nvidia-smi 프로세스 사용량
출력: outputs/latency.json
"""
import json
import statistics
import subprocess
import time

import numpy as np
import torch

import s24_common as S

N_WARM, REPS = 20, 3


def stats(xs):
    xs = sorted(xs)
    q = lambda p: xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]  # noqa: E731
    return {"n": len(xs), "mean_ms": round(statistics.mean(xs), 3), "median_ms": round(statistics.median(xs), 3),
            "p50_ms": round(q(0.50), 3), "p95_ms": round(q(0.95), 3), "max_ms": round(xs[-1], 3)}


def main():
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    env = S.load_json(S.ENV_JSON)
    cfg = S.load_json(S.RUN_OUT / "hybrid_config.json")
    max_len = env["selected_max_length"]
    _, _, core_test = S.eval_sets()
    raw = [g["text_ko"] for g in core_test]
    lin, _ = S.linear_model()
    T_lin = cfg["T_lin_margin(STEP23 dev)"]
    tok = AutoTokenizer.from_pretrained(S.FT_DIR)
    gpu = torch.device("cuda")
    torch.cuda.reset_peak_memory_stats()
    mg = AutoModelForSequenceClassification.from_pretrained(S.FT_DIR).to(gpu).eval()
    mc = AutoModelForSequenceClassification.from_pretrained(S.FT_DIR).to("cpu").eval()
    torch.set_grad_enabled(False)

    def koe(m, dev, text):
        b = tok([S.norm(text)], truncation=True, max_length=max_len, return_tensors="pt")
        out = m(**{k: v.to(dev) for k, v in b.items()}).logits
        r = int(out.argmax(-1).item())                    # .item() 이 GPU 동기화 포함
        return r

    def linear(text):
        s = lin.decision_function([S.norm(text)])[0]
        o = np.sort(s)
        return int(s.argmax()), float(o[-1] - o[-2])

    def hybrid_b(text):
        c, m = linear(text)
        return c if m >= T_lin else koe(mg, gpu, text)

    def both(text):
        linear(text)
        return koe(mg, gpu, text)

    paths = {"LINEAR_CHAR_CPU": linear, "KOELECTRA_GPU": lambda t: koe(mg, gpu, t), "KOELECTRA_CPU": lambda t: koe(mc, "cpu", t),
             "HYBRID_B_fastpath": hybrid_b, "HYBRID_A_or_C_both_models": both}
    res = {}
    for name, f in paths.items():
        for t in (raw * 2)[:N_WARM]:
            f(t)
        if name.endswith("GPU") or name.startswith("HYBRID"):
            torch.cuda.synchronize()
        xs = []
        for t in raw * REPS:
            t0 = time.perf_counter()
            f(t)
            if name != "LINEAR_CHAR_CPU" and name != "KOELECTRA_CPU":
                torch.cuda.synchronize()
            xs.append((time.perf_counter() - t0) * 1000)
        res[name] = stats(xs)
        print(name, res[name], flush=True)

    b = tok([S.norm(t) for t in raw], padding=True, truncation=True, max_length=max_len, return_tensors="pt")
    bt = []
    for i in range(12):
        torch.cuda.synchronize()
        t0 = time.perf_counter()
        mg(**{k: v.to(gpu) for k, v in b.items()}).logits.argmax(-1).cpu()
        torch.cuda.synchronize()
        if i >= 2:
            bt.append((time.perf_counter() - t0) * 1000)
    smi = subprocess.run(["nvidia-smi", "--query-compute-apps=pid,used_memory", "--format=csv,noheader"], capture_output=True, text=True).stdout
    out = {"single_message": res,
           "batch_gpu_koelectra": {"batch_size": len(raw), "median_ms_per_batch": round(statistics.median(bt), 3),
                                   "median_ms_per_sentence": round(statistics.median(bt) / len(raw), 4)},
           "inference_peak_vram": {"alloc_mib": round(torch.cuda.max_memory_allocated() / 2 ** 20, 1),
                                   "reserved_mib": round(torch.cuda.max_memory_reserved() / 2 ** 20, 1), "nvidia_smi_compute_apps": smi.strip()},
           "torch_cpu_threads": torch.get_num_threads(), "note": "STT 제외, 원문→top1. 이 측정 시점 GPU 경합 여부는 wait 로그 참조",
           "T_lin": T_lin}
    S.dump_json(S.OUT / "latency.json", out)
    print(json.dumps(out, ensure_ascii=False)[:1500])


if __name__ == "__main__":
    main()
