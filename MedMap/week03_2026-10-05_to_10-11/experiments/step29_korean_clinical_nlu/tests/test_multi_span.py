import unittest

from _nlu import concept_of, ms


class TestMulti(unittest.TestCase):
    def test_example_three_mentions(self):
        got = [concept_of(m) or m.get("canonical_id") for m in ms("어제부터 코피가 나고 머리가 아파요. 열은 없어요.")]
        self.assertIn("pain", got)
        self.assertIn("fever", got)
        self.assertTrue(any(x in ("HP:0000421", "EV:E_178") for x in got))

    def test_not_first_only(self):
        got = [concept_of(m) for m in ms("기침하고 열이 나요")]
        self.assertIn("cough", got)
        self.assertIn("fever", got)

    def test_relative_clause_primary(self):
        m = ms("누런 가래가 나오는 기침을 해요")
        self.assertTrue(any(x["role"] == "PRIMARY" and concept_of(x) == "cough" for x in m))
        self.assertFalse(any(concept_of(x) == "EV:E_182" for x in m))


if __name__ == "__main__":
    unittest.main()
