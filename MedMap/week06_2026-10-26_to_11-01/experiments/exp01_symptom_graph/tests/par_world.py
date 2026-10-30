"""병렬화 동일성 검증용 가상 세계(2026-10-28). DDXPlus 환자 행은 읽지 않는다.

toy_world: synth 가상 세계(그래프 계열 + 가상 결정 트리 B). 빠른 단위 테스트용.
ddx_world: DDXPlus 근거 정의(release_evidences.json)·STEP16B 우도표·Baseline A 모델(pkl)을 그대로 쓰고,
           환자는 우도표에서 지어낸다(질환 균등, 근거는 P(a|q,d) 로 표본). 실제 실행과 같은 경로(A·aref·B·WD·누출·잡음).
"""
from __future__ import annotations

import pickle
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import synth  # noqa: E402
from likelihood import GraphLikelihood  # noqa: E402
from searchers import build_b_features, encode_b, fit_baseline_b  # noqa: E402

S16B = "/home/<user>/medmap/exp/step16b_next_information_validation"
NOISE = {"budget": 5, "models": ["C", "PA"],
         "modes": [["flip", 0.05], ["flip", 0.10], ["uncertain", 0.05], ["uncertain", 0.10]]}
TAUS = [0.01, 0.001, 0.0001]
SEEDS = (42, 43, 44)
BUDGETS = [3, 5, 10]


def toy_world(n=40, seed=3, with_tree=True, n_classes=12):
    sem, _, prior, table, P = synth.make_world(n_classes=n_classes, seed=seed)
    classes = [f"D{d:02d}" for d in range(n_classes)]        # 사전순 = 인덱스순(트리 클래스 순서 일치)
    lik = GraphLikelihood(table, sem.answer_space, classes, prior)
    cases = synth.sample_cases(sem, classes, P, n, seed=seed + 1)
    for i, c in enumerate(cases):                          # 평가 전용 필드(차등 진단·새 프로필)도 지어냄
        c["differential"] = [(c["truth"], 0.6), (classes[(classes.index(c["truth"]) + 1) % len(classes)], 0.4)]
        c["novel"] = bool(i % 3 == 0)
    rank = list(np.array(classes)[np.argsort(-prior)])
    tree = None
    if with_tree:
        tr_cases = synth.sample_cases(sem, classes, P, 600, seed=seed + 7)
        names, ev_index = build_b_features(sem)
        X = np.stack([encode_b(names, set(x["tokens"]), x["age"], x["sex"]) for x in tr_cases])
        t = fit_baseline_b(X, [x["truth"] for x in tr_cases], classes, seed=42, min_samples_leaf=5)
        tree = (t, names, ev_index)
    kw = dict(sem=sem, lik=lik, classes=classes, budgets=BUDGETS, taus=TAUS, seeds=SEEDS, tree=tree,
              wd_rank=lambda c: rank, leak_check=True, noise=NOISE)
    return cases, kw, frozenset(classes[:4]), prior


def _fabricate(sem, lik, rng, d, i, classes):
    top_bin = [q for q in lik.binary if q not in sem.parent and sem.safe.get(q, True)]
    pos = {q for q in top_bin if rng.random() < lik.p_pos[q][d]}
    if not pos:
        pos = {max(top_bin, key=lambda q: lik.p_pos[q][d])}
    for q in lik.binary:                                   # 자식 이진: 부모 양성일 때만
        par = sem.parent.get(q)
        if par in pos and rng.random() < lik.p_pos[q][d]:
            pos.add(q)
    toks = sorted(pos, key=lambda e: int(e[2:]))
    for q in sem.qids:                                     # 범주형: 부모 없음 또는 부모 양성이면 값 1개(우도표 비율)
        if sem.dtype[q] == "B":
            continue
        par = sem.parent.get(q)
        if par is not None and par not in pos:
            continue
        vals = [a for a in sem.answer_space[q] if a.startswith("VALUE::")]
        if q in lik.table:
            w = np.array([lik.table[q][d, lik.col[q][a]] for a in vals])
            v = vals[int(rng.choice(len(vals), p=w / w.sum()))]
        else:
            v = vals[0]
        toks.append(f"{q}_@_{v.split('::', 1)[1]}")
    init_opts = sorted((q for q in pos if q in top_bin), key=lambda e: int(e[2:]))
    init = init_opts[int(rng.integers(len(init_opts)))]
    other = classes[(d + 1 + int(rng.integers(len(classes) - 1))) % len(classes)]
    return {"row_index": 10_000_000 + i, "age": int(rng.integers(1, 90)), "sex": "M" if rng.random() < .5 else "F",
            "initial": init, "tokens": tuple(toks), "truth": classes[d],
            "differential": [(classes[d], 0.5), (other, 0.3), ("NOT_A_CLASS", 0.2)], "novel": bool(rng.random() < .3)}


def ddx_world(n=60, seed=20261028, n_tree=3000, prior_uniform=True):
    """반환: cases, evaluate 인자(kw), 가상 중증 집합, prior. ~/medmap 엔진·STEP16B 모델 읽기 전용."""
    for p in ("/home/<user>/medmap", S16B):
        if p not in sys.path:
            sys.path.insert(0, p)
    import s16b_core as c
    from aref import AReference
    from medmap.diagnosis import DiagnosisEngine
    from medmap.evidence import EvidenceCatalog
    from medmap.next_information import NextInformationEngine
    from medmap.patient_state import PatientState
    sem = c.Semantics()
    z = np.load(f"{S16B}/ig_table_step16b_train.npz", allow_pickle=True)
    classes = [str(x) for x in z["__classes__"]]
    prior = np.full(len(classes), 1.0 / len(classes))
    lik = GraphLikelihood.from_npz(f"{S16B}/ig_table_step16b_train.npz", sem.answer_space, prior)
    rng = np.random.default_rng(seed)
    cases = [_fabricate(sem, lik, rng, int(rng.integers(len(classes))), i, classes) for i in range(n)]
    trng = np.random.default_rng(seed + 1)
    tr = [_fabricate(sem, lik, trng, i % len(classes), i, classes) for i in range(n_tree)]
    names, ev_index = build_b_features(sem)
    X = np.stack([encode_b(names, {t.partition("_@_")[0] for t in x["tokens"]}, x["age"], x["sex"]).astype(np.uint8)
                  for x in tr])
    tree = fit_baseline_b(X, np.array([x["truth"] for x in tr]), classes, seed=42)
    cat = EvidenceCatalog()
    engines = {k: DiagnosisEngine(cat, k) for k in ("k3", "k5", "k10")}

    def a_factory(ctx, max_q):
        return NextInformationEngine(engines[ctx], cat, max_questions=max_q)

    def wd_rank(case):
        st = PatientState.new(age=case["age"], sex=case["sex"], initial_evidence=case["initial"])
        return [c_ for c_, _ in engines["k3"].diagnose(st).ranking]
    models = {k: pickle.load(open(f"{S16B}/model_k{k}.pkl", "rb")) for k in (3, 5, 10)}
    aref = AReference(c, sem, models, {k: z[k] for k in z.files if k != "__classes__"}, classes)
    kw = dict(sem=sem, lik=lik, classes=classes, budgets=BUDGETS, taus=TAUS, seeds=SEEDS, tree=(tree, names, ev_index),
              a_factory=a_factory, wd_rank=wd_rank, leak_check=True, aref=aref, noise=NOISE)
    return cases, kw, frozenset(sorted(classes)[:17]), prior
