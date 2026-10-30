import unittest

from _v4 import NEW, autos


class T(unittest.TestCase):
    def test_vomit_not_hematemesis(self):
        for P in NEW:
            for t in ("토했", "오바이트했어요", "토했어요"):
                self.assertNotIn("hematemesis", autos(t, P), (P, t))

    def test_blood_vomit(self):
        for P in NEW:
            self.assertIn("hematemesis", autos("피를 토했어요", P), P)

    def test_modal_is_not_vomiting(self):
        for P in NEW:
            self.assertNotIn("vomiting", autos("토할 것 같아요", P), P)
