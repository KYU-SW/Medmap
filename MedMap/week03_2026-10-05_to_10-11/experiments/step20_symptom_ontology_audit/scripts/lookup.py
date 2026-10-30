"""큐레이션 보조 조회(출력 파일 없음). 사용: python lookup.py "dyspnea" "shortness of breath" ...
HPO(name/synonym) · SNOMED(active, 설명어) · UMLS(주요 SAB 문자열) 에서 정규화 완전일치 + 부분일치 상위를 보여준다.
판정은 사람이(이번 단계는 Claude 검토) 내린다 — 이 도구는 후보만 보여준다.
"""
import sys

import common as c

hpo, sct, umls = c.load_hpo(), c.load_snomed(), c.load_umls()
H_IDX = {}
for t in hpo["terms"].values():
    if t.get("obsolete"):
        continue
    for s in [t.get("name", "")] + [x for x, _ in t["syn"]]:
        H_IDX.setdefault(c.norm(s), set()).add(t["id"])
S_IDX = {}
for cid, term in list(sct["pt"].items()) + [(k, s) for k, v in sct["syn"].items() for s in v] + list(sct["fsn"].items()):
    if sct["active"].get(cid):
        S_IDX.setdefault(c.norm(term), set()).add(cid)


def show(q, limit=6):
    n = c.norm(q)
    print(f"\n### {q}  [{n}]")
    hs = sorted(H_IDX.get(n, ()))
    hsub = sorted({h for k, v in H_IDX.items() if n in k.split(" ") or (len(n) > 5 and n in k) for h in v} - set(hs))
    for h in hs + hsub[:limit]:
        t = hpo["terms"][h]
        print(f"  HPO {'=' if h in hs else '~'} {h} {t['name']} | is_a {','.join(hpo['terms'].get(p, {}).get('name', p) for p in t['is_a'])}")
    ss = sorted(S_IDX.get(n, ()))
    ssub = sorted({x for k, v in S_IDX.items() if len(n) > 5 and n in k for x in v} - set(ss),
                  key=lambda x: len(sct["pt"].get(x, "")))
    for s in ss + ssub[:limit]:
        print(f"  SCT {'=' if s in ss else '~'} {s} {sct['fsn'].get(s)} | parents {','.join(sct['pt'].get(p, p) for p in sct['parents'].get(s, []))}")
    for cui in umls["strings"].get(n, [])[:limit]:
        print(f"  CUI = {cui} {umls['pref'].get(cui)} | {','.join(st for _, st in umls['sty'].get(cui, []))} | {[x for x in umls['codes'].get(cui, []) if x[0] in ('HPO', 'SNOMEDCT_US', 'ICD10CM')][:6]}")


if __name__ == "__main__":
    for q in sys.argv[1:]:
        show(q)
