#!/usr/bin/env bash
# EXP-SN-NBI-003 NBI-B1 runner — RG RUN + 사용자 실행 승인 후 launch_b1.sh 로만 시작. LOCAL ONLY. 인자 금지.
# 종료코드: 0 COMPLETE / 2 INVALID(python) / 3 STOP_TITLE / 4 output_exists / 5 pinned_sha_mismatch / 6 cd_failed / 7 args_not_allowed
# 공개 출력(out/b1/b1_public.json)이 생성되지 않은 실행은 승인된 실데이터 1회 실행으로 세지 않음(manifest [K]).
# 모든 경로는 스크립트 위치 기준 절대경로.
set -uo pipefail
if [ $# -ne 0 ]; then echo "B1_FINAL verdict=INVALID reason=args_not_allowed counted=no"; exit 7; fi
PINNED_SHA=da0fc2726cb16b63604c3ca7ed76d96b724d1dc327e04d74508f4b7927e1c7da
SCHEMA_SHA=a5c86039d83c4182f8dd63e67c3e0177f2d7aca581fb2f3f89e54b8b048b463f
ED_ZIP=/mnt/c/Users/<user>/Downloads/mimic-iv-ed-2.2.zip
ED_SHA=d17bbf2efe6a4a7e0f29c73b0743e6d2b7fb840e9b1a14f9064f23c70d868fc9
ECG_ZIP=/mnt/c/Users/<user>/Downloads/mimic-iv-ecg-ext-icd-diagnostic-labels-for-mimic-iv-ecg-1.0.1.zip
ECG_SHA=4b99cac62b675fcf35e6822910014431c511aebba903b5ebc3f3739856ff553c
H=/mnt/c/Users/<user>/Downloads/mimic_raw/mimiciv_3.1/hosp
LAB_SHA=2cd5e09b7e48c0189828854221f97e2e8568268eda82157c6933bf8e674d08d5
DLAB_SHA=b7afdda77b637a7afe4f2ddfcce19e6c6becad41da397e95631cc1d416de548f
PAT_SHA=4c7507de7ecad8c5ba7647ea4d26018e88ff6672c5fc22ab59c2a5697d687cdd
B0A_PUB_SHA=8434a874dedea405609ddd8a1a4b1ba424e9fbda46f577cff7c0daaf8104cfc6
B0C_PUB_SHA=bde70d7854407813310ca117c6af6fe476d7e1858571c4d75d6e44e2eb9078be
B0D_PUB_SHA=83d09679724144c2fb2a3f859d8c5ede7ebcb17bc7bdb037b52cc8dd71f0a5f0
B="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)" || { echo "B1_FINAL verdict=INVALID reason=cd_failed counted=no"; exit 6; }
O="$(cd "$B/../b0/out" && pwd)" || { echo "B1_FINAL verdict=INVALID reason=cd_failed counted=no"; exit 6; }
R="$HOME/<restricted>/nbi_b1"
cd "$B" || { echo "B1_FINAL verdict=INVALID reason=cd_failed counted=no"; exit 6; }
L="$B/logs"
mkdir -p "$L"
TS=$(date +%Y%m%d_%H%M%S)
PRE="$L/${TS}_b1_precheck.log"
FIN="$L/${TS}_b1_final.log"
RUN="$L/${TS}_b1_run.log"
if [ -e "$B/out/b1" ] || [ -e "$R/sealed" ]; then echo "B1_FINAL verdict=INVALID reason=output_exists counted=no" | tee -a "$PRE" "$FIN"; exit 4; fi
echo "${PINNED_SHA}  B1_PINNED_SHA256SUMS" | sha256sum -c - >>"$PRE" 2>&1; r_pin=$?
sha256sum -c B1_PINNED_SHA256SUMS >>"$PRE" 2>&1; r_files=$?
echo "runner_sha256 $(sha256sum "$B/run_b1.sh" | cut -d' ' -f1)" >>"$PRE"
echo "launcher_sha256 $(sha256sum "$B/launch_b1.sh" | cut -d' ' -f1)" >>"$PRE"
python3 --version >>"$PRE" 2>&1
cat "$PRE"
if [ $r_pin -ne 0 ] || [ $r_files -ne 0 ]; then
  echo "B1_FINAL verdict=INVALID reason=pinned_sha_mismatch counted=no" | tee -a "$PRE" "$FIN"; exit 5
fi
mkdir -p "$R" && chmod 700 "$R"
python3 "$B/b1_feasibility.py" --ed-zip "$ED_ZIP" --ed-zip-sha "$ED_SHA" --ecg-zip "$ECG_ZIP" --ecg-zip-sha "$ECG_SHA" \
  --labevents "$H/labevents.csv.gz" --labevents-sha "$LAB_SHA" --d-labitems "$H/d_labitems.csv.gz" \
  --d-labitems-sha "$DLAB_SHA" --patients "$H/patients.csv.gz" --patients-sha "$PAT_SHA" \
  --schema "$B/expected_schema_b1.json" --schema-sha "$SCHEMA_SHA" \
  --b0a-public "$O/b0a/b0a_public.json" --b0a-public-sha "$B0A_PUB_SHA" \
  --b0c-public "$O/b0c/b0c_public.json" --b0c-public-sha "$B0C_PUB_SHA" \
  --b0d-public "$O/b0d/b0d_public.json" --b0d-public-sha "$B0D_PUB_SHA" \
  --out "$B/out/b1" --sealed "$R/sealed" --private-log "$R/private_${TS}.log" >"$RUN" 2>&1
rc=$?
cat "$RUN"
V=$(grep -o 'B1_VERDICT [A-Z_]*' "$RUN" | tail -1 | cut -d' ' -f2)
if [ -f "$B/out/b1/b1_public.json" ]; then C=yes; else C=no; fi
echo "B1_FINAL verdict=${V:-NO_VERDICT} rc=$rc counted=$C" | tee "$FIN"
exit $rc
