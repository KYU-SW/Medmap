import unittest

import _v3  # noqa: F401
from asr_sentence_segmenter import sentences


def texts(t):
    return [o["text"] for o in sentences(t)]


class T(unittest.TestCase):
    def test_ef_boundary_without_period(self):
        self.assertEqual(texts("열이 났어요 오늘은 괜찮아요"), ["열이 났어요", "오늘은 괜찮아요"])
        self.assertEqual(texts("기침이 나요 숨도 차요"), ["기침이 나요", "숨도 차요"])
        self.assertEqual(texts("기침은 없어요 숨은 차요"), ["기침은 없어요", "숨은 차요"])

    def test_period_same_subsentences(self):
        self.assertEqual(texts("열이 났어요. 오늘은 괜찮아요."), texts("열이 났어요 오늘은 괜찮아요"))

    def test_connective_not_split(self):
        self.assertEqual(texts("어제부터 기침하고 오늘은 열이 나요"), ["어제부터 기침하고 오늘은 열이 나요"])
        self.assertEqual(texts("머리가 아팠는데 지금은 괜찮아요"), ["머리가 아팠는데 지금은 괜찮아요"])

    def test_quotative_not_split(self):
        self.assertEqual(len(sentences("엄마가 아프다고 해요")), 1)

    def test_yo_after_connective(self):
        self.assertEqual(texts("기침이 나고요 열도 나요"), ["기침이 나고요", "열도 나요"])

    def test_offsets_are_source_slices(self):
        t = "음 기침이 나요 그리고 열이 나요"
        for o in sentences(t):
            self.assertEqual(o["text"], t[o["start"]:o["end"]])

    def test_question_mark_kept(self):
        self.assertTrue(sentences("열이 나요 병원에 가야 하나요?")[-1]["text"].endswith("?"))


if __name__ == "__main__":
    unittest.main()
