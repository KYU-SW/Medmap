"""STEP26 실험용 SafeNormalizer — 단일 입력 → 상태 인터페이스(JSON dict). production 코드 아님.

구성(모두 고정, read-only): Linear(STEP23) · KoELECTRA(STEP24-v2 seed42, CPU) · BEST_POLICY 파라미터(policy_selection.json) ·
status classifier(models/status_classifier.joblib) · T_non(status_classifier.json). 상태 결정 순서는 evaluate_ood_gate 와 동일.
"""
import difflib

import joblib
import numpy as np
import torch

import policy_lib as P
import s26_common as S


class SafeNormalizer:
    def __init__(self):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.lin, _ = S.S24.linear_model()
        self.cls = list(self.lin.classes_)
        self.tok = AutoTokenizer.from_pretrained(S.KOE_DIR)
        self.koe = AutoModelForSequenceClassification.from_pretrained(S.KOE_DIR).to("cpu").eval()
        self.max_len = S.load_json(S.S24.ENV_JSON)["selected_max_length"]
        sel = S.load_json(S.OUT / "policy_selection.json")
        self.policy = sel["BEST_POLICY"]
        self.params = sel["policies"][self.policy]["params"] if self.policy != "NONE" else None
        assert self.policy in ("B1", "B2", "B3", "B4"), "SafeNormalizer 는 규칙 정책만 지원(GATE 미승격 전제)"
        self.stat = joblib.load(S.STEP / "models/status_classifier.joblib")
        self.T_non = S.load_json(S.OUT / "status_classifier.json")["T_non"]
        self.train_ns = [S.nospace(r["expression"]) for r in S.read_csv(S.S23 / "data/expanded_train_expressions.csv")]
        torch.set_grad_enabled(False)

    def _sim(self, x):
        best = 0.0
        for t in self.train_ns:
            sm = difflib.SequenceMatcher(None, x, t, autojunk=False)
            if sm.real_quick_ratio() > best and sm.quick_ratio() > best:
                best = max(best, sm.ratio())
        return best

    def __call__(self, text: str) -> dict:
        t = S.norm(text)
        flags = S.complex_flags(text)
        L = self.lin.decision_function([t])[0]
        order_l = np.argsort(-L)
        b = self.tok([t], truncation=True, max_length=self.max_len, return_tensors="pt")
        lg = self.koe(**b).logits[0].numpy()
        pr = np.exp(lg - lg.max())
        pr /= pr.sum()
        order_k = np.argsort(-pr)
        l1, l2, k1, k2 = self.cls[order_l[0]], self.cls[order_l[1]], self.cls[order_k[0]], self.cls[order_k[1]]
        x = S.nospace(text)
        r = {"lin_top1": l1, "lin_margin": float(L[order_l[0]] - L[order_l[1]]), "koe_top1": k1, "koe_conf": float(pr[order_k[0]]),
             "agree": l1 == k1, "train_sim": self._sim(x) if len(x) <= 40 else -1.0, "complex": bool(flags), "row_id": "-"}
        label, auto = P.decide(self.policy, self.params, r)
        pn = float(self.stat.predict_proba([t])[0, 1])
        if flags:
            st, dec, cand, why = "UNCERTAIN", "NEEDS_CONFIRMATION", [], "COMPLEX_INPUT:" + ";".join(flags)
        elif auto:
            st, dec, cand, why = "KNOWN_SYMPTOM", "AUTO_ACCEPT", [label], self.policy
        elif self.T_non is not None and pn >= self.T_non:
            st, dec, cand, why = "NON_SYMPTOM", "DO_NOT_MAP", [], "NON_SYMPTOM_SCORE"
        elif r["agree"]:
            st, dec, cand, why = "UNCERTAIN", "ASK_CONFIRMATION", list(dict.fromkeys([l1, l2, k2]))[:3], "AGREE_LOW_CONFIDENCE"
        elif pn < 0.5:
            st, dec, cand, why = "UNKNOWN_SYMPTOM", "NEEDS_CONFIRMATION", [], "DISAGREE_SYMPTOM_LIKE"
        else:
            st, dec, cand, why = "UNCERTAIN", "NEEDS_CONFIRMATION", [], "DISAGREE_UNCLEAR"
        return {"status": st, "canonical_id": cand[0] if st == "KNOWN_SYMPTOM" else None, "candidate_ids": cand, "decision": dec,
                "requires_confirmation": dec in ("ASK_CONFIRMATION", "NEEDS_CONFIRMATION"), "source_text": text,
                "model_evidence": {"linear_top1": l1, "linear_margin": round(r["lin_margin"], 4), "transformer_top1": k1,
                                   "transformer_score": round(r["koe_conf"], 4), "agreement": r["agree"], "train_similarity": round(r["train_sim"], 4),
                                   "non_symptom_score": round(pn, 4)}, "reason": why}
