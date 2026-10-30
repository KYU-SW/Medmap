"""STEP29.1 사후 탐색(EXPLORATORY_POST_HOC — 공식 판정 후 작성, 판정에 쓰지 않음).
질문: P5 가드 중 무엇이 coverage(0.625→0.5119)·다중 보존(0.675→0.625)을 깎았나?
 1 pilot 274 에서 P5 가드가 막은 EXISTING mention 을 규칙별로 '정답 concept 이었음(gold 집합 안)' / '오답이었음' 으로 집계
 2 규칙 하나씩 끈 변형(P5−rule)의 REGRESSION168 precision·coverage·pilot 다중 보존·G5(pilot absent·새 계약) 재계산
 3 전향적 T4_RESOLVED 0/10 원인: 템플릿이 '…났어요 오늘은 괜찮아요.'(첫 문장 뒤 마침표 없음) — 문장 분리 확인
출력: outputs/exploratory_guard_ablation.json"""
from __future__ import annotations

import collections
import json

import mention_context_validator as MCV
import s291_common as S
from clause_segmenter import segment
from contract_check_v2 import check as check2
from nlu_pipeline_v2 import analyze

EX = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")
RULES = ("PAIN_PREDICATE_MISMATCH", "LEXICAL_OVERLAP_ZERO", "EVIDENCE_IDEOPHONE_MISSING", "MODEL_ONLY_NO_CUE")


def metrics(pilot, regg, models, cnew):
    ra = rc = mn = mm = g5 = 0
    for r in pilot:
        o = analyze(r["text_ko"], "P5")
        golds = json.loads(r["gold_mentions"] or "[]")
        gm = [g for g in golds if g["concept"] in models]
        ex = [x for x in o["mentions"] if x["status"] in EX]
        used = set()
        for g in gm:
            if len(gm) >= 2:
                mn += 1
            i = next((k for k, x in enumerate(ex) if k not in used and x["canonical_id"] == g["concept"]), None)
            if i is not None:
                used.add(i)
                mm += len(gm) >= 2
                if g.get("status") == "absent" and ex[i]["assertion"] == "PRESENT" and ex[i]["model_input"]["polarity"] == "POSITIVE":
                    g5 += 1
        if r["text_ko"] in regg and ex:
            ra += 1
            rc += ex[0]["canonical_id"] == regg[r["text_ko"]]
    g5 += sum(1 for c in cnew for e in check2(c, analyze(c["text"], "P5")) if e["type"] == "MODEL_POSITIVE_FORBIDDEN" or (e["type"] == "NEGATION" and e.get("unsafe")))
    return {"reg_precision": S.rnd(rc / ra), "reg_coverage": S.rnd(ra / len(regg)), "pilot_multi_retention": S.rnd(mm / mn), "G5_pilot_absent+new_contract": g5}


def main():
    pilot = S.read_csv(S.S21_DIR / "data/pilot_gold.csv")
    regg = {r["text"]: r["gold_concept"] for r in S.read_csv(S.S27_DIR / "outputs/routing_features.csv") if r["set"] in ("INT_DEV_CORE", "INT_REGRESSION_CORE")}
    models = {r["canonical_id"] for r in S.read_csv(S.S28.DATA / "existing_concept_inventory.csv")}
    cnew = json.loads((S.DATA / "contract_cases.json").read_text(encoding="utf-8"))["contracts"]
    blocked = collections.Counter()
    ex_rows = []
    for r in pilot:
        gset = {g["concept"] for g in json.loads(r["gold_mentions"] or "[]")}
        for x in analyze(r["text_ko"], "P5")["mentions"]:
            if x.get("guard_blocked_concept") and any(g in RULES for g in x.get("guard_reasons") or []):
                ok = x["guard_blocked_concept"] in gset
                for g in x["guard_reasons"]:
                    if g in RULES:
                        blocked[(g, "blocked_correct" if ok else "blocked_wrong")] += 1
                ex_rows.append((r["text_ko"], x["raw_span"], x["guard_blocked_concept"], x["guard_reasons"], "정답" if ok else "오답"))
    orig = MCV.apply
    abl = {"P5_official": metrics(pilot, regg, models, cnew)}
    for rule in RULES:
        def patched(m, rule=rule):
            out = orig(m)
            rs = [g for g in out.get("guard_reasons") or [] if g in RULES]
            if out is not m and rs == [rule]:
                return m
            return out
        MCV.apply = patched
        abl[f"P5_minus_{rule}"] = metrics(pilot, regg, models, cnew)
        MCV.apply = orig
    t = "기침이 났어요 오늘은 괜찮아요."
    seg = [(c["sentence_index"], c["kind"], c["text"]) for c in segment(t)]
    out = {"label": "EXPLORATORY_POST_HOC(공식 판정 아님)", "rules": __doc__, "blocked_by_rule(pilot)": {f"{a}:{b}": v for (a, b), v in sorted(blocked.items())},
           "blocked_examples": ex_rows[:30], "ablation": abl, "prospective_T4_segmentation": {"text": t, "clauses": seg}}
    S.dump_json(S.OUT / "exploratory_guard_ablation.json", out)
    print(S.dumps({k: out[k] for k in ("blocked_by_rule(pilot)", "ablation", "prospective_T4_segmentation")}))
    for e in ex_rows[:25]:
        print(" ", e)


if __name__ == "__main__":
    main()
