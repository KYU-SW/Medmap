"""Streaming STT 순수 로직(Real-time Clinical Loop): LocalAgreement-2 · 스트림 버퍼 · 메시지.

오디오·전사문은 스트림 수명 동안 메모리에만 둔다(디스크·로그 금지). PARTIAL 은 UI 전용이며
이 모듈은 매퍼·엔진·세션을 import 하지 않는다.
설계: docs/superpowers/specs/2026-09-30-medmap-realtime-streaming-stt-design.md
"""
from __future__ import annotations

import numpy as np

SR = 16000
RECENT_S = 2.5                 # pre-roll 용으로 기억하는 최근 오디오(발화와 별개, VAD 모드에서만 의미)


class StreamLimit(Exception):
    """스트림 입력이 계약을 벗어남. `code`: AUDIO_INVALID · UTTERANCE_TOO_LONG · STREAM_TOO_LONG."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class LocalAgreement:
    """LocalAgreement-2: 연속 두 가설이 같은 단어 prefix 를 내면 그 prefix 를 고정(stable)한다.

    stable 은 절대 줄지 않는다. 모델이 고정 구간과 다른 가설을 내면 unstable 을 비워 고정 prefix 만 보인다(깜빡임 방지).
    """

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._stable: list[str] = []
        self._previous: list[str] | None = None

    def update(self, hypothesis: str) -> tuple[str, str]:
        words = hypothesis.split()
        if self._previous is not None:
            agreed = []
            for a, b in zip(self._previous, words):
                if a != b:
                    break
                agreed.append(a)
            if len(agreed) > len(self._stable) and agreed[:len(self._stable)] == self._stable:
                self._stable = agreed
        self._previous = words
        stable = " ".join(self._stable)
        rest = words[len(self._stable):] if words[:len(self._stable)] == self._stable else []
        unstable = " ".join(rest)
        if unstable and stable:
            unstable = " " + unstable
        return stable, unstable


class StreamSession:
    """한 스트림의 메모리 버퍼. 발화(utterance) 단위로 PCM 을 모으고 상한을 강제한다."""

    def __init__(self, sid: str, *, max_stream_s: float = 60.0, max_utt_s: float = 30.0, sample_rate: int = SR):
        self.sid = sid
        self.sample_rate = sample_rate
        self.max_stream_samples = int(max_stream_s * sample_rate)
        self.max_utt_samples = int(max_utt_s * sample_rate)
        self.utt = 1
        self.closed = False
        self._chunks: list[np.ndarray] = []
        self._utt_samples = 0
        self._stream_samples = 0
        self._recent: list[np.ndarray] = []      # 최근 오디오(≤ RECENT_S) — VAD speech_start 때 pre-roll 로 발화 앞에 붙인다
        self._recent_samples = 0

    @property
    def utt_seconds(self) -> float:
        return self._utt_samples / self.sample_rate

    @property
    def stream_seconds(self) -> float:
        return self._stream_samples / self.sample_rate

    def append(self, pcm: bytes) -> None:
        """16-bit little-endian mono PCM 을 현재 발화에 붙인다."""
        frame = self._check(pcm)
        if self._utt_samples + frame.size > self.max_utt_samples:
            raise StreamLimit("UTTERANCE_TOO_LONG")
        self._chunks.append(frame)
        self._utt_samples += frame.size
        self._count(frame)

    def hold(self, pcm: bytes) -> None:
        """VAD 가 아직 발화를 열지 않은 오디오: 스트림 길이에는 세고 최근 버퍼에만 둔다(디코드하지 않음)."""
        self._count(self._check(pcm))

    def open_preroll(self, samples: int) -> None:
        """발화가 비어 있을 때, 최근 오디오의 끝 `samples` 개(가능한 만큼)로 발화를 시작한다(pre-roll)."""
        if self._chunks or samples <= 0 or not self._recent:
            return
        tail = np.concatenate(self._recent)[-min(samples, self.max_utt_samples):]
        self._chunks = [tail]
        self._utt_samples = tail.size

    def _check(self, pcm: bytes) -> np.ndarray:
        if len(pcm) % 2:
            raise StreamLimit("AUDIO_INVALID")
        frame = np.frombuffer(pcm, dtype="<i2")
        if self._stream_samples + frame.size > self.max_stream_samples:     # 스트림 상한을 먼저 본다
            raise StreamLimit("STREAM_TOO_LONG")
        return frame

    def _count(self, frame: np.ndarray) -> None:
        self._stream_samples += frame.size
        self._recent.append(frame)
        self._recent_samples += frame.size
        limit = int(RECENT_S * self.sample_rate)
        while self._recent and self._recent_samples - self._recent[0].size >= limit:
            self._recent_samples -= self._recent.pop(0).size

    def utterance_pcm(self) -> np.ndarray:
        """현재 발화 전체를 float32 [-1, 1] 로."""
        if not self._chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(self._chunks).astype(np.float32) / 32768.0

    def close_utterance(self, reason: str) -> int:
        """현재 발화를 닫고(버퍼 비움) 그 번호를 돌려준다. 다음 발화 번호로 넘어간다."""
        closed = self.utt
        self._chunks = []
        self._utt_samples = 0
        self.utt += 1
        return closed

    def discard(self) -> None:
        """연결 종료·오류: 오디오를 즉시 버린다. 발화 번호도 넘겨 이전 가설이 새 오디오와 짝지어지지 않게 한다."""
        self._chunks = []
        self._utt_samples = 0
        self._recent = []
        self._recent_samples = 0
        self.utt += 1
        self.closed = True


def partial_msg(utt: int, stable: str, unstable: str, audio_ms: int, srv_ms: dict) -> dict:
    return {"type": "partial", "utt": utt, "stable": stable, "unstable": unstable, "audio_ms": audio_ms, "srv_ms": srv_ms}


def final_msg(utt: int, text: str, audio_ms: int, srv_ms: dict) -> dict:
    return {"type": "final", "utt": utt, "text": text, "audio_ms": audio_ms, "srv_ms": srv_ms}


def end_msg(utt: int, reason: str) -> dict:
    return {"type": "utterance_end", "utt": utt, "reason": reason}


def error_msg(code: str) -> dict:
    return {"type": "error", "code": code}
