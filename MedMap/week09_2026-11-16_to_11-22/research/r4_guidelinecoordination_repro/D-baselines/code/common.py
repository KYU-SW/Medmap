# -*- coding: utf-8 -*-
"""공통 유틸: 조건 토큰화/파싱(원자 추상화 Z3), 어휘."""
import json
import os
import re

D_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(D_ROOT, "src_copy", "rules_gold.json")
PRED_RE = re.compile(r"pred\.[A-Za-z0-9_]+")
TOK_RE = re.compile(r"pred\.[A-Za-z0-9_]+|\(|\)|AND\b|OR\b|NOT\b|\S+")

PERMISSIONS = {"allow", "recommend", "require", "caution", "avoid", "contraindicate", "continue", "stop",
               "consider", "reduce_dose", "increase_dose", "start_low_dose", "max_dose_limit", "titrate"}


def load_rules():
    with open(RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


def tokenize(cond):
    return TOK_RE.findall(cond or "")


def detok(toks):
    s = " ".join(toks)
    return s.replace("( ", "(").replace(" )", ")")


class ParseError(Exception):
    pass


def parse(cond):
    """NOT > AND > OR. 반환: 중첩 튜플 AST ('atom',id)|('not',x)|('and',[..])|('or',[..])"""
    toks = tokenize(cond)
    pos = [0]

    def peek():
        return toks[pos[0]] if pos[0] < len(toks) else None

    def eat(t=None):
        tok = peek()
        if tok is None or (t is not None and tok != t):
            raise ParseError(f"expected {t} got {tok} in {cond!r}")
        pos[0] += 1
        return tok

    def p_or():
        xs = [p_and()]
        while peek() == "OR":
            eat("OR"); xs.append(p_and())
        return xs[0] if len(xs) == 1 else ("or", xs)

    def p_and():
        xs = [p_not()]
        while peek() == "AND":
            eat("AND"); xs.append(p_not())
        return xs[0] if len(xs) == 1 else ("and", xs)

    def p_not():
        if peek() == "NOT":
            eat("NOT"); return ("not", p_not())
        return p_atom()

    def p_atom():
        t = peek()
        if t == "(":
            eat("("); x = p_or(); eat(")"); return x
        if t is not None and PRED_RE.fullmatch(t):
            eat(); return ("atom", t)
        raise ParseError(f"bad token {t!r} in {cond!r}")

    if not toks:
        raise ParseError("empty condition")
    ast = p_or()
    if pos[0] != len(toks):
        raise ParseError(f"trailing tokens in {cond!r}")
    return ast


def to_z3(ast, z3, cache):
    k = ast[0]
    if k == "atom":
        if ast[1] not in cache:
            cache[ast[1]] = z3.Bool(ast[1])
        return cache[ast[1]]
    if k == "not":
        return z3.Not(to_z3(ast[1], z3, cache))
    xs = [to_z3(a, z3, cache) for a in ast[1]]
    return z3.And(*xs) if k == "and" else z3.Or(*xs)


def vocab(rules, exclude_idx=None):
    preds, meds = set(), set()
    for i, r in enumerate(rules):
        if i == exclude_idx:
            continue
        preds.update(PRED_RE.findall(r.get("condition") or ""))
        for s in r["action"].get("subjects", []):
            if isinstance(s, str) and s.startswith("med."):
                meds.add(s)
    return preds, meds
