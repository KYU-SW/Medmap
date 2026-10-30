#!/usr/bin/env bash
# EXP-SN-NBI-002 NBI-B0d runner — RG RUN(재심사) + 사용자 실행 승인 후 launch_b0d.sh 로만 시작. LOCAL ONLY. 인자 금지.
# 종료코드: 0 COMPLETE / 2 INVALID(python) / 3 STOP_TITLE / 4 output_exists / 5 pinned_sha_mismatch / 6 cd_failed / 7 args_not_allowed
# 공개 출력(out/b0d/b0d_public.json)이 생성되지 않은 실행은 승인된 실데이터 1회 실행으로 세지 않음(manifest [K]·[O]).
# 모든 경로는 스크립트 위치 기준 절대경로(B0c ram_guard 상대경로 사고 재발 방지).
set -uo pipefail
if [ $# -ne 0 ]; then echo "B0D_FINAL verdict=INVALID reason=args_not_allowed counted=no"; exit 7; fi
PINNED_SHA=67c91e317b3faaef9c6c67ec7883f6e9dcf951d7a0021e5705d7a3c7864d4dc9
SCHEMA_SHA=5beeb7c81d049166a23c5f92f637557bad09c8c5d7494eca1f2ebba30a5ed897
ED_ZIP=/mnt/c/Users/<user>/Downloads/mimic-iv-ed-2.2.zip
ED_SHA=d17bbf2efe6a4a7e0f29c73b0743e6d2b7fb840e9b1a14f9064f23c70d868fc9
ECG_ZIP=/mnt/c/Users/<user>/Downloads/mimic-iv-ecg-ext-icd-diagnostic-labels-for-mimic-iv-ecg-1.0.1.zip
ECG_SHA=4b99cac62b675fcf35e6822910014431c511aebba903b5ebc3f3739856ff553c
N=/mnt/c/Users/<user>/Downloads/mimic_raw/mimic-iv-note_2.2/note
RAD_SHA=2c09bc76ee12d5f3b8f572deb7218fbaf3e59b32eccfdae14686e05ae099eebb
DET_SHA=9d3f6c44183c55ef8a0c511a2c72612568ad457fc53c035c8443c28a8cc53773
B0A_PUB_SHA=8434a874dedea405609ddd8a1a4b1ba424e9fbda46f577cff7c0daaf8104cfc6
B0C_PUB_SHA=bde70d7854407813310ca117c6af6fe476d7e1858571c4d75d6e44e2eb9078be
B="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)" || { echo "B0D_FINAL verdict=INVALID reason=cd_failed counted=no"; exit 6; }
R="$HOME/<restricted>/nbi_b0d"
cd "$B" || { echo "B0D_FINAL verdict=INVALID reason=cd_failed counted=no"; exit 6; }
L="$B/logs"
mkdir -p "$L"
TS=$(date +%Y%m%d_%H%M%S)
PRE="$L/${TS}_b0d_precheck.log"
FIN="$L/${TS}_b0d_final.log"
RUN="$L/${TS}_b0d_run.log"
if [ -e "$B/out/b0d" ] || [ -e "$R/sealed" ]; then echo "B0D_FINAL verdict=INVALID reason=output_exists counted=no" | tee -a "$PRE" "$FIN"; exit 4; fi
echo "${PINNED_SHA}  B0D_PINNED_SHA256SUMS" | sha256sum -c - >>"$PRE" 2>&1; r_pin=$?
sha256sum -c B0D_PINNED_SHA256SUMS >>"$PRE" 2>&1; r_files=$?
echo "runner_sha256 $(sha256sum "$B/run_b0d.sh" | cut -d' ' -f1)" >>"$PRE"
echo "launcher_sha256 $(sha256sum "$B/launch_b0d.sh" | cut -d' ' -f1)" >>"$PRE"
python3 --version >>"$PRE" 2>&1
cat "$PRE"
if [ $r_pin -ne 0 ] || [ $r_files -ne 0 ]; then
  echo "B0D_FINAL verdict=INVALID reason=pinned_sha_mismatch counted=no" | tee -a "$PRE" "$FIN"; exit 5
fi
mkdir -p "$R" && chmod 700 "$R"
python3 "$B/b0d_availability.py" --ed-zip "$ED_ZIP" --ed-zip-sha "$ED_SHA" --ecg-zip "$ECG_ZIP" --ecg-zip-sha "$ECG_SHA" \
  --radiology "$N/radiology.csv.gz" --radiology-sha "$RAD_SHA" --radiology-detail "$N/radiology_detail.csv.gz" \
  --radiology-detail-sha "$DET_SHA" --schema "$B/expected_schema_b0d.json" --schema-sha "$SCHEMA_SHA" \
  --b0a-public "$B/out/b0a/b0a_public.json" --b0a-public-sha "$B0A_PUB_SHA" \
  --b0c-public "$B/out/b0c/b0c_public.json" --b0c-public-sha "$B0C_PUB_SHA" --out "$B/out/b0d" --sealed "$R/sealed" \
  --private-log "$R/private_${TS}.log" >"$RUN" 2>&1
rc=$?
cat "$RUN"
V=$(grep -o 'B0D_VERDICT [A-Z_]*' "$RUN" | tail -1 | cut -d' ' -f2)
if [ -f "$B/out/b0d/b0d_public.json" ]; then C=yes; else C=no; fi
echo "B0D_FINAL verdict=${V:-NO_VERDICT} rc=$rc counted=$C" | tee "$FIN"
exit $rc
