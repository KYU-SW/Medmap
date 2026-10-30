import unittest

from _nlu import find

CASES = [("열이 없어요", "열", "ABSENT"), ("기침은 안 해요", "기침", "ABSENT"), ("토하지 않았어요", "토하", "ABSENT"), ("숨이 차지 않아요", "숨", "ABSENT"),
         ("어지럽지는 않아요", "어지럽", "ABSENT"), ("통증이 전혀 없어요", "통증", "ABSENT"), ("기침하지 않는 건 아니에요", "기침", "POSSIBLE"),
         ("열이 없는 건 아닌 것 같아요", "열", "POSSIBLE"), ("속이 안 좋아요", "속", "PRESENT"), ("토할 것 같아요", "토할", "PRESENT")]


class TestNegation(unittest.TestCase):
    def test_cases(self):
        for t, a, want in CASES:
            m = find(t, a)
            with self.subTest(t=t):
                self.assertIsNotNone(m)
                self.assertEqual(m["assertion"], want)

    def test_scope_per_clause(self):
        self.assertEqual(find("기침은 없지만 가래는 나와요", "기침")["assertion"], "ABSENT")
        self.assertEqual(find("기침은 없지만 가래는 나와요", "가래")["assertion"], "PRESENT")
        self.assertEqual(find("열은 없는데 기침은 계속 나요", "기침")["assertion"], "PRESENT")


if __name__ == "__main__":
    unittest.main()
