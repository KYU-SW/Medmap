# -*- coding: utf-8 -*-
"""원본 pipeline(src_copy 사본)을 __init__.py 실행 없이 로드한다.

- __init__.py 는 graph/langchain/LLM 관련 import 를 포함하므로 실행하지 않는다.
- analyzer.py / z3env.py / models.py / lsh_cluster.py 만 로드한다 (LLM 호출 함수 없음).
- predicates.json 이 공개 저장소에 없으므로, 각 pred.X 를 독립 Bool 원자
  "$ Has(atom.X) $" 로 정의하는 '원자 술어 추상화(atomic predicate abstraction)'를 사용한다.
"""
import importlib
import json
import os
import re
import sys
import types

D_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(D_ROOT, "src_copy")
RULES_PATH = os.path.join(SRC, "rules_gold.json")


def load_pipeline_modules():
    if "pipeline.analyzer" in sys.modules:
        return sys.modules["pipeline.analyzer"], sys.modules["pipeline.z3env"], sys.modules["pipeline.lsh_cluster"]
    pkg = types.ModuleType("pipeline")
    pkg.__path__ = [os.path.join(SRC, "pipeline")]
    sys.modules["pipeline"] = pkg
    z3env = importlib.import_module("pipeline.z3env")
    lsh = importlib.import_module("pipeline.lsh_cluster")
    analyzer = importlib.import_module("pipeline.analyzer")
    return analyzer, z3env, lsh


def load_rules():
    with open(RULES_PATH, encoding="utf-8") as f:
        return json.load(f)


PRED_RE = re.compile(r"pred\.[A-Za-z0-9_]+")


def atomic_predicates(rules):
    ids = sorted({p for r in rules for p in PRED_RE.findall(r.get("condition") or "")})
    return [{"id": p, "label": p, "formal_definition": f"$ Has(atom.{p[5:]}) $", "dependencies": []} for p in ids]
