"""캐시 생성(HPO·SNOMED·UMLS 파싱). 원본 읽기만."""
import time
import common as c
for name, fn in [("hpo", c.load_hpo), ("snomed", c.load_snomed), ("umls", c.load_umls)]:
    t = time.time(); d = fn(); print(name, "ok", round(time.time() - t, 1), "s", flush=True)
