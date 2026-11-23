# -*- coding: utf-8 -*-
"""mutation_spec/mutation_operators_v1.json 정의대로 변이 규칙을 생성한다 (결정적, seed 고정)."""
import copy
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import D_ROOT, PRED_RE, detok, load_rules, parse, tokenize, vocab, ParseError  # noqa: E402

SPEC = json.load(open(os.path.join(D_ROOT, "mutation_spec", "mutation_operators_v1.json"), encoding="utf-8"))
SEED = SPEC["seed"]
NMAX = SPEC["max_samples_per_operator"]
rules = load_rules()
VP, VM = vocab(rules)


def top_level_split(toks, op):
    """깊이 0 의 op 위치 목록"""
    d, out = 0, []
    for i, t in enumerate(toks):
        if t == "(":
            d += 1
        elif t == ")":
            d -= 1
        elif d == 0 and t == op:
            out.append(i)
    return out


def conjuncts(toks):
    """최상위 OR 이 없을 때 최상위 AND 로 분할한 토큰 구간 리스트"""
    if top_level_split(toks, "OR"):
        return None
    cuts = top_level_split(toks, "AND")
    segs, prev = [], 0
    for c in cuts:
        segs.append(toks[prev:c]); prev = c + 1
    segs.append(toks[prev:])
    return segs


# ---------------- 연산자 ----------------
def m01(r, rng):
    toks = tokenize(r["condition"]); segs = conjuncts(toks)
    if not segs or len(segs) < 2:
        return None
    if rng is None:
        return True
    k = rng.randrange(len(segs))
    new = [t for j, s in enumerate(segs) if j != k for t in (s + ["AND"])][:-1]
    return {"condition": detok(new), "detail": f"drop conjunct {detok(segs[k])}"}


def tok_replace(op_from, op_to):
    def f(r, rng):
        toks = tokenize(r["condition"]); idx = [i for i, t in enumerate(toks) if t == op_from]
        if not idx:
            return None
        if rng is None:
            return True
        i = rng.choice(idx); toks[i] = op_to
        return {"condition": detok(toks), "detail": f"{op_from}->{op_to} at token {i}"}
    return f


def m04(r, rng):
    toks = tokenize(r["condition"]); idx = [i for i, t in enumerate(toks) if t == "NOT"]
    if not idx:
        return None
    if rng is None:
        return True
    i = rng.choice(idx); del toks[i]
    return {"condition": detok(toks), "detail": f"remove NOT at token {i}"}


def m05(r, rng):
    toks = tokenize(r["condition"])
    idx = [i for i, t in enumerate(toks) if PRED_RE.fullmatch(t) and (i == 0 or toks[i - 1] != "NOT")]
    if not idx:
        return None
    if rng is None:
        return True
    i = rng.choice(idx); toks.insert(i, "NOT")
    return {"condition": detok(toks), "detail": f"add NOT before {toks[i + 1]}"}


CMP_SWAP = {"lt": "ge", "ge": "lt", "gt": "le", "le": "gt"}
CMP_RE = re.compile(r"_(lt|ge|gt|le)_")


def m06(r, rng):
    toks = tokenize(r["condition"])
    idx = [i for i, t in enumerate(toks) if PRED_RE.fullmatch(t) and CMP_RE.search(t)]
    if not idx:
        return None
    if rng is None:
        return True
    i = rng.choice(idx); old = toks[i]
    new = CMP_RE.sub(lambda m: f"_{CMP_SWAP[m.group(1)]}_", old, count=1)
    toks[i] = new
    return {"condition": detok(toks), "detail": f"{old}->{new}", "new_id": new, "new_id_in_vocab": new in VP}


THR = {"egfr": ["15", "20", "25", "30", "45", "60"], "hba1c": ["7_0", "7_5", "9"],
       "potassium": ["5_0", "5_5", "6_0"], "uacr": ["30", "200"]}
NUM_RE = re.compile(r"(?<=_)(\d+(?:_\d+)?)(?=$|_)")


def m07(r, rng):
    toks = tokenize(r["condition"])
    idx = [i for i, t in enumerate(toks) if PRED_RE.fullmatch(t) and NUM_RE.search(t[5:])]
    if not idx:
        return None
    if rng is None:
        return True
    i = rng.choice(idx); old = toks[i]; body = old[5:]
    m = NUM_RE.search(body); val = m.group(1)
    stem = body.split("_")[0]
    if stem in THR and any(v != val for v in THR[stem]):
        newval = rng.choice([v for v in THR[stem] if v != val])
    else:
        a = val.split("_"); newval = str(int(a[0]) * 2) + ("_" + a[1] if len(a) > 1 else "")
    new = "pred." + body[:m.start()] + newval + body[m.end():]
    toks[i] = new
    return {"condition": detok(toks), "detail": f"{old}->{new}", "new_id": new, "new_id_in_vocab": new in VP}


def pred_syn(p):
    b = p[5:]
    if b.startswith("has_"):
        return "pred." + b[4:]
    if b.startswith("is_"):
        return "pred." + b[3:]
    return "pred.has_" + b


def m08(r, rng):
    toks = tokenize(r["condition"]); idx = [i for i, t in enumerate(toks) if PRED_RE.fullmatch(t)]
    if not idx:
        return None
    if rng is None:
        return True
    i = rng.choice(idx); old = toks[i]; new = pred_syn(old); toks[i] = new
    return {"condition": detok(toks), "detail": f"{old}->{new}", "new_id": new, "new_id_in_vocab": new in VP}


MED_ALIAS = {"sglt2": "sglt2i", "sglt2i": "sglt2", "dpp4": "dpp4i", "dpp4i": "dpp4", "glp1": "glp1ra",
             "glp1ra": "glp1", "bb": "beta_blocker", "beta_blocker": "bb", "nsmra": "ns_mra", "ns_mra": "nsmra",
             "mra": "mra_class"}


def med_syn(m):
    if m.startswith("med.class."):
        b = m[10:]
        return "med.class." + MED_ALIAS.get(b, b + "i")
    b = m[4:]
    if b == "semaglutide_tablet":
        return "med.semaglutide"
    return "med." + b + "_tablet"


def m09(r, rng):
    subs = [s for s in r["action"]["subjects"] if isinstance(s, str) and s.startswith("med.")]
    if not subs:
        return None
    if rng is None:
        return True
    k = rng.randrange(len(subs)); old = subs[k]; new = med_syn(old)
    act = copy.deepcopy(r["action"]); act["subjects"] = [new if s == old else s for s in act["subjects"]]
    return {"action": act, "detail": f"{old}->{new}", "new_id": new, "new_id_in_vocab": new in VM}


def m10(r, rng):
    toks = tokenize(r["condition"]); segs = conjuncts(toks)
    if not segs or len(segs) < 2:
        return None
    neg = [j for j, s in enumerate(segs) if s and s[0] == "NOT"]
    if not neg:
        return None
    if rng is None:
        return True
    k = rng.choice(neg)
    new = [t for j, s in enumerate(segs) if j != k for t in (s + ["AND"])][:-1]
    return {"condition": detok(new), "detail": f"delete exception {detok(segs[k])}"}


VP_SORTED = sorted(VP)


def m11(r, rng):
    if rng is None:
        return True
    present = set(PRED_RE.findall(r["condition"]))
    y = rng.choice([p for p in VP_SORTED if p not in present])
    return {"condition": f"({r['condition']}) AND {y}", "detail": f"add {y}"}


VM_CLASS = sorted(m for m in VM if m.startswith("med.class."))
VM_DRUG = sorted(m for m in VM if not m.startswith("med.class."))


def m12(r, rng):
    subs = [s for s in r["action"]["subjects"] if isinstance(s, str) and s.startswith("med.")]
    if not subs:
        return None
    if rng is None:
        return True
    k = rng.randrange(len(subs)); old = subs[k]
    pool = VM_CLASS if old.startswith("med.class.") else VM_DRUG
    new = rng.choice([m for m in pool if m not in subs])
    act = copy.deepcopy(r["action"]); act["subjects"] = [new if s == old else s for s in act["subjects"]]
    return {"action": act, "detail": f"{old}->{new}", "new_id": new, "new_id_in_vocab": True}


PFLIP = {"recommend": "avoid", "allow": "avoid", "consider": "avoid", "require": "contraindicate",
         "continue": "stop", "caution": "recommend", "avoid": "allow", "contraindicate": "allow", "stop": "continue",
         "reduce_dose": "increase_dose", "increase_dose": "reduce_dose", "start_low_dose": "avoid",
         "max_dose_limit": "increase_dose", "titrate": "avoid"}


def m13(r, rng):
    p = r["action"].get("permission")
    if p not in PFLIP:
        return None
    if rng is None:
        return True
    act = copy.deepcopy(r["action"]); act["permission"] = PFLIP[p]
    return {"action": act, "detail": f"{p}->{PFLIP[p]}"}


OPS = [("M01", m01), ("M02", tok_replace("AND", "OR")), ("M03", tok_replace("OR", "AND")), ("M04", m04),
       ("M05", m05), ("M06", m06), ("M07", m07), ("M08", m08), ("M09", m09), ("M10", m10), ("M11", m11),
       ("M12", m12), ("M13", m13)]
NAMES = {o["id"]: o["name"] for o in SPEC["operators"]}


def main():
    order = sorted(range(len(rules)), key=lambda i: rules[i]["id"])
    out, appl = [], {}
    for k, (oid, fn) in enumerate(OPS):
        cand = [i for i in order if fn(rules[i], None)]
        appl[oid] = len(cand)
        rng = random.Random(SEED + k)
        chosen = cand if len(cand) <= NMAX else rng.sample(cand, NMAX)
        for n, i in enumerate(chosen):
            r = rules[i]; res = fn(r, rng)
            mut = copy.deepcopy(r)
            if "condition" in res:
                mut["condition"] = res["condition"]
            if "action" in res:
                mut["action"] = res["action"]
            try:
                parse(mut["condition"]); ok = True
            except ParseError:
                ok = False
            out.append({"mutant_id": f"{oid}_{n:03d}", "op": oid, "op_name": NAMES[oid], "rule_idx": i,
                        "rule_id": r["id"], "orig_condition": r["condition"], "mut_condition": mut["condition"],
                        "orig_action": r["action"], "mut_action": mut["action"], "detail": res["detail"],
                        "new_id": res.get("new_id"), "new_id_in_vocab": res.get("new_id_in_vocab"),
                        "mut_parses": ok, "changed": (mut["condition"] != r["condition"] or mut["action"] != r["action"])})
    path = os.path.join(D_ROOT, "mutation_spec", "mutants_v1.jsonl")
    with open(path, "w", encoding="utf-8") as f:
        for m in out:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    print("applicable:", appl)
    print("mutants:", len(out), "unchanged:", sum(not m["changed"] for m in out),
          "unparseable:", sum(not m["mut_parses"] for m in out))


if __name__ == "__main__":
    main()
