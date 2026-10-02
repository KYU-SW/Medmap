#!/usr/bin/env bash
# MedMap demo 서버(P2-7): 빌드된 프론트를 API 와 same-origin 으로, HTTPS(자체 서명)로 띄운다.
# 계약: docs/superpowers/plans/2026-09-27-medmap-demo-deployment.md
#
# 사용:
#   scripts/demo_serve.sh                 # https://127.0.0.1:8443 (이 PC 에서만)
#   scripts/demo_serve.sh --http          # http://127.0.0.1:8000 (인증서 없이, 같은 PC 확인용)
#   scripts/demo_serve.sh --lan           # 0.0.0.0 바인딩 — 같은 네트워크의 휴대폰 마이크 확인용(직접 실행할 때만)
#   scripts/demo_serve.sh --prewarm       # Whisper 를 서버 시작 직후 백그라운드로 로드(GPU 사용)
#   scripts/demo_serve.sh --no-build      # medmap-web/dist 를 다시 빌드하지 않음
#   scripts/demo_serve.sh --stt-streaming # 로컬 STT worker(faster-whisper/CT2 + Silero VAD)까지 띄워 실시간 받아쓰기 사용.
#                                         # GPU 가 바쁘거나 worker 가 준비되지 않으면 기존 음성 입력으로 시작(fail-safe)
#   scripts/demo_serve.sh --dry-run       # 실행 계획만 출력(빌드·인증서·프로세스 없음)
#   PORT=9443 scripts/demo_serve.sh
#
# OFFLINE_ON_PREM_FIRST: 항상 scripts/offline_env.sh 를 적용한다(HF/transformers 오프라인, telemetry 끔, 로컬 모델 경로).
# 모델이 로컬에 없으면 다운로드하지 않고 실패한다 — 배포 전 scripts/offline_assets_check.py 로 확인.
#
# 휴대폰 마이크는 보안 컨텍스트(HTTPS)에서만 열린다. 자체 서명 인증서라 브라우저 경고를 한 번 수락해야 한다.
# 인증서는 저장소 밖(~/.medmap-demo-cert/)에 한 번만 만든다. 외부 공개·배포는 하지 않는다.
# 긴 실행이므로 nohup 백그라운드 + ~/scripts/ram_guard.sh 를 권장한다(README 참고).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=offline_env.sh
source "$ROOT/scripts/offline_env.sh"
PYTHON="${PYTHON:-$MEDMAP_SERVER_PYTHON}"
WAIT_FOR_RESOURCES="${WAIT_FOR_RESOURCES:-$HOME/scripts/wait_for_resources.sh}"
CERT_DIR="${MEDMAP_DEMO_CERT_DIR:-$HOME/.medmap-demo-cert}"
HOST=127.0.0.1
SCHEME=https
BUILD=1
PREWARM=0
STREAMING=0
DRY=0

for arg in "$@"; do
  case "$arg" in
    --lan) HOST=0.0.0.0 ;;
    --http) SCHEME=http ;;
    --prewarm) PREWARM=1 ;;
    --no-build) BUILD=0 ;;
    --stt-streaming) STREAMING=1 ;;
    --dry-run) DRY=1 ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done
if [ "$SCHEME" = https ]; then PORT="${PORT:-8443}"; else PORT="${PORT:-8000}"; fi

if [ "$BUILD" = 1 ] && [ "$DRY" = 0 ]; then
  (cd "$ROOT/medmap-web" && npm run build --silent)
fi
DIST="$ROOT/medmap-web/dist"
[ "$DRY" = 1 ] || [ -f "$DIST/index.html" ] || { echo "no $DIST/index.html — run without --no-build" >&2; exit 1; }

# 실시간 받아쓰기: worker 는 GPU 를 쓴다 → 비어 있을 때만. 바쁘면 기존 음성 입력(/v1/stt/transcribe)으로 시작한다.
STREAMING_NOTE=""
if [ "$STREAMING" = 1 ]; then
  if [ ! -x "$WAIT_FOR_RESOURCES" ]; then
    STREAMING=0; STREAMING_NOTE="wait_for_resources.sh not found: cannot check GPU, starting WITHOUT streaming worker"
  elif ! "$WAIT_FOR_RESOURCES" --check >/dev/null; then
    STREAMING=0; STREAMING_NOTE="GPU busy (wait_for_resources --check = WAIT): starting WITHOUT streaming worker (legacy voice input)"
  fi
fi
[ -n "$STREAMING_NOTE" ] && echo "$STREAMING_NOTE" >&2
SOCK="${MEDMAP_STT_WORKER_SOCKET:-${XDG_RUNTIME_DIR:-/tmp/medmap-stt-$(id -u)}/medmap-stt-worker.sock}"
WSP="$("$MEDMAP_WORKER_PYTHON" -c 'import site;print(site.getsitepackages()[0])' 2>/dev/null || echo /nonexistent)"
WORKER_CMD=("$MEDMAP_WORKER_PYTHON" "$ROOT/medmap/stt_worker.py" --model-dir "$MEDMAP_CT2_MODEL_DIR" --socket "$SOCK")

if [ "$PREWARM" = 1 ] && [ "$DRY" = 0 ]; then
  # GPU 를 확인할 수 없거나 바쁘면 prewarm 없이 시작한다(fail-safe). STT 는 첫 요청 때 로드된다.
  if [ ! -x "$HOME/scripts/wait_for_resources.sh" ]; then
    echo "wait_for_resources.sh not found: cannot check GPU, starting WITHOUT prewarm" >&2
    PREWARM=0
  elif ! "$HOME/scripts/wait_for_resources.sh" --check >/dev/null; then
    echo "GPU busy (wait_for_resources --check = WAIT): starting WITHOUT prewarm; STT loads on first request" >&2
    PREWARM=0
  fi
fi

# 프록시 헤더 무시: 이 서버는 프록시 뒤에 두지 않는다. 켜 두면(uvicorn 기본) 루프백 접속의 X-Forwarded-For 가
# 접속 주소를 바꿔 인계 기기별 잠금을 우회·오작동시킨다(WSL localhost 전달·portproxy 는 루프백으로 들어온다)
UVICORN_ARGS=(--host "$HOST" --port "$PORT" --no-proxy-headers)

if [ "$DRY" = 1 ]; then
  echo "MedMap demo (dry-run): $SCHEME://$HOST:$PORT  prewarm=$PREWARM  stt_streaming=$([ "$STREAMING" = 1 ] && echo on || echo off)"
  echo "offline env: HF_HUB_OFFLINE=$HF_HUB_OFFLINE TRANSFORMERS_OFFLINE=$TRANSFORMERS_OFFLINE ORT_DISABLE_TELEMETRY=$ORT_DISABLE_TELEMETRY HF_HOME=$HF_HOME"
  if [ "$STREAMING" = 1 ]; then
    echo "worker: LD_LIBRARY_PATH=$WSP/nvidia/cublas/lib:$WSP/nvidia/cudnn/lib ${WORKER_CMD[*]}"
    echo "server: MEDMAP_STT_ENGINE=ct2 MEDMAP_STT_STREAMING=1 MEDMAP_STT_WORKER_SOCKET=$SOCK $PYTHON -m uvicorn medmap.api:app ${UVICORN_ARGS[*]}"
  else
    echo "server: $PYTHON -m uvicorn medmap.api:app ${UVICORN_ARGS[*]}"
  fi
  exit 0
fi

SSL_ARGS=()
if [ "$SCHEME" = https ]; then
  if [ ! -f "$CERT_DIR/cert.pem" ] || [ ! -f "$CERT_DIR/key.pem" ]; then
    mkdir -p "$CERT_DIR"
    chmod 700 "$CERT_DIR"
    LAN_IPS="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+(\.[0-9]+){3}$' | sed 's/^/,IP:/' | tr -d '\n' || true)"
    SAN="DNS:localhost,IP:127.0.0.1${LAN_IPS}"
    openssl req -x509 -newkey rsa:2048 -nodes -days 30 -subj "/CN=medmap-demo" \
      -addext "subjectAltName=$SAN" -keyout "$CERT_DIR/key.pem" -out "$CERT_DIR/cert.pem" 2>/dev/null
    chmod 600 "$CERT_DIR/key.pem"
    echo "self-signed cert created: $CERT_DIR (SAN $SAN, 30 days)"
  fi
  SSL_ARGS=(--ssl-keyfile "$CERT_DIR/key.pem" --ssl-certfile "$CERT_DIR/cert.pem")
fi

cd "$ROOT"
export MEDMAP_SERVE_WEB_DIST="$DIST"
if [ "$PREWARM" = 1 ]; then export MEDMAP_STT_PREWARM=1; fi

if [ "$STREAMING" = 1 ]; then
  mkdir -p "$ROOT/logs"
  WORKER_LOG="$ROOT/logs/stt_worker_$(date +%Y%m%d_%H%M%S).log"
  LD_LIBRARY_PATH="$WSP/nvidia/cublas/lib:$WSP/nvidia/cudnn/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
    "${WORKER_CMD[@]}" > "$WORKER_LOG" 2>&1 &
  WORKER_PID=$!
  for _ in $(seq 1 180); do
    grep -q "worker ready" "$WORKER_LOG" 2>/dev/null && break
    kill -0 "$WORKER_PID" 2>/dev/null || break
    sleep 0.5
  done
  stop_worker() { kill "$WORKER_PID" 2>/dev/null || true; wait "$WORKER_PID" 2>/dev/null || true; }
  if grep -q "worker ready" "$WORKER_LOG" 2>/dev/null; then
    trap 'stop_worker; exit 130' INT TERM
    echo "STT worker ready (pid $WORKER_PID, log $WORKER_LOG)"
    export MEDMAP_STT_ENGINE=ct2 MEDMAP_STT_STREAMING=1 MEDMAP_STT_WORKER_SOCKET="$SOCK"
  else
    stop_worker
    echo "STT worker did not become ready (log $WORKER_LOG): starting WITHOUT streaming (legacy voice input)" >&2
    STREAMING=0
  fi
fi

echo "MedMap demo: $SCHEME://$HOST:$PORT  (prewarm=$PREWARM, stt_streaming=$([ "$STREAMING" = 1 ] && echo on || echo off), offline)"
if [ "$STREAMING" = 1 ]; then
  rc=0
  "$PYTHON" -m uvicorn medmap.api:app "${UVICORN_ARGS[@]}" "${SSL_ARGS[@]}" || rc=$?   # worker 를 함께 정리하려고 exec 하지 않음
  stop_worker
  exit "$rc"
else
  exec "$PYTHON" -m uvicorn medmap.api:app "${UVICORN_ARGS[@]}" "${SSL_ARGS[@]}"
fi
