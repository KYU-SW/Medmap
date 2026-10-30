"""가상 사례 시연(7절 흐름 1~10). 환자는 모두 가상. 결과 문장은 실제 추론 결과 객체에서 생성.

실행: ~/ai_env/bin/python demo.py [--out outputs/demo_<시각>]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from graph_engine import (EvidenceRecord, ReasoningSession, Status, assess_working_dx, from_medmap_input)
from knowledge_real_hsdn import build_hsdn_graph
from knowledge_toy import build_toy_graph
from report_ko import render_ko, to_json

HERE = Path(__file__).resolve().parent


def toy_case():
    g = build_toy_graph()
    # 1. 환자 증상 입력(기존 MedMap 입력 형식: 나이·성별·첫 증상·이진·범주형·추가 답변). 나이는 미제공 → None 유지.
    pr = from_medmap_input("TOY-P1", {
        "sex": "F", "initial_evidence": "s1", "working_dx": "TA",           # 2. 현재 의사 진단
        "binary": {"s2": "POSITIVE", "s4": "UNCERTAIN", "g1": "NEGATIVE"},
        "categorical": {"s3": "R"},
        "extra": [{"node_id": "f1", "status": "NOT_TESTED", "source_id": "order-T1", "observed_at": 0.0,
                   "recorded_at": 0.0, "source_type": "test"}],
    }, recorded_at=1.0)
    sess = ReasoningSession(g, pr, as_of=1.0)                               # 3~5. 경로 탐색·조건·통합
    wd1 = assess_working_dx(g, sess.current, pr, pr.working_dx)             # 6. 분류
    step1 = (sess.current, wd1, None)
    g1_old = next(r for r in pr.history("g1"))
    new = [  # 7. 새 증상·검사 정보 + 병력 정정(원 기록 유지, supersedes 로 연결)
        EvidenceRecord("s4", Status.POSITIVE, "TOY-P1-q-s4-recheck", 2.0, 2.0, "patient_report", evidence_id="TOY-P1-e101"),
        EvidenceRecord("g1", Status.POSITIVE, "TOY-P1-chart-g1", 0.5, 2.0, "chart_review",
                       evidence_id="TOY-P1-e102", supersedes=g1_old.evidence_id, provenance="병력 정정(가상)"),
        EvidenceRecord("f1", Status.POSITIVE, "order-T1-result", 1.5, 2.0, "test", value="820", unit="u/L",
                       evidence_id="TOY-P1-e103"),
    ]
    inf2, trans, aff = sess.update(new, as_of=2.0)                          # 8. 영향 질환만 재계산
    wd2 = assess_working_dx(g, inf2, pr, pr.working_dx)                     # 9~10. 재활성화·최종 경로
    return g, pr, step1, (inf2, wd2, trans), aff


def real_case():
    g, meta = build_hsdn_graph()
    pr = from_medmap_input("REAL-P1", {   # 가상 환자
        "age": 63, "sex": "M", "initial_evidence": "S:CHEST_PAIN", "working_dx": "D:MI",
        "binary": {"S:DYSPNEA": "POSITIVE", "S:HEMOPTYSIS": "POSITIVE", "S:FEVER": "NEGATIVE",
                   "S:COUGH": "UNCERTAIN"},
        "extra": [{"node_id": "X:LEG_SWELLING_UNMAPPED", "status": "POSITIVE", "source_id": "q-leg",
                   "observed_at": 1.0, "recorded_at": 1.0}],
    }, recorded_at=1.0)
    sess = ReasoningSession(g, pr, as_of=1.0)
    inf1 = sess.current
    wd1 = assess_working_dx(g, inf1, pr, pr.working_dx)
    inf2, trans, aff = sess.update([EvidenceRecord("S:SYNCOPE", Status.POSITIVE, "q-syncope", 2.0, 2.0,
                                                   "patient_report", evidence_id="REAL-P1-e101")], as_of=2.0)
    wd2 = assess_working_dx(g, inf2, pr, pr.working_dx)
    wd_alt = assess_working_dx(g, inf2, pr, "D:PERICARDITIS")   # 같은 추론 결과에 다른 현재 진단을 넣은 비교
    return g, meta, (inf1, wd1), (inf2, wd2, trans, wd_alt), aff


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(HERE / "outputs" / time.strftime("demo_%Y%m%d_%H%M%S")))
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=False)
    g, pr, (inf1, wd1, _), (inf2, wd2, trans), aff = toy_case()
    md = ["# EXP-01b 최소 추론 엔진 시연(가상 사례)", "",
          "> TOY 그래프 = 구현 시험용 가상 관계(의학 지식 아님). REAL 그래프 = HSDN 문헌 공출현 관계. 환자는 모두 가상.",
          "> 실제 환자 진단·성능 주장 없음.", "",
          "# A. TOY 사례", "", render_ko(g, inf1, wd1, title="A-1. 첫 입력 후(as_of=1.0)"), "",
          f"- 새 정보 노드: s4·g1(정정)·f1 → 그래프 순회로 재계산한 질환: {sorted(aff)}",
          "- g1 변경 이력: " + " → ".join(f"{r.evidence_id}:{r.status.value}@{r.recorded_at}"
                                          + (f"(정정 대상 {r.supersedes})" if r.supersedes else "")
                                          for r in pr.history("g1")), "",
          render_ko(g, inf2, wd2, trans, title="A-2. 새 근거 입력·재계산 후(as_of=2.0)")]
    rg, meta, (rinf1, rwd1), (rinf2, rwd2, rtrans, rwd_alt), raff = real_case()
    alt = render_ko(rg, rinf2, rwd_alt, title="B-3. 같은 근거, 현재 진단을 심낭염으로 바꾼 비교(as_of=2.0)")
    md += ["", "# B. REAL(HSDN) 사례", "", "```json", json.dumps(meta, ensure_ascii=False, indent=1), "```", "",
           render_ko(rg, rinf1, rwd1, title="B-1. 첫 입력 후(as_of=1.0)"), "",
           f"- 새 정보 노드: S:SYNCOPE → 그래프 순회로 재계산한 질환: {sorted(raff)}", "",
           render_ko(rg, rinf2, rwd2, rtrans, title="B-2. 실신 추가 후(as_of=2.0)"), "",
           alt[alt.index("### 의사 현재 진단 비교"):].replace("### ", "## B-3. 같은 근거·현재 진단 = 심낭염 — ", 1)]
    (out / "demo_report_ko.md").write_text("\n".join(md), encoding="utf-8")
    (out / "demo_results.json").write_text(json.dumps({
        "toy_step1": to_json(inf1, wd1), "toy_step2": to_json(inf2, wd2, trans), "toy_recomputed": sorted(aff),
        "real_meta": meta, "real_step1": to_json(rinf1, rwd1), "real_step2": to_json(rinf2, rwd2, rtrans),
        "real_step2_wd_pericarditis": to_json(rinf2, rwd_alt)["working_dx"],
        "real_recomputed": sorted(raff)}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
