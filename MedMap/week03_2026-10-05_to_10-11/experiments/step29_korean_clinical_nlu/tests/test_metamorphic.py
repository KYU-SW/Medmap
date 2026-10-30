import json
import unittest

import _nlu
from metamorphic import run


class TestMetamorphic(unittest.TestCase):
    def test_rule_consistency(self):
        r = run(_nlu.analyze, "NLU_P5")
        bad = [x for x in r["rows"] if not x["pass"]]
        self.assertEqual(bad, [], json.dumps(r["summary"], ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
