"""STEP26 공통 — OOD 탐지·안전 정규화(실험용). 기존 모델·데이터는 읽기만 한다.

고정 모델: LINEAR_CHAR(STEP23 EXPANDED) · KOELECTRA_SMALL(STEP24-v2 seed42, CPU) · HYBRID_B(STEP24-v2 seed42 hybrid_config 임계값).
weak label(외부 NER 범주) 은 MedMap concept 정답이 아니다 — 위험 탐지용 proxy 로만 쓴다.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
S25_DIR = REPO / "exp/step25_external_korean_medical_data"
sys.path.insert(0, str(S25_DIR / "scripts"))
import s25_common as S25  # noqa: E402

S24 = S25.S24
V2, S23 = S25.V2, S24.S23
RAW = S25.RAW
DATA, OUT, DOCS = STEP / "data", STEP / "outputs", STEP / "docs"
for _d in (DATA, OUT, DOCS):
    _d.mkdir(exist_ok=True)
read_csv, write_csv, sha256, norm, nospace, rnd, load_json, dump_json = (S25.read_csv, S25.write_csv, S25.sha256, S25.norm, S25.nospace,
                                                                         S25.rnd, S25.load_json, S25.dump_json)
TARGET20 = S25.TARGET20
SEED = 42
HC = S24.load_json(V2 / "outputs/seeds/seed42/hybrid_config.json")
T_LIN, T_KOE = HC["T_lin_margin(STEP23 dev)"], HC["T_koe_conf(dev)"]
KOE_DIR = V2 / "models/koelectra_small_seed42"

# 외부 NER 태그 정의(파일에서 확인한 실제 태그만)
WEAK_GROUP = {("BERT_NER_KO", "ST"): "WEAK_SYMPTOM", ("BERT_NER_KO", "DS"): "WEAK_NON_SYMPTOM", ("BERT_NER_KO", "BD"): "WEAK_NON_SYMPTOM",
              ("KBMC", "Body"): "WEAK_NON_SYMPTOM", ("KBMC", "Treatment"): "WEAK_NON_SYMPTOM", ("KBMC", "Disease"): "WEAK_MIXED"}

JOSA = re.compile(r"(으로는|으로|에서|에게|까지|부터|이라고|라고|이나|인지|이며|이고|이란|이라|하고|과|와|이|가|을|를|은|는|도|의|에|로|만|일)$")
COMPLEX = {"negation": re.compile(r"(없어|없고|없는|없다|않|안 |못 |아니)"), "historical": re.compile(r"(었었|았었|예전|전에는|나았|괜찮아졌)"),
           "other_person": re.compile(r"(엄마|아빠|어머니|아버지|아이가|애가|남편|아내|딸|아들|친구|동생|언니|오빠|형이|누나|할머니|할아버지)"),
           "multi": re.compile(r"(그리고|그리고요|랑 |하고 |이고 |, )")}


def stem_key(s: str) -> str:
    k = nospace(s)
    for _ in range(2):
        k2 = JOSA.sub("", k)
        if len(k2) < 1 or k2 == k:
            break
        k = k2
    return k


def complex_flags(text: str) -> list[str]:
    f = [k for k, p in COMPLEX.items() if p.search(text)]
    if len(text) > 40:
        f.append("long_gt40")
    return f


def split_of(cluster_key: str) -> str:
    h = int(hashlib.sha256(f"step26|{cluster_key}".encode()).hexdigest(), 16)
    return "DEVELOPMENT" if h % 2 == 0 else "HELD_OUT_EXTERNAL_EVALUATION"


def load_bert_ner_ko_docs() -> list[dict]:
    """CoNLL + -DOCSTART- 문서 경계(536 답변)."""
    rows = []
    for split in ("train", "eval"):
        doc, sent = -1, []
        for ln in (RAW / f"bert_ner_ko/{split}_diagnosis_shuffle1.txt").read_text(encoding="utf-8").splitlines() + [""]:
            p = ln.split()
            if p and p[0] == "-DOCSTART-":
                doc += 1
                continue
            if not p:
                if sent:
                    toks, tags = [x[0] for x in sent], [x[-1] for x in sent]
                    rows.append({"doc": f"NERKO_{split}_d{doc:04d}", "tokens": toks, "tags": tags, "spans": S25.bio_spans(toks, tags)})
                sent = []
            else:
                sent.append(p)
    return rows


def dumps(o):
    return json.dumps(o, ensure_ascii=False)
