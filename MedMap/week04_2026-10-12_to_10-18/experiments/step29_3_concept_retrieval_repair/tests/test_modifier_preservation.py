import unittest

from _v4 import NEW, autos, find


class T(unittest.TestCase):
    def test_burning_vs_queasy(self):
        for P in NEW:
            self.assertNotIn("nausea", autos("속이 화끈거려요", P), P)
            self.assertNotIn("heartburn", autos("속이 울렁거려요", P), P)

    def test_modifier_recorded(self):
        m = find("머리가 지끈지끈 아파요", "머리", "R2")
        self.assertTrue(any("지끈지끈" in a for a in (m.get("attributes") or [])) or "지끈지끈" in (m.get("normalization") or {}).get("symptom_modifiers", []))
