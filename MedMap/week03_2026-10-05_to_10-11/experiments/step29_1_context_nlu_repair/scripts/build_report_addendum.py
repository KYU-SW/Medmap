"""STEP29.1 보고서 부록(사후 — 공식 판정 고정 후). build_report.py(동결)는 건드리지 않고 docs/step29_1_report.md 끝에 덧붙인다(재실행 시 재생성)."""
import json

import s291_common as S

R = S.DOCS / "step29_1_report.md"
x = S.load_json(S.OUT / "exploratory_guard_ablation.json")
M = S.load_json(S.OUT / "eval_summary.json")["metrics"]
md = R.read_text(encoding="utf-8").split("\n## 7. 사후 발견")[0]
ab = x["ablation"]
md += f"""
## 7. 사후 발견·탐색(EXPLORATORY_POST_HOC — 공식 판정 아님)

- 공식 REGRESSION 의 원인 = P5 가드의 coverage 손실(S1·S2 동시 FAIL). hard 게이트 10 개는 전부 PASS.
- 가드별 pilot 차단(정답 concept 차단 / 오답 차단): {json.dumps(x['blocked_by_rule(pilot)'], ensure_ascii=False)} — 'B4 단독 + 증상 단서 없음' 이 정답 24 를 막음
  (STEP27 SYMPTOM_CUE 사전이 '몸이 펄펄 끓어요'·'게워냈어요'·'목이 칼칼해요' 같은 말바꿈을 모름).
- 규칙 하나씩 끈 변형: {json.dumps(ab, ensure_ascii=False)}
  → B4 가드를 빼면 P4 수준 회복에 가까우나 precision 0.9333 바로 아래 — 채택 안 함(평가 후 변경 금지). 다음 단계에서 사전 고정 후 재평가 대상.
- P3·P4 단계 자체는 손실 없음: P4 = precision {M['P4']['reg_precision']} · coverage {M['P4']['reg_coverage']} · 다중 {M['P4']['pilot_multi_retention']}, 단 P4 는 hard G5 {M['P4']['G5_neg_resolved_hypothetical_positive']}(가정·질문 표현 미처리) → P5 의 가정·질문 가드가 G5 를 0 으로 만듦.
- 전향적 T4_RESOLVED 0/10(모든 정책): 생성 문장 '…났어요 오늘은 괜찮아요.' 가 첫 문장 뒤 마침표 없이 한 문장으로 분석됨({x['prospective_T4_segmentation']['clauses']}) — 문장부호 없는 입력(음성 전사)에서 문장·절 분리가 안 되는 한계. 생성기 결함이기도 함(마침표 누락).
"""
import csv
E = list(csv.DictReader(open(S.OUT / "eval_errors.csv", encoding="utf-8")))
neg10 = [e["text"] for e in E if e["level"] == "P5" and e["set"] == "PROS" and e["type"] == "NEGATION"]
v5 = [f"{e['set']}:{e['type']}:{e['text']}" for e in E if e["level"] == "P5" and e["type"].startswith("V5_")]
md += f"""- **새 오류(P3 도입)**: 문장부호 없는 '…했어요 오늘은 괜찮아요' 가 한 단위가 되어 '괜찮' 이 과거 증상 mention 의 술어로 잡힘 → 과거 증상 ABSENT {len(neg10)} 건(전향적 T4_RESOLVED 전부, P1 0).
  예 {neg10[:3]}. 지시문 §4 가 금지한 '괜찮다 과잉 부정' 이 문장 분리 실패와 겹쳐 발생 — 다음 단계 필수 수정(평가형 술어는 같은 절·같은 문장 안 mention 명사에만, EF 종결 기준 분리).
- 검사기 v5 위반(P5) {len(v5)}: {v5} — '박동성 두통'·'회전성 어지럼증' 은 증상 성질 수식어인데 v5 의 'X성' 진단형 규칙이 위반으로 셈(검사기 한계, 경과 수식어 목록에 성질 수식어 없음).
  '속이 메스꺼웠어요 오늘은 구토를 해요' 는 문장 미분리로 두 증상이 한 범위에 들어간 경우.
- 전향적 정상화 실패 P1 {M['P1']['pros_err_WRONG_NORMALIZATION']} → P5 {M['P5']['pros_err_WRONG_NORMALIZATION']}(가드 영향 포함) · 모델 양성 금지 위반 P1 {M['P1']['pros_err_MODEL_POSITIVE_FORBIDDEN']} → P5 {M['P5']['pros_err_MODEL_POSITIVE_FORBIDDEN']}.
"""
R.write_text(md, encoding="utf-8")
print("ok")
