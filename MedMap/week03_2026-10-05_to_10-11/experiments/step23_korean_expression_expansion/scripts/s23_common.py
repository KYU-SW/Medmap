"""STEP23 공통. STEP22 lin_common(모델 정의·top-k·지표·NORMALIZER_CORE)을 그대로 재사용한다.

- 기존 STEP21/22 test 는 이 단계부터 FIXED_REGRESSION_TEST 라고 부른다(완전 blind holdout 아님).
- 학습 label space = STEP22 와 같은 77 class (TARGET_20 증강 + CONFUSER_57 기존 표현 유지).
"""
from __future__ import annotations

import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
S22 = REPO / "exp/step22_korean_linear_normalizer"
sys.path.insert(0, str(S22 / "scripts"))
import lin_common as L22  # noqa: E402

c21 = L22.c21
WS = Path.home() / "medmap_step23_authoring_ws"
DATA = STEP / "data"
OUT = STEP / "outputs"
MODELS = STEP / "models"
for _d in (DATA, OUT, MODELS):
    _d.mkdir(exist_ok=True)

SEED = 42
TARGET20 = list(L22.PILOT)
FAMILIES = ["LINEAR_CHAR", "LINEAR_WORD_CHAR"]          # 실행 전 사전 등록한 두 후보
CONDITIONS = {"ORIGINAL": "STEP22 CURATED 276", "EXPANDED": "STEP22 CURATED 276 + STEP23 VALID TARGET_20"}
# STEP22 dev 선택값(ngram·min_df 고정). 이번 tuning 은 C × class_weight 작은 grid 만(dev).
S22_PARAMS = {"LINEAR_CHAR": {"ngram": [2, 4], "min_df": 2, "C": 4.0, "class_weight": None},
              "LINEAR_WORD_CHAR": {"ngram": [2, 4], "min_df": 1, "C": 0.5, "class_weight": "balanced"}}
SMALL_GRID_C = [0.5, 1.0, 2.0, 4.0]
SMALL_GRID_CW = [None, "balanced"]

read_csv, write_csv, sha256, norm, dump_json, rnd = (L22.read_csv, L22.write_csv, L22.sha256, L22.norm, L22.dump_json, L22.rnd)
build, topk, score, is_core, load_gold = L22.build, L22.topk, L22.score, L22.is_core, L22.load_gold


def nospace(s: str) -> str:
    return norm(s).replace(" ", "")


def grid(family: str) -> list[dict]:
    base = S22_PARAMS[family]
    return [{**base, "C": C, "class_weight": cw} for C in SMALL_GRID_C for cw in SMALL_GRID_CW]


def load_condition(cond: str) -> tuple[list[str], list[str]]:
    rows = read_csv(DATA / "expanded_train_expressions.csv")
    if cond == "ORIGINAL":
        rows = [r for r in rows if r["origin"] == "STEP22_CURATED"]
    return [r["normalized_expression"] for r in rows], [r["canonical_id"] for r in rows]


def macro_top1(rows: list[dict], ranked: dict) -> float | None:
    by = {}
    for g in rows:
        by.setdefault(g["primary_concept"], []).append(bool(ranked[g["utterance_id"]][:1] and ranked[g["utterance_id"]][0] == g["primary_concept"]))
    return rnd(sum(sum(v) / len(v) for v in by.values()) / len(by)) if by else None
