"""독립 감사(2026-10-27) M2~M6·MINOR 수정 검증 — 가상 세계만(실데이터 미접근; lockhash 는 ~/medmap 코드 파일 SHA 만 읽음)."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

import artifacts  # noqa: E402
import confirm  # noqa: E402
import metrics as mt  # noqa: E402
import run_exp01  # noqa: E402
import synth  # noqa: E402
from core import NEG, POS, UNKNOWN, NoisySimulator, run_case  # noqa: E402
from likelihood import GraphLikelihood  # noqa: E402
from searchers import GraphSearcher  # noqa: E402

SEEDS = (42, 43, 44)


def world(n=40, seed=3):
    sem, classes, prior, table, P = synth.make_world(seed=seed)
    lik = GraphLikelihood(table, sem.answer_space, classes, prior)
    cases = synth.sample_cases(sem, classes, P, n, seed=seed + 1)
    rank = list(np.array(classes)[np.argsort(-prior)])
    return sem, classes, prior, lik, cases, rank


class TestM3TauSelection(unittest.TestCase):
    def base(self):
        return {"PB_REL": {"severe_miss": 0.05},
                0.01: {"top5": 0.90, "severe_miss": 0.05, "wrong_term": 0.01},
                0.001: {"top5": 0.905, "severe_miss": 0.04, "wrong_term": 0.0},
                0.0001: {"top5": 0.80, "severe_miss": 0.04, "wrong_term": 0.0},
                ("PB_REL_virtual", 0.01): {"wrong_term": 0.01}, ("PB_REL_virtual", 0.001): {"wrong_term": 0.0},
                ("PB_REL_virtual", 0.0001): {"wrong_term": 0.0}}

    def test_rule(self):
        r = mt.select_tau(self.base(), [0.01, 0.001, 0.0001])
        self.assertEqual(r["tau"], 0.001)                 # 0.01 은 0.905 와 차 0.005 ≥ 0.001 → 동률 아님
        st = self.base()
        st[0.01]["top5"] = 0.9049                          # 차 < 0.1%p → 동률, 더 작은 τ
        self.assertEqual(mt.select_tau(st, [0.01, 0.001, 0.0001])["tau"], 0.001)
        st[0.01]["top5"] = 0.70                            # 이제 0.0001 이 최고, 0.001 은 차 < 0.1%p 동률이 아님
        st[0.001]["top5"] = 0.79
        st[0.0001]["top5"] = 0.8005
        self.assertEqual(mt.select_tau(st, [0.01, 0.001, 0.0001])["tau"], 0.0001)

    def test_safety_conditions_exclude(self):
        st = self.base()
        st[0.001]["severe_miss"] = 0.06                    # PB_REL 보다 나쁨 → 제외
        st[0.0001]["wrong_term"] = 0.01                    # 가상 판정보다 나쁨 → 제외
        self.assertEqual(mt.select_tau(st, [0.01, 0.001, 0.0001])["tau"], 0.01)

    def test_wrong_term_condition_matters(self):
        st = self.base()
        st[0.0001]["top5"] = 0.99                          # 최고지만 잘못된 분기 종료가 가상 판정보다 나쁨 → 제외돼야 함
        st[0.0001]["wrong_term"] = 0.02
        self.assertEqual(mt.select_tau(st, [0.01, 0.001, 0.0001])["tau"], 0.001)

    def test_tie_prefers_smaller_tau(self):
        st = self.base()
        st[0.0001]["top5"] = 0.9045                        # 0.905 와 차 0.0005 < 0.001 → 동률 → 더 작은 τ
        self.assertEqual(mt.select_tau(st, [0.01, 0.001, 0.0001])["tau"], 0.0001)

    def test_tau_fail(self):
        st = self.base()
        for t in (0.01, 0.001, 0.0001):
            st[t]["severe_miss"] = 0.5
        r = mt.select_tau(st, [0.01, 0.001, 0.0001])
        self.assertEqual((r["tau"], r["status"]), (None, "TAU_FAIL"))


class TestM2M3M4FinalAnalysis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sem, classes, prior, lik, cases, rank = world()
        cls.classes = classes
        cls.severe = frozenset(classes[:2])
        cls.recs_tau = run_exp01.evaluate(cases, sem, lik, classes, [5], [1e-2], SEEDS, wd_rank=lambda c: rank,
                                          leak_check=False)
        cls.recs_fail = run_exp01.evaluate(cases, sem, lik, classes, [5], [None], SEEDS, wd_rank=lambda c: rank,
                                           leak_check=False)

    def test_tau_fail_path_runs_end_to_end(self):           # M3: PC(tau=None) 행이 생기고 분석이 끝까지
        self.assertTrue(any(r["model"] == "PC" and r["tau"] is None for r in self.recs_fail))
        f = confirm.final_analysis(self.recs_fail, self.severe, None, SEEDS, B=200)
        self.assertEqual(f["tau_status"], "TAU_FAIL")
        self.assertEqual(f["components"]["H2b"], {"tau_fail": 1.0})
        self.assertIsNone(f["components"]["H3a"]["wrong_term"])
        self.assertEqual(f["stages"]["PB"]["tau_fail"], True)

    def test_selected_tau_path(self):
        f = confirm.final_analysis(self.recs_tau, self.severe, 1e-2, SEEDS, B=200)
        self.assertEqual(set(f["components"]), {"H1", "H2a", "H2b", "H3a", "H3b", "H3c"})
        self.assertEqual(len(f["components"]["H3b"]), 6)
        self.assertIn(f["prespecified_model"], ("C", "PA", "PB_REL", "PB", "PC"))
        rows = artifacts.comparisons_rows(f)
        self.assertTrue(any(r["hypothesis"] == "H1" and r["component"] == "severe_miss" for r in rows))
        n_comp = sum(len(c) for c in f["components"].values())
        self.assertEqual(sum(1 for r in rows if not r["hypothesis"].startswith("STAGE:") and r["component"] != "label"),
                         n_comp)                                   # 모든 성분 p 가 행으로 남는다

    def test_disease_counts_are_integers_and_rule_uses_counts(self):   # M4
        miss, n = confirm.disease_counts([r for r in self.recs_tau if r["model"] == "C"], self.severe)
        self.assertTrue(all(isinstance(v, int) for v in list(miss.values()) + list(n.values())))
        with self.assertRaises(ValueError):
            mt.disease_rule_fires({"A": 0.05}, {"A": 0.0}, {"A": 100})   # 비율을 넘기면 거부
        fired = confirm.disease_fired_all(self.recs_tau, self.severe, 1e-2, SEEDS)
        self.assertEqual(set(fired), {"PA", "PB_REL", "PB", "PC"})

    def test_disease_rule_fires_detected_in_pipeline(self):
        recs = [dict(r) for r in self.recs_tau]
        d0 = sorted(self.severe)[0]
        rows = [r for r in recs if r["model"] == "PA" and r["truth"] == d0]
        for r in rows:                                     # PA 를 인위적으로 악화
            r["in8"] = False
        crows = [r for r in recs if r["model"] == "C" and r["truth"] == d0]
        for r in crows:
            r["in8"] = True
        n = len(rows)
        fired = confirm.disease_fired_all(recs, self.severe, 1e-2, SEEDS)
        self.assertEqual(fired["PA"], [d0] if n >= 100 else [])


class TestM5Artifacts(unittest.TestCase):
    def test_seven_outputs_and_secondary_metrics(self):
        with tempfile.TemporaryDirectory() as d:
            r = subprocess.run([sys.executable, str(HERE / "run_exp01.py"), "--split", "SYNTHETIC", "--out",
                                str(Path(d) / "o")], capture_output=True, text=True, timeout=300)
            self.assertEqual(r.returncode, 0, r.stderr[-500:])
            o = Path(d) / "o"
            for f in ("split_manifest.json", "metrics.csv", "comparisons.csv", "per_case.parquet", "graph_stats.json",
                      "run_meta.json", "subgroups.csv"):
                self.assertTrue((o / f).exists(), f)
            import pandas as pd
            m = pd.read_csv(o / "metrics.csv")
            for col in ("ece_top1", "brier", "macro_top5", "diff_recall", "neg_direction_rate", "first_top5_step_mean",
                        "counter_median", "prune_rate", "reactivations_mean", "severe_miss", "leak_checked"):
                self.assertIn(col, m.columns)
            self.assertTrue(m["noise"].notna().any())        # 응답 잡음 민감도 행
            pc = pd.read_parquet(o / "per_case.parquet")
            self.assertNotIn("tokens", pc.columns)
            self.assertNotIn("differential", pc.columns)
            sg = pd.read_csv(o / "subgroups.csv")
            self.assertTrue({"age", "sex", "prior_quartile", "severe_disease"} <= set(sg["dimension"]))
            gs = json.loads((o / "graph_stats.json").read_text())
            self.assertIn("wd_mixture", gs)
            self.assertIn("wd_model_vs_graph_initial_top1", gs)

    def test_metric_values_hand_check(self):
        recs = []
        for i, (top5, in8, truth) in enumerate([(True, True, "D0"), (False, False, "D0"), (True, True, "D1"),
                                                (False, True, "D2")]):
            recs.append({k: None for k in artifacts.PER_CASE_COLS} | {
                "row_index": i, "truth": truth, "model": "C", "budget": 5, "top1": False, "top3": top5, "top5": top5,
                "in8": in8, "p_top1": 0.5, "top1_correct": False, "brier": 1.0, "n_questions": 5, "ms": 1.0,
                "counter": 10, "leak": "PASS", "first_top5_step": None, "age": 30, "sex": "M"})
        row = artifacts.metrics_rows(recs, frozenset({"D0"}), ())[0]
        self.assertAlmostEqual(row["top5"], 0.5)
        self.assertEqual(row["severe_n"], 2)
        self.assertAlmostEqual(row["severe_miss"], 0.5)
        self.assertAlmostEqual(row["macro_top5"], (0.5 + 1 + 0) / 3)
        self.assertAlmostEqual(row["first_top5_step_mean"], 6.0)    # 미진입 = Q+1


class TestM6ConfigLock(unittest.TestCase):
    def cfg(self, d, **kw):
        c = {"experiment_id": "EXP-MAI-001", "split": "SELECT", "budgets": [3, 5, 10], "seeds": [42, 43, 44],
             "taus": [0.01, 0.001, 0.0001], "leak_check": True} | kw
        p = Path(d, "cfg.json")
        p.write_text(json.dumps(c))
        return p

    def test_seeds_and_final_tau_required(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(SystemExit):
                run_exp01.load_config(self.cfg(d, seeds=[42]))
            with self.assertRaises(SystemExit):
                run_exp01.load_config(self.cfg(d, split="FINAL"))
            c = run_exp01.load_config(self.cfg(d, split="FINAL", tau_selected="TAU_FAIL"))
            self.assertEqual(c["taus"], [None])
            c = run_exp01.load_config(self.cfg(d, split="FINAL", tau_selected=0.001))
            self.assertEqual(c["taus"], [0.001])

    def test_cli_has_no_free_budget_seed_tau_args(self):
        r = subprocess.run([sys.executable, str(HERE / "run_exp01.py"), "--help"], capture_output=True, text=True)
        for a in ("--budgets", "--seeds", "--tau "):
            self.assertNotIn(a, r.stdout)

    def test_lock_hash_binds_config_bytes(self):
        import lockhash
        with tempfile.TemporaryDirectory() as d:
            p = self.cfg(d)
            h1 = lockhash.run_lock_hash(p, run_exp01.CODE_SCOPE)["lock_sha256"]
            p.write_text(p.read_text().replace("[3, 5, 10]", "[5]"))
            h2 = lockhash.run_lock_hash(p, run_exp01.CODE_SCOPE)["lock_sha256"]
            self.assertNotEqual(h1, h2)
            parts = lockhash.run_lock_hash(p, run_exp01.CODE_SCOPE)["parts"]
            self.assertTrue(any(name.startswith("common/") for name, _ in parts["code"]))   # 범위 = exp/main_ai

    def test_make_final_config_only_from_select(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "tau_selection.json").write_text(json.dumps({"tau": None, "source_split": "SELECT_SMOKE"}))
            with self.assertRaises(SystemExit):
                run_exp01.make_final_config(d, Path(d, "f.json"))
            Path(d, "tau_selection.json").write_text(json.dumps({"tau": 0.001, "source_split": "SELECT"}))
            c = run_exp01.make_final_config(d, Path(d, "f.json"))
            self.assertEqual((c["split"], c["tau_selected"], c["seeds"]), ("FINAL", 0.001, [42, 43, 44]))


class TestMinorFixes(unittest.TestCase):
    def test_holm_rejection_matches_adjusted_p(self):
        for ps in ({"H1": 0.004, "H2a": 0.003, "H2b": 0.5, "H3a": 0.5, "H3b": 0.5, "H3c": 0.5},
                   {"H1": 0.001, "H2a": 0.002, "H2b": 0.003, "H3a": 0.004, "H3b": 0.005, "H3c": 0.024}):
            h = mt.holm(ps)
            for k in h:
                self.assertEqual(h[k]["rejected"], h[k]["p_adj"] < 0.025)

    def test_noise_simulator_deterministic_and_unknown_not_used(self):
        sem, classes, prior, lik, cases, _ = world(n=5)
        c = cases[0]
        a = NoisySimulator(sem, c["tokens"], "uncertain", 1.0, "k")
        q = next(x for x in sem.qids if x != c["initial"])
        self.assertEqual(a.answer(q), UNKNOWN)
        f1 = NoisySimulator(sem, c["tokens"], "flip", 0.5, "k").answer(q)
        f2 = NoisySimulator(sem, c["tokens"], "flip", 0.5, "k").answer(q)
        self.assertEqual(f1, f2)
        s = GraphSearcher(lik, sem, "PA", 5)
        tr, s = run_case(s, sem, c["initial"], c["age"], c["sex"], c["tokens"], 5,
                         sim=NoisySimulator(sem, c["tokens"], "uncertain", 1.0, "k"))
        self.assertTrue(all(a != UNKNOWN for _, a in s.stats()["used"]))

    def test_prune_denominator_and_wd_tracking(self):
        sem, classes, prior, lik, cases, rank = world(n=5)
        c = cases[0]
        s = GraphSearcher(lik, sem, "PC", 5, tau=0.5).reset(c["initial"], wd=classes[-1])
        n_wd = 0
        while s.n_asked < 5:
            q = s.next_question()
            if q is None:
                break
            s.observe(q, POS if q in c["tokens"] else NEG)
            n_wd += 1
        st = s.stats()
        self.assertLessEqual(st["cand_steps"], st["steps"])
        self.assertLessEqual(st["prune_steps"], st["cand_steps"])
        self.assertIsNotNone(s._prev_act)

    def test_static_check_strips_inline_comments(self):
        import checks
        with tempfile.TemporaryDirectory() as d:
            for m in checks.SEARCH_MODULES:
                Path(d, m).write_text((HERE / m).read_text(encoding="utf-8"), encoding="utf-8")
            Path(d, "likelihood.py").write_text(Path(d, "likelihood.py").read_text(encoding="utf-8")
                                                + "\nX = 1  # release_conditions 언급만\n", encoding="utf-8")
            checks.static_check(Path(d))                   # 주석은 통과
            Path(d, "likelihood.py").write_text(Path(d, "likelihood.py").read_text(encoding="utf-8")
                                                + "\nY = 'severity'\n", encoding="utf-8")
            with self.assertRaises(Exception):
                checks.static_check(Path(d))


if __name__ == "__main__":
    unittest.main()


class TestSurvivorKillers(unittest.TestCase):
    """1차 변이 검사에서 살아남은 변이를 잡기 위한 테스트(2026-10-27)."""

    def test_tau_none_produces_pb_and_pc_rows(self):
        sem, classes, prior, lik, cases, rank = world(n=3)
        recs = run_exp01.evaluate(cases, sem, lik, classes, [5], [None], SEEDS, wd_rank=lambda c: rank, leak_check=False)
        self.assertTrue(any(r["model"] == "PB" and r["tau"] is None for r in recs))
        self.assertTrue(any(r["model"] == "PC" and r["tau"] is None for r in recs))

    def test_severe_miss_uses_top8_not_top5(self):
        base = {k: None for k in artifacts.PER_CASE_COLS}
        recs = [base | {"row_index": 0, "truth": "D0", "model": "C", "budget": 5, "top1": False, "top3": False,
                        "top5": False, "in8": True, "p_top1": 0.5, "top1_correct": False, "brier": 1.0,
                        "n_questions": 5, "ms": 1.0, "counter": 1, "leak": "PASS", "age": 30, "sex": "M"}]
        self.assertEqual(artifacts.metrics_rows(recs, frozenset({"D0"}), ())[0]["severe_miss"], 0.0)

    def test_confirm_selects_rows_of_chosen_tau(self):
        sem, classes, prior, lik, cases, rank = world(n=20)
        recs = run_exp01.evaluate(cases, sem, lik, classes, [5], [1e-2, 1e-3], SEEDS, wd_rank=lambda c: rank,
                                  leak_check=False)
        f = confirm.final_analysis(recs, frozenset(classes[:2]), 1e-2, SEEDS, B=100)   # 다른 τ 행이 섞이면 UNPAIRED
        self.assertEqual(f["tau"], 1e-2)

    def test_disease_rule_covers_random_wrong_seeds(self):
        recs = []
        for i in range(120):
            for model, mode, seed in (("PB", None, None), ("PC", "WD_MODEL", 42), ("PC", "WD_MODEL_WRONG", 42),
                                      ("PC", "WD_RANDOM_WRONG", 42), ("PC", "WD_RANDOM_WRONG", 43),
                                      ("PC", "WD_RANDOM_WRONG", 44), ("C", None, None), ("PA", None, None),
                                      ("PB_REL", None, None)):
                bad = (model == "PC" and mode == "WD_RANDOM_WRONG" and seed == 43 and i < 10)
                recs.append({"row_index": i, "truth": "D0", "model": model, "budget": 5, "wd_mode": mode,
                             "seed": seed, "tau": (0.01 if model in ("PB", "PC") else None), "in8": not bad})
        fired = confirm.disease_fired_all(recs, frozenset({"D0"}), 0.01, SEEDS)
        self.assertEqual(fired["PC"], ["D0"])              # seed 43 만 악화돼도 발동
        self.assertEqual(fired["PA"], [])


class TestReauditGate5Fixes(unittest.TestCase):
    """재감사 N1·N2·N3b, 설계 gate5 MAJOR 2, 통계 gate5 MINOR 회귀 테스트."""

    def test_N1_final_analysis_with_default_noise(self):
        sem, classes, prior, lik, cases, rank = world(n=20)
        recs = run_exp01.evaluate(cases, sem, lik, classes, [5], [1e-2], SEEDS, wd_rank=lambda c: rank,
                                  leak_check=False, noise=run_exp01.DEFAULT_CONFIG["noise"])
        self.assertTrue(any(r["noise"] is not None for r in recs))
        f = confirm.final_analysis(recs, frozenset(classes[:2]), 1e-2, SEEDS, B=100)   # 수정 전에는 EXP01_UNPAIRED
        self.assertIn("descriptive", f)
        self.assertIn("p_star_ge_mid", f["descriptive"]["H1:top5"])
        self.assertIn("H2b:efficiency", f["descriptive"])
        with self.assertRaises(RuntimeError):
            confirm.disease_counts([r for r in recs if r["noise"] is not None], frozenset(classes))

    def cfg(self, d, **kw):
        c = {"experiment_id": "EXP-MAI-001", "split": "SELECT", "budgets": [3, 5, 10], "seeds": [42, 43, 44],
             "taus": [0.01, 0.001, 0.0001], "leak_check": True} | kw
        p = Path(d, "cfg.json")
        p.write_text(json.dumps(c))
        return p

    def test_N2_select_final_requirements(self):
        with tempfile.TemporaryDirectory() as d:
            for bad in ({"leak_check": False}, {"budgets": [5]}, {"seeds": [44, 43, 42]}, {"taus": [0.01]}):
                with self.assertRaises(SystemExit, msg=str(bad)):
                    run_exp01.load_config(self.cfg(d, **bad))
            run_exp01.load_config(self.cfg(d))

    def test_N3b_select_tau_handles_missing_severe(self):
        st = {"PB_REL": {"severe_miss": None}, 0.01: {"top5": 0.9, "severe_miss": None, "wrong_term": 0.0},
              ("PB_REL_virtual", 0.01): {"wrong_term": 0.0}}
        self.assertEqual(mt.select_tau(st, [0.01])["tau"], 0.01)

    def test_tie_uses_integer_counts(self):
        st = {"PB_REL": {"severe_miss": 0.1},
              0.01: {"top5": 0.9, "k_top5": 900, "n": 1000, "severe_miss": 0.1, "wrong_term": 0.0},
              0.001: {"top5": 0.899, "k_top5": 899, "n": 1000, "severe_miss": 0.1, "wrong_term": 0.0},
              ("PB_REL_virtual", 0.01): {"wrong_term": 0.0}, ("PB_REL_virtual", 0.001): {"wrong_term": 0.0}}
        self.assertEqual(mt.select_tau(st, [0.01, 0.001])["tau"], 0.01)    # 차 정확히 0.1%p → 동률 아님
        st[0.001]["k_top5"] = 900
        self.assertEqual(mt.select_tau(st, [0.01, 0.001])["tau"], 0.001)

    def test_ece_correctness_is_argmax(self):
        sem, classes, prior, lik, cases, rank = world(n=5)
        recs = run_exp01.evaluate(cases, sem, lik, classes, [5], [1e-2], SEEDS, wd_rank=lambda c: rank,
                                  leak_check=False)
        for r in recs:
            self.assertEqual(r["top1_correct"], r["rank"] == 1 or r["top1_correct"])

    def test_wilson_nonzero_when_no_miss(self):
        w = artifacts._wilson(0, 30)
        self.assertEqual(w["severe_miss_wilson_lo"], 0.0)
        self.assertGreater(w["severe_miss_wilson_hi"], 0.05)

    def test_final_gate_requires_same_code_as_select(self):
        import lockhash
        with tempfile.TemporaryDirectory() as d:
            sel = Path(d, "sel")
            sel.mkdir()
            fcfg = Path(d, "final.json")
            fcfg.write_text(json.dumps({"experiment_id": "EXP-MAI-001", "split": "FINAL", "budgets": [3, 5, 10],
                                        "seeds": [42, 43, 44], "leak_check": True, "tau_selected": 0.001,
                                        "tau_selection_run": str(sel)}))
            h = lockhash.run_lock_hash(fcfg, run_exp01.CODE_SCOPE)
            (sel / "tau_selection.json").write_text(json.dumps({"tau": 0.001, "source_split": "SELECT"}))
            parts = dict(h["parts"])
            parts["code"] = parts["code"][:-1]                     # 코드가 다르다고 가정
            (sel / "run_meta.json").write_text(json.dumps({"split": "SELECT", "run_lock": {"parts": parts}}))
            lock = Path(d, "lock.json")
            lock.write_text(json.dumps({"config_sha256": h["lock_sha256"], "config_path": str(fcfg),
                                       "outputs_root": str(Path(d).resolve())}))
            class A:
                final_lock = str(lock)
                retry_environmental = False
            with self.assertRaises(SystemExit) as cm:
                run_exp01.final_gate(A, str(fcfg), Path(d, "o"), used_marker=Path(d, "FU"), outputs_root=Path(d))
            self.assertIn("EXP01_FINAL_CODE_DIFFERS_FROM_SELECT", str(cm.exception))
            (sel / "tau_selection.json").write_text(json.dumps({"tau": 0.01, "source_split": "SELECT"}))
            with self.assertRaises(SystemExit) as cm:
                run_exp01.final_gate(A, str(fcfg), Path(d, "o"), used_marker=Path(d, "FU"), outputs_root=Path(d))
            self.assertIn("EXP01_FINAL_TAU_MISMATCH", str(cm.exception))


class TestGate6LockCompare(unittest.TestCase):
    def test_final_gate_accepts_same_code_after_json_roundtrip(self):
        """정상 경로: SELECT run_meta(JSON 저장) 와 같은 코드면 통과하고 FinalGuard 를 1회 획득(임시 표시 파일)."""
        import lockhash
        with tempfile.TemporaryDirectory() as d:
            sel = Path(d, "sel")
            sel.mkdir()
            fcfg = Path(d, "final.json")
            fcfg.write_text(json.dumps({"experiment_id": "EXP-MAI-001", "split": "FINAL", "budgets": [3, 5, 10],
                                        "seeds": [42, 43, 44], "leak_check": True, "tau_selected": 0.001,
                                        "tau_selection_run": str(sel)}))
            h = lockhash.run_lock_hash(fcfg, run_exp01.CODE_SCOPE)
            (sel / "tau_selection.json").write_text(json.dumps({"tau": 0.001, "source_split": "SELECT"}))
            (sel / "run_meta.json").write_text(json.dumps({"split": "SELECT", "run_lock": {"parts": h["parts"]}}))
            lock = Path(d, "lock.json")
            lock.write_text(json.dumps({"config_sha256": h["lock_sha256"], "config_path": str(fcfg),
                                       "outputs_root": str(Path(d).resolve())}))
            class A:
                final_lock = str(lock)
                retry_environmental = False
            marker = Path(d, "FINAL_USED")
            out = run_exp01.final_gate(A, str(fcfg), Path(d, "o"), used_marker=marker, outputs_root=Path(d))
            self.assertEqual(out["lock_sha256"], h["lock_sha256"])
            self.assertTrue(marker.exists())
            with self.assertRaises(Exception) as cm:          # 두 번째는 거부(사유까지 확인, gate7 MINOR)
                run_exp01.final_gate(A, str(fcfg), Path(d, "o"), used_marker=marker, outputs_root=Path(d))
            self.assertIn("EXP01_FINAL_ALREADY_USED", str(cm.exception))
            self.assertFalse(Path(run_exp01.HERE, "outputs", "FINAL_USED").exists())
