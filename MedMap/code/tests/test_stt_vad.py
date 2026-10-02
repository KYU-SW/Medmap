"""VAD 발화 경계 상태기계 + 환각 문구 가드(순수 로직, 모델 없음).

실행: ~/ai_env/bin/python -m unittest tests.test_stt_vad
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from medmap.stt_vad import Endpointer, filter_hallucination


def run(ep, probs):
    events = []
    for i, p in enumerate(probs):
        events += [(i, e) for e in ep.push(p)]
    return events


class EndpointerTest(unittest.TestCase):
    def test_start_after_96ms_end_after_600ms_silence(self):
        ep = Endpointer(frame_ms=32, silence_ms=600)
        probs = [0.1] * 5 + [0.9] * 20 + [0.1] * 25
        ev = run(ep, probs)
        self.assertEqual(ev[0], (5 + 2, "speech_start"))            # 3 frames = 96 ms
        self.assertEqual(ev[1][1], "speech_end")
        self.assertEqual(ev[1][0], 25 + 18)                           # ceil(600/32)=19 → index 25+18
        self.assertFalse(ep.in_speech)

    def test_short_pause_does_not_split(self):
        ep = Endpointer(frame_ms=32, silence_ms=600)
        ev = run(ep, [0.9] * 10 + [0.1] * 10 + [0.9] * 10 + [0.1] * 20)
        self.assertEqual([e for _, e in ev], ["speech_start", "speech_end"])

    def test_blip_is_not_speech(self):
        self.assertEqual(run(Endpointer(frame_ms=32), [0.9, 0.9, 0.1] * 5), [])

    def test_silence_threshold_configurable(self):
        ev = run(Endpointer(frame_ms=32, silence_ms=320), [0.9] * 5 + [0.1] * 12)
        self.assertEqual(ev[-1], (5 + 9, "speech_end"))

    def test_silence_default_from_env(self):
        import os
        old = os.environ.get("MEDMAP_STT_VAD_SILENCE_MS")
        os.environ["MEDMAP_STT_VAD_SILENCE_MS"] = "320"
        try:
            self.assertEqual(Endpointer().silence_frames, 10)
        finally:
            if old is None:
                del os.environ["MEDMAP_STT_VAD_SILENCE_MS"]
            else:
                os.environ["MEDMAP_STT_VAD_SILENCE_MS"] = old
        self.assertEqual(Endpointer(silence_ms=600).silence_frames, 19)


class HallucinationGuardTest(unittest.TestCase):
    def test_removed_only_when_speech_ratio_low(self):
        self.assertEqual(filter_hallucination("시청해주셔서 감사합니다", 0.1), "")
        self.assertEqual(filter_hallucination("배가 아파요 구독과 좋아요", 0.2), "배가 아파요")
        self.assertEqual(filter_hallucination("시청해주셔서 감사합니다", 0.8), "시청해주셔서 감사합니다")

    def test_manual_mode_unknown_ratio_keeps_text(self):
        self.assertEqual(filter_hallucination("시청해주셔서 감사합니다", None), "시청해주셔서 감사합니다")


if __name__ == "__main__":
    unittest.main()
