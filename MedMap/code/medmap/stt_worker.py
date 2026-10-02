"""로컬 STT worker(B: faster-whisper / CTranslate2) + 그 IPC 프로토콜·클라이언트.

OFFLINE_ON_PREM_FIRST: Unix domain socket(파일 권한 0600, 디렉터리 0700)만 쓴다. TCP·외부 호출·런타임 다운로드 없음
(모델은 로컬 경로 + local_files_only). REALTIME_FIRST: 상주 프로세스 — 모델은 시작 시 1회 로드·prewarm, 연결은 유지,
오디오는 raw PCM 바이트로 메모리에서만 오간다(임시 파일·subprocess·재로드 없음). 오디오·전사문은 로그에 남기지 않는다.

이 파일은 worker 쪽(~/stt_ct2_env)에서 **스크립트로** 실행된다: `python medmap/stt_worker.py --model-dir ... --socket ...`
(그 venv 에는 medmap 패키지 의존성이 없으므로 이 모듈은 medmap 의 다른 모듈을 import 하지 않는다 — 표준 라이브러리 + numpy 만).
서버 쪽(~/ai_env)은 `WorkerClient` 를 import 해서 쓴다.

프레임: [4바이트 big-endian 헤더 길이][UTF-8 JSON 헤더][payload 바이트(헤더 nbytes)]
  요청 헤더: {"op": "decode"|"ping"|"vad", "id": int, "mode": "partial"|"final", "sample_rate": 16000, "nbytes": int}
  응답 헤더: {"id": int, "ok": bool, "text": str, "worker_ms": {"decode": float, "total": float}, "code": str?}  (payload 없음)
  ping 응답에는 "vad": bool(Silero VAD 사용 가능) 이 붙는다.
  vad: payload = 512-sample 프레임 N 개(int16). 응답 {"id", "ok", "probs": [N 개 음성 확률], "worker_ms": {"vad", "total"}}.
       VAD 상태(Silero h·c·64-sample context)는 **연결마다** 이어진다 → 서버는 스트림마다 VAD 연결을 따로 연다.
       VAD 는 CPU(onnxruntime, thread 1)이고 decode lock 과 무관하다(디코드 중에도 바로 응답).
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import struct
import threading
import time

import numpy as np

LOG = logging.getLogger("medmap.stt_worker")
SR = 16000
MAX_HEADER = 4096
MAX_PAYLOAD = SR * 2 * 31          # 31 s 의 16-bit mono(발화 상한 30 s + 여유)
VAD_FRAME = 512                    # Silero v6 @16 kHz 프레임(32 ms)
VAD_CONTEXT = 64
MAX_VAD_BYTES = SR * 2 * 2         # 한 요청 최대 2 s


def default_socket_path() -> str:
    base = os.environ.get("XDG_RUNTIME_DIR") or f"/tmp/medmap-stt-{os.getuid()}"
    return os.environ.get("MEDMAP_STT_WORKER_SOCKET") or os.path.join(base, "medmap-stt-worker.sock")


# ---------------- 프레이밍(양쪽 공통, 순수 함수) ----------------
def encode_frame(header: dict, payload: bytes = b"") -> bytes:
    raw = json.dumps(header, ensure_ascii=False).encode("utf-8")
    return struct.pack(">I", len(raw)) + raw + payload


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("peer closed")
        buf.extend(chunk)
    return bytes(buf)


def read_frame(sock: socket.socket) -> tuple[dict, bytes]:
    (size,) = struct.unpack(">I", _recv_exact(sock, 4))
    if size <= 0 or size > MAX_HEADER:
        raise ValueError("bad header size")
    header = json.loads(_recv_exact(sock, size).decode("utf-8"))
    if not isinstance(header, dict):
        raise ValueError("bad header")
    nbytes = int(header.get("nbytes", 0) or 0)
    if nbytes < 0 or nbytes > MAX_PAYLOAD or nbytes % 2:
        raise ValueError("bad payload size")
    return header, (_recv_exact(sock, nbytes) if nbytes else b"")


# ---------------- 서버 쪽 클라이언트(~/ai_env) ----------------
class SttWorkerUnavailable(Exception):
    """worker 연결 실패·끊김·시간 초과·잘못된 응답. `code` 에 종류만 담는다(내용 없음)."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class WorkerClient:
    """영구 연결 1개를 재사용하는 동기 클라이언트(스레드 안전). 실패하면 backoff 동안 즉시 Unavailable(재연결 폭주 방지)."""

    def __init__(self, path: str | None = None, *, timeout_s: float = 5.0, backoff_s: float = 2.0):
        self.path = path or default_socket_path()
        self.timeout_s = timeout_s
        self.backoff_s = backoff_s
        self._sock: socket.socket | None = None
        self._lock = threading.Lock()
        self._next_id = 0
        self._down_until = 0.0
        self.connects = 0
        self.last = {}                      # 마지막 호출 타이밍(숫자만)

    def _connect(self) -> socket.socket:
        if time.monotonic() < self._down_until:
            raise SttWorkerUnavailable("WORKER_BACKOFF")
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(self.timeout_s)
            sock.connect(self.path)
        except OSError:
            self._down_until = time.monotonic() + self.backoff_s
            raise SttWorkerUnavailable("WORKER_CONNECT_FAILED") from None
        self.connects += 1
        return sock

    def _drop(self, code: str) -> SttWorkerUnavailable:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self._down_until = time.monotonic() + self.backoff_s
        return SttWorkerUnavailable(code)

    def _call(self, header: dict, payload: bytes = b"") -> dict:
        with self._lock:
            if self._sock is None:
                self._sock = self._connect()
            self._next_id += 1
            header = {**header, "id": self._next_id, "nbytes": len(payload)}
            started = time.perf_counter()
            try:
                self._sock.sendall(encode_frame(header, payload))
                reply, _ = read_frame(self._sock)
            except socket.timeout:
                raise self._drop("WORKER_TIMEOUT") from None
            except (OSError, ConnectionError):
                raise self._drop("WORKER_DISCONNECTED") from None
            except (ValueError, UnicodeDecodeError):
                raise self._drop("WORKER_BAD_RESPONSE") from None
            if reply.get("id") != header["id"]:
                raise self._drop("WORKER_BAD_RESPONSE")
            round_trip = (time.perf_counter() - started) * 1000
            worker = reply.get("worker_ms") or {}
            self.last = {"round_trip": round(round_trip, 1), "worker_decode": worker.get("decode"),
                         "ipc": round(round_trip - float(worker.get("total") or 0.0), 1)}
            return reply

    def ping(self) -> dict:
        reply = self._call({"op": "ping"})
        if not reply.get("ok"):
            raise SttWorkerUnavailable(str(reply.get("code") or "WORKER_NOT_READY"))
        return reply

    def vad_probs(self, pcm: bytes) -> list[float]:
        """512-sample 프레임 N 개(int16 bytes) → 음성 확률 N 개. 상태는 이 클라이언트의 연결에 묶인다."""
        reply = self._call({"op": "vad", "sample_rate": SR}, pcm)
        probs = reply.get("probs")
        if not reply.get("ok") or not isinstance(probs, list) or len(probs) != len(pcm) // (VAD_FRAME * 2):
            raise SttWorkerUnavailable(str(reply.get("code") or "WORKER_BAD_RESPONSE"))
        return [float(p) for p in probs]

    def transcribe(self, x: np.ndarray, mode: str = "partial") -> str:
        return self.transcribe_timed(x, mode)[0]

    def transcribe_timed(self, x: np.ndarray, mode: str = "partial") -> tuple[str, dict]:
        """(text, {"worker": worker 안 decode ms, "ipc": 왕복 − worker 처리 ms}). 타이밍은 같은 호출의 값(경합 없음)."""
        pcm = (np.clip(x, -1.0, 1.0) * 32767.0).astype("<i2").tobytes()
        reply = self._call({"op": "decode", "mode": mode, "sample_rate": SR}, pcm)
        if not isinstance(reply.get("text"), str) or not reply.get("ok"):
            raise SttWorkerUnavailable(str(reply.get("code") or "WORKER_BAD_RESPONSE"))
        worker = reply.get("worker_ms") or {}
        timings = {"worker": worker.get("decode"), "ipc": round(self.last["round_trip"] - float(worker.get("total") or 0.0), 1)}
        return reply["text"], timings

    def close(self) -> None:
        with self._lock:
            if self._sock is not None:
                self._sock.close()
                self._sock = None


# ---------------- worker 프로세스(~/stt_ct2_env) ----------------
def serve(decode, path: str, *, vad_factory=None, ready_event: threading.Event | None = None,
          stop_event: threading.Event | None = None) -> None:
    """Unix socket 서버. 연결마다 스레드 하나, decode 는 전역 lock 으로 한 번에 하나(GPU 1개).

    vad_factory: 연결마다 한 번 호출해 VAD 상태 객체(float32 프레임들 → 확률 list)를 만든다. None 이면 VAD 미지원."""
    directory = os.path.dirname(path)
    os.makedirs(directory, mode=0o700, exist_ok=True)
    if os.path.exists(path):
        os.unlink(path)
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    old = os.umask(0o177)
    try:
        server.bind(path)
    finally:
        os.umask(old)
    os.chmod(path, 0o600)
    server.listen(8)
    server.settimeout(0.2)
    decode_lock = threading.Lock()
    if ready_event is not None:
        ready_event.set()

    def handle(conn: socket.socket) -> None:
        vad = None                                   # 이 연결의 VAD 상태(첫 vad 요청 때 생성)
        with conn:
            while True:
                try:
                    header, payload = read_frame(conn)
                except (ConnectionError, OSError):
                    return
                except (ValueError, UnicodeDecodeError):
                    try:
                        conn.sendall(encode_frame({"id": None, "ok": False, "code": "BAD_REQUEST"}))
                    except OSError:
                        pass
                    return
                started = time.perf_counter()
                if header.get("op") == "ping":
                    reply = {"id": header.get("id"), "ok": True, "text": "", "vad": vad_factory is not None,
                             "worker_ms": {"decode": 0.0, "total": 0.0}}
                elif header.get("op") == "vad":
                    if vad_factory is None:
                        reply = {"id": header.get("id"), "ok": False, "code": "VAD_UNAVAILABLE"}
                    elif (header.get("sample_rate") != SR or not payload or len(payload) % (VAD_FRAME * 2)
                          or len(payload) > MAX_VAD_BYTES):
                        reply = {"id": header.get("id"), "ok": False, "code": "BAD_REQUEST"}
                    else:
                        try:
                            if vad is None:
                                vad = vad_factory()
                            t0 = time.perf_counter()
                            probs = vad(np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0)
                            reply = {"id": header.get("id"), "ok": True, "probs": [round(float(p), 4) for p in probs],
                                     "worker_ms": {"vad": round((time.perf_counter() - t0) * 1000, 2),
                                                   "total": round((time.perf_counter() - started) * 1000, 2)}}
                        except Exception as exc:      # 종류만(내용 없음)
                            LOG.info("worker vad_failed kind=%s", type(exc).__name__)
                            reply = {"id": header.get("id"), "ok": False, "code": "VAD_FAILED"}
                elif header.get("op") == "decode" and header.get("sample_rate") == SR:
                    x = np.frombuffer(payload, dtype="<i2").astype(np.float32) / 32768.0
                    try:
                        with decode_lock:
                            t0 = time.perf_counter()
                            text = decode(x)
                            decode_ms = (time.perf_counter() - t0) * 1000
                        reply = {"id": header.get("id"), "ok": True, "text": text,
                                 "worker_ms": {"decode": round(decode_ms, 1),
                                               "total": round((time.perf_counter() - started) * 1000, 1)}}
                    except Exception as exc:          # 종류만(내용 없음)
                        LOG.info("worker decode_failed kind=%s", type(exc).__name__)
                        reply = {"id": header.get("id"), "ok": False, "code": "DECODE_FAILED"}
                    LOG.info("worker %s samples=%d ms=%.1f", header.get("mode"), x.size,
                             (time.perf_counter() - started) * 1000)
                else:
                    reply = {"id": header.get("id"), "ok": False, "code": "BAD_REQUEST"}
                try:
                    conn.sendall(encode_frame(reply))
                except OSError:
                    return

    try:
        while stop_event is None or not stop_event.is_set():
            try:
                conn, _ = server.accept()
            except socket.timeout:
                continue
            threading.Thread(target=handle, args=(conn,), daemon=True).start()
    finally:
        server.close()
        if os.path.exists(path):
            os.unlink(path)


class SileroStreamVad:
    """Silero VAD v6(ONNX, CPU) 스트리밍 상태: 프레임 사이에 h·c 와 앞 64 샘플 context 를 이어 간다(연결 = 스트림 하나)."""

    def __init__(self, session):
        self.session = session
        self.h = np.zeros((1, 1, 128), dtype=np.float32)
        self.c = np.zeros((1, 1, 128), dtype=np.float32)
        self.context = np.zeros((1, VAD_CONTEXT), dtype=np.float32)

    def __call__(self, x: np.ndarray) -> list[float]:
        probs = []
        for start in range(0, x.size - VAD_FRAME + 1, VAD_FRAME):
            frame = x[start:start + VAD_FRAME].reshape(1, VAD_FRAME).astype(np.float32)
            out, self.h, self.c = self.session.run(
                None, {"input": np.concatenate([self.context, frame], axis=1), "h": self.h, "c": self.c})
            self.context = frame[:, -VAD_CONTEXT:]
            probs.append(float(np.ravel(out)[0]))
        return probs


def load_silero_vad_factory():
    """faster-whisper 패키지에 들어 있는 silero_vad_v6.onnx 를 CPU(onnxruntime, thread 1)로 로드. 다운로드 없음.

    세션은 프로세스당 1개(onnxruntime run 은 스레드 안전), 상태는 연결마다 `SileroStreamVad`.
    OFFLINE_ON_PREM_FIRST: onnxruntime 공식 빌드는 Linux 에서 1DS telemetry(HTTPS → Microsoft)가 기본 ON 이다
    (2026-09-30 M2 e2e 에서 worker 의 외부 443 연결로 확인). 초기화 전에 ORT_DISABLE_TELEMETRY=1 로 끈다(강제, 덮어쓰기 불가)."""
    os.environ["ORT_DISABLE_TELEMETRY"] = "1"
    import onnxruntime
    if hasattr(onnxruntime, "disable_telemetry_events"):
        onnxruntime.disable_telemetry_events()
    from faster_whisper.utils import get_assets_path
    opts = onnxruntime.SessionOptions()
    opts.inter_op_num_threads = 1
    opts.intra_op_num_threads = 1
    opts.log_severity_level = 4
    session = onnxruntime.InferenceSession(os.path.join(get_assets_path(), "silero_vad_v6.onnx"),
                                           providers=["CPUExecutionProvider"], sess_options=opts)
    return lambda: SileroStreamVad(session)


def load_ct2_decoder(model_dir: str, compute_type: str):
    """faster-whisper 모델을 로컬 경로에서만 로드(local_files_only). 반환: float32 → text 함수."""
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from faster_whisper import WhisperModel
    model = WhisperModel(os.path.expanduser(model_dir), device="cuda", compute_type=compute_type, local_files_only=True)

    def decode(x: np.ndarray) -> str:
        segments, _ = model.transcribe(x, language="ko", task="transcribe", beam_size=1, best_of=1, temperature=0.0,
                                       condition_on_previous_text=False, vad_filter=False, without_timestamps=True)
        return "".join(s.text for s in segments).strip()
    return decode


def main() -> None:
    ap = argparse.ArgumentParser(description="MedMap local STT worker (faster-whisper/CT2, Unix socket only)")
    ap.add_argument("--model-dir", default=os.path.expanduser("~/models/faster-whisper-large-v3-turbo"))
    ap.add_argument("--compute", default="int8_float16")
    ap.add_argument("--socket", default=default_socket_path())
    args = ap.parse_args()
    os.environ["ORT_DISABLE_TELEMETRY"] = "1"                  # 어떤 경로로든 onnxruntime 이 먼저 로드돼도 telemetry 없음
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    started = time.perf_counter()
    decode = load_ct2_decoder(args.model_dir, args.compute)
    load_ms = (time.perf_counter() - started) * 1000
    warm = time.perf_counter()
    decode(np.zeros(SR, dtype=np.float32))                   # prewarm(1 s 무음) — 첫 요청 지연 제거
    prewarm_ms = (time.perf_counter() - warm) * 1000
    try:
        vad_factory = load_silero_vad_factory()
        vad_factory()(np.zeros(VAD_FRAME, dtype=np.float32))    # VAD 도 한 번 돌려 둔다
    except Exception as exc:                                       # VAD 없이도 decode 는 제공(서버는 수동 stop 으로)
        LOG.info("worker vad_unavailable kind=%s", type(exc).__name__)
        vad_factory = None
    LOG.info("worker ready load_ms=%.1f prewarm_ms=%.1f compute=%s vad=%d", load_ms, prewarm_ms, args.compute,
             int(vad_factory is not None))
    serve(decode, args.socket, vad_factory=vad_factory)


if __name__ == "__main__":
    main()
