"""medmap/stt_stream.py 순수 로직(LocalAgreement-2 · StreamSession · 메시지).

실행: ~/ai_env/bin/python -m unittest tests.test_stt_stream
설계: docs/superpowers/specs/2026-09-30-medmap-realtime-streaming-stt-design.md §2·§6
"""
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from medmap import stt_stream as ss


def pcm(seconds, value=1000):
    return np.full(int(16000 * seconds), value, dtype=np.int16).tobytes()


class LocalAgreementTest(unittest.TestCase):
    def test_commits_only_prefix_agreed_twice(self):
        la = ss.LocalAgreement()
        self.assertEqual(la.update("어제부터 배가"), ("", "어제부터 배가"))
        self.assertEqual(la.update("어제부터 배가 아팠"), ("어제부터 배가", " 아팠"))
        self.assertEqual(la.update("어제부터 배가 아팠는데"), ("어제부터 배가", " 아팠는데"))
        self.assertEqual(la.update("어제부터 배가 아팠는데 오늘은"), ("어제부터 배가 아팠는데", " 오늘은"))

    def test_stable_never_shrinks_even_if_model_revises(self):
        la = ss.LocalAgreement()
        la.update("어제부터 배가 아팠")
        la.update("어제부터 배가 아팠")
        stable, unstable = la.update("어제 부터 배가")        # 모델이 앞부분을 바꿔도
        self.assertEqual(stable, "어제부터 배가 아팠")          # 고정된 prefix 는 유지
        self.assertEqual(unstable, "")

    def test_reset(self):
        la = ss.LocalAgreement()
        la.update("a b")
        la.update("a b")
        la.reset()
        self.assertEqual(la.update("c"), ("", "c"))

    def test_empty_hypothesis(self):
        la = ss.LocalAgreement()
        self.assertEqual(la.update(""), ("", ""))


class StreamSessionTest(unittest.TestCase):
    def test_append_and_close_utterance(self):
        s = ss.StreamSession("x")
        s.append(pcm(1.0))
        s.append(pcm(0.5))
        self.assertAlmostEqual(s.utt_seconds, 1.5, places=3)
        x = s.utterance_pcm()
        self.assertEqual(x.dtype, np.float32)
        self.assertAlmostEqual(float(x.max()), 1000 / 32768, places=5)
        self.assertEqual(s.close_utterance("manual"), 1)
        self.assertEqual(s.utt_seconds, 0.0)
        self.assertEqual(s.utt, 2)
        self.assertEqual(s.utterance_pcm().size, 0)
        self.assertAlmostEqual(s.stream_seconds, 1.5, places=3)

    def test_limits(self):
        s = ss.StreamSession("x", max_stream_s=2.0, max_utt_s=1.0)
        s.append(pcm(1.0))
        with self.assertRaises(ss.StreamLimit) as ctx:
            s.append(pcm(0.1))
        self.assertEqual(ctx.exception.code, "UTTERANCE_TOO_LONG")
        s.close_utterance("max_duration")
        s.append(pcm(0.9))
        with self.assertRaises(ss.StreamLimit) as ctx:
            s.append(pcm(0.2))
        self.assertEqual(ctx.exception.code, "STREAM_TOO_LONG")

    def test_odd_bytes_rejected(self):
        with self.assertRaises(ss.StreamLimit) as ctx:
            ss.StreamSession("x").append(b"\x00")
        self.assertEqual(ctx.exception.code, "AUDIO_INVALID")

    def test_discard_clears_audio(self):
        s = ss.StreamSession("x")
        s.append(pcm(0.5))
        s.discard()
        self.assertTrue(s.closed)
        self.assertEqual(s.utt, 2)                           # 이전 가설과 새 오디오가 짝지어지지 않게
        self.assertEqual(s.utterance_pcm().size, 0)

    def test_messages_have_no_extra_keys(self):
        self.assertEqual(set(ss.partial_msg(1, "a", "b", 900, {"decode": 1.0})),
                         {"type", "utt", "stable", "unstable", "audio_ms", "srv_ms"})
        self.assertEqual(set(ss.final_msg(1, "a", 900, {})), {"type", "utt", "text", "audio_ms", "srv_ms"})
        self.assertEqual(ss.end_msg(2, "manual"), {"type": "utterance_end", "utt": 2, "reason": "manual"})
        self.assertEqual(ss.error_msg("STREAM_OVERLOADED"), {"type": "error", "code": "STREAM_OVERLOADED"})


if __name__ == "__main__":
    unittest.main()
