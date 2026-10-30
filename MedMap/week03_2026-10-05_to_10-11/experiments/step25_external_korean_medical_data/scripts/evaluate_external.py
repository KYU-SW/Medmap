"""STEP25 외부 데이터 고정 모델 분석(정답 없음 → 정확도 계산 금지).

고정 모델(재학습·재튜닝 없음): LINEAR_CHAR(STEP23 EXPANDED) · KOELECTRA_SMALL(STEP24-v2 seed42, CPU 추론) ·
HYBRID_B(Linear margin ≥ T_lin → Linear, 아니면 KoELECTRA; auto = fast path 또는 KoE confidence ≥ T_koe) · HYBRID_C(참고, α·T_fus).
임계값·α = STEP24-v2 seed42 hybrid_config(dev 결정값). 실행 시 먼저 outputs/frozen_eval_config.json 에 모델 SHA·임계값을 기록한다.

분석 집합(eligible_for_unlabeled_analysis = 학습·gold 와 exact 겹침 제외):
 A NERKO_ST   : 외부 annotator 가 '증상(ST)'으로 표시한 고유 span — 증상 표현이지만 concept 미지정
 B NERKO_DS   : 외부 annotator 가 '질병(DS)'으로 표시한 고유 span — 위험 자동 수락 후보 탐지용(증상 concept 으로 자동 수락되면 위험 후보)
 C KBMC_DIS   : KBMC Disease 고유 span(질병·증상 혼재)
 D KMC_TURN   : ko_medical_chat 첫 client 발화(생성문, 복수 증상·부정 포함 가능) — normalizer 입력 단위가 아님(참고)
 SILVER       : 학습 표현과 완전일치 span — 규칙 concept 과의 일치율(정확도 아님)
지표: 모델 간 agreement, 예측 분포(pilot 20 비율·상위 class), 미인식률(= auto-accept 안 됨), auto-accept 비율, 위험 자동 수락 후보 수, latency.
출력: outputs/frozen_eval_config.json · outputs/model_comparison.csv · outputs/external_predictions.csv · outputs/error_analysis.csv · outputs/latency_external.json
"""
import collections
import statistics
import time

import numpy as np
import torch

import s25_common as S

MODELS = ["LINEAR_CHAR", "KOELECTRA_SMALL", "HYBRID_B", "HYBRID_C"]


def zs(a):
    return (a - a.mean(1, keepdims=True)) / (a.std(1, keepdims=True) + 1e-9)


def main():
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    hc = S.load_json(S.V2 / "outputs/seeds/seed42/hybrid_config.json")
    T_lin, T_koe, alpha, T_fus = hc["T_lin_margin(STEP23 dev)"], hc["T_koe_conf(dev)"], hc["alpha(dev)"], hc["T_fusion_margin(dev)"]
    ft = S.V2 / "models/koelectra_small_seed42"
    lin, sel23 = S.S24.linear_model()
    lin_file = S.S24.S23 / sel23["conditions"]["EXPANDED"]["families"]["LINEAR_CHAR"]["model_file"]
    max_len = S.load_json(S.S24.ENV_JSON)["selected_max_length"]
    S.dump_json(S.OUT / "frozen_eval_config.json", {
        "linear_model": str(lin_file.relative_to(S.REPO)), "linear_sha256": S.sha256(lin_file),
        "koelectra_dir": str(ft.relative_to(S.REPO)), "koelectra_safetensors_sha256": S.sha256(ft / "model.safetensors"),
        "T_lin": T_lin, "T_koe": T_koe, "alpha": alpha, "T_fus": T_fus, "max_length": max_len, "koelectra_device": "cpu",
        "no_training_no_tuning": True, "source": "STEP24-v2 seed42 hybrid_config (dev 결정값)"})

    units = [u for u in S.read_csv(S.DATA / "eligible_external_examples.csv")]
    nk = S.load_bert_ner_ko()
    ds_spans = {}
    for r in nk:
        for t, x in r["spans"]:
            if t == "DS":
                ds_spans.setdefault(S.nospace(x), x)
    train_ns = {S.nospace(r["expression"]) for r in S.read_csv(S.S24.S23 / "data/expanded_train_expressions.csv")}
    sets = {"A_NERKO_ST": [u for u in units if u["dataset"] == "BERT_NER_KO" and u["eligible_for_unlabeled_analysis"] == "True"],
            "B_NERKO_DS": [{"unit_id": f"DS{i:04d}", "dataset": "BERT_NER_KO", "unit_type": "DS_span", "text": x, "negation_cue_in_text": "False"}
                           for i, (k, x) in enumerate(sorted(ds_spans.items())) if k not in train_ns],
            "C_KBMC_DISEASE": [u for u in units if u["dataset"] == "KBMC" and u["eligible_for_unlabeled_analysis"] == "True"],
            "D_KMC_FIRST_TURN": [u for u in units if u["dataset"] == "KO_MEDICAL_CHAT" and u["eligible_for_unlabeled_analysis"] == "True"],
            "SILVER_TRAIN_EXACT": [u for u in units if u["tier"] == "SILVER"]}

    tok = AutoTokenizer.from_pretrained(ft)
    koe = AutoModelForSequenceClassification.from_pretrained(ft).to("cpu").eval()
    cls = list(lin.classes_)
    lm = S.load_json(S.V2 / "data/label_map.json")
    assert cls == sorted(lm, key=lm.get)
    torch.set_grad_enabled(False)

    def koe_logits(texts, bs=128):
        out = []
        for i in range(0, len(texts), bs):
            b = tok(texts[i:i + bs], padding=True, truncation=True, max_length=max_len, return_tensors="pt")
            out.append(koe(**b).logits.float().numpy())
        return np.concatenate(out)

    rows, preds, errs = [], [], []
    for sn, us in sets.items():
        texts = [S.norm(u["text"]) for u in us]
        L = np.atleast_2d(lin.decision_function(texts))
        T = koe_logits(texts)
        P = np.exp(T - T.max(1, keepdims=True))
        P /= P.sum(1, keepdims=True)
        F = alpha * zs(T) + (1 - alpha) * zs(L)
        res = {m: [] for m in MODELS}
        for i, u in enumerate(us):
            ls, fs = np.sort(L[i]), np.sort(F[i])
            lmar, kconf, fmar = float(ls[-1] - ls[-2]), float(P[i].max()), float(fs[-1] - fs[-2])
            l1, k1, f1 = cls[int(L[i].argmax())], cls[int(P[i].argmax())], cls[int(F[i].argmax())]
            fast = lmar >= T_lin
            b1, bauto = (l1, True) if fast else (k1, kconf >= T_koe)
            out = {"LINEAR_CHAR": (l1, fast), "KOELECTRA_SMALL": (k1, kconf >= T_koe), "HYBRID_B": (b1, bauto),
                   "HYBRID_C": (f1, T_fus is not None and fmar >= T_fus)}
            for m in MODELS:
                res[m].append(out[m])
            rec = {"set": sn, "unit_id": u["unit_id"], "dataset": u["dataset"], "text": u["text"], "linear_top1": l1, "linear_margin": round(lmar, 5),
                   "koe_top1": k1, "koe_conf": round(kconf, 5), "hybrid_b_top1": b1, "hybrid_b_auto": bauto, "hybrid_b_called_koe": not fast,
                   "hybrid_c_top1": f1, "silver_rule_concept": u.get("silver_rule_concept", "")}
            preds.append(rec)
            cats = []
            if l1 != k1:
                cats.append("MODEL_DISAGREEMENT")
            if bauto and l1 != k1:
                cats.append("AUTO_ACCEPT_DESPITE_DISAGREEMENT")
            if bauto and sn == "B_NERKO_DS":
                cats.append("AUTO_ACCEPT_ON_EXTERNAL_DISEASE_SPAN")
            if bauto and u.get("negation_cue_in_text") == "True":
                cats.append("AUTO_ACCEPT_WITH_NEGATION_CUE")
            if cats and sn != "SILVER_TRAIN_EXACT":
                errs.append({**rec, "categories": ";".join(cats)})
        n = len(us)
        for m in MODELS:
            top = [t for t, _ in res[m]]
            auto = [a for _, a in res[m]]
            dist = collections.Counter(top)
            row = {"set": sn, "model": m, "n": n, "auto_accept_rate": S.rnd(sum(auto) / n) if n else None,
                   "unknown_rate(not_auto)": S.rnd(1 - sum(auto) / n) if n else None,
                   "pred_pilot20_share": S.rnd(sum(t in S.TARGET20 for t in top) / n) if n else None,
                   "pred_distinct_classes": len(dist), "pred_top5": ";".join(f"{c}:{v}" for c, v in dist.most_common(5)),
                   "agree_with_linear": S.rnd(sum(a == b for a, b in zip(top, [t for t, _ in res["LINEAR_CHAR"]])) / n) if n else None,
                   "agree_with_koelectra": S.rnd(sum(a == b for a, b in zip(top, [t for t, _ in res["KOELECTRA_SMALL"]])) / n) if n else None}
            if sn == "SILVER_TRAIN_EXACT":
                row["agree_with_rule_label(NOT_accuracy)"] = S.rnd(sum(t == u["silver_rule_concept"] for t, u in zip(top, us)) / n) if n else None
            if m == "HYBRID_B":
                row["koe_call_rate"] = S.rnd(sum(p["hybrid_b_called_koe"] for p in preds if p["set"] == sn) / n) if n else None
                row["auto_accept_despite_disagreement"] = sum(1 for p in preds if p["set"] == sn and p["hybrid_b_auto"] and p["linear_top1"] != p["koe_top1"])
            rows.append(row)
        print(sn, n, {m: next(r for r in rows if r["set"] == sn and r["model"] == m)["auto_accept_rate"] for m in MODELS},
              "L-K agree", next(r for r in rows if r["set"] == sn and r["model"] == "KOELECTRA_SMALL")["agree_with_linear"], flush=True)
    S.write_csv(S.OUT / "model_comparison.csv", rows, ["set", "model", "n", "auto_accept_rate", "unknown_rate(not_auto)", "pred_pilot20_share",
                                                          "pred_distinct_classes", "pred_top5", "agree_with_linear", "agree_with_koelectra",
                                                          "agree_with_rule_label(NOT_accuracy)", "koe_call_rate", "auto_accept_despite_disagreement"])
    S.write_csv(S.OUT / "external_predictions.csv", preds)
    S.write_csv(S.OUT / "error_analysis.csv", errs)

    # latency: A 집합 span 1개씩(warm-up 20 후 전부 1회), CPU
    xs = [S.norm(u["text"]) for u in sets["A_NERKO_ST"]]
    lat = {}

    def lin1(t):
        s = lin.decision_function([t])[0]
        o = np.sort(s)
        return float(o[-1] - o[-2])

    def koe1(t):
        b = tok([t], truncation=True, max_length=max_len, return_tensors="pt")
        return int(koe(**b).logits.argmax(-1).item())

    def hyb1(t):
        return None if lin1(t) >= T_lin else koe1(t)

    for name, f in (("LINEAR_CHAR_CPU", lin1), ("KOELECTRA_CPU", koe1), ("HYBRID_B_CPU", hyb1)):
        for t in xs[:20]:
            f(t)
        ms = []
        for t in xs:
            t0 = time.perf_counter()
            f(t)
            ms.append((time.perf_counter() - t0) * 1000)
        ms.sort()
        lat[name] = {"n": len(ms), "mean_ms": round(statistics.mean(ms), 3), "p50_ms": round(ms[len(ms) // 2], 3),
                     "p95_ms": round(ms[int(0.95 * (len(ms) - 1))], 3)}
    S.dump_json(S.OUT / "latency_external.json", {"input": "A_NERKO_ST spans, single message, CPU", "torch_threads": torch.get_num_threads(), **lat})
    print(lat)


if __name__ == "__main__":
    main()
