"""Safety Patch P1 회귀: 수정 안 한 tests/test_pipeline.py 를 hybrid2_p1 로 실행하고, 이어서 P1 테스트 실행. 결과 outputs/p1_regression_tail.txt"""
import importlib
import io
import sys
import unittest
from pathlib import Path

H = Path(__file__).resolve().parent
sys.path.insert(0, str(H))
sys.path.insert(0, str(H / "tests"))
sys.modules["hybrid2"] = importlib.import_module("hybrid2_p1")      # test_pipeline.py 의 import 를 패치 패키지로 연결(파일은 무수정)
for m in ("lexicon", "parser", "pipeline", "relations"):
    sys.modules[f"hybrid2.{m}"] = importlib.import_module(f"hybrid2_p1.{m}")

lines, ok = [], True
for name in ("test_pipeline", "test_safety_patch_p1"):
    buf = io.StringIO()
    r = unittest.TextTestRunner(stream=buf, verbosity=0).run(unittest.defaultTestLoader.loadTestsFromName(name))
    ok = ok and r.wasSuccessful()
    lines.append(f"{name} on hybrid2_p1: Ran {r.testsRun}, failures {len(r.failures)}, errors {len(r.errors)}")
    print(buf.getvalue()[-6000:])
assert sys.modules["hybrid2.pipeline"].__name__ == "hybrid2_p1.pipeline"
(H / "outputs/p1_regression_tail.txt").write_text("\n".join(lines) + f"\nALL_OK={ok}\n", encoding="utf-8")
print("\n".join(lines), f"ALL_OK={ok}")
sys.exit(0 if ok else 1)
