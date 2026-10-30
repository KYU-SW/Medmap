"""STEP24 KoELECTRA-small 평가(dev+FIXED_REGRESSION_TEST 1회). 선택·임계값은 koelectra_selection.json(dev)에서만 온다.
출력: outputs/transformer_logits.npz · outputs/predictions_transformer.csv · outputs/transformer_metrics.json
"""
import numpy as np
import torch

import s24_common as S
from train_koelectra_small import predict_logits


def main():
    from transformers import AutoModelForSequenceClassification, AutoTokenizer
    env = S.load_json(S.ENV_JSON)
    sel = S.load_json(S.RUN_OUT / "koelectra_selection.json")
    lm = S.load_json(S.DATA / "label_map.json")
    inv = sorted(lm, key=lm.get)
    gold, core_dev, core_test = S.eval_sets()
    dev = torch.device("cuda")
    tok = AutoTokenizer.from_pretrained(S.FT_DIR)
    model = AutoModelForSequenceClassification.from_pretrained(S.FT_DIR).to(dev)
    ids = [g["utterance_id"] for g in gold]
    lg = predict_logits(model, tok, [S.norm(g["text_ko"]) for g in gold], env["selected_max_length"], dev)
    np.savez(S.RUN_OUT / "transformer_logits.npz", ids=np.array(ids), logits=lg, classes=np.array(inv))
    prob = torch.softmax(torch.tensor(lg), -1).numpy()
    rk = {u: [inv[i] for i in np.argsort(-p, kind="stable")[:5]] for u, p in zip(ids, prob)}
    conf = {u: float(p.max()) for u, p in zip(ids, prob)}
    sim = S.test_similarity(core_test)
    low = [g for g in core_test if sim[g["utterance_id"]] < 0.5]
    th = sel["auto_accept_dev"]
    acc = [g for g in core_test if th and conf[g["utterance_id"]] >= th["conf_threshold"]]
    m = {"model": S.HF_REPO, "selection": sel,
         "core_test": {**S.score(core_test, rk), "macro_top1": S.macro_top1(core_test, rk)},
         "core_dev": S.score(core_dev, rk),
         "low_similarity_lt_0.5": {**S.score(low, rk), "n": len(low)},
         "unseen_step21_def": S.score([g for g in core_test if g["lexical_exposure"] == "novel"], rk),
         "auto_accept_dev_fixed": {"conf_threshold": th["conf_threshold"] if th else None, "n_accepted": len(acc),
                                   "coverage": S.rnd(len(acc) / len(core_test)),
                                   "precision": S.rnd(sum(rk[g["utterance_id"]][0] == g["primary_concept"] for g in acc) / len(acc)) if acc else None}}
    S.write_csv(S.RUN_OUT / "predictions_transformer.csv", [
        {"model": "KOELECTRA_SMALL", "utterance_id": g["utterance_id"], "split": g["split"], "is_core": str(S.is_core(g)),
         "gold_primary": g["primary_concept"], "top1": rk[g["utterance_id"]][0], "confidence_max_softmax": round(conf[g["utterance_id"]], 6),
         "ranked_top5": ";".join(rk[g["utterance_id"]]), "sim_max_generated": round(sim.get(g["utterance_id"], -1), 4) if g["utterance_id"] in sim else "",
         "top1_correct": str(rk[g["utterance_id"]][0] in S.c21.patient_concepts(g))} for g in gold])
    S.dump_json(S.RUN_OUT / "transformer_metrics.json", m)
    print({k: m[k] for k in ("core_test", "core_dev", "low_similarity_lt_0.5", "unseen_step21_def", "auto_accept_dev_fixed")})


if __name__ == "__main__":
    main()
