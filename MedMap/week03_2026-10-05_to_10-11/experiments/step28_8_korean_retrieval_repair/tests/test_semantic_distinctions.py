"""P5 출력이 구별 규칙을 어기지 않는지(코피·구토·떨림·고혈압·기침 억제제). 노출 probe."""
import unittest

import _engine
from evaluator import violations

CASES = ["코피", "코피가 나요", "토했어요", "구토", "떨림", "고혈압", "기침 억제제", "메스꺼워요", "토할 것 같아요", "몸이 덜덜 떨려요"]


class TestDistinctions(unittest.TestCase):
    def test_no_violation_auto_or_display(self):
        for t in CASES:
            rs = _engine.run(t)
            auto = [o["canonical_id"] for o in rs if o["status"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")]
            disp = [c for o in rs for c in o["display"]]
            with self.subTest(t=t, auto=auto, disp=disp):
                self.assertEqual(violations(t, auto + disp), [])

    def test_epistaxis_not_bleeding_synonym(self):
        self.assertNotIn("hemoptysis", _engine.autos("코피가 나요"))
        self.assertNotIn("hematemesis", _engine.autos("코피가 나요"))


if __name__ == "__main__":
    unittest.main()
