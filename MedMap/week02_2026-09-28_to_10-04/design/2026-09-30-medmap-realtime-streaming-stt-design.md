# MedMap Real-time Clinical Loop — Streaming STT design spec

- 상태: **APPROVED rev2 (2026-09-30 사용자 결정 4건 반영, §17)**. implementation plan: `docs/superpowers/plans/2026-09-30-medmap-realtime-streaming-stt.md`(검토 전 구현 금지).
- 작성: 2026-09-30, 브랜치 `feat/realtime-streaming-stt` (worktree `~/medmap-worktrees/realtime-stt`). rev1은 master `d2341b5` 기준, rev2는 Doctor Foundation 병합 후 새 master **`f39a60f`** 기준(fast-forward).
- 영구 원칙: `REALTIME_FIRST` (`~/medmap/.claude/memory/realtime-first-principle.md`) — 이 spec의 모든 결정은 그 원칙을 따른다.
- 근거: 2026-09-30 사용자 "Real-time Clinical Loop" 지시, repo 읽기 감사(§1), 웹 조사(§4 출처, 2026-09-30 확인; 신뢰도 H/M/L 표기)

---

## 0. 목표와 non-goals

**목표**: 환자가 말하는 동안 transcript가 자막처럼 따라오고(PARTIAL), 말이 끝나면 거의 즉시 확정되며(FINAL), 확인된 정보(CONFIRMED)가 들어오면 감별 후보 재계산과 다음 IG 질문까지 진료 대화를 멈추지 않는 속도로 이어지는 **Real-time Clinical Loop**.

**Non-goals**: 자체 ASR 학습·fine-tuning · 진단 엔진/IG/매퍼 교체·수정 · PARTIAL을 진단에 투입 · 서버 저장(음성·transcript) · 외부 API/클라우드 ASR · 기존 `/v1/stt/transcribe` 제거.

## 1. 현재 상태 (2026-09-30 repo 감사)

### 1-1. git
- rev1 작성 시 master `d2341b5`, Doctor Foundation 미병합. **rev2: 사용자 명령으로 Doctor Mode Foundation 병합 완료 — master `f39a60f`**(병합 전 7be9ede 재검증 backend 267/vitest 238/build, 병합 후 master 재검증 동일). 이 작업은 새 master 기준.
- 다른 worktree: `research/intake-positive-error`(D, 다른 세션) · `feat/web-ui`(보류) · `feat/doctor-mode-foundation`. master 미커밋은 `.claude/` 메모리와 `exp/step17a…`뿐(건드리지 않음).

### 1-2. 현재 STT 경로 (전부 master)
```
[browser] useRecorder: getUserMedia → MediaRecorder(webm/opus 우선, 32 kbps, 최대 60 s) → stop 시 Blob 1개
   → VoiceInput.onRecorded → POST /v1/stt/transcribe (raw body, MIME allowlist 6, ≤2 MB)
[server]  anyio worker thread → speech.decode_audio(PyAV, 16 kHz mono, 메모리만) → check_speech(길이·RMS)
   → WhisperTranscriber(HF transformers pipeline, openai/whisper-large-v3-turbo, fp16 CUDA, language=ko, chunk_length_s=30)
      · lazy singleton + load lock + inference lock(직렬화) · opt-in prewarm(MEDMAP_STT_PREWARM=1, demo_serve --prewarm)
   → {"transcript","duration_s","language"}  (로그: bytes·duration·ms·code만)
[browser] joinTranscript → FreeTextInput textarea에 이어 붙임 → 사용자가 [확인하기] → POST /v1/intake/extract(매퍼)
   → 후보 확인 → initial → bootstrap → /v1/session/start (여기서부터 PatientState)
```
- 경계: STT는 매퍼·엔진·세션과 무관(`speech.py`가 `medmap.intake`를 import하지 않음). transcript 자동 제출 없음. 원문 저장·로그 없음.
- 측정(기존 기록, GPU 독점 시, TTS 7.7 s 1개): load 9.2 s · cold 첫 요청 1.24 s(+load 10.4 s) · warm median 0.34 s / p95 0.39 s · VRAM 794 → 2929 MiB(+2135).
- API 계산 경로(기존 기록): warm endpoint p95 < 3 ms, start+answer×3 흐름 median 8.6 ms / p95 9.6 ms. **서버 계산은 병목이 아니다** — Doctor `T_next`는 네트워크·렌더가 지배할 것(Doctor endpoint 자체는 미측정).
- 환경: `~/ai_env`에 torch 2.5.1+cu121 · transformers 5.13 · av 18.1 · websockets 17.1 · uvicorn 0.53 · fastapi 0.141. **없음**: faster-whisper, ctranslate2, silero-vad, onnxruntime, ffmpeg CLI. Whisper turbo 캐시 1.6 GB 있음.
- 실기기: 2026-09-29 사용자 휴대폰(기종·브라우저 미기록)에서 HTTPS(자체 서명) + 기존 STT "너무 잘 된다". iPhone 여부 확인 필요.

### 1-3. 문제
전체 녹음이 끝나야 전송·인식이 시작된다 → 체감 지연 = 발화 길이 무관하게 "말 끝 → 0.3~0.4 s(warm)"이지만 **말하는 동안 아무것도 안 보인다**(T_partial = 발화 전체 길이). cold면 첫 발화 10 s.

## 2. Transcript 상태 기계 (절대 경계)

```
            (audio frames)                  (utterance end: VAD 또는 수동 stop)
PARTIAL ──────────────────────▶ PARTIAL' ─────────────────────────────────▶ FINAL ──(사용자/의사 확인)──▶ CONFIRMED
 UI 표시만                        교체 가능                                 매퍼 후보 준비 가능            기존 PatientState/session
 PatientState·세션·진단 금지                                               PatientState 아님             계약으로만 반영
```
| 상태 | 만드는 곳 | 허용 | 금지 |
|---|---|---|---|
| PARTIAL | streaming worker | 화면 표시(교체 가능) | PatientState·session·answer 기록, 매퍼 확정 입력, 진단 영구 반영, 저장·로그 |
| FINAL | finalizer(Whisper, 발화 전체 오디오) | 텍스트 입력칸 확정 반영, 매퍼 후보 준비(`/v1/intake/extract`) | PatientState 반영(확인 전), 자동 제출, 저장·로그 |
| CONFIRMED | 기존 확인 UI(후보 확인·bootstrap·Doctor 답변 클릭) | 기존 `/v1/session/*`, `/v1/doctor/*` | — |

- PARTIAL/FINAL은 클라이언트 메모리와 서버 스트림 버퍼(메모리, 수명 = 연결)에만 존재한다.
- speculative compute(예: FINAL 직후 매퍼 후보 미리 계산)는 허용, **speculative state mutation 금지**.

## 3. 요구 latency (REALTIME_FIRST 초기 target, engineering target)

| 지표 | 정의 | 목표 |
|---|---|---|
| `T_partial` | 발화 오디오가 마이크에 들어온 시각 → 그 말이 PARTIAL로 화면에 보인 시각 | 300~600 ms |
| `T_final` | 발화 끝(마지막 음성 프레임) → FINAL 표시 | ≤ 500 ms warm |
| `T_prep` | FINAL → 매퍼 후보 표시 | ≤ 300 ms |
| `T_next` | Doctor 답변 클릭 → 다음 IG 질문이 화면에 읽을 수 있게 렌더 | ≤ 500 ms warm |
| cold | 서버 기동/모드 진입 → STT 준비 완료 | 진료 경로 밖에서 끝낼 것(§9) |

## 4. Streaming 접근 비교

| | A. 현 HF Whisper turbo rolling window | B. faster-whisper(CTranslate2) turbo rolling window | C. 저지연 streaming ASR(partial) + Whisper finalizer | D. WhisperLiveKit 통째 도입 | E. sherpa-onnx/Vosk 한국어(CPU) |
|---|---|---|---|---|---|
| 방식 | 발화 시작부터 누적 오디오를 ~400 ms마다 재디코드, LocalAgreement-2로 안정 prefix만 고정 | A와 같은 정책, 엔진만 CT2(int8_float16) | Nemotron 3.5 ASR Streaming 0.6B(cache-aware RNNT, ko-KR) partial, 끝나면 현 Whisper로 FINAL | SimulStreaming/faster-whisper 백엔드 + 자체 웹 클라이언트 | streaming transducer(Korean zipformer) / Vosk small-ko |
| 한국어 품질 | 현 finalizer와 **같은 모델** — partial도 동일 어휘·표기(의료 용어 보존 동일) | 같은 모델 가중치(CT2 변환본) → A와 거의 동일(H: turbo 공식 지원) | FLEURS ko CER 7.1~7.6%(H, 모델 카드). partial과 final 표기가 달라 확정 시 문장이 바뀌어 보일 수 있음 | 백엔드 의존(Whisper면 A/B 수준) | zipformer ko: Android 빈 출력 이슈 미해결(M), CER 미확인 · Vosk small-ko WER 28.1(H) → 부적합 |
| partial 지연(예상) | tick 400 ms + 디코드(발화 5~10 s 누적 시 ~0.2~0.35 s, 7.7 s warm 0.34 s 실측에서 외삽 — **미측정**) ≈ 0.5~0.8 s | CT2 가속으로 디코드 단축(openai-whisper 대비 ~2.3×, H; HF 대비 수치 없음) ≈ 0.4~0.6 s(**미측정**) | 80~320 ms chunk(H) → 가장 낮음 | 미공개(M) | 낮음(CPU) |
| final 지연 | 발화 전체 1회 디코드 ≈ 현 warm 0.3~0.4 s | 더 짧을 것(미측정) | Whisper finalizer = A와 같음 | 백엔드 의존 | — |
| VRAM | 기존 +2.1 GB 그대로(모델 1개 공유) | 더 적을 것(int8; turbo 수치 미확인 L) | Whisper 2.1 GB + NeMo 0.6B(미확인) — **8 GB에서 2모델 + 다른 세션 경합 위험** | 백엔드 의존 | CPU만 |
| GPU 부하 | 말하는 동안 지속 재디코드(발화 길이에 비례해 증가 → window 상한 필요) | A보다 낮음 | streaming 모델 상주 + finalizer | 백엔드 의존 | 없음 |
| 새 의존성/다운로드 | **없음** | ctranslate2 4.8(CUDA 12.4 wheel) ↔ torch cu121 라이브러리 충돌 가능(L) → 별도 venv/프로세스 권장, CT2 turbo 가중치 ~1.6 GB 다운로드 | NeMo 26.06 대형 의존성 + 모델 다운로드, 라이선스 OpenMDW-1.1 검토 | whisperlivekit(Apache-2.0) + 백엔드; 기본 ffmpeg 필요(이 PC 없음, PCM 모드로 우회) | sherpa-onnx/vosk |
| 구현 복잡도 | 중(정책·버퍼·window 관리 직접) | 중+(A + 별도 런타임 운영) | 상(2모델·정렬·교체 UX) | 중(통합) — 단 로깅·개인정보·계약을 외부 코드에 맡김 | 중 |
| local/offline·privacy | O | O | O | O(설정 의존, 감사 필요) | O |
| fallback 호환 | 기존 `/transcribe`와 같은 모델 → 결과 일관 | 모델 동일, 런타임 다름 | 기존 경로 그대로 finalizer | 별도 경로 | — |
| 라이선스 | MIT(Whisper) | MIT(faster-whisper), CT2 MIT | OpenMDW-1.1(검토 필요) | Apache-2.0 | Apache-2.0 등 |

출처(2026-09-30 확인): faster-whisper PyPI 1.2.1·README(H) · CTranslate2 4.8.2 PyPI(H) · ufal/whisper_streaming(LocalAgreement, "SimulStreaming으로 대체 중", H) · ufal/SimulStreaming(M) · WhisperLiveKit 0.2.26(H) · nvidia/nemotron-3.5-asr-streaming-0.6b 모델 카드(H) · sherpa-onnx issue #2886(M) · alphacephei Vosk models(H).

### 결정(사용자 2026-09-30): **A로 시작, 엔진을 교체 가능하게.** 목표 latency를 못 맞추면 B(faster-whisper)를 별도 benchmark해 교체 판단. **목표를 낮추지 않는다** — A가 느리면 B 또는 이후 대안(C 등).
- 이유: ① 새 의존성·다운로드 없이 M1을 바로 실측 가능 ② partial과 final이 **같은 모델**이라 확정 순간 문장이 바뀌는 혼란이 가장 적음(의료 용어 표기 일관) ③ 기존 `/transcribe`와 결과 일관(fallback이 자연스러움) ④ 8 GB VRAM에 모델 1개.
- 위험: 재디코드 비용이 발화 길이에 비례 → **rolling window 상한(예: 최근 15 s)과 LocalAgreement로 고정된 prefix 이후만 재디코드**, tick 간격 동적 조절. 이 위험을 M1 실측으로 판정하고, 목표 미달이면 B(별도 프로세스, 사용자 승인 후 설치·다운로드)로 같은 인터페이스 교체.
- 인터페이스: `StreamingTranscriber.feed(pcm) -> PartialUpdate | None`, `finalize() -> Final`, `reset()`. 구현체 `HfWhisperRolling`(A) → 필요 시 `CT2WhisperRolling`(B).

## 5. Audio capture (브라우저)

| 방식 | 장점 | 문제 | 판정 |
|---|---|---|---|
| MediaRecorder timeslice chunk | 기존 코드 재사용 | 첫 chunk만 컨테이너 헤더 → 조각 단독 디코드 불가, 서버가 스트림 디코더(ffmpeg stdin 등) 필요(이 PC ffmpeg 없음). iOS fMP4 조각 연결 디코드 불안정(M) | 부적합 |
| **AudioWorklet PCM** | 16-bit PCM 프레임을 바로 전송, 서버 디코드 없음, 프레임 단위 VAD 가능. iOS Safari 14.5+/Android Chrome 지원(H) | iOS가 `AudioContext({sampleRate})`를 무시하고 48 kHz일 수 있음(M) → **worklet 안에서 16 kHz로 다운샘플** | **채택** |
| ScriptProcessorNode | 구형 호환 | deprecated, 메인 스레드 | AudioWorklet 미지원 시만 |
| 기존 MediaRecorder 전체 blob | 검증됨 | streaming 아님 | **fallback 유지** |

- 프레임: 16 kHz mono Int16, 20 ms(320 samples) 단위를 묶어 **~100 ms 패킷**으로 전송(전송 오버헤드와 지연 균형). 클라이언트 타임스탬프(오디오 샘플 기준 ms)를 함께 보낸다(`T_partial` 측정용).
- 같은 PCM을 메모리에 계속 모아 두었다가 streaming이 실패하면 **WAV로 감싸 기존 `/v1/stt/transcribe`로 전송**(MIME `audio/wav`는 이미 allowlist, 2 MB = 16 kHz 16-bit mono ≈ 65 s → 60 s 상한과 맞음). MediaRecorder가 없는 브라우저에서도 fallback 가능해진다.

## 6. Transport

- **1순위 WebSocket** `wss /v1/stt/stream` (uvicorn + websockets 17.1 설치됨).
- **2순위 HTTP chunk POST**: 같은 메시지를 `POST /v1/stt/stream/{stream_id}/audio`(PCM ~100~300 ms 묶음)로 보내고 응답으로 최신 PARTIAL/FINAL을 받음. 이유: **iPhone Safari는 자체 서명 인증서에서 HTTPS 경고를 수락해도 wss가 실패한다는 보고(M, 2026-03 gist 등)** — 현 데모는 자체 서명. fetch POST는 이미 휴대폰에서 동작 확인됨.
- **3순위** 기존 `/v1/stt/transcribe`(발화 종료 후 WAV/blob 1회).
- 클라이언트가 자동 강등: WS 연결 실패/첫 메시지 2 s 무응답 → HTTP chunk → 실패 → 기존 경로. 강등 사유는 코드로만(오류 텍스트 없음) 콘솔·성능 로그에.

### 6-1. 메시지(양 transport 공통, JSON 제어 + binary PCM)
```
C→S  {"type":"start","sample_rate":16000,"format":"s16le","client":"web","run_id":"<uuid>"}   # run_id 익명
C→S  <binary PCM packet>  (HTTP 경로는 body + header x-audio-t0-ms)
C→S  {"type":"stop"}                                # 수동 종료(항상 가능)
S→C  {"type":"ready","stt_state":"WARM"|"LOADING","vad":"server"}
S→C  {"type":"partial","utt":3,"stable":"어제부터 배가","unstable":" 아팠는","audio_ms":2140,"srv_ms":{"recv":..,"decode":..}}
S→C  {"type":"final","utt":3,"text":"어제부터 배가 아팠는데","audio_ms":2890,"srv_ms":{...}}
S→C  {"type":"utterance_end","utt":3,"reason":"vad"|"manual"|"max_duration"}
S→C  {"type":"error","code":"STREAM_OVERLOADED"|"STT_UNAVAILABLE"|"AUDIO_INVALID"|...}   # → 클라이언트 fallback
```
- 서버 상한(기존 계약 계승): 스트림당 60 s 누적 오디오, 발화당 최대 30 s(초과 시 강제 utterance_end `max_duration`), 동시 스트림 N(기본 1, 설정), idle 15 s 종료.
- 서버는 PCM을 스트림 수명 동안 **메모리에만** 둔다. 종료 시 즉시 폐기. 디스크·로그 금지.

## 7. VAD / utterance finalization

- **서버 측 VAD**(클라이언트 WASM VAD는 iOS에서 SIMD·메모리 문제 보고(M)).
  - **결정: Silero VAD(설치 승인 2026-09-30), CPU 실행.** v6(MIT, JIT ~2 MB, 512 samples@16 kHz 프레임 <1 ms CPU, H). 설치는 M2 착수 시(`~/ai_env`, 설치 전후 `pip check`·기존 테스트로 회귀 확인, 설치 기록을 문서에 남김). GPU 사용 금지(`device=cpu`, torch thread 1~2).
  - 규칙(**초기값일 뿐 — 설정값으로 두고 실제 음성 테스트로 조정**): speech start = 확률 ≥ 0.5 연속 ≥ 96 ms · end = 비음성 연속 ≥ **600 ms**(`MEDMAP_STT_VAD_SILENCE_MS`) · 발화 최대 30 s · 앞쪽 pre-roll 300 ms 포함. **수동 stop은 항상 fallback으로 유지.**
- 중간 절단 위험: 600 ms 쉼("음…", 생각하며 멈춤)에서 잘릴 수 있음 → (1) 잘려도 FINAL은 **입력칸에 이어 붙기만** 하고 다음 발화가 이어 붙으므로 내용 손실 없음 (2) 사용자가 끄기 전까지 스트림 유지(여러 발화) (3) 수동 stop 항상 가능 (4) 매퍼 준비는 FINAL마다가 아니라 **스트림 종료 또는 사용자가 [확인하기]** 시(§17-3 결정 대상).
- 환각 방지(Whisper, H): VAD로 무음 구간은 디코드하지 않음 · `condition_on_previous_text=False` · no_speech/logprob 임계 · 기존 `check_speech`(RMS·길이) 재사용 · 알려진 한국어 환각 문구("시청해주셔서 감사합니다" 등)는 **VAD 음성 비율이 낮은 발화에서만** 제거(목록은 코드 상수·테스트로 고정).
- FINAL 생성: 발화 전체 PCM(서버 메모리에 이미 있음)을 기존 `WhisperTranscriber.transcribe`로 1회 디코드 = **기존 모델을 finalizer로 재사용**(재업로드 없음).

## 8. Frontend state / render

- 새 hook `useStreamingStt`(기존 `useRecorder`·`VoiceInput` 불변, 새 컴포넌트 `StreamingVoiceInput`이 기능 플래그로 선택). 상태: `idle → connecting → listening(speaking|silent) → finalizing → idle`, `sttState: WARM|LOADING|UNAVAILABLE`, `transport: ws|http|legacy`.
- 표시: textarea는 **FINAL만** 반영(`joinTranscript` 재사용, 커서·선택·모바일 키보드 보존). PARTIAL은 textarea 밖 별도 "받아쓰는 중" 줄(aria-live polite)에 `stable`(진한 글씨) + `unstable`(옅은 글씨)로만 표시 — 매 chunk마다 textarea를 갈아엎지 않는다.
- 렌더 빈도: partial 메시지는 requestAnimationFrame으로 병합(초당 최대 ~10회), render 시간을 `performance.mark`로 측정.
- "음성 엔진 준비 중 / 준비 완료" 상태 표시(`/health` 확장 필드 또는 `ready` 메시지).
- 기존 전사 잠금 규칙 계승: FINAL 대기 중 [확인하기] 비활성.

## 9. Backend worker / concurrency / cold start / GPU

- Streaming 세션 관리자(프로세스 내, asyncio): 연결마다 버퍼·VAD 상태. GPU 추론은 기존 `WhisperTranscriber` 싱글톤 + inference lock을 공유하는 **단일 GPU 워커 큐**(anyio thread)로 직렬화.
- 우선순위: FINAL > PARTIAL. 큐에 같은 스트림의 PARTIAL이 쌓이면 **최신 것만 남기고 버림**(오래된 partial 계산 낭비 금지). 과부하(큐 대기 > 1 s): partial 간격 자동 확대 → 그래도 초과 시 partial 중단·FINAL만 → `STREAM_OVERLOADED`면 클라이언트 fallback. **오디오 수신은 GPU와 분리**(수신 루프는 막히지 않음) → GPU 경합이 있어도 오디오 스트림은 끊기지 않고 최악에는 FINAL만 늦어진다.
- 동시 사용자 가정: 데모 1명(설정 가능). 2명 이상은 범위 밖(측정 후).
- Cold start 제거: Doctor/Handoff/Patient 앱 진입 시 `POST /v1/stt/prewarm`(멱등, 로드만 트리거) 또는 서버 기동 prewarm 기본값 on(데모). UI는 LOADING이면 "음성 엔진 준비 중…"을 보여주고 텍스트 입력은 막지 않는다. 매 요청 cold load 금지(이미 싱글톤).
- GPU 불가/경합: `wait_for_resources` WAIT 상황에서도 동작해야 함 → CPU fallback은 turbo 기준 비현실적일 가능성 높음(미측정) → **GPU 불가 시 streaming 비활성 + 기존 경로 안내**. VRAM 예산: Whisper 상주 ~2.1 GB + 진단 엔진(CPU) — 다른 세션 학습과 동시 실행 시 OOM 위험은 `ram_guard`/`--check`로 관리.
- 디코드 비용 제어: rolling window 상한 15 s, LocalAgreement로 고정된 prefix 이후 오디오만 재디코드, partial tick 기본 400 ms(동적).

## 10. Clinical pipeline 연결 (단계)

| Phase | 내용 | 상태 경계 |
|---|---|---|
| 1 | Streaming transcript만 | PARTIAL 표시만 |
| 2 | 발화 확정(VAD/수동) → FINAL을 입력칸에 | FINAL |
| 3 | **FINAL 즉시 매퍼 후보 자동 준비 + 화면에 '확인 대기'로 표시**(`/v1/intake/extract` 기존 그대로) | 후보는 확인 전까지 PatientState 아님 — 자동 분석 허용, 자동 반영 금지 |
| 4 | 기존 확인 UI → CONFIRMED → 기존 `/session/start` | 기존 계약 |
| 5 | Doctor: 의사 답변 → `/v1/doctor/answer` → 후보 재계산 + 다음 IG (`T_next`) | Doctor Foundation 계약 그대로 |
| 6 | 전체 최적화·baseline | — |

- Doctor Mode 연결(master `f39a60f`에 병합됨): 스트리밍 입력은 공유 컴포넌트(`FreeTextInput`)에 붙으므로 기본 환자 흐름과 `#/handoff` 인계 흐름 **둘 다** 적용된다. M5 범위 = 인계 → Doctor 답변 클릭(CONFIRMED) → `/v1/doctor/answer` → 후보 재계산 + 다음 IG 렌더의 `T_next` 계측·최적화. 의사 화면에 환자 발화를 자막으로 띄우는 기능은 **이번 범위 밖**(추가 시 표시 전용, 답은 의사 클릭만). blind WD·확률 비노출·claim 경계 불변.
- **FINAL → 후보 자동 준비(결정 3)**: FINAL이 입력칸에 붙는 즉시 입력칸 **전체 텍스트**로 `/v1/intake/extract`를 호출(최신 요청만 유효, 이전 응답 폐기)해 입력칸 아래 "확인 대기 중인 증상 후보" 목록으로 보여준다. 사용자가 별도 '분석하기'를 누르지 않아도 후보가 이미 준비돼 있다. [확인하기]를 누르면 텍스트가 같을 때 **준비된 결과를 재사용**(두 번째 요청 없음)해 바로 기존 확인 단계로 간다. 사용자가 직접 타이핑으로 텍스트를 바꾸면 준비 결과는 무효(표시 제거), [확인하기] 시 기존처럼 요청. 확인 대기 목록은 선택·확정 UI가 아니다(기존 확인 단계가 유일한 CONFIRMED 경로). 원문은 요청 본문에만(기존 원칙).
- speculative: 위 후보 준비가 대표 사례. 같은 텍스트면 [확인하기] 시 재사용. Doctor에서는 현재 질문의 가능한 답(예/아니요/모름) 각각의 다음 턴을 미리 계산하는 것도 검토 가능(서버 계산 ~ms라 이득은 네트워크 왕복 절약뿐) — **state mutation 없음**, M6에서 측정 후 결정.

## 11. Performance instrumentation / regression

- 클라이언트: 오디오 샘플 시각(t_audio) · 패킷 송신 · partial 수신 · partial 렌더(`performance.mark`) · final 수신/렌더 · Doctor 클릭→응답→렌더.
- 서버: 수신 · VAD 판정 · 큐 대기 · 디코드 · 송신 (`srv_ms` 필드로 클라이언트에 전달 → 클라이언트가 단계 breakdown 계산).
- 저장: `logs/perf/<date>_<run_id>.jsonl` — **숫자와 코드만**(stage, ms, audio_ms, transport, stt_state, gpu_util 샘플). 텍스트·오디오·evidence id 없음.
- Benchmark: `scripts/bench_realtime.py`(서버 단독: 고정 합성 음성 파일(기존 `stt/samples`) 을 실시간 속도로 스트리밍 재생 → T_partial·T_final p50/p95, cold/warm) + e2e(Playwright 가짜 마이크로 브라우저 경로 T_partial·T_final·T_next). 결과 `exp/perf_baseline/<date>.json`.
- Gate: baseline 대비 p95 **+20% 이상 또는 목표 초과**면 `PERF_REGRESSION` 경고(로컬/릴리스 게이트, CI GPU 강제 아님). 임계는 baseline 측정 후 확정. 조건(GPU 경합·cold/warm·기기)을 결과에 함께 기록, 경합 중 측정은 무효 표시(메모리 `gpu-contended-runtime-benchmark-invalid`).

## 12. Privacy / security

- 음성·partial·final: 서버 메모리(스트림 수명)만, 디스크·로그·perf 로그 금지. 클라이언트도 저장소에 넣지 않음(FINAL은 기존처럼 입력칸 React 상태).
- WebSocket: same-origin만(Origin 검사), 메시지 크기 상한, 스트림 수·시간 상한, 인증 없음 → **로컬/LAN 데모 한정**(기존 원칙).
- 위험: 스트림 중 PHI가 메모리에 오래 남음(최대 60 s) → 종료·오류·연결 끊김 시 즉시 폐기, 예외 로그에 버퍼 내용 금지(예외 종류만).
- iPhone wss 문제로 사용자 기기에 자체 CA를 설치하는 방법은 **권장하지 않음**(기기 신뢰 저장소 변경) → HTTP chunk fallback으로 해결.

## 13. Backward compatibility

- `/v1/stt/transcribe`·`speech.decode_audio/check_speech/WhisperTranscriber`·`useRecorder`·`VoiceInput` 계약 불변(추가만). 기존 음성 e2e `VOICE_E2E_OK` 유지.
- Streaming은 기능 플래그(`MEDMAP_STT_STREAMING=1` 서버, `/health`로 클라이언트에 노출 + 클라이언트 capability 확인)로 켜고, 꺼져 있으면 현재와 같은 화면·동작.
- 수정되는 기존 프론트 파일(플래그 분기 추가만): `FreeTextInput.jsx`(VoiceInput ↔ StreamingVoiceInput 선택, 확인 대기 후보 표시), `NaturalIntakeScreen.jsx`(준비된 후보 재사용). P2-4 계약 유지 — 준비된 후보·transcript는 React 메모리만, 저장소 쓰기 없음. `useMedmapSession.js`·`startPlan.js`·매퍼·엔진·Doctor 코드 무변경.
- 매퍼·엔진·IG·session·Doctor 계약 불변.

## 14. Failure modes → 동작

| 상황 | 동작 |
|---|---|
| AudioWorklet 없음/권한 거부 | 기존 MediaRecorder 경로(현재 UX) |
| wss 실패(iOS 자체 서명 등) | HTTP chunk 경로 |
| HTTP chunk도 실패 | 발화 종료 후 모아둔 PCM을 WAV로 `/transcribe` |
| 모델 LOADING | "음성 엔진 준비 중" + 오디오는 계속 수신·버퍼, 준비되면 FINAL 생성(partial 생략) |
| GPU 경합·큐 지연 | partial 간격 확대 → partial 중단·FINAL만 → 과부하 코드 → fallback |
| VAD 중간 절단 | FINAL 이어 붙기(손실 없음), 다음 발화 계속 |
| VAD 끝 미검출(소음) | 발화 최대 30 s 강제 종료 + 수동 stop |
| 연결 끊김 | 수신한 PCM으로 FINAL 시도(서버) / 클라이언트는 legacy 재전송 |
| 환각(무음) | VAD 무음 미디코드 + 임계 + 문구 필터 |
| 중복/손실 | utt 번호·audio_ms 기준으로 FINAL은 발화당 1회만 반영(멱등), 테스트로 검증 |

## 15. Test strategy

- 단위(backend): 버퍼·VAD 규칙(합성 PCM: 음성/무음 패턴), LocalAgreement(고정 prefix 단조 증가), utt 멱등, 상한(60 s/30 s/idle), 큐 정책(최신 partial만), 로그·perf 로그에 텍스트/오디오 없음(대조군 포함), 기존 `/transcribe` 회귀.
- 단위(frontend): 상태 기계, transport 강등 순서, textarea에는 FINAL만(PARTIAL 입력 시 textarea 값 불변·커서 유지), rAF 병합, PatientState/세션 API 호출 0(PARTIAL/FINAL 단계).
- 통합: 실제 Whisper로 합성 음성 스트리밍 → FINAL이 기존 `/transcribe` 결과와 일치(같은 모델), partial 단조성.
- e2e: Chromium 가짜 마이크(기존 방식)로 partial 표시·FINAL·fallback 강제(WS 차단) · 기존 음성 e2e.
- 실기기: Android Chrome + iPhone Safari(가능하면), HTTPS, partial 보임, FINAL, fallback — 결과를 기기·OS·브라우저·transport·지연과 기록.
- 성능: §11 benchmark, GPU 비경합 조건.

## 16. Rollout (Milestone gate, 사용자 지시 그대로)

| M | 내용 | 성공 조건 |
|---|---|---|
| 1 | Streaming transcript prototype (A, AudioWorklet, WS + HTTP chunk, 수동 stop) | 실제 브라우저 마이크 · 말하는 동안 partial · PatientState 변경 0 · 기존 STT fallback 그대로 |
| 2 | VAD + finalization (Whisper finalizer) | speech stop 검출 · FINAL · 중복/손실 0 |
| 3 | 실기기 모바일 | 휴대폰 HTTPS 마이크 · partial · FINAL · fallback 확인 |
| 4 | 매퍼 준비 통합 | FINAL만 · 후보 추출 · 미확인 PatientState 변경 0 |
| 5 | Doctor real-time loop (Foundation 병합됨 `f39a60f`) | CONFIRMED 답 · 재계산 · 다음 IG · `T_next` 측정 |
| 6 | 성능 최적화 | p50/p95 · T_partial · T_next · cold/warm · CPU/GPU/VRAM · baseline · (필요 시 B 평가) |

각 M은 기능·정확성 검증 → 사용자 보고 → 다음 M.

## 17. 사용자 결정 (2026-09-30)

1. **엔진**: A(현 HF Whisper turbo rolling window + LocalAgreement)로 시작, 실제 `T_partial` 측정. 목표 미달 시에만 B(faster-whisper) 별도 benchmark 후 교체 판단. 목표를 낮추지 않는다.
2. **VAD**: Silero VAD, 설치 승인, CPU 실행. 수동 stop 항상 fallback. 600 ms는 조정 가능한 초기값.
3. **매퍼 후보**: FINAL 즉시 자동 준비, 화면에 '확인 대기' 표시. 자동 PatientState 반영 금지(PARTIAL=UI only · FINAL=후보 준비 · CONFIRMED=PatientState).
4. **기준 브랜치**: Doctor Mode Foundation 먼저 master 병합(완료 `f39a60f`) → 새 master 기준으로 진행. realtime 브랜치는 새 master로 fast-forward(spec 보존).
