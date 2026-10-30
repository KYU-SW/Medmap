"""G12 라이선스·외부 전송 검사. outputs/·preview/·docs/·data/ 파일에서
 (1) UMLS CUI 형식(C+7자리) · semantic type 형식(T+3자리:) · snomed_ids/umls_cuis 열 이름
 (2) STEP28 inventory·STEP28.7 감사표에 있는 SNOMED ID·UMLS CUI 값 그대로의 토큰
 을 찾는다. 그리고 이 단계 scripts 에 네트워크 호출 모듈 import 가 없는지 본다. 출력: outputs/license_scan.json"""
from __future__ import annotations

import re

import s30_common as S

PATTERNS = {"UMLS_CUI": re.compile(r"\bC\d{7}\b"), "SEMANTIC_TYPE": re.compile(r"\bT\d{3}:"), "COLUMN": re.compile(r"snomed_ids|umls_cuis|snomed_only")}
NET = re.compile(r"^\s*(import|from)\s+(requests|urllib|http\.client|httpx|socket|aiohttp|openai|anthropic)\b", re.M)


def restricted_tokens() -> set:
    toks = set()
    for r in S.read_csv(S.S28_DIR / "data/existing_concept_inventory.csv"):
        for k in ("snomed_ids", "umls_cuis"):
            toks |= {x for x in r.get(k, "").split(";") if x}
    return toks


def main():
    toks = restricted_tokens()
    tok_re = re.compile(r"\b(" + "|".join(sorted(map(re.escape, toks), key=len, reverse=True)) + r")\b") if toks else None
    hits = []
    scanned = 0
    for d in (S.OUT, S.PREVIEW, S.DOCS, S.DATA):
        for f in sorted(d.rglob("*")):
            if not f.is_file() or f.suffix not in (".json", ".csv", ".md", ".html", ".txt"):
                continue
            scanned += 1
            txt = f.read_text(encoding="utf-8", errors="ignore")
            for name, p in PATTERNS.items():
                for m in p.finditer(txt):
                    hits.append({"file": str(f.relative_to(S.STEP)), "kind": name, "match": m.group(0)})
            if tok_re:
                for m in tok_re.finditer(txt):
                    hits.append({"file": str(f.relative_to(S.STEP)), "kind": "RESTRICTED_ID_VALUE", "match": m.group(0)})
    net = []
    for f in sorted((S.STEP / "scripts").glob("*.py")):
        for m in NET.finditer(f.read_text(encoding="utf-8")):
            net.append({"file": f.name, "import": m.group(0).strip()})
    res = {"G12": "PASS" if not hits and not net else "FAIL", "files_scanned": scanned, "restricted_tokens_checked": len(toks),
           "hits": hits[:100], "n_hits": len(hits), "network_imports": net,
           "note": "공개 push 없음(commit/push 금지). HPO ID·이름만 사용. 산출물은 LOCAL_ONLY(UMLS/SNOMED 유래 STEP 결과를 참조하므로 공개 저장소 push 금지는 유지)."}
    S.dump_json(S.OUT / "license_scan.json", res)
    print(S.dumps({k: res[k] for k in ("G12", "files_scanned", "n_hits", "network_imports")}))


if __name__ == "__main__":
    main()
