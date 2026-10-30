#!/usr/bin/env bash
# EXP-SN-NBI-004 NBI-B1S runner — RG RUN 후 launch_b1s.sh 로만 시작. LOCAL ONLY. 인자 금지.
# 종료코드: 0 COMPLETE / 2 INVALID(python) / 3 STOP_TITLE / 4 output_exists / 5 pinned_sha_mismatch / 6 cd_failed / 7 args_not_allowed
# 공개 출력(out/b1s/b1s_public.json)이 생성되지 않은 실행은 counted run 으로 세지 않음.
# 모든 경로는 스크립트 위치 기준 절대경로.
set -uo pipefail
if [ $# -ne 0 ]; then echo "B1S_FINAL verdict=INVALID reason=args_not_allowed counted=no"; exit 7; fi
PINNED_SHA=dd924dad7fa4cb0128e488a63769c3a8085f7f8b07e3e46ea8cb7229e1bed855
SCHEMA_SHA=b08c31346dbaf0b9f79601d6a9946b96fe8cd45dd221cd8871f6c527dc58b612
ED_ZIP=/mnt/c/Users/<user>/Downloads/mimic-iv-ed-2.2.zip
ED_SHA=d17bbf2efe6a4a7e0f29c73b0743e6d2b7fb840e9b1a14f9064f23c70d868fc9
ECG_ZIP=/mnt/c/Users/<user>/Downloads/mimic-iv-ecg-ext-icd-diagnostic-labels-for-mimic-iv-ecg-1.0.1.zip
ECG_SHA=4b99cac62b675fcf35e6822910014431c511aebba903b5ebc3f3739856ff553c
H=/mnt/c/Users/<user>/Downloads/mimic_raw/mimiciv_3.1/hosp
LAB_SHA=2cd5e09b7e48c0189828854221f97e2e8568268eda82157c6933bf8e674d08d5
DLAB_SHA=b7afdda77b637a7afe4f2ddfcce19e6c6becad41da397e95631cc1d416de548f
PAT_SHA=4c7507de7ecad8c5ba7647ea4d26018e88ff6672c5fc22ab59c2a5697d687cdd
B1_PUB_SHA=1137ab9dd3eb66874ab719db7355ff89e12f3815cd34aaf35cc78ecc65ac3e0b
B="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)" || { echo "B1S_FINAL verdict=INVALID reason=cd_failed counted=no"; exit 6; }
O="$(cd "$B/../b1/out/b1" && pwd)" || { echo "B1S_FINAL verdict=INVALID reason=cd_failed counted=no"; exit 6; }
R="$HOME/<restricted>/nbi_b1s"
cd "$B" || { echo "B1S_FINAL verdict=INVALID reason=cd_failed counted=no"; exit 6; }
L="$B/logs"
mkdir -p "$L"
TS=$(date +%Y%m%d_%H%M%S)
PRE="$L/${TS}_b1s_precheck.log"
FIN="$L/${TS}_b1s_final.log"
RUN="$L/${TS}_b1s_run.log"
if [ -e "$B/out/b1s" ] || [ -e "$R/sealed" ]; then echo "B1S_FINAL verdict=INVALID reason=output_exists counted=no" | tee -a "$PRE" "$FIN"; exit 4; fi
echo "${PINNED_SHA}  B1S_PINNED_SHA256SUMS" | sha256sum -c - >>"$PRE" 2>&1; r_pin=$?
sha256sum -c B1S_PINNED_SHA256SUMS >>"$PRE" 2>&1; r_files=$?
echo "runner_sha256 $(sha256sum "$B/run_b1s.sh" | cut -d' ' -f1)" >>"$PRE"
echo "launcher_sha256 $(sha256sum "$B/launch_b1s.sh" | cut -d' ' -f1)" >>"$PRE"
python3 --version >>"$PRE" 2>&1
cat "$PRE"
if [ $r_pin -ne 0 ] || [ $r_files -ne 0 ]; then
  echo "B1S_FINAL verdict=INVALID reason=pinned_sha_mismatch counted=no" | tee -a "$PRE" "$FIN"; exit 5
fi
mkdir -p "$R" && chmod 700 "$R"
python3 "$B/b1s_sensitivity.py" --ed-zip "$ED_ZIP" --ed-zip-sha "$ED_SHA" --ecg-zip "$ECG_ZIP" --ecg-zip-sha "$ECG_SHA" \
  --labevents "$H/labevents.csv.gz" --labevents-sha "$LAB_SHA" --d-labitems "$H/d_labitems.csv.gz" \
  --d-labitems-sha "$DLAB_SHA" --patients "$H/patients.csv.gz" --patients-sha "$PAT_SHA" \
  --schema "$B/expected_schema_b1s.json" --schema-sha "$SCHEMA_SHA" \
  --b1-public "$O/b1_public.json" --b1-public-sha "$B1_PUB_SHA" \
  --out "$B/out/b1s" --sealed "$R/sealed" --private-log "$R/private_${TS}.log" >"$RUN" 2>&1
rc=$?
cat "$RUN"
V=$(grep -o 'B1S_VERDICT [A-Z_]*' "$RUN" | tail -1 | cut -d' ' -f2)
if [ -f "$B/out/b1s/b1s_public.json" ]; then C=yes; else C=no; fi
echo "B1S_FINAL verdict=${V:-NO_VERDICT} rc=$rc counted=$C" | tee "$FIN"
exit $rc
