import unittest

from _v4 import NEW, ms


class T(unittest.TestCase):
    def test_new_never_model_input(self):
        for P in NEW:
            for t in ("손이 떨려요", "재채기가 나와요", "코피가 났어요"):
                for m in ms(t, P):
                    self.assertFalse(m["status"] in ("NEW_ONTOLOGY_CANDIDATE", "EXISTING_SUBTYPE") and m["model_input"]["eligible"], (P, t))

    def test_not_applied(self):
        for m in ms("열이 나요"):
            self.assertFalse(m["model_input"]["applied"])
