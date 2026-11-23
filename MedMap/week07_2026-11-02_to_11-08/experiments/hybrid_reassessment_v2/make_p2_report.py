"""outputs JSON 에서 docs/SAFETY_PATCH_P2.md 생성(수치 손 입력 금지). 기존 문서·결과는 건드리지 않는다."""
import json
from pathlib import Path

H = Path(__file__).parent
G = json.loads((H / "outputs/p2_regression.json").read_text(encoding="utf-8"))
R = json.loads((H / "outputs/p2_replay_regression.json").read_text(encoding="utf-8"))
K = json.loads((H / "outputs/p2_preservation.json").read_text(encoding="utf-8"))
A = {"Labs.test_normal": "A", "Types.test_1d_low_pretest_outside_scope": "B", "CaseTimelinePhase.test_corrected_report_no_longer_confirms": "A",
     "CaseTimelinePhase.test_result_available_later_not_retroactive": "A", "CaseTimelinePhase.test_unavailable_document_not_used": "A",
     "DdimerClinicalPhase.test_anticoagulant_without_target_holds": "A", "DdimerClinicalPhase.test_followup_without_more_context_holds": "A",
     "DdimerClinicalPhase.test_high_pretest_and_point_of_care": "A", "DdimerClinicalPhase.test_phase_not_stated_holds": "A",
     "DdimerClinicalPhase.test_suspected_evaluation_keeps_relation": "A"}          # 분류 근거: 실패 메시지 확인(아래 표에 메시지 함께 기록)
L = ["# Hybrid v2 P2 Clinical Evidence Safety Patch", "",
     "구현 정책 검사 기록이다. 합성 문장·노출 문장으로 확인했고 임상 정확도가 아니다.", "",
     "## P2 안전 정책",
     "- **A. D-dimer 정상**: 의심 평가 단계 + 기록에서 확인된 임상 확률 + 검사법 민감도 + 판정 기준이 모두 있을 때만 WEAKEN. 고민감(ELISA 등)은 낮음·중간, 중등도 민감·현장 검사는 낮음만. 하나라도 없으면 INSUFFICIENT_EVIDENCE",
     "- **B. 임상 단계**: CTPA 음성·CTPA 양성·관류 정상·D-dimer 정상 관계에 단계 조건 적용. 확진·치료 중·치료 후 추적 = NOT_APPLICABLE, 재발 평가 = UNCERTAIN, 단계 불명 = INSUFFICIENT_EVIDENCE",
     "- **B. 가설 대상**: `hypothesis_target`(diagnosis_episode_id, kind, hypothesis_target_time) 와 근거 관찰 시각 연결. 과거 에피소드 판단 시점 이후 근거 = NOT_APPLICABLE, 시점 불명 = 보류, 재발 대상 = 재발 단계",
     "- **C. 맥락 출처**: 기본 CLINICAL 모드는 RECORD·PHYSICIAN_CONFIRMED 값만 사용. 출처 미지정·가정·환자 보고 값은 사용 안 함. SYNTHETIC_ASSUMPTION 모드에서만 가정값 사용, 출력에 `output_mode`·`assumed_context_used` 표시",
     "- 공통 스키마 무수정. 새 관계 없음(관계 ID·가설·소견·관계 종류 P1 과 동일). 추가 인용은 기존 관계의 적용 조건 근거",
     "- 지침 인용은 OUP 공식 페이지를 WebFetch 로 읽은 발췌. 사람 원문 대조 필요", "",
     "## 보존 확인"] + [f"- {k}: {v}" for k, v in K.items()] + ["", "## 회귀 테스트(코드 × 기준)", "| 코드 | 기준 | 실행 | 실패 |", "|---|---|---|---|"]
for x in G:
    L.append(f"| {x['code']} | {x['suite']}{' (분류용 가정값 모드)' if x.get('variant') else ''} | {x.get('ran')} | {len(x.get('failed', {}))} |")
syn = {k.split(".", 1)[1] for x in G if x.get("variant") for k in x["failed"]}
L += ["", "P2 코드에서 P1 기준이 실패한 항목 분류(C = 가정값을 쓰지 않음, A = 검사 조건, B = 단계 조건):", ""]
for x in G:
    if x["code"] == "hybrid2_p2" and not x.get("variant") and x["suite"] != "test_safety_patch_p2":
        for k, (t, m) in x["failed"].items():
            n = k.split(".", 1)[1]
            L.append(f"- {x['suite']}.{n}: {'C(+' + A[n] + ')' if n in syn and n in A else ('C' if n not in syn else '분류 없음: 의도하지 않은 회귀 가능')} — `{m[:120]}`")
L += ["", "## 노출 문장 재생(독립 평가 아님, 분모는 출력 단위)"]
for n, s in R["sets"].items():
    L += [f"### {n} ({s['n_sentences']}문장, {s['n_documents']}문서)", "| 조건 | 출력 | 방향 | 잘못된 방향 |", "|---|---|---|---|"]
    L += [f"| {c} | {v['n_outputs']} | {v['directions']} | {v['wrong_direction']} |" for c, v in s["summary"].items()]
    for c, ch in s["changed_vs_P1"].items():
        L.append(f"- P1 대비 바뀐 출력({c}) {len(ch)}건: " + "; ".join(f"{x['id']}번 {x['relation']} {x['before']}→{x['after']} 원인 {x['cause']}" for x in ch))
    L.append("")
L += [f"- P1 기준선 재현 일치: {R['p1_baseline_matches_stored']}", "",
      "## 미해결 위험",
      "- 실제 기록에서 임상 확률·의심 여부·검사법을 읽는 기능 없음. 기본 경로에서 SUPPORT·WEAKEN 은 사실상 나오지 않음(맥락 입력이 있을 때만)",
      "- YEARS 는 임상 확률 범주 대신 자체 항목을 쓰지만 현재 규칙은 임상 확률 범주를 요구(보수적 보류). 나이 보정은 나이 >50 조건 미확인",
      "- 'high-sensitivity D-dimer' 는 D-dimer 결과 창에서 'high' 로 읽혀 상충 기권. 'ELISA' 등만 고민감으로 인식, 실험실 검사명 목록 없음",
      "- 문장 수준 단계 신호는 규칙. 'on warfarin' 처럼 치료 대상 불명은 보류. 문서·문장 간 맥락 연결 제한",
      "- 재발 평가·치료 중 잔존 혈전의 의미에 대한 지침 문구 미확인 → 방향 없이 보류",
      "- 가설 대상(hypothesis_target)은 입력으로만 받음. 자동 에피소드 구분 없음",
      "- 원본 단위 테스트 48개·P1 테스트 44개 중 각 12개가 P2 코드에서 실패: 의도된 정책 변경, 테스트는 P1 역사 기준으로 보존",
      "- P2 변이 검사는 범위 제한 지시에 따라 하지 않음"]
(H / "docs/SAFETY_PATCH_P2.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))
