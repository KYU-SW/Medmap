import unittest

from _v2 import find


class T(unittest.TestCase):
    def test_switch(self):
        self.assertEqual(find("아이가 열이 나고 저는 머리가 아파요", "열")["experiencer"], "OTHER_PERSON")
        self.assertEqual(find("아이가 열이 나고 저는 머리가 아파요", "머리")["experiencer"], "PATIENT")
        self.assertFalse(find("엄마가 기침해요", "기침")["model_input"]["eligible"])


if __name__ == "__main__":
    unittest.main()
