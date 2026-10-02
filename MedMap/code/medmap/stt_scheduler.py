"""단일 GPU 추론 큐(streaming STT).

- 추론은 한 번에 하나(anyio worker thread). 기존 WhisperTranscriber 의 inference lock 과도 직렬화된다.
- FINAL 이 대기 중인 PARTIAL 보다 먼저 처리된다.
- 같은 스트림의 PARTIAL 은 가장 최신 것 하나만 대기한다(오래된 것은 None 으로 버린다 — 낡은 결과 계산 낭비 금지).
- 오디오·전사문을 로그에 남기지 않는다.
"""
from __future__ import annotations

import asyncio
import time
from typing import Callable

import anyio
import numpy as np


class SttInferenceError(Exception):
    """추론 실패. 원래 예외의 종류 이름만 담는다(내용·traceback 없음).

    원래 예외를 그대로 넘기면 그 traceback 이 워커 코루틴 frame 을 붙잡는다. 호출자가 traceback frame 을 정리하면
    (예: unittest assertRaises 의 clear_frames) 워커 코루틴이 닫혀 이후 요청이 영원히 대기한다 → 새 예외만 넘긴다.
    """

    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


class SttScheduler:
    def __init__(self, transcribe: Callable[[np.ndarray], str], *, overload_ms: float = 1000.0, overload_window_s: float = 3.0):
        self._transcribe = transcribe
        self._overload_ms = overload_ms
        self._overload_window_s = overload_window_s
        self.last_queue_at = 0.0
        self._finals: list = []                 # [(future, audio, t_enqueue)]
        self._partials: dict = {}               # sid -> (future, audio, t_enqueue)
        self._wake: asyncio.Event | None = None
        self._worker: asyncio.Task | None = None
        self.last_queue_ms = 0.0
        self.last_decode_ms = 0.0

    @property
    def overloaded(self) -> bool:
        """최근(overload_window_s 이내) 측정된 큐 대기가 overload_ms 를 넘었는가. 오래된 측정은 과부하로 보지 않는다
        (partial 이 꺼진 채로 다음 측정이 오지 않아 영영 안 풀리는 것을 막는다)."""
        recent = time.perf_counter() - self.last_queue_at <= self._overload_window_s
        return recent and self.last_queue_ms > self._overload_ms

    def _kick(self) -> None:
        if self._wake is None:
            self._wake = asyncio.Event()
        if self._worker is None or self._worker.done():
            self._worker = asyncio.get_running_loop().create_task(self._run())
        self._wake.set()

    async def submit_partial(self, sid: str, audio: np.ndarray):
        """(text, {"queue","decode"}) 또는 더 새 partial 이 들어와 버려지면 None."""
        future = asyncio.get_running_loop().create_future()
        old = self._partials.pop(sid, None)
        if old is not None and not old[0].done():
            old[0].set_result(None)
        self._partials[sid] = (future, audio, time.perf_counter())
        self._kick()
        return await future

    async def submit_final(self, sid: str, audio: np.ndarray):
        """(text, {"queue","decode"}). 대기 중인 모든 partial 보다 먼저 처리한다."""
        future = asyncio.get_running_loop().create_future()
        self._finals.append((future, audio, time.perf_counter()))
        self._kick()
        return await future

    def _take(self):
        if self._finals:
            return self._finals.pop(0)
        if self._partials:
            sid = min(self._partials, key=lambda k: self._partials[k][2])
            return self._partials.pop(sid)
        return None

    async def _run(self) -> None:
        while True:
            item = self._take()
            if item is None:
                self._wake.clear()
                if not self._finals and not self._partials:
                    await self._wake.wait()
                continue
            future, audio, enqueued = item
            if future.done():
                continue
            started = time.perf_counter()
            self.last_queue_ms = (started - enqueued) * 1000
            self.last_queue_at = started
            try:
                text = await anyio.to_thread.run_sync(self._transcribe, audio)
            except Exception as exc:          # 호출자에게 종류만 전달(내용·traceback 없음), 워커는 계속
                kind = type(exc).__name__
                del exc
                if not future.done():
                    future.set_exception(SttInferenceError(kind))
                continue
            self.last_decode_ms = (time.perf_counter() - started) * 1000
            extra = {}
            if isinstance(text, tuple):                  # (text, {worker 쪽 타이밍}) — 숫자만
                text, extra = text
            if not future.done():
                future.set_result((text, {"queue": round(self.last_queue_ms, 1),
                                          "decode": round(self.last_decode_ms, 1), **extra}))
