"""M6 성능 회귀 gate(scripts/perf_gate.py): e2e 결과 → baseline 형식, 비교 규칙(회귀·목표·알려진 미달·경합 거부).

실행: ~/ai_env/bin/python -m unittest tests.test_perf_gate
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import perf_gate as pg


def e2e_summary(tp=420.0, tfv=606.0, prep=5.0, cer=0.0):
    block = lambda: {"T_partial_ms": {"p50": 280.0, "p95": tp, "n": 700}, "T_final_ms": {"p50": 16.0, "p95": 18.0, "n": 12},
                     "T_final_vad_ms": {"p50": 600.0, "p95": tfv, "n": 24}, "T_prep_ms": {"p50": 4.0, "p95": prep, "n": 12},
                     "cer": {"mean": cer, "max": cer}}
    return {"summary": {"ws_warm": block(), "http": block()}}


def doctor_summary(p95=16.4):
    return {"summary": {"warm": {"T_next": {"p50": 15.6, "p95": p95, "max": 17.2, "n": 57}}}}


def metrics(**kw):
    return pg.collect(e2e_summary(**{k: v for k, v in kw.items() if k != "tnext"}), doctor_summary(kw.get("tnext", 16.4)),
                      {"gpu_util_start": 0, "commit_stt": "abc", "commit_doctor": "def"})


class CollectTest(unittest.TestCase):
    def test_baseline_has_targets_and_conditions(self):
        b = metrics()
        m = b["metrics"]
        self.assertEqual(m["stt.ws.T_partial"]["target"], 600)
        self.assertEqual(m["stt.ws.T_final_vad"]["target"], 500)
        self.assertEqual(m["intake.T_prep"]["target"], 300)
        self.assertEqual(m["doctor.T_next_warm"]["target"], 500)
        self.assertEqual(m["stt.ws.T_partial"]["p95"], 420.0)
        self.assertFalse(b["conditions"]["contended"])
        self.assertIn("stt.ws.cer", m)


class CompareTest(unittest.TestCase):
    def test_same_numbers_pass_but_known_target_miss_is_listed(self):
        verdict = pg.compare(metrics(), metrics())
        self.assertEqual(verdict["status"], "PERF_OK")
        self.assertIn("stt.ws.T_final_vad", verdict["known_target_miss"])    # baseline 도 606 > 500 — 목표는 그대로, 따로 표시

    def test_relative_and_absolute_regression(self):
        verdict = pg.compare(metrics(), metrics(tp=560.0))                  # +33 %, +140 ms
        self.assertEqual(verdict["status"], "PERF_REGRESSION")
        self.assertIn("stt.ws.T_partial", verdict["regressions"])

    def test_small_metric_noise_is_not_a_regression(self):
        verdict = pg.compare(metrics(), metrics(prep=9.0, tnext=22.0))      # +80 % 이지만 +4 ms / +5.6 ms
        self.assertEqual(verdict["status"], "PERF_OK")

    def test_new_target_miss_fails_even_within_20_percent(self):
        verdict = pg.compare(metrics(tp=560.0), metrics(tp=610.0))          # +9 % 이지만 600 초과(baseline 은 목표 안)
        self.assertEqual(verdict["status"], "PERF_REGRESSION")
        self.assertIn("stt.ws.T_partial", verdict["target_miss"])

    def test_known_miss_getting_worse_is_a_regression(self):
        verdict = pg.compare(metrics(), metrics(tfv=800.0))
        self.assertEqual(verdict["status"], "PERF_REGRESSION")
        self.assertIn("stt.ws.T_final_vad", verdict["regressions"])

    def test_quality_regression(self):
        verdict = pg.compare(metrics(), metrics(cer=0.03))
        self.assertEqual(verdict["status"], "PERF_REGRESSION")
        self.assertIn("stt.ws.cer", verdict["regressions"])

    def test_contended_measurement_is_refused(self):
        current = metrics()
        current["conditions"] = {**current["conditions"], "gpu_util_start": 65, "contended": True}
        self.assertEqual(pg.compare(metrics(), current)["status"], "INVALID_CONTENDED")

    def test_missing_metric_fails(self):
        current = metrics()
        del current["metrics"]["doctor.T_next_warm"]
        verdict = pg.compare(metrics(), current)
        self.assertEqual(verdict["status"], "PERF_REGRESSION")
        self.assertIn("doctor.T_next_warm", verdict["missing"])


class CliTest(unittest.TestCase):
    def test_exit_codes(self):
        with tempfile.TemporaryDirectory() as d:
            base, same, worse = (Path(d) / n for n in ("b.json", "s.json", "w.json"))
            base.write_text(json.dumps(metrics()))
            same.write_text(json.dumps(metrics()))
            worse.write_text(json.dumps(metrics(tp=700.0)))
            self.assertEqual(pg.main(["compare", "--baseline", str(base), "--current", str(same)]), 0)
            self.assertEqual(pg.main(["compare", "--baseline", str(base), "--current", str(worse)]), 2)


if __name__ == "__main__":
    unittest.main()
