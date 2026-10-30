import unittest

from _v4 import find


class T(unittest.TestCase):
    def test_concept_and_assertion_separate(self):
        self.assertEqual(find("기침해요", "기침")["assertion"], "PRESENT")
        m = find("기침하지 않아요", "기침")
        self.assertEqual(m["assertion"], "ABSENT")
        self.assertFalse(m["model_input"]["eligible"] and m["model_input"]["polarity"] == "POSITIVE")
