"""35회차 연결 정확성 검사. 실행: ~/ai_env/bin/python -B -m unittest discover -s tests"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ddxplus_adapter import answer_records, build_mapping, case_records  # noqa: E402
from graph_engine import GRADE, PatientRecord, Status, infer  # noqa: E402
from knowledge_real_kg import build_real_graph, disease_node_id, verify_quote  # noqa: E402

CHEST, RADIATING, DYSPNEA, PALP, ARRHY, GER = ("HP:0100749", "HP:6000684", "HP:0002094", "HP:0001962",
                                               "HP:0011675", "HP:0002020")


def case(evs):
    return {"EVIDENCES": str(evs), "INITIAL_EVIDENCE": "E_66", "AGE": 40, "SEX": "F", "row_index": -1}


class A(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = build_mapping()
        cls.g, cls.meta = build_real_graph(sorted({h for v in cls.m.values() if v["used"] for h in v["hp_ids"]}))

    def nodes(self, recs):
        return {(r.node_id, r.status) for r in recs}

    # 넓은 개념 음성 전파 금지: '휴식 중 흉통 없음' ≠ 흉통 없음 / 같은 개념은 음성 사용
    def test_broader_negative_not_propagated(self):
        self.assertEqual(self.m["E_14"]["status"], "EXACT_BROADER")
        self.assertEqual(self.nodes(answer_records("P", "E_14", Status.NEGATIVE, [], self.m, 1.0)),
                         {("DDX:E_14", Status.NEGATIVE)})
        self.assertEqual(self.nodes(answer_records("P", "E_14", Status.POSITIVE, [], self.m, 1.0)),
                         {(CHEST, Status.POSITIVE)})
        self.assertEqual(self.nodes(answer_records("P", "E_66", Status.NEGATIVE, [], self.m, 1.0)),
                         {(DYSPNEA, Status.NEGATIVE)})                     # 같은 개념 EXACT 는 음성 사용
        self.assertEqual(self.nodes(answer_records("P", "E_66", Status.UNCERTAIN, [], self.m, 1.0)),
                         {(DYSPNEA, Status.UNCERTAIN)})
        for code, v in self.m.items():                                     # 음성 사용 = EXACT 단일 개념 + 필수 성분 복합 2개
            if v["negative_ok"]:
                if code in ("E_220", "E_151"):
                    self.assertEqual(v["status"], "EXACT_COMPOSITE", code)
                else:
                    self.assertEqual((v["status"], len(v["hp_ids"])), ("EXACT", 1), code)

    # 증상 ↔ 진단 개념 혼동 금지
    def test_symptom_not_diagnosis(self):
        self.assertEqual(self.m["E_164"]["hp_ids"], [PALP])                 # 불규칙 박동 느낌 → 두근거림, 부정맥 아님
        self.assertNotIn(ARRHY, [h for v in self.m.values() if v["used"] for h in v["hp_ids"]])
        self.assertEqual((self.m["E_173"]["status"], self.m["E_173"]["used"]), ("REVIEW", False))   # 속쓰림 ≠ GERD
        self.assertNotIn(GER, [h for v in self.m.values() if v["used"] for h in v["hp_ids"]])
        es = [e for v in self.g.out.values() for e in v if e.rel == "SUGGESTS"]
        self.assertNotIn(("HP:0012819", disease_node_id("Myocarditis")), {(e.src, e.dst) for e in es})
        self.assertEqual([x["hp"] for x in self.meta["excluded_self_concept"]], ["HP:0012819"])

    # 복합(OR) 질문을 개별 소견 양성으로 쪼개지 않음
    def test_or_composites_not_split(self):
        for code in ("E_175", "E_77", "E_30", "E_89", "E_174", "E_211", "E_93"):
            self.assertFalse(self.m[code]["used"], code)
            self.assertEqual(self.nodes(answer_records("P", code, Status.POSITIVE, [], self.m, 1.0)),
                             {(f"DDX:{code}", Status.POSITIVE)}, code)
        self.assertTrue(self.m["E_188"]["used"])                           # 'A AND B' 는 둘 다

    # 값 의미: nowhere = 음성, 척도 0 = 없음, N = 아니오, 통증 성질로 위치 추정 안 함
    def test_value_rules(self):
        self.assertEqual(self.nodes(answer_records("P", "E_57", Status.POSITIVE, ["V_123"], self.m, 1.0)),
                         {(RADIATING, Status.NEGATIVE)})
        self.assertEqual(self.nodes(answer_records("P", "E_57", Status.POSITIVE, ["V_56"], self.m, 1.0)),
                         {(RADIATING, Status.POSITIVE)})
        self.assertEqual(self.nodes(answer_records("P", "E_136", Status.POSITIVE, ["0"], self.m, 1.0)),
                         {("DDX:E_136", Status.NEGATIVE)})
        self.assertEqual(self.nodes(answer_records("P", "E_136", Status.POSITIVE, ["4"], self.m, 1.0)),
                         {("HP:0000989", Status.POSITIVE)})
        self.assertEqual(self.nodes(answer_records("P", "E_131", Status.POSITIVE, ["V_10"], self.m, 1.0)),
                         {("DDX:E_131", Status.NEGATIVE)})                 # 'N' 선택, 상위 개념 연결이라 HPO 음성 아님
        recs = case_records("P", case(["E_53", "E_54_@_V_179", "E_220"]), self.m, ["E_53", "E_54", "E_220"], 1.0)
        self.assertNotIn(CHEST, {r.node_id for r in recs})                 # 부위 없으면 흉통 만들지 않음
        self.assertNotIn("HP:0033771", {r.node_id for r in recs})          # 흡기 시 악화만으로 흉막성 흉통 아님

    # 공출현은 임상 소견 근거로 세지 않음 · 근거 등급은 개수와 별개
    def test_cooccurrence_not_clinical(self):
        pr = PatientRecord("P")
        pr.add(answer_records("P", "E_53", Status.POSITIVE, [], self.m, 1.0)[0])   # 통증: HSDN 공출현만
        pe = infer(self.g, pr, 1.0).diseases[disease_node_id("Pulmonary embolism")]
        self.assertEqual((pe.n_support, pe.n_clinical, pe.n_cooccurrence_only), (1, 0, 1))
        self.assertEqual(GRADE["HSDN_LITERATURE_COOCCURRENCE"], 0)
        es = [e for v in self.g.out.values() for e in v]
        self.assertTrue(all("확률 아님" in e.source for e in es if e.spec_dict()["evidence_class"].startswith("HSDN")))
        self.assertFalse([e for e in es if e.rel in ("ARGUES_AGAINST", "PART_OF", "GATES")])   # 진단 규칙·반박 0

    def test_composites_37(self):
        from ddxplus_adapter import LIMB_SWELLING_HP, PLEURITIC_HP
        base = ["E_53", "E_55_@_V_29", "E_220"]
        def nodes(evs):
            return {r.node_id for r in case_records("P", case(evs), self.m, sorted({t.split("_@_")[0] for t in evs}), 1.0)}
        self.assertIn(PLEURITIC_HP, nodes(base + ["E_54_@_V_192"]))       # 흡기 악화 + 흉부 + 날카로움
        self.assertNotIn(PLEURITIC_HP, nodes(base + ["E_54_@_V_183"]))    # 무거움 → 아님
        self.assertNotIn(PLEURITIC_HP, nodes(base))                       # 성질 값 없음 → 추정 안 함
        self.assertNotIn(PLEURITIC_HP, nodes(["E_53", "E_55_@_V_159", "E_220", "E_54_@_V_192"]))   # 흉부 아님(유방)
        self.assertIn(LIMB_SWELLING_HP, nodes(["E_151", "E_152_@_V_119"]))   # 종아리
        self.assertNotIn(LIMB_SWELLING_HP, nodes(["E_151", "E_152_@_V_89"]))  # 이마
        self.assertNotIn("HP:0000969", nodes(["E_151", "E_152_@_V_119"]))     # Edema 로 넘기지 않음
        self.assertEqual(self.nodes(answer_records("P", "E_220", Status.NEGATIVE, [], self.m, 1.0)),
                         {(PLEURITIC_HP, Status.NEGATIVE)})                  # 필수 성분 부재 → 음성
        self.assertEqual(self.m["E_54"]["status"], "NO_CONCEPT")
        self.assertEqual(self.m["E_33"]["status"], "EXACT_COMPOSITE")   # 38회차 개념 노드

    def test_wd_not_own_review_candidate(self):
        pr = PatientRecord("P")
        for r in answer_records("P", "E_159", Status.POSITIVE, [], self.m, 1.0):     # 의식 소실: 하위 '실신'만 PE 에 연결
            pr.add(r)
        from graph_engine import assess_working_dx
        wd = disease_node_id("Pulmonary embolism")
        a = assess_working_dx(self.g, infer(self.g, pr, 1.0), pr, wd)
        self.assertIn(("HP:0007185", "NARROWER_CONCEPT_LINKED"), [(n, c) for n, c, *_ in a.unexplained])
        self.assertNotIn(wd, dict(a.review_candidates))

    def test_quote_verification(self):
        self.assertEqual(verify_quote({"reference": "PMID:17904458", "snippet": "Dyspnea may be absent even in patients with circulatory collapse."}), "FOUND")
        self.assertEqual(verify_quote({"reference": "PMID:17904458", "snippet": "Dyspnea is always present in every pulmonary embolism patient."}), "NOT_FOUND")
        self.assertEqual(verify_quote({"reference": "PMID:1", "snippet": "x" * 20}), "NO_CACHE")
        self.assertEqual(verify_quote({"reference": "", "snippet": "x"}), "NO_PMID")


if __name__ == "__main__":
    unittest.main()
