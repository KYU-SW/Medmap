"""STT worker IPC(Unix socket) 프로토콜·클라이언트 회귀(가짜 decode, GPU 없음).

실행: ~/ai_env/bin/python -m unittest tests.test_stt_worker
"""
import os
import socket
import stat
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

import numpy as np

# 파일 경로로 로드: worker venv(~/stt_ct2_env)에는 medmap 패키지 의존성이 없다(worker 는 스크립트로 실행된다)
import importlib.util
_spec = importlib.util.spec_from_file_location("stt_worker", Path(__file__).resolve().parents[1] / "medmap" / "stt_worker.py")
w = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(w)


def start_worker(decode, path, vad_factory=None):
    ready, stop = threading.Event(), threading.Event()
    t = threading.Thread(target=w.serve, args=(decode, path),
                         kwargs={"vad_factory": vad_factory, "ready_event": ready, "stop_event": stop}, daemon=True)
    t.start()
    assert ready.wait(5)
    return stop, t


class WorkerIpcTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="medmap-stt-test-")
        self.path = os.path.join(self.dir, "sub", "w.sock")
        self.calls = []

        def decode(x):
            self.calls.append(x.size)
            return f"n{x.size}"
        self.stop, self.thread = start_worker(decode, self.path)

    def tearDown(self):
        self.stop.set()
        self.thread.join(2)

    def test_socket_is_private_and_local(self):
        mode = stat.S_IMODE(os.stat(self.path).st_mode)
        self.assertEqual(mode, 0o600)
        self.assertEqual(stat.S_IMODE(os.stat(os.path.dirname(self.path)).st_mode), 0o700)
        self.assertTrue(stat.S_ISSOCK(os.stat(self.path).st_mode))

    def test_decode_roundtrip_reuses_one_connection(self):
        client = w.WorkerClient(self.path)
        self.assertEqual(client.transcribe(np.zeros(16000, dtype=np.float32)), "n16000")
        self.assertEqual(client.transcribe(np.zeros(8000, dtype=np.float32), mode="final"), "n8000")
        self.assertEqual(client.ping()["ok"], True)
        self.assertEqual(client.connects, 1)                  # 요청마다 새 연결 없음
        self.assertEqual(set(client.last), {"round_trip", "worker_decode", "ipc"})
        client.close()

    def test_pcm_is_int16_scaled(self):
        seen = []
        stop, t = start_worker(lambda x: seen.append(float(x.max())) or "ok", os.path.join(self.dir, "b.sock"))
        try:
            w.WorkerClient(os.path.join(self.dir, "b.sock")).transcribe(np.full(1600, 0.5, dtype=np.float32))
        finally:
            stop.set()
            t.join(2)
        self.assertAlmostEqual(seen[0], 0.5, places=3)

    def test_worker_down_raises_and_backs_off(self):
        client = w.WorkerClient(os.path.join(self.dir, "missing.sock"), backoff_s=0.2)
        with self.assertRaises(w.SttWorkerUnavailable) as ctx:
            client.transcribe(np.zeros(160, dtype=np.float32))
        self.assertEqual(ctx.exception.code, "WORKER_CONNECT_FAILED")
        with self.assertRaises(w.SttWorkerUnavailable) as ctx:
            client.transcribe(np.zeros(160, dtype=np.float32))
        self.assertEqual(ctx.exception.code, "WORKER_BACKOFF")

    def test_worker_crash_mid_session_then_recovers(self):
        client = w.WorkerClient(self.path, backoff_s=0.05)
        client.transcribe(np.zeros(160, dtype=np.float32))
        self.stop.set()
        self.thread.join(2)
        client._sock.shutdown(socket.SHUT_RDWR)                 # 연결 끊김 흉내
        with self.assertRaises(w.SttWorkerUnavailable) as ctx:
            client.transcribe(np.zeros(160, dtype=np.float32))
        self.assertIn(ctx.exception.code, {"WORKER_DISCONNECTED", "WORKER_TIMEOUT"})
        self.stop, self.thread = start_worker(lambda x: "back", self.path)
        time.sleep(0.06)
        self.assertEqual(client.transcribe(np.zeros(160, dtype=np.float32)), "back")

    def test_timeout_and_decode_failure(self):
        slow = os.path.join(self.dir, "slow.sock")
        stop, t = start_worker(lambda x: time.sleep(0.5) or "late", slow)
        try:
            with self.assertRaises(w.SttWorkerUnavailable) as ctx:
                w.WorkerClient(slow, timeout_s=0.1).transcribe(np.zeros(160, dtype=np.float32))
            self.assertEqual(ctx.exception.code, "WORKER_TIMEOUT")
        finally:
            stop.set()
            t.join(2)
        bad = os.path.join(self.dir, "bad.sock")
        stop, t = start_worker(lambda x: 1 / 0, bad)
        try:
            with self.assertRaises(w.SttWorkerUnavailable) as ctx:
                w.WorkerClient(bad).transcribe(np.zeros(160, dtype=np.float32))
            self.assertEqual(ctx.exception.code, "DECODE_FAILED")
        finally:
            stop.set()
            t.join(2)

    def test_malformed_frames_rejected(self):
        with self.assertRaises(ValueError):
            a, b = socket.socketpair()
            a.sendall(b"\x00\x00\xff\xff")                     # 너무 큰 헤더
            w.read_frame(b)
        a, b = socket.socketpair()
        a.sendall(w.encode_frame({"op": "decode", "nbytes": 3}, b"abc"))    # 홀수 바이트
        with self.assertRaises(ValueError):
            w.read_frame(b)

    def test_no_audio_or_text_in_worker_logs(self):
        with self.assertLogs("medmap.stt_worker", level="INFO") as logs:
            w.WorkerClient(self.path).transcribe(np.zeros(16000, dtype=np.float32))
            w.LOG.info("probe")
        self.assertNotIn("n16000", "\n".join(logs.output))     # 전사문(대조군: 실제 반환값)은 로그에 없다


class FakeVad:
    """연결마다 하나: 프레임 최대 진폭 > 0.1 이면 0.9. 누적 프레임 수를 확률 끝자리에 실어 상태가 연결별인지 본다."""

    def __init__(self):
        self.frames = 0

    def __call__(self, x):
        out = []
        for i in range(0, x.size, 512):
            self.frames += 1
            out.append((0.9 if np.abs(x[i:i + 512]).max() > 0.1 else 0.1) + self.frames / 10000)
        return out


def pcm_frames(n, amp=0.0):
    return (np.full(512 * n, amp, dtype=np.float32) * 32767).astype("<i2").tobytes()


class WorkerVadTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="medmap-stt-vad-")
        self.path = os.path.join(self.dir, "v.sock")
        self.stop, self.thread = start_worker(lambda x: time.sleep(0.5) or "slow", self.path, vad_factory=FakeVad)

    def tearDown(self):
        self.stop.set()
        self.thread.join(2)

    def test_vad_roundtrip_state_is_per_connection(self):
        a, b = w.WorkerClient(self.path), w.WorkerClient(self.path)
        self.assertTrue(a.ping()["vad"])
        self.assertEqual([round(p, 4) for p in a.vad_probs(pcm_frames(2, 0.5))], [0.9001, 0.9002])
        self.assertEqual([round(p, 4) for p in a.vad_probs(pcm_frames(1))], [0.1003])     # 같은 연결 = 상태 이어짐
        self.assertEqual([round(p, 4) for p in b.vad_probs(pcm_frames(1))], [0.1001])     # 다른 연결 = 새 상태
        a.close()
        b.close()

    def test_vad_is_not_blocked_by_decode(self):
        decoding = w.WorkerClient(self.path)
        t = threading.Thread(target=decoding.transcribe, args=(np.zeros(160, dtype=np.float32),), daemon=True)
        t.start()
        time.sleep(0.05)                                        # decode(0.5 s)가 lock 을 잡은 상태
        started = time.perf_counter()
        w.WorkerClient(self.path).vad_probs(pcm_frames(3))
        self.assertLess(time.perf_counter() - started, 0.2)
        t.join(2)

    def test_bad_vad_sizes_rejected(self):
        client = w.WorkerClient(self.path, backoff_s=0.0)
        for payload in (pcm_frames(1)[:-2], b"", pcm_frames(64)):      # 프레임 배수 아님 · 빈 요청 · 2 s 초과
            with self.assertRaises(w.SttWorkerUnavailable) as ctx:
                client.vad_probs(payload)
            self.assertEqual(ctx.exception.code, "BAD_REQUEST")

    def test_vad_unavailable_when_worker_has_no_vad(self):
        path = os.path.join(self.dir, "novad.sock")
        stop, t = start_worker(lambda x: "t", path)
        try:
            client = w.WorkerClient(path)
            self.assertFalse(client.ping()["vad"])
            with self.assertRaises(w.SttWorkerUnavailable) as ctx:
                client.vad_probs(pcm_frames(1))
            self.assertEqual(ctx.exception.code, "VAD_UNAVAILABLE")
        finally:
            stop.set()
            t.join(2)


class OnnxTelemetryOffTest(unittest.TestCase):
    """OFFLINE_ON_PREM_FIRST: onnxruntime 을 import 하는 시점에 이미 ORT_DISABLE_TELEMETRY=1 이어야 한다(가짜 모듈로 확인)."""

    def test_env_set_before_onnxruntime_import(self):
        import types
        seen = {}

        class Session:
            def __init__(self, *a, **k):
                pass

        class Opts:
            pass
        fake_ort = types.ModuleType("onnxruntime")
        fake_ort.SessionOptions, fake_ort.InferenceSession = Opts, Session
        fake_ort.disable_telemetry_events = lambda: seen.setdefault("api", True)
        fake_utils = types.ModuleType("faster_whisper.utils")
        fake_utils.get_assets_path = lambda: "/nonexistent"
        saved = {k: sys.modules.get(k) for k in ("onnxruntime", "faster_whisper", "faster_whisper.utils")}
        old_env = os.environ.pop("ORT_DISABLE_TELEMETRY", None)
        try:
            sys.modules["faster_whisper"] = types.ModuleType("faster_whisper")
            sys.modules["faster_whisper.utils"] = fake_utils
            sys.modules.pop("onnxruntime", None)
            import builtins
            real_import = builtins.__import__

            def spy(name, *a, **k):
                if name == "onnxruntime":
                    seen["env_at_import"] = os.environ.get("ORT_DISABLE_TELEMETRY")
                    return fake_ort
                return real_import(name, *a, **k)
            builtins.__import__ = spy
            try:
                w.load_silero_vad_factory()
            finally:
                builtins.__import__ = real_import
        finally:
            for k, v in saved.items():
                if v is None:
                    sys.modules.pop(k, None)
                else:
                    sys.modules[k] = v
            if old_env is None:
                os.environ.pop("ORT_DISABLE_TELEMETRY", None)
            else:
                os.environ["ORT_DISABLE_TELEMETRY"] = old_env
        self.assertEqual(seen.get("env_at_import"), "1")
        self.assertTrue(seen.get("api"))


def _silero_available():
    try:
        import onnxruntime  # noqa: F401
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False


@unittest.skipUnless(_silero_available(), "Silero ONNX 는 worker venv(~/stt_ct2_env)에서만: ~/stt_ct2_env/bin/python -m unittest tests.test_stt_worker")
class SileroRealTest(unittest.TestCase):
    """실제 silero_vad_v6.onnx(CPU). 기존 TTS 샘플(22.05 kHz)을 16 kHz 로 바꿔 무음·음성 확률을 본다."""

    def test_silence_low_speech_high_streaming_equals_batch(self):
        import wave
        from faster_whisper.vad import get_vad_model
        sample = Path(__file__).resolve().parents[1] / "stt" / "samples" / "medmap_tts_test.wav"
        if not sample.exists():
            self.skipTest("stt/samples 없음")
        with wave.open(str(sample)) as f:
            rate = f.getframerate()
            y = np.frombuffer(f.readframes(f.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
        t = np.arange(0, y.size / rate, 1 / 16000)
        y = np.interp(t, np.arange(y.size) / rate, y).astype(np.float32)
        x = np.concatenate([np.zeros(16000, np.float32), y])
        x = x[: x.size // 512 * 512]
        vad = w.load_silero_vad_factory()()
        probs = []
        for i in range(0, x.size, 16000 // 512 * 512):             # 스트리밍처럼 나눠서
            probs += vad(x[i:i + 16000 // 512 * 512])
        probs = np.array(probs)
        self.assertLess(probs[:25].max(), 0.2)                      # 앞 0.8 s 무음
        self.assertGreater(probs[40:200].mean(), 0.5)               # 음성 구간
        self.assertLess(np.abs(probs - np.ravel(get_vad_model()(x))[: probs.size]).max(), 1e-4)


if __name__ == "__main__":
    unittest.main()
