import unittest

from _nlu import find


class TestExperiencer(unittest.TestCase):
    def test_switch(self):
        self.assertEqual(find("엄마는 기침하고 저는 열이 나요", "기침")["experiencer"], "OTHER_PERSON")
        self.assertEqual(find("엄마는 기침하고 저는 열이 나요", "열")["experiencer"], "PATIENT")

    def test_other_never_model_input(self):
        for t, a in (("엄마가 기침해요", "기침"), ("동생이 열이 나요", "열")):
            m = find(t, a)
            with self.subTest(t=t):
                self.assertIn(m["experiencer"], ("OTHER_PERSON", "MULTIPLE"))
                self.assertFalse(m["model_input"]["eligible"])

    def test_default_marked_assumed(self):
        self.assertEqual(find("기침해요", "기침")["experiencer_basis"], "ASSUMED_INTAKE_DEFAULT")


if __name__ == "__main__":
    unittest.main()
