import unittest

from _v2 import find, ms

POS = ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "EXISTING_SUBTYPE", "NEW_ONTOLOGY_CANDIDATE")


class T(unittest.TestCase):
    def test_appetite_ok(self):
        m = find("입맛은 괜찮아요", "입맛")
        if m is not None and m["status"] in POS:
            self.assertEqual(m["assertion"], "ABSENT")
        self.assertFalse(any(x["model_input"]["polarity"] == "POSITIVE" for x in ms("입맛은 괜찮아요")))

    def test_no_target_no_absent(self):
        for t in ("이제 괜찮아요", "검사 결과는 괜찮아요", "괜찮지 않은 건 아니에요", "괜찮지 않아요"):
            with self.subTest(t=t):
                self.assertFalse([x for x in ms(t) if x["status"] in POS])

    def test_head_ok_belly_pain(self):
        m = find("머리는 괜찮은데 배가 아파요", "배")
        self.assertEqual((m["canonical_id"], m["assertion"]), ("pain", "PRESENT"))

    def test_hedged_low(self):
        for x in ms("숨은 괜찮은 것 같아요"):
            self.assertNotEqual(x["model_input"]["polarity"], "POSITIVE")

    def test_deficit_present(self):
        self.assertEqual(find("입맛이 없어요", "입맛")["assertion"], "PRESENT")


if __name__ == "__main__":
    unittest.main()
