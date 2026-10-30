#!/usr/bin/env bash
# EXP-SN-NBI-002 NBI-B0a runner (v2) — RG RUN(재심사) + 사용자 실행 승인 후에만 사용. LOCAL ONLY. 인자 금지.
# 종료코드: 0 COMPLETE / 2 INVALID(python) / 3 STOP_TITLE / 4 output_exists / 5 pinned_sha_mismatch / 6 cd_failed / 7 args_not_allowed
# 공개 출력(out/b0a/b0a_public.json)이 생성되지 않은 실행은 승인된 실데이터 1회 실행으로 세지 않음(manifest [K]).
set -uo pipefail
if [ $# -ne 0 ]; then echo "B0A_FINAL verdict=INVALID reason=args_not_allowed counted=no"; exit 7; fi
PINNED_SHA=91593a07a5de7a26a7809534d1f19aea9abf713d971b1466b783dc57bbb0cf41
SCHEMA_SHA=ae5c20ee9ae394658983b9a1f39a8173c8a5bff3696ff28435e7f24b407f052c
ED_ZIP=/mnt/c/Users/<user>/Downloads/mimic-iv-ed-2.2.zip
ED_SHA=d17bbf2efe6a4a7e0f29c73b0743e6d2b7fb840e9b1a14f9064f23c70d868fc9
ECG_ZIP=/mnt/c/Users/<user>/Downloads/mimic-iv-ecg-ext-icd-diagnostic-labels-for-mimic-iv-ecg-1.0.1.zip
ECG_SHA=4b99cac62b675fcf35e6822910014431c511aebba903b5ebc3f3739856ff553c
B="$(cd "$(dirname "$0")" && pwd)"
R="$HOME/<restricted>/nbi_b0a"
cd "$B" || { echo "B0A_FINAL verdict=INVALID reason=cd_failed counted=no"; exit 6; }
mkdir -p logs
TS=$(date +%Y%m%d_%H%M%S)
PRE="logs/${TS}_b0a_precheck.log"
FIN="logs/${TS}_b0a_final.log"
if [ -e out/b0a ] || [ -e "$R/sealed" ]; then echo "B0A_FINAL verdict=INVALID reason=output_exists counted=no" | tee -a "$PRE" "$FIN"; exit 4; fi
echo "${PINNED_SHA}  B0A_PINNED_SHA256SUMS" | sha256sum -c - >>"$PRE" 2>&1; r_pin=$?
sha256sum -c B0A_PINNED_SHA256SUMS >>"$PRE" 2>&1; r_files=$?
echo "runner_sha256 $(sha256sum run_b0a.sh | cut -d' ' -f1)" >>"$PRE"
python3 --version >>"$PRE" 2>&1
cat "$PRE"
if [ $r_pin -ne 0 ] || [ $r_files -ne 0 ]; then
  echo "B0A_FINAL verdict=INVALID reason=pinned_sha_mismatch counted=no" | tee -a "$PRE" "$FIN"; exit 5
fi
mkdir -p "$R" && chmod 700 "$R"
python3 b0a_availability.py --ed-zip "$ED_ZIP" --ed-zip-sha "$ED_SHA" --ecg-zip "$ECG_ZIP" --ecg-zip-sha "$ECG_SHA" \
  --schema expected_schema.json --schema-sha "$SCHEMA_SHA" --out out/b0a --sealed "$R/sealed" \
  --private-log "$R/private_${TS}.log" >"logs/${TS}_b0a_run.log" 2>&1
rc=$?
cat "logs/${TS}_b0a_run.log"
V=$(grep -o 'B0A_VERDICT [A-Z_]*' "logs/${TS}_b0a_run.log" | tail -1 | cut -d' ' -f2)
if [ -f out/b0a/b0a_public.json ]; then C=yes; else C=no; fi
echo "B0A_FINAL verdict=${V:-NO_VERDICT} rc=$rc counted=$C" | tee "$FIN"
exit $rc
