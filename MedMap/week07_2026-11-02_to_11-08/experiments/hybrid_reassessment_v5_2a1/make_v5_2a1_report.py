"""v5-2A.1 검증·보고서: 테스트(v5-2A.1·v5-2A·v5-1·v4·v3·v2), 기존 파일 체크섬, git 상태, 레지스트리 → outputs/v5_2a1_validation.json, docs/V5_2A1_REPORT.md.
수치는 결과 파일에서 계산한다. run_v5_2a1.py 실행 후 실행."""
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

H = Path(__file__).resolve().parent
EXP, OUT = H.parent, H / "outputs"
ROOT = EXP.parent
sys.path.insert(0, str(EXP / "hybrid_reassessment_v5_2a"))
from make_v5_2a_report import run_tests  # noqa: E402  (v5-2A 의 테스트 실행 함수 재사용)

SUITES = {"v5_2a1": H, "v5_2a": EXP / "hybrid_reassessment_v5_2a", "v5_1": EXP / "hybrid_reassessment_v5_1", "v4": EXP / "hybrid_reassessment_v4",
          "v3": EXP / "hybrid_reassessment_v3", "v2": EXP / "hybrid_reassessment_v2"}


def checksums():
    base = {}
    for line in (OUT / "v5_2a1_baseline_sha256.txt").read_text().splitlines():
        h, f = line.split(None, 1)
        base[f.strip()] = h
    changed = [f for f, h in base.items() if (ROOT / f).exists() and hashlib.sha256((ROOT / f).read_bytes()).hexdigest() != h]
    return {"files_checked": len(base), "changed": changed, "missing": [f for f in base if not (ROOT / f).exists()]}


def git_state():
    now = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    before = (OUT / "v5_2a1_baseline_git_status.txt").read_text().splitlines()
    return {"before_count": len(before), "now_count": len(now), "added_by_this_work": sorted(set(now) - set(before)), "disappeared": sorted(set(before) - set(now))}


def main():
    tests = {k: run_tests(d) for k, d in SUITES.items()}
    cs, gs = checksums(), git_state()
    cases = json.loads((OUT / "v5_2a1_cases.json").read_text())
    grp = json.loads((OUT / "v5_2a1_grouping.json").read_text())
    gf = json.loads((OUT / "v5_2a1_graph_flat.json").read_text())
    aud = json.loads((OUT / "v5_2a1_legacy_duplicate_audit.json").read_text())
    ev = [(n, x) for n, v in grp.items() for x in v]
    raw_d = sum(1 for _, x in ev for r in x["raw_judgments"] if r["raw_kind"] == "RAW_DIRECTIONAL_JUDGMENT")
    raw_c = sum(1 for _, x in ev for r in x["raw_judgments"] if r["raw_kind"] == "RAW_CRITERION_INPUT")
    gd = [g for _, x in ev for g in x["groups"] if g["group_kind"] == "RAW_DIRECTIONAL_JUDGMENT"]
    gc = [g for _, x in ev for g in x["groups"] if g["group_kind"] == "RAW_CRITERION_INPUT"]
    st_d, st_c = Counter(g["dependency_status"] for g in gd), Counter(g["dependency_status"] for g in gc)
    conf = sum(len(x["conflicts"]) for _, x in ev)
    sup_raw = sum(len(x["superseded_raw_judgments"]) for _, x in ev)
    issues = Counter(i.split("(")[0] for _, x in ev for r in x["raw_judgments"] for i in r["lineage_issues"])
    reg = cases["C20_registry_preserved"]["registry"]
    val = {"tests": tests, "checksums_v1_to_v5_2a": cs, "git": gs, "registry": reg,
           "graph_flat": {k: gf[k] for k in ("evaluations", "identical", "grouping_identical", "declarations_equal_cases")},
           "counts": {"cases": len(grp) + 2, "evaluations": len(ev), "raw_directional": raw_d, "raw_criterion_input": raw_c, "directional_groups": len(gd),
                      "criterion_groups": len(gc), "directional_status": dict(st_d), "criterion_status": dict(st_c), "conflicts": conf,
                      "superseded_raw_preserved": sup_raw, "lineage_issues": dict(issues)},
           "fabricated_judgment": cases["E07_fabricated_judgment"]["result"], "legacy_audit": {k: aud[k] for k in
                                                                                                ("reported_by_v5_2a", "rows_reconstructed", "rows_match_report", "unique_raw_judgments", "unique_same_event_groups", "class_counts")},
           "active_direction_relations_v5_2a1": 0, "clinical_performance": "NOT_EVALUATED"}
    (OUT / "v5_2a1_validation.json").write_text(json.dumps(val, ensure_ascii=False, indent=1), encoding="utf-8")
    ex = next(x for n, v in grp.items() if n == "C01_same_event_three_docs" for x in v)
    ex2 = next(x for n, v in grp.items() if n == "C09_after_correction" for x in v)
    L = ["# MedMap v5-2A.1 보고서 — 검사 사건 단위 근거 그룹화·출처 추적", "",
         "자동 생성(make_v5_2a1_report.py). 수치는 outputs/*.json 에서 계산. 합성 사례 기술 검증이며 임상 성능 NOT_EVALUATED.", "",
         "## 1. 알고리즘", "",
         "v5-2A 비교 결과(무수정) → 원시 사용 수집(레거시 v4 방향 판단 그대로 + 원자 기준 입력) → 증거 ID→기록→명시 선언(사건·파생·완전 중복) 출처 해석"
         "(순환·사건 ID 충돌·부모 누락·뿌리 여러 개는 무효 → DEPENDENCY_UNKNOWN) → 그룹 키(가설·에피소드·사건·소견·관계)가 모두 같을 때만 묶음 → "
         "같은 사건·같은 개념·다른 결과는 충돌 표시(제거 없음) → 정정본 공개 후 이전 판단은 정정 직전 시점 출력으로 SUPERSEDED_EVIDENCE 보존 → 보고 문장.", "",
         "| 모듈 | 역할 |", "|---|---|",
         "| hybrid521/lineage.py | 선언 수집·사건 해석(순환·충돌·부분 출처 검출) |",
         "| hybrid521/grouping.py | 원시 판단 수집, 그룹화, 개수 분리 |",
         "| hybrid521/conflict.py | 동시 충돌, 정정·다단계 정정 |",
         "| hybrid521/comparator.py | v5-2A 결과 연결, 그래프·평면표 공용 규칙 |",
         "| hybrid521/graphs.py / flat.py | PatientGraph52 상속(중복 ID 거부·선언 이력·부분 출처 자리 노드) / 같은 선언 행 |",
         "| hybrid521/report.py | 원시 판단과 그룹 분리 문장 |",
         "| hybrid521/audit.py | v5-2A 레거시 중복 9건 읽기 전용 감사 |", "",
         "## 2. 결과", "",
         f"- 사례 {val['counts']['cases']}개(CASE 01~20 + 경계 E01~E07), 평가 시점 {len(ev)}개",
         f"- 레거시 방향 원시 판단 {raw_d}개 → 그룹 {len(gd)}개, 상태 {dict(sorted(st_d.items()))}",
         f"- 기준 입력 원시 {raw_c}개 → 그룹 {len(gc)}개, 상태 {dict(sorted(st_c.items()))}",
         f"- 동시 충돌 {conf}건(해결하지 않음) · 정정으로 대체된 원시 판단 보존 {sup_raw}개 · 출처 해석 문제 {dict(sorted(issues.items()))}",
         f"- 원본에 없는 판단 주입: {val['fabricated_judgment'][:60]}",
         f"- Graph vs Flat: 전체 {gf['identical']}/{gf['evaluations']} · 그룹 {gf['grouping_identical']}/{gf['evaluations']} · 선언 동일 {gf['declarations_equal_cases']}/{len(grp)}"
         " (공용 규칙 — 구현 일관성일 뿐 의학적 정확도 아님)",
         f"- 레지스트리 {reg['n']}개 {reg['groups']} 활성 {reg['engine_active_true']} · 실행 전후 SHA256 동일 {reg['unchanged']} · 신규 방향 관계 0", "",
         "## 3. v5-2A 레거시 중복 9건 감사", "",
         f"- 보고 {aud['reported_by_v5_2a']}건 = 재구성 {aud['rows_reconstructed']}행(일치 {aud['rows_match_report']}). {aud['count_unit_note']}",
         f"- 고유 원시 판단 {aud['unique_raw_judgments']}개, 같은 사건 그룹 {aud['unique_same_event_groups']}개 {aud['groups']}",
         f"- 분류: {aud['class_counts']} — 근거는 v5-2A 합성 사례에 선언된 메타데이터(실제 EMR 사건 ID 아님)", "",
         "## 4. 테스트·보존", "", "| 묶음 | 실행 | 결과 |", "|---|---|---|"]
    L += [f"| {k} | {v['ran']} | {'OK' if v['ok'] else 'FAIL'} |" for k, v in tests.items()]
    L += ["", f"- 기존 v1~v5-2A 파일 {cs['files_checked']}개 체크섬: 변경 {len(cs['changed'])} · 누락 {len(cs['missing'])}",
          f"- git: 전 {gs['before_count']}줄 → 후 {gs['now_count']}줄, 추가 {gs['added_by_this_work']}, 사라짐 {gs['disappeared']}", "",
          "## 5. 보고서 예시", "", ex["report_markdown"], ex2["report_markdown"], "",
          "## 6. 발견·한계", "",
          "- v5-2A 의 '9건'은 평가 시점별 반복 집계였음(고유 5개).",
          "- v5-2A dependency.group_of 는 첫 부모만 따라가며 순환·사건 ID 충돌을 검출하지 않음. 같은 기록에 사건 ID 를 두 번 선언하면 그래프(첫 간선)와 평면표(마지막 선언)가 다르게 읽을 수 있음"
          " → v5-2A 는 수정하지 않고, v5-2A.1 상속 클래스에서 평면 meta 를 '첫 사건·모든 파생'으로 맞추고 전체 선언은 lineage 에서 검사.",
          "- v5-2A 그래프는 없는 부모 기록을 가리키는 파생 선언에서 KeyError → v5-2A.1 은 MISSING_SOURCE_RECORD 자리 노드로 보존.",
          "- 테스트 작성 오류 1건: 그래프·평면표 평가 수 기대값을 27 로 잘못 계산 → 사례 정의상 24 로 정정(동작 기대값 변경 아님).",
          "- 정정 이전 판단은 '정정 공개 직전 시점'의 레거시 출력으로 재구성(그 시점 다른 기록 영향 포함).",
          "- 실제 EMR 의 사건 ID·파생 관계 가용성은 확인 필요. 그룹 수는 증거 강도·통계적 독립성 아님.",
          "- 레거시 PE 판단 자체의 의학적 타당성은 미검증(LEGACY_V4_UNVALIDATED, 전문의 검토 전).", "",
          "## 7. v5-2B 진입 조건", "",
          "- ACS·MI 방향 관계·허혈 규칙, 심낭염 적용 조건(CRQ-06·07·09·10·11·15) 전문의 검토",
          "- 방향 판단 집계 시 근거 그룹 단위 사용 여부(정책) 결정 — 현재는 표시만",
          "- 실제 자료의 사건 ID 확보 방법 확인", ""]
    (H / "docs" / "V5_2A1_REPORT.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps({k: (v["ran"], v["ok"]) for k, v in tests.items()}), "changed", len(cs["changed"]), "missing", len(cs["missing"]), "git+", gs["added_by_this_work"],
          "git-", gs["disappeared"], val["counts"])


if __name__ == "__main__":
    main()
