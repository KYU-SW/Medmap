"""38회차 판별 근거 검사(가상 사례 — 실제 환자 아님). 실행: ~/ai_env/bin/python -B -m unittest discover -s tests"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ddxplus_adapter import build_mapping, case_records  # noqa: E402
from graph_engine import EvidenceRecord, PatientRecord, ReasoningSession, Status, assess_working_dx, infer  # noqa: E402
from knowledge_discriminators import relations  # noqa: E402
from knowledge_real_kg import build_real_graph, disease_node_id  # noqa: E402

PE, PERI, MYO, TB = (disease_node_id(x) for x in ("Pulmonary embolism", "Pericarditis", "Myocarditis", "Tuberculosis"))


def path(inf, d, pid):
    return next(p for p in inf.diseases[d].paths if p.path_id == pid)


class K(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = build_mapping()
        cls.g, cls.meta = build_real_graph(sorted({h for v in cls.m.values() if v["used"] for h in v["hp_ids"]}),
                                           discriminators=True)

    def pr(self, evs, codes=None):
        c = {"EVIDENCES": str(evs), "INITIAL_EVIDENCE": "E_53"}
        p = PatientRecord("V")
        for r in case_records("V", c, self.m, codes or sorted({t.split("_@_")[0] for t in evs}), 1.0):
            p.add(r)
        return p

    def rec(self, node, st, eid, t=2.0):
        return EvidenceRecord(node, Status(st), f"V-{eid}", t, t, "test", evidence_id=eid)

    def test_relation_table(self):
        R = relations()
        self.assertEqual(sum(r["status"] == "APPLIED" for r in R), 9)
        ex = next(r for r in R if r["id"] == "PE-DDIMER-EXCLUDE")
        self.assertTrue(ex["status"].startswith("NOT_APPLIED"))                     # 인용 미확인 배제 규칙 미적용
        self.assertFalse([e for v in self.g.out.values() for e in v if e.rel == "ARGUES_AGAINST"])
        for rid in ("PERI-CRIT-2of4", "MYO-CMR-BOTH", "TB-HIV-SYMPTOM-SCREEN"):
            self.assertEqual(next(r for r in R if r["id"] == rid)["quote_check"], "FOUND", rid)

    def test_pericarditis_criterion_withholds_without_tests(self):
        p = self.pr(["E_53", "E_55_@_V_29", "E_33"])                    # 흉통 + 앞으로 숙이면 완화
        inf = infer(self.g, p, 1.0)
        self.assertEqual(path(inf, PERI, "RULE:PERI-CRIT-2of4->" + PERI).state, "UNKNOWN")   # 검사 없음 → 보류
        self.assertIn("CONCEPT:chest_pain_relieved_sitting_forward", inf.diseases[PERI].support_nodes)
        for d in (PE, MYO, TB):                                        # 자세성 흉통은 심낭염에만 연결
            self.assertNotIn("CONCEPT:chest_pain_relieved_sitting_forward", inf.diseases[d].support_nodes)
        s = ReasoningSession(self.g, p, 1.0)                             # 가상 진찰·심전도 결과 입력 → 기준 충족
        inf2, trans, _ = s.update([self.rec("HP:0034788", "POSITIVE", "rub"), self.rec("HP:0012251", "POSITIVE", "st")], 2.0)
        self.assertEqual(path(inf2, PERI, "RULE:PERI-CRIT-2of4->" + PERI).state, "SUPPORTS")
        self.assertEqual(len([g for g in inf2.diseases[PERI].support_groups if {"HP:0034788"} & g]), 1)   # 마찰음 1회만

    def test_friction_rub_negative_uninformative(self):
        p = self.pr(["E_53", "E_55_@_V_29"])
        p.add(self.rec("HP:0034788", "NEGATIVE", "rubneg", 1.0))
        p.add(self.rec("HP:0012251", "NEGATIVE", "stneg", 1.0))
        p.add(self.rec("HP:0031594", "NEGATIVE", "prneg", 1.0))
        p.add(self.rec("HP:0001698", "NEGATIVE", "effneg", 1.0))
        pe = path(infer(self.g, p, 1.0), PERI, "RULE:PERI-CRIT-2of4->" + PERI)
        self.assertEqual(pe.state, "UNKNOWN")                            # 마찰음 음성은 보류 → 기준 불충족으로 단정 안 함
        self.assertIn(PERI, infer(self.g, p, 1.0).diseases)

    def test_myocarditis_cmr_and_or(self):
        p = PatientRecord("V")
        p.add(self.rec("CONCEPT:cmr_t2_marker", "POSITIVE", "t2", 1.0))
        inf = infer(self.g, p, 1.0)
        self.assertEqual(path(inf, MYO, "RULE:MYO-CMR-ANY->" + MYO).state, "SUPPORTS")
        self.assertEqual(path(inf, MYO, "RULE:MYO-CMR-BOTH->" + MYO).state, "UNKNOWN")   # T1 미검사
        p.add(self.rec("CONCEPT:cmr_t1_marker", "POSITIVE", "t1", 2.0))
        inf2 = infer(self.g, p, 2.0)
        self.assertEqual(path(inf2, MYO, "RULE:MYO-CMR-BOTH->" + MYO).state, "SUPPORTS")
        self.assertEqual(inf2.diseases[MYO].n_support, 2)                 # 두 규칙이 같은 노드 → 묶음 2(T1·T2), 규칙 수만큼 늘지 않음

    def test_tb_hiv_gate(self):
        pos = self.pr(["E_2", "E_91"])
        self.assertEqual(path(infer(self.g, pos, 1.0), TB, "RULE:TB-HIV-SYMPTOM-SCREEN->" + TB).state, "SUPPORTS")
        unk = self.pr(["E_91"])
        r = path(infer(self.g, unk, 1.0), TB, "RULE:TB-HIV-SYMPTOM-SCREEN->" + TB)
        self.assertEqual(r.state, "SUPPORTS")
        self.assertIn("적용 조건 미확정", r.detail)                       # HIV 미기록 → 적용 조건 미확정 표시
        neg = PatientRecord("V")
        neg.add(EvidenceRecord("HP:0001945", Status.POSITIVE, "V-f", 1.0, 1.0, "patient_report", evidence_id="f"))
        neg.add(EvidenceRecord("CONCEPT:hiv_infection", Status.NEGATIVE, "V-h", 1.0, 1.0, "patient_report", evidence_id="h"))
        self.assertEqual(path(infer(self.g, neg, 1.0), TB, "RULE:TB-HIV-SYMPTOM-SCREEN->" + TB).state, "DISABLED")
        d = infer(self.g, pos, 1.0).diseases[TB]
        self.assertEqual(sum(1 for g in d.support_groups if "HP:0001945" in g), 1)   # 발열: 직접 간선 + 규칙 → 1 묶음

    def test_wd_output_cites_sources(self):
        p = self.pr(["E_53", "E_55_@_V_29", "E_33"])
        a = assess_working_dx(self.g, infer(self.g, p, 1.0), p, MYO)
        cls = {n: c for n, c, *_ in a.unexplained}
        self.assertEqual(cls.get("CONCEPT:chest_pain_relieved_sitting_forward"), "EXPLAINED_BY_OTHER")
        self.assertIn(PERI, dict(a.review_candidates))
        sup = [p for p in infer(self.g, p, 1.0).diseases[PERI].paths if p.state == "SUPPORTS"
               and "CONCEPT:chest_pain_relieved_sitting_forward" in p.evidence_nodes]
        self.assertTrue(sup and "DisMech" in sup[0].hops[-1][3])
        self.assertEqual(a.conflict_knowledge, "NO_KNOWLEDGE")


if __name__ == "__main__":
    unittest.main()
