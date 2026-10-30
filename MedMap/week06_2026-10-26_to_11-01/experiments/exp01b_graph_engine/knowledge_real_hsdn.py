"""실제 의료 관계(REAL 등급): HSDN 증상–질환 문헌 공출현 관계만 사용.

출처: Zhou X, Menche J, Barabási A-L, Sharma A. Human symptoms–disease network. Nat Commun 5:4212 (2014),
      Supplementary Data 3(로컬 ~/medmap/data/hsdn, MeSH ID 부여본 processed/hsdn_edges_mesh.parquet, 읽기 전용).
의미: '문헌에서 함께 언급됨'(SUGGESTS = 연관). P(증상|질환)이 아니며 확률로 쓰지 않는다(HSDN README 사용 제한).
HSDN 에 없는 것: 검사·위험인자·AND/OR 진단 규칙·반박(ARGUES_AGAINST)·근거 의존 관계 → 이 그래프에 만들지 않는다.

선택 규칙(코드 상수, 의학적 검증된 기준이 아니라 소규모 구현용 사전 고정값):
  질환 5 = 흉통·호흡곤란 감별에서 겹치는 DDXPlus 대응 질환, 증상 8, 간선 포함 = PubMed 공출현 ≥ MIN_COOC.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from graph_engine import MedGraph

HSDN_PARQUET = Path("/home/<user>/medmap/data/hsdn/processed/hsdn_edges_mesh.parquet")
MIN_COOC = 10
DISEASES = {  # MeSH 용어 → (노드 id, 한국어 표시명)
    "Pulmonary Embolism": ("D:PE", "폐색전증"),
    "Pneumonia": ("D:PNEUMONIA", "폐렴"),
    "Pericarditis": ("D:PERICARDITIS", "심낭염"),
    "Myocardial Infarction": ("D:MI", "심근경색"),
    "Pneumothorax": ("D:PNEUMOTHORAX", "기흉"),
}
SYMPTOMS = {
    "Chest Pain": ("S:CHEST_PAIN", "흉통"),
    "Dyspnea": ("S:DYSPNEA", "호흡곤란"),
    "Cough": ("S:COUGH", "기침"),
    "Fever": ("S:FEVER", "발열"),
    "Hemoptysis": ("S:HEMOPTYSIS", "객혈"),
    "Syncope": ("S:SYNCOPE", "실신"),
    "Respiratory Sounds": ("S:RESP_SOUNDS", "호흡음 이상"),
    "Edema": ("S:EDEMA", "부종"),
}


def file_sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build_hsdn_graph(path: Path = HSDN_PARQUET) -> tuple[MedGraph, dict]:
    df = pd.read_parquet(path)
    sel = df[df["disease_mesh_term"].isin(list(DISEASES)) & df["symptom_mesh_term"].isin(list(SYMPTOMS))]
    g = MedGraph("REAL_HSDN_v1")
    src_node = "HSDN Nat Commun 2014;5:4212 (MeSH 용어)"
    for term, (nid, ko) in DISEASES.items():
        g.add_node(nid, "DISEASE", ko, "REAL", f"{src_node}: {term}")
    for term, (nid, ko) in SYMPTOMS.items():
        g.add_node(nid, "SYMPTOM", ko, "REAL", f"{src_node}: {term}")
    kept = dropped = 0
    for row in sel.itertuples(index=False):
        if row.pubmed_cooccurrence < MIN_COOC:
            dropped += 1
            continue
        g.add_edge(SYMPTOMS[row.symptom_mesh_term][0], "SUGGESTS", DISEASES[row.disease_mesh_term][0], "REAL",
                   f"HSDN Supp Data 3: '{row.symptom_mesh_term}'–'{row.disease_mesh_term}' "
                   f"PubMed co-occurrence={int(row.pubmed_cooccurrence)}, TF-IDF={row.tfidf_score:.2f}")
        kept += 1
    meta = {"source_file": str(path), "source_sha256": file_sha(path), "min_cooccurrence": MIN_COOC,
            "candidate_pairs": int(len(sel)), "edges_kept": kept, "edges_dropped_below_min": dropped,
            "not_available_in_source": ["TEST", "RISK_FACTOR", "AND/OR rule", "ARGUES_AGAINST", "DEPENDS_ON"]}
    return g, meta
