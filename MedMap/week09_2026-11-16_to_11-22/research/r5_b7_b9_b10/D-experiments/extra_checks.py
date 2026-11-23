"""[합성] 추가 확인 (정답 수정 없음, 읽기 전용 입력):
1) B vs B' 차이가 구현 결함이 아니라 '결합 시 공유 변수 상관 소실' 때문인지: B' 의 근거 모듈에 임상 상태를 조건으로 넘기면
   (= 공유 변수 유지) B 와 같아지는지 차이 인스턴스 전부에서 확인. 또 B' 가 EVIDENCE_GAP 으로 바꾼 상태마다,
   그 상태에서 실제로 불가능한 근거 조합(공유 변수 값과 모순)만이 라벨 불일치를 만들었는지 확인.
2) 혼합 양화 차이 인스턴스의 EWAS/FSEW.
3) E6: r 별 정답 상태 라벨 PREF 비율.
4) B' 최장 시간 인스턴스의 UNK 행동 수(근거 조합 2^m).
출력: results_extra_checks.json
"""
import json, os, sys, time, itertools
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "methods"))
import strong  # noqa

insts = {i["id"]: i for i in json.load(open(os.path.join(HERE, "inputs", "instances.json")))["instances"]}
GT = json.load(open(os.path.join(HERE, "frozen", "ground_truth.json")))["gt"]
out = {}

bb = pd.read_csv(os.path.join(HERE, "results_bvsbp.csv"))
sv = bb[bb.cause.str.contains("shared", na=False)]
conditioned_equal, impossible_only = 0, 0
for iid in sv.id:
    inst = insts[iid]
    xv = inst["patient_cov"]["x1_var"]
    ob = strong.run_B(inst); obp = strong.run_Bp(inst)
    # 조건부 근거 모듈: 차이 난 각 상태에서 '그 상태의 공유 변수 값과 일치하는 근거 완성' 하나만 쓰면 B 라벨이 재현되는가
    G = inst["guidelines"]; plans = list(itertools.product(*[g["options"] for g in G]))
    U, S = strong._states(inst); Wv = strong.Wset(inst)
    allok = True
    for s in S:
        k = strong._key(U, s)
        if ob["per_state"][k] == obp["per_state"][k]:
            continue
        sval = s[xv]

        def ev_of(a, sval=sval):
            act = inst["actions"][a]
            if act["trial"] is None:
                return "NOENTRY"
            return "OK" if strong._in_hull_lp(act["trial"], strong._cov(inst, sval)) else "OUT"
        r, ex = strong._state_core(inst, plans, G, s, ev_of, "B")
        lab = r if ex is None else strong._label_from_vecs(r, ex[0], ex[1], Wv)[0]
        allok &= (tuple(lab[0:1]) + (sorted(map(tuple, lab[1])),)) == (tuple(ob["per_state"][k][0:1]) + (sorted(map(tuple, ob["per_state"][k][1])),))
    conditioned_equal += int(allok)
    # B' 가 다르게 낸 상태에서: 실제 공유 변수 값과 일치하는 근거 완성만 쓰면 B 와 같은가
    ok = True
    for k in ob["per_state"]:
        if ob["per_state"][k] != obp["per_state"][k]:
            ok &= (obp["per_state"][k][0] == "EVIDENCE_GAP") and (xv is not None)
    impossible_only += int(ok)
out["shared_var_diffs"] = dict(n=len(sv), Bp_states_changed_only_to_EVIDENCE_GAP=impossible_only,
                               B_reproducible=conditioned_equal,
                               Bp_wrong_confirm_in_diffs=int(((sv.Bp_full_ok == 0) & sv.Bp_final.isin(["CONVERGED", "CONFIRMED_PLAN", "CONDITIONAL_PLAN"])).sum()))
mq = bb[bb.cause.str.contains("mixed", na=False)]
out["mixed_quantifier"] = [dict(id=i, gt_ewas=GT[i]["ewas"], gt_fsew=GT[i]["fsew"], gt_final=GT[i]["final"]) for i in mq.id]
rows = []
for iid, inst in insts.items():
    if inst["exp"] != "E6" or GT[iid]["final"] == "NO_GROUND_TRUTH":
        continue
    ks = [v[0] for v in GT[iid]["per_state"].values()]
    rows.append(dict(r=inst["params"]["r"], pref_states=sum(k == "PREF" for k in ks), states=len(ks),
                     gap_states=sum(k in ("EVIDENCE_GAP", "KNOWLEDGE_GAP") for k in ks), final=GT[iid]["final"]))
d = pd.DataFrame(rows)
out["E6_by_r"] = d.groupby("r").agg(pref_states=("pref_states", "sum"), gap_states=("gap_states", "sum"),
                                    states=("states", "sum")).reset_index().to_dict("records")
pi = pd.read_csv(os.path.join(HERE, "results_per_instance.csv"))
w = pi[pi.method == "Bp_modular"].sort_values("time_s").iloc[-1]
inst = insts[w.id]
xv = inst["patient_cov"]["x1_var"]
unk = 0
if xv is not None and inst["obs"][xv] == "U":
    for a in inst["actions"]:
        if a["trial"] is None:
            continue
        r0 = strong._in_hull_lp(a["trial"], strong._cov(inst, 0)); r1 = strong._in_hull_lp(a["trial"], strong._cov(inst, 1))
        unk += int(r0 != r1)
out["Bp_slowest"] = dict(id=w.id, time_s=float(w.time_s), unk_actions=unk, evidence_completions=2 ** unk, n_states=int(w.n_states),
                         B_time_s=float(pi[(pi.method == "B_joint") & (pi.id == w.id)].time_s.iloc[0]))
json.dump(out, open(os.path.join(HERE, "results_extra_checks.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
