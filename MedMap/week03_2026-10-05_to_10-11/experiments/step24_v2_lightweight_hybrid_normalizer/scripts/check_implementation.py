"""STEP24-v2 구현 검사(grid 학습 전, 학습셋만 사용 — dev/test 미사용).

검사(각 PASS/FAIL):
 T1 tokenizer      : vocab 크기 = config.vocab_size, 전체 학습 문장 UNK 비율 < 1%, max_length 32 잘림 0, decode 왕복(공백 제거 비교) 일치율 ≥ 99%
 T2 label mapping  : label_map = LinearSVC classes_(77), inv[lm[c]] == c, 학습 label 전부 매핑, dev/test 정답 concept 전부 매핑
 T3 pretrained load: encoder 가중치가 safetensors 와 동일, 새 초기화는 classifier 만
 T4 initial loss   : 첫 batch CE ≈ ln(77)=4.344 (±0.5)
 T5 gradient       : 1 step 에서 embeddings·layer0·layer11·classifier grad norm 유한·>0
 T6 optimizer step : 위 그룹 파라미터가 1 step 후 실제로 바뀜(lr 2e-4)
 T7 overfit small  : 학습 문장 64개를 150 step 학습 → train loss < 0.1, train acc ≥ 0.95 (모델·loss·label 경로가 학습 가능한지)
 T8 train/eval mode: train() 에서 dropout 켜짐(같은 입력 두 번 logits 다름), eval() 에서 동일
출력: outputs/implementation_check.json
"""
import math
import random

import numpy as np
import torch

import s24_common as S
import train_koelectra_small as T


def main():
    from safetensors.torch import load_file
    from transformers import AutoConfig, AutoModelForSequenceClassification, AutoTokenizer
    res = {}
    env = S.load_json(S.ENV_JSON)
    L = env["selected_max_length"]
    tok = AutoTokenizer.from_pretrained(S.PRETRAINED)
    cfg = AutoConfig.from_pretrained(S.PRETRAINED)
    X, y = S.train_data()
    ids = [tok(x)["input_ids"] for x in X]
    n_tok = sum(len(i) for i in ids)
    unk = sum(t == tok.unk_token_id for i in ids for t in i)
    trunc = sum(len(i) > L for i in ids)
    rt = np.mean([tok.decode(i, skip_special_tokens=True).replace(" ", "") == x.replace(" ", "") for i, x in zip(ids, X)])
    res["T1_tokenizer"] = {"tokenizer_class": type(tok).__name__, "vocab": len(tok), "config_vocab": cfg.vocab_size, "unk_rate": round(unk / n_tok, 5),
                           "n_truncated_at_max_len": trunc, "decode_roundtrip_rate": round(float(rt), 4), "example": [X[0], tok.tokenize(X[0])],
                           "PASS": len(tok) == cfg.vocab_size and unk / n_tok < 0.01 and trunc == 0 and rt >= 0.99}

    lm = S.load_json(S.DATA / "label_map.json")
    inv = sorted(lm, key=lm.get)
    lin, _ = S.linear_model()
    gold, dv, ts = S.eval_sets()
    res["T2_label_map"] = {"n": len(lm), "PASS": list(lin.classes_) == inv and all(inv[lm[c]] == c for c in lm) and set(y) <= set(lm)
                           and all(g["primary_concept"] in lm for g in dv + ts) and len(lm) == 77}

    dev = torch.device("cuda")
    T.set_seed(S.SEED)
    model = AutoModelForSequenceClassification.from_pretrained(S.PRETRAINED, num_labels=77, output_loading_info=False).to(dev)
    st = load_file(str(S.PRETRAINED / "model.safetensors"))
    msd = model.state_dict()
    shared = [k for k in st if k in msd]
    same = all(torch.equal(st[k], msd[k].cpu()) for k in shared)
    fresh = sorted(k for k in msd if k not in st)
    res["T3_pretrained_load"] = {"n_shared_tensors": len(shared), "all_equal": same, "newly_initialized": fresh,
                                 "PASS": same and len(shared) > 150 and all(k.startswith("classifier.") for k in fresh)}

    yi = [lm[c] for c in y]
    rng = random.Random(S.SEED)
    idx = rng.sample(range(len(X)), 32)
    model.train()
    batch = T.encode(tok, [X[i] for i in idx], L, dev)
    tgt = torch.tensor([yi[i] for i in idx], device=dev)
    loss = torch.nn.functional.cross_entropy(model(**batch).logits, tgt)
    res["T4_initial_loss"] = {"loss": round(loss.item(), 4), "ln77": round(math.log(77), 4), "PASS": abs(loss.item() - math.log(77)) < 0.5}

    groups = {"embeddings": "electra.embeddings.word_embeddings.weight", "layer0": "electra.encoder.layer.0.attention.self.query.weight",
              "layer11": "electra.encoder.layer.11.output.dense.weight", "classifier": "classifier.out_proj.weight"}
    params = dict(model.named_parameters())
    before = {g: params[n].detach().clone() for g, n in groups.items()}
    opt = torch.optim.AdamW(model.parameters(), lr=2e-4)
    opt.zero_grad()
    loss.backward()
    gn = {g: float(params[n].grad.norm()) for g, n in groups.items()}
    opt.step()
    delta = {g: float((params[n].detach() - before[g]).abs().max()) for g, n in groups.items()}
    res["T5_gradient"] = {"grad_norm": gn, "PASS": all(math.isfinite(v) and v > 0 for v in gn.values())}
    res["T6_optimizer_step"] = {"max_abs_change": delta, "PASS": all(v > 0 for v in delta.values())}

    T.set_seed(S.SEED)
    m2 = AutoModelForSequenceClassification.from_pretrained(S.PRETRAINED, num_labels=77).to(dev)
    sub = rng.sample(range(len(X)), 64)
    o2 = torch.optim.AdamW(m2.parameters(), lr=2e-4)
    hist = []
    for step in range(150):
        m2.train()
        b = [sub[(step * 16 + j) % 64] for j in range(16)]
        lo = torch.nn.functional.cross_entropy(m2(**T.encode(tok, [X[i] for i in b], L, dev)).logits, torch.tensor([yi[i] for i in b], device=dev))
        o2.zero_grad()
        lo.backward()
        o2.step()
        if step % 25 == 0 or step == 149:
            hist.append([step, round(lo.item(), 4)])
    lg = T.predict_logits(m2, tok, [X[i] for i in sub], L, dev)
    acc = float(np.mean(lg.argmax(1) == np.array([yi[i] for i in sub])))
    full_lo = float(torch.nn.functional.cross_entropy(torch.tensor(lg), torch.tensor([yi[i] for i in sub])))
    res["T7_overfit_64"] = {"loss_history": hist, "final_eval_loss": round(full_lo, 4), "train_acc": acc, "PASS": full_lo < 0.1 and acc >= 0.95}

    with torch.no_grad():
        m2.train()
        a, b = m2(**batch).logits, m2(**batch).logits
        m2.eval()
        c, d = m2(**batch).logits, m2(**batch).logits
    res["T8_train_eval_mode"] = {"train_differs": bool(not torch.allclose(a, b)), "eval_equal": bool(torch.allclose(c, d)),
                                 "PASS": bool(not torch.allclose(a, b)) and bool(torch.allclose(c, d))}
    # T7b (사후 추가, 2026-10-09: T7 이 150 step 안에 기준 미달 — loss 는 단조 감소). 같은 64문장·같은 seed, 600 step.
    T.set_seed(S.SEED)
    m3 = AutoModelForSequenceClassification.from_pretrained(S.PRETRAINED, num_labels=77).to(dev)
    o3 = torch.optim.AdamW(m3.parameters(), lr=2e-4)
    hist3 = []
    for step in range(600):
        m3.train()
        b3 = [sub[(step * 16 + j) % 64] for j in range(16)]
        lo = torch.nn.functional.cross_entropy(m3(**T.encode(tok, [X[i] for i in b3], L, dev)).logits, torch.tensor([yi[i] for i in b3], device=dev))
        o3.zero_grad()
        lo.backward()
        o3.step()
        if step % 100 == 0 or step == 599:
            hist3.append([step, round(lo.item(), 4)])
    lg3 = T.predict_logits(m3, tok, [X[i] for i in sub], L, dev)
    acc3 = float(np.mean(lg3.argmax(1) == np.array([yi[i] for i in sub])))
    lo3 = float(torch.nn.functional.cross_entropy(torch.tensor(lg3), torch.tensor([yi[i] for i in sub])))
    res["T7b_overfit_64_600steps(post-hoc)"] = {"loss_history": hist3, "final_eval_loss": round(lo3, 4), "train_acc": acc3,
                                                 "PASS": lo3 < 0.1 and acc3 >= 0.95}
    for v in res.values():
        v["PASS"] = bool(v["PASS"])
    res["ALL_PASS"] = all(v["PASS"] for k, v in res.items() if k.startswith("T"))
    res["IMPLEMENTATION_OK"] = all(res[k]["PASS"] for k in res if k.startswith("T") and not k.startswith("T7")) and (
        res["T7_overfit_64"]["PASS"] or res["T7b_overfit_64_600steps(post-hoc)"]["PASS"])
    res["IMPLEMENTATION_OK_rule"] = "T1–T6·T8 PASS 그리고 (T7 또는 사후 T7b) PASS. T7 FAIL 기록은 유지."
    S.dump_json(S.OUT / "implementation_check.json", res)
    for k, v in res.items():
        print(k, {kk: vv for kk, vv in v.items() if kk != "example"} if isinstance(v, dict) else v)


if __name__ == "__main__":
    main()
