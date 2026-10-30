"""M1: Baseline A 실제 평가 경로(제품 엔진) ↔ 독립 재계산(STEP16B 연구 경로) 대조.
실제 STEP16B pkl·ig 표·evidences.json 을 읽지만 DDXPlus 환자 행은 읽지 않는다(지어낸 환자만).
"""
import sys
import unittest
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
S16B = "/home/<user>/medmap/exp/step16b_next_information_validation"
for p in ("/home/<user>/medmap", S16B):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    import pickle

    import s16b_core as c
    from medmap.diagnosis import DiagnosisEngine
    from medmap.evidence import EvidenceCatalog
    from medmap.next_information import NextInformationEngine
    AVAILABLE = Path(S16B, "model_k3.pkl").exists()
except Exception:  # noqa: BLE001
    AVAILABLE = False

from aref import AReference  # noqa: E402
from core import Exp01Invalid, run_case  # noqa: E402
from searchers import BaselineASearcher  # noqa: E402


def fabricated_patients(sem, n=12, seed=0):
    """지어낸 환자: 부모 없는 이진 몇 개 + 범주형은 첫 값(부모 조건 충족 시). UNSAFE 없음."""
    rng = np.random.default_rng(seed)
    top_bin = [q for q in sem.qids if sem.dtype[q] == "B" and q not in sem.parent and sem.safe[q]]
    out = []
    for i in range(n):
        pos = set(rng.choice(top_bin, size=int(rng.integers(2, 8)), replace=False).tolist())
        toks = list(pos)
        for q in sem.qids:
            if sem.dtype[q] == "B":
                continue
            par = sem.parent.get(q)
            if par is None or par in pos:
                toks.append(f"{q}_@_{sem.values[q][0]}")
        init = sorted(pos, key=lambda e: int(e[2:]))[0]
        out.append({"initial": init, "tokens": tuple(toks), "age": int(rng.integers(1, 90)),
                    "sex": "M" if i % 2 else "F"})
    return out


@unittest.skipUnless(AVAILABLE, "STEP16B 모델 없음")
class TestBaselineAPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sem = c.Semantics()
        cls.cat = EvidenceCatalog()
        cls.eng = {k: DiagnosisEngine(cls.cat, f"k{k}") for k in (3, 5, 10)}
        cls.models = {k: pickle.load(open(f"{S16B}/model_k{k}.pkl", "rb")) for k in (3, 5, 10)}
        z = np.load(f"{S16B}/ig_table_step16b_train.npz", allow_pickle=True)
        cls.ig = {k: z[k] for k in z.files if k != "__classes__"}
        cls.ref = AReference(c, cls.sem, cls.models, cls.ig, list(cls.models[3].classes_))
        ctx = {"k3": 3, "k5": 5, "k10": 10}
        cls.factory = staticmethod(lambda cx, mq: NextInformationEngine(cls.eng[ctx[cx]], cls.cat, max_questions=mq))

    def test_encoding_columns_identical(self):
        self.assertEqual(self.cat.columns, c.Encoder(self.sem).cols)

    def test_encoding_matrix_identical_on_fabricated_states(self):
        from medmap import patient_state as ps
        enc = c.Encoder(self.sem)
        for p in fabricated_patients(self.sem):
            st = ps.PatientState.new(age=p["age"], sex=p["sex"], initial_evidence=p["initial"])
            vis = {p["initial"]: ("POS",)}
            a = self.cat.encode([st]).toarray()
            b = enc.transform([vis], [p["age"]], [p["sex"]]).toarray()
            np.testing.assert_array_equal(a, b)

    def test_full_path_matches_reference_every_step(self):
        n_val = 0
        for p in fabricated_patients(self.sem, n=10):
            for Q in (3, 5, 10):
                def on_step(s, k, p=p):
                    self.ref.check_step(s, p["age"], p["sex"])
                tr, s = run_case(BaselineASearcher(self.factory, Q), self.sem, p["initial"], p["age"], p["sex"],
                                 p["tokens"], Q, on_step=on_step)
                self.assertEqual(len(tr.asked), Q)
                n_val += sum(1 for a in tr.answers.values() if a[0].startswith("VALUE::"))
        self.assertGreater(n_val, 0, "범주형 VALUE 답이 한 번도 경로를 지나지 않음")

    def test_reference_catches_corrupted_engine(self):
        p = fabricated_patients(self.sem, n=1)[0]
        class Corrupt(BaselineASearcher):
            def scores(self):
                v = super().scores().copy()
                v[0] += 1e-6
                return v
        with self.assertRaises(Exp01Invalid):
            run_case(Corrupt(self.factory, 3), self.sem, p["initial"], p["age"], p["sex"], p["tokens"], 3,
                     on_step=lambda s, k: self.ref.check_step(s, p["age"], p["sex"]))

    def _fake(self, p, visible, tokens=None, next_q="SAME"):
        """사후확률은 독립 재계산값과 같게, 답 변환 토큰·다음 질문만 바꾼 가짜 탐색기(검사 항목을 따로 시험)."""
        ref = self
        post = self.ref.posterior(5, visible, p["age"], p["sex"])
        nq = self.ref.next_question(post, visible) if next_q == "SAME" else next_q
        class Q:
            evidence_id = nq
        class St:
            def feature_tokens(self_):
                return list((tokens if tokens is not None else visible).items())
        class T:
            state = St()
            next_question = Q() if nq is not None else None
        class Fake:
            budget = 5
            n_asked = 1
            observed = visible
            turn = T()
            def scores(self_):
                return post
        return Fake()

    def test_conversion_check_isolated(self):
        p = fabricated_patients(self.sem, n=1)[0]
        vis = {p["initial"]: ("POS",)}
        self.ref.check_step(self._fake(p, vis), p["age"], p["sex"])           # 정상은 통과
        bad = {p["initial"]: ("NEG",)}
        with self.assertRaises(Exp01Invalid):
            self.ref.check_step(self._fake(p, vis, tokens=bad), p["age"], p["sex"])

    def test_question_check_isolated(self):
        p = fabricated_patients(self.sem, n=1)[0]
        vis = {p["initial"]: ("POS",)}
        good = self.ref.next_question(self.ref.posterior(5, vis, p["age"], p["sex"]), vis)
        other = next(q for q in self.ref.qs if q != good and self.sem.currently_eligible(q, vis))
        with self.assertRaises(Exp01Invalid):
            self.ref.check_step(self._fake(p, vis, next_q=other), p["age"], p["sex"])

    def test_reference_catches_wrong_answer_conversion(self):
        from medmap import patient_state as ps
        p = fabricated_patients(self.sem, n=1)[0]
        class BadConv(BaselineASearcher):
            def observe(self, q, ans):
                if ans == ("NEG",):
                    ans2 = ps.positive()           # 음성을 양성으로 잘못 변환
                    self.turn = self.engine.answer(self.turn, q, ans2)
                    self.observed[q] = ans
                    self.n_asked += 1
                else:
                    super().observe(q, ans)
        with self.assertRaises(Exp01Invalid):
            run_case(BadConv(self.factory, 5), self.sem, p["initial"], p["age"], p["sex"], p["tokens"], 5,
                     on_step=lambda s, k: self.ref.check_step(s, p["age"], p["sex"]))


if __name__ == "__main__":
    unittest.main()
