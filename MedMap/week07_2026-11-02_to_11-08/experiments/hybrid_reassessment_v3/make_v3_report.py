"""outputs JSON 에서 docs/V3_REPORT.md 생성(수치 손 입력 금지)."""
import json
from pathlib import Path

H = Path(__file__).parent
E = json.loads((H / "outputs/v3_e2e.json").read_text(encoding="utf-8"))
A = json.loads((H / "outputs/v3_ablation.json").read_text(encoding="utf-8"))
C = json.loads((H / "outputs/v3_linking_compare.json").read_text(encoding="utf-8"))
K = json.loads((H / "outputs/v3_preservation.json").read_text(encoding="utf-8"))
L = ["# MedMap Hybrid v3 — 의료 문맥 추출 · 개념 연결 · 그래프 기반 근거 재평가(PE 파일럿)", "",
     "기술 기능 검증 기록이다. 합성 기록·노출 문장 사용, 임상 성능 검증 아님. 판단은 확률이 아니며 의사 확인 대상.", "",
     "## 구성(실제 구현)",
     "- `hybrid3/concepts.py`: P2 parser·lexicon·finding_state 재사용 + 하위형(SSPE·재발 PE·근위부 DVT)·치료(항응고·혈전용해)·CTPA 변형, 문서 약어 정의, 용어 목록 구간 제외, 사전 밖 검사명 '지원 안 함' 표시",
     "- `hybrid3/context.py`: 기록 문장에서 임상 확률(명시 범주만)·의심/검사 목적·과거 진단 진술·치료 상태·단계 신호·D-dimer 검사법/기준·혈역학 불안정 추출. 사실마다 value·source_type·extraction_method·certainty·관찰/이용 시각·의사 확인 상태",
     "- `hybrid3/kg.py`: EXP-01b 그래프(읽기 전용) + 덧층(검사 결과 상태 노드·검증 관계 간선). 방향은 '검사 노드 → 결과 상태 → 가설' 경로의 검증 간선 속성으로만",
     "- `hybrid3/reasoner.py`: P2 출처 규칙·단계 판정·가설 대상·D-dimer 조건·관계 적용 재사용, 보류 원인 A~E 분류, 시간순 Case(v1 시간 정책), 템플릿 설명",
     "- `knowledge/v3_graph_overlay.json`: 덧층 정의. 방향 간선은 P2 카탈로그(무수정)에서만 생성. 새 의학 관계 없음. 혈역학 불안정 제외 조건은 기존 Figure 5 인용 범위",
     "", "## 보존 확인"] + [f"- {k}: {v}" for k, v in K.items()] + ["", "## 그래프 기여(ablation, 출력 단위)", "| 조건 | 바뀐 출력 | 방향 판단(전→후) |", "|---|---|---|"]
for k, v in A.items():
    if k != "full_graph":
        L.append(f"| {k} | {v['n_changed']} | {v['directional_before']}→{v['directional_after']} |")
L += ["", f"- 전체 그래프 통계: {A['full_graph']['stats']}",
      "- 기존 그래프 SUGGESTS·공출현 간선은 표시 전용(used_for_direction=False). 기존 그래프가 판단에 주는 것은 가설·검사 노드 존재(범위)와 표시용 연관. 방향은 덧층 검증 간선에서 나옴", "",
      f"## P2 기본 경로(맥락 입력 없음)로 같은 사례 문서 처리: {C['p2_default_directions_on_cases']}", "", "## End-to-End 사례"]
for n, sts in E.items():
    for st in sts:
        L.append(f"### {n} @ {st['as_of']}")
        L.append(f"- 가설별 요약: {st['hypotheses']}")
        L.append(f"- 추출 맥락: " + str({k: v for k, v in st['context'].items() if k in ('pretest', 'suspected', 'ddimer_assay', 'ddimer_cutoff', 'haemodynamic_instability', 'phase_signals')}))
        for r in st["results"]:
            if r["concept"] in ("PE_DIAGNOSIS", "DDIMER", "PERFUSION_SCAN", "DVT", "FILLING_DEFECT") or r["direction"] != "ABSTAIN" or r["abstain_reason"] in ("CONCEPT_NOT_SUPPORTED", "HYPOTHESIS_NOT_IN_GRAPH"):
                L.append(f"  - {r['hypothesis_episode']} {r['document']} `{r['surface']}` {r['assertion']} → **{r['direction']}** {r['relation_id'] or r['abstain_reason']}"
                         + (f" 부족 {[g['item'] + '(' + g['class'] + ')' for g in r['gaps']]}" if r["gaps"] else ""))
first = E["CASE01_suspected_positive_ctpa"][0]["results"]
L += ["", "## 설명 출력 예(CASE01)", "```", next(r["explanation"] for r in first if r["direction"] == "SUPPORT"), "```", "",
      "## 노출 문장 개념 연결 비교(개발·회귀 자료, 독립 평가 아님, 단일 문장·사례 맥락 없음)", "| 표본 | 버전 | 찾음/주석 | 상태 일치 | 주석에 없는 연결 | 모호 |", "|---|---|---|---|---|---|"]
for s in ("run1_exposed", "run2_exposed"):
    for v in ("P2", "V3"):
        x = C[s][v]
        L.append(f"| {s} | {v} | {x['found']}/{x['gold']} | {x['agree']}/{x['found']} | {x['unsupported']} | {x['ambiguous']} |")
    L.append(f"- {s} V3 방향 {C[s]['V3']['directions']}, 보류 원인 {C[s]['V3']['gap_classes']}, V3 미검출 {C[s]['V3']['v3_missed']}")
L += ["", "## 지원 범위", "- PE 1개 질환, 검증 관계 8개(P2 카탈로그), 영어 문장, 규칙 기반", "- 임상 확률은 기록에 범주가 명시된 경우만(점수→범주 변환 없음, 2단계 Wells·위험도 미사용)",
      "", "## 지원하지 못하는 범위", "- 기록에서 점수로 임상 확률 범주 계산, 검사실 메타데이터의 검사법 연결, 나이 보정 조건(>50세)",
      "- 문장 간 대명사·생략, 문서 간 에피소드 자동 병합(가설 대상은 입력), 재발 평가·잔존 혈전의 방향 관계(지침 문구 미확인)",
      "- 비표준 CT 표기('CT angiogram of the pulmonary vasculature' 일부), 'high-sensitivity D-dimer' 표기, 사전 밖 질환·검사 연결",
      "- 의사 확인 시각(메타데이터 없으면 UNCONFIRMED), LLM 없음",
      "", "## 임상적으로 검증되지 않은 부분", "- 관계 카탈로그·적용 조건 전문가 검토 없음, 추출 정확도·판단 정확도 전문가 기준 없음, 실제 EMR 미사용"]
(H / "docs/V3_REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print(len(L))
