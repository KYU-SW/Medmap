"""MRCONSO.RRF 해제 + ENG 행만 parquet, SNOMED Snapshot만 해제 (Full/Delta 제외)"""
import zipfile, time, pandas as pd
t0=time.time()
zipfile.ZipFile("data/umls/umls-2026AA-mrconso.zip").extract("2026AA/META/MRCONSO.RRF", "data/umls"); print("mrconso extracted", round(time.time()-t0)); 
cols="CUI LAT TS LUI STT SUI ISPREF AUI SAUI SCUI SDUI SAB TTY CODE STR SRL SUPPRESS CVF".split()
chunks=[]
for ch in pd.read_csv("data/umls/2026AA/META/MRCONSO.RRF", sep="|", header=None, names=cols+["_"], usecols=["CUI","LAT","ISPREF","SAB","TTY","CODE","STR","SUPPRESS"], dtype=str, chunksize=1_000_000, quoting=3, na_filter=False):
    chunks.append(ch[ch["LAT"]=="ENG"].drop(columns="LAT"))
df=pd.concat(chunks); df.to_parquet("data/umls/mrconso_eng.parquet", index=False)
print("eng rows", len(df), "CUIs", df["CUI"].nunique(), "SAB top", df["SAB"].value_counts().head(8).to_dict(), round(time.time()-t0))
zf=zipfile.ZipFile("data/snomed/SnomedCT_InternationalRF2_PRODUCTION_20260901T120000Z.zip")
snap=[n for n in zf.namelist() if "/Snapshot/" in n]; zf.extractall("data/snomed", members=snap); print("snomed snapshot files", len(snap), round(time.time()-t0)); print("DONE")
