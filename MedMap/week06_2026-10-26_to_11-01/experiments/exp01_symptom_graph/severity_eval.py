"""평가 전용: DDXPlus 질환 지식표의 severity 로 중증(≤2) 17질환 집합을 만든다. 탐색기·우도 모듈은 이 파일을 import 하지 않는다.

1차 출처: Fansi Tchango et al., NeurIPS 2022 D&B (arXiv 2205.09148) §3.1, 부록 I.1 — "The lower the more severe."
"""
from __future__ import annotations

import hashlib
import json

CONDITIONS_PATH = "/home/<user>/medmap/data/ddxplus/en/release_conditions.json"
CONDITIONS_SHA256 = "56edf4682d8e86a4209fc3a33932e50ce03d1cc1fecc326c26d5ef8fa5c24890"
SEVERE_17 = frozenset({
    "Anaphylaxis", "Larygospasm", "Ebola", "Possible NSTEMI / STEMI", "Acute pulmonary edema",
    "Spontaneous pneumothorax", "Boerhaave", "Epiglottitis", "Guillain-Barré syndrome", "Croup", "PSVT",
    "Scombroid food poisoning", "Myocarditis", "Acute dystonic reactions", "Unstable angina", "Stable angina",
    "Pulmonary embolism"})


def load_severe(path=CONDITIONS_PATH, expected_sha=CONDITIONS_SHA256) -> frozenset:
    raw = open(path, "rb").read()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise RuntimeError("EXP01_CONDITIONS_SHA_MISMATCH")
    cond = json.loads(raw)
    severe = frozenset(v["cond-name-eng"] for v in cond.values() if int(v["severity"]) <= 2)
    if severe != SEVERE_17:
        raise RuntimeError("EXP01_SEVERE_LIST_MISMATCH")
    return severe


def condition_edges(path=CONDITIONS_PATH, expected_sha=CONDITIONS_SHA256) -> set:
    """평가 전용 graph_stats: 생성기 지식표의 (질환 이름, 근거 id) — symptoms ∪ antecedents."""
    raw = open(path, "rb").read()
    if hashlib.sha256(raw).hexdigest() != expected_sha:
        raise RuntimeError("EXP01_CONDITIONS_SHA_MISMATCH")
    out = set()
    for v in json.loads(raw).values():
        for e in list(v.get("symptoms", {})) + list(v.get("antecedents", {})):
            out.add((v["cond-name-eng"], e))
    return out
