"""v5-2A 검증·보고서 생성: 테스트(v5-2A·v5-1·v4·v3·v2) 실행 결과, 기존 파일 체크섬, git 상태 비교, 레지스트리 보존 → outputs/v5_2a_validation.json, docs/V5_2A_REPORT.md.
보고서의 수치는 모두 결과 파일에서 계산한다(손으로 쓰지 않음). run_v5_2a.py 실행 후에 실행한다."""
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

H = Path(__file__).resolve().parent
EXP = H.parent
ROOT = EXP.parent
OUT = H / "outputs"
PY = sys.executable
SUITES = {"v5_2a": H, "v5_1": EXP / "hybrid_reassessment_v5_1", "v4": EXP / "hybrid_reassessment_v4", "v3": EXP / "hybrid_reassessment_v3",
          "v2": EXP / "hybrid_reassessment_v2"}


def run_tests(d: Path) -> dict:
    p = subprocess.run([PY, "-m", "unittest", "discover", "-s", "tests"], cwd=d, capture_output=True, text=True, timeout=600)
    m = re.search(r"Ran (\d+) tests?", p.stderr)
    return {"ran": int(m.group(1)) if m else None, "ok": p.returncode == 0 and "\nOK" in p.stderr, "tail": p.stderr.strip().splitlines()[-1:]}


def checksums() -> dict:
    base = {}
    for line in (OUT / "v5_2a_baseline_sha256.txt").read_text().splitlines():
        h, f = line.split(None, 1)
        base[f.strip()] = h
    changed, missing = [], []
    for f, h in base.items():
        p = ROOT / f
        if not p.exists():
            missing.append(f)
        elif hashlib.sha256(p.read_bytes()).hexdigest() != h:
            changed.append(f)
    return {"files_checked": len(base), "changed": changed, "missing": missing}


def git_state() -> dict:
    now = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    before = (OUT / "v5_2a_baseline_git_status.txt").read_text().splitlines()
    return {"before_count": len(before), "now_count": len(now), "added_by_this_work": sorted(set(now) - set(before)),
            "disappeared": sorted(set(before) - set(now)), "note": "기존 미커밋·미추적 변경은 그대로 유지(삭제·초기화 없음). 커밋 없음."}


def main():
    tests = {k: run_tests(d) for k, d in SUITES.items()}
    cs, gs = checksums(), git_state()
    cases = json.loads((OUT / "v5_2a_cases.json").read_text())
    comp = json.loads((OUT / "v5_2a_comparison.json").read_text())
    gf = json.loads((OUT / "v5_2a_graph_flat.json").read_text())
    reg = cases["C27_registry_preserved"]["registry"]
    allres = [(n, r["as_of"], r["comparison"]) for n, c in cases.items() if "results" in c for r in c["results"]]
    rows = [x for _, _, g in allres for x in g["condition_evaluations"]]
    res_count = Counter(x["evaluation_result"] for x in rows)
    gap_count = Counter(x["gap"]["category"] for x in rows if x["gap"])
    dep_count = Counter(d["dependency_status"] for _, _, g in allres for d in g["dependency_items"].values())
    unl_count = Counter(u["class"] for _, _, g in allres for u in g["unmapped_and_unevaluated_findings"])
    shared = sum(len(g["shared_findings"]) for _, _, g in allres)
    dups = sum(len(g["duplicate_evidence_groups"]) for _, _, g in allres)
    disc = sum(len(g["value_discrepancies"]) for _, _, g in allres)
    active = sum(g["active_direction_relations_v5_2a"] for _, _, g in allres)
    sup = sum(len(h.get("supporting_evidence_ids", [])) + len(h.get("weakening_evidence_ids", [])) for _, _, g in allres for h in g["hypotheses"])
    mism = sum(len(h.get("v51_consistency_mismatches", [])) for _, _, g in allres for h in g["hypotheses"])
    legacy_dup = [(n, i["evidence_id"], i["duplicate_group_id"]) for n, _, g in allres for h in g["hypotheses"] if h.get("legacy_v4")
                  for i in h["legacy_v4"]["items"] if i.get("duplicate_group_id")]
    val = {"tests": tests, "checksums_v1_to_v5_1_and_v5_0": cs, "git": gs,
           "registry": {k: reg[k] for k in ("n", "groups", "engine_active_true", "sha256", "sha256_before_run", "unchanged")},
           "graph_flat": {"evaluations": gf["evaluations"], "identical": gf["identical"]},
           "counts": {"cases": len([c for c in cases.values() if "results" in c]) + 1, "evaluations": len(allres), "condition_rows": len(rows),
                      "condition_results": dict(res_count), "gap_categories": dict(gap_count), "dependency_status": dict(dep_count),
                      "unlinked_classes": dict(unl_count), "shared_findings": shared, "duplicate_groups": dups, "value_discrepancies": disc,
                      "supporting_or_weakening_ids_v5_2a": sup, "v51_consistency_mismatches": mism},
           "active_direction_relations_v5_2a": active, "clinical_performance": "NOT_EVALUATED",
           "legacy_v4_items_in_duplicate_groups": legacy_dup}
    (OUT / "v5_2a_validation.json").write_text(json.dumps(val, ensure_ascii=False, indent=1), encoding="utf-8")

    t = tests
    L = ["# MedMap v5-2A 보고서 — 다질환 근거 비교 엔진", "", "자동 생성(make_v5_2a_report.py). 수치는 outputs/*.json 에서 계산. 합성 사례 기술 검증이며 임상 성능 NOT_EVALUATED.", "",
         "## 1. 구현 알고리즘", "",
         "환자 기록 → v4/v5-1 추출(개념·수치·ECG) → 가설 등록(출처·의사 확인 분리) → 그래프 순회 또는 평면표 필터로 같은 입력 수집 → "
         "v5-1 기준 사실 함수·eval5/eval_kofn 으로 가설별 조건 평가 → 미확정 이유 분류 → 증거 연결 4단계 → 명시 메타데이터 기반 중복·종속 → 공통·차별·미연결 분류 → 비교 결과·보고서.", "",
         "| 모듈 | 역할 | 재사용 |", "|---|---|---|",
         "| hybrid52/hypotheses.py | 가설 출처·의사 확인·WD 1개/에피소드·자동 생성 금지 | v5-1 MultiHypothesis |",
         "| hybrid52/dependency.py | EXACT_DUPLICATE/DERIVED/DISTINCT/UNKNOWN, 중복 그룹, 같은 사건 값 불일치 | — (신규, 명시 메타데이터만) |",
         "| hybrid52/criteria.py | 가설별 조건 행, 부족 정보 7분류, v5-1 분류와 일치 검사 | v5-1 criterion_facts_*, eval5, eval_kofn, combine_evidence, v1 test_status |",
         "| hybrid52/evidence_linker.py | 연결 4단계, 미연결 소견 분류(A~F) | v3 link_status, v5-1 v5_override |",
         "| hybrid52/comparator.py | 그래프·평면표 공용 비교 | v5-1 evaluate_common |",
         "| hybrid52/graphs.py | PatientGraph5 상속, 메타데이터·검사 종류 노드, 순회 수집, 비교 부분그래프 | v4 PatientGraph(as_of·정정·에피소드), v4 Reasoner(레거시 PE) |",
         "| hybrid52/flat.py | 같은 정보를 행 필터로 수집 | v5-1 rows_of |",
         "| hybrid52/report.py | 한국어 비교 보고서 | — |", "",
         "## 2. 결과 요약", "",
         f"- 사례: CASE 01~28 ({val['counts']['cases']}개, 평가 시점 {val['counts']['evaluations']}개), 조건 행 {val['counts']['condition_rows']}개",
         f"- 조건 결과 분포: {dict(sorted(res_count.items()))}",
         f"- 부족 정보 분류: {dict(sorted(gap_count.items()))}",
         f"- 종속 상태: {dict(sorted(dep_count.items()))} · 중복 그룹 {dups} · 같은 사건 값 불일치 {disc} · 공통 소견 {shared}",
         f"- 미연결·미평가 분류: {dict(sorted(unl_count.items()))}",
         f"- Graph vs Flat: {gf['identical']}/{gf['evaluations']} 동일(공용 평가 함수 — 구현 일관성 확인일 뿐 임상 정확도 아님)",
         f"- v5-1 분류와 기준 상태 불일치: {mism}건 · v5-2A SUPPORT/WEAKEN ID: {sup}건 · 신규 활성 방향 관계: {active}건",
         f"- 레지스트리: 후보 {reg['n']}개, 그룹 {reg['groups']}, 활성 {reg['engine_active_true']}, 실행 전후 SHA256 동일 {reg['unchanged']}", "",
         "## 3. 테스트·보존", "", "| 묶음 | 실행 | 결과 |", "|---|---|---|"]
    L += [f"| {k} | {v['ran']} | {'OK' if v['ok'] else 'FAIL'} |" for k, v in t.items()]
    L += ["", f"- 기존 v1~v5-1(+v5-0) 파일 {cs['files_checked']}개 체크섬: 변경 {len(cs['changed'])} · 누락 {len(cs['missing'])}",
          f"- git 상태: 작업 전 {gs['before_count']}줄 → 후 {gs['now_count']}줄, 이번 작업으로 추가: {gs['added_by_this_work']}, 사라진 줄: {gs['disappeared']}", "",
          "## 4. 발견한 문제", "",
          f"- 레거시 v4 PE 는 같은 CTPA 결과의 반복 서술을 각각 판단함: 중복 그룹에 속한 레거시 항목 {len(legacy_dup)}개(예: {legacy_dup[:3]}). "
          "v4 는 수정하지 않고 v5-2A 에서 duplicate_group_id 로 표시만 함.",
          "- v3 추출은 ECG 기록의 'ECG' 단어 자체를 UNSUPPORTED_TEST_OR_PROCEDURE 로 남김 → UNSUPPORTED_EXTRACTION 으로 분류됨(소견 아님).",
          "- 구현 중 결함: hybrid52/criteria.py 가 v1 모듈을 v4 경로 설정 전에 import 하면 실패(뮤테이션 검사용 별도 실행에서 발견, 정상 실행 경로는 import 순서상 통과하고 있었음) → 패키지 __init__ 에서 v4 graphs 를 먼저 import 하도록 수정.", "",
          "## 5. 비교 보고서 예시(CASE 01)", "", comp["C01_three_hypotheses"][0]["report_markdown"], "",
          "## 6. 한계·미검증", "",
          "- 신규 진단 방향 관계 0 — 가설 간 우열·확률·순위 없음. 임상 성능 NOT_EVALUATED.",
          "- 심낭염(ESC 2025 Table 4)·급성 심근손상(UDMI5 Box 1) 기준은 연구용. CRQ-10·11·15(심낭염), CRQ-06·07·09(MI) 전문의 검토 전.",
          "- ACS·MI 진단 기준(허혈 근거 포함)은 NO_VERIFIED_RULE. PE 는 LEGACY_V4_UNVALIDATED.",
          "- 중복·종속은 명시 메타데이터가 있을 때만 판정. 실제 EMR 의 사건 ID 가용성은 확인 필요.",
          "- 검사 종류→기준 연결표(TEST_FEEDS)는 v5-1 기준 함수 입력 구조를 옮긴 것(의학 관계 아님).",
          "- 추출 범위는 v3·v5-1 사전·정규식 한계 그대로(예: 진단명 외 증상 다수 미추출).", "",
          "## 7. v5-2B 진입 조건", "",
          "- ACS·MI 검증 가능한 방향 관계와 허혈 근거 규칙(전문의 검토)",
          "- 심낭염 기준 적용 조건(CRQ-10·11·15) 확정",
          "- PE 레거시 관계의 위험 조건 해석 재검토 및 반복 서술 중복 계산 정책",
          "- 다질환 비교 결과의 임상 평가 기준 정의", ""]
    (H / "docs" / "V5_2A_REPORT.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps({k: (v["ran"], v["ok"]) for k, v in tests.items()}), "checksum_changed", len(cs["changed"]), "missing", len(cs["missing"]),
          "git_added", gs["added_by_this_work"], "disappeared", gs["disappeared"], "gf", gf["identical"], gf["evaluations"])


if __name__ == "__main__":
    main()
