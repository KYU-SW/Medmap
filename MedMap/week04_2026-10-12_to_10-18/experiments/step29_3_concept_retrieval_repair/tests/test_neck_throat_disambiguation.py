import unittest

from _v4 import NEW, autos


class T(unittest.TestCase):
    def test_neck_back_not_sore_throat(self):
        for P in NEW:
            self.assertNotIn("sore_throat", autos("목 뒤가 아파요", P), P)

    def test_swallow_is_throat(self):
        for P in NEW:
            self.assertNotIn("pain", autos("침 삼킬 때 목이 아파요", P), P)
