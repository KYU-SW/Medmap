"""POST /v1/stt/transcribe 계약 — audio→transcript 뿐, 매퍼·세션·GPU와 무관.

실측 근거: 이 환경(av 18.1.0)에서 PyAV encode→decode 라운드트립이 실제로 확인된 5개 형식
(wav/pcm_s16le, webm/libopus, ogg/libopus, mp4/aac, mp3/libmp3lame)만 이 테스트에서 검증하고,
그 결과가 `medmap.speech.ALLOWED_MIME`과 일치하는지 확인한다(추측이 아니라 라운드트립 성공 여부로
allowlist를 정한다). 실제 Whisper 모델은 로드하지 않는다(가짜 transcriber만 사용, GPU 게이트).

실행: ~/ai_env/bin/python -m unittest tests.test_stt_api -v
"""
import io
import logging
import sys
import threading
import time
import unittest
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

import av
import numpy as np
from fastapi.testclient import TestClient

from medmap import api as api_module
from medmap import speech

CLIENT = TestClient(api_module.app)
ENDPOINT = "/v1/stt/transcribe"

# MIME → (container format, codec) 후보. 라운드트립이 성공한 것만 여기 남기고
# ALLOWED_MIME과의 일치는 test_00에서 확인한다.
CANDIDATE_FORMATS = {
    "audio/wav": ("wav", "pcm_s16le"),
    "audio/webm": ("webm", "libopus"),
    "audio/ogg": ("ogg", "libopus"),
    "audio/mp4": ("mp4", "aac"),
    "audio/mpeg": ("mp3", "libmp3lame"),
}


def setUpModule():
    CLIENT.__enter__()          # lifespan 실행(Whisper 아님, 기존 엔진만 로드)


def tearDownModule():
    CLIENT.__exit__(None, None, None)


def synth_tone(seconds=1.0, freq=440.0, amp=0.3, sr=speech.SR):
    t = np.arange(int(seconds * sr), dtype=np.float32) / sr
    return (amp * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def encode(container_format, codec_name, seconds=1.0, freq=440.0, amp=0.3, sr=speech.SR):
    """PyAV로 메모리에서만 합성·인코드한다(디스크에 쓰지 않는다)."""
    x = synth_tone(seconds, freq, amp, sr)
    buf = io.BytesIO()
    out = av.open(buf, mode="w", format=container_format)
    stream = out.add_stream(codec_name, rate=sr, layout="mono")
    resampler = av.AudioResampler(format="fltp", layout="mono", rate=sr)
    frame = av.AudioFrame.from_ndarray(x.reshape(1, -1), format="fltp", layout="mono")
    frame.sample_rate = sr
    for rframe in resampler.resample(frame):
        rframe.pts = None
        for packet in stream.encode(rframe):
            out.mux(packet)
    for packet in stream.encode(None):
        out.mux(packet)
    out.close()
    return buf.getvalue()


def decode_roundtrip(data):
    """probe에서 쓴 것과 같은 방식으로 직접 디코드(참고용 — 실제 검증은 speech.decode_audio가 한다)."""
    return speech.decode_audio(data)


class FakeTranscriber:
    """실제 Whisper를 대신한다. GPU/모델 로드 없음."""

    def __init__(self, text="가짜 전사 결과"):
        self.text = text
        self.calls = 0
        self.thread_names = []

    def transcribe(self, x):
        self.calls += 1
        self.thread_names.append(threading.current_thread().name)
        return self.text


def post_audio(data, content_type, headers=None):
    h = {"content-type": content_type}
    if headers:
        h.update(headers)
    return CLIENT.post(ENDPOINT, content=data, headers=h)


class AllowedMimeRoundTripTests(unittest.TestCase):
    """ALLOWED_MIME은 이 환경에서 실제로 encode→decode가 성공한 형식만 남긴다."""

    def test_00_roundtrip_matches_allowed_mime(self):
        results = {}
        for mime, (fmt, codec) in CANDIDATE_FORMATS.items():
            try:
                data = encode(fmt, codec)
                x, duration = speech.decode_audio(data)
                results[mime] = (True, x.size, duration, None)
            except Exception as exc:                       # pragma: no cover - 진단용
                results[mime] = (False, None, None, f"{type(exc).__name__}: {exc}")
        ok = {mime for mime, r in results.items() if r[0]}
        failed = {mime: r[3] for mime, r in results.items() if not r[0]}
        # 실측 결과(이 환경, av 18.1.0): 5개 후보 전부 라운드트립 성공.
        self.assertEqual(failed, {}, f"round-trip failures: {failed}")
        self.assertEqual(ok, set(CANDIDATE_FORMATS), f"round trip results: {results}")
        # audio/x-wav는 audio/wav와 동일 바이트를 별칭으로만 취급(자체 인코더 없음).
        self.assertEqual(speech.ALLOWED_MIME, ok | {"audio/x-wav"})


class SttTranscribeTests(unittest.TestCase):
    def test_01_valid_each_allowed_mime(self):
        for mime, (fmt, codec) in CANDIDATE_FORMATS.items():
            with self.subTest(mime=mime):
                data = encode(fmt, codec, seconds=1.0)
                fake = FakeTranscriber(text=f"transcript-for-{mime}")
                with patch.object(api_module.speech, "get_transcriber", return_value=fake):
                    response = post_audio(data, mime)
                self.assertEqual(response.status_code, 200, response.text)
                body = response.json()
                self.assertEqual(set(body), {"transcript", "duration_s", "language"})
                self.assertEqual(body["transcript"], f"transcript-for-{mime}")
                self.assertEqual(body["language"], "ko")
                self.assertIsInstance(body["duration_s"], float)
                self.assertAlmostEqual(body["duration_s"], round(body["duration_s"], 2))
                self.assertGreater(body["duration_s"], 0.0)
                self.assertEqual(fake.calls, 1)

    def test_02_x_wav_alias_of_wav(self):
        data = encode(*CANDIDATE_FORMATS["audio/wav"], seconds=1.0)
        fake = FakeTranscriber(text="x-wav ok")
        with patch.object(api_module.speech, "get_transcriber", return_value=fake):
            response = post_audio(data, "audio/x-wav")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["transcript"], "x-wav ok")

    def test_03_empty_body_422(self):
        fake = FakeTranscriber()
        with patch.object(api_module.speech, "get_transcriber", return_value=fake):
            response = post_audio(b"", "audio/wav")
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["error"]["code"], "AUDIO_EMPTY")
        self.assertEqual(fake.calls, 0)

    def test_04_corrupt_bytes_422(self):
        fake = FakeTranscriber()
        with patch.object(api_module.speech, "get_transcriber", return_value=fake):
            response = post_audio(b"this is not a real audio container" * 20, "audio/wav")
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["error"]["code"], "AUDIO_DECODE_ERROR")
        self.assertEqual(fake.calls, 0)

    def test_05_unsupported_mime_415(self):
        data = encode(*CANDIDATE_FORMATS["audio/wav"])
        response = post_audio(data, "audio/flac")
        self.assertEqual(response.status_code, 415, response.text)
        self.assertEqual(response.json()["error"]["code"], "UNSUPPORTED_AUDIO_TYPE")

    def test_06_mime_parameter_is_normalized(self):
        data = encode(*CANDIDATE_FORMATS["audio/webm"])
        fake = FakeTranscriber(text="param ok")
        with patch.object(api_module.speech, "get_transcriber", return_value=fake):
            response = post_audio(data, "audio/webm;codecs=opus")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["transcript"], "param ok")

    def test_07_content_length_precheck_413(self):
        """선언된 Content-Length가 클 때 실제 스트림을 읽기 전에 즉시 413."""
        fake = FakeTranscriber()

        def tiny_gen():
            yield b"x" * 16

        huge = speech.MAX_BYTES + 1
        with patch.object(api_module.speech, "get_transcriber", return_value=fake):
            response = CLIENT.post(ENDPOINT, content=tiny_gen(),
                                   headers={"content-type": "audio/wav", "content-length": str(huge)})
        self.assertEqual(response.status_code, 413, response.text)
        self.assertEqual(response.json()["error"]["code"], "AUDIO_TOO_LARGE")
        self.assertEqual(fake.calls, 0)

    def test_08_streaming_over_2mb_aborts_413(self):
        """Content-Length 없이(chunked) 실제 2MB를 넘기면 누적 도중 즉시 413."""
        fake = FakeTranscriber()

        def big_gen():
            chunk = b"y" * 65536
            total = 0
            budget = speech.MAX_BYTES + 65536 * 4
            while total < budget:
                yield chunk
                total += len(chunk)

        with patch.object(api_module.speech, "get_transcriber", return_value=fake):
            response = CLIENT.post(ENDPOINT, content=big_gen(), headers={"content-type": "audio/wav"})
        self.assertEqual(response.status_code, 413, response.text)
        self.assertEqual(response.json()["error"]["code"], "AUDIO_TOO_LARGE")
        self.assertEqual(fake.calls, 0)

    def test_09_duration_over_60s_413(self):
        """61초 저비트레이트 webm/opus는 2MB 아래로 들어오지만 AUDIO_TOO_LONG이어야 한다."""
        data = encode("webm", "libopus", seconds=61.0)
        self.assertLess(len(data), speech.MAX_BYTES, "테스트 전제: 61s opus는 2MB 미만이어야 duration 게이트만 본다")
        fake = FakeTranscriber()
        with patch.object(api_module.speech, "get_transcriber", return_value=fake):
            response = post_audio(data, "audio/webm")
        self.assertEqual(response.status_code, 413, response.text)
        self.assertEqual(response.json()["error"]["code"], "AUDIO_TOO_LONG")
        self.assertEqual(fake.calls, 0)

    def test_10_silence_422(self):
        data = encode("wav", "pcm_s16le", seconds=1.0, amp=0.0)
        fake = FakeTranscriber()
        with patch.object(api_module.speech, "get_transcriber", return_value=fake):
            response = post_audio(data, "audio/wav")
        self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(response.json()["error"]["code"], "AUDIO_EMPTY")
        self.assertEqual(fake.calls, 0)

    def test_11_mapper_not_called(self):
        """STT는 medmap.intake를 호출하지 않는다. 호출되면 즉시 실패하도록 raise로 감시한다."""
        data = encode(*CANDIDATE_FORMATS["audio/wav"])
        fake = FakeTranscriber(text="mapper must stay untouched")
        with patch.object(api_module, "intake_extract",
                          side_effect=AssertionError("STT must not call the intake mapper")):
            with patch.object(api_module.speech, "get_transcriber", return_value=fake):
                response = post_audio(data, "audio/wav")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["transcript"], "mapper must stay untouched")

    def test_12_response_shape_is_session_independent(self):
        data = encode(*CANDIDATE_FORMATS["audio/wav"])
        fake = FakeTranscriber(text="no session needed")
        with patch.object(api_module.speech, "get_transcriber", return_value=fake):
            response = post_audio(data, "audio/wav")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(set(body), {"transcript", "duration_s", "language"})
        self.assertNotIn("session", body)

    def test_13_transcript_is_never_logged(self):
        marker = "MARKER_9f8c2e_do_not_leak_this_transcript"
        data = encode(*CANDIDATE_FORMATS["audio/wav"])
        fake = FakeTranscriber(text=marker)
        with self.assertLogs("medmap", level=logging.DEBUG) as captured:
            with patch.object(api_module.speech, "get_transcriber", return_value=fake):
                response = post_audio(data, "audio/wav")
            logging.getLogger("medmap").debug("keepalive so assertLogs always has >=1 record")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["transcript"], marker)
        for record in captured.records:
            self.assertNotIn(marker, record.getMessage())

    def test_14_transcribe_runs_on_worker_thread(self):
        """anyio.to_thread.run_sync는 이름이 'AnyIO worker thread'인 스레드에서 실행한다(anyio 내부 계약,
        _backends/_asyncio.py의 WorkerThread.__init__). event loop 스레드에서 직접 돌리지 않았다는
        증거로 이 스레드 이름을 확인한다."""
        data = encode(*CANDIDATE_FORMATS["audio/wav"])
        fake = FakeTranscriber(text="thread check")
        with patch.object(api_module.speech, "get_transcriber", return_value=fake):
            response = post_audio(data, "audio/wav")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(fake.calls, 1)
        self.assertEqual(len(fake.thread_names), 1)
        self.assertTrue(fake.thread_names[0].startswith("AnyIO worker thread"),
                        fake.thread_names[0])
        self.assertNotEqual(fake.thread_names[0], threading.current_thread().name)


class WhisperTranscriberLazyLoadTests(unittest.TestCase):
    """speech.WhisperTranscriber 자체 단위 테스트(HTTP 무관). 실제 transformers/Whisper를 로드하지 않는다."""

    @staticmethod
    def _make_counting_loader(delay=0.0):
        calls = {"n": 0}
        lock = threading.Lock()

        def fake_pipeline(x, **kwargs):
            return {"text": "ok"}

        def loader():
            if delay:
                time.sleep(delay)
            with lock:
                calls["n"] += 1
            return fake_pipeline

        return loader, calls

    def test_15_not_loaded_before_first_transcribe(self):
        loader, calls = self._make_counting_loader()
        transcriber = speech.WhisperTranscriber(loader=loader)
        self.assertEqual(calls["n"], 0)
        x = np.zeros(1000, dtype=np.float32)
        transcriber.transcribe(x)
        self.assertEqual(calls["n"], 1)
        for _ in range(3):
            transcriber.transcribe(x)
        self.assertEqual(calls["n"], 1)

    def test_16_concurrent_first_calls_load_once(self):
        loader, calls = self._make_counting_loader(delay=0.02)
        transcriber = speech.WhisperTranscriber(loader=loader)
        x = np.zeros(1000, dtype=np.float32)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: transcriber.transcribe(x), range(8)))
        self.assertEqual(calls["n"], 1)


class SttReviewFollowupTests(unittest.TestCase):
    """리뷰 후속: 로드 실패 503·재시도, 미지정/대문자 Content-Type."""

    def test_17_loader_failure_maps_unavailable_and_retries(self):
        n = {"c": 0}

        def loader():
            n["c"] += 1
            if n["c"] == 1:
                raise RuntimeError("CUDA out of memory")
            return lambda x, **k: {"text": " ok "}

        t = speech.WhisperTranscriber(loader=loader)
        with self.assertRaises(speech.TranscriberUnavailable):
            t.transcribe(np.zeros(10, np.float32))
        self.assertEqual(t.transcribe(np.zeros(10, np.float32)), "ok")
        self.assertEqual(n["c"], 2)

    def test_18_unavailable_is_503(self):
        class Bad:
            def transcribe(self, x):
                raise speech.TranscriberUnavailable("x")

        with patch.object(api_module.speech, "get_transcriber", return_value=Bad()):
            r = post_audio(encode("wav", "pcm_s16le"), "audio/wav")
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (503, "STT_UNAVAILABLE"))

    def test_19_missing_and_uppercase_content_type(self):
        r = CLIENT.post(ENDPOINT, content=b"abc")
        self.assertEqual(r.status_code, 415)
        self.assertIsNone(r.json()["error"]["field"])
        fake = FakeTranscriber(text="u")
        with patch.object(api_module.speech, "get_transcriber", return_value=fake):
            r = post_audio(encode("wav", "pcm_s16le"), "  AUDIO/WAV ; x=1")
        self.assertEqual(r.status_code, 200)


if __name__ == "__main__":
    unittest.main()
