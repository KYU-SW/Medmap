"""STEP24 공통. STEP23 데이터·선택·모델(LINEAR_CHAR EXPANDED)과 STEP22/21 공통 함수를 그대로 참조한다.

데이터 고정(STEP23 expanded_train_expressions.csv · core dev 59 · FIXED_REGRESSION_TEST core 109), 모델만 변경.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
S23 = REPO / "exp/step23_korean_expression_expansion"
sys.path.insert(0, str(S23 / "scripts"))
import s23_common as S23C  # noqa: E402

c21 = S23C.c21
DATA, OUT, MODELS = STEP / "data", STEP / "outputs", STEP / "models"
for _d in (DATA, OUT, MODELS):
    _d.mkdir(exist_ok=True)
SEED = 42
HF_REPO = "monologg/koelectra-small-v3-discriminator"
HF_REVISION = "7488f8db0f208beff4a1f3f9bb3ed04650a89ed7"
PRETRAINED_SRC = MODELS / "pretrained_koelectra_small_main"      # 원본(.bin, 소유자 main 커밋)
PRETRAINED = MODELS / "pretrained_koelectra_small"               # weights_only 로 읽어 safetensors 로 변환한 사본
FT_DIR = MODELS / "koelectra_small"

read_csv, write_csv, sha256, norm, rnd = S23C.read_csv, S23C.write_csv, S23C.sha256, S23C.norm, S23C.rnd
score, is_core, load_gold, nospace, macro_top1 = S23C.score, S23C.is_core, S23C.load_gold, S23C.nospace, S23C.macro_top1
TARGET20 = S23C.TARGET20


def dump_json(p: Path, o):
    S23C.dump_json(p, o)


def load_json(p: Path):
    return json.load(open(p, encoding="utf-8"))


def train_data():
    """EXPANDED 학습셋(1,119). 입력 텍스트는 STEP23 과 같은 norm() 적용 문자열."""
    X, y = S23C.load_condition("EXPANDED")
    return X, y


def label_map() -> dict[str, int]:
    """class → int. 사전순 = sklearn LinearSVC classes_ 순서와 동일(assert 로 확인)."""
    _, y = train_data()
    return {c: i for i, c in enumerate(sorted(set(y)))}


def eval_sets():
    gold = load_gold()
    core_dev = [g for g in gold if g["split"] == "dev" and is_core(g)]
    core_test = [g for g in gold if g["split"] == "test" and is_core(g)]
    assert (len(core_dev), len(core_test)) == (59, 109)
    return gold, core_dev, core_test


def linear_model():
    import joblib
    sel = load_json(S23 / "outputs/selection.json")
    return joblib.load(S23 / sel["conditions"]["EXPANDED"]["families"]["LINEAR_CHAR"]["model_file"]), sel


def sim_bucket(x: float) -> str:
    return "<0.3" if x < 0.3 else "0.3-0.5" if x < 0.5 else "0.5-0.7" if x < 0.7 else ">=0.7"


def test_similarity(core_test) -> dict[str, float]:
    """STEP23 contamination_sensitivity 와 같은 정의: 같은 concept STEP23 생성 학습 표현과의 최대 difflib ratio."""
    import difflib
    rows = read_csv(S23 / "data/expanded_train_expressions.csv")
    gen = [(nospace(r["expression"]), r["canonical_id"]) for r in rows if r["origin"] == "STEP23_GENERATED"]
    out = {}
    for g in core_test:
        u = nospace(g["text_ko"])
        out[g["utterance_id"]] = max([difflib.SequenceMatcher(None, u, x, autojunk=False).ratio() for x, c in gen
                                      if c == g["primary_concept"]] or [0.0])
    return out
