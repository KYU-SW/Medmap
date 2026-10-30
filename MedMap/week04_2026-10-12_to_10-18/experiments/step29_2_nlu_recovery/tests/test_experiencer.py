import unittest

from _v3 import find


class T(unittest.TestCase):
    def test_other_person_not_patient_positive(self):
        m = find("엄마는 기침이 나고 저는 열이 나요", "기침")
        self.assertIn(m["experiencer"], ("OTHER_PERSON", "MULTIPLE"))
        self.assertFalse(m["model_input"]["eligible"] and m["experiencer"] == "PATIENT")
        self.assertEqual(find("엄마는 기침이 나고 저는 열이 나요", "열")["experiencer"], "PATIENT")

    def test_other_person_separate_sentence(self):
        m = find("엄마는 기침이 나요 저는 열이 나요", "기침")
        self.assertIn(m["experiencer"], ("OTHER_PERSON", "MULTIPLE"))


if __name__ == "__main__":
    unittest.main()
