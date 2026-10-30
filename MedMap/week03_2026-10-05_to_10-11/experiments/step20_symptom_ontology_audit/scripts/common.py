"""STEP20 공통 로더 — DDXPlus 증상 · HPO · SNOMED CT · UMLS 읽기 전용 파싱.

원본(data/)은 읽기만 한다. 파싱 결과는 .cache/*.pkl 에 저장(재실행 시 재사용, 원본 SHA 가 바뀌면 다시 만든다).
경로: MEDMAP_DATA(기본 ~/medmap/data). 결정적 처리: 정렬된 키·고정 규칙만 사용, 난수 없음.
"""
from __future__ import annotations

import hashlib
import json
import os
import pickle
import re
from collections import defaultdict
from pathlib import Path

DATA = Path(os.environ.get("MEDMAP_DATA", Path.home() / "medmap" / "data"))
STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
OUT = STEP / "outputs"
CACHE = STEP / ".cache"
CURATION = STEP / "curation"

DDX_EVIDENCES = DATA / "ddxplus/en/release_evidences.json"
DDX_CONDITIONS = DATA / "ddxplus/en/release_conditions.json"
HPO_OBO = DATA / "hpo/hp.obo"
HPO_HPOA = DATA / "hpo/phenotype.hpoa"
UMLS_CONSO = DATA / "umls/mrconso_eng.parquet"
UMLS_STY = DATA / "umls/2026AA/relations/MRSTY.RRF"
SCT_ROOT = DATA / "snomed/SnomedCT_InternationalRF2_PRODUCTION_20260901T120000Z/Snapshot"
SCT_CONCEPT = SCT_ROOT / "Terminology/sct2_Concept_Snapshot_INT_20260901.txt"
SCT_DESC = SCT_ROOT / "Terminology/sct2_Description_Snapshot-en_INT_20260901.txt"
SCT_REL = SCT_ROOT / "Terminology/sct2_Relationship_Snapshot_INT_20260901.txt"
SCT_LANG = SCT_ROOT / "Refset/Language/der2_cRefset_LanguageSnapshot-en_INT_20260901.txt"
SCT_ASSOC = SCT_ROOT / "Refset/Content/der2_cRefset_AssociationSnapshot_INT_20260901.txt"
TERMINOLOGY_KO = REPO / "medmap/data/terminology_ko.json"
STEP8 = DATA.parent / "exp/step8_mapping"   # 기존 후보(원본 저장소, 읽기만)

SCT_ISA = "116680003"
SCT_FSN = "900000000000003001"
SCT_US_LANG = "900000000000509007"
SCT_PREFERRED = "900000000000548007"
SCT_CLINICAL_FINDING = "404684003"
SCT_ASSOC_NAMES = {"900000000000527005": "SAME_AS", "900000000000526001": "REPLACED_BY",
                   "900000000000523009": "POSSIBLY_EQUIVALENT_TO", "1186921001": "POSSIBLY_REPLACED_BY",
                   "900000000000528000": "WAS_A", "1186924009": "PARTIALLY_EQUIVALENT_TO",
                   "900000000000530003": "ALTERNATIVE"}

OUT.mkdir(exist_ok=True)
CACHE.mkdir(exist_ok=True)


def sha256(path: Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


def _stamp(paths) -> str:
    # 캐시 무효화 키: 크기+mtime(대용량 원본 전체 해시는 versions 기록 때만 계산)
    return "|".join(f"{p.name}:{p.stat().st_size}:{int(p.stat().st_mtime)}" for p in paths)


def _cached(name: str, sources, build):
    path = CACHE / f"{name}.pkl"
    stamp = _stamp(sources)
    if path.exists():
        with open(path, "rb") as f:
            obj = pickle.load(f)
        if obj.get("_stamp") == stamp:
            return obj["data"]
    data = build()
    with open(path, "wb") as f:
        pickle.dump({"_stamp": stamp, "data": data}, f, protocol=pickle.HIGHEST_PROTOCOL)
    return data


# ---------------- DDXPlus ----------------
def load_evidences() -> dict:
    return json.load(open(DDX_EVIDENCES, encoding="utf-8"))


def load_symptoms() -> dict:
    ev = load_evidences()
    sym = {k: v for k, v in ev.items() if v["is_antecedent"] is False}
    ante = {k: v for k, v in ev.items() if v["is_antecedent"] is True}
    assert len(ev) == 223, f"evidences={len(ev)}"
    assert len(sym) == 110, f"symptoms={len(sym)} (expected 110)"
    assert len(ante) == 113, f"antecedents={len(ante)} (expected 113)"
    return sym


def load_terminology_ko() -> dict:
    return json.load(open(TERMINOLOGY_KO, encoding="utf-8"))


# ---------------- HPO ----------------
def _build_hpo():
    terms, cur = {}, None
    data_version = None
    for line in open(HPO_OBO, encoding="utf-8"):
        line = line.rstrip("\n")
        if line.startswith("data-version:") and data_version is None:
            data_version = line.split(":", 1)[1].strip()
        if line.startswith("["):
            cur = {"syn": [], "is_a": [], "alt_id": [], "consider": [], "replaced_by": [], "obsolete": False,
                   "def": "", "xref": []} if line == "[Term]" else None
            continue
        if cur is None or not line:
            continue
        tag, _, val = line.partition(": ")
        if tag == "id":
            cur["id"] = val
            terms[val] = cur
        elif tag == "name":
            cur["name"] = val
        elif tag == "def":
            m = re.match(r'"(.*)"', val)
            cur["def"] = m.group(1) if m else val
        elif tag == "synonym":
            m = re.match(r'"(.*?)" (\w+)', val)
            if m:
                cur["syn"].append((m.group(1), m.group(2)))
        elif tag == "is_a":
            cur["is_a"].append(val.split(" ! ")[0])
        elif tag == "alt_id":
            cur["alt_id"].append(val)
        elif tag == "is_obsolete" and val == "true":
            cur["obsolete"] = True
        elif tag == "replaced_by":
            cur["replaced_by"].append(val)
        elif tag == "consider":
            cur["consider"].append(val)
        elif tag == "xref":
            cur["xref"].append(val.split(" ")[0])
    alt = {a: t["id"] for t in terms.values() for a in t["alt_id"]}
    return {"terms": terms, "alt": alt, "version": data_version}


def load_hpo():
    return _cached("hpo", [HPO_OBO], _build_hpo)


def hpo_ancestors(hpo, hid: str) -> set:
    seen, stack = set(), [hid]
    while stack:
        for p in hpo["terms"].get(stack.pop(), {}).get("is_a", []):
            if p not in seen:
                seen.add(p)
                stack.append(p)
    return seen


# ---------------- SNOMED CT ----------------
def _build_snomed():
    active = {}
    for line in open(SCT_CONCEPT, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if f[0] == "id":
            continue
        active[f[0]] = f[2] == "1"
    preferred = set()
    for line in open(SCT_LANG, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if f[0] != "id" and f[2] == "1" and f[4] == SCT_US_LANG and f[6] == SCT_PREFERRED:
            preferred.add(f[5])
    fsn, pt, syn = {}, {}, defaultdict(list)
    for line in open(SCT_DESC, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if f[0] == "id" or f[2] != "1":
            continue
        did, cid, typ, term = f[0], f[4], f[6], f[7]
        if typ == SCT_FSN:
            fsn[cid] = term
        elif did in preferred:
            pt[cid] = term
        else:
            syn[cid].append(term)
    parents = defaultdict(list)
    for line in open(SCT_REL, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if f[0] != "id" and f[2] == "1" and f[7] == SCT_ISA:
            parents[f[4]].append(f[5])
    assoc = defaultdict(list)
    for line in open(SCT_ASSOC, encoding="utf-8"):
        f = line.rstrip("\n").split("\t")
        if f[0] != "id" and f[2] == "1":
            assoc[f[5]].append((SCT_ASSOC_NAMES.get(f[4], f[4]), f[6]))
    return {"active": active, "fsn": fsn, "pt": pt, "syn": {k: sorted(v) for k, v in syn.items()},
            "parents": {k: sorted(v) for k, v in parents.items()}, "assoc": dict(assoc)}


def load_snomed():
    return _cached("snomed", [SCT_CONCEPT, SCT_DESC, SCT_REL, SCT_LANG, SCT_ASSOC], _build_snomed)


def sct_ancestors(sct, cid: str) -> set:
    seen, stack = set(), [cid]
    while stack:
        for p in sct["parents"].get(stack.pop(), []):
            if p not in seen:
                seen.add(p)
                stack.append(p)
    return seen


def sct_semantic_tag(sct, cid: str) -> str:
    m = re.search(r"\(([^()]*)\)\s*$", sct["fsn"].get(cid, ""))
    return m.group(1) if m else ""


# ---------------- UMLS ----------------
UMLS_SABS = ("HPO", "SNOMEDCT_US", "MSH", "ICD10CM", "ICD10", "MTH", "NCI", "MEDLINEPLUS", "CHV", "MDR")


def _build_umls():
    import pandas as pd
    df = pd.read_parquet(UMLS_CONSO, columns=["CUI", "ISPREF", "SAB", "TTY", "CODE", "STR", "SUPPRESS"])
    df = df[df["SUPPRESS"] == "N"]
    # CUI 별 대표명: MTH PN 우선, 없으면 ISPREF=Y 첫 행(정렬 고정)
    df = df.sort_values(["CUI", "SAB", "TTY", "CODE", "STR"], kind="mergesort")
    pref = {}
    for cui, s in df[(df["SAB"] == "MTH") & (df["TTY"] == "PN")][["CUI", "STR"]].itertuples(index=False):
        pref.setdefault(cui, s)
    for cui, s in df[df["ISPREF"] == "Y"][["CUI", "STR"]].itertuples(index=False):
        pref.setdefault(cui, s)
    codes = defaultdict(set)
    sub = df[df["SAB"].isin(["HPO", "SNOMEDCT_US", "ICD10CM", "ICD10", "MSH"])]
    for cui, sab, code in sub[["CUI", "SAB", "CODE"]].itertuples(index=False):
        codes[cui].add((sab, code))
    strings = defaultdict(set)   # 정규화 문자열 → CUI (조회용, 주요 SAB 만)
    for cui, s in df[df["SAB"].isin(UMLS_SABS)][["CUI", "STR"]].itertuples(index=False):
        strings[norm(s)].add(cui)
    sty = defaultdict(list)
    with open(UMLS_STY, encoding="utf-8") as f:
        for line in f:
            p = line.split("|")
            sty[p[0]].append((p[1], p[3]))
    return {"pref": pref, "codes": {k: sorted(v) for k, v in codes.items()},
            "strings": {k: sorted(v) for k, v in strings.items()}, "sty": dict(sty)}


def load_umls():
    return _cached("umls", [UMLS_CONSO, UMLS_STY], _build_umls)


def norm(s: str) -> str:
    s = s.lower().replace("’", "'")
    s = re.sub(r"\[.*?\]|\(.*?\)", " ", s)
    s = re.sub(r"[^a-z0-9' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ---------------- 출력 기록 ----------------
def write_csv(df, name: str):
    path = OUT / name
    df.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")
    return path


def file_record(path: Path) -> dict:
    import pandas as pd
    rec = {"file": str(path.relative_to(STEP)), "sha256": sha256(path)}
    if path.suffix == ".csv":
        rec["rows"] = len(pd.read_csv(path, dtype=str, keep_default_na=False))
    return rec


# ---------------- 판정 정의 ----------------
CLASSES = ["EXACT", "ACCEPTABLE_BROADER", "ACCEPTABLE_NARROWER", "PARTIAL", "WRONG", "NO_MATCH", "NOT_APPLICABLE"]
USABLE = {"EXACT", "ACCEPTABLE_BROADER", "ACCEPTABLE_NARROWER"}
RANK = {k: i for i, k in enumerate(CLASSES)}   # 작을수록 좋음(union 은 최솟값)
CURATED_REVIEW = "LLM_REVIEWED(Claude, 2026-10-08) - not clinician-validated"
AUTO_REVIEW = "AUTO_RULE_VS_CURATED"


def load_curation():
    import pandas as pd
    df = pd.read_csv(CURATION / "curated_mappings.tsv", sep="\t", dtype=str, keep_default_na=False)
    assert len(df) == 110 and df["evidence_id"].is_unique, "curation must cover 110 symptoms exactly once"
    assert set(df["evidence_id"]) == set(load_symptoms())
    for col in ("hpo_class", "sct_class"):
        bad = set(df[col]) - set(CLASSES)
        assert not bad, (col, bad)
    bad = set(df["umls_class"]) - set(CLASSES) - {"=SCT", "=HPO"}
    assert not bad, bad
    return df


def split_ids(s: str) -> list:
    return [x.strip() for x in s.split(";") if x.strip()]


def load_step8():
    import pandas as pd
    hpo = pd.read_csv(STEP8 / "evidence_hpo_candidates.csv", dtype=str, keep_default_na=False)
    umls = pd.read_csv(STEP8 / "evidence_umls_candidates.csv", dtype=str, keep_default_na=False)
    cmap = pd.read_csv(STEP8 / "evidence_concept_map.csv", dtype=str, keep_default_na=False)
    return hpo, umls, cmap


def inventory_labels() -> dict:
    import pandas as pd
    inv = pd.read_csv(OUT / "symptom_inventory.csv", dtype=str, keep_default_na=False)
    return {r.evidence_id: (r.label_en, r.label_ko) for r in inv.itertuples()}
