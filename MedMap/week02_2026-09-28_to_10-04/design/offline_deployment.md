# MedMap 오프라인(병원 내부망·단일 장비) 배포

원칙: OFFLINE_ON_PREM_FIRST — 런타임에 외부 인터넷·모델 다운로드·telemetry·CDN 0. 모든 모델·런타임을 미리 로컬에 둔다.
개발 중 다운로드는 별개(이 문서는 런타임만).

## 1. 구성 요소

| 구성 | 위치(기본값, 환경변수로 변경) | 크기 | 비고 |
|---|---|---|---|
| API 서버 venv | `MEDMAP_SERVER_PYTHON` = `~/ai_env/bin/python` | – | fastapi·uvicorn·torch·transformers·av·kiwipiepy |
| STT worker venv | `MEDMAP_WORKER_PYTHON` = `~/stt_ct2_env/bin/python` | – | faster-whisper·ctranslate2·onnxruntime(+ nvidia cublas·cudnn wheel) |
| 실시간 STT 모델(CT2 int8) | `MEDMAP_CT2_MODEL_DIR` = `~/models/faster-whisper-large-v3-turbo` | 1.6 GB | worker 가 `local_files_only` 로 로드 |
| legacy STT 모델(HF Whisper) | `HF_HOME` = `~/.cache/huggingface` 의 `hub/models--openai--whisper-large-v3-turbo` | 1.6 GB | `/v1/stt/transcribe` fallback. 오프라인 설정으로 캐시만 사용 |
| Silero VAD | worker venv 의 `faster_whisper/assets/silero_vad_v6.onnx` | 2 MB | 새 설치 없음 |
| Kiwi(발화 완결 등급) | 서버 venv 의 `kiwipiepy_model` | 105 MB | LGPL v3 — 배포 시 라이선스 고지·교체 가능 형태 유지 **확인 필요** |
| 프론트 | `medmap-web/dist` | < 1 MB | 외부 URL 0(검사 스크립트) |

## 2. 환경

`scripts/offline_env.sh` 하나가 모든 프로세스의 오프라인 환경을 정한다: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`,
`HF_DATASETS_OFFLINE=1`, `HF_HUB_DISABLE_TELEMETRY=1`, `ORT_DISABLE_TELEMETRY=1`(onnxruntime 1DS 는 Linux 에서도 기본 ON — 2026-09-30
실제 외부 연결 발견, worker 코드도 import 전에 강제), `DO_NOT_TRACK=1`, 위 경로 변수. `demo_serve.sh`·`release_offline_check.sh` 가 source 한다.
통신: 브라우저 ↔ 서버(같은 주소, HTTPS 자체 서명), 서버 ↔ worker(Unix socket 0600). 외부 호출 없음.

## 3. 기동

```bash
scripts/demo_serve.sh --dry-run --stt-streaming   # 계획만 확인
scripts/demo_serve.sh --stt-streaming             # worker(ready 대기) → 서버. 종료 시 worker 도 정리
```
- worker 는 GPU 를 쓴다: `wait_for_resources --check` 가 WAIT 이거나 worker 가 90 s 안에 준비되지 않으면 **기존 음성 입력으로 시작**(fail-safe).
- 모델이 로컬에 없으면 다운로드하지 않고 실패한다.
- LAN 공개(`--lan`)는 사용자가 직접 실행.

## 4. 배포 전 검사(순서)

1. `source scripts/offline_env.sh && ~/ai_env/bin/python scripts/offline_assets_check.py` → `OFFLINE_ASSETS_OK`
   (파일·venv import·Silero·CUDA 라이브러리·HF 캐시·프론트 외부 URL. GPU·네트워크 사용 안 함)
2. `scripts/release_offline_check.sh` → `RELEASE_OFFLINE_OK` (네트워크 차단 + 블랙홀 경로 + 양성 대조군, worker·서버·브라우저 e2e,
   종료 후 5 s 까지 연결 시도 감시). GPU 필요 — `wait_for_resources --check` 단독 실행 후.
3. 새 dependency·worker·프로세스를 추가할 때마다 1·2 를 다시 돌린다(2 의 "프로세스" 절에 새 프로세스 추가).

## 5. 남은 일

- 배포 묶음 형태(venv 복제 vs 컨테이너 vs 설치 스크립트)와 대상 장비(GPU 종류·드라이버·CUDA) 확정 — 사용자 결정 필요.
- Kiwi LGPL v3 배포 조건 검토(확인 필요).
- `--stt-streaming` 실제 기동 검증(GPU 필요, 다른 세션 GPU 우선권 기간이면 대기).
