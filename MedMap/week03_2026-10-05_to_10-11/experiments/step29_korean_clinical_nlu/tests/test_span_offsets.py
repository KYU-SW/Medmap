import unittest

from _nlu import load, ms

EXTRA = ["어제부터 코피가 나고  머리가 아파요. 열은 없어요.", "기침, 가래가 있어요!", "숨이 차요\n열은 없어요", "토했어요...  그리고 어지러워요"]


class TestOffsets(unittest.TestCase):
    def test_raw_span_equals_slice(self):
        for t in [c["text"] for c in load()["contracts"]] + EXTRA:
            for m in ms(t):
                with self.subTest(t=t, span=m["raw_span"]):
                    self.assertEqual(t[m["span_start"]:m["span_end"]], m["raw_span"])
                    self.assertTrue(0 <= m["span_start"] < m["span_end"] <= len(t))
                    self.assertIn(m["raw_span"], m["source_sentence"])
                    self.assertEqual(m["source_text"], t)


if __name__ == "__main__":
    unittest.main()
