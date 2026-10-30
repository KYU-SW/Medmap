import unittest

from _base import item_at, packet


class MultiSpan(unittest.TestCase):
    def check(self, text, surfaces):
        p = packet(text)
        its = [item_at(p, s) for s in surfaces]
        self.assertTrue(all(its), text)
        self.assertEqual(len({i["item_id"] for i in its}), len(surfaces), text)
        spans = sorted((i["span_start"], i["span_end"]) for i in its)
        for (a1, b1), (a2, b2) in zip(spans, spans[1:]):
            self.assertLessEqual(b1, a2, text)
        for i in p["items"]:
            self.assertEqual(i["raw_span"], text[i["span_start"]:i["span_end"]])
        return p

    def test_cases(self):
        self.check("어제부터 코피가 나고 머리가 아파요.", ["코피", "머리가 아파"])
        p = self.check("목이 아프고 숨이 차요.", ["목이 아프", "숨이 차"])
        self.assertEqual(item_at(p, "숨이 차")["canonical_id"], "dyspnea")
        p = self.check("기침약을 먹었는데 기침이 계속 나요.", ["기침약", "기침이 계속"])
        self.assertNotEqual(item_at(p, "기침약")["category"], "A")
        self.check("그제부터 열이 나고 배가 아파요.", ["열이 나", "배가 아파"])


if __name__ == "__main__":
    unittest.main()
