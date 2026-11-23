"""outputs JSON 에서 docs/SAFETY_PATCH_P1.md 생성(수치 손 입력 금지). 기존 문서·결과는 건드리지 않는다."""
import json
from pathlib import Path

H = Path(__file__).parent
R = json.loads((H / "outputs/p1_replay_regression.json").read_text(encoding="utf-8"))
M = json.loads((H / "outputs/mutation_results_p1.json").read_text(encoding="utf-8"))
T = (H / "outputs/p1_regression_tail.txt").read_text(encoding="utf-8").strip().splitlines()


def block(name):
    s = R["sets"][name]
    b, a = s["before"], s["after"]
    rows = [
        ("문장 / 문서", f"{b['n_sentences']} / {b['n_documents']}", f"{a['n_sentences']} / {a['n_documents']}"),
        ("출력 단위", b["n_outputs"], a["n_outputs"]),
        ("방향", b["directions"], a["directions"]),
        ("기권 / 전체 출력", f"{b['n_abstain']}/{b['n_outputs']}", f"{a['n_abstain']}/{a['n_outputs']}"),
        ("개념 찾음 / 주석 언급", f"{b['concept_found']}/{b['concept_mentions_gold']}", f"{a['concept_found']}/{a['concept_mentions_gold']}"),
        ("언급 상태 일치 / 비교한 언급", f"{b['assertion_agree']}/{b['assertion_compared']}", f"{a['assertion_agree']}/{a['assertion_compared']}"),
        ("주석에 없는 개념 연결", b["unsupported_mapping"], a["unsupported_mapping"]),
        ("관계 경로 찾음 / 주석 경로", f"{b['relation_paths_found']}/{b['relation_paths_gold']}", f"{a['relation_paths_found']}/{a['relation_paths_gold']}"),
        ("잘못 적용된 WEAKEN / SUPPORT", f"{len(b['wrong_weaken'])} / {len(b['wrong_support'])}", f"{len(a['wrong_weaken'])} / {len(a['wrong_support'])}"),
        ("출처 완전성(기권 제외 출력)", b["provenance"], a["provenance"]),
        ("임상 단계 판정 출력", b["clinical_phase_outputs"], a["clinical_phase_outputs"]),
    ]
    out = [f"### {name}", "| 항목 | 수정 전 | 수정 후 |", "|---|---|---|"] + [f"| {x} | {y} | {z} |" for x, y, z in rows]
    out += ["", f"바뀐 출력 {len(s['changed_outputs'])}건:", ""]
    for c in s["changed_outputs"]:
        p, q = c["before"], c["after"]
        out.append(f"- {c['id']}번 `{c['surface']}`: {p['assertion']}/{p['direction']}/{p['abstain_reason'] or '-'} → {q['assertion']}/{q['direction']}/{q['abstain_reason'] or '-'}")
    out += ["", "수정 후 남은 언급 상태 불일치: " + str([(e["id"], e["concept"], e["want"], e["got"]) for e in s["after"]["assertion_mismatch"]]), ""]
    return out


L = ["# Hybrid v2 Clinical Context & Assertion Safety Patch (P1)", "",
     "회귀 확인 기록이다. 노출된 문장을 다시 돌린 결과라 독립 평가가 아니고, 임상 정확도가 아니다. 임상 확률·의심 여부는 실행 가정이다.", "",
     "## 범위", "- `hybrid2/`·`knowledge/evidence_relations.json`·`tests/test_pipeline.py`·기존 결과 무수정. 패치는 `hybrid2_p1/`, `knowledge/evidence_relations_p1.json`",
     "- 원본과의 차이: `patches/safety_patch_p1.diff`", "- 2차 결과 재현 시 기준선 일치: " + str(R["baseline_matches_stored_run2"]), "",
     "## 지침 확인(ESC 2019 공식 페이지, 자동 도구로 읽음, 일부 절 잘림 가능)", "- D-dimer 배제 문구의 대상은 의심 PE 진단 알고리즘(Figure 5 제목, §4.4)",
     "- 읽은 범위에서 치료 중·추적·재발 평가의 D-dimer 해석 문구 없음. 그래서 '금지'가 아니라 '적용 범위 밖'으로 처리", "",
     "## 회귀 테스트"] + [f"- {x}" for x in T] + [f"- P1 변이 {M['n']}종, 생존 {M['survived']}", "", "## 수정 전후"] + block("run2_exposed") + block("run1_exposed") + [
     "## 해결하지 않은 문제", "- 검사법·판정 기준이 문장에 없어도 의심 평가 입력이면 WEAKEN 유지(uncertainty 에 표시). 기존 테스트가 이 동작을 요구함",
     "- 진단 맥락 입력이 실행 가정이면 문장 신호 없는 정상 D-dimer 는 WEAKEN 유지",
     "- 같은 범위 문제가 CTPA·관류 관계에 남음: 'Follow-up CTPA showed no PE', 'Perfusion scan was normal at follow-up' → WEAKEN. 범위 밖이라 미수정",
     "- 절 전체에 걸리는 불확실 표현(12번 D-dimer·CTPA), 'previously' 오인(14번), v3b 충돌로 기권하는 음성 판독(7번)",
     "- PE 약어·문서 내 약어 미해결, 약어 풀이의 CTPA 언급 자체는 개념 연결로 남음", "- 재발 평가의 D-dimer 문구 미확인, 혈역학 불안정·입원·임신 조건 미구현"]
(H / "docs/SAFETY_PATCH_P1.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
