# MedMap STT (speech → text) — bounded 구현 계약 (2026-09-26 승인)

branch `feat/stt` (master `336463f`에서 분기) · worktree `~/medmap-worktrees/stt`
read-only symlink: `data`, `exp/step16b_next_information_validation/model_k{3,5,10}.pkl`, `stt/samples` → `~/medmap/...`

## 책임 분리 (절대)
- STT = audio → transcript 뿐. evidence 추출·진단·PatientState 변경·증상 해석 금지.
- `/v1/stt/transcribe`는 매퍼(`medmap.intake`)·엔진·세션을 import/호출하지 않는다.
- transcript는 자유입력 textbox에만 들어간다 → 사용자 수정 → 사용자가 [확인하기] → 기존 `/v1/intake/extract`. 자동 submit 금지.
- frozen 매퍼(`medmap/intake/`)·기존 session/diagnosis 의미·기존 endpoint 계약 수정 금지. `stt/stt_whisper.py`(기존 스크립트) 보존.
- 디자인 PAUSED: 기존 plain.css class만 사용.

## Backend 계약
- 모듈 `medmap/speech.py`
  - `ALLOWED_MIME`: base MIME allowlist. 후보 `audio/webm, audio/ogg, audio/wav, audio/x-wav, audio/mp4, audio/mpeg` 중 **테스트에서 PyAV로 실제 encode→decode가 확인된 형식만** 남긴다.
  - `normalize_mime(content_type: str|None) -> str`: `;` 앞 base, 소문자, 공백 제거. exact match 금지(`audio/webm;codecs=opus` → `audio/webm`).
  - `MAX_BYTES = 2 * 1024 * 1024`, `MAX_SECONDS = 60.0`(디코드 허용 60.5s), `MIN_SECONDS = 0.3`, `SILENCE_RMS = 1e-3`, `SR = 16000`.
  - `decode_audio(data: bytes) -> tuple[np.ndarray, float]`: `av.open(io.BytesIO(data))`, 첫 audio stream, `av.AudioResampler(format="fltp", layout="mono", rate=16000)`, **flush(`resample(None)`) 포함**, float32 1-D. 누적 샘플이 60.5s를 넘는 즉시 중단 → `AudioTooLong`. 디코드 실패 → `AudioDecodeError`. `|x|.max() > 1.5` → `AudioDecodeError`(PyAV 정수 스케일 가드). 디스크·임시파일 금지.
  - `check_speech(x, duration)`: `duration < MIN_SECONDS` 또는 RMS < `SILENCE_RMS` → `AudioEmpty`.
  - `WhisperTranscriber(loader=None, device=None)`: `transcribe(x: np.ndarray) -> str`. 첫 호출 때 `loader()`로 pipeline 1회 로드(`threading.Lock` double-checked), 추론은 별도 `threading.Lock`으로 직렬화. 기본 loader = transformers `pipeline("automatic-speech-recognition", model="openai/whisper-large-v3-turbo")`, CUDA면 fp16 GPU 아니면 CPU fp32, `MEDMAP_STT_DEVICE`(cuda|cpu) 강제 가능. 호출: `generate_kwargs={"language": "ko", "task": "transcribe"}`, `chunk_length_s=30`. 결과 `text.strip()`.
  - `get_transcriber()`: 모듈 싱글톤(최초 호출 시 생성, 모델은 아직 미로드). 테스트는 이 함수를 monkeypatch.
  - 예외 클래스: `AudioTooLarge, AudioTooLong, AudioDecodeError, AudioEmpty, UnsupportedAudioType, TranscriberUnavailable`.
- endpoint (`medmap/api.py`, **추가만**) `POST /v1/stt/transcribe`
  - `async def`, `request: Request`. **raw binary body**(multipart 아님, `python-multipart` 설치 금지).
  - Content-Type → `normalize_mime` → allowlist 아니면 415 `UNSUPPORTED_AUDIO_TYPE`.
  - `Content-Length` 헤더가 있고 > MAX_BYTES면 즉시 413(사전 검사). 그 값만 믿지 않고 `async for chunk in request.stream()`으로 누적, **> MAX_BYTES가 되는 즉시 중단** → 413 `AUDIO_TOO_LARGE`. bytes는 메모리(bytearray)에만.
  - 빈 body → 422 `AUDIO_EMPTY`.
  - decode·check·transcribe는 `anyio.to_thread.run_sync`로 worker thread에서. event loop에서 직접 실행 금지.
  - 오류: 413 `AUDIO_TOO_LARGE`/`AUDIO_TOO_LONG`, 415 `UNSUPPORTED_AUDIO_TYPE`, 422 `AUDIO_DECODE_ERROR`/`AUDIO_EMPTY`, 503 `STT_UNAVAILABLE`(모델 로드 실패·CUDA OOM), 500 `STT_FAILED`. 형식 `{"error":{"code","message","field":null}}`(기존 `_error_response`), message에 오디오·transcript 내용 금지.
  - 응답 200: 정확히 `{"transcript": str, "duration_s": float(소수 2자리), "language": "ko"}`.
  - 로그: 크기(bytes)·duration·ms·결과 코드만. transcript·오디오 금지. `LOG_PAYLOAD`와 무관.
  - API startup(lifespan)에서 Whisper 로드 금지. `/health`·기존 4 endpoint 무변경.

## Frontend 계약 (medmap-web)
- `src/api/client.js`: `transcribeAudio(blob)` → `fetch('/v1/stt/transcribe', {method:'POST', headers:{'content-type': blob.type || 'audio/webm'}, body: blob})`, 기존 `request()`/`ApiError` 재사용. vite proxy `/v1`은 이미 있음.
- `src/voice/joinTranscript.js`: `joinTranscript(existing, transcript)`
  - transcript가 비면 existing 그대로. existing이 공백뿐이면 `transcript.trim()`.
  - 아니면 `existing.trimEnd()` + (끝이 `[.!?。]` 또는 한글 종결 `[요다죠]`로 끝나지 않으면 `.`) + `\n` + `transcript.trim()`.
  - 이유(Ruling): 매퍼는 공백/줄바꿈을 정규화하고 `[.!?\n]` 또는 `[요다죠] ` 뒤에서 문장을 나눈다. 줄바꿈만으로는 "…기침" + "열은 없어요"가 한 문장이 되어 부정 scope가 섞일 수 있다 → 필요할 때만 마침표 보충. 기존 입력을 덮어쓰지 않는다.
- `src/voice/useRecorder.js`: `useRecorder({maxSeconds=60, getUserMedia, MediaRecorderImpl, now})` → `{state: 'idle'|'recording'|'transcribing', elapsed, error, start(), stop()}`; 녹음 결과 Blob을 `onRecorded(blob)`로 넘김. `audioBitsPerSecond: 32000`, mimeType은 `MediaRecorder.isTypeSupported`로 `audio/webm;codecs=opus` → `audio/webm` → `audio/ogg;codecs=opus` → `audio/mp4` 순. 60초 도달 시 자동 stop. stop 후 트랙 정지(`track.stop()`). 저장소 쓰기 없음.
  - 오류 분류: `NotAllowedError`/`SecurityError`→`permission`, `NotFoundError`/`OverconstrainedError`→`no_mic`, MediaRecorder·getUserMedia 없음→`unsupported`, 그 외 시작 실패→`start_failed`, blob size 0→`empty`.
- `src/components/VoiceInput.jsx`: props `{onTranscript(text), transcribe(blob) (기본 client.transcribeAudio), disabled}`.
  - idle: `[🎙 말하기]` 버튼. recording: `● 듣고 있어요 MM:SS` + `[그만 말하기]`. transcribing: `음성을 글로 바꾸는 중...`(role=status).
  - 성공: `onTranscript(transcript)`만 호출. 자동 submit·extract 호출 없음.
  - 실패: role=alert 안내 문구, 내부 코드 비노출. 기본 문구 `마이크를 사용할 수 없습니다. 직접 입력해서 계속할 수 있어요.` 권한 거부·마이크 없음·미지원·시작 실패는 이 문구 계열, 빈 녹음/`AUDIO_EMPTY`는 `음성이 감지되지 않았어요. 다시 말하거나 직접 입력해 주세요.`, 서버·네트워크·디코드·추론 실패는 `음성을 글로 바꾸지 못했어요. 직접 입력해서 계속할 수 있어요.`
- `src/components/FreeTextInput.jsx`: textarea 아래 `<VoiceInput onTranscript={(t) => setText((prev) => joinTranscript(prev, t))} disabled={pending} />`. 제출 흐름·검증은 그대로(사용자가 [확인하기]).

## 테스트 (GPU 없이 먼저 전부 통과)
- Backend `tests/test_stt_api.py`(unittest, 가짜 transcriber, 오디오는 테스트 안에서 PyAV·numpy로 메모리 합성): valid(각 allowlist 형식) · empty body · corrupt bytes · unsupported MIME · MIME parameter normalize(`audio/webm;codecs=opus`) · Content-Length 사전 413 · 스트리밍 >2MB 중단 413(Content-Length 없이 chunked) · duration >60s 413 · silence 422 · lazy load(요청 전 미로드, 반복 요청 1회 로드) · concurrent load once(threads) · mapper 미호출(`medmap.intake.extract` patch 후 호출 0) · session 무관(응답 키 3개, session 없음) · transcript 비로그(assertLogs) · 추론을 worker thread에서 실행(transcribe 호출 스레드 ≠ event loop 스레드).
- Backend `tests/test_stt_whisper_integration.py`: `MEDMAP_STT_REAL=1`이고 `stt/samples/medmap_tts_test.wav` 존재할 때만. **GPU가 비어 있을 때만 실행.**
- Frontend(vitest, getUserMedia·MediaRecorder mock, fake timers): permission allowed · denied · start/stop · timer · auto-stop 60s · loading · empty text 삽입 · 기존 텍스트 안전 append(joinTranscript 단위 테스트 포함) · 삽입 후 편집 가능 · 실패 시 기존 텍스트 보존 · 자동 submit 없음(extract 미호출) · 기존 Natural Intake 회귀.

## GPU 게이트
- 지금(다른 세션 `train.py` GPU 학습 중) 금지: 실제 Whisper 로드·GPU 추론·실음성 Playwright E2E·cold/warm 벤치마크.
- 조건: `nvidia-smi --query-compute-apps=pid --format=csv,noheader`가 비고 `utilization.gpu`가 낮을 때만. 다른 GPU 작업을 종료·방해하지 않는다. RAM 90%·ram_guard 준수.
