"""outputs JSON 에서 docs/V4_REPORT.md 생성(수치 손 입력 금지)."""
import json
from pathlib import Path

H = Path(__file__).parent
J = lambda n: json.loads((H / f"outputs/{n}").read_text(encoding="utf-8"))  # noqa: E731
C, T, D, K, TR = J("v4_cases.json"), J("v4_tests.json"), J("v4_v3_diff.json"), J("v4_preservation.json"), J("v4_trees.json")
L = ["# MedMap v4 — Patient Evidence Graph & Conditional Clinical Reasoning(PE)", "",
     "A 기능 구현 완료 / B 기술 검증 완료(합성 사례) / C 임상 성능 NOT_EVALUATED.", "",
     "## 구성", "- `hybrid4/logic.py`: 4값 AND/OR/NOT, P2 카탈로그 → EXCLUSION GATE·REQUIRED·ALTERNATIVE·FALLBACK 분리, decide",
     "- `hybrid4/graphs.py`: 정규화 관계 원본(그래프·평면표 공용), 질환 그래프 A, 환자 증거그래프 B(에피소드·기록·증거·사실·검사 사건·정정·AI 후보)",
     "- `hybrid4/reason.py`: A·B 연결 추론, 공용 평가 함수 evaluate_one, 근거 종합(합산 없음), 미설명 소견 상태, 재검토 트리",
     "- `hybrid4/flat.py`: 평면 규칙표 기준선(같은 관계·연관·질환 범위·평가 함수·출력)", "",
     "## 우선순위 처리", "- EXCLUSION GATE(카탈로그의 방향 규칙 앞 비방향 규칙): TRUE → 그 결과, UNKNOWN/CONFLICT → 방향 판단 보류(HOLD)",
     "- v3 덧층 혈역학 불안정 제외는 카탈로그 필수 조건이 아니라 BLOCK_ONLY_IF_TRUE(명시된 경우만 차단, 부족 정보로 세지 않음) — 전문가 검토 필요",
     "- REQUIRED(방향 경로 공통) AND, ALTERNATIVE(경로별) OR. 카탈로그의 OR 관계: " + str(T["E_and_or_same_structure"]["or_relations"]),
     "- FALLBACK(방향 규칙 뒤 비방향 규칙): 방향 경로가 TRUE 가 아닐 때만", "- 값이 모두 확정된 조합에서 P2 apply 와 v4 decide 결과 동일(테스트 CatalogConversion)", "",
     "## 보존"] + [f"- {k}: {v}" for k, v in K.items()] + ["", "## TEST A 검증 관계 비활성화"]
for k, v in T.items():
    if k.startswith("A_"):
        L.append(f"- {k}: 바뀐 출력 {v['n_changed']}, 모두 해당 관계 의존 {v['all_changed_depend_on_relation']}")
L += ["", f"## TEST B 환자 증거 제거: 사라진 항목 {T['B_remove_ultrasound_record']['removed']}, 다른 항목 변화 {T['B_remove_ultrasound_record']['changed_other']}",
      "", "## TEST C 에피소드 변경"] + [f"- {k}: {v}" for k, v in T["C_episode_relink"].items()] + [
      "", "## TEST D·E 그래프 vs 평면 규칙표", f"- 판단 항목 {T['D_graph_vs_flat']['items']}, 방향 일치 {T['D_graph_vs_flat']['direction_agree']}, 항목 키 동일 {T['D_graph_vs_flat']['all_keys_equal']}, 조건 추적·출처·부족 정보 동일 {T['D_graph_vs_flat']['all_decision_traces_equal']}",
      f"- 조건 구조 동일: {T['E_and_or_same_structure']['structures_identical']}",
      "- 공정성 조정(개발 중 발견): 처음엔 평면표에 기존 그래프의 표시용 연관·질환 범위가 없어 보류 사유 라벨 6건이 달랐음 → 같은 목록을 평면표에도 제공 후 완전 일치",
      f"- 실행 시간(전체 사례 1회, 5회 평균): 그래프 {T['cost']['graph_sec_per_full_run']}s, 평면 {T['cost']['flat_sec_per_full_run']}s", f"- 코드 줄 수: {T['cost']['loc']}",
      f"- 관계 수정 지점: {T['cost']['relation_edit_points']}", "",
      f"## TEST F 출처 추적: {T['F_provenance']}", "", "## v3 대비 출력 차이(같은 사례)", f"- 차이 {D['n_diff']}건, 원인 {D['by_reason']}"]
L += [f"  - {r['case']} {r['episode']} {r['doc']} `{r['surface']}` v3 {r['v3']} → v4 {r['v4']} : {r['why']}" for r in D["rows"]]
L += ["", "## 사례 요약(그래프 모드)"]
for c, v in C.items():
    for st in v["states"]:
        for h in st["graph"]["hypotheses"]:
            dirs = [f"{i['source_record_id']}:{i['relation_id'] or i['hold_reason']}={i['direction']}" for i in h["items"] if i["relation_id"] or i["direction"] != "ABSTAIN"]
            L.append(f"- {c}@{st['as_of']} {h['hyp_id']}({h['episode_id']}, 사용 {h['usable']}): {dirs or '방향 관련 항목 없음'}" + (f" / 미해결 연결 {[x['source_record_id'] for x in h['unresolved_episode_evidence']]}" if h["unresolved_episode_evidence"] else ""))
t = TR["C03_multiple_evidence@5.0"][0]
L += ["", "## 재검토 트리 예(C03, 섹션 요약)", "```", json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in t.items() if k not in ("pending_tests",)}, ensure_ascii=False),
      json.dumps({k: t["weakening"][0][k] for k in ("evidence_id", "sentence", "relation_id", "graph_path", "direction", "available_time")}, ensure_ascii=False),
      json.dumps(t["weakening"][0]["condition_trace"]["required"], ensure_ascii=False), "```", "",
      "## 그래프의 실제 기여와 한계", "- 판단·조건 추적·출처: 같은 지식을 준 평면 규칙표와 완전히 같음. 의학적 판단 이점 없음",
      "- 그래프에서만 자연스럽게 된 것: 증거→원본 기록→정정 기록 간선 순회, 에피소드→기록·증거·사실 순회, 관계→조건 요구·출처 노드 조회. 평면표도 ID 조인으로 같은 결과를 낼 수 있음(이번 비교에서 그렇게 함)",
      "- 단점: 코드 양(graphs.py) 증가, 원본 MedGraph 의 고정 종류 목록 때문에 별도 그래프 클래스 필요",
      "", "## 미구현·한계", "- 증분 갱신 없음(as_of 마다 재계산). 확률·가중치 없음(의도). 에피소드 자동 연결은 메타데이터·단일 에피소드·명시 문구만",
      "- TRUE 경로의 충돌 의존 검사는 현재 원자 구조에서 구조적으로 발생하지 않음(TRUE 인 AND 는 CONFLICT 자식을 가질 수 없음). 방어 코드로만 존재",
      "- 미설명 소견 분류에 검사명 언급(TEST_NAME_WITHOUT_RESULT)이 섞임", "- 관계 8개·조건 모두 전문의 검토 없음"]
(H / "docs/V4_REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print(len(L))
