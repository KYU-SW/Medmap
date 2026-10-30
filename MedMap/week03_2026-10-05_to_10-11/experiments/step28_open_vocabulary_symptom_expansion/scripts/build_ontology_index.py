"""STEP28 경량 ontology 색인(SQLite, LOCAL_ONLY_LICENSED). 원본은 스트리밍으로 1회 읽기만 한다.

내용:
 concept   : HPO 전체 term(이름·정의·is_a·obsolete·replaced_by·phenotype 여부) + SNOMED 'Clinical finding'(404684003) 하위 활성 concept
             (FSN·semantic tag·정의·is_a). kind = HPO 'phenotype'/'other' · SNOMED semantic tag(finding/disorder …)
 sct_status: SNOMED 전체 concept 활성 여부(비활성 concept 판정용)
 term      : 정규화 영어 문자열 → concept/CUI(HPO 이름·동의어, SNOMED 활성 description, UMLS ENG 문자열 중 아래 CUI 의 허용 SAB)
 xref      : UMLS CUI ↔ (HPO code, SNOMEDCT_US code). HPO term 또는 SNOMED Clinical finding 하위 code 가 있는 CUI 만 유지(증상 검색 범위)
 sty       : 위 CUI 의 semantic type(MRSTY)
 kor_term  : UMLS KOR 중 SRL 0 출처(LNC-KO-KR 검사명 · TKMT 약재명)만. MDRKOR·KCD5(SRL 3)는 읽지 않는다(행 수만 센다)
 meta      : 빌드 시각·원본 크기·행 수·소요 시간
UMLS MRREL(6.4 GB)은 읽지 않는다: 계층은 HPO is_a·SNOMED is_a 원본을 쓰고, CUI 는 같은 개념 묶음(xref)으로만 쓴다.
출력: index/ontology_index.sqlite · outputs/index_build.json
"""
import collections
import re
import sqlite3
import time

import s28_common as S

FSN, IS_A = "900000000000003001", "116680003"


def tnorm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_hpo():
    terms, cur = {}, None
    for ln in S.HPO_OBO.open(encoding="utf-8"):
        ln = ln.rstrip("\n")
        if ln == "[Term]":
            cur = {"syn": [], "is_a": [], "obsolete": False, "replaced_by": "", "def": "", "alt": []}
            continue
        if ln.startswith("[") and ln.endswith("]"):
            cur = None
            continue
        if cur is None or ": " not in ln:
            continue
        k, v = ln.split(": ", 1)
        if k == "id":
            cur["id"] = v
            terms[v] = cur
        elif k == "name":
            cur["name"] = v
        elif k == "def":
            cur["def"] = v.split('"')[1] if '"' in v else v
        elif k == "synonym":
            cur["syn"].append((v.split('"')[1], v.split('"')[2].split()[0] if len(v.split('"')) > 2 and v.split('"')[2].split() else ""))
        elif k == "is_a":
            cur["is_a"].append(v.split(" ! ")[0])
        elif k == "is_obsolete" and v == "true":
            cur["obsolete"] = True
        elif k == "replaced_by":
            cur["replaced_by"] = v
        elif k == "alt_id":
            cur["alt"].append(v)
    kids = collections.defaultdict(list)
    for t in terms.values():
        for p in t["is_a"]:
            kids[p].append(t["id"])
    pheno, st = set(), [S.HPO_PHENO_ROOT]
    while st:
        x = st.pop()
        if x in pheno:
            continue
        pheno.add(x)
        st.extend(kids[x])
    return terms, pheno


def tsv(path):
    with path.open(encoding="utf-8") as f:
        next(f)
        for ln in f:
            yield ln.rstrip("\n").split("\t")


def main():
    t0 = time.time()
    db_path = S.INDEX / "ontology_index.sqlite"
    if db_path.exists():
        db_path.unlink()
    db = sqlite3.connect(db_path)
    db.executescript("""
    CREATE TABLE concept(cid TEXT PRIMARY KEY, source TEXT, name TEXT, definition TEXT, active INT, kind TEXT, parents TEXT, replaced_by TEXT);
    CREATE TABLE sct_status(sctid TEXT PRIMARY KEY, active INT);
    CREATE TABLE term(term_norm TEXT, term TEXT, cid TEXT, ttype TEXT);
    CREATE TABLE xref(cui TEXT, sab TEXT, code TEXT);
    CREATE TABLE sty(cui TEXT, tui TEXT, sty TEXT);
    CREATE TABLE kor_term(term TEXT, cui TEXT, sab TEXT, tty TEXT);
    CREATE TABLE hpo_alt(alt TEXT, cid TEXT);
    CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT);
    """)
    meta = {}
    # HPO
    t = time.time()
    terms, pheno = parse_hpo()
    db.executemany("INSERT INTO concept VALUES(?,?,?,?,?,?,?,?)",
                   [(x["id"], "HPO", x.get("name", ""), x["def"], 0 if x["obsolete"] else 1, "phenotype" if x["id"] in pheno else "other",
                     ";".join(x["is_a"]), x["replaced_by"]) for x in terms.values()])
    rows = []
    for x in terms.values():
        rows.append((tnorm(x.get("name", "")), x.get("name", ""), x["id"], "HPO:name"))
        rows += [(tnorm(s), s, x["id"], f"HPO:syn:{ty}") for s, ty in x["syn"]]
    db.executemany("INSERT INTO term VALUES(?,?,?,?)", rows)
    db.executemany("INSERT INTO hpo_alt VALUES(?,?)", [(a, x["id"]) for x in terms.values() for a in x["alt"]])
    meta["hpo"] = {"terms": len(terms), "phenotype_subtree": len(pheno), "obsolete": sum(x["obsolete"] for x in terms.values()),
                   "term_rows": len(rows), "seconds": round(time.time() - t, 1)}
    # SNOMED
    t = time.time()
    status = {f[0]: int(f[2]) for f in tsv(S.SCT_DIR / "sct2_Concept_Snapshot_INT_20260901.txt")}
    db.executemany("INSERT INTO sct_status VALUES(?,?)", status.items())
    parents, kids = collections.defaultdict(list), collections.defaultdict(list)
    for f in tsv(S.SCT_DIR / "sct2_Relationship_Snapshot_INT_20260901.txt"):
        if f[2] == "1" and f[7] == IS_A:
            parents[f[4]].append(f[5])
            kids[f[5]].append(f[4])
    finding, st = set(), [S.SCT_FINDING_ROOT]
    while st:
        x = st.pop()
        if x in finding:
            continue
        finding.add(x)
        st.extend(kids[x])
    fsn, desc = {}, collections.defaultdict(list)
    for f in tsv(S.SCT_DIR / "sct2_Description_Snapshot-en_INT_20260901.txt"):
        if f[2] == "1" and f[4] in finding:
            if f[6] == FSN:
                fsn[f[4]] = f[7]
            desc[f[4]].append(f[7])
    defs = {}
    for f in tsv(S.SCT_DIR / "sct2_TextDefinition_Snapshot-en_INT_20260901.txt"):
        if f[2] == "1" and f[4] in finding:
            defs[f[4]] = f[7]
    crow, trow = [], []
    for c in finding:
        name = fsn.get(c, "")
        tag = re.search(r"\(([^()]+)\)$", name)
        crow.append((f"SCTID:{c}", "SNOMED", re.sub(r"\s*\([^()]+\)$", "", name), defs.get(c, ""), status.get(c, 0), tag.group(1) if tag else "",
                     ";".join(f"SCTID:{p}" for p in parents[c]), ""))
        trow += [(tnorm(d), d, f"SCTID:{c}", "SCT:desc") for d in desc[c]]
    db.executemany("INSERT INTO concept VALUES(?,?,?,?,?,?,?,?)", crow)
    db.executemany("INSERT INTO term VALUES(?,?,?,?)", trow)
    meta["snomed"] = {"concepts_all": len(status), "active_all": sum(status.values()), "clinical_finding_subtree": len(finding),
                      "with_definition": len(defs), "term_rows": len(trow), "seconds": round(time.time() - t, 1)}
    # UMLS (CUI 순 정렬 파일 — CUI 블록 단위로 판단)
    t = time.time()
    kor_skipped = collections.Counter()
    xrow, srow, krow, keep = [], [], [], set()
    block, cur_cui = [], None

    def flush(b):
        codes = [(f[11], f[13]) for f in b if (f[11] == "HPO" and f[13] in terms) or (f[11] == "SNOMEDCT_US" and f[13] in finding)]
        if not codes:
            return
        cui = b[0][0]
        keep.add(cui)
        xrow.extend((cui, sab, code) for sab, code in set(codes))
        srow.extend((tnorm(f[14]), f[14], f"CUI:{cui}", f"UMLS:{f[11]}:{f[12]}") for f in b if f[1] == "ENG" and f[11] in S.UMLS_EN_SABS)
    n = 0
    with S.UMLS_CONSO.open(encoding="utf-8") as fh:
        for ln in fh:
            n += 1
            f = ln.split("|")
            if f[1] == "KOR":
                if f[11] in S.SRL_ALLOWED_KOR:
                    krow.append((f[14], f[0], f[11], f[12]))
                else:
                    kor_skipped[f[11]] += 1
            if f[0] != cur_cui:
                if block:
                    flush(block)
                block, cur_cui = [], f[0]
            if f[1] == "ENG" and (f[11] in S.UMLS_EN_SABS):
                block.append(f)
        if block:
            flush(block)
    db.executemany("INSERT INTO xref VALUES(?,?,?)", xrow)
    db.executemany("INSERT INTO term VALUES(?,?,?,?)", srow)
    db.executemany("INSERT INTO kor_term VALUES(?,?,?,?)", krow)
    sty = []
    with S.UMLS_STY.open(encoding="utf-8") as fh:
        for ln in fh:
            f = ln.split("|")
            if f[0] in keep:
                sty.append((f[0], f[1], f[3]))
    db.executemany("INSERT INTO sty VALUES(?,?,?)", sty)
    meta["umls"] = {"mrconso_lines": n, "kept_cuis(HPO term or SNOMED clinical finding code)": len(keep), "xref_rows": len(xrow), "eng_term_rows": len(srow),
                    "kor_rows_loaded(SRL0)": len(krow), "kor_rows_not_loaded(SRL>0)": dict(kor_skipped), "sty_rows": len(sty),
                    "seconds": round(time.time() - t, 1)}
    db.executescript("""
    CREATE INDEX i_term ON term(term_norm); CREATE INDEX i_term_cid ON term(cid);
    CREATE INDEX i_x_cui ON xref(cui); CREATE INDEX i_x_code ON xref(code); CREATE INDEX i_sty ON sty(cui); CREATE INDEX i_kor ON kor_term(term);
    """)
    meta["total_seconds"] = round(time.time() - t0, 1)
    db.executemany("INSERT INTO meta VALUES(?,?)", [(k, S.dumps(v)) for k, v in meta.items()])
    db.commit()
    db.execute("VACUUM")
    db.close()
    meta["index_bytes"] = db_path.stat().st_size
    meta["source_bytes"] = {"hp.obo": S.HPO_OBO.stat().st_size, "MRCONSO.RRF": S.UMLS_CONSO.stat().st_size, "MRSTY.RRF": S.UMLS_STY.stat().st_size,
                            "snomed_snapshot_terminology": sum(p.stat().st_size for p in S.SCT_DIR.glob("*.txt"))}
    meta["license"] = "LOCAL_ONLY_LICENSED: UMLS(UTS)·SNOMED 문자열 포함 — 공개 저장소·외부 전송 금지"
    S.dump_json(S.OUT / "index_build.json", meta)
    print(S.dumps(meta))


if __name__ == "__main__":
    main()
