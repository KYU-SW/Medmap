"""37회차 정렬(spec)·4분류 검사. 실행: ~/ai_env/bin/python -B -m unittest discover -s tests"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ddxplus_adapter import answer_records, build_mapping  # noqa: E402
from discrimination import spec_key, spec_scores, wd_categories  # noqa: E402
from graph_engine import PatientRecord, Status, assess_working_dx, infer  # noqa: E402
from knowledge_real_kg import build_real_graph, disease_node_id  # noqa: E402

PE, TB, PERI = (disease_node_id(x) for x in ("Pulmonary embolism", "Tuberculosis", "Pericarditis"))


class D(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = build_mapping()
        cls.g, _ = build_real_graph(sorted({h for v in cls.m.values() if v["used"] for h in v["hp_ids"]}))

    def patient(self, codes):
        pr = PatientRecord("P")
        for c in codes:
            for r in answer_records("P", c, Status.POSITIVE, [], self.m, 1.0):
                pr.add(r)
        return pr

    def test_specific_evidence_weighs_more_and_no_double_count(self):
        pr = self.patient(["E_66"])                                      # 호흡곤란: DisMech 4질환 모두 연결
        sc = spec_scores(self.g, infer(self.g, pr, 1.0))
        self.assertAlmostEqual(sc[PE]["S_clin"], 0.25, places=6)
        self.assertAlmostEqual(sc[TB]["S_clin"], 0.25, places=6)
        pr2 = self.patient(["E_66", "E_162"])                             # + 체중감소: DisMech 결핵만
        sc2 = spec_scores(self.g, infer(self.g, pr2, 1.0))
        self.assertGreater(sc2[TB]["S_clin"], sc2[PE]["S_clin"])
        self.assertLess(spec_key(sc2[TB]), spec_key(sc2[PE]))
        for d, x in sc2.items():                                         # 묶음당 1번만 더함
            self.assertLessEqual(sc2[d]["S_clin"], len(x["groups"]) + 1e-9)

    def test_hsdn_not_in_clinical_score_and_no_removal(self):
        pr = self.patient(["E_53"])                                      # 통증: HSDN 공출현만
        sc = spec_scores(self.g, infer(self.g, pr, 1.0))
        self.assertEqual(sc[PE]["S_clin"], 0.0)
        self.assertGreater(sc[PE]["S_all"], 0.0)
        self.assertEqual(len(sc), 4)                                     # 질환 제거 없음

    def test_wd_categories_separate_gap_and_review(self):
        pr = self.patient(["E_66", "E_162", "E_155"])                    # 두근거림: 그래프 내 관계 없음
        a = assess_working_dx(self.g, infer(self.g, pr, 1.0), pr, PERI)
        c = wd_categories(a)
        self.assertTrue(c["review_signal"])                              # 체중감소 → 결핵이 설명(B)
        self.assertTrue(c["knowledge_gap_flag"])                         # 두근거림 → 지식 부족(C)
        self.assertEqual((c["D_verified_conflict"], c["D_status"]), (0, "판단 불가(반박 관계 없음)"))
        pr2 = self.patient(["E_155"])
        c2 = wd_categories(assess_working_dx(self.g, infer(self.g, pr2, 1.0), pr2, PERI))
        self.assertEqual((c2["review_signal"], c2["knowledge_gap_flag"]), (False, True))   # 지식 부족만 → 재검토 신호 아님


if __name__ == "__main__":
    unittest.main()
