import unittest

from _v4 import NEW, autos


class T(unittest.TestCase):
    def test_no_auto_link(self):
        for P in NEW:
            for t in ("기침약을 먹었어요", "심장 부분", "혈관성 편두통 진단을 받았어요", "날씨가 많이 추워요", "머리 주위"):
                self.assertEqual(autos(t, P), [], (P, t))

    def test_epistemic_not_confusion(self):
        for P in NEW:
            self.assertNotIn("confusion", autos("목은 괜찮은지 헷갈려요", P), P)
