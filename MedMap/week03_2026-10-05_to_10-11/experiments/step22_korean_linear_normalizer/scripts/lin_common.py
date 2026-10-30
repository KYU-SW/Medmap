"""STEP22 공통: 경로 · NORMALIZER_CORE 정의 · 모델 정의 · top-k 예측 · 지표.

원칙
- 결정적(random_state=42). CPU sklearn 만 사용(CUDA·PyTorch·Transformer 없음).
- 학습 입력 = STEP21 dictionary_expressions.csv(기존 MedMap 자원) 뿐. pilot_gold 의 test 문장은 학습·선택에 쓰지 않는다.
- 정규화는 STEP21 el_common.norm(NFC·문장부호 제거·공백 정리)을 그대로 재사용한다.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import numpy as np

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
S21 = REPO / "exp/step21_korean_symptom_entity_linking"
sys.path.insert(0, str(S21 / "scripts"))
import el_common as c21  # noqa: E402

DATA = STEP / "data"
OUT = STEP / "outputs"
MODELS = STEP / "models"
for _d in (DATA, OUT, MODELS):
    _d.mkdir(exist_ok=True)

SEED = 42
FAMILIES = ["LINEAR_WORD", "LINEAR_CHAR", "LINEAR_WORD_CHAR"]
VIEWS = ["CURATED", "RAW"]          # 주 view = CURATED(실행 전 고정), RAW = 비교용
PRIMARY_VIEW = "CURATED"
PILOT = c21.PILOT
PILOT_NAMES = c21.PILOT_NAMES

read_csv = c21.read_csv
write_csv = c21.write_csv
sha256 = c21.sha256
norm = c21.norm


def load_gold() -> list[dict]:
    return c21.load_gold()


def is_core(g: dict) -> bool:
    """NORMALIZER_CORE: 환자 본인·PRESENT·단일 증상·should_link·Tier A/B, 부정/과거/타인/불확실/복수 제외."""
    pc = c21.patient_concepts(g)
    return (g["tier"] in ("A", "B") and g["should_link"] == "True" and g["is_multi"] == "False"
            and g["has_negation"] == "False" and g["has_temporal"] == "False"
            and g["has_other_person"] == "False" and g["has_uncertain"] == "False"
            and g["primary_status"] == "present" and pc == {g["primary_concept"]}
            and all(m["subject"] == "patient" and m["status"] == "present" for m in g["gold_mentions"]))


def load_train(view: str) -> tuple[list[str], list[str]]:
    rows = read_csv(DATA / "train_expressions.csv")
    if view == "CURATED":
        rows = [r for r in rows if r["curated_include"] == "True"]
    return [r["normalized_expression"] for r in rows], [r["canonical_id"] for r in rows]


# ---------------- 모델 ----------------
TOKEN = r"(?u)\b\w+\b"   # 한 글자 어절('열'·'목')도 살린다


def build(family: str, p: dict):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.pipeline import FeatureUnion, Pipeline
    from sklearn.svm import LinearSVC

    def word():
        return TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True, token_pattern=TOKEN,
                               min_df=p.get("min_df", 1))

    def char():
        return TfidfVectorizer(analyzer="char", ngram_range=tuple(p["ngram"]), sublinear_tf=True, min_df=p["min_df"])

    feats = {"LINEAR_WORD": word, "LINEAR_CHAR": char,
             "LINEAR_WORD_CHAR": lambda: FeatureUnion([("word", word()), ("char", char())])}[family]()
    svm = LinearSVC(C=p["C"], class_weight=p["class_weight"], random_state=SEED, max_iter=20000)
    return Pipeline([("feats", feats), ("svm", svm)])


def grid(family: str) -> list[dict]:
    Cs = [0.25, 0.5, 1.0, 2.0, 4.0]
    cws = [None, "balanced"]
    if family == "LINEAR_WORD":
        return [{"C": C, "class_weight": cw, "min_df": 1} for C in Cs for cw in cws]
    return [{"ngram": list(ng), "min_df": md, "C": C, "class_weight": cw}
            for ng in [(2, 4), (2, 5), (3, 5), (3, 6)] for md in (1, 2) for C in Cs for cw in cws]


def topk(model, texts: list[str], k: int = 5) -> list[list[tuple[str, float]]]:
    """decision_function 기준 상위 k (동점은 class id 사전순). 점수는 확률이 아니라 SVM decision margin."""
    S = model.decision_function(texts)
    cls = list(model.classes_)
    out = []
    for row in np.atleast_2d(S):
        order = sorted(range(len(cls)), key=lambda i: (-row[i], cls[i]))[:k]
        out.append([(cls[i], float(row[i])) for i in order])
    return out


# ---------------- 지표 ----------------
def rnd(x):
    return None if x is None else round(float(x), 4)


def score(gold_rows: list[dict], ranked: dict[str, list[str]]) -> dict:
    """ranked: utterance_id → concept 순위 목록. 정답 = 환자 concept 집합(core 는 단일)."""
    n = len(gold_rows)
    if not n:
        return {"n": 0, "top1": None, "recall_at_3": None, "recall_at_5": None}
    hit = {k: 0 for k in (1, 3, 5)}
    for g in gold_rows:
        gs = c21.patient_concepts(g)
        r = ranked.get(g["utterance_id"], [])
        for k in hit:
            hit[k] += bool(gs & set(r[:k])) if k > 1 else bool(r[:1] and r[0] in gs)
    return {"n": n, "top1": rnd(hit[1] / n), "recall_at_3": rnd(hit[3] / n), "recall_at_5": rnd(hit[5] / n),
            "n_top1_correct": hit[1]}


def dump_json(path: Path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=False)
        f.write("\n")


__all__ = ["csv"]
