# MedMap OFFLINE_ON_PREM_FIRST 런타임 환경(source 전용). 서버·STT worker·release gate 가 같은 값을 쓴다.
# 원칙: 런타임에 외부 인터넷·모델 다운로드·telemetry 0. 모든 모델·런타임은 미리 로컬에 둔다(개발 중 다운로드는 별개).
# 경로는 환경변수로 덮어쓸 수 있다(병원 배포 시 /opt/medmap/... 등). 문서: docs/offline_deployment.md
#
#   source scripts/offline_env.sh        # 이후 실행하는 모든 프로세스에 적용

# --- 다운로드·원격 조회 금지 ---
export HF_HUB_OFFLINE=1                 # huggingface_hub: 캐시만 사용(원격 조회·다운로드 없음)
export TRANSFORMERS_OFFLINE=1           # transformers: 로컬 파일만
export HF_DATASETS_OFFLINE=1
# --- telemetry 끔 ---
export HF_HUB_DISABLE_TELEMETRY=1
export ORT_DISABLE_TELEMETRY=1          # onnxruntime 1DS(Linux 기본 ON — 2026-09-30 실제 외부 연결 발견). worker 코드도 강제한다
export DO_NOT_TRACK=1
# --- 로컬 자산 경로(기본값 = 이 개발 PC) ---
export MEDMAP_CT2_MODEL_DIR="${MEDMAP_CT2_MODEL_DIR:-$HOME/models/faster-whisper-large-v3-turbo}"   # worker(faster-whisper/CT2)
export MEDMAP_WORKER_PYTHON="${MEDMAP_WORKER_PYTHON:-$HOME/stt_ct2_env/bin/python}"                  # worker 전용 venv
export MEDMAP_SERVER_PYTHON="${MEDMAP_SERVER_PYTHON:-$HOME/ai_env/bin/python}"                       # API 서버 venv
# HF Whisper(legacy fallback /v1/stt/transcribe) 는 모델 id 로 로드되고, 오프라인 설정 때문에 HF 캐시에서만 찾는다.
# 배포 시 캐시 폴더를 함께 복사하고 HF_HOME 을 그곳으로 지정한다(기본: ~/.cache/huggingface).
export HF_HOME="${HF_HOME:-$HOME/.cache/huggingface}"
