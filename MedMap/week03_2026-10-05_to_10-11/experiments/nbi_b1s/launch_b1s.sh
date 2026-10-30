#!/usr/bin/env bash
# EXP-SN-NBI-004 NBI-B1S launcher — 사전등록된 유일한 실행 명령: `bash <절대경로>/launch_b1s.sh` (인자 금지).
# RG RUN + 사용자 실행 승인 후 정확히 1회. 순서: (1) 자원 점검 wait_for_resources --check --no-gpu (2) 중복 실행 차단
# (marker 디렉터리 원자적 생성) (3) run_b1s.sh 를 nohup 백그라운드로 시작 (4) 그 PID 에 ram_guard(90 %) 부착.
# 자원 점검 결과·실제 도구 경로·override 여부를 marker/launch 에 기록(B1 실행기와 동일 구조).
# 모든 경로는 이 파일 위치 기준 절대경로. 종료코드: 0 launched / 4 already_launched / 6 cd_failed / 7 args_not_allowed /
# 8 resources_not_ok / 9 launch_failed
set -uo pipefail
if [ $# -ne 0 ]; then echo "B1S_LAUNCH refused reason=args_not_allowed"; exit 7; fi
B="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)" || { echo "B1S_LAUNCH refused reason=cd_failed"; exit 6; }
L="$B/logs"
mkdir -p "$L"
MARK="$L/b1s_launch.marker"
if [ -e "$B/out/b1s" ]; then echo "B1S_LAUNCH refused reason=already_launched"; exit 4; fi
OVR="none"
if [ -n "${B1S_RESOURCE_CHECK:-}" ] || [ -n "${B1S_RAM_GUARD:-}" ]; then OVR="TEST_OVERRIDE_SET"; fi
RES_CMD="${B1S_RESOURCE_CHECK:-$HOME/scripts/wait_for_resources.sh}"
RG_CMD="${B1S_RAM_GUARD:-$HOME/scripts/ram_guard.sh}"
RES=$("$RES_CMD" --check --no-gpu 2>&1); r_res=$?
echo "resource_check rc=$r_res $RES"
if [ $r_res -ne 0 ] || [ "${RES:0:2}" != "OK" ]; then echo "B1S_LAUNCH refused reason=resources_not_ok"; exit 8; fi
mkdir "$MARK" 2>/dev/null || { echo "B1S_LAUNCH refused reason=already_launched"; exit 4; }
TS=$(date +%Y%m%d_%H%M%S)
RG_EXP=EXP-SN-NBI-004 nohup bash "$B/run_b1s.sh" > "$L/nohup_b1s.log" 2>&1 &
JOB=$!
printf 'pid=%s ts=%s\nresource_check rc=%s %s\nresource_cmd=%s\nram_guard_cmd=%s\noverride=%s\n' \
  "$JOB" "$TS" "$r_res" "$RES" "$RES_CMD" "$RG_CMD" "$OVR" > "$MARK/launch"
if ! kill -0 "$JOB" 2>/dev/null && [ ! -s "$L/nohup_b1s.log" ]; then echo "B1S_LAUNCH failed reason=launch_failed"; exit 9; fi
nohup bash "$RG_CMD" "$JOB" 90 60 "$L/ram_guard_b1s.log" > /dev/null 2>&1 &
echo "B1S_LAUNCH ok pid=$JOB marker=$MARK/launch ram_guard_log=$L/ram_guard_b1s.log nohup_log=$L/nohup_b1s.log override=$OVR"
exit 0
