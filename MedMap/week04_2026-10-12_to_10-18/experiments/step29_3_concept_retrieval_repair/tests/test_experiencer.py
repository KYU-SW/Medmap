import unittest

from _v4 import find


class T(unittest.TestCase):
    def test_patient_vs_family(self):
        self.assertEqual(find("제가 어지러워요", "어지")["experiencer"], "PATIENT")
        self.assertIn(find("엄마가 어지러워요", "어지")["experiencer"], ("OTHER_PERSON", "MULTIPLE"))

    def test_trigger_subject_inherited(self):
        m = find("엄마가 침을 삼킬 때 목이 아파요", "목", "R2")
        self.assertIn(m["experiencer"], ("OTHER_PERSON", "MULTIPLE"))
