"""STEP29 보고서 부록(사후 — 공식 판정 고정 후). build_report.py(동결)는 건드리지 않고 docs/step29_nlu_report.md 끝에 사후 절을 덧붙인다(재실행 시 재생성)."""
import json

import s29_common as S

R = S.DOCS / "step29_nlu_report.md"
x = S.load_json(S.OUT / "exploratory_v2.json")
ut = S.load_json(S.OUT / "unit_tests.json")["by_file"]
fails = {k: v["messages"] for k, v in ut.items() if v["failures"] or v["errors"]}
md = R.read_text(encoding="utf-8").split("\n## 7. 사후 발견")[0]
md += f"""
## 7. 사후 발견·탐색 v2(EXPLORATORY_POST_HOC — 공식 판정 아님)

- 공식 REGRESSION 원인 ① G3 2건 = **검사기 v4 결함**(문장 단위 적용): '고혈압이 있고 머리가 아파요'·'기침약을 먹었는데 기침이 계속 나요' 는 NLU 가 비증상(고혈압·기침약)과 증상(머리 통증·기침)을 올바로 분리했으나 문장에 고혈압·기침약이 있어 위반으로 셈. 검사기 정답 대조에 다중 구문 문장을 넣지 않은 실수.
- ② G4 1건 = **실제 NLU 오류**: '입맛은 괜찮아요'(pilot gold decreased_appetite absent) → 부정 표지가 없어 PRESENT.
- v2(동결 파일 무수정, 실행 중 덮어쓰기): 검사기를 mention 단위로 적용 + '괜찮' 평가형 부정 → {json.dumps(x['NLU_P5_v2'], ensure_ascii=False)}
  → hard {json.dumps(x['hard_gates_v2'], ensure_ascii=False)} → **{x['STEP29_RESULT_EXPLORATORY_V2']} / {x['STEP30_READINESS_EXPLORATORY_V2']}(탐색)**. '괜찮' 규칙은 평가 세트 오류를 보고 만든 것 → 일반화 근거 아님. 다음 단계에서 사전 고정 후 새 자료로 재검증 필요.
- 단위 테스트 실패(공식 실행): {json.dumps(fails, ensure_ascii=False)[:600]} — '어제는 숨이 찼는데 오늘은 괜찮아요' 가 RESOLVED 대신 PAST('오늘은 괜찮아요' 절이 mention 으로 남아 해소 단서로 쓰이지 않음). 계약은 PAST 도 허용해 통과.
- 계약 실패 3(P5 한계, 모두 '미연결'로 안전): '토하지 않았어요'(P5 '토하' 모호) · '지금은 안 아파요'(생략된 부위) · '숨 쉴 때마다 옆구리가 찌르듯이 아파요'(중간 부사절 → pain 미연결, dyspnea 오연결은 없음).
"""
R.write_text(md, encoding="utf-8")
print("ok")
