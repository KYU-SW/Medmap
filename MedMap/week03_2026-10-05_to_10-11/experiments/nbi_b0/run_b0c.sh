#!/usr/bin/env bash
# EXP-SN-NBI-002 NBI-B0c runner — RG RUN(재심사) + 사용자 실행 승인 후에만 사용. LOCAL ONLY. 인자 금지.
# 종료코드: 0 COMPLETE / 2 INVALID(python) / 3 STOP_TITLE / 4 output_exists / 5 pinned_sha_mismatch / 6 cd_failed / 7 args_not_allowed
# 공개 출력(out/b0c/b0c_public.json)이 생성되지 않은 실행은 승인된 실데이터 1회 실행으로 세지 않음(manifest [K]·[N]).
set -uo pipefail
if [ $# -ne 0 ]; then echo "B0C_FINAL verdict=INVALID reason=args_not_allowed counted=no"; exit 7; fi
PINNED_SHA=7b5f3c2defe9e958e000db804d2ba87448d0fc26867c61003000522b4ff1e394
SCHEMA_SHA=cf029fd05b8109678ef9016deefeeb76faa05040106522abd1995ff1f6bfba58
ED_ZIP=/mnt/c/Users/<user>/Downloads/mimic-iv-ed-2.2.zip
ED_SHA=d17bbf2efe6a4a7e0f29c73b0743e6d2b7fb840e9b1a14f9064f23c70d868fc9
ECG_ZIP=/mnt/c/Users/<user>/Downloads/mimic-iv-ecg-ext-icd-diagnostic-labels-for-mimic-iv-ecg-1.0.1.zip
ECG_SHA=4b99cac62b675fcf35e6822910014431c511aebba903b5ebc3f3739856ff553c
H=/mnt/c/Users/<user>/Downloads/mimic_raw/mimiciv_3.1/hosp
LAB_SHA=2cd5e09b7e48c0189828854221f97e2e8568268eda82157c6933bf8e674d08d5
DLAB_SHA=b7afdda77b637a7afe4f2ddfcce19e6c6becad41da397e95631cc1d416de548f
ADM_SHA=a9584ed88e9ed664a2f66f86a5cf9fd175c8bb0af50e3b6115598b19e978384e
B0A_PUB_SHA=8434a874dedea405609ddd8a1a4b1ba424e9fbda46f577cff7c0daaf8104cfc6
B="$(cd "$(dirname "$0")" && pwd)"
R="$HOME/<restricted>/nbi_b0c"
cd "$B" || { echo "B0C_FINAL verdict=INVALID reason=cd_failed counted=no"; exit 6; }
mkdir -p logs
TS=$(date +%Y%m%d_%H%M%S)
PRE="logs/${TS}_b0c_precheck.log"
FIN="logs/${TS}_b0c_final.log"
if [ -e out/b0c ] || [ -e "$R/sealed" ]; then echo "B0C_FINAL verdict=INVALID reason=output_exists counted=no" | tee -a "$PRE" "$FIN"; exit 4; fi
echo "${PINNED_SHA}  B0C_PINNED_SHA256SUMS" | sha256sum -c - >>"$PRE" 2>&1; r_pin=$?
sha256sum -c B0C_PINNED_SHA256SUMS >>"$PRE" 2>&1; r_files=$?
echo "runner_sha256 $(sha256sum run_b0c.sh | cut -d' ' -f1)" >>"$PRE"
python3 --version >>"$PRE" 2>&1
cat "$PRE"
if [ $r_pin -ne 0 ] || [ $r_files -ne 0 ]; then
  echo "B0C_FINAL verdict=INVALID reason=pinned_sha_mismatch counted=no" | tee -a "$PRE" "$FIN"; exit 5
fi
mkdir -p "$R" && chmod 700 "$R"
python3 b0c_availability.py --ed-zip "$ED_ZIP" --ed-zip-sha "$ED_SHA" --ecg-zip "$ECG_ZIP" --ecg-zip-sha "$ECG_SHA" \
  --labevents "$H/labevents.csv.gz" --labevents-sha "$LAB_SHA" --d-labitems "$H/d_labitems.csv.gz" \
  --d-labitems-sha "$DLAB_SHA" --admissions "$H/admissions.csv.gz" --admissions-sha "$ADM_SHA" \
  --schema expected_schema_b0c.json --schema-sha "$SCHEMA_SHA" --b0a-public out/b0a/b0a_public.json \
  --b0a-public-sha "$B0A_PUB_SHA" --out out/b0c --sealed "$R/sealed" \
  --private-log "$R/private_${TS}.log" >"logs/${TS}_b0c_run.log" 2>&1
rc=$?
cat "logs/${TS}_b0c_run.log"
V=$(grep -o 'B0C_VERDICT [A-Z_]*' "logs/${TS}_b0c_run.log" | tail -1 | cut -d' ' -f2)
if [ -f out/b0c/b0c_public.json ]; then C=yes; else C=no; fi
echo "B0C_FINAL verdict=${V:-NO_VERDICT} rc=$rc counted=$C" | tee "$FIN"
exit $rc
