"""EXP-01b 최소 추론 엔진 필수 테스트(8절). 실행: cd exp/exp01b_graph_engine && ~/ai_env/bin/python -m unittest -v"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import graph_engine as ge  # noqa: E402
from graph_engine import (EvidenceRecord, MedGraph, PatientRecord, ReasoningSession, RuleState, Status,  # noqa: E402
                          assess_working_dx, combine, eval_leaf, from_medmap_input, infer)
from knowledge_real_hsdn import build_hsdn_graph  # noqa: E402
from knowledge_toy import TOY, build_toy_graph  # noqa: E402
from report_ko import render_ko, to_json  # noqa: E402

WT = HERE.parents[2]                                   # ~/medmap-worktrees/main-ai


def rec(node, st, eid, t=1.0, src=None, **kw):
    return EvidenceRecord(node, Status(st), src or f"src-{eid}", t, t, kw.pop("source_type", "patient_report"),
                          evidence_id=eid, **kw)


def patient(*recs, wd=None):
    pr = PatientRecord("P", working_dx=wd)
    for r in recs:
        pr.add(r)
    return pr


def path(inf, d, pid):
    return next(p for p in inf.diseases[d].paths if p.path_id == pid)


class T01MultiPath(unittest.TestCase):
    def test_same_disease_reached_by_several_paths_single_node(self):
        g = build_toy_graph()
        self.assertEqual(sum(1 for n in g.nodes.values() if n.node_id == "TB"), 1)
        again = g.add_node("TB", "DISEASE", "가상질환B", "TOY", TOY)
        self.assertIs(again, g.nodes["TB"])                       # 재등록 = 공유, 복제 없음
        with self.assertRaises(ValueError):
            g.add_node("TB", "SYMPTOM", "x", "TOY", TOY)
        pr = patient(rec("s1", "POSITIVE", "e1"), rec("s2", "POSITIVE", "e2"), rec("g1", "POSITIVE", "e3"),
                     rec("f1", "POSITIVE", "e4", value="600", unit="u/L", source_type="test"))
        inf = infer(g, pr, 1.0)
        sup = [p.path_id for p in inf.diseases["TB"].paths if p.state == "SUPPORTS"]
        self.assertEqual(sorted(sup), ["R1->TB", "s1-SUGGESTS->TB", "s2-SUGGESTS->TB"])
        self.assertEqual(set(inf.diseases), {"TA", "TB", "TC", "TD"})

    def test_graph_edges_drive_result(self):
        g = build_toy_graph()
        pr = patient(rec("s1", "POSITIVE", "e1"), rec("s2", "POSITIVE", "e2"))
        self.assertEqual(infer(g, pr, 1.0).diseases["TB"].n_support, 2)
        g.remove_edge(next(e for e in g.in_edges("TB") if e.src == "s2"))
        self.assertEqual(infer(g, pr, 1.0).diseases["TB"].n_support, 1)   # 간선 제거 → 결과 변화


class T02AndOr(unittest.TestCase):
    S, U, I = RuleState.SATISFIED, RuleState.UNMET, RuleState.INDETERMINATE

    def test_kleene_tables(self):
        S, U, I = self.S, self.U, self.I
        self.assertEqual(combine("AND", [S, S]), S)
        self.assertEqual(combine("AND", [S, I]), I)
        self.assertEqual(combine("AND", [I, U]), U)
        self.assertEqual(combine("OR", [U, I]), I)
        self.assertEqual(combine("OR", [U, U]), U)
        self.assertEqual(combine("OR", [I, S]), S)
        self.assertEqual(combine("AND", []), I)

    def test_rules_in_graph(self):
        g = build_toy_graph()
        # R1 AND: s2 양성, f1 미검사 → 미확정(성급히 참/거짓 아님)
        pr = patient(rec("s2", "POSITIVE", "e1"), rec("f1", "NOT_TESTED", "e2"), rec("g1", "POSITIVE", "e3"))
        self.assertEqual(path(infer(g, pr, 1.0), "TB", "R1->TB").state, "UNKNOWN")
        # f1 임계 미만 → AND 불충족(질환 유지)
        pr.add(rec("f1", "POSITIVE", "e4", t=2.0, value="100", unit="u/L", source_type="test"))
        inf = infer(g, pr, 2.0)
        self.assertEqual(path(inf, "TB", "R1->TB").state, "UNMET")
        self.assertIn("TB", inf.diseases)
        # R2 OR: s6 양성 하나로 충족, f2 미기록이어도
        pr2 = patient(rec("s6", "POSITIVE", "e1"))
        self.assertEqual(path(infer(g, pr2, 1.0), "TA", "R2->TA").state, "SUPPORTS")
        pr3 = patient(rec("s6", "NEGATIVE", "e1"))
        self.assertEqual(path(infer(g, pr3, 1.0), "TA", "R2->TA").state, "UNKNOWN")   # f2 미기록 → OR 미확정


class T03FiveStates(unittest.TestCase):
    def test_leaf_states_distinct(self):
        g = build_toy_graph()
        e = next(x for x in g.in_edges("TB") if x.src == "s2")
        out = {}
        for st in ("POSITIVE", "NEGATIVE", "UNCERTAIN", "NOT_TESTED"):
            out[st] = eval_leaf(e, patient(rec("s2", st, "e1")).view(1.0))
        out["NOT_RECORDED"] = eval_leaf(e, patient().view(1.0))
        self.assertEqual(out["POSITIVE"].state, RuleState.SATISFIED)
        self.assertEqual(out["NEGATIVE"].state, RuleState.UNMET)
        for k in ("UNCERTAIN", "NOT_TESTED", "NOT_RECORDED"):
            self.assertEqual(out[k].state, RuleState.INDETERMINATE, k)
            self.assertEqual(out[k].status, Status(k))                   # 상태가 서로 구분돼 보존
        self.assertEqual(len({o.status for o in out.values()}), 5)

    def test_not_recorded_never_used_as_negative(self):
        g = build_toy_graph()
        inf_missing = infer(g, patient(rec("s1", "POSITIVE", "e1")), 1.0)
        inf_neg = infer(g, patient(rec("s1", "POSITIVE", "e1"), rec("s2", "NEGATIVE", "e2")), 1.0)
        self.assertEqual(path(inf_missing, "TB", "s2-SUGGESTS->TB").state, "UNKNOWN")
        self.assertEqual(path(inf_neg, "TB", "s2-SUGGESTS->TB").state, "NEGATED")
        self.assertNotEqual(len(inf_missing.diseases["TB"].negated), len(inf_neg.diseases["TB"].negated))
        # 적용 조건 g1 미기록 → 규칙 비활성 아님
        self.assertFalse(inf_missing.diseases["TB"].disabled)

    def test_negative_never_removes_disease_and_missing_demographics_not_imputed(self):
        g = build_toy_graph()
        pr = from_medmap_input("P", {"binary": {"s1": "NEGATIVE", "s2": "NEGATIVE", "s4": "NEGATIVE"}})
        inf = infer(g, pr, 0.0)
        self.assertEqual(set(inf.diseases), set(g.diseases()))
        self.assertIsNone(pr.age)
        self.assertIsNone(pr.sex)
        self.assertNotIn("s3", pr.view(0.0))                           # 범주 질문 미제공 → 만들지 않음

    def test_future_records_not_visible(self):
        g = build_toy_graph()
        pr = patient(rec("s2", "POSITIVE", "e1", t=5.0))
        self.assertEqual(path(infer(g, pr, 1.0), "TB", "s2-SUGGESTS->TB").state, "UNKNOWN")

    def test_categorical_and_threshold(self):
        g = build_toy_graph()
        inf = infer(g, patient(rec("s3", "POSITIVE", "e1", value="R")), 1.0)
        self.assertEqual(path(inf, "TC", "s3-SUGGESTS->TC").state, "SUPPORTS")
        self.assertEqual(path(inf, "TA", "s3-SUGGESTS->TA").state, "NEGATED")
        inf2 = infer(g, patient(rec("s3", "POSITIVE", "e1")), 1.0)     # 값 미기록 → 보류
        self.assertEqual(path(inf2, "TC", "s3-SUGGESTS->TC").state, "UNKNOWN")
        e = next(x for x in g.in_edges("R1", "PART_OF") if x.src == "f1")
        lv = eval_leaf(e, patient(rec("f1", "POSITIVE", "e1", value="9", unit="mmol/L")).view(1.0))
        self.assertEqual(lv.state, RuleState.INDETERMINATE)               # 단위 변환 규칙 없음 → 보류


class T04NoDoubleCount(unittest.TestCase):
    def test_same_node_via_two_paths_counted_once(self):
        g = build_toy_graph()
        pr = patient(rec("s2", "POSITIVE", "e1"), rec("g1", "POSITIVE", "e2"),
                     rec("f1", "POSITIVE", "e3", value="700", unit="u/L", source_type="test"))
        d = infer(g, pr, 1.0).diseases["TB"]
        self.assertEqual(sum(1 for p in d.paths if p.state == "SUPPORTS" and "s2" in p.evidence_nodes), 2)
        self.assertEqual(d.support_nodes, ("f1", "s2"))
        self.assertEqual(d.n_support, 2)

    def test_known_dependency_and_same_source_grouped(self):
        g = build_toy_graph()
        d = infer(g, patient(rec("s1", "POSITIVE", "e1"), rec("s5", "POSITIVE", "e2")), 1.0).diseases["TC"]
        self.assertEqual(d.n_support, 1)                                  # s5 DEPENDS_ON s1
        d2 = infer(g, patient(rec("s1", "POSITIVE", "e1", src="doc-1"), rec("s4", "POSITIVE", "e2", src="doc-1")),
                   1.0).diseases["TC"]
        self.assertEqual(d2.n_support, 1)                                 # 같은 source_id
        d3 = infer(g, patient(rec("s1", "POSITIVE", "e1"), rec("s4", "POSITIVE", "e2")), 1.0).diseases["TC"]
        self.assertEqual((d3.n_support, d3.independence), (2, "UNVERIFIED"))   # 관계 미확인 → 독립성 미확인


class T05RelationTypes(unittest.TestCase):
    def test_relation_type_changes_computation(self):
        pr = patient(rec("s4", "POSITIVE", "e1"))
        g = build_toy_graph()
        inf = infer(g, pr, 1.0)
        self.assertEqual(len(inf.diseases["TA"].conflicts), 1)
        self.assertEqual(inf.diseases["TA"].n_support, 0)
        g2 = build_toy_graph()
        g2.remove_edge(next(e for e in g2.in_edges("TA") if e.src == "s4"))
        g2.add_edge("s4", "SUGGESTS", "TA", "TOY", TOY)
        inf2 = infer(g2, pr, 1.0)
        self.assertEqual((len(inf2.diseases["TA"].conflicts), inf2.diseases["TA"].n_support), (0, 1))

    def test_gate_vs_part_of(self):
        # 같은 음성 근거라도 GATES 면 비활성(가역), PART_OF 면 규칙 불충족
        pr = patient(rec("s2", "POSITIVE", "e1"), rec("g1", "NEGATIVE", "e2"))
        self.assertEqual(path(infer(build_toy_graph(), pr, 1.0), "TB", "R1->TB").state, "DISABLED")
        pr2 = patient(rec("s2", "NEGATIVE", "e1"), rec("g1", "POSITIVE", "e2"))
        self.assertEqual(path(infer(build_toy_graph(), pr2, 1.0), "TB", "R1->TB").state, "UNMET")

    def test_relation_kind_validation(self):
        g = build_toy_graph()
        with self.assertRaises(ValueError):
            g.add_edge("TA", "SUGGESTS", "TB", "TOY", TOY)
        with self.assertRaises(ValueError):
            g.add_edge("s1", "SUGGESTS", "TA", "TOY", "")              # 출처 없는 관계 금지


class T06DisableReactivate(unittest.TestCase):
    def test_disable_then_reactivate_by_correction(self):
        g = build_toy_graph()
        pr = patient(rec("s2", "POSITIVE", "e1"), rec("g1", "NEGATIVE", "e2"),
                     rec("f1", "POSITIVE", "e3", value="800", unit="u/L", source_type="test"))
        s = ReasoningSession(g, pr, 1.0)
        self.assertEqual(path(s.current, "TB", "R1->TB").state, "DISABLED")
        self.assertIn("TB", s.current.diseases)                           # 질환은 유지
        inf, trans, aff = s.update([EvidenceRecord("g1", Status.POSITIVE, "chart", 0.5, 2.0, "chart_review",
                                                   evidence_id="e4", supersedes="e2")], 2.0)
        self.assertEqual(path(inf, "TB", "R1->TB").state, "SUPPORTS")
        self.assertIn(("R1->TB", "REACTIVATED"), [(t.path_id, t.kind) for t in trans])
        self.assertEqual([r.evidence_id for r in pr.history("g1")], ["e2", "e4"])   # 이전 기록 보존
        with self.assertRaises(ValueError):
            pr.add(EvidenceRecord("g1", Status.NEGATIVE, "x", 0.0, 2.0, "chart_review", evidence_id="e5",
                                  supersedes="e4"))                       # 같은 시각 정정 = 모호 → 거부
        with self.assertRaises(ValueError):
            pr.add(rec("g1", "NEGATIVE", "e4"))                           # ID 중복


class T07UpdateCorrect(unittest.TestCase):
    def test_incremental_equals_full_recompute(self):
        for build, init, new in [
            (build_toy_graph, [rec("s1", "POSITIVE", "e1"), rec("s2", "POSITIVE", "e2"), rec("g1", "NEGATIVE", "e3")],
             [rec("f1", "POSITIVE", "e4", t=2.0, value="900", unit="u/L", source_type="test"),
              EvidenceRecord("g1", Status.POSITIVE, "c", 2.0, 2.0, "chart_review", evidence_id="e5", supersedes="e3"),
              rec("s5", "POSITIVE", "e6", t=2.0)]),
            (lambda: build_hsdn_graph()[0], [rec("S:CHEST_PAIN", "POSITIVE", "e1")],
             [rec("S:SYNCOPE", "POSITIVE", "e2", t=2.0), rec("S:FEVER", "NEGATIVE", "e3", t=2.0)])]:
            g = build()
            pr = patient(*init)
            s = ReasoningSession(g, pr, 1.0)
            inc, _, aff = s.update(new, 2.0)
            full = infer(g, pr, 2.0)
            self.assertEqual(json.dumps(to_json(inc), sort_keys=True), json.dumps(to_json(full), sort_keys=True))
            self.assertTrue(aff)
        g = build_toy_graph()
        self.assertEqual(ge.affected_diseases(g, {"s7"}), {"TD"})
        self.assertEqual(ge.affected_diseases(g, {"g1"}), {"TB"})        # 규칙 노드 경유


class T08WorkingDx(unittest.TestCase):
    def test_unexplained_vs_conflict_vs_undetermined(self):
        g = build_toy_graph()
        pr = patient(rec("s1", "POSITIVE", "e1"), rec("s2", "POSITIVE", "e2"), rec("s4", "UNCERTAIN", "e3"),
                     rec("g1", "NEGATIVE", "e4"))
        inf = infer(g, pr, 1.0)
        a = assess_working_dx(g, inf, pr, "TA")
        self.assertEqual([n for n, c, *_ in a.unexplained], ["s2"])
        self.assertEqual(a.unexplained[0][1], "EXPLAINED_BY_OTHER")
        self.assertEqual(a.conflicting, ())
        self.assertIn("s4", [n for n, *_ in a.undetermined])            # 불확실 → 충돌 아님, 판단 보류
        self.assertIn("TB", dict(a.review_candidates))
        pr_g = patient(rec("s1", "POSITIVE", "e1"), rec("g1", "POSITIVE", "e2"))
        a_g = assess_working_dx(g, infer(g, pr_g, 1.0), pr_g, "TA")
        self.assertIn("g1", infer(g, pr_g, 1.0).positive_in_graph)
        self.assertNotIn("g1", [n for n, *_ in a_g.unexplained])        # 양성 적용 조건도 설명 대상 아님
        pr.add(rec("s4", "POSITIVE", "e5", t=2.0))
        b = assess_working_dx(g, infer(g, pr, 2.0), pr, "TA")
        self.assertEqual([n for p in b.conflicting for n in p.evidence_nodes], ["s4"])
        self.assertNotIn("s4", [n for n, *_ in b.unexplained])

    def test_unexplained_in_graph_and_impossible(self):
        g = build_toy_graph()
        pr = patient(rec("s7", "POSITIVE", "e1"), rec("ZZ", "POSITIVE", "e2"))
        g.remove_edge(next(e for e in g.in_edges("TD") if e.src == "s7"))
        a = assess_working_dx(g, infer(g, pr, 1.0), pr, "TA")
        self.assertEqual(a.unexplained[0][:2], ("s7", "UNEXPLAINED_IN_GRAPH"))
        self.assertEqual(a.out_of_graph, ("ZZ",))
        self.assertEqual(assess_working_dx(g, infer(g, pr, 1.0), pr, "NOT_A_NODE").status, "INFERENCE_IMPOSSIBLE")

    def test_no_conflict_knowledge_reported_as_insufficient(self):
        g, _ = build_hsdn_graph()
        pr = patient(rec("S:CHEST_PAIN", "POSITIVE", "e1"))
        a = assess_working_dx(g, infer(g, pr, 1.0), pr, "D:MI")
        self.assertEqual(a.conflict_knowledge, "NO_KNOWLEDGE")
        self.assertIn("판단 불가", render_ko(g, infer(g, pr, 1.0), a))

    def test_wd_does_not_block_other_candidates(self):
        g = build_toy_graph()
        pr = patient(rec("s1", "POSITIVE", "e1"), rec("s2", "POSITIVE", "e2"))
        inf = infer(g, pr, 1.0)
        a = assess_working_dx(g, inf, pr, "TA")
        self.assertEqual(len(inf.ranking()), 4)
        self.assertEqual(inf.ranking()[0].disease, "TB")                # 현재 진단이 순서를 바꾸지 않음


class T09Provenance(unittest.TestCase):
    def test_every_path_traceable(self):
        for g in (build_toy_graph(), build_hsdn_graph()[0]):
            pr = patient(*[rec(n, "POSITIVE", f"e{i}", value="R" if n == "s3" else None)
                           for i, n in enumerate(sorted(g.nodes)) if g.nodes[n].kind == "SYMPTOM"])
            inf = infer(g, pr, 1.0)
            ids = {r.evidence_id for r in pr.all_records()}
            for d in inf.diseases.values():
                for p in d.paths:
                    self.assertTrue(p.hops)
                    for s, r, dst, so, tier in p.hops:
                        self.assertTrue(so)
                        self.assertIn(tier, ("REAL", "TOY"))
                    self.assertTrue(set(p.evidence_ids) <= ids)
                    if p.state == "SUPPORTS":
                        self.assertTrue(p.evidence_ids)

    def test_real_edges_cite_hsdn_and_tiers_not_mixed(self):
        g, meta = build_hsdn_graph()
        es = [e for v in g.out.values() for e in v]
        self.assertTrue(es and all(e.tier == "REAL" and e.source.startswith("HSDN Supp Data 3") for e in es))
        self.assertEqual(meta["edges_kept"], len(es))
        g.add_node("TOYX", "SYMPTOM", "가상", "TOY", TOY)
        with self.assertRaises(ValueError):
            g.add_edge("TOYX", "SUGGESTS", "D:MI", "TOY", TOY)           # 가상 관계를 실제 질환에 연결 금지
        self.assertFalse(any(n.tier == "REAL" for n in build_toy_graph().nodes.values()))


class T10Exp01Preserved(unittest.TestCase):
    def test_main_ai_files_unchanged_and_final_sha(self):
        before = {}
        for line in (HERE / "exp01_main_ai_sha256_before_exp01b.txt").read_text().splitlines():
            h, p = line.split("  ", 1)
            before[p] = h
        root = WT / "exp" / "main_ai"
        now = {str(p.relative_to(WT)): hashlib.sha256(p.read_bytes()).hexdigest()
               for p in root.rglob("*") if p.is_file() and "__pycache__" not in p.parts and "outputs" not in p.parts}
        self.assertEqual(now, before)                                     # 추가·수정·삭제 0
        r = subprocess.run(["sha256sum", "-c", "--quiet", "archive/final_20261029_0925_SHA256SUMS"], cwd=WT,
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        used = (root / "exp01_symptom_graph/outputs/FINAL_USED").read_text().strip()
        self.assertEqual(used, "used ee8ef094a9acbf5400afcecccef46b38bd0441024c877aedc7d77398da979e08")


if __name__ == "__main__":
    unittest.main()
