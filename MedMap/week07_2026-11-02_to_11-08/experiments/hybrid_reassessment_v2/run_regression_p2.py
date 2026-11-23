"""P2 회귀: 테스트 묶음 × 코드(P1·P2)를 각각 별도 프로세스로 실행해 테스트별 결과 기록. 테스트 파일은 수정하지 않는다.
결과 outputs/p2_regression.json. 사용: python run_regression_p2.py [--one PACKAGE SUITE]"""
import importlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

H = Path(__file__).resolve().parent
RUNS = [("hybrid2_p1", "test_pipeline"), ("hybrid2_p1", "test_safety_patch_p1"),
        ("hybrid2_p2", "test_pipeline"), ("hybrid2_p2", "test_safety_patch_p1"), ("hybrid2_p2", "test_safety_patch_p2"),
        ("hybrid2_p2", "test_pipeline", "synthetic"), ("hybrid2_p2", "test_safety_patch_p1", "synthetic")]
# synthetic: 분류용. 실행기 안에서만 mode 미지정 입력을 SYNTHETIC_ASSUMPTION 으로 실행(코드·테스트 무수정). 남는 실패는 C 이외 원인


def one(pkg, suite, variant=""):
    sys.path.insert(0, str(H))
    sys.path.insert(0, str(H / "tests"))
    for alias in ("hybrid2", "hybrid2_p1"):                              # 테스트가 import 하는 패키지 이름을 대상 코드로 연결
        if alias == pkg:
            continue
        sys.modules[alias] = importlib.import_module(pkg)
        for m in ("clinical_context", "lexicon", "parser", "pipeline", "relations"):
            sys.modules[f"{alias}.{m}"] = importlib.import_module(f"{pkg}.{m}")
    if variant == "synthetic":
        ec = importlib.import_module(f"{pkg}.evidence_conditions")
        orig = ec.normalize_context
        ec.normalize_context = lambda ctx: orig({"mode": ec.SYNTHETIC, **ctx})
    r = unittest.TextTestRunner(stream=open("/dev/null", "w"), verbosity=0).run(unittest.defaultTestLoader.loadTestsFromName(suite))
    bad = {t.id(): ("FAIL", str(e).strip().splitlines()[-1][:300]) for t, e in r.failures} | {t.id(): ("ERROR", str(e).strip().splitlines()[-1][:300]) for t, e in r.errors}
    print(json.dumps({"code": pkg, "suite": suite, "variant": variant, "ran": r.testsRun, "failed": bad, "pipeline_module": sys.modules["hybrid2_p1.pipeline" if pkg != "hybrid2_p1" else "hybrid2.pipeline"].__name__}, ensure_ascii=False))


if len(sys.argv) >= 4 and sys.argv[1] == "--one":
    one(*sys.argv[2:])
    sys.exit(0)
res = []
for pkg, suite, *v in RUNS:
    p = subprocess.run([sys.executable, "-B", __file__, "--one", pkg, suite, *v], cwd=H, capture_output=True, text=True, timeout=300)
    res.append(json.loads(p.stdout.strip().splitlines()[-1]) if p.returncode == 0 else {"code": pkg, "suite": suite, "crash": p.stderr[-1500:]})
    x = res[-1]
    print(pkg, suite, *v, "ran", x.get("ran"), "failed", len(x.get("failed", {})), "crash" if "crash" in x else "")
(H / "outputs/p2_regression.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
