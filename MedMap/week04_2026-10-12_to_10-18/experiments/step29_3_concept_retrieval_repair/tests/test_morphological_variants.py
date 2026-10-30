import unittest

from _v4 import NEW, autos


class T(unittest.TestCase):
    def test_neck_endings_consistent(self):
        for P in NEW:
            a, b = autos("목이 아파요", P), autos("목이 아프고", P)
            self.assertEqual(a, b, P)

    def test_negated_form_keeps_concept(self):
        for P in NEW:
            self.assertEqual(autos("숨이 차지 않아요", P), autos("숨이 차요", P), P)

    def test_time_prefix_does_not_drop_symptom(self):
        for P in NEW:
            self.assertIn("nausea", autos("지난주에 속이 메스꺼웠어요", P), P)
