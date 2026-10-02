"""질환 한국어 표시명 ↔ 로컬 UMLS 한국어 용어(KCD5·MDRKOR) 대조 → boolean 플래그만 기록.

UMLS KCD5/MDRKOR 는 SRL=3(재배포 제한)이다. 이 스크립트는 로컬 MRCONSO 를 메모리에서만 읽고
문자열을 출력·저장하지 않는다. 정본에는 `umls_kor_crosscheck` 한 필드만 쓴다.
  true  = 표시명(ok 는 label_ko, review_needed 는 draft_ko)이 해당 질환 CUI/ICD 의 KOR 문자열과 공백·기호 무시 일치
  false = KOR 후보는 있으나 일치 없음
  null  = KOR 후보 없음
질환 → CUI/ICD 매핑: exp/step9_external_knowledge/01_disease_concept_map.csv (umls_cui, ddxplus_code, icd10).

실행: ~/ai_env/bin/python scripts/crosscheck_umls_kor.py [--mrconso PATH] [--write]
  (--write 없으면 변경 예정 개수만 출력). 실행 후 scripts/export_web_terminology.py 로 파생 파일을 갱신한다.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "medmap" / "data" / "terminology_ko.json"
CONCEPT_MAP = ROOT / "exp" / "step9_external_knowledge" / "01_disease_concept_map.csv"
DEFAULT_MRCONSO = ROOT / "data" / "umls" / "2026AA" / "META" / "MRCONSO.RRF"
KOR_SABS = {"KCD5", "MDRKOR"}


def norm(text: str) -> str:
    return re.sub(r"[\s\-·ㆍ/()\[\],]", "", text)


def load_kor(mrconso: Path):
    by_cui, by_icd = defaultdict(set), defaultdict(set)
    with open(mrconso, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            if "|KOR|" not in line:
                continue
            f = line.split("|")
            if f[1] != "KOR" or f[11] not in KOR_SABS:
                continue
            by_cui[f[0]].add(norm(f[14]))
            if f[11] == "KCD5":
                by_icd[f[13].replace(".", "").upper()].add(norm(f[14]))
    return by_cui, by_icd


def compute(doc: dict, by_cui, by_icd) -> dict:
    rows = {r["ddxplus_disease"]: r for r in csv.DictReader(open(CONCEPT_MAP, encoding="utf-8"))}
    flags = {}
    for name, entry in doc["diseases"].items():
        row = rows.get(name)
        candidates = set()
        if row:
            for cui in filter(None, row["umls_cui"].split(";")):
                candidates |= by_cui.get(cui.strip(), set())
            for code in filter(None, (row["ddxplus_code"] + ";" + row["icd10"]).split(";")):
                candidates |= by_icd.get(code.strip().replace(".", "").upper(), set())
        shown = entry.get("label_ko") or entry.get("draft_ko")
        flags[name] = None if not candidates else norm(shown) in candidates
    return flags


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mrconso", type=Path, default=DEFAULT_MRCONSO)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args(argv)
    if not args.mrconso.exists():
        print(f"MRCONSO not found: {args.mrconso} (로컬 UMLS 필요)", file=sys.stderr)
        return 2
    doc = json.loads(CANONICAL.read_text(encoding="utf-8"))
    flags = compute(doc, *load_kor(args.mrconso))
    changed = [n for n, f in flags.items() if doc["diseases"][n].get("umls_kor_crosscheck") != f]
    counts = {str(v).lower(): sum(1 for f in flags.values() if f is v) for v in (True, False, None)}
    print(f"crosscheck true={counts['true']} false={counts['false']} null={counts['none']} changed={len(changed)}")
    if args.write and changed:
        for name, flag in flags.items():
            doc["diseases"][name]["umls_kor_crosscheck"] = flag
        CANONICAL.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        print("written", CANONICAL.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
