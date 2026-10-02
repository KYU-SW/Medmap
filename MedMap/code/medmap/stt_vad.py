"""Streaming STT 발화 경계(VAD) 순수 로직: 확률 → speech_start / speech_end 상태기계 + 한국어 환각 문구 가드.

Silero 확률 자체는 로컬 STT worker(~/stt_ct2_env, onnxruntime CPU)가 계산한다(`stt_worker.SileroStreamVad`).
이 모듈은 numpy·torch 도 쓰지 않는 순수 파이썬이다(~/ai_env 변경 없음).
설계: docs/superpowers/specs/2026-09-30-medmap-realtime-streaming-stt-design.md §7
"""
from __future__ import annotations

import math
import os

# 알려진 Whisper 한국어 환각 문구. VAD 음성 비율이 낮은 발화에서만 제거한다(실제로 말한 경우는 유지).
HALLUCINATION_PHRASES = ("시청해주셔서 감사합니다", "구독과 좋아요")
LOW_SPEECH_RATIO = 0.3


def silence_ms_default() -> int:
    return int(os.environ.get("MEDMAP_STT_VAD_SILENCE_MS", "600"))


class Endpointer:
    """프레임 확률을 하나씩 받아 발화 시작·끝 이벤트를 낸다.

    start: 확률 ≥ start_prob 가 연속 start_ms 이상 · end: 비음성이 연속 silence_ms 이상(초기값 600 ms, 설정 가능).
    짧은 쉼(< silence_ms)은 발화를 나누지 않는다.
    """

    def __init__(self, *, frame_ms: int = 32, start_prob: float = 0.5, start_ms: int = 96,
                 silence_ms: int | None = None, preroll_ms: int = 300):
        self.frame_ms = frame_ms
        self.start_prob = start_prob
        self.silence_ms = silence_ms_default() if silence_ms is None else silence_ms
        self.start_frames = max(1, math.ceil(start_ms / frame_ms))
        self.silence_frames = max(1, math.ceil(self.silence_ms / frame_ms))
        self.preroll_ms = preroll_ms
        self.in_speech = False
        self._speech_run = 0
        self._silence_run = 0

    @property
    def silence_run_ms(self) -> int:
        """발화 중 지금까지 이어진 비음성 길이(ms). predecode 시작 판단용."""
        return self._silence_run * self.frame_ms

    def push(self, prob: float) -> list[str]:
        if prob >= self.start_prob:
            self._speech_run += 1
            self._silence_run = 0
        else:
            self._silence_run += 1
            self._speech_run = 0
        if not self.in_speech and self._speech_run >= self.start_frames:
            self.in_speech = True
            return ["speech_start"]
        if self.in_speech and self._silence_run >= self.silence_frames:
            self.in_speech = False
            return ["speech_end"]
        return []


def predecode_ms_default(silence_ms: int) -> int:
    """침묵이 이만큼 이어지면 FINAL 후보를 미리 디코드한다(speculative compute). endpoint(silence_ms)보다 짧아야 의미가 있다."""
    value = int(os.environ.get("MEDMAP_STT_VAD_PREDECODE_MS", "96"))
    return max(32, min(value, silence_ms - 32))


def filter_hallucination(text: str, speech_ratio: float | None) -> str:
    """음성 비율이 낮은(< 0.3) 발화에서만 알려진 환각 문구를 지운다. 비율을 모르면(None, 수동 모드) 그대로."""
    if speech_ratio is None or speech_ratio >= LOW_SPEECH_RATIO:
        return text
    for phrase in HALLUCINATION_PHRASES:
        text = text.replace(phrase, "")
    return " ".join(text.split())
