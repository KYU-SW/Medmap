"""실제 의료 지식 그래프(REAL): HSDN + DisMech + HPO 계층. 지식원별 관계 의미를 섞지 않고 간선 출처·근거 등급으로 구분한다.

지식원(전부 로컬 사본, 이번 회차 새 다운로드 없음)
  - HPO hp.obo(data-version 2026-09-01): 소견 개념·IS_A 계층·UMLS 교차참조. phenotype.hpoa(2026-09-02)는 희귀질환 주석 —
    선택 질환에는 해당 주석 없음(NOT 주석 포함 0건) → 질환–소견 간선으로 쓰지 않음.
  - DisMech(monarch-initiative/dismech commit eaa5fe99, BSD-3-Clause): AI 큐레이션 질환 항목. phenotypes(HP ID, 빈도 등급, PMID 근거),
    environmental(위험 노출), diagnosis(검사 이름), differential_diagnoses(감별 이름). 검증된 진단 규칙이 아님 → 규칙(AND/OR)으로 승격하지 않음.
  - HSDN(Nat Commun 2014;5:4212 Supp Data 3): 문헌 공출현(연관, 확률 아님).
관계 의미
  - DisMech phenotype → SUGGESTS(evidence_class = DISMECH_AI_CURATED_PMID / DISMECH_AI_CURATED_NO_REF)
  - HSDN 공출현 → SUGGESTS(evidence_class = HSDN_LITERATURE_COOCCURRENCE)
  - DisMech environmental → RISK_FACTOR_FOR, diagnosis → EVALUATES, differential(이름이 선택 질환과 정확히 같을 때만) → DIFFERENTIAL_OF
  - HPO is_a → IS_A(하위 → 상위)
  - 반박(ARGUES_AGAINST)·AND/OR 규칙·근거 의존: 실제 출처 없음 → 만들지 않음. DisMech EXCLUDED 빈도는 기록만(간선 없음).
질환 동일성: DDXPlus 질환 → UMLS CUI(STEP9 01_disease_concept_map.csv) = HSDN disease_cui(ID 일치) /
  DisMech disease_term MONDO 라벨 = STEP9 umls_name(대소문자 무시 완전 일치). MONDO↔UMLS 교차참조 파일은 로컬에 없음 → 상태 LABEL_EXACT_NO_XREF.
"""
from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path

import pandas as pd
import yaml

from graph_engine import MedGraph

DATA = Path("/home/<user>/medmap/data")
HP_OBO = DATA / "hpo/hp.obo"
HPOA = DATA / "hpo/phenotype.hpoa"
HSDN = DATA / "hsdn/processed/hsdn_edges_mesh.parquet"
DISMECH_DIR = DATA / "dismech/raw/dismech/kb/disorders"
DISMECH_COMMIT = "eaa5fe99bd0289e737d65646456d928b1f973282"
MRCONSO = DATA / "umls/mrconso_eng.parquet"     # UMLS 2026AA(로컬 라이선스 사용, 문자열은 출력하지 않음 — CUI·HP 코드만)
REF_CACHE = DATA / "dismech/raw/dismech/references_cache"   # DisMech 저장소의 PubMed 초록 캐시(로컬)
STEP9_MAP = Path("/home/<user>/medmap/exp/step9_external_knowledge/01_disease_concept_map.csv")
MIN_COOC = 10                                    # HSDN 기존 값 유지(33회차 고정)

# 선택 질환(DDXPlus 이름 → DisMech 파일, 한국어 표시). 선택 근거 = disease_link_audit() 에서 HSDN ID 일치 + DisMech 라벨 일치.
SELECTED = {
    "Pulmonary embolism": ("Pulmonary_Embolism.yaml", "폐색전증"),
    "Pericarditis": ("Pericarditis.yaml", "심낭염"),
    "Myocarditis": ("Myocarditis.yaml", "심근염"),
    "Tuberculosis": ("Tuberculosis.yaml", "결핵"),
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def disease_node_id(ddx_name: str) -> str:
    return f"DX:{ddx_name}"


# ───────────── HPO ─────────────

def load_hpo(path: Path = HP_OBO) -> dict:
    """id → {name, is_a[], umls[], obsolete}. data-version 은 '_meta'."""
    terms, cur, meta = {}, None, {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("data-version:"):
            meta["data_version"] = line.split(":", 1)[1].strip()
        if line == "[Term]":
            cur = {"is_a": [], "umls": [], "obsolete": False}
            continue
        if line.startswith("[") and line != "[Term]":
            cur = None
            continue
        if cur is None or ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        if k == "id":
            terms[v] = cur
        elif k == "name":
            cur["name"] = v
        elif k == "is_a":
            cur["is_a"].append(v.split(" ! ")[0].strip())
        elif k == "xref" and v.startswith("UMLS:"):
            cur["umls"].append(v.split()[0][5:])
        elif k == "is_obsolete" and v == "true":
            cur["obsolete"] = True
    terms["_meta"] = meta
    return terms


def hpo_ancestors(hpo: dict, hp: str) -> dict:
    """조상 id → 경로(hp, …, 조상). 최단 경로 하나."""
    out, frontier = {}, [(hp, (hp,))]
    while frontier:
        nxt = []
        for t, path in frontier:
            for p in hpo.get(t, {}).get("is_a", []):
                if p not in out:
                    out[p] = path + (p,)
                    nxt.append((p, path + (p,)))
        frontier = nxt
    return out


def load_cui2hp() -> dict:
    """UMLS MRCONSO SAB=HPO(SUPPRESS=N): CUI → HP 코드 목록. 이 HPO 판 hp.obo 에는 UMLS 교차참조가 없어 UMLS 쪽 매핑을 쓴다."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq
    t = pq.read_table(MRCONSO, columns=["CUI", "SAB", "CODE", "SUPPRESS"],
                      filters=[("SAB", "=", "HPO")])
    t = t.filter(pc.equal(t.column("SUPPRESS"), pa.scalar("N")))
    out: dict = {}
    for c, code in zip(t.column("CUI").to_pylist(), t.column("CODE").to_pylist()):
        if code.startswith("HP:") and code not in out.get(c, []):
            out.setdefault(c, []).append(code)
    return out


# ───────────── 질환 동일성 감사 ─────────────

def _dismech_disease_term(f: Path):
    """최상위 disease_term 블록의 term.id·label 만 줄 단위로 읽는다(전체 YAML 파싱 대신). 없으면 None."""
    inside, tid, lab = False, None, None
    with open(f, encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("disease_term:"):
                inside = True
                continue
            if inside:
                if line and not line[0].isspace():
                    break
                s = line.strip()
                if s.startswith("id:") and tid is None:
                    tid = s[3:].strip().strip('"')
                elif s.startswith("label:") and lab is None:
                    lab = s[6:].strip().strip('"')
            if tid and lab:
                break
    return (tid, lab) if tid and lab else None


def disease_link_audit() -> list:
    """DDXPlus 49 질환 → HSDN(CUI 일치) · DisMech(MONDO 라벨 = UMLS 이름) 연결 상태. 이름 유사만으로는 연결하지 않는다."""
    hs = pd.read_parquet(HSDN, columns=["disease_mesh_term", "disease_mesh_id", "disease_cui"]).drop_duplicates()
    dm = {}
    for f in sorted(DISMECH_DIR.glob("*.yaml")):
        lab = _dismech_disease_term(f)
        if lab:
            dm.setdefault(lab[1].strip().lower(), []).append((f.name, lab[0]))
    rows = []
    with open(STEP9_MAP, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            cui = r["umls_cui"]
            h = hs[hs.disease_cui == cui]
            dmm = dm.get(r["umls_name"].strip().lower(), []) if r["umls_name"] else []
            rows.append({
                "ddxplus_disease": r["ddxplus_disease"], "umls_cui": cui, "umls_name": r["umls_name"],
                "hsdn_status": "EXACT_CUI" if len(h) else "NONE",
                "hsdn_mesh": ";".join(sorted(set(h.disease_mesh_id))) if len(h) else "",
                "dismech_status": "LABEL_EXACT_NO_XREF" if len(dmm) == 1 else ("AMBIGUOUS" if dmm else "NONE"),
                "dismech_file": dmm[0][0] if len(dmm) == 1 else "",
                "dismech_mondo": dmm[0][1] if len(dmm) == 1 else "",
            })
    return rows


# ───────────── 그래프 ─────────────

def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9%.,;:()\-+/ ]", "", re.sub(r"\s+", " ", t.lower())).strip()


def verify_quote(e: dict) -> str:
    """DisMech 근거 1건의 인용문(snippet)이 캐시된 PubMed 초록에 그대로 있는지. 내용의 임상적 타당성 검증이 아니다.
    → FOUND / NOT_FOUND / NO_CACHE / NO_SNIPPET / NO_PMID"""
    ref = str(e.get("reference", ""))
    if not ref.startswith("PMID:"):
        return "NO_PMID"
    if not e.get("snippet"):
        return "NO_SNIPPET"
    f = REF_CACHE / f"PMID_{ref[5:]}.md"
    if not f.exists():
        return "NO_CACHE"
    body = _norm(f.read_text(encoding="utf-8"))
    parts = [_norm(x) for x in re.split(r"\.\.\.|…", str(e["snippet"])) if len(_norm(x)) >= 12]
    return "FOUND" if parts and all(x in body for x in parts) else "NOT_FOUND"


def evidence_class(ev: list) -> tuple[str, dict]:
    """간선 근거 등급(개수가 아니라 확인 수준): SUPPORT 근거 중 인용문이 초록에 있는 것이 하나라도 있으면
    DISMECH_QUOTE_IN_ABSTRACT, PMID 는 있으나 인용 미확인이면 DISMECH_PMID_QUOTE_UNVERIFIED, PMID 없으면 DISMECH_NO_REF."""
    checks = [(str(e.get("supports")), verify_quote(e)) for e in ev]
    cnt: dict = {}
    for sup, q in checks:
        cnt[f"{sup}:{q}"] = cnt.get(f"{sup}:{q}", 0) + 1
    if any(sup == "SUPPORT" and q == "FOUND" for sup, q in checks):
        return "DISMECH_QUOTE_IN_ABSTRACT", cnt
    if any(q != "NO_PMID" for _, q in checks):
        return "DISMECH_PMID_QUOTE_UNVERIFIED", cnt
    return "DISMECH_NO_REF", cnt


def _ev_summary(ev: list) -> tuple:
    pm = sorted({e.get("reference") for e in ev if str(e.get("reference", "")).startswith("PMID:")})
    sup = [e.get("supports") for e in ev]
    return pm, {k: sup.count(k) for k in sorted({str(s) for s in sup})}


def build_real_graph(extra_hp_nodes=(), discriminators: bool = False) -> tuple[MedGraph, dict]:
    """extra_hp_nodes: 환자 근거가 매핑되는 HP id(어댑터 제공) — 질환 간선이 없어도 노드로 두어 '그래프 밖'과 '연결 지식 없음'을 구분."""
    hpo = load_hpo()
    g = MedGraph("REAL_KG_v1(HSDN+DisMech+HPO)")
    hpo_src = f"HPO hp.obo {hpo['_meta'].get('data_version', '?')}"
    audit = {r["ddxplus_disease"]: r for r in disease_link_audit()}
    meta = {"sources": {
        "hp.obo": {"path": str(HP_OBO), "sha256": sha(HP_OBO), "data_version": hpo["_meta"].get("data_version"),
                   "license": "HPO 라이선스(hpo.jax.org 이용 조건, 출처 표기)"},
        "phenotype.hpoa": {"path": str(HPOA), "sha256": sha(HPOA), "version_line": HPOA.read_text(encoding="utf-8").splitlines()[1].strip()},
        "dismech": {"path": str(DISMECH_DIR), "commit": DISMECH_COMMIT, "license": "BSD-3-Clause"},
        "umls_mrconso_hpo": {"path": str(MRCONSO), "use": "HSDN 증상 CUI → HP 코드(SAB=HPO, SUPPRESS=N, 유일할 때만)",
                             "license": "UMLS 라이선스 — 로컬 사용만, 문자열 비출력·비배포"},
        "hsdn": {"path": str(HSDN), "sha256": sha(HSDN), "min_cooccurrence": MIN_COOC,
                 "license": "RESEARCH_USE_CHECK_REQUIRED(data/hsdn/README)"}},
        "diseases": {}, "edges": [], "excluded_annotations": [], "excluded_self_concept": [], "hpoa_rows_for_selected": 0,
        "relation_roles_absent": {"DIAGNOSTIC_RULE": "실제 출처 없음 — 0", "ARGUES_AGAINST": "실제 출처 없음 — 0"}}

    def add_hp(hp, kind="FINDING"):
        if hp not in hpo or hpo[hp].get("obsolete"):
            return False
        g.add_node(hp, kind, hpo[hp].get("name", hp), "REAL", hpo_src)
        return True

    def edge(src, rel, dst, source, **spec):
        g.add_edge(src, rel, dst, "REAL", source, **spec)
        meta["edges"].append({"src": src, "rel": rel, "dst": dst, "evidence_class": spec.get("evidence_class", ""),
                              "role": spec.get("role", ""), "source": source})

    hs = pd.read_parquet(HSDN)
    hpoa = pd.read_csv(HPOA, sep="\t", comment="#", header=None, dtype=str)
    cui2hp = load_cui2hp()
    for ddx, (fname, ko) in SELECTED.items():
        a = audit[ddx]
        assert a["hsdn_status"] == "EXACT_CUI" and a["dismech_status"] == "LABEL_EXACT_NO_XREF" and a["dismech_file"] == fname, a
        did = disease_node_id(ddx)
        g.add_node(did, "DISEASE", f"{ko}({ddx})", "REAL",
                   f"DDXPlus 질환명 · UMLS {a['umls_cui']} · MeSH {a['hsdn_mesh']} · DisMech {a['dismech_mondo']}(라벨 일치, 교차참조 미확인)",
                   cui=a["umls_cui"], mesh=a["hsdn_mesh"], mondo=a["dismech_mondo"])
        d = yaml.safe_load((DISMECH_DIR / fname).read_text(encoding="utf-8"))
        meta["diseases"][did] = {"ddxplus": ddx, "ko": ko, **{k: a[k] for k in ("umls_cui", "hsdn_mesh", "dismech_mondo")},
                                 "dismech_file": fname, "dismech_creation_date": d.get("creation_date")}
        # DisMech phenotypes(같은 HP 가 여러 번 나오면 근거를 합쳐 간선 1개)
        merged = {}
        for p in d.get("phenotypes") or []:
            t = ((p.get("phenotype_term") or {}).get("term") or {})
            hp = t.get("id")
            if not hp:
                continue
            if p.get("frequency") == "EXCLUDED":
                meta["excluded_annotations"].append({"disease": did, "hp": hp, "name": p.get("name")})
                continue
            m = merged.setdefault(hp, {"names": [], "freq": set(), "ev": []})
            m["names"].append(p.get("name"))
            m["freq"].add(str(p.get("frequency")))
            m["ev"] += p.get("evidence") or []
        self_hp = set(cui2hp.get(a["umls_cui"], []))       # 질환 자체를 뜻하는 HPO 용어(같은 CUI)
        for hp, m in merged.items():
            if hp in self_hp or hpo.get(hp, {}).get("name", "").lower() == ddx.lower():
                meta["excluded_self_concept"].append({"disease": did, "hp": hp, "name": hpo.get(hp, {}).get("name"),
                                                      "reason": "질환 자체 개념을 소견으로 쓰지 않음(증상·질환 혼동)"})
                continue
            if not add_hp(hp):
                continue
            pm, sup = _ev_summary(m["ev"])
            cls, qc = evidence_class(m["ev"])
            edge(hp, "SUGGESTS", did, f"DisMech {DISMECH_COMMIT[:8]} {fname} phenotypes['{'/'.join(m['names'])}'] "
                 f"freq={'/'.join(sorted(m['freq']))} supports={sup} refs={','.join(pm) or '없음'} quote_check={qc} "
                 f"(AI 큐레이션 — 인용 일치는 내용 검증 아님)", evidence_class=cls, role="CLINICAL_FINDING")
        for i, e in enumerate(d.get("environmental") or []):
            t = ((e.get("exposure_term") or {}).get("term") or {})
            rid = f"RF:{t['id']}" if t.get("id") else f"RF:{fname[:-5]}:{i}"
            g.add_node(rid, "RISK_FACTOR", e["name"] + (f" ({t.get('label')})" if t.get("label") else ""), "REAL",
                       f"DisMech {DISMECH_COMMIT[:8]} {fname} environmental")
            pm, sup = _ev_summary(e.get("evidence") or [])
            cls, qc = evidence_class(e.get("evidence") or [])
            edge(rid, "RISK_FACTOR_FOR", did, f"DisMech {DISMECH_COMMIT[:8]} {fname} environmental['{e['name']}'] "
                 f"supports={sup} refs={','.join(pm) or '없음'} quote_check={qc} (AI 큐레이션, 효과 크기 미사용)",
                 evidence_class=cls, role="RISK_FACTOR")
        for i, x in enumerate(d.get("diagnosis") or []):
            tid = f"TEST:{fname[:-5]}:{i}"
            g.add_node(tid, "TEST", x["name"], "REAL", f"DisMech {DISMECH_COMMIT[:8]} {fname} diagnosis")
            edge(tid, "EVALUATES", did, f"DisMech {DISMECH_COMMIT[:8]} {fname} diagnosis['{x['name']}']",
                 evidence_class="DISMECH_AI_CURATED", role="TEST_INFORMATION")
        meta["diseases"][did]["dismech_differentials"] = [x["name"] for x in d.get("differential_diagnoses") or []]
        # HSDN(CUI 일치 질환, 증상 CUI → HPO UMLS 교차참조가 하나일 때만)
        h = hs[(hs.disease_cui == a["umls_cui"]) & (hs.pubmed_cooccurrence >= MIN_COOC)]
        for r in h.itertuples(index=False):
            hps = cui2hp.get(r.symptom_cui, [])
            if len(hps) != 1:
                meta.setdefault("hsdn_unmapped", []).append({"symptom": r.symptom_mesh_term, "cui": r.symptom_cui,
                                                              "hp_candidates": hps})
                continue
            if not add_hp(hps[0]):
                continue
            edge(hps[0], "SUGGESTS", did, f"HSDN Supp Data 3: '{r.symptom_mesh_term}'–'{r.disease_mesh_term}' "
                 f"PubMed co-occurrence={int(r.pubmed_cooccurrence)}, TF-IDF={r.tfidf_score:.2f} (문헌 공출현, 확률 아님)",
                 evidence_class="HSDN_LITERATURE_COOCCURRENCE", role="LITERATURE_COOCCURRENCE")
        meta["hpoa_rows_for_selected"] += int(hpoa[hpoa[1].str.lower() == ddx.lower()].shape[0])
    # 감별 관계: 이름이 선택 질환의 DDXPlus 이름과 정확히 같을 때만
    names = {k.lower(): disease_node_id(k) for k in SELECTED}
    for did, info in meta["diseases"].items():
        for x in info["dismech_differentials"]:
            if x.strip().lower() in names and names[x.strip().lower()] != did:
                edge(did, "DIFFERENTIAL_OF", names[x.strip().lower()],
                     f"DisMech {DISMECH_COMMIT[:8]} {info['dismech_file']} differential_diagnoses['{x}'] (이름 일치)",
                     evidence_class="DISMECH_AI_CURATED", role="DIFFERENTIAL")
    for hp in extra_hp_nodes:
        add_hp(hp)
    if discriminators:                                    # 38회차 판별 근거(knowledge_discriminators), 기본 꺼짐
        from knowledge_discriminators import add_discriminators
        add_discriminators(g, meta)
    # HPO IS_A: 그래프 안 HP 노드끼리 하위 → 상위(조상) 직접 간선, 경로는 출처에 기록
    hp_nodes = [n for n in g.nodes if n.startswith("HP:")]
    hp_set = set(hp_nodes)
    for n in hp_nodes:
        for anc, path in hpo_ancestors(hpo, n).items():
            if anc in hp_set:
                edge(n, "IS_A", anc, f"{hpo_src} is_a: " + " > ".join(f"{p}({hpo[p].get('name', '')})" for p in path),
                     evidence_class="HPO_ONTOLOGY", role="ONTOLOGY_HIERARCHY")
    counts = {}
    for e in meta["edges"]:
        counts[(e["rel"], e["evidence_class"])] = counts.get((e["rel"], e["evidence_class"]), 0) + 1
    meta["counts"] = {"nodes_by_kind": {k: sum(1 for v in g.nodes.values() if v.kind == k)
                                        for k in sorted({v.kind for v in g.nodes.values()})},
                      "edges_by_rel_class": {f"{r}|{c}": n for (r, c), n in sorted(counts.items())}}
    meta["disease_link_audit"] = list(audit.values())
    return g, meta
