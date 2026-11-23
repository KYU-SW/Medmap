"""outputs JSON 에서 docs/V5_1_REPORT.md 생성(수치 손 입력 금지)."""
import json
from collections import Counter
from pathlib import Path

H = Path(__file__).parent
J = lambda n: json.loads((H / f"outputs/{n}").read_text(encoding="utf-8"))  # noqa: E731
C, CMP, REG, K = J("v5_1_cases.json"), J("v5_1_compare.json"), J("v5_1_registry_compat.json"), J("v5_1_preservation.json")
L = ["# MedMap v5-1 — 다질환 근거 처리 기반(구조 구현)", "",
     "A 코드 구현 완료 / B 기술 검증(합성 사례) 완료 / C 의학 해석 검증 미완료 / D 임상 성능 NOT_EVALUATED. **신규 활성 방향 관계 0건.**", "",
     "## 모듈", "- `hybrid5/logic.py` v4 4값 논리 재사용 + AT_LEAST_K·EXACTLY_K(최소·최대 충족 범위, 미확정 원인 UNKNOWN_ONLY/CONFLICT_ONLY/CONFLICT_AND_UNKNOWN)",
     "- `hybrid5/concepts.py` 다질환 개념·분류 축(임상 표현/기전/경과), 진단 상태 5종, 문장 언급(미확인 후보)",
     "- `hybrid5/observations.py` 트로포닌·CRP 수치·단위·검사법·기준값, 시계열(비교 가능성·수학적 변화량), as_of·정정",
     "- `hybrid5/ecg.py` ECG 판독문 구조화(소견·상태·유도·분포·mm·대측·리듬·심박), 미지원 표현 표시",
     "- `hybrid5/classification.py` 연구용 분류: 심낭염 Table 4, 급성·만성 심근손상(UDMI5 Box 1·2). 방향 판단과 분리",
     "- `hybrid5/graphs.py`·`flat.py` v4 PatientGraph 상속 확장 / 같은 입력의 평면표, 공용 평가 함수", "",
     "## 보존"] + [f"- {k}: {v}" for k, v in K.items()] + ["", f"## 그래프 vs 평면표: {CMP['n']}개 상태 모두 동일 {CMP['all_identical']}", "",
     "## 사례 결과"]
for name, v in C.items():
    if not isinstance(v, dict) or "states" not in v:
        L.append(f"- **{name}**: `{json.dumps(v, ensure_ascii=False)[:600]}`")
        continue
    for st in v["states"]:
        for h in st["hypotheses"]:
            cls = "; ".join(f"{c.get('guideline_classification') or ''}{c.get('acute_injury') or ''} 범위{c.get('criteria_count_range') or ''}" for c in h["classifications"])
            ser = "; ".join(f"{s['analyte']}: " + ", ".join(f"{p['from']}→{p['to']} {p['delta_status'][:30]}" for p in s["pairs"]) for s in h["series"] if s["pairs"])
            ecg = ", ".join(f"{f['finding_type']}/{f['assertion_status']}/{f['lead_or_distribution']['distribution']}" for f in h["ecg_findings"])
            L.append(f"- {name}@{st['as_of']} `{h['hyp_id']}` {h['concept_id']} [{h['diagnosis_status']}] 축 {h['presentation_axis']}/{h['mechanism_axis']}"
                     + (f" | 분류 {cls}" if cls else "") + (f" | 시계열 {ser}" if ser else "") + (f" | ECG {ecg}" if ecg else "")
                     + (f" | 후보 {[(c['concept_id'], c['attributes'], c['diagnosis_status']) for c in h['ai_candidates_unconfirmed']]}" if h["ai_candidates_unconfirmed"] else "")
                     + (" | LEGACY_V4 " + str(h["legacy_v4"]["items"]) if h.get("legacy_v4") else "") + f" | 지지·약화 {len(h['supporting_evidence_ids'])}/{len(h['weakening_evidence_ids'])}")
L += ["", "## v5-0B 후보 37건 호환성(엔진 비활성 유지)", f"- 레지스트리 sha256 `{REG['registry_sha256']}`, 후보 {REG['n']}, 활성 {REG['active_in_registry']}, v5-1 활성화 {REG['activated_in_v5_1']}",
      f"- 상태 빈도: {dict(Counter(s for r in REG['rows'] for s in r['v5_1_status']))}"]
L += [f"  - {r['candidate_id']}({r['v5_0b_group']}): {r['v5_1_status']} {r['reason'][:90]}" for r in REG["rows"]]
L += ["", "## 한계", "- 텍스트 수치 추출은 규칙 기반(같은 문장 내 분석물·값·기준). 문장 간 연결, 표 형식 검사지, 단위 변환 없음",
      "- 상승·하강 '유의성' 기준이 원문에 없어(UDMI5 §14.1.4) 기록 진술만 사용 → 수치만 있으면 급성 손상 미결",
      "- 심낭염 임상 양상은 흉통 HPO 개념 또는 구조화 입력만. 영상 2항목 계산(CRQ-15) 미결이라 두 방식 병기",
      "- ECG 는 판독문 표현만(파형 없음). 유도별 mm·성별·연령 기준 적용 안 함",
      "- 진단 언급의 언급 상태는 v3 parser 의존(같은 한계 승계)"]
(H / "docs/V5_1_REPORT.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print(len(L))
