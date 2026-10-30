"""부분 문자열 오매칭 차단(STEP28.7 위험 사례·지시문 예시 — 노출 사례 회귀 테스트). P3(수정 KO) 기준 auto 금지 concept."""
import unittest

import _engine

CASES = [("외 음 부 근", "palpitations"), ("치아 주위", "dizziness"), ("감각의 이상을", "EV:E_178"), ("경추성 어지럼증의", "dizziness"),
         ("혈관성 편두통", "pain"), ("기침 억제제", "cough")]


class TestSubstring(unittest.TestCase):
    def test_no_auto_from_substring(self):
        for t, bad in CASES:
            for p in ("P3", "P5"):
                with self.subTest(t=t, p=p):
                    self.assertNotIn(bad, _engine.autos(t, p))

    def test_one_char_head_key_not_used(self):
        from repair_korean_matching import RepairedRetriever  # noqa: F401
        o = _engine.engine().R
        sp = {"noun_phrase": "외 음 부 근", "head_noun": "근", "pred_class": "NONE", "query_ko": "외 음 부 근", "span_text": "외 음 부 근", "predicate": ""}
        self.assertNotIn("근", o.rkeys(sp))


if __name__ == "__main__":
    unittest.main()
