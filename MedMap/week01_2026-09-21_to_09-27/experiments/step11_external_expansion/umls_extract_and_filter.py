"""UMLS 2026AA full zip → MRREL/MRSTY/MRSAB만 추출(전체 해제 금지) + 49질환 CUI·evidence CUI 주변 MRREL 스트리밍 필터"""
import zipfile, hashlib, os, io, time, collections, pandas as pd
zp = "/mnt/c/Users/<user>/Desktop/umls-2026AA-metathesaurus-full.zip"; OUT = "data/umls/2026AA/relations"; O = "exp/step11_external_expansion"
t0 = time.time(); log = lambda *a: print(f"[{time.time()-t0:6.0f}s]", *a, flush=True)
zf = zipfile.ZipFile(zp)
for s in ["MRSAB.RRF", "MRSTY.RRF", "MRREL.RRF"]:
    m = f"2026AA/META/{s}"
    with zf.open(m) as src, open(f"{OUT}/{s}", "wb") as dst:
        for chunk in iter(lambda: src.read(1 << 24), b""): dst.write(chunk)
    log("extracted", s, os.path.getsize(f"{OUT}/{s}"))
with open(f"{OUT}/SHA256SUMS.txt", "w") as f:
    for s in ["MRSAB.RRF", "MRSTY.RRF", "MRREL.RRF"]:
        h = hashlib.sha256()
        with open(f"{OUT}/{s}", "rb") as g:
            for c in iter(lambda: g.read(1 << 24), b""): h.update(c)
        f.write(f"{h.hexdigest()}  {s}\n")
log("sha done")
dm = pd.read_csv("exp/step9_external_knowledge/01_disease_concept_map.csv", dtype=str).fillna(""); em = pd.read_csv("exp/step8_mapping/evidence_concept_map.csv", dtype=str).fillna("")
dcui = set(dm.umls_cui) - {""}; ecui = (set(em.concept_1_cui) | set(em.concept_2_cui)) - {""}; keep = dcui | ecui; log("disease CUIs", len(dcui), "evidence CUIs", len(ecui))
cols = "CUI1 AUI1 STYPE1 REL CUI2 AUI2 STYPE2 RELA RUI SRUI SAB SL RG DIR SUPPRESS CVF".split()
n = kept = 0; ncol = collections.Counter()
with open(f"{OUT}/MRREL.RRF", encoding="utf-8") as src, open(f"{O}/01a_umls_relations_around_ddx_diseases.csv", "w") as dst:
    dst.write(",".join(cols) + "\n")
    for line in src:
        n += 1; p = line.rstrip("\n").split("|")
        if n <= 1000: ncol[len(p)] += 1
        if p[0] in dcui or p[4] in dcui:
            dst.write(",".join(x.replace(",", ";") for x in p[:16]) + "\n"); kept += 1
        if n % 20_000_000 == 0: log("scanned", n, "kept", kept)
log("MRREL lines", n, "kept around diseases", kept, "column count sample", dict(ncol))
print("DONE")
