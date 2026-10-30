"""실제 지식(HSDN+DisMech+HPO) × DDXPlus 연결 테스트(34회차). 실행: ~/ai_env/bin/python -B -m unittest discover -s tests"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from ddxplus_adapter import (CHEST_PAIN_HP, build_mapping, case_records, mapping_summary,  # noqa: E402
                             patient_from_case)
from extract_dev_cases import is_holdout, split_key  # noqa: E402
from graph_engine import ReasoningSession, Status, assess_working_dx, infer, with_is_a  # noqa: E402
from knowledge_real_kg import SELECTED, build_real_graph, disease_link_audit, disease_node_id, load_hpo  # noqa: E402
from knowledge_toy import TOY  # noqa: E402
from report_ko import to_json  # noqa: E402

import os  # noqa: E402
DEV = Path(os.environ["EXP01B_DEV_CASES"]) if os.environ.get("EXP01B_DEV_CASES") else \
    sorted((HERE.parent / "outputs").glob("dev_cases_*/dev_cases.json"))[-1]
PAIN = "HP:0012531"


def case(evs, ini="E_66", age=40, sex="F"):
    return {"AGE": age, "SEX": sex, "EVIDENCES": str(evs), "INITIAL_EVIDENCE": ini, "row_index": -1}


class R(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = build_mapping()
        extra = sorted({h for v in cls.m.values() if v["used"] for h in v["hp_ids"]})
        cls.g, cls.meta = build_real_graph(extra_hp_nodes=extra)
        cls.dev = json.loads(DEV.read_text(encoding="utf-8"))

    # 1. 실제 자료 파싱
    def test_sources_parsed(self):
        hpo = load_hpo()
        self.assertEqual(hpo["_meta"]["data_version"], "hp/releases/2026-09-01")
        c = self.meta["counts"]["edges_by_rel_class"]
        for k in ("SUGGESTS|HSDN_LITERATURE_COOCCURRENCE", "SUGGESTS|DISMECH_QUOTE_IN_ABSTRACT",
                  "RISK_FACTOR_FOR|DISMECH_QUOTE_IN_ABSTRACT", "EVALUATES|DISMECH_AI_CURATED", "IS_A|HPO_ONTOLOGY"):
            self.assertGreater(c.get(k, 0), 0, k)
        self.assertEqual(self.meta["hpoa_rows_for_selected"], 0)         # 선택 질환의 HPO 주석(NOT 포함) 없음
        self.assertEqual(self.meta["counts"]["nodes_by_kind"]["DISEASE"], 4)

    # 2. 질환 식별자: ID·라벨 일치만, 이름 유사 연결 없음
    def test_disease_identity(self):
        a = {r["ddxplus_disease"]: r for r in disease_link_audit()}
        for d in SELECTED:
            self.assertEqual((a[d]["hsdn_status"], a[d]["dismech_status"]), ("EXACT_CUI", "LABEL_EXACT_NO_XREF"))
        nst = a["Possible NSTEMI / STEMI"]                               # DisMech 'Myocardial Infarction' 존재하지만 연결 안 됨
        self.assertEqual((nst["hsdn_status"], nst["dismech_status"]), ("NONE", "NONE"))
        self.assertEqual(a["Pulmonary embolism"]["hsdn_mesh"], "D011655")

    # 3. 증상·범주값 매핑
    def test_evidence_mapping(self):
        m = self.m
        self.assertEqual(len(m), 223)
        self.assertEqual((m["E_66"]["status"], m["E_66"]["hp_ids"], m["E_66"]["used"]), ("EXACT", ["HP:0002094"], True))
        self.assertEqual(m["E_45"]["hp_ids"], ["HP:0002105"])
        self.assertEqual((m["E_220"]["status"], m["E_220"]["used"]), ("EXACT_COMPOSITE", True))   # 37회차 흉막성 흉통 복합
        self.assertEqual((m["E_89"]["status"], m["E_89"]["used"]), ("REVIEW", False))     # OR 복합
        self.assertEqual(m["E_33"]["status"], "EXACT_COMPOSITE")   # 38회차 개념 노드
        self.assertEqual((m["E_196"]["status"], m["E_196"]["used"]), ("REVIEW", False))   # 병력↔노출 후보
        s = mapping_summary(m)
        self.assertEqual(s["symptoms"] + s["antecedents"], 223)
        recs = case_records("P", case(["E_53", "E_55_@_V_29", "E_55_@_V_159"]), m, ["E_53", "E_55"], 1.0)
        nodes = {r.node_id for r in recs}
        self.assertIn(CHEST_PAIN_HP, nodes)                              # 통증 + 흉부 부위 → 흉통
        self.assertIn("DDX:E_55", nodes)                                 # 유방 부위는 연결 개념 없음
        recs2 = case_records("P", case(["E_53", "E_55_@_V_159"]), m, ["E_53", "E_55"], 1.0)
        self.assertNotIn(CHEST_PAIN_HP, {r.node_id for r in recs2})
        recs3 = case_records("P", case(["E_55_@_V_29"]), m, ["E_55"], 1.0)   # E_53 없으면 흉통 만들지 않음
        self.assertNotIn(CHEST_PAIN_HP, {r.node_id for r in recs3})

    # 4. 관계 출처 보존·실제/가상 분리·없는 관계 미생성
    def test_provenance_and_separation(self):
        g = self.g
        es = [e for v in g.out.values() for e in v]
        self.assertTrue(all(e.tier == "REAL" and e.source for e in es))
        self.assertTrue(all(e.spec_dict().get("evidence_class") for e in es))
        self.assertFalse([e for e in es if e.rel in ("ARGUES_AGAINST", "PART_OF", "GATES", "DEPENDS_ON")])
        self.assertFalse([n for n in g.nodes.values() if n.kind == "RULE" or n.tier != "REAL"])
        dm = [e for e in es if e.spec_dict()["evidence_class"].startswith("DISMECH")]
        self.assertTrue(dm and all("eaa5fe99" in e.source for e in dm))
        g.add_node("TOYZ", "FINDING", "가상", "TOY", TOY)
        with self.assertRaises(ValueError):
            g.add_edge("TOYZ", "SUGGESTS", disease_node_id("Pericarditis"), "TOY", TOY)
        del g.nodes["TOYZ"], g.out["TOYZ"], g.inc["TOYZ"]

    # 5. 부정·미기록: DDXPlus 에 없는 근거는 NEGATIVE 로 만들지 않음
    def test_absent_is_not_recorded(self):
        for i, c in enumerate(self.dev["cases"]):
            pr, p1, new = patient_from_case(f"D{i}", c, self.m, None)
            allr = pr.all_records() + new
            neg = [r for r in allr if r.status != Status.POSITIVE]       # 음성은 명시적 값에서만(nowhere·N·척도 0)
            self.assertTrue(all(r.status == Status.NEGATIVE and any(x in (r.value or "") for x in ("V_123", "V_10", "_@_0"))
                                for r in neg), neg)
        pr, _, _ = patient_from_case("D", self.dev["cases"][0], self.m, None)
        inf = infer(self.g, pr, 1.0)
        unk = [p for d in inf.diseases.values() for p in d.paths if p.state == "UNKNOWN"]
        self.assertTrue(unk and all("NOT_RECORDED" in p.detail for p in unk))
        self.assertFalse([p for d in inf.diseases.values() for p in d.paths if p.state == "NEGATED"])

    # 6. 새 정보 후 갱신 = 전체 재계산
    def test_update_equals_full(self):
        for i, c in enumerate(self.dev["cases"][:4]):
            pr, p1, new = patient_from_case(f"D{i}", c, self.m, disease_node_id("Pericarditis"))
            s = ReasoningSession(self.g, pr, 1.0)
            inc, trans, aff = s.update(new, 2.0)
            full = infer(self.g, pr, 2.0)
            self.assertEqual(json.dumps(to_json(inc), sort_keys=True), json.dumps(to_json(full), sort_keys=True))

    # 7. IS_A: 하위 양성 → 상위 유도(같은 묶음), 상위 양성 → 하위 유도 없음
    def test_is_a(self):
        g = self.g
        pr, _, _ = patient_from_case("P", case(["E_53", "E_55_@_V_29"], ini="E_53"), self.m, None)
        v = with_is_a(g, pr.view(1.0))
        self.assertEqual(v[PAIN].status, Status.POSITIVE)
        pe = infer(g, pr, 1.0).diseases[disease_node_id("Pulmonary embolism")]
        self.assertEqual(pe.n_support, 1)                                # 통증·흉통 = 의존 → 1 묶음
        self.assertEqual(set(pe.support_groups[0]), {PAIN, CHEST_PAIN_HP})
        pr2, _, _ = patient_from_case("P2", case(["E_53", "E_55_@_V_159"], ini="E_53"), self.m, None)
        self.assertNotIn(CHEST_PAIN_HP, with_is_a(g, pr2.view(1.0)))

    # 8. 의사 진단 비교: 설명 부족 ≠ 충돌, 반박 지식 없음 → 판단 불가, 하위 개념만 연결 → 판단 불가
    def test_wd_assessment(self):
        g = self.g
        pr, _, new = patient_from_case("P", case(["E_66", "E_45", "E_159"]), self.m, None)
        for r in new:
            pr.add(r)
        a = assess_working_dx(g, infer(g, pr, 2.0), pr, disease_node_id("Pericarditis"))
        cls = {n: c for n, c, *_ in a.unexplained}
        self.assertEqual(cls.get("HP:0002105"), "EXPLAINED_BY_OTHER")
        self.assertEqual(cls.get("HP:0007185"), "NARROWER_CONCEPT_LINKED")
        self.assertEqual(a.conflicting, ())
        self.assertEqual(a.conflict_knowledge, "NO_KNOWLEDGE")
        self.assertTrue(a.tests_available)
        self.assertIn(disease_node_id("Myocarditis"), dict(a.review_candidates))   # DisMech 감별 목록

    # 9. 개발 사례 = TRAIN16(HOLDOUT 아님)
    def test_dev_cases_train16_only(self):
        meta = self.dev["meta"]["split_check"]
        self.assertEqual((meta["rows"], meta["holdout"], meta["matches_step16b"]), (1025602, 204663, True))
        for c in self.dev["cases"]:
            self.assertEqual(split_key(c["row_index"], c["AGE"], c["SEX"], c["PATHOLOGY_REFERENCE_ONLY"], c["EVIDENCES"]),
                             c["split_key"])                             # 저장된 키 재계산 일치
            self.assertFalse(is_holdout(c["split_key"]))
            self.assertNotIn("DIFFERENTIAL_DIAGNOSIS", c)


if __name__ == "__main__":
    unittest.main()
