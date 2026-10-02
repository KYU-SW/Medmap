# MedMap Real-time Streaming STT Implementation Plan

> **For agentic workers:** 이 저장소에는 superpowers의 subagent-driven-development / executing-plans가 설치돼 있지 않다. Task 단위로 실행하고, Task마다 커밋, Milestone 끝마다 독립 reviewer(opus code-reviewer) + 사용자 보고 후 다음 Milestone. 기존 코드는 삭제하지 않는다(`project-safety-review`). 사용자 CLAUDE.md(핵심 실행 전 승인·과금 방지·nohup+ram_guard)가 이 문서보다 우선한다. Steps use checkbox (`- [ ]`) syntax.

**Goal:** 환자가 말하는 동안 PARTIAL transcript가 보이고, 발화가 끝나면 FINAL이 즉시 확정되고, FINAL 즉시 매퍼 후보가 '확인 대기'로 준비되며, 확인 후 Doctor 루프까지 REALTIME_FIRST 목표 안에서 이어지는 Real-time Clinical Loop.

**Architecture:** 브라우저 AudioWorklet이 16 kHz Int16 PCM을 ~100 ms 패킷으로 WebSocket(실패 시 HTTP chunk POST)으로 보낸다. 서버는 스트림별 메모리 버퍼 + Silero VAD(CPU)로 발화를 나누고, 기존 `WhisperTranscriber` 싱글톤(HF whisper-large-v3-turbo)을 단일 GPU 큐로 공유해 rolling 재디코드 + LocalAgreement-2로 PARTIAL을, 발화 전체 1회 디코드로 FINAL을 만든다. 모든 실패는 모아둔 PCM을 WAV로 감싸 기존 `/v1/stt/transcribe`로 보내는 fallback으로 강등된다.

**Tech Stack:** FastAPI 0.141 / uvicorn 0.53 + websockets 17.1(설치됨) · transformers 5.13 Whisper(기존) · silero-vad(M2에서 설치, 승인됨, CPU) · React 19 + Vite 8 · AudioWorklet · vitest · Playwright(캐시, 브라우저 1246 shim).

**Spec:** `docs/superpowers/specs/2026-09-30-medmap-realtime-streaming-stt-design.md` (APPROVED rev2). 원칙: `~/medmap/.claude/memory/realtime-first-principle.md`(REALTIME_FIRST).

## Global Constraints

- 상태 경계: **PARTIAL = UI only · FINAL = 매퍼 후보 준비까지 · CONFIRMED = PatientState 반영.** PARTIAL/FINAL 단계에서 `/v1/session/*`, `/v1/doctor/answer` 호출 0.
- 기존 `/v1/stt/transcribe`, `speech.decode_audio/check_speech/WhisperTranscriber`, `useRecorder`, `VoiceInput`의 입력·출력·동작 불변(추가만). 기존 `VOICE_E2E_OK` 유지.
- 매퍼(`medmap/intake/`, frozen)·진단 엔진·IG·`useMedmapSession.js`·`startPlan.js`·Doctor 코드의 의미 불변. MAX_QUESTIONS=3 불변.
- 기능 플래그: 서버 `MEDMAP_STT_STREAMING=1`일 때만 streaming endpoint 활성. 꺼져 있으면 현재 화면·동작 그대로.
- 음성·PARTIAL·FINAL: 서버 메모리(스트림 수명)만, 디스크·로그·perf 로그 금지. 클라이언트 저장소 쓰기 금지(P2-4). 로그는 bytes·ms·code·익명 run_id만.
- 상한: 스트림 누적 오디오 60 s · 발화 최대 30 s · idle 15 s · 동시 스트림 1(설정 `MEDMAP_STT_MAX_STREAMS`) · WS 메시지 64 KB · same-origin만.
- VAD: Silero, **CPU**(torch threads 1), silence 초기값 600 ms(`MEDMAP_STT_VAD_SILENCE_MS`, 조정 가능). 수동 stop 항상 가능.
- 엔진 A(현 Whisper rolling + LocalAgreement-2). **목표 latency를 낮추지 않는다**: T_partial 300~600 ms · T_final ≤ 500 ms warm · T_prep ≤ 300 ms · T_next ≤ 500 ms warm. 미달이면 M6에서 B(faster-whisper) 별도 benchmark(설치·다운로드는 그때 사용자 승인).
- GPU 작업(실제 Whisper 테스트·benchmark·음성 e2e) 전 `~/scripts/wait_for_resources.sh --check`; WAIT면 해당 단계 "미실행(경합)" 보고. 긴 실행은 `nohup` + `~/scripts/ram_guard.sh <PID> 90 60 <log>`. 서버는 ps로 실제 PID 확인 후 kill.
- 포트: 8000은 다른 프로젝트 사용 중 → 로컬 서버/e2e는 **8010**(dist 서빙). Playwright는 캐시 버전과 설치 브라우저(1246) 불일치 → `PLAYWRIGHT_PATH`에 scratchpad shim + `CHROMIUM_PATH`(메모리 `playwright-npx-cache-upgrade-breaks-browser`).
- 커밋: `git -c user.name=medmap -c user.email=<email> commit` + `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>`. 브랜치 `feat/realtime-streaming-stt`(worktree `~/medmap-worktrees/realtime-stt`). master merge는 사용자 명령 시에만.
- 금지 표현(Doctor claim 경계) 유지, 화면 영어 노출 0.
- **OFFLINE release gate(2026-09-30 추가, 사용자 지시)**: 새 dependency·새 worker·새 프로세스를 추가할 때마다 `scripts/release_offline_check.sh`(unshare -rn 네트워크 차단 + 블랙홀 경로로 연결 시도 탐지 + 양성 대조군)를 돌려 `RELEASE_OFFLINE_OK`(제품 프로세스 비-루프백 시도 0 + e2e 통과)를 받는다. 새 프로세스는 스크립트의 "프로세스" 절에 추가. 네이티브 라이브러리 telemetry(예: onnxruntime 1DS)는 import 전 비활성화.
- **M2 endpoint(2026-09-30 사용자 지시)**: speculative FINAL predecode(침묵 시작 후 후보 계산, endpoint 전 표시·상태 변경 금지) → **실제 사람 발화 녹음** replay 로 threshold 300/350/400/450/600 비교(`scripts/stt_replay_prepare.py` + `scripts/stt_vad_sweep.sh`): false endpoint·missed/delayed endpoint·누락/중복·T_final_vad p50/p95·숫자 정확성. 목표 T_final_vad p95 ≤ 500 + 문장 중간 잘림 최소. 300 을 미리 정답으로 두지 않는다. **실측 전 M2 최종 PASS 금지.** TTS 합성음 결과는 도구 점검용일 뿐 결정 근거가 아니다.

## File Structure

| 파일 | 책임 | M |
|---|---|---|
| `medmap/stt_stream.py` (new) | 순수 로직: `LocalAgreement`, `Utterance`/`StreamSession`(버퍼·상한·utt 번호·상태), 메시지 dataclass. FastAPI·torch import 없음 | 1 |
| `medmap/stt_scheduler.py` (new) | 단일 GPU 큐: 스트림별 최신 PARTIAL 1개만 유지, FINAL 우선, 과부하 판정. 추론 함수 주입(테스트 가짜) | 1 |
| `medmap/api_stt_stream.py` (new) | Router: `WS /v1/stt/stream`, `POST /v1/stt/stream`(HTTP 세션 생성), `POST /v1/stt/stream/{sid}/audio`, `POST /v1/stt/stream/{sid}/stop`, `GET /v1/stt/status`, `POST /v1/stt/prewarm` | 1 |
| `medmap/api.py` (modify, 추가만) | `include_router` 1줄 + 플래그 상수, dist mount 앞 | 1 |
| `medmap/stt_vad.py` (new) | `Endpointer`(순수 상태기계: 프레임 확률 → start/end 이벤트) + `SileroFrameVad`(silero 래퍼, CPU) | 2 |
| `medmap-web/public/pcm-worklet.js` (new) | AudioWorkletProcessor: 입력 샘플레이트 → 16 kHz Int16, 20 ms 프레임 post | 1 |
| `medmap-web/src/voice/pcm.js` (new) | `downsampleTo16k`, `floatToInt16`, `encodeWav`(순수) | 1 |
| `medmap-web/src/voice/pcmCapture.js` (new) | getUserMedia + AudioContext + worklet, 100 ms 패킷, 전체 PCM 누적(fallback용) | 1 |
| `medmap-web/src/voice/streamTransport.js` (new) | `openWsTransport`, `openHttpTransport`, `connectWithFallback`(WS → HTTP) | 1 |
| `medmap-web/src/voice/useStreamingStt.js` (new) | 상태기계·rAF partial 병합·FINAL 멱등·legacy fallback·perf mark | 1 |
| `medmap-web/src/voice/perf.js` (new) | 클라이언트 타이밍 기록(숫자만) | 1 |
| `medmap-web/src/components/StreamingVoiceInput.jsx` (new) | 말하기/그만 버튼, 준비 상태, partial 줄(stable/unstable) | 1 |
| `medmap-web/src/components/FreeTextInput.jsx` (modify, 분기 추가) | streaming 가능 시 `StreamingVoiceInput`, 아니면 기존 `VoiceInput`; 확인 대기 후보 표시 | 1, 3 |
| `medmap-web/src/api/client.js` (modify, export 추가) | `getSttStatus`, `prewarmStt` | 1 |
| `medmap-web/src/intake/usePreparedCandidates.js` (new) | FINAL 텍스트 → extract 자동 호출(최신만), 텍스트 일치 시 재사용 | 3 |
| `medmap-web/src/screens/NaturalIntakeScreen.jsx` (modify, 추가만) | [확인하기] 시 준비된 결과 재사용 | 3 |
| `scripts/bench_realtime.py` (new) | 서버 단독 streaming benchmark(합성 재생) → `exp/perf_baseline/*.json` | 4 |
| `medmap-web/e2e/realtime-stt.e2e.mjs` (new) | 가짜 마이크 streaming e2e + T_partial/T_final + fallback 강제 | 2, 4 |
| `medmap-web/e2e/doctor-latency.e2e.mjs` (new) | T_next 측정 | 5 |
| `tests/test_stt_stream.py`, `tests/test_stt_scheduler.py`, `tests/test_stt_stream_api.py`, `tests/test_stt_vad.py`, `tests/test_stt_stream_whisper_integration.py` (new) | backend 테스트 | 1–2 |

---

## Milestone 1 — Streaming transcript prototype

성공 조건(사용자): 실제 브라우저 마이크 · 말하는 동안 partial · PatientState 변경 0 · 기존 STT fallback 그대로. M1 발화 경계 = **수동 stop만**(VAD는 M2).

### Task 0: 기준선

- [ ] **Step 1:** worktree 준비(symlink, npm ci)

```bash
cd ~/medmap-worktrees/realtime-stt
ln -s ~/medmap/data data
for k in 3 5 10; do ln -s ~/medmap/exp/step16b_next_information_validation/model_k$k.pkl exp/step16b_next_information_validation/; done
ln -s ~/medmap/stt/samples stt/samples
git status --short          # symlink 가 보이지 않아야 함(/data·*.pkl·/stt/samples exclude)
cd medmap-web && npm ci --prefer-offline --no-audit --no-fund && git diff --stat package-lock.json   # 변화 0
```

- [ ] **Step 2:** 기준선 측정(변경 전) — backend 267 OK(skip 3) · vitest 238 · build OK 기대. 다르면 멈추고 보고.

```bash
cd ~/medmap-worktrees/realtime-stt && mkdir -p logs
timeout 300 ~/ai_env/bin/python -m unittest discover -s tests > logs/rt_t0_backend.log 2>&1; tail -3 logs/rt_t0_backend.log
cd medmap-web && npx vitest run 2>&1 | grep -E "Test Files|Tests " && npm run build 2>&1 | tail -1
```

- [ ] **Step 3:** spec rev2 + 이 plan 커밋 `docs: realtime streaming STT spec rev2 + implementation plan`.

### Task 1: `LocalAgreement` + `StreamSession` (순수 로직)

**Files:** Create `medmap/stt_stream.py`, Test `tests/test_stt_stream.py`

**Interfaces — Produces:**
- `class LocalAgreement: update(hypothesis: str) -> tuple[str, str]` → `(stable, unstable)`; `stable`은 단조 증가(이전 stable의 prefix를 절대 줄이지 않음). `reset()`.
- `class StreamSession(sid: str, *, max_stream_s=60.0, max_utt_s=30.0, sample_rate=16000)`: `append(pcm: bytes) -> None`(Int16 LE), `utterance_pcm() -> np.ndarray`(float32 [-1,1], 현재 발화), `close_utterance(reason: str) -> int`(utt 번호 반환, 버퍼 비움), `utt: int`, `stream_seconds: float`, `utt_seconds: float`, `closed: bool`. 상한 초과 시 `StreamLimit` 예외(`code` 속성: `STREAM_TOO_LONG`).
- 메시지 생성 함수: `partial_msg(utt, stable, unstable, audio_ms, srv_ms) -> dict`, `final_msg(utt, text, audio_ms, srv_ms) -> dict`, `end_msg(utt, reason) -> dict`, `error_msg(code) -> dict`.

- [ ] **Step 1: failing test**

```python
"""medmap/stt_stream.py 순수 로직. 실행: ~/ai_env/bin/python -m unittest tests.test_stt_stream"""
import sys, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from medmap import stt_stream as ss


def pcm(seconds, value=1000):
    return (np.full(int(16000 * seconds), value, dtype=np.int16)).tobytes()


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
        la = ss.LocalAgreement(); la.update("a b"); la.update("a b"); la.reset()
        self.assertEqual(la.update("c"), ("", "c"))


class StreamSessionTest(unittest.TestCase):
    def test_append_and_close_utterance(self):
        s = ss.StreamSession("x")
        s.append(pcm(1.0)); s.append(pcm(0.5))
        self.assertAlmostEqual(s.utt_seconds, 1.5, places=3)
        x = s.utterance_pcm()
        self.assertEqual(x.dtype, np.float32); self.assertAlmostEqual(float(x.max()), 1000 / 32768, places=5)
        self.assertEqual(s.close_utterance("manual"), 1)
        self.assertEqual(s.utt_seconds, 0.0); self.assertEqual(s.utt, 2)
        self.assertAlmostEqual(s.stream_seconds, 1.5, places=3)

    def test_limits(self):
        s = ss.StreamSession("x", max_stream_s=2.0, max_utt_s=1.0)
        s.append(pcm(1.0))
        with self.assertRaises(ss.StreamLimit) as ctx: s.append(pcm(0.1))
        self.assertEqual(ctx.exception.code, "UTTERANCE_TOO_LONG")
        s.close_utterance("max_duration"); s.append(pcm(0.9))
        with self.assertRaises(ss.StreamLimit) as ctx: s.append(pcm(0.2))
        self.assertEqual(ctx.exception.code, "STREAM_TOO_LONG")

    def test_odd_bytes_rejected(self):
        with self.assertRaises(ss.StreamLimit) as ctx: ss.StreamSession("x").append(b"\x00")
        self.assertEqual(ctx.exception.code, "AUDIO_INVALID")

    def test_messages_have_no_extra_keys(self):
        self.assertEqual(set(ss.partial_msg(1, "a", "b", 900, {"decode": 1.0})),
                         {"type", "utt", "stable", "unstable", "audio_ms", "srv_ms"})
        self.assertEqual(ss.final_msg(1, "a", 900, {})["type"], "final")
        self.assertEqual(ss.error_msg("STREAM_OVERLOADED"), {"type": "error", "code": "STREAM_OVERLOADED"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2:** `~/ai_env/bin/python -m unittest tests.test_stt_stream` → FAIL(모듈 없음).

- [ ] **Step 3: 구현**

```python
"""Streaming STT 순수 로직(Real-time Clinical Loop). 오디오·전사문은 메모리에만 두고 로그에 남기지 않는다.
PARTIAL 은 UI 전용 — 이 모듈은 매퍼·엔진·세션을 import 하지 않는다.
설계: docs/superpowers/specs/2026-09-30-medmap-realtime-streaming-stt-design.md
"""
from __future__ import annotations

import numpy as np

SR = 16000


class StreamLimit(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _words(text: str) -> list[str]:
    return text.split()


class LocalAgreement:
    """LocalAgreement-2: 연속 두 가설이 같은 단어 prefix 를 내면 그 prefix 를 고정(stable)한다. stable 은 줄지 않는다."""

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._stable: list[str] = []
        self._previous: list[str] | None = None

    def update(self, hypothesis: str) -> tuple[str, str]:
        words = _words(hypothesis)
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
        if words[:len(self._stable)] == self._stable:
            rest = words[len(self._stable):]
        else:
            rest = []            # 모델이 고정 구간을 바꾼 가설: 고정 prefix 만 보여 준다(깜빡임 방지)
        unstable = (" " + " ".join(rest)) if rest and stable else " ".join(rest)
        return stable, unstable


class StreamSession:
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

    @property
    def utt_seconds(self) -> float:
        return self._utt_samples / self.sample_rate

    @property
    def stream_seconds(self) -> float:
        return self._stream_samples / self.sample_rate

    def append(self, pcm: bytes) -> None:
        if len(pcm) % 2:
            raise StreamLimit("AUDIO_INVALID")
        frame = np.frombuffer(pcm, dtype="<i2")
        if self._stream_samples + frame.size > self.max_stream_samples:     # 스트림 상한을 먼저(발화 상한보다 우선)
            raise StreamLimit("STREAM_TOO_LONG")
        if self._utt_samples + frame.size > self.max_utt_samples:
            raise StreamLimit("UTTERANCE_TOO_LONG")
        self._chunks.append(frame)
        self._utt_samples += frame.size
        self._stream_samples += frame.size

    def utterance_pcm(self) -> np.ndarray:
        if not self._chunks:
            return np.zeros(0, dtype=np.float32)
        return (np.concatenate(self._chunks).astype(np.float32) / 32768.0)

    def close_utterance(self, reason: str) -> int:
        closed = self.utt
        self._chunks = []
        self._utt_samples = 0
        self.utt += 1
        return closed

    def discard(self) -> None:
        self._chunks = []
        self._utt_samples = 0
        self.closed = True


def partial_msg(utt: int, stable: str, unstable: str, audio_ms: int, srv_ms: dict) -> dict:
    return {"type": "partial", "utt": utt, "stable": stable, "unstable": unstable, "audio_ms": audio_ms, "srv_ms": srv_ms}


def final_msg(utt: int, text: str, audio_ms: int, srv_ms: dict) -> dict:
    return {"type": "final", "utt": utt, "text": text, "audio_ms": audio_ms, "srv_ms": srv_ms}


def end_msg(utt: int, reason: str) -> dict:
    return {"type": "utterance_end", "utt": utt, "reason": reason}


def error_msg(code: str) -> dict:
    return {"type": "error", "code": code}
```

- [ ] **Step 4:** 테스트 PASS 확인. `test_stable_never_shrinks…`의 기대값과 구현의 `rest=[]` 분기가 맞는지 확인(맞지 않으면 테스트가 아니라 구현을 고친다).
- [ ] **Step 5:** 커밋 `stt_stream: LocalAgreement-2 and in-memory StreamSession`.

### Task 2: 단일 GPU 스케줄러

**Files:** Create `medmap/stt_scheduler.py`, Test `tests/test_stt_scheduler.py`

**Interfaces — Consumes:** 없음(추론 함수 주입). **Produces:**
- `class SttScheduler(transcribe: Callable[[np.ndarray], str], *, overload_ms: float = 1000.0)`
- `async submit_partial(sid: str, audio: np.ndarray) -> tuple[str, dict] | None` — 같은 sid의 이전 대기 partial은 **버려지고** None 반환. 결과 `(hypothesis, {"queue": ms, "decode": ms})`.
- `async submit_final(sid: str, audio: np.ndarray) -> tuple[str, dict]` — 대기 중 partial보다 먼저 처리.
- `overloaded: bool` — 최근 대기 시간 > overload_ms.
- 추론은 `anyio.to_thread.run_sync`로 1개씩(직렬). 기존 `WhisperTranscriber` inference lock과 같은 싱글톤을 쓰므로 `/transcribe` 요청과도 직렬화된다.

- [ ] **Step 1: failing test**

```python
"""SttScheduler: 최신 partial 만, final 우선, 직렬 실행. 실행: ~/ai_env/bin/python -m unittest tests.test_stt_scheduler"""
import asyncio, sys, threading, time, unittest
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from medmap.stt_scheduler import SttScheduler


class FakeModel:
    def __init__(self, delay=0.05):
        self.calls, self.delay, self.active, self.max_active = [], delay, 0, 0
        self.lock = threading.Lock()
    def __call__(self, audio):
        with self.lock:
            self.active += 1; self.max_active = max(self.max_active, self.active)
        time.sleep(self.delay)
        with self.lock:
            self.active -= 1
        self.calls.append(len(audio))
        return f"len{len(audio)}"


def run(coro):
    return asyncio.run(coro)


class SchedulerTest(unittest.TestCase):
    def test_latest_partial_wins(self):
        model = FakeModel(0.1); sch = SttScheduler(model)
        async def go():
            first = asyncio.create_task(sch.submit_partial("s", np.zeros(10)))
            await asyncio.sleep(0.01)                          # first 가 실행 중
            stale = asyncio.create_task(sch.submit_partial("s", np.zeros(20)))
            latest = asyncio.create_task(sch.submit_partial("s", np.zeros(30)))
            return await first, await stale, await latest
        a, b, c = run(go())
        self.assertEqual(a[0], "len10"); self.assertIsNone(b); self.assertEqual(c[0], "len30")
        self.assertEqual(model.calls, [10, 30])

    def test_final_before_waiting_partial_and_serial(self):
        model = FakeModel(0.05); sch = SttScheduler(model)
        async def go():
            busy = asyncio.create_task(sch.submit_partial("a", np.zeros(1)))
            await asyncio.sleep(0.01)
            p = asyncio.create_task(sch.submit_partial("b", np.zeros(2)))
            f = asyncio.create_task(sch.submit_final("c", np.zeros(3)))
            await asyncio.gather(busy, p, f)
        run(go())
        self.assertEqual(model.calls, [1, 3, 2])
        self.assertEqual(model.max_active, 1)

    def test_timings_and_overload(self):
        sch = SttScheduler(FakeModel(0.02), overload_ms=1.0)
        async def go():
            await asyncio.gather(*(sch.submit_final(str(i), np.zeros(1)) for i in range(3)))
        run(go())
        self.assertTrue(sch.overloaded)
        text, ms = run(SttScheduler(FakeModel(0.0)).submit_final("x", np.zeros(5)))
        self.assertEqual(set(ms), {"queue", "decode"})


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2:** FAIL 확인.
- [ ] **Step 3: 구현**

```python
"""단일 GPU 추론 큐(streaming STT). FINAL 우선, 스트림별 최신 PARTIAL 1개만. 오디오·결과를 로그에 남기지 않는다."""
from __future__ import annotations

import asyncio
import time
from typing import Callable

import anyio
import numpy as np


class SttScheduler:
    def __init__(self, transcribe: Callable[[np.ndarray], str], *, overload_ms: float = 1000.0):
        self._transcribe = transcribe
        self._overload_ms = overload_ms
        self._finals: list = []                 # [(future, sid, audio, t_enqueue)]
        self._partials: dict = {}               # sid -> (future, audio, t_enqueue)
        self._wake = asyncio.Event()
        self._worker: asyncio.Task | None = None
        self.last_queue_ms = 0.0

    @property
    def overloaded(self) -> bool:
        return self.last_queue_ms > self._overload_ms

    def _ensure_worker(self) -> None:
        if self._worker is None or self._worker.done():
            self._worker = asyncio.get_running_loop().create_task(self._run())

    async def submit_partial(self, sid: str, audio: np.ndarray):
        loop = asyncio.get_running_loop()
        old = self._partials.pop(sid, None)
        if old is not None and not old[0].done():
            old[0].set_result(None)               # 대기 중이던 오래된 partial 은 버린다
        future = loop.create_future()
        self._partials[sid] = (future, audio, time.perf_counter())
        self._ensure_worker(); self._wake.set()
        return await future

    async def submit_final(self, sid: str, audio: np.ndarray):
        future = asyncio.get_running_loop().create_future()
        self._finals.append((future, sid, audio, time.perf_counter()))
        self._ensure_worker(); self._wake.set()
        return await future

    def _next(self):
        if self._finals:
            future, _sid, audio, t0 = self._finals.pop(0)
            return future, audio, t0
        if self._partials:
            sid = min(self._partials, key=lambda k: self._partials[k][2])
            future, audio, t0 = self._partials.pop(sid)
            return future, audio, t0
        return None

    async def _run(self) -> None:
        while True:
            item = self._next()
            if item is None:
                self._wake.clear()
                if self._next_peek_empty():
                    await self._wake.wait()
                continue
            future, audio, t0 = item
            if future.done():
                continue
            started = time.perf_counter()
            self.last_queue_ms = (started - t0) * 1000
            try:
                text = await anyio.to_thread.run_sync(self._transcribe, audio)
            except Exception as exc:              # 내용 없이 예외 종류만 호출자에게
                if not future.done():
                    future.set_exception(exc)
                continue
            if not future.done():
                future.set_result((text, {"queue": round(self.last_queue_ms, 1),
                                          "decode": round((time.perf_counter() - started) * 1000, 1)}))

    def _next_peek_empty(self) -> bool:
        return not self._finals and not self._partials
```

- [ ] **Step 4:** PASS 확인. **Step 5:** 커밋 `stt_scheduler: single GPU queue, final-first, latest partial only`.

### Task 3: Streaming API (WS + HTTP chunk + status/prewarm), 플래그 뒤

**Files:** Create `medmap/api_stt_stream.py`; Modify `medmap/api.py`(dist mount 앞에 추가만); Test `tests/test_stt_stream_api.py`

**Interfaces — Consumes:** Task 1 `StreamSession`, `LocalAgreement`, 메시지 함수; Task 2 `SttScheduler`; 기존 `speech.get_transcriber()`, `speech.check_speech`, `speech.start_prewarm`. **Produces(프로토콜, spec §6-1):**
- `GET /v1/stt/status` → `{"streaming": bool, "stt_state": "WARM"|"LOADING"|"COLD"|"UNAVAILABLE", "vad": "manual"|"server"}` (플래그 off면 `streaming:false`)
- `POST /v1/stt/prewarm` → 202 `{"stt_state": ...}`(멱등, 로드만 트리거)
- `WS /v1/stt/stream`: C→S JSON `start{sample_rate:16000, format:"s16le", run_id}` → S `ready{stt_state, vad}`; C→S binary PCM; S→C `partial` 주기(tick); C→S `{"type":"stop"}` → S `utterance_end{reason:"manual"}` → `final` → 연결 유지(다음 발화) 또는 C가 `{"type":"close"}`
- `POST /v1/stt/stream` → `{"sid"}`(스트림 수 초과 시 429 `STREAM_BUSY`, WS는 `error_msg("STREAM_BUSY")`); `expire_idle()`(모듈 함수, 요청마다 호출 + 테스트에서 직접 호출); `POST /v1/stt/stream/{sid}/audio`(body PCM, header `x-audio-end-ms`) → `{"messages":[...]}`(그 사이 생긴 partial/final); `POST /v1/stt/stream/{sid}/stop` → `{"messages":[... final]}`; idle 15 s 자동 폐기.
- 서버 모듈 상수: `STREAMING = os.environ.get("MEDMAP_STT_STREAMING") == "1"`, `PARTIAL_TICK_MS = 400`(동적: `max(400, 1.2*last_decode_ms)`), `MAX_STREAMS`.
- partial 계산: tick마다 `utterance_pcm()`에 `check_speech` 통과 시에만 `submit_partial`(무음·0.3 s 미만은 건너뜀 — 환각 방지), 결과를 `LocalAgreement.update`로 stable/unstable 생성. final: `submit_final(utterance_pcm())` → LocalAgreement.reset.
- 오류 → `error_msg(code)` 후 close: `STREAMING_DISABLED`, `STREAM_BUSY`(MAX_STREAMS 초과), `AUDIO_INVALID`, `STREAM_TOO_LONG`, `UTTERANCE_TOO_LONG`(→ 자동 manual finalize 후 계속), `STT_UNAVAILABLE`, `STREAM_OVERLOADED`.
- 로그: `LOG.info("stt_stream sid_hash=%s event=%s ms=%.1f audio_ms=%d code=%s")` 숫자·코드만. Origin 헤더가 Host와 다르면 WS 거부(403).

- [ ] **Step 1: failing test** (가짜 transcriber 주입 — `api_stt_stream.set_transcribe_for_tests(fn)`; 실제 Whisper 없음)

```python
"""/v1/stt/stream* 회귀(가짜 transcriber). 실행: MEDMAP_STT_STREAMING=1 ~/ai_env/bin/python -m unittest tests.test_stt_stream_api"""
import os, sys, unittest, warnings
from pathlib import Path
import numpy as np
os.environ["MEDMAP_STT_STREAMING"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.filterwarnings("ignore")
from fastapi.testclient import TestClient
from medmap import api as api_module
from medmap import api_stt_stream as st

SPEECH = (np.sin(np.linspace(0, 2000, 16000)) * 8000).astype(np.int16).tobytes()     # 1 s 톤(무음 아님)
CLIENT = TestClient(api_module.app)


def fake(audio):
    return "어제부터 배가 아팠어요"[: max(1, int(len(audio) / 16000 * 4))]


def setUpModule():
    CLIENT.__enter__(); st.set_transcribe_for_tests(fake)


def tearDownModule():
    st.set_transcribe_for_tests(None); CLIENT.__exit__(None, None, None)


class StreamWsTest(unittest.TestCase):
    def test_status(self):
        body = CLIENT.get("/v1/stt/status").json()
        self.assertTrue(body["streaming"]); self.assertIn(body["stt_state"], {"WARM", "LOADING", "COLD", "UNAVAILABLE"})

    def test_ws_partial_then_final_on_stop(self):
        with CLIENT.websocket_connect("/v1/stt/stream", headers={"origin": "http://testserver"}) as ws:
            ws.send_json({"type": "start", "sample_rate": 16000, "format": "s16le", "run_id": "r1"})
            self.assertEqual(ws.receive_json()["type"], "ready")
            for _ in range(3):
                ws.send_bytes(SPEECH)
            seen = []
            ws.send_json({"type": "stop"})
            while True:
                msg = ws.receive_json(); seen.append(msg)
                if msg["type"] == "final":
                    break
            types = [m["type"] for m in seen]
            self.assertIn("utterance_end", types)
            final = seen[-1]
            self.assertEqual((final["utt"], final["text"]), (1, fake(np.zeros(48000))))
            self.assertEqual(set(final), {"type", "utt", "text", "audio_ms", "srv_ms"})

    def test_ws_rejects_cross_origin_and_bad_format(self):
        with self.assertRaises(Exception):
            with CLIENT.websocket_connect("/v1/stt/stream", headers={"origin": "http://evil.example"}) as ws:
                ws.receive_json()
        with CLIENT.websocket_connect("/v1/stt/stream", headers={"origin": "http://testserver"}) as ws:
            ws.send_json({"type": "start", "sample_rate": 44100, "format": "s16le", "run_id": "r"})
            self.assertEqual(ws.receive_json(), {"type": "error", "code": "AUDIO_INVALID"})


class StreamHttpTest(unittest.TestCase):
    def test_http_chunk_path(self):
        sid = CLIENT.post("/v1/stt/stream", json={"sample_rate": 16000, "format": "s16le", "run_id": "r2"}).json()["sid"]
        for i in range(2):
            r = CLIENT.post(f"/v1/stt/stream/{sid}/audio", content=SPEECH,
                            headers={"content-type": "application/octet-stream", "x-audio-end-ms": str((i + 1) * 1000)})
            self.assertEqual(r.status_code, 200)
        msgs = CLIENT.post(f"/v1/stt/stream/{sid}/stop").json()["messages"]
        self.assertEqual(msgs[-1]["type"], "final")
        self.assertEqual(CLIENT.post(f"/v1/stt/stream/{sid}/audio", content=SPEECH,
                                     headers={"content-type": "application/octet-stream"}).status_code, 404)

    def test_no_text_or_audio_in_logs(self):
        with self.assertLogs("medmap", level="DEBUG") as logs:
            sid = CLIENT.post("/v1/stt/stream", json={"sample_rate": 16000, "format": "s16le", "run_id": "r3"}).json()["sid"]
            CLIENT.post(f"/v1/stt/stream/{sid}/audio", content=SPEECH, headers={"content-type": "application/octet-stream"})
            CLIENT.post(f"/v1/stt/stream/{sid}/stop")
            api_module.LOG.info("probe")
        joined = "\n".join(logs.output)
        self.assertNotIn("배가", joined); self.assertNotIn(sid, joined)

    def test_existing_transcribe_route_unchanged(self):
        r = CLIENT.post("/v1/stt/transcribe", content=b"", headers={"content-type": "audio/wav"})
        self.assertEqual(r.json()["error"]["code"], "AUDIO_EMPTY")


class LimitsTest(unittest.TestCase):
    def test_second_stream_busy(self):
        with CLIENT.websocket_connect("/v1/stt/stream", headers={"origin": "http://testserver"}) as ws1:
            ws1.send_json({"type": "start", "sample_rate": 16000, "format": "s16le", "run_id": "a"})
            ws1.receive_json()
            r = CLIENT.post("/v1/stt/stream", json={"sample_rate": 16000, "format": "s16le", "run_id": "b"})
            self.assertEqual((r.status_code, r.json()["error"]["code"]), (429, "STREAM_BUSY"))

    def test_http_idle_expiry(self):
        sid = CLIENT.post("/v1/stt/stream", json={"sample_rate": 16000, "format": "s16le", "run_id": "c"}).json()["sid"]
        st._http_streams[sid].touched -= st.IDLE_S + 1          # 가짜 시계 대신 마지막 접촉 시각을 과거로
        st.expire_idle()
        self.assertEqual(CLIENT.post(f"/v1/stt/stream/{sid}/stop").status_code, 404)

    def test_prewarm_idempotent(self):
        a = CLIENT.post("/v1/stt/prewarm"); b = CLIENT.post("/v1/stt/prewarm")
        self.assertEqual((a.status_code, b.status_code), (202, 202))


class FlagOffTest(unittest.TestCase):
    def test_disabled_flag(self):
        st.STREAMING = False
        try:
            self.assertFalse(CLIENT.get("/v1/stt/status").json()["streaming"])
            self.assertEqual(CLIENT.post("/v1/stt/stream", json={"sample_rate": 16000, "format": "s16le", "run_id": "r"}).status_code, 404)
        finally:
            st.STREAMING = True


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2:** FAIL 확인.
- [ ] **Step 3: 구현** `medmap/api_stt_stream.py` — 아래 구조 그대로(세부는 Interfaces 계약을 따른다):

```python
"""Streaming STT 라우터(opt-in MEDMAP_STT_STREAMING=1). PARTIAL 은 UI 전용 — 매퍼·엔진·세션을 호출하지 않는다.
오디오·전사문은 스트림 수명 동안 메모리에만, 로그에는 숫자·코드만(sid 도 해시)."""
from __future__ import annotations

import asyncio, hashlib, logging, os, time, uuid

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

from . import speech
from .stt_scheduler import SttScheduler
from .stt_stream import LocalAgreement, StreamLimit, StreamSession, end_msg, error_msg, final_msg, partial_msg

LOG = logging.getLogger("medmap.stt_stream")
STREAMING = os.environ.get("MEDMAP_STT_STREAMING") == "1"
MAX_STREAMS = int(os.environ.get("MEDMAP_STT_MAX_STREAMS", "1"))
PARTIAL_TICK_MS = 400
IDLE_S = 15.0
MAX_WS_MESSAGE = 64 * 1024

router = APIRouter()
_override = None
_scheduler: SttScheduler | None = None
_http_streams: dict = {}          # sid -> _Stream


def set_transcribe_for_tests(fn) -> None:
    global _override, _scheduler
    _override, _scheduler = fn, None


def _transcribe(audio):
    return _override(audio) if _override else speech.get_transcriber().transcribe(audio)


def scheduler() -> SttScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = SttScheduler(_transcribe)
    return _scheduler


def stt_state() -> str:
    if _override is not None:
        return "WARM"
    t = speech.get_transcriber()
    return "WARM" if t._pipeline is not None else ("LOADING" if t._load_lock.locked() else "COLD")


def _h(sid: str) -> str:
    return hashlib.sha256(sid.encode()).hexdigest()[:8]


class _Stream:
    """한 스트림(WS 또는 HTTP)의 상태. 메시지는 out 큐로 나간다."""

    def __init__(self, sid: str):
        self.session = StreamSession(sid)
        self.agree = LocalAgreement()
        self.out: list[dict] = []
        self.audio_end_ms = 0
        self.last_partial_at = 0.0
        self.tick_ms = PARTIAL_TICK_MS
        self.touched = time.monotonic()
        self.partial_task: asyncio.Task | None = None

    async def feed(self, pcm: bytes, audio_end_ms: int | None) -> None:
        self.touched = time.monotonic()
        try:
            self.session.append(pcm)
        except StreamLimit as exc:
            if exc.code == "UTTERANCE_TOO_LONG":
                await self.finalize("max_duration")
                self.session.append(pcm)
            else:
                raise
        self.audio_end_ms = audio_end_ms if audio_end_ms is not None else int(self.session.stream_seconds * 1000)
        now = time.monotonic() * 1000
        if now - self.last_partial_at >= self.tick_ms and (self.partial_task is None or self.partial_task.done()):
            self.last_partial_at = now
            self.partial_task = asyncio.create_task(self._partial())

    async def _partial(self) -> None:
        audio = self.session.utterance_pcm()
        try:
            speech.check_speech(audio, audio.size / 16000)
        except speech.AudioEmpty:
            return
        utt, audio_ms = self.session.utt, self.audio_end_ms
        result = await scheduler().submit_partial(self.session.sid, audio)
        if result is None or utt != self.session.utt:
            return
        text, ms = result
        self.tick_ms = max(PARTIAL_TICK_MS, 1.2 * ms["decode"])
        stable, unstable = self.agree.update(text)
        self.out.append(partial_msg(utt, stable, unstable, audio_ms, ms))

    async def finalize(self, reason: str) -> None:
        audio = self.session.utterance_pcm()
        audio_ms = self.audio_end_ms
        utt = self.session.close_utterance(reason)
        self.agree.reset()
        self.out.append(end_msg(utt, reason))
        try:
            speech.check_speech(audio, audio.size / 16000)
        except speech.AudioEmpty:
            self.out.append(final_msg(utt, "", audio_ms, {}))
            return
        text, ms = await scheduler().submit_final(self.session.sid, audio)
        self.out.append(final_msg(utt, text, audio_ms, ms))
        LOG.info("stt_stream sid=%s event=final audio_ms=%d decode_ms=%.1f", _h(self.session.sid), audio_ms, ms["decode"])

    def drain(self) -> list[dict]:
        out, self.out = self.out, []
        return out

    def close(self) -> None:
        self.session.discard()
```

(`/v1/stt/status`, `/v1/stt/prewarm`, WS 핸들러(Origin 검사 → start 검증 → ready → 수신 루프: bytes → `feed` → `drain` 송신 / `stop` → `finalize("manual")` → drain / `close` → 종료, finally `close()`), HTTP 3 endpoint(`_http_streams` + idle 정리) 를 같은 파일에 둔다. 모든 예외 로그는 `type(exc).__name__`만.)

`medmap/api.py` — 기존 Doctor include 바로 아래, dist mount 앞에 추가:

```python
from .api_stt_stream import router as _stt_stream_router  # noqa: E402

app.include_router(_stt_stream_router)
```

- [ ] **Step 4:** `MEDMAP_STT_STREAMING=1 ~/ai_env/bin/python -m unittest tests.test_stt_stream_api` PASS + 전체 backend(기존 267 유지) PASS. `git diff --numstat master -- medmap/api.py` = 추가만.
- [ ] **Step 5:** 커밋 `api_stt_stream: WS and HTTP chunk streaming behind MEDMAP_STT_STREAMING, status/prewarm`.

### Task 4: 실제 Whisper 통합 테스트 (GPU, 게이트)

**Files:** Create `tests/test_stt_stream_whisper_integration.py`(기존 `test_stt_whisper_integration.py`처럼 `MEDMAP_RUN_WHISPER=1`일 때만 실행, 아니면 skip)

- [ ] **Step 1:** 테스트: `stt/samples/medmap_tts_test.wav`를 16 kHz Int16으로 읽어 100 ms 패킷으로 `_Stream.feed`(실시간 속도 `asyncio.sleep(0.1)`) → stop. 검증: (a) partial 1개 이상, (b) 모든 partial의 stable이 단조 증가, (c) FINAL 텍스트 == 같은 오디오로 `speech.get_transcriber().transcribe()` 결과(같은 모델 → 동일), (d) 기존 `/v1/stt/transcribe`에 같은 WAV → 같은 텍스트, (e) partial·final의 `srv_ms` 기록.
- [ ] **Step 2:** `~/scripts/wait_for_resources.sh --check` → OK일 때만 `MEDMAP_RUN_WHISPER=1 nohup ~/ai_env/bin/python -m unittest tests.test_stt_stream_whisper_integration > logs/rt_t4_whisper.log 2>&1 &` + ram_guard. WAIT면 "미실행(경합)" 기록 후 Task 5 진행, M1 완료 전 재시도.
- [ ] **Step 3:** 커밋 `Whisper streaming integration test (gated)`.

### Task 5: 브라우저 PCM 캡처 (worklet + 순수 함수)

**Files:** Create `medmap-web/public/pcm-worklet.js`, `medmap-web/src/voice/pcm.js`, `medmap-web/src/voice/pcmCapture.js`; Test `medmap-web/src/voice/pcm.test.js`, `pcmCapture.test.js`

**Interfaces — Produces:**
- `pcm.js`: `downsampleTo16k(float32: Float32Array, inputRate: number): Float32Array`(평균 decimation, 16000이면 복사), `floatToInt16(f: Float32Array): Int16Array`(clip), `encodeWav(chunks: Int16Array[], sampleRate=16000): Blob`(`audio/wav`, 44-byte header).
- `pcmCapture.js`: `startPcmCapture({ onPacket, getUserMedia, AudioContextImpl, packetMs = 100, now }) -> Promise<{ stop(): Int16Array[], sampleRate: number }>`; `onPacket({ pcm: ArrayBuffer, audioEndMs: number, capturedAt: number })`. 전체 Int16 청크를 누적해 `stop()`이 반환(legacy fallback용). 오류는 `{ type: 'permission'|'no_mic'|'unsupported'|'start_failed' }` throw(기존 `useRecorder` 분류와 동일 문자열).
- worklet: `registerProcessor('medmap-pcm', ...)` — `sampleRate` 전역으로 입력률 확인, 128-sample 블록을 모아 20 ms(16 kHz 기준 320) 프레임 단위로 `port.postMessage(Float32Array)`(다운샘플은 worklet 안에서 `downsampleTo16k`와 같은 알고리즘).

- [ ] **Step 1: failing tests**

```js
import { downsampleTo16k, encodeWav, floatToInt16 } from './pcm.js'

test('downsample 48k → 16k keeps length ratio and averages', () => {
  const x = new Float32Array(480).fill(0.5)
  const y = downsampleTo16k(x, 48000)
  expect(y.length).toBe(160)
  expect(y[0]).toBeCloseTo(0.5)
  expect(downsampleTo16k(new Float32Array([0.1, 0.2]), 16000)).toEqual(new Float32Array([0.1, 0.2]))
})

test('floatToInt16 clips', () => {
  expect(Array.from(floatToInt16(new Float32Array([2, -2, 0, 0.5])))).toEqual([32767, -32768, 0, 16384])
})

test('encodeWav header + payload', async () => {
  const blob = encodeWav([new Int16Array([1, 2]), new Int16Array([3])], 16000)
  expect(blob.type).toBe('audio/wav')
  const buf = new DataView(await blob.arrayBuffer())
  expect(buf.byteLength).toBe(44 + 6)
  expect(String.fromCharCode(buf.getUint8(0), buf.getUint8(1), buf.getUint8(2), buf.getUint8(3))).toBe('RIFF')
  expect(buf.getUint32(24, true)).toBe(16000)
  expect(buf.getInt16(44 + 4, true)).toBe(3)
})
```

`pcmCapture.test.js`: 가짜 `AudioContextImpl`(audioWorklet.addModule 기록, `AudioWorkletNode` 가짜 port로 320-sample 프레임 16개 주입) → `onPacket` 3회(100 ms 묶음), `audioEndMs` 100/200/300, `stop()`이 모든 Int16 반환 + 트랙 stop + context close; getUserMedia `NotAllowedError` → `{type:'permission'}`; `audioWorklet` 없음 → `{type:'unsupported'}`.

- [ ] **Step 2:** FAIL 확인. **Step 3:** 구현(위 인터페이스). **Step 4:** PASS. **Step 5:** 커밋 `voice: AudioWorklet 16 kHz PCM capture + wav encoder`.

### Task 6: Transport (WS → HTTP chunk)

**Files:** Create `medmap-web/src/voice/streamTransport.js`; Modify `medmap-web/src/api/client.js`(export 추가: `getSttStatus()`, `prewarmStt()`); Test `streamTransport.test.js`

**Interfaces — Produces:** `connectWithFallback({ onMessage, runId, WebSocketImpl, fetchImpl, wsTimeoutMs = 2000 }) -> Promise<{ kind: 'ws'|'http', send(pcm: ArrayBuffer, audioEndMs: number), stop(): Promise<void>, close() }>`. WS URL은 `location`에서 `ws(s)://host/v1/stt/stream`. WS open 실패 또는 `ready` 미수신 2 s → HTTP(`POST /v1/stt/stream` → sid; `send`는 100 ms 패킷을 최대 300 ms 묶어 POST, 응답 `messages`를 `onMessage`로; `stop`은 `/stop` 응답 messages 전달). 둘 다 실패 → reject `{ type: 'transport_failed' }`.

- [ ] Steps: 가짜 WebSocket(open→ready 메시지)으로 kind='ws' · open error → kind='http'(fetch 가짜가 sid·messages 반환) · ready 타임아웃(fake timers) → http · 둘 다 실패 → reject · HTTP send가 300 ms 묶음으로 POST 하고 `x-audio-end-ms` 헤더 설정 · 메시지 순서 보존. 구현 → PASS → 커밋 `voice: stream transport with WS→HTTP fallback`.

### Task 7: `useStreamingStt` + `StreamingVoiceInput` + FreeTextInput 분기

**Files:** Create `medmap-web/src/voice/perf.js`, `useStreamingStt.js`, `components/StreamingVoiceInput.jsx`; Modify `components/FreeTextInput.jsx`(분기 추가만); Test `useStreamingStt.test.jsx`, `StreamingVoiceInput.test.jsx`, `FreeTextInput.test.jsx`(기존 파일에 케이스 추가)

**Interfaces — Produces:**
- `perf.js`: `perfMark(name, fields)` → 메모리 링버퍼(최대 500)에 `{name, t: performance.now(), ...fields}`(숫자·코드만), `perfEntries()`, `perfReset()`; `window.__medmapPerf`로 e2e가 읽음.
- `useStreamingStt({ onFinal, capture = startPcmCapture, connect = connectWithFallback, transcribeLegacy = transcribeAudio, now })` → `{ state: 'idle'|'connecting'|'listening'|'finalizing', partial: {stable, unstable}, transport: 'ws'|'http'|'legacy'|null, error, start(), stop() }`.
  - partial 메시지는 rAF로 병합해 state 반영(초당 ≤ ~10회). `T_partial` 계산: 패킷 송신 시 `audioEndMs → capturedAt` 맵 저장, partial 렌더 시 `perfMark('partial_render', {audio_ms, t_partial: now - capturedAt(audio_ms)})`.
  - final: `utt` 기준 멱등(같은 utt 두 번 오면 무시) → `onFinal(text)` → partial 비움 → `perfMark('final_render', {audio_ms, t_final})`.
  - transport 실패/서버 error/도중 끊김 → 모아둔 PCM을 `encodeWav`로 감싸 `transcribeLegacy(blob)` → `onFinal`(transport='legacy'). 캡처 실패(unsupported) → `error` 설정(부모가 기존 VoiceInput으로 전환).
  - **API 호출은 STT 경로뿐**: 세션·매퍼 호출 없음.
- `StreamingVoiceInput({ onTranscript, disabled, onBusyChange })`: 기존 VoiceInput과 같은 props + 버튼 문구(🎙 말하기 / 그만 말하기), 준비 상태("음성 엔진 준비 중…" = status LOADING/COLD), partial 줄(`data-testid="stt-partial"`, `aria-live="polite"`, stable `strong`/unstable `span.stt-unstable`), 오류 문구는 기존 VoiceInput 메시지 재사용(export 추가).
- `FreeTextInput`: mount 시 `getSttStatus()`(실패 → false) → `streaming && hasAudioWorklet`이면 `StreamingVoiceInput`, 아니면 기존 `VoiceInput`(현재와 동일). `onTranscript`는 기존과 같은 `joinTranscript` 경로 → **textarea에는 FINAL만**. mount 시 `prewarmStt()` 1회(실패 무시).

- [ ] **Step 1: failing tests (핵심 케이스)**

```jsx
// useStreamingStt.test.jsx (가짜 capture/connect)
test('partial is UI-only and final is delivered once per utterance', async () => { /* 가짜 connect 가 partial×2, final(utt1)×2(중복) 전달
  → result.current.partial 갱신, onFinal 1회, fetch 로 /v1/session·/v1/intake 호출 0 */ })
test('transport failure falls back to legacy /transcribe with WAV of captured PCM', async () => { /* connect reject → stop() 시
  transcribeLegacy 가 type audio/wav blob 으로 1회 호출, onFinal(legacy text), transport==='legacy' */ })
test('server error mid-stream falls back without losing audio', async () => { /* error 메시지 → legacy 에 전체 PCM */ })
test('capture unsupported surfaces error for parent fallback', async () => { /* capture throws {type:'unsupported'} */ })
// FreeTextInput.test.jsx 추가
test('streaming off → existing VoiceInput rendered (unchanged)', async () => { /* getSttStatus → {streaming:false} */ })
test('partial never touches textarea; final appends via joinTranscript', async () => { /* textarea value 불변 while partial,
  selectionStart 유지, final 후 값 === joinTranscript(prev, final) */ })
```

(각 테스트 본문은 기존 `VoiceInput.test.jsx`/`useRecorder.test.js`의 가짜 주입 패턴을 그대로 따른다: 의존성을 props/옵션으로 주입, `vi.useFakeTimers()`로 rAF·타임아웃 제어.)

- [ ] **Step 2:** FAIL 확인. **Step 3:** 구현. **Step 4:** vitest 전체(238 + 신규) PASS, build OK. **Step 5:** 커밋 `voice: useStreamingStt + StreamingVoiceInput behind server flag; textarea receives FINAL only`.

### Task 8: M1 e2e + 실기기 전 로컬 확인 + 리뷰 게이트

- [ ] **Step 1:** `medmap-web/e2e/realtime-stt.e2e.mjs` — 기존 voice e2e처럼 Chromium 가짜 마이크(`--use-file-for-fake-audio-capture=<wav>%noloop`), 서버 `MEDMAP_STT_STREAMING=1 MEDMAP_SERVE_WEB_DIST=medmap-web/dist uvicorn … --port 8010`. 시나리오: (A) 말하는 동안 `stt-partial`이 비어 있지 않은 시점이 FINAL 이전에 ≥1회 · stop → textarea에 FINAL · 요청 로그에 `/v1/session/*`·`/v1/intake/extract` 0 · (B) WS 차단(`page.route('**/v1/stt/stream', abort)` + WS 차단 스크립트) → HTTP 경로로 동일 결과 · (C) streaming 엔드포인트 전부 차단 → legacy `/v1/stt/transcribe` 1회로 FINAL · 390/1280. 성공 `REALTIME_STT_E2E_OK`. `window.__medmapPerf`에서 `t_partial`, `t_final` 수집해 `logs/rt_m1_perf.json`(숫자만).
- [ ] **Step 2:** GPU `--check` OK일 때 실행(WAIT면 미실행 보고). 기존 e2e 6종(텍스트 5 + 음성) 회귀 — 플래그 on/off 각각 음성 e2e.
- [ ] **Step 3:** opus code-reviewer whole-branch 리뷰 → 수정 → 사용자에게 M1 보고(측정값: T_partial/T_final p50·p95, warm/cold, GPU 조건 명시). **사용자 확인 전 M2 착수 금지.**

---

## Milestone 2 — VAD + finalization

성공 조건: speech stop 검출 · FINAL(현 Whisper finalizer) · transcript 중복/손실 0.

### Task 9: Silero 설치 (승인됨, 기록 필수)

> **변경(2026-09-30, 사용자 결정 "worker 환경 재사용")**: `~/ai_env` 변경 금지 규칙과 충돌하므로 아래 Step 1–3(ai_env 에 silero-vad 설치)은 **실행하지 않는다**.
> 대신 worker venv(`~/stt_ct2_env`)에 이미 있는 `faster_whisper/assets/silero_vad_v6.onnx` + onnxruntime 1.30(CPU, thread 1)을 쓴다 — 새 설치·다운로드 0.
> Silero 확률은 worker 의 `vad` op(연결마다 h·c·context 상태, decode lock 과 무관)가 계산하고, 서버(`~/ai_env`)는 순수 `Endpointer`(`medmap/stt_vad.py`)만 돌린다.
> 결과: VAD 는 `MEDMAP_STT_ENGINE=ct2` + worker 가 VAD 지원일 때만 켜진다(`MEDMAP_STT_VAD=0` 으로 끔). hf 엔진·VAD 장애 시 수동 stop(M1 동작).
> Task 10 의 `SileroFrameVad` → `stt_worker.SileroStreamVad`(worker 쪽) + `WorkerClient.vad_probs`(서버 쪽, 스트림 전용 연결)로 대체.
> Task 12 의 합성 WAV(D) 대신 기존 샘플을 그대로 쓴다: 두 문장 사이 무음이 ≈ 830 ms(Silero 실측) > 600 ms 라 자동 FINAL 2개가 나와야 한다.

- [ ] **Step 1:** 설치 전 `~/ai_env/bin/pip freeze > logs/rt_t9_freeze_before.txt`.
- [ ] **Step 2:** `~/ai_env/bin/pip install "silero-vad==6.2.3"` (torch 기존 사용, onnxruntime 불필요). 설치 후 `pip check`, freeze diff를 `docs/environment_changes.md`(신규)에 날짜·패키지·이유로 기록. torch/transformers 버전이 바뀌었으면 **멈추고 보고**.
- [ ] **Step 3:** backend 전체 회귀(267 + M1 신규) PASS. 커밋 `env: add silero-vad 6.2.3 (CPU VAD), recorded`.

### Task 10: `Endpointer` (순수 상태기계) + `SileroFrameVad`

**Files:** Create `medmap/stt_vad.py`; Test `tests/test_stt_vad.py`

**Interfaces — Produces:**
- `Endpointer(*, frame_ms=32, start_prob=0.5, start_ms=96, silence_ms=int(os.environ.get("MEDMAP_STT_VAD_SILENCE_MS", 600)), preroll_ms=300)`: `push(prob: float) -> list[str]` 이벤트 `"speech_start"`/`"speech_end"`; `in_speech: bool`.
- `SileroFrameVad()`: CPU 전용(`torch.set_num_threads(1)` 범위 제한), `prob(frame_f32_512: np.ndarray) -> float`, `reset()`. 모델은 프로세스당 1회 로드(싱글톤).

- [ ] **Step 1: failing test**

```python
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from medmap.stt_vad import Endpointer


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


if __name__ == "__main__":
    unittest.main()
```

`SileroFrameVad` 테스트는 `MEDMAP_RUN_SILERO=1`일 때: 무음 512 프레임 prob < 0.2, 기존 TTS WAV의 음성 구간 프레임 평균 prob > 0.5, 스레드가 CPU(`torch.cuda` 미사용: `torch.cuda.memory_allocated()==0` 전후 동일).

- [ ] **Step 2–5:** FAIL → 구현(연속 카운터 2개: 음성 연속 ≥ start_frames면 start, 비음성 연속 ≥ silence_frames면 end) → PASS → 커밋 `stt_vad: Endpointer state machine + CPU Silero wrapper`.

### Task 11: VAD 연결 + 발화 자동 확정

**Files:** Modify `medmap/api_stt_stream.py`(추가), `medmap/stt_stream.py`(pre-roll 링버퍼 추가); Test `tests/test_stt_stream_api.py`(케이스 추가)

- [ ] `_Stream.feed`가 PCM을 512-sample 프레임으로 잘라 `SileroFrameVad.prob`(anyio thread, CPU) → `Endpointer.push` → `speech_end` 시 `finalize("vad")`. `speech_start` 이전 오디오는 pre-roll(300 ms)만 발화에 포함, 나머지는 버림(무음 디코드 방지 = 환각 방지). 수동 `stop`은 그대로(진행 중 발화 즉시 확정). status `vad:"server"`.
- [ ] 테스트(가짜 VAD 주입 `set_vad_for_tests(fn)`): 톤 1 s → 무음 1 s → 톤 1 s → 무음 1 s 스트림에서 FINAL 2개(utt 1, 2), 각 FINAL 텍스트가 해당 구간 오디오만으로 계산됨(가짜 transcriber가 길이를 텍스트로 반환), 수동 stop이 발화 중이면 FINAL 1개 추가·중복 없음, 무음만 스트림 → FINAL 0·디코드 호출 0.
- [ ] 한국어 환각 문구 필터: `HALLUCINATION_PHRASES = ("시청해주셔서 감사합니다", "구독과 좋아요")` — 발화의 VAD 음성 비율 < 0.3일 때만 해당 문구를 제거(테스트: 비율 높으면 유지).
- [ ] 커밋 `stream: server VAD endpointing, auto finalization, preroll, hallucination guard`.

### Task 12: M2 e2e + 조정 + 게이트

- [ ] `realtime-stt.e2e.mjs`에 (D) 두 문장 사이 1 s 무음인 WAV(기존 샘플 + 무음 + 기존 샘플을 **테스트 코드 안에서 메모리로 합성해 scratchpad에 저장**, 저장소 커밋 금지) → 수동 stop 없이 FINAL 2개, textarea = 두 FINAL join, 중복·손실 0.
- [ ] silence 600 ms 조정: 가짜 마이크 + (가능하면) 사용자 실제 발화 1회로 절단 여부 기록, 값 변경 시 근거를 spec §7에 append.
- [ ] 리뷰 → 사용자 M2 보고. 사용자 확인 전 M3 금지.

---

## Milestone 3 — 실기기 모바일 (사용자 동행)

### Task 13: 실기기 체크리스트 실행

- [ ] `scripts/demo_serve.sh`에 `MEDMAP_STT_STREAMING=1` 전달 확인(스크립트 수정이 필요하면 환경변수 전달 1줄 추가만). `--lan`은 **사용자가 직접 실행**.
- [ ] 휴대폰(Android Chrome, 가능하면 iPhone Safari): HTTPS 경고 수락 → 🎙 → 말하는 동안 partial 보임 → 멈추면 FINAL → transport 종류 기록(ws/http/legacy) → 강제 fallback 확인(개발자 없이 가능한 방법: 서버를 `MEDMAP_STT_STREAMING=0`으로 재시작 → legacy 동작).
- [ ] 결과를 기기·OS·브라우저·transport·체감/측정 T_partial/T_final로 `docs/superpowers/plans/2026-09-30-medmap-realtime-streaming-stt.ledger.md`에 기록. 문제(예: iPhone에서 WS 실패 → HTTP 경로 동작 여부) 발견 시 수정 Task 추가 후 재검증.

---

## Milestone 4 — FINAL → 매퍼 후보 자동 준비 ('확인 대기')

### Task 14: `usePreparedCandidates` + 표시 + 재사용

**Files:** Create `medmap-web/src/intake/usePreparedCandidates.js`; Modify `components/FreeTextInput.jsx`(표시 추가), `screens/NaturalIntakeScreen.jsx`(재사용 추가); Test `usePreparedCandidates.test.jsx`, `NaturalIntakeScreen.test.jsx`(케이스 추가)

**Interfaces — Produces:** `usePreparedCandidates({ extract })` → `{ prepared: { text, candidates } | null, pending: boolean, prepare(text), invalidate(), takeIfSame(text) → candidates | null }`. `prepare`는 요청 세대 번호로 최신 응답만 채택(메모리 `stale-async-response-after-reset-needs-request-id`). 저장소 쓰기 없음.

- [ ] 규칙: FINAL이 textarea에 붙은 직후 `prepare(전체 텍스트)`. 사용자가 타이핑으로 텍스트를 바꾸면 `invalidate()`. [확인하기] → `NaturalIntakeScreen.describe`가 `takeIfSame(text)`가 있으면 **extract 요청 없이** 그 후보로 확인 단계 진입, 없으면 기존처럼 `onExtract`.
- [ ] 표시: textarea 아래 "확인 대기 중인 증상 후보"(`data-testid="prepared-candidates"`) — 후보 한국어 라벨만 나열, 버튼·체크 없음, 안내 "아래 [확인하기]를 누르면 하나씩 확인합니다." 원문·matched_text 표시·저장 금지.
- [ ] 테스트: FINAL 2회 연속 → 두 번째 결과만 표시(첫 응답 늦게 도착해도 폐기) · 준비 완료 후 [확인하기] → extract 추가 호출 0, 확인 단계에 준비된 후보 · 타이핑 후 [확인하기] → extract 1회(새 텍스트) · 준비 단계에서 `/v1/session/*` 호출 0 · sessionStorage 쓰기 0.
- [ ] `T_prep` 계측: FINAL 렌더 → 후보 목록 렌더(`perfMark('prep_render')`), 서버 `/v1/intake/extract` ms 로그(기존 로그 재사용).
- [ ] e2e (E): 음성 → FINAL → 수동 조작 없이 `prepared-candidates` 표시 → [확인하기] → extract 요청 1회(준비 때)뿐. 기존 natural-intake/flow/summary e2e 회귀.
- [ ] 리뷰 → 사용자 M4 보고.

---

## Milestone 5 — Doctor real-time loop (`T_next`)

### Task 15: 계측 + 측정

**Files:** Modify `medmap-web/src/doctor/useDoctorSession.js`(**계측 추가만**: answer 클릭 시 `perfMark('doctor_answer_click')`, 응답 수신 `perfMark('doctor_answer_response')`), `NextInformationSection.jsx`(새 질문 렌더 후 `useLayoutEffect`에서 `perfMark('doctor_next_render', {question_id 제외 — 숫자만})`); Create `medmap-web/e2e/doctor-latency.e2e.mjs`; 서버 `/v1/doctor/answer` 처리 시간은 기존 access log(ms) 사용.

- [ ] e2e: handoff → doctor → 건너뛰기 → 질문 3회 답변을 20회 반복(새 컨텍스트) → `T_next = next_render − click` p50/p95, breakdown(click→response, response→render, 서버 ms) → `logs/rt_m5_tnext.json`. warm(두 번째 실행부터)/cold(서버 재시작 직후) 구분.
- [ ] 목표 ≤ 500 ms warm. 미달 시 원인 단계 표시 후 M6에서 처리(목표 하향 금지).
- [ ] Doctor 기존 테스트·e2e(DOCTOR_E2E_OK) 회귀. 리뷰 → 사용자 M5 보고.

---

## Milestone 6 — 성능 최적화 + baseline + regression gate

### Task 16: `scripts/bench_realtime.py` + baseline

- [ ] 서버 단독: 앱 lifespan 기동 후 `_Stream`에 샘플 WAV(1개, 7.7 s; + 무음 결합 2문장 합성)를 실시간 속도로 N=20회 → `T_partial`(서버 부분: audio_end → partial 생성), `T_final`(stop/VAD end → final), decode ms, queue ms, VRAM(`nvidia-smi --query-gpu=memory.used` 전후), CPU% → `exp/perf_baseline/2026-XX-XX_realtime.json`(숫자만 + 조건: GPU 경합 여부·cold/warm·commit SHA). 실행은 nohup + ram_guard, GPU `--check` OK일 때만.
- [ ] 브라우저 포함 수치는 M1/M2/M4/M5 e2e perf JSON을 합쳐 같은 파일에 기록.

### Task 17: 최적화 (측정 기반, 하나씩)

순서(각각 전후 p50/p95 비교, 목표 달성 시 중단): ① partial tick 동적 조정·고정 prefix 이후만 재디코드(rolling window 상한 15 s) ② 앱 진입 prewarm 경로 확인(cold를 진료 경로 밖으로) ③ React partial 렌더 빈도 ④ Doctor 응답 경로(`_project`의 중복 diagnose 1회 제거 가능성 — `/doctor/answer` 동일성 테스트 유지 조건) ⑤ 그래도 `T_partial`/`T_final` 미달이면 **B 평가**: faster-whisper를 **별도 venv·별도 프로세스**로 설치·CT2 turbo 다운로드(이 시점 사용자 승인 필요) → 같은 `bench_realtime` 입력으로 품질(FINAL 일치율·문자 차이)·지연·VRAM 비교 → 교체 여부 사용자 결정.

### Task 18: regression gate

- [ ] `scripts/bench_realtime.py --compare exp/perf_baseline/<baseline>.json`: p95가 baseline 대비 +20% 초과 또는 목표 초과 → exit 2 + `PERF_REGRESSION` 출력(기능 PASS와 별개). GPU 경합 상태로 측정된 결과는 비교 거부(`INVALID_CONTENDED`).
- [ ] README(`medmap-web/README.md`)에 streaming 플래그·e2e·bench 실행법 추가. REALTIME_FIRST 메모리에 baseline 경로 추가.
- [ ] 최종: 전체 backend·vitest·build·e2e(기존 6 + realtime + doctor-latency) · 리뷰 · 사용자 보고(merge-ready, 병합은 명령 시).

---

## Self-review (2026-09-30)

- **Spec coverage:** §2 상태 경계 → Task 3(PARTIAL 서버 전용)·7(textarea FINAL만)·14(CONFIRMED 전 호출 0). §4 엔진 A + B 조건부 → Task 3·17. §5 AudioWorklet + WAV fallback → Task 5·7. §6 WS→HTTP→legacy → Task 3·6·7. §7 Silero CPU·600 ms 조정·수동 stop·환각 → Task 9–12. §8 partial 줄·rAF·준비 상태 → Task 7. §9 단일 큐·최신 partial·과부하·prewarm → Task 2·3·17. §10 Phase 3 자동 후보 → Task 14, Phase 5 → Task 15. §11 계측·baseline·gate → Task 7·15·16·18. §12 privacy → Global Constraints + Task 3 로그 테스트 + Task 14 저장소 테스트. §13 기존 경로 보존·플래그 → Task 3·7 회귀. §14 failure modes → Task 3·6·7·11 테스트. §15 test strategy → 각 Task. §16 milestone gate → 각 M 끝 게이트.
- **간극 처리(반영 완료):** 동시 스트림 초과(`STREAM_BUSY` 429)·HTTP idle 만료(`expire_idle()`)·prewarm 멱등 테스트를 Task 3 Step 1 `LimitsTest`에 추가. Task 1 한도 검사 순서(스트림 상한 우선)를 테스트 기대값에 맞춰 수정.
- **Placeholder:** Task 7 테스트 본문은 케이스·검증값을 명시하고 기존 주입 패턴을 지정했다(가짜 객체 모양이 구현 인터페이스에 종속되므로 구현과 같은 커밋에서 확정). Task 3의 WS/HTTP 핸들러 본문은 인터페이스 계약으로 고정하고 `_Stream` 핵심 로직은 코드로 제시.
- **타입 일치:** `partial_msg/final_msg/end_msg/error_msg`(Task 1) = Task 3 사용 · `submit_partial/submit_final → (text, {"queue","decode"})`(Task 2) = Task 3 `_partial/finalize` · `onPacket({pcm, audioEndMs, capturedAt})`(Task 5) = Task 6 `send(pcm, audioEndMs)` · `perfMark`(Task 7) = Task 14·15.
