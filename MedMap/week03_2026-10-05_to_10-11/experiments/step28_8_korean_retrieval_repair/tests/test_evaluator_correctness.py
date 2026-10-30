"""검사기 v3 정답 대조(지시문 §2 필수 사례 + 정답 세트 오판 0). 노출 사례 — 단위·회귀 테스트일 뿐."""
import unittest

import _engine  # noqa: F401  (경로)
from evaluator import violations
from validate_evaluator import MUST_FLAG, MUST_PASS, gold_pairs


class TestEvaluator(unittest.TestCase):
    def test_must_flag(self):
        for t, cs in MUST_FLAG:
            with self.subTest(t=t, cs=cs):
                self.assertTrue(violations(t, cs))

    def test_must_pass(self):
        for t, cs in MUST_PASS:
            with self.subTest(t=t, cs=cs):
                self.assertEqual(violations(t, cs), [])

    def test_gold_pairs_never_flagged(self):
        bad = [(s, t, cs) for s, t, cs in gold_pairs() if violations(t, cs)]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
