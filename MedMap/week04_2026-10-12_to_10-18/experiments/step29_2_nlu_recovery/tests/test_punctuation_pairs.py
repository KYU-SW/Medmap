import unittest

from _v3 import analyze, SEL
from contract_check_v3 import signature

PAIRS = [("열이 났어요 오늘은 괜찮아요", "열이 났어요. 오늘은 괜찮아요."), ("기침이 나요 숨도 차요", "기침이 나요. 숨도 차요."),
         ("기침은 없어요 숨은 차요", "기침은 없어요. 숨은 차요."), ("어제 배가 아팠어요 이제 안 아파요", "어제 배가 아팠어요. 이제 안 아파요.")]


class T(unittest.TestCase):
    def test_same_structure(self):
        for a, b in PAIRS:
            self.assertEqual(signature(analyze(a, SEL)), signature(analyze(b, SEL)), a)


if __name__ == "__main__":
    unittest.main()
