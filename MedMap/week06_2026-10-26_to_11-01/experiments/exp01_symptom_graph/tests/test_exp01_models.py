"""EXP-01 탐색기·검사·지표·확인적 판정 단위 테스트 — 가상 세계만 사용(실데이터 미접근).
실행: ~/ai_env/bin/python -m unittest discover -s exp/main_ai/exp01_symptom_graph/tests -v (worktree 루트)
"""
import math
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import checks  # noqa: E402
import confirm  # noqa: E402
import metrics as mt  # noqa: E402
import synth  # noqa: E402
from core import NEG, POS, Exp01Invalid, guard_inputs, run_case  # noqa: E402
from likelihood import GraphLikelihood  # noqa: E402
from searchers import (GraphSearcher, TreeSearcher, build_b_features, encode_b, expected_used,  # noqa: E402
                       fit_baseline_b)

CHILD = {"E_10": "E_0", "E_11": "E_0"}


def world(child=CHILD, seed=0):
    sem, classes, prior, table, P = synth.make_world(seed=seed, child_of=child)
    lik = GraphLikelihood(table, sem.answer_space, classes, prior)
    cases = synth.sample_cases(sem, classes, P, 60, seed=seed + 1, child_of=child)
    return sem, classes, prior, lik, cases, P


class TestLikelihood(unittest.TestCase):
    def test_relation_definition(self):
        sem, classes, prior, lik, _, _ = world()
        for q in lik.binary:
            marg = float(prior @ lik.p_pos[q])
            np.testing.assert_array_equal(lik.suggests[q], lik.p_pos[q] > marg)
        rc = lik.relation_counts()
        self.assertEqual(rc["SUGGESTS"] + rc["ARGUES_AGAINST"], len(lik.binary) * len(classes))

    def test_bad_prior_rejected(self):
        sem, classes, prior, table, _ = synth.make_world()
        with self.assertRaises(ValueError):
            GraphLikelihood(table, sem.answer_space, classes, np.ones(len(classes)))


class TestGraphSearchers(unittest.TestCase):
    def setUp(self):
        self.sem, self.classes, self.prior, self.lik, self.cases, _ = world()

    def go(self, variant, case, Q=5, tau=None, wd=None):
        return run_case(GraphSearcher(self.lik, self.sem, variant, Q, tau), self.sem, case["initial"], case["age"],
                        case["sex"], case["tokens"], Q, wd)

    def test_budget_no_duplicate_eligibility(self):
        for v in ("C", "PA", "PB_REL"):
            for c in self.cases:
                tr, s = self.go(v, c, Q=5)
                self.assertLessEqual(len(tr.asked), 5)
                self.assertEqual(len(set(tr.asked)), len(tr.asked))
                for q in tr.asked:                       # 자식은 부모 POS 뒤에만
                    if q in CHILD:
                        self.assertEqual(tr.answers.get(CHILD[q], s.stats()["observed"].get(CHILD[q])), POS)

    def test_c_ignores_negative_pa_uses_it(self):
        for c in self.cases:
            _, sc = self.go("C", c)
            _, spa = self.go("PA", c)
            self.assertTrue(all(a != NEG for _, a in sc.stats()["used"]))
            obs = spa.stats()["observed"]
            if any(a == NEG for a in obs.values()):
                self.assertTrue(any(a == NEG for _, a in spa.stats()["used"]))
            checks.check_evidence_set(sc)
            checks.check_evidence_set(spa)
            checks.check_reference(sc, self.lik)
            checks.check_reference(spa, self.lik)

    def test_c_and_pa_same_question_rule(self):
        # 첫 질문은 관측이 같으면(초기 근거만) 같아야 한다 — 변수 1개(음성)만 다름
        for c in self.cases:
            a = GraphSearcher(self.lik, self.sem, "C", 5).reset(c["initial"]).next_question()
            b = GraphSearcher(self.lik, self.sem, "PA", 5).reset(c["initial"]).next_question()
            self.assertEqual(a, b)

    def test_pb_never_drops_disease_from_ranking(self):
        for c in self.cases:
            _, s = self.go("PB", c, tau=1e-2)
            self.assertEqual(len(s.scores()), len(self.classes))
            self.assertTrue(np.all(np.isfinite(s.scores())))

    def test_pb_large_tau_reduces_candidates_and_counter(self):
        s1 = GraphSearcher(self.lik, self.sem, "PB_REL", 5).reset(self.cases[0]["initial"])
        s2 = GraphSearcher(self.lik, self.sem, "PB", 5, tau=0.99).reset(self.cases[0]["initial"])
        s1.next_question(); s2.next_question()
        self.assertLessEqual(s2.counter, s1.counter)
        self.assertLessEqual(len(s2.active()), len(self.classes))

    def test_reactivation_counted(self):
        s = GraphSearcher(self.lik, self.sem, "PB", 10, tau=0.5).reset(self.cases[0]["initial"])
        s._prev_act = set()                                # 직전 활성 집합 비움 → 다음 계산에서 재활성으로 셈
        s.next_question()
        self.assertGreater(s.reactivations, 0)

    def test_counter_closed_formula(self):
        s = GraphSearcher(self.lik, self.sem, "PB_REL", 5).reset(self.cases[0]["initial"])
        before = s.counter
        self.assertEqual(before, len(self.classes))        # 초기 근거 1개 갱신
        elig = s._eligible()
        cand = s._order()[:8]
        s.next_question()
        self.assertEqual(s.counter - before, len(cand) * len(elig) * 2)

    def test_pc_wd_questions_first_and_ranking_untouched(self):
        c = self.cases[0]
        wd = self.classes[-1]
        s = GraphSearcher(self.lik, self.sem, "PC", 5, tau=1e-3).reset(c["initial"], wd=wd)
        q = s.next_question()
        w = self.classes.index(wd)
        elig = s._eligible()
        opts = [x for x in elig if self.lik.suggests[x][w]]
        if opts:
            best = min(opts, key=lambda x: (-round(float(self.lik.p_pos[x][w]), 12), int(x[2:])))
            self.assertEqual(q, best)
        np.testing.assert_allclose(s.scores(), checks.reference_logpost(self.lik, s.stats()["observed"], True))

    def test_pc_requires_wd(self):
        with self.assertRaises(ValueError):
            GraphSearcher(self.lik, self.sem, "PC", 5, tau=1e-3).reset(self.cases[0]["initial"])

    def test_forbidden_inputs_rejected(self):
        for k in ("PATHOLOGY", "EVIDENCES", "DIFFERENTIAL_DIAGNOSIS", "severity"):
            with self.assertRaises(Exp01Invalid):
                GraphSearcher(self.lik, self.sem, "PA", 5).reset("E_0", **{k: "x"})
        guard_inputs({"age": 1})


class TestChecksCatchBugs(unittest.TestCase):
    """검사기가 고의 오류를 잡는지(변이)."""

    def setUp(self):
        self.sem, self.classes, self.prior, self.lik, self.cases, _ = world()

    def test_unrecorded_as_negative_is_caught(self):
        class ClosedWorld(GraphSearcher):        # 미기록 근거를 NEG 로 더하는 오류
            def next_question(self):
                q = super().next_question()
                for e in self.lik.binary:
                    if e not in self.observed:
                        self.logpost = self.logpost + self.lik.loglik(e, NEG)
                        self.used.add((e, NEG))
                        break
                return q
        c = self.cases[0]
        tr, s = run_case(ClosedWorld(self.lik, self.sem, "PA", 5), self.sem, c["initial"], c["age"], c["sex"],
                         c["tokens"], 5)
        with self.assertRaises(Exp01Invalid):
            checks.check_evidence_set(s)

    def test_silent_score_bug_caught_by_reference(self):
        class Silent(GraphSearcher):            # used 기록 없이 점수만 오염(자기보고 의존 검사 회피형)
            def observe(self, q, ans):
                super().observe(q, ans)
                self.logpost = self.logpost + 1e-3 * np.arange(self.lik.n)
        c = self.cases[0]
        _, s = run_case(Silent(self.lik, self.sem, "PA", 5), self.sem, c["initial"], c["age"], c["sex"], c["tokens"], 5)
        checks.check_evidence_set(s)            # 자기보고 검사는 통과하지만
        with self.assertRaises(Exp01Invalid):
            checks.check_reference(s, self.lik)  # 독립 참조 점수기가 잡는다

    def test_hidden_leak_caught(self):
        holder = {}
        class Leaky(GraphSearcher):
            def reset(self, *a, **k):
                super().reset(*a, **k)
                self.logpost = self.logpost + 0.01 * len(holder["tokens"])   # 숨은 기록 길이를 엿봄
                return self
        c = self.cases[0]
        holder["tokens"] = c["tokens"]
        def make():
            return Leaky(self.lik, self.sem, "PA", 3)
        orig = checks.run_case
        def patched(searcher, sem, init, age, sex, toks, budget, wd=None, on_step=None):
            holder["tokens"] = toks
            return orig(searcher, sem, init, age, sex, toks, budget, wd, on_step)
        checks.run_case = patched
        try:
            with self.assertRaises(Exp01Invalid):
                checks.check_hidden_leak(make, self.sem, c, 3, "k")
            honest = checks.check_hidden_leak(lambda: GraphSearcher(self.lik, self.sem, "PA", 3), self.sem, c, 3, "k")
            self.assertIn(honest, (True, None))
        finally:
            checks.run_case = orig

    def test_static_check(self):
        checks.static_check(HERE)
        with tempfile.TemporaryDirectory() as d:
            for m in checks.SEARCH_MODULES:
                Path(d, m).write_text((HERE / m).read_text(encoding="utf-8"), encoding="utf-8")
            Path(d, "searchers.py").write_text(Path(d, "searchers.py").read_text(encoding="utf-8")
                                               + "\nX = 'release_conditions.json'\n", encoding="utf-8")
            with self.assertRaises(Exp01Invalid):
                checks.static_check(Path(d))
            Path(d, "searchers.py").write_text((HERE / "searchers.py").read_text(encoding="utf-8")
                                               + "\nimport metrics\n", encoding="utf-8")   # 금지 문자열 없이 import 만으로 걸리는지
            with self.assertRaises(Exp01Invalid):
                checks.static_check(Path(d))


class TestTree(unittest.TestCase):
    def test_tree_budget_and_free_demographics(self):
        sem, classes, prior, lik, cases, P = world(child=None)
        names, ev = build_b_features(sem)
        train = synth.sample_cases(sem, classes, P, 600, seed=7)
        X = np.stack([encode_b(names, set(c["tokens"]), c["age"], c["sex"]) for c in train])
        y = [c["truth"] for c in train]
        t = fit_baseline_b(X, y, classes, seed=42, max_depth=6, min_samples_leaf=5)
        for c in cases:
            for Q in (1, 3):
                tr, s = run_case(TreeSearcher(t, names, ev, len(classes), Q), sem, c["initial"], c["age"], c["sex"],
                                 c["tokens"], Q)
                self.assertLessEqual(len(tr.asked), Q)
                self.assertTrue(all(q.startswith("E_") for q in tr.asked))
                checks.check_evidence_set(s)
                self.assertEqual(len(s.scores()), len(classes))

    def test_encoding_unrecorded_zero(self):
        sem, *_ = world(child=None)
        names, _ = build_b_features(sem)
        x = encode_b(names, {"E_1"}, 33, "F")
        self.assertEqual(x[names.index("EV::E_1")], 1)
        self.assertEqual(x[names.index("EV::E_2")], 0)


class TestMetrics(unittest.TestCase):
    def test_pessimistic_rank(self):
        self.assertEqual(mt.truth_rank_pessimistic([3, 3, 3, 1], 0), 3)
        self.assertEqual(mt.truth_rank_pessimistic([5, 3, 3, 1], 1), 3)
        self.assertEqual(mt.truth_rank_pessimistic([5, 4, 3, 1], 1), 2)

    def test_wrong_termination(self):
        lp = np.log([0.5, 0.4, 0.001])
        self.assertTrue(mt.wrong_termination(lp, 2, 1e-2))
        self.assertFalse(mt.wrong_termination(lp, 1, 1e-2))
        self.assertIsNone(mt.wrong_termination(lp, 2, None))

    def test_one_sided_p(self):
        d = np.array([-0.01, 0.0, 0.002, 0.006, 0.01])
        self.assertAlmostEqual(mt.p_one_sided(d, 0.0, "better"), (2 + 1) / 6)
        self.assertAlmostEqual(mt.p_one_sided(d, 0.005, "notworse"), (2 + 1) / 6)

    def test_composite_and_na(self):
        self.assertEqual(mt.composite_p({"a": 0.01, "b": 0.03}), 0.03)
        self.assertEqual(mt.composite_p({"a": 0.01, "b": None}), 0.01)
        self.assertEqual(mt.composite_p({"a": None}), 1.0)

    def test_holm_monotone_and_ties(self):
        h = mt.holm({"H1": 0.001, "H2a": 0.004, "H2b": 0.004, "H3a": 0.03, "H3b": 0.002, "H3c": 0.02})
        adj = [h[k]["p_adj"] for k in sorted(h, key=lambda k: h[k]["rank"])]
        self.assertEqual(adj, sorted(adj))
        self.assertEqual(h["H2a"]["alpha_star"], h["H2b"]["alpha_star"])          # 동률은 작은 순위 공유
        self.assertAlmostEqual(h["H1"]["alpha_star"], 0.025 / 6)
        self.assertFalse(h["H3a"]["rejected"])
        self.assertTrue(h["H1"]["rejected"])
        h2 = mt.holm({"H1": 0.01, "H2a": 0.001, "H2b": 0.5, "H3a": 0.5, "H3b": 0.5, "H3c": 0.5})
        self.assertFalse(h2["H1"]["rejected"])                                      # 단계 하강 정지

    def test_mid_integer(self):
        self.assertTrue(mt.mid_met(110, 100, 1000))     # Δ=0.010
        self.assertFalse(mt.mid_met(109, 100, 1000))    # Δ=0.009
        self.assertTrue(mt.mid_met(1001, 0, 100100))

    def test_disease_rule_integer(self):
        n = {"A": 100, "B": 99, "C": 200}
        self.assertEqual(mt.disease_rule_fires({"A": 3, "B": 9, "C": 4}, {"A": 0, "B": 0, "C": 0}, n), ["A"])
        self.assertEqual(mt.disease_rule_fires({"A": 2, "B": 0, "C": 4}, {"A": 0, "B": 0, "C": 0}, n), [])

    def test_h1_label_table_covers_all(self):
        seen = set()
        for inv in (True, False):
            for sp in (0.001, 0.5):
                for fired in ([], ["X"]):
                    for padj in (0.01, 0.2):
                        for mid in (True, False):
                            seen.add(mt.label_h1(inv, sp, 0.005, fired, padj, mid))
        self.assertEqual(seen, set(mt.H1_LABELS))
        self.assertEqual(mt.label_h1(False, 0.5, 0.005, [], 0.001, True), "SAFETY_FAIL")   # 안전 우선, 상쇄 불가

    def test_stage_labels_and_chain(self):
        ok = mt.label_stage(False, True, False, [0.001], 0.005, [], [0.001], [], True)
        self.assertEqual(ok["label"], "ADOPTED")
        ne = mt.label_stage(False, False, False, [0.5], 0.005, [], [], [], False)
        self.assertEqual((ne["label"], ne["safety_state"], ne["conditional_label"]), ("NOT_ELIGIBLE", "SAFETY_FAIL", "SAFETY_FAIL"))
        tf = mt.label_stage(False, True, True, [None], 0.005, [], [], [], False)
        self.assertEqual((tf["label"], tf["tau_fail"]), ("TAU_FAIL", True))
        self.assertEqual(mt.chain("SUCCESS", {"PB_REL": "ADOPTED", "PB": "TAU_FAIL", "PC": "ADOPTED"}), "PB_REL")
        self.assertEqual(mt.chain("SIGNIFICANT_BELOW_MID", {"PB_REL": "ADOPTED"}), "C")


class TestConfirmEndToEnd(unittest.TestCase):
    def test_pipeline_on_synthetic(self):
        import run_exp01
        sem, classes, prior, lik, cases, _ = world(child=None)
        rank = list(np.array(classes)[np.argsort(-prior)])
        recs = run_exp01.evaluate(cases[:30], sem, lik, classes, [5], [1e-2], seeds=(42, 43, 44),
                                  wd_rank=lambda c: rank, leak_check=True)
        self.assertTrue(all(r["leak"] in ("PASS", "NA") for r in recs))
        comps, eff = confirm.component_ps(recs, frozenset(classes[:2]), 1e-2, (42, 43, 44), B=200)
        self.assertEqual(set(comps), {"H1", "H2a", "H2b", "H3a", "H3b", "H3c"})
        self.assertEqual(len(comps["H3b"]), 6)
        out = confirm.judge(comps, eff, {})
        self.assertIn(out["H1"], mt.H1_LABELS)
        self.assertIn(out["prespecified_model"], ("C", "PA", "PB_REL", "PB", "PC"))
        for st, v in out["stages"].items():   # Holm 기각된 단계에는 성분 실패 라벨이 붙지 않는다
            if all(out["holm"][h]["rejected"] for h in {"PB_REL": ["H2a"], "PB": ["H2b"], "PC": ["H3a", "H3b", "H3c"]}[st]):
                self.assertNotIn(v["label"], ("SAFETY_FAIL", "NI_NOT_SHOWN", "EFFICIENCY_NOT_SHOWN", "HOLM_NOT_REJECTED"))
        comps_tf, _ = confirm.component_ps(recs, frozenset(classes[:2]), None, (42, 43, 44), B=50) \
            if any(r["model"] == "PC" and r["tau"] is None for r in recs) else (None, None)
        self.assertIsNone(comps_tf)   # τ 격자 실행에서는 TAU_FAIL 경로 기록이 없으므로 호출하지 않음

    def test_tau_fail_components_na(self):
        sem, classes, prior, lik, cases, _ = world(child=None)
        import run_exp01
        rank = list(np.array(classes)[np.argsort(-prior)])
        recs = run_exp01.evaluate(cases[:10], sem, lik, classes, [5], [None], seeds=(42,),
                                  wd_rank=lambda c: rank, leak_check=False)
        recs = [dict(r, model="PB_REL") if r["model"] == "PB" else r for r in recs if r["model"] != "PB"]
        comps, eff = confirm.component_ps(recs, frozenset(classes[:2]), None, (42,), B=50)
        self.assertEqual(comps["H2b"], {"tau_fail": 1.0})
        self.assertIsNone(comps["H3a"]["wrong_term"])
        self.assertIsNone(comps["H3c"]["wrong_term"])
        self.assertEqual(mt.composite_p(comps["H3a"]), comps["H3a"]["severe_miss"])


class TestRunnerAuthorization(unittest.TestCase):
    def test_real_split_refused_without_approval(self):
        import subprocess
        import json as _json
        with tempfile.TemporaryDirectory() as d:
            cfg = Path(d, "cfg.json")
            cfg.write_text(_json.dumps({"experiment_id": "EXP-MAI-001", "split": "SELECT_SMOKE", "budgets": [3, 5, 10],
                                        "seeds": [42, 43, 44], "taus": [0.01, 0.001, 0.0001]}))
            r = subprocess.run([sys.executable, str(HERE / "run_exp01.py"), "--config", str(cfg),
                                "--out", str(Path(d) / "o")], capture_output=True, text=True)
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("EXP01_NOT_AUTHORIZED", r.stderr + r.stdout)
            self.assertFalse((Path(d) / "o").exists())


if __name__ == "__main__":
    unittest.main()


class TestRepro(unittest.TestCase):
    def test_repro_check_and_no_truth_columns(self):
        import csv as _csv
        import repro
        with tempfile.TemporaryDirectory() as d:
            p = Path(d, "pred.csv")
            with open(p, "w", newline="", encoding="utf-8") as fh:
                w = _csv.writer(fh)
                w.writerow(["config", "row_index", "truth", "top1", "top2", "p_top1", "truth_rank", "wrong", "n_visible"])
                w.writerow(["k3_s42", 7, "SECRET", "D1", "D2", 0.5, 1, False, 2])
                w.writerow(["k3_s43", 7, "SECRET", "D9", "D2", 0.9, 1, False, 2])
                w.writerow(["k3_s42", 8, "SECRET", "D2", "D1", 0.25, 1, False, 2])
            ref = repro.load_reference({7}, ks=(3,), path=str(p))
            self.assertEqual(ref, {(3, 7): ("D1", 0.5)})
            self.assertNotIn("SECRET", repr(ref))
            cases = [{"row_index": 7}]
            self.assertEqual(repro.check(lambda k, c: ("D1", 0.5), cases, ref, ks=(3,))["mismatch"], 0)
            with self.assertRaises(Exp01Invalid):
                repro.check(lambda k, c: ("D2", 0.5), cases, ref, ks=(3,))
            with self.assertRaises(Exp01Invalid):
                repro.check(lambda k, c: ("D1", 0.51), cases, ref, ks=(3,))
