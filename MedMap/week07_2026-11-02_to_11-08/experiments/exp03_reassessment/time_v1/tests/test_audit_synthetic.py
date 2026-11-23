"""run_time_policy_audit 가상 parquet 테스트(지어낸 행 — 실제 MIMIC 없음). 실제 자료 실행 없음."""
from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import run_time_policy_audit as R  # noqa: E402
import time_policy as TP  # noqa: E402

POS = "FINDINGS: Filling defects in the right lower lobe segmental arteries.\nIMPRESSION: Acute pulmonary embolism."
T0 = pd.Timestamp("2150-01-01 10:00")


def ts(h):
    return T0 + pd.Timedelta(hours=h)


def fixture(d: Path):
    co = pd.DataFrame([{"subject_id": 1, "hadm_id": None, "stay_id": 11, "intime": ts(0), "outtime": ts(8), "gender": "F",
                        "cohort_diseases": "", "temperature": 98.6, "heartrate": 120, "resprate": 18, "o2sat": 97, "sbp": 120,
                        "dbp": 70, "pain": 3, "acuity": 2, "chiefcomplaint": "SOB"},
                       {"subject_id": 2, "hadm_id": None, "stay_id": 22, "intime": ts(0), "outtime": ts(4), "gender": "M",
                        "cohort_diseases": "", "temperature": None, "heartrate": None, "resprate": None, "o2sat": None, "sbp": None,
                        "dbp": None, "pain": None, "acuity": None, "chiefcomplaint": None}])
    labs = pd.DataFrame([{"labevent_id": 1, "subject_id": 1, "hadm_id": None, "specimen_id": 1, "itemid": 51003, "charttime": ts(1),
                          "storetime": ts(2), "value": None, "valuenum": None, "valueuom": "ng/mL", "ref_range_lower": None,
                          "ref_range_upper": 0.01, "flag": None, "priority": "STAT", "comments": "<0.01.  cTropnT > 0.10 ng/mL"},
                         {"labevent_id": 2, "subject_id": 1, "hadm_id": None, "specimen_id": 2, "itemid": 50915, "charttime": ts(1),
                          "storetime": None, "value": "900", "valuenum": 900.0, "valueuom": "ng/mL", "ref_range_lower": None,
                          "ref_range_upper": 500.0, "flag": "abnormal", "priority": "STAT", "comments": None}])
    rad = pd.DataFrame([{"note_id": "n1", "subject_id": 1, "charttime": ts(2), "storetime": ts(3), "text": POS,
                         "exam_name": "CTA CHEST W&W/O C&RECONS, NON-CORONARY"},
                        {"note_id": "n2", "subject_id": 2, "charttime": ts(3), "storetime": ts(6), "text": POS, "exam_name": "CTA CHEST"},
                        {"note_id": "n3", "subject_id": 1, "charttime": ts(4), "storetime": ts(3.5), "text": POS, "exam_name": "CTA CHEST"}])
    ecg = pd.DataFrame([{"study_id": 7, "ed_stay_id": 11, "ecg_time_ext": ts(-2)}])
    d.mkdir(parents=True)
    co.to_parquet(d / "cohort.parquet")
    labs.to_parquet(d / "labs.parquet")
    rad.to_parquet(d / "radiology.parquet")
    ecg.to_parquet(d / "ecg.parquet")


class AuditSynthetic(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        fixture(self.tmp / "src")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_run_counts_and_safety(self):
        res = R.run(self.tmp / "src", self.tmp / "out")
        self.assertFalse(any(res["stop_conditions"].values()), res["stop_conditions"])
        ra = res["record_audit_STRICT"]
        self.assertEqual(ra["flag:TIME_CONFLICT"], "<10")                      # n3 역전
        self.assertEqual(ra["flag:NOT_IDENTIFIABLE"], "<10")                   # ECG
        st = res["states"]["STRICT_AVAILABLE_TIME"]
        self.assertIn("SUPPORTED", st["T2"])                                    # stay11 CTA 양성(storetime 3h)
        self.assertIn("INSUFFICIENT", st["T0"])                                 # triage 미사용 → T0 근거 없음
        self.assertIn("SUPPORTED", res["states"]["S1_TRIAGE_AT_INTIME_APPROX"]["T0"])   # 근사 정책: 빈맥·SOB
        self.assertTrue((self.tmp / "out" / "time_policy_audit_public.json").exists())
        txt = (self.tmp / "out" / "time_policy_audit_public.json").read_text(encoding="utf-8")
        self.assertNotIn("Filling defects", txt)                                # 원문 비출력
        self.assertNotIn("2150-", txt)                                          # 정확 시각 비출력

    def test_abort_on_strict_C_use(self):
        real = TP.time_info

        def bad(r, stay, policy):
            if r.source == "ecg_machine":
                return TP.TimeInfo(stay.intime, TP.C, "OK")
            return real(r, stay, policy)
        with mock.patch.object(TP, "time_info", bad):
            res = R.run(self.tmp / "src", self.tmp / "out2")
        self.assertGreater(res["stop_conditions"].get("strict_C_used", 0), 0)
        self.assertTrue((self.tmp / "out2" / "ABORT_time_policy_audit.json").exists())

    def test_cli_refuses_without_approval_flag(self):
        with mock.patch.object(sys, "argv", ["x", "--src", str(self.tmp / "src"), "--out", str(self.tmp / "o")]):
            with self.assertRaises(SystemExit):
                R.main()
        self.assertFalse((self.tmp / "o").exists())


if __name__ == "__main__":
    unittest.main()
