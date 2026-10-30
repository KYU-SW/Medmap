"""STEP28.8 탐색 변형 P5x(EXPLORATORY_POST_HOC — 공식 평가 결과를 본 뒤 작성, 판정에 쓰지 않음). 고정 파일은 바꾸지 않고 실행 중에만 덮어쓴다.

사후 발견(1차 평가 후):
 (a) 남은 부분 문자열 오매칭 39 중 대부분이 STEP28.5 술어 정규화 키(nkey) 일치 — 의성어·부사·위치 명사를 버려
     '속이 화끈화끈해요'(gold heartburn) = '속이 울렁울렁해요'(nausea) 처럼 다른 의미를 같은 키로 만든다.
 (b) 경계 일치 항목 중 부사가 빠져 핵심 형태소가 원 용어보다 크게 줄어든 것('심장이 덜컥거립니다' → [심장])이 신체 부위 단독처럼 동작.
P5x = P5 + (a) nkey 일치는 용어 핵심 형태소열이 질의 형태소열에 연속으로 들어 있을 때만 인정 + (b) 경계 항목은 핵심 형태소 글자 수 ≥ 용어 조사 제거 키의 50%.
지표 정의는 evaluate_policies 와 같음(주요 지표만). 출력: outputs/exploratory_p5x.json
"""
from __future__ import annotations

import json

import s288_common as S
from evaluator import violations
from evaluate_policies import PROBES28_7, PROBES_NEW, SUPPORTED12
from policies import PolicyEngine
from repair_korean_matching import RepairedRetriever, contains, core_tokens, modal
from safe_offline_retriever import EXISTING, POSITIVE


def strict_exact(self, sp, keys):
    qm = modal(sp["span_text"]) or modal(sp.get("source_text", ""))
    Q = core_tokens(sp["span_text"])
    out = []
    for k in keys:
        for r in self.idx.get(k, []) + self.skey.get(k, []):
            via_nkey = r.get("nkey") == k and r["key"] != k
            if via_nkey and (len(k) < 2 or modal(r["ko_term"]) != qm or not contains(Q, core_tokens(r["ko_term"]))):
                continue
            out.append({**r, "tier": "EXACT", "qkey": k})
    return out


def main():
    E = PolicyEngine()
    RepairedRetriever.exact = strict_exact
    for f, lst in list(E.R.by_first.items()):
        E.R.by_first[f] = [(C, r) for C, r in lst if sum(map(len, C)) >= 0.5 * len(S.ko_key(S.stem_key(r["ko_term"])))]
    E.R.ko_mode = "repaired"

    def p5x(t):
        rep = E.R.run(t, "KO_ONLY")
        out = []
        for o in rep:
            ks = E.keys(t, o, len(rep))
            r = E.combine(t, o, E.clean.lookup(ks), "P5")
            out.append(E.apply_distinct(E.apply_held(r, o, ks), ks))
        return out
    feats = {r["text"]: r["gold_concept"] for r in S.read_csv(S.S27_DIR / "outputs/routing_features.csv") if r["set"] in ("INT_DEV_CORE", "INT_REGRESSION_CORE")}
    pilot = S.read_csv(S.S21_DIR / "data/pilot_gold.csv")
    gset = {r["text_ko"]: {m["concept"] for m in json.loads(r["gold_mentions"] or "[]")} for r in pilot}
    models = E.models
    res = {"reg": [], "extra": [], "wn": 0, "viol": 0, "sup": 0}
    for t, g in feats.items():
        a = [o["canonical_id"] for o in p5x(t) if o["status"] in EXISTING and o["canonical_id"] in models]
        res["reg"].append((t, g, a))
    for r in pilot:
        if r["text_ko"] in feats:
            continue
        a = [o["canonical_id"] for o in p5x(r["text_ko"]) if o["status"] in EXISTING and o["canonical_id"] in models]
        res["extra"].append((r["text_ko"], r["primary_concept"], r["should_link"], a))
    wn = [r["text"] for r in S.read_csv(S.S28_DIR / "outputs/weak_non_check.csv")]
    sil = [r["raw_expression"] for r in S.read_csv(S.S28_DIR / "data/external_silver_expansion.csv")]
    allin = list(feats) + [x[0] for x in res["extra"]] + wn + sil + list(dict.fromkeys(PROBES28_7 + PROBES_NEW)) + [t for t, _ in SUPPORTED12]
    for t in allin:
        os_ = p5x(t)
        a = [o["canonical_id"] for o in os_ if o["status"] in EXISTING]
        d = [c for o in os_ for c in o["display"]]
        res["viol"] += bool(violations(t, a + d))
        if t in wn and any(o["status"] in POSITIVE for o in os_):
            res["wn"] += 1
    res["sup"] = sum(g in [o["canonical_id"] for o in p5x(t) if o["status"] in EXISTING] for t, g in SUPPORTED12)
    au = [(t, g, a) for t, g, a in res["reg"] if a]
    link = [x for x in res["extra"] if x[2] == "True" and x[1] in models]
    spans = [(t, c) for t, _, _, a in res["extra"] for c in a]
    out = {"label": "EXPLORATORY_POST_HOC(공식 판정 아님)", "rules": __doc__,
           "P5x": {"R1_regression_coverage": S.rnd(len(au) / len(res["reg"])), "R2_regression_precision(first_auto)": S.rnd(sum(a[0] == g for _, g, a in au) / len(au)),
                   "R2_n": f"{sum(a[0] == g for _, g, a in au)}/{len(au)}", "X1_extra_span_precision": S.rnd(sum(c in gset[t] for t, c in spans) / len(spans)) if spans else None,
                   "X2_extra_primary_coverage": S.rnd(sum(x[1] in x[3] for x in link) / len(link)), "X3_should_not_link_auto": sum(bool(x[3]) for x in res["extra"] if x[2] == "False"),
                   "W1_weaknon_auto_link": res["wn"], "V1_semantic_violation_inputs(all inputs)": res["viol"], "SUP_supported12": res["sup"],
                   "regression_wrong": [(t, g, a[0]) for t, g, a in au if a[0] != g]},
           "P5_official": {k: S.load_json(S.OUT / "eval_summary.json")["metrics"]["P5"].get(k) for k in ("R1_regression_coverage", "R2_regression_precision(first_auto)",
                                                                                                         "X1_extra_span_precision", "X2_extra_primary_coverage", "X3_should_not_link_auto",
                                                                                                         "W1_weaknon_auto_link", "V1_semantic_violation_inputs", "SUP_supported12")}}
    S.dump_json(S.OUT / "exploratory_p5x.json", out)
    print(S.dumps({k: out[k] for k in ("P5x", "P5_official")}))


if __name__ == "__main__":
    main()
