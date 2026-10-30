"""STEP25 공통: 외부 한국어 의료 데이터 경로·파서 + 고정 모델(STEP23 Linear, STEP24-v2 KoELECTRA seed42, Hybrid B/C 정책).

- 원본 외부 데이터는 git 밖 ~/medmap_external_data/step25/raw/ 에 둔다(커밋·푸시 금지).
- 모델은 재학습·재튜닝하지 않는다. 임계값·α 는 STEP24-v2 seed42 hybrid_config(dev 로 정한 값) 그대로.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
V2 = REPO / "exp/step24_v2_lightweight_hybrid_normalizer"
sys.path.insert(0, str(V2 / "scripts"))
import s24_common as S24  # noqa: E402

RAW = Path.home() / "medmap_external_data/step25/raw"
DATA, OUT, DOCS = STEP / "data", STEP / "outputs", STEP / "docs"
for _d in (DATA, OUT, DOCS):
    _d.mkdir(exist_ok=True)
read_csv, write_csv, sha256, norm, nospace, rnd = S24.read_csv, S24.write_csv, S24.sha256, S24.norm, S24.nospace, S24.rnd
load_json = S24.load_json
TARGET20 = S24.TARGET20


def dump_json(p: Path, o):
    with open(p, "w", encoding="utf-8") as f:
        json.dump(o, f, ensure_ascii=False, indent=2)
        f.write("\n")


# ---------------- 파서 ----------------
def bio_spans(tokens: list[str], tags: list[str], joiner=" ") -> list[tuple[str, str]]:
    """BIO 태그 → (type, text). 'Disease-B'·'B-DS' 두 형식 모두 처리."""
    out, cur, typ = [], [], None
    for tok, tag in zip(tokens, tags):
        if "-" in tag:
            a, b = tag.split("-", 1)
            pos, t = (a, b) if a in ("B", "I") else (b, a)
        else:
            pos, t = "O", None
        if pos == "B" or (pos == "I" and t != typ):
            if cur:
                out.append((typ, joiner.join(cur)))
            cur, typ = [tok], t
        elif pos == "I":
            cur.append(tok)
        else:
            if cur:
                out.append((typ, joiner.join(cur)))
            cur, typ = [], None
    if cur:
        out.append((typ, joiner.join(cur)))
    return out


def load_kbmc() -> list[dict]:
    rows = []
    with open(RAW / "kbmc/KBMC.tsv", encoding="utf-8") as f:
        r = csv.reader(f, delimiter="\t")
        next(r)
        for i, (sent, tags) in enumerate(r):
            toks, tg = sent.split(), tags.split()
            rows.append({"id": f"KBMC_{i:05d}", "text": sent, "tokens": toks, "tags": tg, "aligned": len(toks) == len(tg),
                         "spans": bio_spans(toks, tg) if len(toks) == len(tg) else []})
    return rows


def load_bert_ner_ko() -> list[dict]:
    """CoNLL(토큰, 문자마스크, 태그). shuffle1 의 train+eval = 전체 1 분할. 같은 문장 중복은 dedupe 단계에서 집계."""
    rows = []
    for split in ("train", "eval"):
        sent = []
        lines = (RAW / f"bert_ner_ko/{split}_diagnosis_shuffle1.txt").read_text(encoding="utf-8").splitlines() + [""]
        for ln in lines:
            p = ln.split()
            if not p:
                if sent:
                    toks, tags = [x[0] for x in sent], [x[-1] for x in sent]
                    rows.append({"id": f"NERKO_{split}_{len(rows):05d}", "split": split, "text": " ".join(toks), "tokens": toks, "tags": tags,
                                 "aligned": True, "spans": bio_spans(toks, tags)})
                sent = []
            elif p[0] != "-DOCSTART-":
                sent.append(p)
    return rows


def load_ko_medical_chat() -> list[dict]:
    data = json.load(open(RAW / "ko_medical_chat/medical_conversation_HealthCareMagic.json", encoding="utf-8"))
    rows = []
    for d in data:
        cl = [t["value"] for t in d.get("conversations", []) if t.get("from") == "client"]
        rows.append({"id": f"KMC_{d['id']:05d}", "client_turns": cl, "n_turns": len(d.get("conversations", []))})
    return rows


PII = {"phone": re.compile(r"01[016789][- .]?\d{3,4}[- .]?\d{4}"), "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
       "rrn": re.compile(r"\d{6}[- ]?[1-4]\d{6}"), "url": re.compile(r"https?://|www\.")}


def pii_counts(texts) -> dict:
    return {k: sum(bool(p.search(t)) for t in texts) for k, p in PII.items()}


NEG_CUE = re.compile(r"(없|않|안 |못 |아니)")
