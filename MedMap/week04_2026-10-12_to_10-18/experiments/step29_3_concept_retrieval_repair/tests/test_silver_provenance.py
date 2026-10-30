import unittest

from _v4 import find


class T(unittest.TestCase):
    def test_silver_kept_separate(self):
        m = find("재채기가 나와요", "재채기", "R2")
        self.assertEqual(m["status"], "NEW_ONTOLOGY_CANDIDATE")
        self.assertEqual(m.get("evidence_sources"), "SILVER")
        self.assertFalse(m["model_input"]["eligible"])

    def test_hand_tremor_not_chills(self):
        m = find("손이 떨려요", "손", "R2")
        self.assertNotEqual(m.get("canonical_id"), "chills")
