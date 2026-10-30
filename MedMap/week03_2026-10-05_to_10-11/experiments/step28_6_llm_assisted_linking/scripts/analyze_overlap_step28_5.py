"""STEP28.6 사후 탐색 분석(결과를 본 뒤 추가 — 판정·규칙에 미사용).
STEP28.6 이 NEW_ONTOLOGY_CANDIDATE 로 둔 입력 중 STEP28.5 병렬 검색이 한국어 근거로 기존 77 concept(EXISTING_*)에 연결한 것을 센다
= 영어 경로만으로는 '77 안에 이미 있는 한국어 용어'를 신규로 오인할 수 있는 중복 위험.
출력: outputs/new_vs_step28_5_existing.csv
"""
import collections

import s286_common as S


def main():
    comp = S.read_csv(S.OUT / "comparison_step28_5.csv")
    rows = [r for r in comp if r["step28_6_final"].startswith("NEW_ONTOLOGY_CANDIDATE") and "EXISTING" in r["step28_5_category"]]
    S.wcsv(S.OUT / "new_vs_step28_5_existing.csv", rows, list(comp[0]))
    print(len(rows), dict(collections.Counter((r["step28_6_final"].split(":", 1)[1], r["step28_5_concept"]) for r in rows)))


if __name__ == "__main__":
    main()
