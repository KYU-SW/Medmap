"""/v1/stt/stream* · /v1/stt/status · /v1/stt/prewarm 회귀(가짜 transcriber, 실제 Whisper 없음).

실행: ~/ai_env/bin/python -m unittest tests.test_stt_stream_api
PARTIAL 은 UI 전용 — 이 경로는 매퍼·엔진·세션을 호출하지 않는다. 오디오·전사문·sid 는 로그에 남지 않는다.
"""
import os
import sys
import unittest
import warnings
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")

from fastapi.testclient import TestClient

from medmap import api as api_module
from medmap import api_stt_stream as st

SPEECH = (np.sin(np.linspace(0, 2000, 16000)) * 8000).astype(np.int16).tobytes()     # 1 s 톤(무음 아님)
SILENCE = np.zeros(16000, dtype=np.int16).tobytes()
ORIGIN = {"origin": "http://testserver"}
START = {"type": "start", "sample_rate": 16000, "format": "s16le", "run_id": "r"}
CLIENT = TestClient(api_module.app)
CALLS = []


def fake(audio):
    CALLS.append(audio.size)
    return "어제부터 배가 아팠어요"[: max(1, int(audio.size / 16000 * 4))]


def setUpModule():
    CLIENT.__enter__()
    st.STREAMING = True
    st.set_transcribe_for_tests(fake)


def tearDownModule():
    st.set_transcribe_for_tests(None)
    CLIENT.__exit__(None, None, None)


def receive_until_final(ws):
    seen = []
    while True:
        msg = ws.receive_json()
        seen.append(msg)
        if msg["type"] in ("final", "error"):
            return seen


class StatusTest(unittest.TestCase):
    def test_overloaded_skips_partials_but_final_still_arrives(self):
        CALLS.clear()
        st.scheduler().last_queue_ms = 10_000.0              # 직전 대기가 길었다 = 과부하
        st.scheduler().last_queue_at = __import__("time").perf_counter()
        try:
            with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
                ws.send_json(START)
                ws.receive_json()
                ws.send_bytes(SPEECH)
                ws.send_json({"type": "stop"})
                seen = receive_until_final(ws)
        finally:
            st.scheduler().last_queue_ms = 0.0
        self.assertEqual([m["type"] for m in seen], ["utterance_end", "final"])
        self.assertEqual(CALLS, [16000])                     # FINAL 1회만

    def test_status_and_prewarm(self):
        body = CLIENT.get("/v1/stt/status").json()
        self.assertEqual(body, {"streaming": True, "stt_state": "WARM", "vad": "manual", "engine": st.ENGINE})
        a, b = CLIENT.post("/v1/stt/prewarm"), CLIENT.post("/v1/stt/prewarm")
        self.assertEqual((a.status_code, b.status_code), (202, 202))


class StreamWsTest(unittest.TestCase):
    def test_partial_then_final_on_stop_and_next_utterance(self):
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            ws.send_json(START)
            self.assertEqual(ws.receive_json(), {"type": "ready", "stt_state": "WARM", "vad": "manual"})
            for _ in range(3):
                ws.send_bytes(SPEECH)
            ws.send_json({"type": "stop"})
            seen = receive_until_final(ws)
            types = [m["type"] for m in seen]
            self.assertIn("utterance_end", types)
            final = seen[-1]
            self.assertEqual((final["utt"], final["text"]), (1, fake(np.zeros(48000))))
            self.assertEqual(final["audio_ms"], 3000)
            self.assertEqual(set(final), {"type", "utt", "text", "audio_ms", "srv_ms"})
            for m in seen:
                if m["type"] == "partial":
                    self.assertEqual(m["utt"], 1)
            # 다음 발화는 새 번호, 이전 발화 오디오를 포함하지 않는다(발화 간 격리)
            ws.send_bytes(SPEECH)
            ws.send_json({"type": "stop"})
            second = receive_until_final(ws)[-1]
            self.assertEqual((second["utt"], second["text"]), (2, fake(np.zeros(16000))))
            self.assertEqual(second["audio_ms"], 4000)

    def test_final_reuses_partial_that_covers_whole_utterance(self):
        """같은 모델·같은 오디오면 결과가 같으므로, 발화 전체를 덮은 partial 이 있으면 FINAL 은 다시 디코드하지 않는다."""
        CALLS.clear()
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            ws.send_json(START)
            ws.receive_json()
            ws.send_bytes(SPEECH)
            partial = ws.receive_json()
            self.assertEqual((partial["type"], partial["audio_ms"]), ("partial", 1000))
            ws.send_json({"type": "stop"})
            final = receive_until_final(ws)[-1]
        calls = list(CALLS)                                  # 기대값 계산(fake 호출) 전에 서버 호출만 떠 둔다
        self.assertEqual(calls, [16000])                     # partial 1회뿐, FINAL 재디코드 없음
        self.assertEqual(final["text"], fake(np.zeros(16000)))
        self.assertTrue(final["srv_ms"]["reused"])

    def test_final_decodes_when_new_audio_after_last_partial(self):
        CALLS.clear()
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            ws.send_json(START)
            ws.receive_json()
            ws.send_bytes(SPEECH)
            ws.receive_json()                                # partial(1 s)
            ws.send_bytes(SPEECH)                            # tick 전이라 partial 없음
            ws.send_json({"type": "stop"})
            final = receive_until_final(ws)[-1]
        calls = list(CALLS)
        self.assertEqual(calls, [16000, 32000])              # partial(1 s) + FINAL 재디코드(2 s)
        self.assertEqual(final["text"], fake(np.zeros(32000)))
        self.assertNotIn("reused", final["srv_ms"])

    def test_silence_only_gives_empty_final_without_decoding(self):
        CALLS.clear()
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            ws.send_json(START)
            ws.receive_json()
            ws.send_bytes(SILENCE)
            ws.send_json({"type": "stop"})
            final = receive_until_final(ws)[-1]
        self.assertEqual(final["text"], "")
        self.assertEqual(CALLS, [])

    def test_rejects_cross_origin_bad_format_and_bad_bytes(self):
        with self.assertRaises(Exception):
            with CLIENT.websocket_connect("/v1/stt/stream", headers={"origin": "http://evil.example"}) as ws:
                ws.receive_json()
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            ws.send_json({**START, "sample_rate": 44100})
            self.assertEqual(ws.receive_json(), {"type": "error", "code": "AUDIO_INVALID"})
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            ws.send_json(START)
            ws.receive_json()
            ws.send_bytes(b"\x00")
            self.assertEqual(ws.receive_json(), {"type": "error", "code": "AUDIO_INVALID"})

    def test_second_stream_busy(self):
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws1:
            ws1.send_json(START)
            ws1.receive_json()
            r = CLIENT.post("/v1/stt/stream", json={"sample_rate": 16000, "format": "s16le", "run_id": "b"})
            self.assertEqual((r.status_code, r.json()["error"]["code"]), (429, "STREAM_BUSY"))
            with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws2:
                ws2.send_json(START)
                self.assertEqual(ws2.receive_json(), {"type": "error", "code": "STREAM_BUSY"})


class StreamHttpTest(unittest.TestCase):
    def open(self):
        r = CLIENT.post("/v1/stt/stream", json={"sample_rate": 16000, "format": "s16le", "run_id": "h"})
        self.assertEqual(r.status_code, 200, r.text)
        return r.json()["sid"]

    def audio(self, sid, data=SPEECH):
        return CLIENT.post("/v1/stt/stream/audio", content=data,
                           headers={"content-type": "application/octet-stream", "x-stt-stream": sid})

    def test_http_chunk_path(self):
        sid = self.open()
        for _ in range(2):
            self.assertEqual(self.audio(sid).status_code, 200)
        msgs = CLIENT.post("/v1/stt/stream/stop", headers={"x-stt-stream": sid}).json()["messages"]
        self.assertEqual(msgs[-1]["type"], "final")
        self.assertEqual(msgs[-1]["text"], fake(np.zeros(32000)))
        closed = CLIENT.post("/v1/stt/stream/close", headers={"x-stt-stream": sid})
        self.assertEqual(closed.status_code, 200)
        self.assertEqual(self.audio(sid).status_code, 404)

    def test_http_idle_expiry(self):
        sid = self.open()
        st._streams[sid].touched -= st.IDLE_S + 1
        st.expire_idle()
        self.assertEqual(CLIENT.post("/v1/stt/stream/stop", headers={"x-stt-stream": sid}).status_code, 404)

    def test_bad_open_and_bad_audio(self):
        r = CLIENT.post("/v1/stt/stream", json={"sample_rate": 8000, "format": "s16le", "run_id": "x"})
        self.assertEqual(r.json()["error"]["code"], "AUDIO_INVALID")
        sid = self.open()
        r = self.audio(sid, b"\x00")
        self.assertEqual((r.status_code, r.json()["error"]["code"]), (400, "AUDIO_INVALID"))
        CLIENT.post("/v1/stt/stream/close", headers={"x-stt-stream": sid})

    def test_no_text_audio_or_sid_in_logs(self):
        spoken = fake(np.zeros(16000))                       # 이 스트림이 실제로 만드는 전사문(대조군)
        with self.assertLogs("medmap", level="DEBUG") as logs:
            sid = self.open()
            self.audio(sid)
            final = CLIENT.post("/v1/stt/stream/stop", headers={"x-stt-stream": sid}).json()["messages"][-1]
            CLIENT.post("/v1/stt/stream/close", headers={"x-stt-stream": sid})
            api_module.LOG.info("probe")
        joined = "\n".join(logs.output)
        self.assertEqual(final["text"], spoken)              # 대조군: 전사문이 실제로 만들어졌다
        self.assertTrue(spoken)
        self.assertNotIn(spoken, joined)
        self.assertNotIn(sid, joined)


class Ct2WorkerEngineTest(unittest.TestCase):
    """MEDMAP_STT_ENGINE=ct2: 실제 WorkerClient ↔ 가짜 decode 를 쓰는 Unix socket worker. 실패는 FINAL 없이 error 로."""

    def setUp(self):
        import tempfile
        import threading
        from medmap import stt_worker as w
        self.w = w
        self.path = os.path.join(tempfile.mkdtemp(prefix="medmap-ct2-"), "w.sock")
        self.ready, self.stop = threading.Event(), threading.Event()
        self.decoded = []

        def decode(x):
            self.decoded.append(x.size)
            return "ct2-" + str(x.size)
        self.thread = threading.Thread(target=w.serve, args=(decode, self.path),
                                       kwargs={"ready_event": self.ready, "stop_event": self.stop}, daemon=True)
        self.thread.start()
        self.ready.wait(5)
        st.set_transcribe_for_tests(None)
        st.ENGINE = "ct2"
        st.set_worker_for_tests(w.WorkerClient(self.path, backoff_s=0.05))

    def tearDown(self):
        self.stop.set()
        self.thread.join(2)
        st.ENGINE = "hf"
        st.set_worker_for_tests(None)
        st.set_transcribe_for_tests(fake)

    def test_stream_uses_worker_with_timing_breakdown(self):
        self.assertEqual(CLIENT.get("/v1/stt/status").json()["stt_state"], "WARM")
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            ws.send_json(START)
            ws.receive_json()
            ws.send_bytes(SPEECH)
            partial = ws.receive_json()
            ws.send_bytes(SPEECH)
            ws.send_json({"type": "stop"})
            final = receive_until_final(ws)[-1]
        self.assertEqual(partial["unstable"], "ct2-16000")
        self.assertTrue({"queue", "decode", "worker", "ipc", "held", "since_recv"} <= set(partial["srv_ms"]))
        self.assertEqual(final["text"], "ct2-32000")
        self.assertEqual(st.worker_client().connects, 1)            # 영구 연결 1개

    def test_worker_down_final_becomes_error_not_final(self):
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            ws.send_json(START)
            ws.receive_json()
            self.stop.set()
            self.thread.join(2)
            if st.worker_client()._sock is not None:
                st.worker_client()._sock.shutdown(__import__("socket").SHUT_RDWR)
            ws.send_bytes(SPEECH)
            ws.send_bytes(SPEECH)
            ws.send_json({"type": "stop"})
            seen = receive_until_final(ws)
        types = [m["type"] for m in seen]
        self.assertEqual(types[-1], "error")
        self.assertEqual(seen[-1]["code"], "STT_UNAVAILABLE")
        self.assertNotIn("final", types)                           # 클라이언트 legacy 가 FINAL 을 1회만 만든다
        st._worker_state = (0.0, "COLD")
        self.assertEqual(CLIENT.get("/v1/stt/status").json()["stt_state"], "UNAVAILABLE")


def fake_vad(pcm):
    """가짜 VAD: 512-sample 프레임 RMS > 1000 이면 음성(0.9), 아니면 0.05."""
    x = np.frombuffer(pcm, dtype="<i2").astype(np.float32).reshape(-1, 512)
    return [0.9 if float(np.sqrt(np.mean(np.square(f)))) > 1000 else 0.05 for f in x]


def sized(audio):
    CALLS.append(audio.size)
    return f"n{audio.size}"


def receive_finals(ws, n):
    seen = []
    while sum(m["type"] == "final" for m in seen) < n:
        msg = ws.receive_json()
        seen.append(msg)
        if msg["type"] == "error":
            break
    return seen


class VadStreamTest(unittest.TestCase):
    """서버 VAD(M2): 발화 자동 확정 · pre-roll · 무음 미디코드 · 수동 stop 공존 · 환각 가드 · VAD 장애 → 수동."""

    def setUp(self):
        CALLS.clear()
        st.set_transcribe_for_tests(sized)
        st.set_vad_for_tests(fake_vad)

    def tearDown(self):
        st.set_vad_for_tests(None)
        st.set_transcribe_for_tests(fake)

    def open_ws(self, ws):
        ws.send_json(START)
        ready = ws.receive_json()
        self.assertEqual((ready["type"], ready["vad"]), ("ready", "server"))

    def test_two_utterances_auto_finalized_from_their_own_audio(self):
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            self.open_ws(ws)
            for chunk in (SPEECH, SILENCE, SPEECH, SILENCE):     # 수동 stop 없음
                ws.send_bytes(chunk)
            seen = receive_finals(ws, 2)
            ws.send_json({"type": "close"})
        ends = [m for m in seen if m["type"] == "utterance_end"]
        finals = [m for m in seen if m["type"] == "final"]
        self.assertEqual([(m["utt"], m["reason"]) for m in ends], [(1, "vad"), (2, "vad")])
        self.assertEqual([m["utt"] for m in finals], [1, 2])
        self.assertEqual(finals[0]["text"], "n32000")                    # 톤 1 s + 끝 판정까지 받은 무음 1 s
        self.assertEqual(finals[1]["text"], "n37056")                    # pre-roll(≥300 ms 앞 무음) + 톤 1 s + 무음 1 s
        self.assertEqual(finals[0]["srv_ms"]["speech_start_ms"], 0)
        self.assertEqual(finals[0]["srv_ms"]["speech_end_ms"], 1024)     # 32 ms 프레임 경계
        self.assertEqual(finals[1]["srv_ms"]["speech_start_ms"], 1984)
        self.assertEqual(finals[1]["srv_ms"]["speech_end_ms"], 3008)
        self.assertTrue(all(m["utt"] in (1, 2) for m in seen if m["type"] == "partial"))

    def test_final_reports_in_utterance_pauses_for_scoring(self):
        """채점용: 발화 안 쉼(≥ predecode 96 ms, 말이 다시 이어진 것만)을 FINAL srv_ms.pauses_ms 로(스트림 ms, 숫자만)."""
        gap_300 = SILENCE[: 4800 * 2]
        gap_64 = SILENCE[: 1024 * 2]
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            self.open_ws(ws)
            for chunk in (SPEECH, gap_300, SPEECH, gap_64, SPEECH, SILENCE):
                ws.send_bytes(chunk)
            seen = receive_finals(ws, 1)
            ws.send_json({"type": "close"})
        finals = [m for m in seen if m["type"] == "final"]
        self.assertEqual(len(finals), 1)
        pauses = finals[0]["srv_ms"]["pauses_ms"]
        self.assertEqual(len(pauses), 1)                                  # 64 ms 틈·끝 무음은 넣지 않는다
        start, end = pauses[0]
        self.assertTrue(992 <= start <= 1056, pauses)
        self.assertTrue(256 <= end - start <= 352, pauses)
        self.assertTrue(all(isinstance(v, int) for v in pauses[0]))

    def test_final_without_pause_reports_empty_list(self):
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            self.open_ws(ws)
            for chunk in (SPEECH, SILENCE):
                ws.send_bytes(chunk)
            seen = receive_finals(ws, 1)
            ws.send_json({"type": "close"})
        self.assertEqual([m for m in seen if m["type"] == "final"][0]["srv_ms"]["pauses_ms"], [])

    def test_manual_stop_mid_speech_gives_one_final(self):
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            self.open_ws(ws)
            ws.send_bytes(SPEECH)
            ws.send_json({"type": "stop"})
            seen = receive_finals(ws, 1)
            ws.send_json({"type": "close"})
        self.assertEqual([m["reason"] for m in seen if m["type"] == "utterance_end"], ["manual"])
        finals = [m for m in seen if m["type"] == "final"]
        self.assertEqual(len(finals), 1)
        self.assertEqual(finals[0]["text"], "n16000")

    def test_stop_after_auto_final_gives_empty_final_and_no_duplicate(self):
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            self.open_ws(ws)
            ws.send_bytes(SPEECH)
            ws.send_bytes(SILENCE)
            first = receive_finals(ws, 1)
            ws.send_json({"type": "stop"})
            second = receive_finals(ws, 1)
            ws.send_json({"type": "close"})
        self.assertEqual([m["text"] for m in first + second if m["type"] == "final"], ["n32000", ""])
        self.assertEqual([m["reason"] for m in second if m["type"] == "utterance_end"], ["manual"])

    def test_after_manual_stop_new_audio_needs_vad_start_again(self):
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            self.open_ws(ws)
            ws.send_bytes(SPEECH)
            ws.send_json({"type": "stop"})
            first = receive_finals(ws, 1)
            ws.send_bytes(SILENCE)                                       # 발화 밖 무음 → 발화가 열리지 않음
            ws.send_json({"type": "stop"})
            second = receive_finals(ws, 1)
            ws.send_json({"type": "close"})
        self.assertEqual([m["text"] for m in first if m["type"] == "final"], ["n16000"])
        self.assertEqual([(m["type"], m.get("reason"), m.get("text")) for m in second],
                         [("utterance_end", "manual", None), ("final", None, "")])

    def test_silence_only_never_decodes(self):
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            self.open_ws(ws)
            ws.send_bytes(SILENCE)
            ws.send_bytes(SILENCE)
            ws.send_json({"type": "stop"})
            seen = receive_finals(ws, 1)
        self.assertEqual([m["type"] for m in seen], ["utterance_end", "final"])
        self.assertEqual(seen[-1]["text"], "")
        self.assertEqual(CALLS, [])                                      # 무음은 partial·final 모두 디코드 0

    def test_hallucination_removed_only_in_low_speech_utterance(self):
        st.set_transcribe_for_tests(lambda audio: "시청해주셔서 감사합니다")
        with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
            self.open_ws(ws)
            ws.send_bytes(SPEECH[: 3200 * 2])                           # 0.2 s 톤 → 음성 비율 < 0.3
            ws.send_bytes(SILENCE)
            low = receive_finals(ws, 1)
            ws.send_bytes(SPEECH)                                        # 1 s 톤 → 음성 비율 높음
            ws.send_bytes(SPEECH)
            ws.send_bytes(SILENCE)
            high = receive_finals(ws, 1)
            ws.send_json({"type": "close"})
        self.assertEqual([m["text"] for m in low if m["type"] == "final"], [""])
        self.assertEqual([m["text"] for m in high if m["type"] == "final"], ["시청해주셔서 감사합니다"])

    def test_http_path_auto_final_in_audio_response(self):
        r = CLIENT.post("/v1/stt/stream", json={"sample_rate": 16000, "format": "s16le", "run_id": "v"})
        self.assertEqual(r.json()["vad"], "server")
        sid = r.json()["sid"]
        msgs = []
        for chunk in (SPEECH, SILENCE):
            msgs += CLIENT.post("/v1/stt/stream/audio", content=chunk,
                                headers={"content-type": "application/octet-stream", "x-stt-stream": sid}).json()["messages"]
        self.assertEqual([m["text"] for m in msgs if m["type"] == "final"], ["n32000"])
        stop = CLIENT.post("/v1/stt/stream/stop", headers={"x-stt-stream": sid}).json()["messages"]
        self.assertEqual([(m["type"], m.get("text")) for m in stop], [("utterance_end", None), ("final", "")])
        CLIENT.post("/v1/stt/stream/close", headers={"x-stt-stream": sid})

    def test_vad_failure_falls_back_to_manual_without_losing_audio(self):
        calls = []

        def flaky(pcm):
            calls.append(len(pcm))
            raise RuntimeError("vad down")
        st.set_vad_for_tests(flaky)
        with self.assertLogs("medmap.stt_stream", level="INFO") as logs:
            with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
                self.open_ws(ws)
                ws.send_bytes(SPEECH)
                ws.send_bytes(SPEECH)
                ws.send_json({"type": "stop"})
                seen = receive_finals(ws, 1)
        self.assertEqual(len(calls), 1)                                  # 실패 후 이 스트림은 VAD 를 다시 부르지 않는다
        self.assertEqual([m["text"] for m in seen if m["type"] == "final"], ["n32000"])
        self.assertTrue(any("event=vad_failed kind=RuntimeError" in line for line in logs.output))

    def test_large_http_chunk_is_split_for_vad_and_vad_stays_on(self):
        sizes = []

        def recording(pcm):
            sizes.append(len(pcm))
            return fake_vad(pcm)
        st.set_vad_for_tests(recording)
        r = CLIENT.post("/v1/stt/stream", json={"sample_rate": 16000, "format": "s16le", "run_id": "big"})
        sid = r.json()["sid"]
        big = SPEECH * 3 + SILENCE                                       # 4 s 한 번에(HTTP 상한 안, worker VAD 한 요청 상한 2 s 초과)
        msgs = CLIENT.post("/v1/stt/stream/audio", content=big,
                           headers={"content-type": "application/octet-stream", "x-stt-stream": sid}).json()["messages"]
        CLIENT.post("/v1/stt/stream/close", headers={"x-stt-stream": sid})
        self.assertTrue(sizes and max(sizes) <= 2 * 16000 * 2)
        self.assertEqual(sum(sizes) // 1024, 64000 // 512)              # 4 s = 125 프레임 전부 VAD 를 거침
        self.assertEqual([(m["type"], m.get("reason")) for m in msgs if m["type"] == "utterance_end"], [("utterance_end", "vad")])

    def test_status_reports_server_vad(self):
        body = CLIENT.get("/v1/stt/status").json()
        self.assertEqual((body["vad"], body["vad_silence_ms"], body["vad_predecode_ms"]), ("server", 600, 96))


TONE_100 = SPEECH[: 1600 * 2]
SIL_100 = SILENCE[: 1600 * 2]


class PredecodeTest(unittest.TestCase):
    """Speculative FINAL predecode: 침묵 시작 후 미리 계산, endpoint 전에는 아무것도 내보내지 않음, 말이 이어지면 폐기."""

    def setUp(self):
        CALLS.clear()
        st.set_transcribe_for_tests(sized)
        st.set_vad_for_tests(fake_vad)
        r = CLIENT.post("/v1/stt/stream", json={"sample_rate": 16000, "format": "s16le", "run_id": "p"})
        self.sid = r.json()["sid"]

    def tearDown(self):
        CLIENT.post("/v1/stt/stream/close", headers={"x-stt-stream": self.sid})
        st.set_vad_for_tests(None)
        st.set_transcribe_for_tests(fake)

    def post(self, chunk):
        return CLIENT.post("/v1/stt/stream/audio", content=chunk, headers={
            "content-type": "application/octet-stream", "x-stt-stream": self.sid}).json()["messages"]

    def test_candidate_computed_during_silence_but_not_shown_before_endpoint(self):
        for _ in range(10):
            self.post(TONE_100)
        before_silence = len(CALLS)
        shown = []
        spec_seen_at = None
        for i in range(8):                                            # 800 ms 침묵(endpoint 600 ms)
            msgs = self.post(SIL_100)
            if spec_seen_at is None and st._streams[self.sid].spec is not None:
                spec_seen_at = i
                calls_at_spec = len(CALLS)
            shown.append([m["type"] for m in msgs])
            if any(m["type"] == "final" for m in msgs):
                final = [m for m in msgs if m["type"] == "final"][0]
                break
        self.assertIsNotNone(spec_seen_at)
        self.assertLess(spec_seen_at, 2)                              # 96 ms 침묵 직후(두 번째 100 ms 패킷 안)
        before_final = [t for types in shown[:-1] for t in types]
        self.assertNotIn("final", before_final)                       # endpoint 전: FINAL·발화 종료 메시지 없음
        self.assertNotIn("utterance_end", before_final)
        self.assertNotIn("partial", before_final[spec_seen_at:])      # 후보 계산 중 partial 안 함
        self.assertTrue(final["srv_ms"].get("predecoded"))
        snapshot = int(final["text"][1:])
        self.assertIn(snapshot, CALLS[before_silence:])               # 미리 디코드된 크기 = FINAL 오디오
        self.assertGreaterEqual(snapshot, 16000)
        self.assertLess(snapshot, 16000 + 3 * 1600)                   # 음성 + 짧은 꼬리(뒤따른 침묵 전체가 아님)
        # endpoint 에서 추가 디코드 없음. 후보 디코드는 비동기 task 라 spec 을 본 시점에 아직 기록 전일 수 있다
        # → spec 이후 호출은 [] 또는 후보 1회뿐이고, 같은 오디오 디코드는 발화 전체에서 1회
        self.assertIn(CALLS[calls_at_spec:], ([], [snapshot]))
        self.assertEqual(CALLS[before_silence:].count(snapshot), 1)

    def test_candidate_dropped_when_speech_resumes(self):
        for chunk in [TONE_100] * 5 + [SIL_100] * 3 + [TONE_100] * 5:   # 300 ms 쉼 < 600 ms → 같은 발화
            msgs = self.post(chunk)
            self.assertNotIn("final", [m["type"] for m in msgs])
        finals = []
        for _ in range(8):
            finals += [m for m in self.post(SIL_100) if m["type"] == "final"]
        self.assertEqual(len(finals), 1)
        self.assertEqual(finals[0]["srv_ms"]["spec_discarded"], 1)       # 이 발화에서 버린 후보 수(숫자만)
        self.assertGreaterEqual(int(finals[0]["text"][1:]), 13 * 1600)   # 두 번째 톤까지 포함한 발화

    def test_manual_stop_during_silence_uses_candidate(self):
        for chunk in [TONE_100] * 10:
            self.post(chunk)
        before_silence = len(CALLS)
        for chunk in [SIL_100] * 2:
            self.post(chunk)
        self.assertIsNotNone(st._streams[self.sid].spec)
        calls = len(CALLS)
        msgs = CLIENT.post("/v1/stt/stream/stop", headers={"x-stt-stream": self.sid}).json()["messages"]
        final = [m for m in msgs if m["type"] == "final"][0]
        self.assertTrue(final["srv_ms"].get("predecoded"))
        self.assertEqual(final["srv_ms"]["spec_discarded"], 0)
        # stop 에서 추가 디코드 없음. 후보 디코드(비동기 task)는 spec 확인 시점에 아직 기록 전일 수 있다
        snapshot = int(final["text"][1:])
        self.assertIn(CALLS[calls:], ([], [snapshot]))
        self.assertEqual(CALLS[before_silence:].count(snapshot), 1)

    def test_predecode_threshold_is_below_endpoint(self):
        from medmap.stt_vad import predecode_ms_default
        self.assertEqual(predecode_ms_default(600), 96)
        self.assertEqual(predecode_ms_default(96), 64)                # endpoint 보다 항상 짧게


class PauseCensusTest(unittest.TestCase):
    """STEP A 쉼 전수 기록(MEDMAP_STT_PAUSE_CENSUS=1): 발화 안 쉼마다 길이·재개 여부·완결 등급·안정성을 숫자/코드로만 로그."""

    def setUp(self):
        CALLS.clear()
        st.set_transcribe_for_tests(sized)
        st.set_vad_for_tests(fake_vad)
        st.PAUSE_CENSUS = True
        self.sid = CLIENT.post("/v1/stt/stream", json={"sample_rate": 16000, "format": "s16le", "run_id": "c"}).json()["sid"]

    def tearDown(self):
        CLIENT.post("/v1/stt/stream/close", headers={"x-stt-stream": self.sid})
        st.PAUSE_CENSUS = False
        st.set_vad_for_tests(None)
        st.set_transcribe_for_tests(fake)

    def post(self, chunk):
        return CLIENT.post("/v1/stt/stream/audio", content=chunk, headers={
            "content-type": "application/octet-stream", "x-stt-stream": self.sid}).json()["messages"]

    def test_pause_resumed_and_turn_end_are_logged_without_text(self):
        with self.assertLogs("medmap.stt_stream", level="INFO") as logs:
            for chunk in [TONE_100] * 5 + [SIL_100] * 3 + [TONE_100] * 5 + [SIL_100] * 8:
                self.post(chunk)
        pauses = [line for line in logs.output if "event=pause " in line]
        self.assertEqual(len(pauses), 2)
        first, last = pauses
        self.assertIn("resumed=1", first)
        self.assertIn("censored=0", first)
        dur = int(first.split("dur_ms=")[1].split()[0])
        self.assertTrue(250 <= dur <= 400, dur)                          # 300 ms 쉼(32 ms 프레임 경계)
        self.assertIn("resumed=0", last)
        self.assertIn("censored=1", last)                                # endpoint 로 끝난 쉼 = 실제 길이는 모름(잘림)
        for line in pauses:
            for key in ("cls_partial=", "cls_cand=", "stable=", "cand_ready_ms=", "silence_ms=600"):
                self.assertIn(key, line)
        joined = "\n".join(logs.output)
        for size in set(CALLS):
            self.assertNotIn(f"n{size}", joined)                         # 전사문(가짜: "n<샘플 수>")은 로그에 없음

    def test_census_mode_actually_emits_log_lines(self):
        # assertLogs 는 handler 가 없어도 잡는다 → 실제 출력 경로(handler·level)를 따로 확인(2026-10-01: 0줄 사고)
        import logging
        st.enable_census_output()
        for name in ("medmap.stt_stream", "medmap.stt_turn"):
            logger = logging.getLogger(name)
            self.assertTrue(logger.isEnabledFor(logging.INFO), name)
            self.assertTrue(any(getattr(h, "_medmap_census", False) for h in logger.handlers), name)
        st.enable_census_output()                                         # 두 번 불러도 handler 하나
        self.assertEqual(sum(getattr(h, "_medmap_census", False) for h in logging.getLogger("medmap.stt_stream").handlers), 1)

    def test_census_off_by_default(self):
        st.PAUSE_CENSUS = False
        with self.assertLogs("medmap.stt_stream", level="INFO") as logs:
            for chunk in [TONE_100] * 5 + [SIL_100] * 3 + [TONE_100] * 3:
                self.post(chunk)
            st.LOG.info("probe")
        self.assertFalse(any("event=pause " in line for line in logs.output))


class CompatibilityTest(unittest.TestCase):
    def test_existing_transcribe_route_unchanged(self):
        r = CLIENT.post("/v1/stt/transcribe", content=b"", headers={"content-type": "audio/wav"})
        self.assertEqual(r.json()["error"]["code"], "AUDIO_EMPTY")

    def test_no_session_or_intake_calls(self):
        called = []
        original = api_module.run_session
        api_module.run_session = lambda *a, **k: called.append(1)
        try:
            sid = CLIENT.post("/v1/stt/stream", json={"sample_rate": 16000, "format": "s16le", "run_id": "z"}).json()["sid"]
            CLIENT.post("/v1/stt/stream/audio", content=SPEECH, headers={"content-type": "application/octet-stream", "x-stt-stream": sid})
            CLIENT.post("/v1/stt/stream/stop", headers={"x-stt-stream": sid})
            CLIENT.post("/v1/stt/stream/close", headers={"x-stt-stream": sid})
        finally:
            api_module.run_session = original
        self.assertEqual(called, [])


class FlagOffTest(unittest.TestCase):
    def test_disabled_flag(self):
        st.STREAMING = False
        try:
            self.assertFalse(CLIENT.get("/v1/stt/status").json()["streaming"])
            r = CLIENT.post("/v1/stt/stream", json={"sample_rate": 16000, "format": "s16le", "run_id": "r"})
            self.assertEqual((r.status_code, r.json()["error"]["code"]), (404, "STREAMING_DISABLED"))
            r = CLIENT.post("/v1/stt/prewarm")
            self.assertEqual((r.status_code, r.json()["error"]["code"]), (404, "STREAMING_DISABLED"))
            with CLIENT.websocket_connect("/v1/stt/stream", headers=ORIGIN) as ws:
                ws.send_json(START)
                self.assertEqual(ws.receive_json(), {"type": "error", "code": "STREAMING_DISABLED"})
        finally:
            st.STREAMING = True


if __name__ == "__main__":
    unittest.main()
