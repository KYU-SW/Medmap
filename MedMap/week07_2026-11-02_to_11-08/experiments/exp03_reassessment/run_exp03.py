"""EXP-03 합성 실험 실행: PROPOSED · BASELINE-N · BASELINE-E 를 같은 시나리오·기대 출력으로 채점 + v2/v3b 연결 비교.
출력 outputs/exp03_<시각>/{exp03_results.json, EXP03_REPORT_ko.md} — 숫자는 계산값만(손으로 쓰지 않음). 합성 규칙 정합성일 뿐 임상 성능 아님."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import baselines as BL
import scenarios as SC
from ct_bridge import classify
from reassess import assess, session

HERE = Path(__file__).resolve().parent
TEXTS = {"POS": SC.POS_TXT, "NEG": SC.NEG_TXT, "LONGNEG": SC.LONGNEG_TXT, "CHR": SC.CHR_TXT, "UNC": SC.UNC_TXT,
         "HIST": SC.HIST_TXT, "IND": SC.IND_TXT}
NON_DECISIVE = {"PENDING", "UNKNOWN", "INSUFFICIENT"}


def proposed(tl, T):
    a = assess(tl, T)
    return (a.summary, frozenset(x["rule"] for x in a.alerts))


METHODS = {"PROPOSED": proposed, "BASELINE_N": BL.naive, "BASELINE_E": BL.exp01b}


def score(method, scn) -> dict:
    f = METHODS[method]
    m = Counter()
    per = {}
    for name, (tl, cps, exp, extra) in scn.items():
        rows = []
        for T, (es, ea) in zip(cps, exp):
            got = f(tl, T)
            full, trunc = got, f(tl.truncated(T), T)
            m["checkpoints"] += 1
            m["state_pass"] += got == (es, ea)
            m["leakage"] += full != trunc
            m["absence_as_conflict"] += es in NON_DECISIVE and got[0] == "CONFLICT"
            m["pending_as_confirmed"] += es == "PENDING" and got[0] in ("CONFLICT",) or (es == "PENDING" and got[0] == "SUPPORTED"
                                                                                        and _decisive_pos(tl, T, method))
            m["unneeded_alerts"] += len(got[1] - ea)
            m["missed_alerts"] += len(ea - got[1])
            if name.startswith("I"):
                m["correction_checks"] += 1
                m["correction_pass"] += got == (es, ea)
            if name.startswith("H"):
                m["hypothesis_change_checks"] += 1
                m["hypothesis_change_pass"] += got == (es, ea)
            rows.append({"T": T, "expected": [es, sorted(ea)], "got": [got[0], sorted(got[1])], "pass": got == (es, ea)})
        per[name] = rows
    m["state_pass_rate"] = round(m["state_pass"] / m["checkpoints"], 4)
    return {"metrics": dict(m), "per_scenario": per}


def _decisive_pos(tl, T, method):
    """대기 중 확정으로 본 경우: 아직 사용 불가한 판독을 근거로 SUPPORTED 가 됐는지(관측 시각 기준 방식만 해당)."""
    if method != "BASELINE_N":
        return False
    return any(e.evidence_type == "IMAGING_REPORT" and e.observed_at is not None and e.observed_at <= T
               and (e.available_at is None or e.available_at > T) and e.pe_class == "ACUTE_POS" for e in tl.evidence)


def proposed_extras(scn) -> dict:
    rel = alerts = complete = 0
    excl = Counter()
    for name, (tl, cps, _, _) in scn.items():
        for T in cps:
            a = assess(tl, T)
            for r in a.relations:
                rel += 1
                complete += bool(r[0] and r[2] and r[3] and r[4] and r[5] is not None)
            for al in a.alerts:
                alerts += 1
                complete += all(al.get(k) not in (None, "") for k in ("hypothesis_id", "rule", "event_id", "source_reference",
                                                                      "evidence_type", "available_at"))
        last = assess(tl, cps[-1])
        for k, v in last.excluded.items():
            if k != "NOT_YET_AVAILABLE":
                excl[k] += v
    return {"relations_and_alerts": rel + alerts, "with_full_source": complete,
            "source_completeness": round(complete / (rel + alerts), 4) if rel + alerts else None,
            "excluded_by_availability_policy": dict(excl)}


def bridge_compare() -> dict:
    rows = {k: {"v2": classify(t, "v2"), "v3b": classify(t, "v3b")} for k, t in TEXTS.items()}
    s2, s3 = SC.build("v2"), SC.build("v3b")
    graph_diff = {}
    for name in s3:
        a2 = [proposed(s2[name][0], T) for T in s2[name][1]]
        a3 = [proposed(s3[name][0], T) for T in s3[name][1]]
        if a2 != a3:
            graph_diff[name] = {"v2": [[x[0], sorted(x[1])] for x in a2], "v3b": [[x[0], sorted(x[1])] for x in a3]}
    return {"text_classes": {k: {"v2": list(v["v2"]), "v3b": list(v["v3b"])} for k, v in rows.items()},
            "scenarios_with_different_graph_output": graph_diff}


def main():
    scn = SC.build("v3b")
    res = {"created": datetime.now().isoformat(timespec="seconds"), "n_scenarios": len(scn),
           "n_reject_cases": len(SC.REJECT_CASES), "methods": {m: score(m, scn) for m in METHODS},
           "proposed_extras": proposed_extras(scn), "v2_v3b_bridge": bridge_compare()}
    rej = {}
    for name, fn in SC.REJECT_CASES.items():
        try:
            fn()
            rej[name] = "ACCEPTED(실패)"
        except ValueError:
            rej[name] = "REJECTED"
    res["reject_cases"] = rej
    out = HERE / "outputs" / f"exp03_{datetime.now():%Y%m%d_%H%M}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "exp03_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    L = ["# EXP-03 합성 실험 결과(자동 생성) — 합성 규칙 정합성, 임상 성능 아님", "",
         f"- 생성 {res['created']} · 시나리오 {res['n_scenarios']} · 거부 사례 {res['n_reject_cases']} · 가설 = SIMULATED_WD", "",
         "| 지표 | " + " | ".join(METHODS) + " |", "|---" * (len(METHODS) + 1) + "|"]
    keys = ["checkpoints", "state_pass", "state_pass_rate", "leakage", "absence_as_conflict", "pending_as_confirmed",
            "unneeded_alerts", "missed_alerts", "correction_pass", "correction_checks", "hypothesis_change_pass", "hypothesis_change_checks"]
    for k in keys:
        L.append(f"| {k} | " + " | ".join(str(res["methods"][m]["metrics"].get(k, 0)) for m in METHODS) + " |")
    L += ["", f"- 제안 방식 출처 연결: {res['proposed_extras']}", f"- 거부 사례: {rej}", "",
          "## 실패 체크포인트(방식별)", ""]
    for m in METHODS:
        bad = [f"{n}@{r['T']} 기대 {r['expected']} / 결과 {r['got']}" for n, rows in res["methods"][m]["per_scenario"].items()
               for r in rows if not r["pass"]]
        L.append(f"- {m}: {len(bad)}건" + ("" if not bad else "\n  - " + "\n  - ".join(bad)))
    L += ["", "## v2/v3b 연결(합성 판독문)", ""]
    for k, v in res["v2_v3b_bridge"]["text_classes"].items():
        L.append(f"- {k}: v2 {v['v2'][0]} ({v['v2'][1]}) / v3b {v['v3b'][0]} ({v['v3b'][1]})")
    L.append(f"- 그래프 출력이 달라진 시나리오: {list(res['v2_v3b_bridge']['scenarios_with_different_graph_output'])}")
    (out / "EXP03_REPORT_ko.md").write_text("\n".join(L), encoding="utf-8")
    print("DONE", out)


if __name__ == "__main__":
    main()
