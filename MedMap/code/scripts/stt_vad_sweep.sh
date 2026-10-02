#!/usr/bin/env bash
# VAD endpoint threshold 비교(M2 Task 12): 같은 녹음 세트를 threshold 마다 브라우저 가짜 마이크로 replay 한다.
# worker(VAD) 는 한 번 띄우고, API 서버만 threshold 마다 MEDMAP_STT_VAD_SILENCE_MS 를 바꿔 다시 띄운다.
# 결과(숫자만): <OUT>/replay_thr_<ms>.json + summary.tsv. 전사문·오디오는 저장하지 않는다.
#
# 사용(긴 GPU 실행 — ~/scripts/wait_for_resources.sh --check 단독 실행 후, wait wrapper + nohup):
#   REPLAY_MANIFEST=<prepared/manifest.json> THRESHOLDS="census 300 350 400 450 600" REPEATS=2 scripts/stt_vad_sweep.sh
#   ("census" = 쉼 전수 기록: endpoint 1500 ms + MEDMAP_STT_PAUSE_CENSUS=1 → pause_census.txt. Adaptive 값 결정용 데이터)
#   CHROMIUM_PATH · PLAYWRIGHT_PATH(설치 브라우저 1246 shim) 는 환경변수로. medmap-web/dist 는 미리 빌드.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
: "${REPLAY_MANIFEST:?REPLAY_MANIFEST 필요}"
THRESHOLDS="${THRESHOLDS:-300 350 400 450 600}"
TS=$(date +%Y%m%d_%H%M)
OUT="${OUT:-$ROOT/logs/rt_vadsweep_$TS}"
mkdir -p "$OUT"
SOCK="$OUT/worker.sock"
SP=$("$HOME/stt_ct2_env/bin/python" -c "import site;print(site.getsitepackages()[0])")

HF_HUB_OFFLINE=1 LD_LIBRARY_PATH="$SP/nvidia/cublas/lib:$SP/nvidia/cudnn/lib" \
  "$HOME/stt_ct2_env/bin/python" medmap/stt_worker.py --socket "$SOCK" > "$OUT/worker.log" 2>&1 &
WORKER=$!
for i in $(seq 1 180); do grep -q "worker ready" "$OUT/worker.log" && break; sleep 0.5; done
# 외부 연결 감시(OFFLINE gate: worker·서버의 비-루프백 TCP)
( while kill -0 $WORKER 2>/dev/null; do ss -tnp 2>/dev/null | grep -E "users:.*pid=($WORKER|$(cat "$OUT/.server_pid" 2>/dev/null || echo 0))," \
    | grep -vE "127\.0\.0\.1:[0-9]+ +127\.0\.0\.1"; sleep 2; done ) > "$OUT/external_tcp.txt" &
NET=$!

printf "threshold\tok_runs/runs\tfalse_endpoints/boundaries\tmissed_endpoints/sentence_ends\tdelayed_end_runs\tT_final_vad_p50\tT_final_vad_p95\tover_500/n\tT_partial_p50\tT_partial_p95\tpredecode_reuse\tpredecode_discard\tcer_mean\tdel\tins\tdup_runs\tnumeric_pass/total\tnumeric_split\tmanual_correction_proxy\n" > "$OUT/summary.tsv"
for ITEM in $THRESHOLDS; do
  # "census" = 쉼 전수 기록 실행: 긴 endpoint(CENSUS_MS, 기본 1500)로 거의 모든 발화 안 쉼이 끝까지 관찰되게 한다
  CENSUS=0; THR=$ITEM
  if [ "$ITEM" = "census" ]; then CENSUS=1; THR="${CENSUS_MS:-1500}"; fi
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 MEDMAP_STT_WORKER_SOCKET="$SOCK" MEDMAP_STT_ENGINE=ct2 MEDMAP_STT_STREAMING=1 \
    MEDMAP_STT_VAD_SILENCE_MS="$THR" MEDMAP_STT_PAUSE_CENSUS="$CENSUS" MEDMAP_SERVE_WEB_DIST=medmap-web/dist \
    "$HOME/ai_env/bin/python" -m uvicorn medmap.api:app --host 127.0.0.1 --port 8010 > "$OUT/server_$THR.log" 2>&1 &
  SERVER=$!
  echo $SERVER > "$OUT/.server_pid"
  for i in $(seq 1 60); do curl -s http://127.0.0.1:8010/v1/stt/status | grep -q "\"vad_silence_ms\":$THR" && break; sleep 1; done
  curl -s http://127.0.0.1:8010/v1/stt/status > "$OUT/status_$THR.json"
  (cd medmap-web && MEDMAP_WEB=http://127.0.0.1:8010 OUT_DIR="$OUT" LABEL="thr_$THR" REPLAY_MANIFEST="$REPLAY_MANIFEST" \
    REPEATS="${REPEATS:-2}" TAIL_MS=$(( THR + 1500 )) timeout 5400 node e2e/stt-vad-replay.e2e.mjs > "$OUT/replay_thr_$THR.txt" 2>&1)
  echo "thr=$THR rc=$?" >> "$OUT/rc.txt"
  kill $SERVER; wait $SERVER 2>/dev/null
  [ "$CENSUS" = "1" ] && "$HOME/ai_env/bin/python" scripts/stt_pause_census.py "$OUT/server_$THR.log" > "$OUT/pause_census.txt"
  python3 - "$OUT/replay_thr_$THR.json" "$THR" >> "$OUT/summary.tsv" <<'EOF'
import json, sys
s = json.load(open(sys.argv[1]))["summary"]
t = s["T_final_vad_ms"]
print("\t".join(map(str, [sys.argv[2], f"{s['ok_runs']}/{s['runs']}", f"{s['false_endpoints']}/{s['boundaries']}",
      f"{s['missed_endpoints']}/{s['internal_sentence_ends']}", s["delayed_end_runs"], t["p50"], t["p95"], f"{t['over_500']}/{t['n']}",
      s["T_partial_ms"]["p50"], s["T_partial_ms"]["p95"], s["predecode_reuse_rate"], s["predecode_discard_rate"],
      s["cer_mean"], s["deletions"], s["insertions"], s["dup_runs"],
      f"{s['numeric']['pass']}/{s['numeric']['total']}", s["numeric_split"], s["manual_correction_proxy"]])))
EOF
done
kill $WORKER; wait $WORKER 2>/dev/null
kill $NET 2>/dev/null
echo "external_tcp_lines=$(grep -c . "$OUT/external_tcp.txt")" >> "$OUT/rc.txt"
cat "$OUT/summary.tsv"
echo "out $OUT"
