# -*- coding: utf-8 -*-
"""B6(제안): quote 권고 방향 단서 vs permission 극성 대응 검사 (LLM 없음).

사용: python b6_permission_cue.py dev   -> dev 그룹에서 변형(A/B) 비교, 변형 선택
      python b6_permission_cue.py eval  -> 고정된 변형으로 eval 1회 평가 + v1 변이 전체에 적용
어휘는 dev quote 만 보고 작성했다 (logs/b6_dev_quotes_peek.log).
"""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import D_ROOT, load_rules  # noqa: E402
from gen_mutants import PFLIP  # noqa: E402

NEG_PHRASES = ["不常规推荐", "不建议", "不推荐", "不应", "不宜", "不可", "不能", "不需", "无需", "不适用", "不必"]
PROHIBIT = ["禁用", "禁忌", "不建议", "不推荐", "避免", "不应", "不宜", "停用", "暂停", "停止", "不可", "不能",
            "不适用", "中断", "不常规推荐"]
CAUTION = ["慎用", "谨慎", "关注", "加强监测", "密切监测", "注意"]
POSITIVE = ["推荐", "建议", "优先", "首选", "可", "考虑", "继续", "应", "需", "起始", "维持", "选择", "选用",
            "启动", "正常使用", "保留"]
DOSE_DOWN = ["减", "限制剂量", "≤", "起始剂量", "1/2", "1/4", "低剂量", "不超过"]
DOSE_UP = ["增加至", "增加剂量", "加量", "增至", "增加到"]

GROUP = {"contraindicate": "prohibit", "avoid": "prohibit", "stop": "prohibit", "allow": "positive",
         "recommend": "positive", "require": "positive", "consider": "positive", "continue": "positive",
         "caution": "caution", "reduce_dose": "dose_down", "max_dose_limit": "dose_down",
         "start_low_dose": "dose_down", "increase_dose": "dose_up", "titrate": None}
OPPOSITE = {"prohibit": ["positive"], "positive": ["prohibit", "caution"], "caution": ["positive"],
            "dose_down": ["dose_up"], "dose_up": ["dose_down", "prohibit"]}


def cues(quote):
    q = quote or ""
    stripped = q
    for p in NEG_PHRASES:
        stripped = stripped.replace(p, "")
    return {"prohibit": any(c in q for c in PROHIBIT), "caution": any(c in q for c in CAUTION),
            "positive": any(c in stripped for c in POSITIVE), "dose_down": any(c in q for c in DOSE_DOWN),
            "dose_up": any(c in q for c in DOSE_UP)}


def b6(permission, quote, variant):
    g = GROUP.get(permission)
    if g is None:
        return 0
    c = cues(quote)
    own = c[g]
    if variant == "A":  # 자기 극성 단서 없음
        return int(not own)
    # variant B: 자기 극성 단서 없음 AND 반대 극성 단서 있음
    return int((not own) and any(c[o] for o in OPPOSITE[g]))


def split_groups(rules):
    def g(s):
        return re.sub(r"[（(][^）)]*[）)]", "", s).replace(" ", "")
    gs = sorted({g(r["provenance"][0]["source"]) for r in rules})
    dev = {x for i, x in enumerate(gs) if i % 2 == 0}
    return ["dev" if g(r["provenance"][0]["source"]) in dev else "eval" for r in rules]


def evaluate(rules, split, part, variant):
    idx = [i for i, s in enumerate(split) if s == part]
    fp = [b6(rules[i]["action"]["permission"], rules[i]["provenance"][0]["quote"], variant) for i in idx]
    det = []
    for i in idx:
        p = rules[i]["action"]["permission"]
        if p in PFLIP:
            q = rules[i]["provenance"][0]["quote"]
            det.append(int(b6(PFLIP[p], q, variant) and not b6(p, q, variant)))
    return {"part": part, "variant": variant, "n_orig": len(idx), "orig_flag_rate": round(sum(fp) / len(fp), 3),
            "n_m13_all": len(det), "m13_new_flag_rate": round(sum(det) / len(det), 3)}


def main():
    rules = load_rules(); split = split_groups(rules)
    mode = sys.argv[1]
    out = []
    if mode == "dev":
        for v in ("A", "B"):
            out.append(evaluate(rules, split, "dev", v))
        # 선택 규칙(사전 고정): dev 위양성 <=0.15 중 dev 탐지율 최대, 동률이면 B
        ok = [r for r in out if r["orig_flag_rate"] <= 0.15] or out
        best = max(ok, key=lambda r: (r["m13_new_flag_rate"], r["variant"] == "B"))
        json.dump({"chosen_variant": best["variant"], "dev": out}, open(os.path.join(D_ROOT, "logs", "b6_dev_choice.json"), "w"), indent=1)
        print(json.dumps(out, indent=1), "chosen:", best["variant"])
        return
    choice = json.load(open(os.path.join(D_ROOT, "logs", "b6_dev_choice.json")))["chosen_variant"]
    res = [evaluate(rules, split, "dev", choice), evaluate(rules, split, "eval", choice)]
    # 같은 eval 집합에서 기준선 비교: M13_ALL 에 대해 B1/B3/B5 는 permission 을 보지 않으므로 정의상 신규 플래그 0
    # (B5 는 permission 미사용, B1 은 enum 검사만 -> 반전 permission 도 enum 안). 코드로 확인:
    sys.path.insert(0, HERE)
    import eval_static as es  # noqa: E402
    cmp_rows = []
    for i, s in enumerate(split):
        if s != "eval":
            continue
        r = rules[i]; p = r["action"]["permission"]
        if p not in PFLIP:
            continue
        q = r["provenance"][0]["quote"]
        ma = dict(r["action"]); ma["permission"] = PFLIP[p]
        o1 = set(es.b1_check(r["condition"], r["action"], es.VP, es.VM)); m1 = set(es.b1_check(r["condition"], ma, es.VP, es.VM))
        o5 = set(es.b5_check(r["condition"], r["action"], q)); m5 = set(es.b5_check(r["condition"], ma, q))
        ob3 = set(es.b3_check(es.all_ids(r["condition"], r["action"]))[0]); mb3 = set(es.b3_check(es.all_ids(r["condition"], ma))[0])
        b6n = int(b6(PFLIP[p], q, choice) and not b6(p, q, choice))
        cmp_rows.append({"rule_id": r["id"], "orig_perm": p, "mut_perm": PFLIP[p], "B1_new": int(bool(m1 - o1)),
                         "B3_new": int(bool(mb3 - ob3)), "B5_new": int(bool(m5 - o5)), "B6_new": b6n,
                         "B6_orig_flag": b6(p, q, choice)})
    with open(os.path.join(D_ROOT, "results_b6_eval_m13all.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(cmp_rows[0].keys())); w.writeheader(); w.writerows(cmp_rows)
    # 다른 오류 유형(v1 변이 M01~M12)에 대한 추가 플래그
    muts = [json.loads(l) for l in open(os.path.join(D_ROOT, "mutation_spec", "mutants_v1.jsonl"), encoding="utf-8")]
    other = {}
    for m in muts:
        q = rules[m["rule_idx"]]["provenance"][0]["quote"]
        nf = int(b6(m["mut_action"]["permission"], q, choice) and not b6(m["orig_action"]["permission"], q, choice))
        other.setdefault(m["op"], []).append(nf)
    other_rate = {k: round(sum(v) / len(v), 3) for k, v in sorted(other.items())}
    n = len(cmp_rows)
    summary = {"variant": choice, "dev_eval": res,
               "eval_m13all_rates": {k: round(sum(r[k] for r in cmp_rows) / n, 3) for k in ["B1_new", "B3_new", "B5_new", "B6_new"]},
               "eval_m13all_n": n,
               "eval_B5_or_B6": round(sum(int(r["B5_new"] or r["B6_new"]) for r in cmp_rows) / n, 3),
               "v1_mutants_B6_new_flag_by_op": other_rate,
               "eval_m13_by_orig_perm": {}}
    by = {}
    for r in cmp_rows:
        by.setdefault(r["orig_perm"], []).append(r["B6_new"])
    summary["eval_m13_by_orig_perm"] = {k: f"{sum(v)}/{len(v)}" for k, v in sorted(by.items())}
    json.dump(summary, open(os.path.join(D_ROOT, "results_b6_summary.json"), "w"), ensure_ascii=False, indent=1)
    print(json.dumps(summary, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
