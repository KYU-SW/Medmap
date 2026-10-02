"""발화 완결(turn completion) 등급 — Kiwi(로컬 형태소 분석) + 정규식 fallback. 값(대기 시간)은 없음, 등급만.

실행: ~/ai_env/bin/python -m unittest tests.test_stt_turn
등급: complete(차례를 끝낸 듯) · continuing(연결어미·접속사 — 이어질 듯) · incomplete(조사·간투사·숫자 꼬리 — 미완)
      · ambiguous(명사로 끝남·"-는데요"·"-고요" 등 — 데이터로 정할 것) · unknown(빈 텍스트)
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from medmap import stt_turn


def label(text):
    return stt_turn.classify(text).label


class KiwiTurnCompletionTest(unittest.TestCase):
    def test_complete_final_endings_and_short_answers(self):
        for text in ["오늘 두 번 토했어요.", "두 번이요.", "오른쪽이요.", "사흘 전부터요.", "오늘 아침에 두 번 정도요.",
                     "38.5도예요.", "네.", "아니요.", "토했습니다.", "아프거든요.", "아프죠?", "어제는 좀 있었는데 오늘은 괜찮아요."]:
            with self.subTest(text=text):
                self.assertEqual(label(text), "complete")

    def test_continuing_connective_endings_and_conjunctions(self):
        for text in ["오늘 두 번 토했는데", "배가 아팠는데…", "열은 없고", "기침하고", "그리고", "오한은 없어요 그리고", "약을 먹었는데"]:
            with self.subTest(text=text):
                self.assertEqual(label(text), "continuing")

    def test_incomplete_particles_fillers_and_numeric_tails(self):
        for text in ["열은…", "어제부터… 음…", "통증은… 한…", "삼십팔 점", "혈압이 백이십에", "그게…", "그게… 뭐랄까…",
                     "아침에 쟀을 때…", "어…"]:
            with self.subTest(text=text):
                self.assertEqual(label(text), "incomplete")

    def test_ambiguous_left_for_data(self):
        for text in ["배가 좀 아팠는데요.", "밤새 잠을 못 잤고요,", "삼십팔 도", "오른쪽", "체온은 삼십칠 도 오 부고요,"]:
            with self.subTest(text=text):
                self.assertEqual(label(text), "ambiguous")

    def test_number_never_complete_when_cut_inside(self):
        self.assertEqual(label("열이 삼십팔 점"), "incomplete")        # "…오 도" 앞에서 끊기면 안 됨
        self.assertEqual(label("삼십팔 점 오 도예요"), "complete")

    def test_empty_is_unknown_and_source_reported(self):
        self.assertEqual(label(""), "unknown")
        self.assertEqual(label("   "), "unknown")
        result = stt_turn.classify("두 번이요.")
        self.assertIn(result.source, ("kiwi",))
        self.assertTrue(result.reason)


class RegexFallbackTest(unittest.TestCase):
    def test_regex_rules(self):
        cases = {"토했어요": "complete", "네": "complete", "아팠는데": "continuing", "그리고": "continuing",
                 "음": "incomplete", "삼십팔 점": "incomplete", "아팠는데요": "ambiguous", "": "unknown"}
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(stt_turn.classify_regex(text).label, expected)
                self.assertEqual(stt_turn.classify_regex(text).source, "regex")

    def test_analyzer_failure_falls_back_to_regex(self):
        class Broken:
            def tokenize(self, text):
                raise RuntimeError("boom")
        stt_turn.set_analyzer_for_tests(Broken())
        try:
            result = stt_turn.classify("오늘 두 번 토했는데")
        finally:
            stt_turn.set_analyzer_for_tests(None)
        self.assertEqual((result.label, result.source), ("continuing", "regex"))

    def test_disabled_by_env_uses_regex(self):
        stt_turn.set_analyzer_for_tests(False)                        # False = Kiwi 사용 안 함(로드 실패와 같음)
        try:
            self.assertEqual(stt_turn.classify("두 번이요").source, "regex")
        finally:
            stt_turn.set_analyzer_for_tests(None)


if __name__ == "__main__":
    unittest.main()
