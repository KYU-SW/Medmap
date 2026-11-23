"""v5-2A.2 검증·보고서: 테스트(v5-2A.2·v5-2A.1·v5-2A·v5-1·v4·v3·v2), 기존 파일 체크섬, git 상태 → outputs/v5_2a2_validation.json, docs/V5_2A2_REPORT.md.
수치는 결과 파일에서 계산한다. run_v5_2a2.py 실행 후 실행."""
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
from make_v5_2a_report import run_tests  # noqa: E402

SUITES = {"v5_2a2": H, "v5_2a1": EXP / "hybrid_reassessment_v5_2a1", "v5_2a": EXP / "hybrid_reassessment_v5_2a", "v5_1": EXP / "hybrid_reassessment_v5_1",
          "v4": EXP / "hybrid_reassessment_v4", "v3": EXP / "hybrid_reassessment_v3", "v2": EXP / "hybrid_reassessment_v2"}


def checksums():
    base = {}
    for line in (OUT / "v5_2a2_baseline_sha256.txt").read_text().splitlines():
        h, f = line.split(None, 1)
        base[f.strip()] = h
    return {"files_checked": len(base), "changed": [f for f, h in base.items() if (ROOT / f).exists() and hashlib.sha256((ROOT / f).read_bytes()).hexdigest() != h],
            "missing": [f for f in base if not (ROOT / f).exists()]}


def git_state():
    now = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT, capture_output=True, text=True).stdout.splitlines()
    before = (OUT / "v5_2a2_baseline_git_status.txt").read_text().splitlines()
    return {"before_count": len(before), "now_count": len(now), "added_by_this_work": sorted(set(now) - set(before)), "disappeared": sorted(set(before) - set(now))}


def load(n):
    return json.loads((OUT / n).read_text())


def main():
    tests = {k: run_tests(d) for k, d in SUITES.items()}
    cs, gs = checksums(), git_state()
    cases, ev, ph, cf, gf = (load(f"v5_2a2_{n}.json") for n in ("cases", "event_history", "patient_history", "counterfactual", "graph_flat"))
    versions = [v for c in ev.values() for e in c["events"] for v in e["versions"]]
    vstat = Counter(x["version_status"] for v in versions for x in v["status_timeline"])
    estat = Counter(s["event_state"] for c in ev.values() for e in c["events"] for s in e["state_timeline"])
    unstable = [(n, v["version_id"], j["relation_id"], j["results_over_validity"], j["context_record_ids"]) for n, c in ev.items() for e in c["events"]
                for v in e["versions"] for j in v["direct_judgment_summary"] if not j["stable_within_validity"]]
    unres = Counter(u["status"] for c in ev.values() for u in c["unresolved_event_links"])
    attr = Counter(o["attribution"]["status"] for c in ev.values() for e in c["events"] for v in e["versions"] for o in v["direct_judgment_observations"])
    attr += Counter(o["attribution"]["status"] for c in ev.values() for u in c["unresolved_event_links"] for o in u["judgment_observations"])
    causes = Counter(x["cause"] for c in ph.values() for s in c["snapshots"] if s["diff_from_previous"] for j in s["diff_from_previous"]["judgment_changes"] for x in j["causes"])
    comps = [x for c in cf.values() for x in c["comparisons"]]
    perf = [x for x in comps if x["performed"]]
    c02 = ev["C02_other_result_between"]
    v1 = next(v for e in c02["events"] if e["event_key"] == "CT001@E1" for v in e["versions"] if v["source_record_id"] == "r1")
    j1 = next(j for j in v1["direct_judgment_summary"] if j["relation_id"] == "PE-CTPA-NEGATIVE")
    val = {"tests": tests, "checksums_v1_to_v5_2a1": cs, "git": gs, "registry": cases["C27_registry_preserved"],
           "graph_flat": {k: gf[k] for k in ("cases", "identical", "section_identical")},
           "counts": {"case_functions": len(ev), "unit_checks": 3, "snapshots": sum(len(c["snapshots"]) for c in ph.values()), "events": sum(len(c["events"]) for c in ev.values()),
                      "versions": len(versions), "version_status": dict(vstat), "event_state": dict(estat), "unstable_version_judgments": len(unstable),
                      "unresolved_event_links": dict(unres), "attribution_status": dict(attr), "judgment_change_causes": dict(causes),
                      "counterfactuals": len(comps), "counterfactuals_performed": len(perf), "counterfactual_fixed_context_identical": sum(x["fixed_context_identical"] for x in perf),
                      "counterfactual_with_difference": sum(bool(x["difference"]) for x in perf), "counterfactual_injected": sum(bool(x["injected_versions"]) for x in perf)},
           "reproduction": {"case": "C02_other_result_between", "event_version": v1["version_id"], "first_observed": [j1["first_observed_as_of"], j1["first_observed_result"]],
                            "results_over_validity": j1["results_over_validity"], "context_record_ids": j1["context_record_ids"],
                            "v5_2a1_superseded_groups": [g for g in load("v5_2a2_attribution.json")["C02_other_result_between"]["v5_2a1_superseded_groups"]
                                                         if g["source_record_ids"] == ["r1"]]},
           "active_direction_relations_v5_2a2": 0, "clinical_performance": "NOT_EVALUATED"}
    (OUT / "v5_2a2_validation.json").write_text(json.dumps(val, ensure_ascii=False, indent=1), encoding="utf-8")
    L = ["# MedMap v5-2A.2 보고서 — 검사 사건별 정정 귀속과 시간 일관성", "",
         "자동 생성(make_v5_2a2_report.py). 수치는 outputs/*.json 에서 계산. 합성 사례 기술 검증이며 임상 성능 NOT_EVALUATED.", "",
         "## 1. 재현한 문제(PHASE 1)", "",
         "- 경로: hybrid521/comparator.py `compare521` — 정정된 기록마다 `th = superseded_at - EPS` 로 `_v52(pg, th, mode)` 를 다시 불러 환자 전체 상태로 이전 판단을 재계산.",
         f"- 최소 반례(C02): 사건 버전 {v1['version_id']}(기록 r1)의 공개 시점 판단 {j1['first_observed_as_of']} → {j1['first_observed_result']}, "
         f"유효 구간 안 판단 {j1['results_over_validity']}, 문맥 출처 {j1['context_record_ids']}.",
         f"- v5-2A.1 은 이 버전의 이전 판단을 {[(g['observed_at_as_of'], g['relation_id'], g['directional_result']) for g in val['reproduction']['v5_2a1_superseded_groups']]} "
         "하나로 보고(정정 직전 환자 전체 상태 재계산) → 공개 이후 추가된 문맥 기록(문맥 출처 참조)의 영향이 CT 판독 이력에 섞이고 공개 당시 판단은 사라짐. "
         "같은 구간에 공개된 트로포닌(OBS:t11)은 PE 레거시 판단의 문맥 출처가 아님.", "",
         "## 2. 세 결과 계약", "",
         "| 결과 | 내용 | 표시 |", "|---|---|---|",
         "| EVENT_VERSION_HISTORY | 사건(명시 lineage+supersedes)별 판독 버전, 버전 기록에 직접 귀속되는 원시 판단만, 유효 구간 안 시점별 관측 | 구간 안 판단 변화 시 문맥 출처 표시 |",
         "| PATIENT_AS_OF_HISTORY | 공개 시각마다 v5-2A.1 비교(무수정) 요약, 새 기록·정정 기록·판단 변화와 원인 | 원인: EVENT_VERSION_CHANGED / PATIENT_CONTEXT_CHANGED / ATTRIBUTION_UNRESOLVED |",
         "| CORRECTION_ONLY_COUNTERFACTUAL | 입력 이력 재생, 사건의 한 버전만 남기고 T_ref 에서 같은 평가기 | COUNTERFACTUAL_REPLAY · NOT_HISTORICAL_OBSERVATION · NOT_CAUSAL_PROOF, 고정 문맥 동일성 검사 |", "",
         "## 3. 결과", "",
         f"- 사례 함수 {len(ev)}개 + 단위 검사 3개(C18·C19·C27), 시점 스냅샷 {val['counts']['snapshots']}개, 사건 {val['counts']['events']}개, 버전 {len(versions)}개",
         f"- 버전 상태: {dict(sorted(vstat.items()))} · 사건 상태: {dict(sorted(estat.items()))}",
         f"- 유효 구간 안 판단이 바뀐 버전 판단 {len(unstable)}건: {unstable}",
         f"- 사건 미연결: {dict(unres)} · 귀속 상태: {dict(sorted(attr.items()))}",
         f"- 환자 전체 이력 판단 변화 원인: {dict(sorted(causes.items()))}",
         f"- 가상 비교 {len(comps)}건(수행 {len(perf)}, 고정 문맥 동일 {val['counts']['counterfactual_fixed_context_identical']}, 출력 차이 있음 "
         f"{val['counts']['counterfactual_with_difference']}, 주입 버전 사용 {val['counts']['counterfactual_injected']})",
         f"- Graph vs Flat: {gf['identical']}/{gf['cases']} 전체 동일, 영역별 {gf['section_identical']} (공용 규칙 — 의학적 정확도 아님)",
         f"- 레지스트리 {cases['C27_registry_preserved']['n']}개 활성 {cases['C27_registry_preserved']['engine_active_true']} · 신규 방향 관계 0", "",
         "## 4. 테스트·보존", "", "| 묶음 | 실행 | 결과 |", "|---|---|---|"]
    L += [f"| {k} | {v['ran']} | {'OK' if v['ok'] else 'FAIL'} |" for k, v in tests.items()]
    L += ["", f"- 기존 v1~v5-2A.1 파일 {cs['files_checked']}개 체크섬: 변경 {len(cs['changed'])} · 누락 {len(cs['missing'])}",
          f"- git: 전 {gs['before_count']}줄 → 후 {gs['now_count']}줄, 추가 {gs['added_by_this_work']}, 사라짐 {gs['disappeared']}", "",
          "## 5. 보고서 예시(C02)", "", cases["C02_other_result_between"]["report_markdown"], "",
          "## 6. 발견·한계", "",
          "- [결함·수정] v4 `add_record` 는 없는 기록을 정정 대상으로 받으면 docs·그래프 노드를 먼저 넣은 뒤 KeyError → 그래프에는 남고 평면표에는 없어 결과 불일치(C20 첫 실행에서 발견). "
          "v4 는 수정하지 않고 v5-2A.2 입력 계층에서 상태 변경 전 거부. 회귀 테스트 1개는 발견 후 추가(사전 고정 기대값 아님).",
          "- [표시 수정] 사건 ID 없이 명시 정정만 있는 경우(C13) 판단 소멸은 '원인 미확인', 정정본 판단은 '사건 연결 없는 새 기록(문맥 변화)'으로 엇갈리게 표시되던 것을 "
          "둘 다 ATTRIBUTION_UNRESOLVED(명시 정정 확인·사건 연결 없음)로 통일 — 첫 산출물 검토 중 발견, 테스트 기대값 변경 없음.",
          "- v4 입력 API 로는 supersedes 순환을 만들 수 없음(정정 대상이 먼저 있어야 함) → C19 는 출처 행 단위 검사로만 확인.",
          "- 문맥 출처는 v4 결정 트리가 참조한 사실 키의 출처 기록(키가 없으면 facts_used 전체를 상한으로 사용).",
          "- 가상 비교는 교체 버전에서 파생된 고정 문맥 기록이 있으면 수행하지 않음(문맥 고정 불가).",
          "- T_ref 이후 공개된 버전은 공개 시각을 T_ref 로 당겨 주입 — INJECTED 로 표시.",
          "- 레거시 PE 판단의 의학적 타당성, 검사 전 확률 충돌 처리 규칙(v4)은 미검증.", "",
          "## 7. 다음 단계에 미치는 영향 / v5-2B 진입 조건", "",
          "- 구조 보완은 여기서 종료 가능: 사건 이력·환자 이력·가상 비교가 분리돼, 의학 관계 검토 결과를 넣어도 정정·문맥 영향이 섞이지 않음.",
          "- 남은 핵심은 의학 내용: PE 레거시 관계의 적용 조건(검사 전 확률 충돌 시 처리 등), ACS·MI 방향 관계와 허혈 근거 규칙, 심낭염 적용 조건 — 전문의 검토(CRQ-06·07·09·10·11·15).",
          "- 방향 판단 집계를 근거 그룹 단위로 할지, 문맥 의존 판단을 어떻게 보고할지 정책 결정 필요.", ""]
    (H / "docs" / "V5_2A2_REPORT.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps({k: (v["ran"], v["ok"]) for k, v in tests.items()}), "changed", len(cs["changed"]), "missing", len(cs["missing"]), "git+", gs["added_by_this_work"],
          "git-", gs["disappeared"], val["counts"])


if __name__ == "__main__":
    main()
