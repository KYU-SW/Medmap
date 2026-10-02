#!/usr/bin/env bash
# OFFLINE_ON_PREM_FIRST release gate: 네트워크가 실제로 차단된 상태에서 STT worker·API 서버·브라우저 e2e 를 돌리고,
# 그동안(및 종료 후 몇 초) 루프백·Unix socket 이 아닌 **모든 연결 시도**를 기록한다. 하나라도 있으면 FAIL.
#
# 방식: `unshare -rn`(루트 불필요) 로 새 네트워크 공간을 만들고 lo 만 올린 뒤, 기본 경로를 dummy 인터페이스로 보낸다.
#   → 외부로 가는 패킷은 이 PC 밖으로 나가지 않는다(블랙홀). 그러면서도 연결 시도는 ss 에 SYN-SENT(TCP)·UDP 소켓으로 남아
#     네이티브 코드(예: onnxruntime 1DS telemetry — 2026-09-30 실제 발견)까지 잡힌다. DNS 도 실패한다.
#   자기 검증: 시작 시 의도적인 외부 연결 1건(양성 대조군)을 만들어 탐지기가 잡는지 먼저 확인한다(못 잡으면 FAIL).
#
# 새 dependency·새 worker·새 프로세스를 추가할 때마다 이 스크립트를 돌리고, 새 프로세스는 아래 "프로세스" 절에 추가한다.
# GPU 사용(실제 Whisper) → 실행 전 ~/scripts/wait_for_resources.sh --check 단독 실행. 긴 실행: nohup + ram_guard.
#
# 사용: scripts/release_offline_check.sh            (결과: logs/release_offline_<ts>/summary.txt, 종료 코드 0 = PASS)
#   RUNS=3 HTTP_RUNS=1 LEGACY_RUNS=1 (e2e 횟수) · CHROMIUM_PATH · PLAYWRIGHT_PATH(설치 브라우저 1246 shim) 는 환경변수로.
#   WORKER_SCRIPT=<path> : 음성 대조군용(예: telemetry 수정 전 worker 로 돌려 FAIL 이 나는지 — gate 자체 검증).
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [ "${_MEDMAP_IN_NETNS:-}" != "1" ]; then
  TS=$(date +%Y%m%d_%H%M%S)
  OUT="$ROOT/logs/release_offline_$TS"
  mkdir -p "$OUT"
  _MEDMAP_IN_NETNS=1 OUT="$OUT" unshare -rn bash "$0" "$@"
  rc=$?
  echo "release_offline_check rc=$rc out=$OUT"
  exit $rc
fi

# ---------------- 이 아래는 격리된 네트워크 공간 안 ----------------
cd "$ROOT"
# shellcheck source=offline_env.sh
source "$ROOT/scripts/offline_env.sh"                     # 배포와 같은 오프라인 환경(demo_serve.sh 와 동일)
ip link set lo up
ip link add d0 type dummy && ip addr add 10.255.0.1/24 dev d0 && ip link set d0 up && ip route add default dev d0 \
  || { echo "FAIL: blackhole route setup" | tee "$OUT/summary.txt"; exit 2; }

PY_SERVER="${PY_SERVER:-$MEDMAP_SERVER_PYTHON}"
PY_WORKER="${PY_WORKER:-$MEDMAP_WORKER_PYTHON}"
SOCK="$OUT/worker.sock"
SP=$("$PY_WORKER" -c "import site;print(site.getsitepackages()[0])")

# 탐지기: 루프백(127.0.0.1/::1)이 아닌 TCP·UDP 소켓을 0.2 s 마다 기록(프로세스 이름 포함)
( while [ ! -f "$OUT/.stop_sampler" ]; do
    ss -tunap 2>/dev/null | awk 'NR>1' | grep -vE '(127\.0\.0\.1|\[::1\]|::1):[0-9*]+ +(127\.0\.0\.1|\[::1\]|::1|0\.0\.0\.0|\*|\[::\]):[0-9*]+' \
      | grep -vE ' (0\.0\.0\.0|\*|\[::\]):\*' | sed "s/^/$(date +%s.%N) /"
    sleep 0.2
  done ) > "$OUT/non_loopback.txt" &
SAMPLER=$!

# 0) 양성 대조군: 의도적 외부 연결 시도가 탐지되는지(탐지기 자체 검증)
python3 -c "
import socket,time
s=socket.socket(); s.setblocking(False)
try: s.connect(('203.0.113.7', 443))
except BlockingIOError: pass
time.sleep(1.0)
"
if ! grep -q '203.0.113.7:443' "$OUT/non_loopback.txt"; then
  echo "FAIL: detector did not see the positive control" | tee "$OUT/summary.txt"; touch "$OUT/.stop_sampler"; exit 3
fi
CONTROL_LINES=$(grep -c '203.0.113.7' "$OUT/non_loopback.txt")

# ---------------- 프로세스(새 worker·dependency 는 여기에 추가) ----------------
# 1) STT worker (~/stt_ct2_env: faster-whisper/CT2 + Silero VAD ONNX)
HF_HUB_OFFLINE=1 LD_LIBRARY_PATH="$SP/nvidia/cublas/lib:$SP/nvidia/cudnn/lib" \
  "$PY_WORKER" "${WORKER_SCRIPT:-medmap/stt_worker.py}" --socket "$SOCK" > "$OUT/worker.log" 2>&1 &
WORKER=$!
for i in $(seq 1 180); do grep -q "worker ready" "$OUT/worker.log" && break; sleep 0.5; done
# 2) API 서버(~/ai_env) — 이 네트워크 공간 안의 127.0.0.1:8010(호스트 포트와 무관)
#    선택 모듈도 전부 켠다: MEDMAP_STT_PAUSE_CENSUS=1 → Kiwi(kiwipiepy, 발화 완결 등급) 로드까지 검사 · MEDMAP_HANDOFF_CODES=1 → 기기 간 인계
#    uvicorn 인자는 demo_serve.sh 와 같게(--no-proxy-headers)
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 MEDMAP_STT_WORKER_SOCKET="$SOCK" MEDMAP_STT_ENGINE=ct2 MEDMAP_STT_STREAMING=1 \
  MEDMAP_STT_PAUSE_CENSUS=1 MEDMAP_HANDOFF_CODES=1 \
  MEDMAP_SERVE_WEB_DIST=medmap-web/dist "$PY_SERVER" -m uvicorn medmap.api:app --host 127.0.0.1 --port 8010 --no-proxy-headers \
  > "$OUT/server.log" 2>&1 &
SERVER=$!
for i in $(seq 1 120); do curl -s http://127.0.0.1:8010/v1/stt/status | grep -q WARM && break; sleep 1; done
curl -s http://127.0.0.1:8010/v1/stt/status > "$OUT/status.json"
# 3) 브라우저 e2e(WS·HTTP·legacy=HF 로컬 로드) → worker 강제 종료 → fallback
cd medmap-web
MEDMAP_WEB=http://127.0.0.1:8010 OUT_DIR="$OUT" PERF_NAME=e2e_main RUNS="${RUNS:-3}" HTTP_RUNS="${HTTP_RUNS:-1}" \
  LEGACY_RUNS="${LEGACY_RUNS:-1}" timeout 900 node e2e/realtime-stt.e2e.mjs > "$OUT/e2e_main.txt" 2>&1
E2E_MAIN=$?
# 3b) 텍스트 경로(GPU 불필요 화면): 기기 간 인계 → Doctor
MEDMAP_WEB=http://127.0.0.1:8010 OUT_DIR="$OUT" timeout 300 node e2e/handoff-code.e2e.mjs > "$OUT/e2e_handoff.txt" 2>&1
E2E_HANDOFF=$?
MEDMAP_WEB=http://127.0.0.1:8010 OUT_DIR="$OUT" timeout 300 node e2e/doctor-mode.e2e.mjs > "$OUT/e2e_doctor.txt" 2>&1
E2E_DOCTOR=$?
cd ..
kill "$WORKER"; wait "$WORKER" 2>/dev/null
cd medmap-web
MEDMAP_WEB=http://127.0.0.1:8010 OUT_DIR="$OUT" PERF_NAME=e2e_workerdown ONLY=workerdown timeout 300 \
  node e2e/realtime-stt.e2e.mjs > "$OUT/e2e_workerdown.txt" 2>&1
E2E_DOWN=$?
cd ..
kill "$SERVER"; wait "$SERVER" 2>/dev/null
sleep 5                                                   # 종료 시점 전송 시도까지 본다
touch "$OUT/.stop_sampler"; wait "$SAMPLER" 2>/dev/null

# 제품 프로세스(python: worker·API 서버)의 시도 = FAIL 사유. 테스트 도구(브라우저 등)의 시도는 따로 보고한다.
ATTEMPTS=$(grep -v '203.0.113.7' "$OUT/non_loopback.txt" | grep -c 'users:(("python' || true)
OTHER=$(grep -v '203.0.113.7' "$OUT/non_loopback.txt" | grep -vc 'users:(("python' || true)
{
  echo "positive_control_detected=$CONTROL_LINES"
  echo "worker_ready=$(grep -c 'worker ready' "$OUT/worker.log") $(grep -o 'vad=[01]' "$OUT/worker.log" | head -1)"
  echo "kiwi_pause_lines=$(grep -c 'event=pause ' "$OUT/server.log") kiwi_unavailable=$(grep -c 'kiwi_unavailable' "$OUT/server.log")"
  echo "status=$(cat "$OUT/status.json")"
  echo "e2e_main_rc=$E2E_MAIN e2e_workerdown_rc=$E2E_DOWN e2e_handoff_rc=$E2E_HANDOFF e2e_doctor_rc=$E2E_DOCTOR"
  echo "non_loopback_attempts_product=$ATTEMPTS"
  echo "non_loopback_attempts_harness_or_unknown=$OTHER"
  if [ "$ATTEMPTS" = "0" ] && [ "$E2E_MAIN" = "0" ] && [ "$E2E_DOWN" = "0" ] \
     && [ "$E2E_HANDOFF" = "0" ] && [ "$E2E_DOCTOR" = "0" ]; then echo "RELEASE_OFFLINE_OK"; else echo "RELEASE_OFFLINE_FAIL"; fi
} | tee "$OUT/summary.txt"
grep -q RELEASE_OFFLINE_OK "$OUT/summary.txt"
