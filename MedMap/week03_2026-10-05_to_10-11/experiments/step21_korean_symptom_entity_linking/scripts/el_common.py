"""STEP21 공통: 경로 · label space · 한국어 정규화 · 사전 · gold 로더.

원칙: 결정적(난수 없음). 정규화는 공백·문장부호·의문형 어미·명사형 어미(-ㅁ/-음)만 다룬다(과도한 규칙 금지).
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
DATA = STEP / "data"
OUT = STEP / "outputs"
STEP20 = REPO / "exp/step20_symptom_ontology_audit"
DDX_EVIDENCES = Path.home() / "medmap/data/ddxplus/en/release_evidences.json"
TERMINOLOGY_KO = REPO / "medmap/data/terminology_ko.json"
INITIAL_KO = REPO / "medmap/data/initial_evidence_ko.json"
QLABELS_KO = REPO / "medmap/data/question_labels_ko.json"
OUT.mkdir(exist_ok=True)

# pilot 20 canonical symptom → DDXPlus evidence (STEP20 curation 의 core symptom 만)
PILOT = {
    "pain": ["E_53", "E_14"], "dyspnea": ["E_66", "E_64", "E_67"], "fever": ["E_91"],
    "cough": ["E_201", "E_203", "E_77"], "nausea": ["E_148"], "vomiting": ["E_211", "E_166"],
    "diarrhea": ["E_51"], "dizziness": ["E_76"], "loc": ["E_159"], "palpitations": ["E_155", "E_164"],
    "fatigue": ["E_89", "E_88"], "limb_weakness": ["E_84", "E_176"], "swelling": ["E_151"],
    "hemoptysis": ["E_45"], "hematemesis": ["E_210"], "confusion": ["E_39"], "chills": ["E_94"],
    "sore_throat": ["E_97"], "heartburn": ["E_173"], "decreased_appetite": ["E_32", "E_161"],
}
PILOT_NAMES = {
    "pain": "Pain (site as attribute: chest/head/abdomen …)", "dyspnea": "Dyspnea", "fever": "Fever", "cough": "Cough",
    "nausea": "Nausea", "vomiting": "Vomiting", "diarrhea": "Diarrhea", "dizziness": "Dizziness / lightheadedness",
    "loc": "Loss of consciousness", "palpitations": "Palpitations", "fatigue": "Fatigue",
    "limb_weakness": "Limb weakness", "swelling": "Swelling / edema", "hemoptysis": "Hemoptysis",
    "hematemesis": "Hematemesis", "confusion": "Confusion / disorientation", "chills": "Chills",
    "sore_throat": "Sore throat", "heartburn": "Heartburn", "decreased_appetite": "Decreased appetite",
}
CORE_ROLES = {"SYMPTOM", "SIGN", "COMPOSITE"}
STATUS = {"+": "present", "-": "absent", "h": "historical", "?": "uncertain"}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(1 << 20):
            h.update(b)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter="\t" if path.suffix == ".tsv" else ","))


def write_csv(path: Path, rows: list[dict], fields: list[str] | None = None):
    fields = fields or list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def label_space() -> dict:
    """evidence_id → canonical concept id (pilot id 또는 'EV:E_x'). STEP20 core symptom 87개만."""
    cur = read_csv(STEP20 / "curation/curated_mappings.tsv")
    core = [r for r in cur if r["role"] in CORE_ROLES]
    assert len(core) == 87, len(core)
    ev2c = {}
    for c, evs in PILOT.items():
        for e in evs:
            ev2c[e] = c
    for r in core:
        ev2c.setdefault(r["evidence_id"], "EV:" + r["evidence_id"])
    pilot_evs = {e for evs in PILOT.values() for e in evs}
    assert pilot_evs <= {r["evidence_id"] for r in core}, pilot_evs - {r["evidence_id"] for r in core}
    return {e: c for e, c in ev2c.items() if e in {r["evidence_id"] for r in core}}


# ---------------- 정규화 ----------------
PUNCT = re.compile(r"[^0-9A-Za-z가-힣\s]")
Q_END = re.compile(r"(?:있나요|없나요|인가요|나요|가요|습니까|니까|까요|요)$")


def norm(text: str) -> str:
    t = unicodedata.normalize("NFC", text)
    t = PUNCT.sub(" ", t)
    return re.sub(r"\s+", " ", t).strip()


def nospace(text: str) -> str:
    return norm(text).replace(" ", "")


def _drop_final_m(word: str) -> str:
    """명사형 어미 제거: '…음' → 삭제, 받침 ㅁ → 받침 제거(참→차, 아픔→아프)."""
    if not word:
        return word
    last = word[-1]
    if last == "음" and len(word) > 1:
        return word[:-1]
    code = ord(last) - 0xAC00
    if 0 <= code < 11172 and code % 28 == 16:          # 받침 ㅁ
        return word[:-1] + chr(ord(last) - 16)
    return word


def dict_stem(expr: str) -> str:
    """사전 표현 → 매칭용 기본 stem(공백 없음, 의문형 어미만 제거)."""
    return Q_END.sub("", nospace(expr))


def dict_stems(expr: str) -> list[str]:
    """기본 stem + 명사형 어미(-ㅁ/-음) 제거 변형(2글자 이상일 때만). '기침'처럼 원래 ㅁ 받침인 명사를 지키려고 둘 다 둔다."""
    base = dict_stem(expr)
    alt = _drop_final_m(base)
    return [base] + ([alt] if alt != base and len(alt) >= 2 else [])


def char_ngrams(s: str, n: int = 2) -> set:
    if len(s) < n:
        return {s} if s else set()
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def load_dictionary() -> list[dict]:
    return read_csv(DATA / "dictionary_expressions.csv")


def load_gold() -> list[dict]:
    rows = read_csv(DATA / "pilot_gold.csv")
    for r in rows:
        r["gold_mentions"] = json.loads(r["gold_mentions"])
        r["attributes"] = json.loads(r["attributes"])
    return rows


def patient_concepts(row) -> set:
    return {m["concept"] for m in row["gold_mentions"] if m["subject"] == "patient"}
