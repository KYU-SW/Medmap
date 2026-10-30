#!/usr/bin/env bash
# §17-18 재현성: run_all 2회. 공식 = 1회차 산출물. 결정적 산출물 SHA 비교(latency·memory·verdict·manifest 제외 — 시간 값 포함) → logs/repro_check.json
set -euo pipefail
cd "$(dirname "$0")"
PY="${PY:-$HOME/ai_env/bin/python}"
bash run_all.sh
rm -rf logs/run1_outputs logs/run1_preview && cp -r outputs logs/run1_outputs && cp -r preview logs/run1_preview
bash run_all.sh
rm -rf logs/run2_outputs && cp -r outputs logs/run2_outputs
"$PY" - <<'PYEOF'
import hashlib, json, pathlib
skip = {"latency.json", "memory.json", "integration_verdict.json", "manifest.json"}
a, b = pathlib.Path("logs/run1_outputs"), pathlib.Path("logs/run2_outputs")
h = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
names = sorted({p.name for p in a.iterdir()} | {p.name for p in b.iterdir()})
diff = [n for n in names if n not in skip and (not (a / n).exists() or not (b / n).exists() or h(a / n) != h(b / n))]
res = {"status": "SHA_IDENTICAL" if not diff else "DIFFERENT", "compared": [n for n in names if n not in skip], "excluded": sorted(skip), "different": diff,
       "verdict_run1": json.loads((a / "integration_verdict.json").read_text())["STEP30_RESULT"],
       "verdict_run2": json.loads((b / "integration_verdict.json").read_text())["STEP30_RESULT"],
       "cpu_p95_run1": json.loads((a / "integration_verdict.json").read_text())["CPU_P95"],
       "cpu_p95_run2": json.loads((b / "integration_verdict.json").read_text())["CPU_P95"]}
pathlib.Path("logs/repro_check.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
print(json.dumps(res, ensure_ascii=False)[:600])
PYEOF
# 공식 = 1회차: 결과 복원 후 재현 결과를 넣어 판정·보고서만 다시 생성
rm -rf outputs && cp -r logs/run1_outputs outputs && rm -rf preview && cp -r logs/run1_preview preview
cd scripts && PYTHONDONTWRITEBYTECODE=1 "$PY" finalize_verdict.py && PYTHONDONTWRITEBYTECODE=1 "$PY" build_report.py && PYTHONDONTWRITEBYTECODE=1 "$PY" license_scan.py
echo RUN_TWICE_DONE
