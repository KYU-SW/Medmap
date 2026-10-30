import unittest

from _v2 import find


class T(unittest.TestCase):
    def test_scope(self):
        self.assertEqual(find("기침은 없지만 가래는 나와요", "기침")["assertion"], "ABSENT")
        self.assertEqual(find("기침은 없지만 가래는 나와요", "가래")["assertion"], "PRESENT")
        self.assertEqual(find("열이나 기침은 없어요", "열")["assertion"], "ABSENT")
        self.assertEqual(find("기침하지 않는 건 아니에요", "기침")["assertion"], "POSSIBLE")


if __name__ == "__main__":
    unittest.main()
