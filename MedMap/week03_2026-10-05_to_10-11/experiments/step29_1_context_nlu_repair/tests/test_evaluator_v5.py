import unittest

import _v2  # noqa: F401
from evaluator_v5 import mention_violations
from validate_evaluator_v5 import KNOWN_BAD, MIXED_OK, M


class T(unittest.TestCase):
    def test_mixed_ok_not_flagged(self):
        for t, mm in MIXED_OK:
            for u, c in mm:
                with self.subTest(t=t, u=u):
                    self.assertEqual(mention_violations(M(t, u, c)), [])

    def test_known_bad_flagged(self):
        for t, u, c, kw in KNOWN_BAD:
            with self.subTest(t=t, c=c):
                self.assertTrue(mention_violations(M(t, u, c, **kw)))

    def test_modal_vomit(self):
        self.assertEqual(mention_violations(M("토할 것 같아요", "토할 것 같아요", "nausea")), [])
        self.assertIn("MODAL_VOMIT_AS_VOMITING", mention_violations(M("토할 것 같아요", "토할 것 같아요", "vomiting")))


if __name__ == "__main__":
    unittest.main()
