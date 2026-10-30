#!/usr/bin/env bash
# EXP-SN-NBI-002 NBI-B0d launcher — 사전등록된 유일한 실행 명령: `bash <절대경로>/launch_b0d.sh` (인자 금지).
# RG RUN + 사용자 실행 승인 후 정확히 1회. 하는 일: (1) 중복 실행 차단(marker 디렉터리 원자적 생성) (2) 자원 점검
# wait_for_resources --check --no-gpu (3) run_b0d.sh 를 nohup 백그라운드로 시작 (4) 그 PID 에 ram_guard(90 %) 부착.
# 모든 경로는 이 파일 위치 기준 절대경로 — cwd·cd·& 조합과 무관(B0c ram_guard 로그 중첩 사고 재발 방지).
# 종료코드: 0 launched / 4 already_launched / 6 cd_failed / 7 args_not_allowed / 8 resources_not_ok / 9 launch_failed
set -uo pipefail
if [ $# -ne 0 ]; then echo "B0D_LAUNCH refused reason=args_not_allowed"; exit 7; fi
B="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)" || { echo "B0D_LAUNCH refused reason=cd_failed"; exit 6; }
L="$B/logs"
mkdir -p "$L"
MARK="$L/b0d_launch.marker"
if [ -e "$B/out/b0d" ]; then echo "B0D_LAUNCH refused reason=already_launched"; exit 4; fi
RES_CMD="${B0D_RESOURCE_CHECK:-$HOME/scripts/wait_for_resources.sh}"
RES=$("$RES_CMD" --check --no-gpu 2>&1); r_res=$?
echo "resource_check rc=$r_res $RES"
if [ $r_res -ne 0 ] || [ "${RES:0:2}" != "OK" ]; then echo "B0D_LAUNCH refused reason=resources_not_ok"; exit 8; fi
mkdir "$MARK" 2>/dev/null || { echo "B0D_LAUNCH refused reason=already_launched"; exit 4; }
TS=$(date +%Y%m%d_%H%M%S)
RG_EXP=EXP-SN-NBI-002 nohup bash "$B/run_b0d.sh" > "$L/nohup_b0d.log" 2>&1 &
JOB=$!
echo "pid=$JOB ts=$TS" > "$MARK/launch"
if ! kill -0 "$JOB" 2>/dev/null && [ ! -s "$L/nohup_b0d.log" ]; then echo "B0D_LAUNCH failed reason=launch_failed"; exit 9; fi
nohup bash "${B0D_RAM_GUARD:-$HOME/scripts/ram_guard.sh}" "$JOB" 90 60 "$L/ram_guard_b0d.log" > /dev/null 2>&1 &
echo "B0D_LAUNCH ok pid=$JOB marker=$MARK/launch ram_guard_log=$L/ram_guard_b0d.log nohup_log=$L/nohup_b0d.log"
exit 0
