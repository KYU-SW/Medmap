# -*- coding: utf-8 -*-
"""B1(정적), B2(동치, 정답 필요), B3(용어 정규화), B5(quote 대응) 를 원본 563 규칙과 변이 규칙에 적용."""
import csv
import json
import os
import re
import sys

import z3

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import D_ROOT, PERMISSIONS, PRED_RE, ParseError, load_rules, parse, to_z3, vocab  # noqa: E402
from med_lexicon import CUE_GE, CUE_LT, CUE_NEG, LEX  # noqa: E402
from orig_loader import load_pipeline_modules  # noqa: E402

_, _, LSH = load_pipeline_modules()  # 원본 compute_shingles / compute_minhash 사용
rules = load_rules()
VP, VM = vocab(rules)
VOCAB = VP | VM
ID_RE = re.compile(r"(pred|med)\.[a-z0-9_.]+", re.I)

# ---------- B3 정규화 ----------
ABBR = {"beta_blocker": "bb", "sulfonylurea": "su", "ns_mra": "nsmra", "diuretics": "diuretic", "glinides": "glinide",
        "hepatic": "liver", "servere": "severe", "lactating": "lactation"}


def norm_key(i):
    s = i.lower()
    kind = "med" if s.startswith("med.") else "pred"
    s = re.sub(r"^(pred\.|med\.class\.|med\.)", "", s)
    for a, b in ABBR.items():
        s = s.replace(a, b)
    s = re.sub(r"^(has_|is_)", "", s)
    if i.lower().startswith("med.class."):
        s = re.sub(r"(ra|i)$", "", s)
    return kind + ":" + s.replace("_", "")


KEYMAP = {}
for v in VOCAB:
    KEYMAP.setdefault(norm_key(v), set()).add(v)
_SIG = {}


def sig(i):
    if i not in _SIG:
        _SIG[i] = LSH.compute_minhash(LSH.compute_shingles(re.sub(r"^(pred\.|med\.)", "", i), k=3), num_hashes=100)
    return _SIG[i]


def jac(a, b):
    sa, sb = sig(a), sig(b)
    return sum(x == y for x, y in zip(sa, sb)) / len(sa)


VOCAB_BY_KIND = {"pred": sorted(VP), "med": sorted(VM)}


def b3_check(ids):
    flags, flags_j, warn = [], [], []
    for i in ids:
        kind = "med" if i.startswith("med.") else "pred"
        if i not in VOCAB:
            km = KEYMAP.get(norm_key(i), set())
            best = max(((jac(i, v), v) for v in VOCAB_BY_KIND[kind]), default=(0, None))
            if km:
                flags.append(f"{i}~key~{sorted(km)[0]}")
            if best[0] >= 0.7:
                flags.append(f"{i}~jac{best[0]:.2f}~{best[1]}")
                flags_j.append(f"{i}~jac{best[0]:.2f}~{best[1]}")
        else:
            km = KEYMAP.get(norm_key(i), set())
            if len(km) > 1:
                warn.append(f"{i}~cluster~{'|'.join(sorted(km))}")
    return flags, flags_j, warn


# ---------- B1 ----------
def b1_check(cond, action, vp, vm):
    f = []
    try:
        ast = parse(cond)
    except ParseError as e:
        return ["parse_error"]
    for p in sorted(set(PRED_RE.findall(cond))):
        if p not in vp:
            f.append(f"undef_pred:{p}")
    subs = action.get("subjects", [])
    if not subs:
        f.append("empty_subjects")
    for s in subs:
        if not isinstance(s, str) or not s.startswith("med."):
            f.append(f"bad_subject:{s}")
        elif s not in vm:
            f.append(f"undef_med:{s}")
    if action.get("permission") not in PERMISSIONS:
        f.append(f"bad_permission:{action.get('permission')}")
    e = to_z3(ast, z3, {})
    s = z3.Solver(); s.add(e)
    if s.check() == z3.unsat:
        f.append("cond_unsat")
    s = z3.Solver(); s.add(z3.Not(e))
    if s.check() == z3.unsat:
        f.append("cond_valid")
    return f


# ---------- B2 ----------
def b2_check(oc, oa, mc, ma):
    f = []
    cache = {}
    try:
        e1 = to_z3(parse(oc), z3, cache); e2 = to_z3(parse(mc), z3, cache)
        s = z3.Solver(); s.add(e1 != e2)
        if s.check() == z3.sat:
            s1 = z3.Solver(); s1.add(z3.And(e2, z3.Not(e1)))
            s2 = z3.Solver(); s2.add(z3.And(e1, z3.Not(e2)))
            wider = s1.check() == z3.sat; narrower = s2.check() == z3.sat
            f.append("cond_not_equiv(" + ("wider" if wider and not narrower else "narrower" if narrower and not wider
                                          else "incomparable") + ")")
    except ParseError:
        f.append("parse_error")
    if set(oa.get("subjects", [])) != set(ma.get("subjects", [])):
        f.append("subjects_diff")
    if oa.get("permission") != ma.get("permission"):
        f.append("permission_diff")
    return f


# ---------- B5 ----------
FW = str.maketrans("０１２３４５６７８９．", "0123456789.")


def id_numbers(p):
    toks = p[5:].split("_"); out = []; i = 0
    while i < len(toks):
        if toks[i].isdigit():
            if i + 1 < len(toks) and toks[i + 1].isdigit() and len(toks[i + 1]) == 1:
                out.append(toks[i] + "." + toks[i + 1]); i += 2; continue
            out.append(toks[i])
        i += 1
    return out


def b5_check(cond, action, quote):
    q = (quote or "").translate(FW)
    ql = q.lower()
    f = []
    preds = sorted(set(PRED_RE.findall(cond)))
    for p in preds:
        for n in id_numbers(p):
            if not re.search(r"(?<![\d.])" + re.escape(n) + r"(?![\d])", q):
                alt = n[:-2] if n.endswith(".0") else None
                if not (alt and re.search(r"(?<![\d.])" + re.escape(alt) + r"(?![\d.])", q)):
                    f.append(f"num_missing:{p}:{n}")
        m = re.search(r"_(lt|le|ge|gt)_", p)
        if m:
            cues = CUE_LT if m.group(1) in ("lt", "le") else CUE_GE
            if not any(c in q for c in cues):
                f.append(f"cmp_cue_missing:{p}")
    for s in action.get("subjects", []):
        if s in LEX and not any(n.lower() in ql for n in LEX[s]):
            f.append(f"drug_missing:{s}")
    if "NOT" in (cond or "") and not any(c in q for c in CUE_NEG):
        f.append("neg_cue_missing")
    return f


def all_ids(cond, action):
    return sorted(set(PRED_RE.findall(cond))) + [s for s in action.get("subjects", []) if isinstance(s, str) and s.startswith("med.")]


def run_item(kind, item_id, op, ridx, oc, oa, mc, ma, quote):
    vp_loo, vm_loo = vocab(rules, exclude_idx=ridx)
    b1 = b1_check(mc, ma, VP, VM)
    b1l = b1_check(mc, ma, vp_loo, vm_loo)
    b2 = b2_check(oc, oa, mc, ma)
    b3, b3j, b3w = b3_check(all_ids(mc, ma))
    b5 = b5_check(mc, ma, quote)
    return {"kind": kind, "item_id": item_id, "op": op, "rule_idx": ridx, "condition": mc,
            "subjects": "|".join(map(str, ma.get("subjects", []))), "permission": ma.get("permission"),
            "B1": ";".join(b1), "B1_LOO": ";".join(b1l), "B2": ";".join(b2), "B3": ";".join(b3),
            "B3_jaccard_only": ";".join(b3j), "B3w": ";".join(b3w), "B5": ";".join(b5)}


def main():
    rows = []
    for i, r in enumerate(rules):
        q = r["provenance"][0].get("quote", "") if r["provenance"] else ""
        rows.append(run_item("orig", r["id"], "ORIG", i, r["condition"], r["action"], r["condition"], r["action"], q))
    muts = [json.loads(l) for l in open(os.path.join(D_ROOT, "mutation_spec", "mutants_v1.jsonl"), encoding="utf-8")]
    for m in muts:
        r = rules[m["rule_idx"]]
        q = r["provenance"][0].get("quote", "") if r["provenance"] else ""
        rows.append(run_item("mutant", m["mutant_id"], m["op"], m["rule_idx"], m["orig_condition"], m["orig_action"],
                             m["mut_condition"], m["mut_action"], q))
    out = os.path.join(D_ROOT, "results_static_flags.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print("wrote", out, len(rows))


if __name__ == "__main__":
    main()
