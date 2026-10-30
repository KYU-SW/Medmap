import unittest

from _v3 import find, ms


class T(unittest.TestCase):
    def test_silver_not_model_input(self):
        for t in ("코피가 나요", "재채기가 나요"):
            for m in ms(t):
                self.assertFalse(m["status"] in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE") and m["model_input"]["eligible"], t)

    def test_resolved_not_current_positive(self):
        m = find("열이 났어요 오늘은 괜찮아요", "열")
        self.assertFalse(m["model_input"]["eligible"] and m["model_input"]["polarity"] == "POSITIVE")

    def test_model_input_not_applied(self):
        for m in ms("기침이 나요"):
            self.assertFalse(m["model_input"]["applied"])


if __name__ == "__main__":
    unittest.main()
