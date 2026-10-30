"""STEP27 Safe Symptom Router(실험용, production 아님). 상태 5개: KNOWN_SYMPTOM · UNKNOWN_SYMPTOM · NON_SYMPTOM · UNCERTAIN · COMPLEX_INPUT.

[상태 의미 — 사전 고정]
 KNOWN_SYMPTOM   : 지원 concept(77) 자동 수락 조건 충족 → AUTO_ACCEPT, canonical_id 1개.
 UNKNOWN_SYMPTOM : 증상이라는 근거(SYMPTOM_CUE 또는 비증상 점수 p_non < 0.5)는 있으나 지원 concept 과의 연결 근거가 부족
                   → PRESERVE_RAW, canonical_id null, 표시 후보 없음(내부 후보는 model_evidence 에만), 원문 보존, 확인 필요.
 UNCERTAIN       : (a) 지원 concept 후보가 있으나 자동 수락 기준 미달 → ASK_CONFIRMATION(표시 허용 후보만), 또는
                   (b) 증상인지 아닌지 근거가 모두 부족 → ASK_CONFIRMATION(후보 없이 자유 설명 요청).
 NON_SYMPTOM     : 질환·약물·치료·검사 등 '증상이 아닌 유형'의 적극적 근거 → DO_NOT_MAP(증상 기록과 분리, 원문은 보존).
 COMPLEX_INPUT   : 부정·과거·타인·복수 연결어·40자 초과(STEP26 정규식 그대로) → DEFER_TO_NLU, 단일 증상 자동 수락 금지.

[정책 — 사전 고정, 파라미터는 DEV 에서만 선택(evaluate_routing 문서열)]
 POLICY_A = STEP26 B4 + STEP26 상태 규칙 그대로(COMPLEX→UNCERTAIN, NON = p_non ≥ 0.65, 동의 → 후보 3 표시, 불일치 & p_non<0.5 → UNKNOWN).
 POLICY_B = A 에서 NON 규칙만 교체(보수적 NON): SYMPTOM_CUE 없음 AND [(NON_TYPE_CUE AND p_non ≥ t_type) OR p_non ≥ t_strong].
            SYMPTOM_CUE 가 있거나 근거가 부족하면 NON 금지 → A 의 나머지 규칙으로.
 POLICY_C = B + COMPLEX_INPUT 상태(DEFER_TO_NLU) + UNKNOWN 보존: 불일치 & (SYMPTOM_CUE 또는 p_non < 0.5) → UNKNOWN_SYMPTOM/PRESERVE_RAW.
            동의(지원 후보 존재) → UNCERTAIN/ASK_CONFIRMATION(후보 = 동의 concept + 각 모델 2위, 최대 3 — A 와 같은 pool).
            그 외 → UNCERTAIN/ASK_CONFIRMATION(후보 없음).
 POLICY_D = C + 후보 표시 제한: pool 의 후보 c 는 KoE 확률 P(c) ≥ d_conf AND cand_sim(c) ≥ d_sim 일 때만 표시
            (cand_sim = 입력 ↔ c 의 학습 표현 최대 bigram Jaccard). 표시 후보가 0 이면 → 증상 근거 있으면 UNKNOWN_SYMPTOM/PRESERVE_RAW
            (reason CANDIDATE_LINK_WEAK), 없으면 UNCERTAIN/ASK_CONFIRMATION(후보 없음). D 는 표시를 줄이기만 한다(새 후보 추가 없음).
 POLICY_E(탐색, B4 임계 변경) = D + 자동 수락 규칙 교체: agree & lin_margin ≥ a & koe_conf ≥ b & (train_sim ≥ s OR cand_sim(top1) ≥ c).
 모든 정책: 모델 불일치(agree False)는 자동 수락 불가(B4·E 정의상).
"""
from __future__ import annotations

import s27_common as S

STATUSES = ("KNOWN_SYMPTOM", "UNKNOWN_SYMPTOM", "NON_SYMPTOM", "UNCERTAIN", "COMPLEX_INPUT")
POLICIES = ("POLICY_A", "POLICY_B", "POLICY_C", "POLICY_D", "POLICY_E")
T_NON_A, T_SYM = 0.65, 0.5


def auto_accept(policy: str, f: dict, pe: dict | None) -> bool:
    if f["complex"]:
        return False
    if policy == "POLICY_E":
        return bool(f["agree"] and f["lin_margin"] >= pe["a"] and f["koe_conf"] >= pe["b"]
                    and (f["train_sim"] >= pe["s"] or f["csim"].get(f["lin_top1"], 0.0) >= pe["c"]))
    return bool(f["b4_auto"])


def is_non(policy: str, f: dict, pb: dict | None) -> tuple[bool, str]:
    if policy == "POLICY_A":
        return f["p_non"] >= T_NON_A, "NON_SYMPTOM_SCORE"
    if f["sym_cue"]:
        return False, ""
    if f["non_type"] and f["p_non"] >= pb["t_type"]:
        return True, "NON_TYPE_CUE:" + f["non_type"]
    if f["p_non"] >= pb["t_strong"]:
        return True, "NON_SYMPTOM_SCORE_STRONG"
    return False, ""


def pool(f: dict) -> list[str]:
    return list(dict.fromkeys([f["lin_top1"], f["lin_top2"], f["koe_top2"]]))[:3]


def route(policy: str, f: dict, params: dict) -> dict:
    """f = 특징 dict(evaluate_routing.build_features / SafeSymptomRouter.features). 반환 = 실험용 인터페이스."""
    pb, pd, pe = params.get("B"), params.get("D"), params.get("E")
    internal = pool(f)
    reasons: list[str] = []
    cand: list[str] = []
    canon = None
    if f["complex"]:
        reasons.append("COMPLEX_INPUT:" + ";".join(f["complex_flags"]))
        if policy in ("POLICY_A", "POLICY_B"):
            st, dec = "UNCERTAIN", "ASK_CONFIRMATION"
        else:
            st, dec = "COMPLEX_INPUT", "DEFER_TO_NLU"
    elif auto_accept(policy, f, pe):
        st, dec, canon, cand = "KNOWN_SYMPTOM", "AUTO_ACCEPT", f["lin_top1"], [f["lin_top1"]]
        reasons.append("AUTO_RULE:" + ("B4" if policy != "POLICY_E" else "E"))
    else:
        non, why = is_non(policy, f, pb)
        sym_ev = f["sym_cue"] or f["p_non"] < T_SYM
        if non:
            st, dec = "NON_SYMPTOM", "DO_NOT_MAP"
            reasons.append(why)
        elif f["agree"]:
            cand = internal
            st, dec = "UNCERTAIN", "ASK_CONFIRMATION"
            reasons.append("AGREE_BELOW_AUTO_THRESHOLD")
            if policy in ("POLICY_D", "POLICY_E"):
                shown = [c for c in cand if f["koe_p"][c] >= pd["d_conf"] and f["csim"][c] >= pd["d_sim"]]
                if len(shown) < len(cand):
                    reasons.append(f"CANDIDATE_SUPPRESSED:{len(cand) - len(shown)}")
                cand = shown
                if not cand:
                    if sym_ev:
                        st, dec = "UNKNOWN_SYMPTOM", "PRESERVE_RAW"
                        reasons.append("CANDIDATE_LINK_WEAK")
                    else:
                        reasons.append("TYPE_UNCLEAR_FREE_DESCRIPTION")
        elif (policy in ("POLICY_A", "POLICY_B") and f["p_non"] < T_SYM) or (policy not in ("POLICY_A", "POLICY_B") and sym_ev):
            st, dec = "UNKNOWN_SYMPTOM", "PRESERVE_RAW"
            reasons.append("MODEL_DISAGREE_SYMPTOM_EVIDENCE" + (":CUE" if f["sym_cue"] else ":LOW_P_NON"))
        else:
            st, dec = "UNCERTAIN", "ASK_CONFIRMATION"
            reasons.append("MODEL_DISAGREE_TYPE_UNCLEAR")
    if not f["agree"]:
        reasons.append("MODEL_DISAGREEMENT")
    return {"source_text": f["text"], "status": st, "canonical_id": canon, "candidate_ids": cand,
            "candidate_display_allowed": bool(cand) and st == "UNCERTAIN", "decision": dec,
            "requires_confirmation": dec in ("ASK_CONFIRMATION", "PRESERVE_RAW", "DEFER_TO_NLU"), "reason_codes": reasons,
            "raw_record": {"raw_expression": f["text"], "extracted_span": f.get("span") or f["text"], "supported": st == "KNOWN_SYMPTOM",
                           "internal_candidate_ids": internal, "uncertain_reason": [r for r in reasons if not r.startswith("AUTO_RULE")]},
            "model_evidence": {"linear_top1": f["lin_top1"], "linear_margin": round(f["lin_margin"], 4), "transformer_top1": f["koe_top1"],
                               "transformer_score": round(f["koe_conf"], 4), "agreement": f["agree"], "train_similarity": round(f["train_sim"], 4),
                               "non_symptom_score": round(f["p_non"], 4), "symptom_cue": f["sym_cue"], "non_type_cue": f["non_type"],
                               "candidate_similarity": {c: round(f["csim"][c], 4) for c in internal},
                               "candidate_transformer_prob": {c: round(f["koe_p"][c], 4) for c in internal}}}


class SafeSymptomRouter:
    """단일 입력 → 인터페이스. 모델·분류기·임계값은 모두 고정 파일에서 읽는다(CPU)."""

    def __init__(self, policy: str | None = None):
        import torch
        from safe_normalizer import SafeNormalizer  # STEP26 구성요소 재사용(read-only)
        self.sn = SafeNormalizer()
        self.tr_by_c = S.load_train_by_concept()
        sel = S.load_json(S.OUT / "routing_selection.json")
        self.policy = policy or sel["BEST_POLICY"]
        self.params = sel["params"]
        self.b4 = S.load_json(S.S26.OUT / "policy_selection.json")["policies"]["B4"]["params"]
        torch.set_grad_enabled(False)

    def features(self, text: str) -> dict:
        import numpy as np
        sn = self.sn
        t = S.norm(text)
        flags = S.complex_flags(text)
        L = sn.lin.decision_function([t])[0]
        ol = np.argsort(-L)
        b = sn.tok([t], truncation=True, max_length=sn.max_len, return_tensors="pt")
        lg = sn.koe(**b).logits[0].numpy()
        pr = np.exp(lg - lg.max())
        pr /= pr.sum()
        ok = np.argsort(-pr)
        cls = [str(c) for c in sn.cls]
        x = S.nospace(text)
        f = {"text": text, "complex_flags": flags, "complex": bool(flags), "lin_top1": cls[ol[0]], "lin_top2": cls[ol[1]],
             "lin_margin": float(L[ol[0]] - L[ol[1]]), "koe_top1": cls[ok[0]], "koe_top2": cls[ok[1]], "koe_conf": float(pr[ok[0]]),
             "train_sim": sn._sim(x) if len(x) <= 40 else -1.0, "p_non": float(sn.stat.predict_proba([t])[0, 1]),
             "sym_cue": S.symptom_cue(text), "non_type": S.non_type(text)}
        f["agree"] = f["lin_top1"] == f["koe_top1"]
        f["b4_auto"] = S.P26.decide("B4", self.b4, {**f, "row_id": "-"})[1]
        ci = {c: i for i, c in enumerate(cls)}
        f["csim"] = {c: S.cand_sim(text, c, self.tr_by_c) for c in pool(f)}
        f["koe_p"] = {c: float(pr[ci[c]]) for c in pool(f)}
        if f["lin_top1"] not in f["csim"]:
            f["csim"][f["lin_top1"]] = S.cand_sim(text, f["lin_top1"], self.tr_by_c)
        return f

    def __call__(self, text: str) -> dict:
        return route(self.policy, self.features(text), self.params)
