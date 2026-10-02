"""UMLS 2026AA full/metathesaurus zip에서 MRREL/MRSTY/MRSAB만 선택 추출(전체 해제 금지) + 49질환 CUI·evidence CUI 주변 관계만 스트리밍 필터.
사용: ~/ai_env/bin/python exp/step11_external_expansion/umls_mrrel_extract.py <zip path>
출력: data/umls/2026AA/relations/{MRSTY.RRF, MRSAB.RRF, MRREL_subset_medmap.RRF}, exp/step11_external_expansion/01_umls_disease_finding_edges.csv, umls_rela_freq.csv"""
import sys, zipfile, hashlib, os, io, collections, pandas as pd
zp = sys.argv[1]; OUT = "data/umls/2026AA/relations"; os.makedirs(OUT, exist_ok=True); O = "exp/step11_external_expansion"
h = hashlib.sha256()
with open(zp, "rb") as f:
    for chunk in iter(lambda: f.read(1 << 24), b""): h.update(chunk)
print("zip", zp, os.path.getsize(zp), "sha256", h.hexdigest())
zf = zipfile.ZipFile(zp); names = zf.namelist(); print("members", len(names)); print([n for n in names if n.endswith(("MRREL.RRF", "MRSTY.RRF", "MRSAB.RRF", "MRCONSO.RRF"))])
def member(suffix): return next(n for n in names if n.endswith(suffix))
for s in ["MRSTY.RRF", "MRSAB.RRF"]:
    with zf.open(member(s)) as src, open(f"{OUT}/{s}", "wb") as dst:
        for chunk in iter(lambda: src.read(1 << 24), b""): dst.write(chunk)
    print("extracted", s, os.path.getsize(f"{OUT}/{s}"))
dm = pd.read_csv("exp/step9_external_knowledge/01_disease_concept_map.csv", dtype=str).fillna(""); em = pd.read_csv("exp/step8_mapping/evidence_concept_map.csv", dtype=str).fillna("")
dcui = set(dm.umls_cui) - {""}; ecui = set(em.concept_1_cui) | set(em.concept_2_cui); ecui -= {""}; keep = dcui | ecui
rela = collections.Counter(); n = 0; kept = 0
with zf.open(member("MRREL.RRF")) as src, open(f"{OUT}/MRREL_subset_medmap.RRF", "w") as dst:
    for line in io.TextIOWrapper(src, encoding="utf-8"):
        n += 1; p = line.split("|")
        if p[0] in keep or p[4] in keep:
            dst.write(line); kept += 1
            if p[0] in dcui or p[4] in dcui: rela[(p[3], p[7], p[10])] += 1
        if n % 20_000_000 == 0: print("scanned", n, "kept", kept, flush=True)
print("MRREL total lines", n, "kept", kept)
pd.DataFrame([{"REL": k[0], "RELA": k[1], "SAB": k[2], "n": v} for k, v in rela.most_common()]).to_csv(f"{O}/umls_rela_freq.csv", index=False)
cols = "CUI1 AUI1 STYPE1 REL RELA CUI2 AUI2 STYPE2 SAB SL SUPPRESS".split()
