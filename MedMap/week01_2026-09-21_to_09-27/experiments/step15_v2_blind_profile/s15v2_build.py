"""Assemble registry + facts -> validate every row -> write 00/01 CSVs. Fails hard on any schema/quote error."""
import sys, pathlib, pandas as pd
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from s15v2_schema import Fact, validate, COLUMNS, DISEASES
from s15v2_registry import registry_rows
import s15v2_facts_part1 as P1, s15v2_facts_part2 as P2
from dataclasses import asdict

OUT = pathlib.Path("exp/step15_v2_blind_profile")
reg_rows = registry_rows()
registry = {r["source_id"]: r for r in reg_rows}
facts = P1.FACTS + P2.FACTS
# assign ids
counters = {}
for f in facts:
    k = DISEASES.index(f.disease)+1
    counters[k] = counters.get(k,0)+1
    f.fact_id = f"D{k:02d}_F{counters[k]:03d}"
    if not f.frequency_raw and f.frequency: f.frequency_raw = f.frequency
# validate
errors = []
for f in facts:
    for e in validate(f, registry): errors.append((f.fact_id, f.disease, e))
# duplicates: same disease+concept+relation+source
seen = {}
for f in facts:
    key = (f.disease, f.base_concept.lower(), f.relation, f.source_id)
    if key in seen: errors.append((f.fact_id, f.disease, f"DUPLICATE of {seen[key]}"))
    seen[key] = f.fact_id
# single-source-only diseases
if errors:
    for e in errors: print("ERROR", *e)
    print(f"{len(errors)} errors"); sys.exit(1)
df = pd.DataFrame([asdict(f) for f in facts], columns=COLUMNS)
assert set(df.disease) == set(DISEASES), "not all 10 diseases present"
assert (df.source_id != "").all() and (df.source_quote_short != "").all()
df.to_csv(OUT/"01_disease_profile_facts.csv", index=False)
pd.DataFrame(reg_rows).to_csv(OUT/"00_source_registry.csv", index=False)
# re-read and re-validate column alignment
chk = pd.read_csv(OUT/"01_disease_profile_facts.csv", dtype=str, keep_default_na=False)
assert list(chk.columns) == COLUMNS and len(chk) == len(df)
for _, r in chk.iterrows():
    f = Fact(**{c: (r[c]=="True") if c in ("review_needed","source_limitation") else r[c] for c in COLUMNS})
    assert not validate(f, registry), (r["fact_id"], validate(f, registry))
print("OK facts", len(df), "sources_ok", sum(r["status"]=="OK" for r in reg_rows), "blocked", sum(r["status"]!="OK" for r in reg_rows))
print(df.groupby("disease").size().to_string())
