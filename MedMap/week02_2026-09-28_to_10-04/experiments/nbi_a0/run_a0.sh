#!/usr/bin/env bash
# EXP-SN-NBI-001 NBI-A0 runner (rev2) — RG RUN(재심사) + 사용자 실행 승인 후 1회만 사용.
# 실패를 숨기지 않음: 각 단계 실제 종료코드 보존, 마지막 줄 A0_FINAL 에 판정·종료코드 출력,
# CONFORMANT ∧ rc 0 ∧ 결정론 SAME 이 아니면 nonzero 종료. 최종 판정 = 승인된 첫 실행의 A0_FINAL.
set -uo pipefail
PINNED_SHA=f3993da8fd0fa34d48928c996853e9d0eadeb0af3665beae5215b2c88638a5e8
EXPECTED_SHA=387364c04db1f41608b23b54d4691193effc402613fb56f44909956a6b9d7d99
CKV0_SHA=56df424ed39fb8e4654ccc59d38f8bf92e4f15d7ad5097be28b6b5133884ff38
COVERAGE_SHA=339684f626047983e09dc5ea248393c468a15dfb73a918bdfe712cdc8b5f75e9
UNITS_SUMS_SHA=04d880550c38808d882955b01878bf78d65321847ae9b958ffb9d82c7e4b0f08
DESIGN_SHA=2fb1c00863c25d4e6a834f52f57a105f93c139621a953f546e3fa1c7b30cb18a
W="$(cd "$(dirname "$0")/../../../.." && pwd)"
A="$W/docs/research/nbi/a0"
cd "$A" || { echo "A0_FINAL verdict=INVALID reason=cd_failed"; exit 6; }
mkdir -p logs
TS=$(date +%Y%m%d_%H%M%S)
PRE="logs/${TS}_precheck.log"
if [ -e out ]; then echo "A0_FINAL verdict=INVALID reason=out_exists" | tee -a "$PRE"; exit 3; fi
echo "${PINNED_SHA}  A0_PINNED_SHA256SUMS" | sha256sum -c - >>"$PRE" 2>&1; r_pin=$?
sha256sum -c A0_PINNED_SHA256SUMS >>"$PRE" 2>&1; r_files=$?
echo "runner_sha256 $(sha256sum run_a0.sh | cut -d' ' -f1)" >>"$PRE"
python3 --version >>"$PRE" 2>&1
cat "$PRE"
if [ $r_pin -ne 0 ] || [ $r_files -ne 0 ]; then
  echo "A0_FINAL verdict=INVALID reason=pinned_sha_mismatch r_pin=$r_pin r_files=$r_files" | tee -a "$PRE"; exit 5
fi
run_one() {  # $1 = run 이름, $2 = PYTHONHASHSEED
  PYTHONHASHSEED=$2 python3 build_nbi_a0.py \
    --ckv0 "$W/docs/research/nbi/inputs/ck-v0" --ckv0-sha "$CKV0_SHA" \
    --units-sums "$HOME/medmap_core_kb_ws/stage1/INPUT_SHA256SUMS" --units-sums-sha "$UNITS_SUMS_SHA" \
    --t0-forbidden-ref "$W/docs/research/nbi/EXP-SN-NBI-001_design_v0.md" --t0-forbidden-ref-sha "$DESIGN_SHA" \
    --coverage "$W/docs/research/nbi/inputs/corpus-meta/rag-chestpain-v0.coverage.csv" --coverage-sha "$COVERAGE_SHA" \
    --expected expected_output.json --expected-sha "$EXPECTED_SHA" \
    --out "out/$1" >"logs/${TS}_$1.log" 2>&1
  local rc=$?
  echo "PYTHONHASHSEED=$2 rc=$rc" >>"logs/${TS}_$1.log"
  cat "logs/${TS}_$1.log"
  return $rc
}
run_one run1 0; rc1=$?
run_one run2 12345; rc2=$?
verdict_of() {
  if [ -f "out/$1/nbi_a0_report.json" ]; then
    python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["verdict"])' "out/$1/nbi_a0_report.json"
  else echo NO_OUTPUT; fi
}
v1=$(verdict_of run1); v2=$(verdict_of run2)
if [ -f out/run1/NBI_A0_SHA256SUMS ] && [ -f out/run2/NBI_A0_SHA256SUMS ]; then
  if cmp -s out/run1/NBI_A0_SHA256SUMS out/run2/NBI_A0_SHA256SUMS; then det=SAME; else det=DIFFERENT; fi
else det=NO_OUTPUT; fi
final=$v1
[ "$det" = DIFFERENT ] && final=INVALID
[ "$det" = NO_OUTPUT ] && final=INVALID_NO_OUTPUT
echo "A0_FINAL verdict=$final verdict_run1=$v1 verdict_run2=$v2 rc1=$rc1 rc2=$rc2 determinism=$det" | tee "logs/${TS}_final.log"
if [ "$v1" = CONFORMANT ] && [ "$v2" = CONFORMANT ] && [ $rc1 -eq 0 ] && [ $rc2 -eq 0 ] && [ "$det" = SAME ]; then exit 0; fi
exit 1
