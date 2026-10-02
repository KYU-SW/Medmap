"""실제 Whisper 로 streaming 경로 통합 테스트 + 서버 측 지연 측정(실시간 속도 재생).

기본 skip. `MEDMAP_STT_REAL=1` 이고 `stt/samples/medmap_tts_test.wav` 가 있을 때만 실행(기존 GPU 게이트와 같은 조건:
`~/scripts/wait_for_resources.sh --check` 가 OK 일 때).

측정(숫자만 출력, 텍스트 없음):
  T_partial_srv = 각 오디오 시점 τ(100 ms 간격)가 처음 담긴 partial 이 서버에서 나간 시각 − τ(실시간 재생 기준).
                  틱 사이 대기 + 큐 + decode 를 모두 포함한다(발화 마지막 구간은 partial 이 없으면 제외 — FINAL 이 담당)
  T_final_srv   = final 이 나간 시각 − stop 시각
브라우저 캡처·네트워크·렌더는 포함하지 않는다(그건 e2e 에서 잰다).

실행: MEDMAP_STT_REAL=1 ~/ai_env/bin/python -m unittest tests.test_stt_stream_whisper_integration -v
"""
import asyncio
import json
import os
import sys
import time
import unittest
import warnings
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

SAMPLE_WAV = ROOT / "stt" / "samples" / "medmap_tts_test.wav"
REAL_ENABLED = os.environ.get("MEDMAP_STT_REAL") == "1"
PACKET_MS = 100
RUNS = int(os.environ.get("MEDMAP_STREAM_RUNS", "5"))


def pct(values, q):
    return round(float(np.percentile(values, q)), 1) if values else None


async def play(stream_cls, speech, pcm16: bytes):
    """pcm16 을 100 ms 패킷으로 실시간 속도로 흘리고 stop. (메시지, 방출 시각) 목록과 stop 시각을 돌려준다."""
    events = []
    t0 = time.perf_counter()

    async def emit(msg):
        events.append((time.perf_counter() - t0, msg))

    stream = stream_cls("bench", emit)
    step = int(16000 * PACKET_MS / 1000) * 2
    for i, start in enumerate(range(0, len(pcm16), step)):
        target = (i + 1) * PACKET_MS / 1000                 # 이 패킷의 끝이 마이크에 들어온 시각
        await asyncio.sleep(max(0.0, target - (time.perf_counter() - t0)))
        await stream.feed(pcm16[start:start + step])
    t_stop = time.perf_counter() - t0
    await stream.finalize("manual")                       # 실제 서버처럼 stop 즉시(진행 중 partial 은 finalize 가 처리)
    stream.close()
    return events, t_stop


@unittest.skipUnless(REAL_ENABLED, "MEDMAP_STT_REAL=1 이 아니면 skip(GPU 게이트)")
@unittest.skipUnless(SAMPLE_WAV.exists(), f"sample wav not found: {SAMPLE_WAV}")
class StreamingWhisperIntegration(unittest.TestCase):
    def test_streaming_partials_final_equals_batch_and_latency(self):
        from medmap import api_stt_stream as st
        from medmap import speech

        st.set_transcribe_for_tests(None)
        audio, duration = speech.decode_audio(SAMPLE_WAV.read_bytes())
        pcm16 = (np.clip(audio, -1, 1) * 32767).astype("<i2").tobytes()
        transcriber = speech.get_transcriber()
        cold_start = time.perf_counter()
        batch_text = transcriber.transcribe(np.frombuffer(pcm16, dtype="<i2").astype(np.float32) / 32768.0)
        cold_ms = (time.perf_counter() - cold_start) * 1000

        t_partial, t_final, decode_ms, n_partials, reused = [], [], [], [], []
        for run in range(RUNS):
            st._scheduler = None
            events, t_stop = asyncio.run(play(st._Stream, speech, pcm16))
            partials = [(t, m) for t, m in events if m["type"] == "partial"]
            finals = [(t, m) for t, m in events if m["type"] == "final"]
            self.assertTrue(partials, "no partial while speaking")
            self.assertEqual(len(finals), 1)
            stables = [m["stable"] for _, m in partials]
            for a, b in zip(stables, stables[1:]):
                self.assertTrue(b.startswith(a), "stable prefix shrank")
            self.assertEqual(finals[0][1]["text"], batch_text, "streaming FINAL != batch transcribe (same model)")
            for t, m in partials:
                self.assertTrue(set(m) == {"type", "utt", "stable", "unstable", "audio_ms", "srv_ms"})
                if run > 0:
                    decode_ms.append(m["srv_ms"]["decode"])
            if run > 0:                                       # 첫 run 은 warm-up
                # T_partial: 각 오디오 시점 τ(패킷 끝, 0.3 s 이후 = 최소 발화 길이)가 처음으로 화면에 보이는 partial
                # (audio_ms ≥ τ)까지의 시간. 틱 사이에 말한 소리가 다음 틱을 기다리는 시간까지 포함한다.
                for k in range(3, int(duration * 1000 // PACKET_MS) + 1):
                    tau = k * PACKET_MS
                    shown = [t for t, m in partials if m["audio_ms"] >= tau]
                    if shown:
                        t_partial.append(shown[0] * 1000 - tau)
            if run > 0:
                t_final.append((finals[0][0] - t_stop) * 1000)
                reused.append(bool(finals[0][1]["srv_ms"].get("reused")))
                n_partials.append(len(partials))
        report = {
            "sample_duration_s": round(duration, 2), "runs_measured": RUNS - 1, "packet_ms": PACKET_MS,
            "first_transcribe_ms_incl_load": round(cold_ms, 1),
            "T_partial_srv_ms": {"p50": pct(t_partial, 50), "p95": pct(t_partial, 95), "n": len(t_partial)},
            "partial_decode_ms": {"p50": pct(decode_ms, 50), "p95": pct(decode_ms, 95)},
            "T_final_srv_ms": {"p50": pct(t_final, 50), "p95": pct(t_final, 95), "n": len(t_final)},
            "final_reused": reused,
            "partials_per_utterance": n_partials,
        }
        print("STREAM_PERF " + json.dumps(report))
        out = os.environ.get("MEDMAP_PERF_OUT")
        if out:
            Path(out).write_text(json.dumps(report, indent=1), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
