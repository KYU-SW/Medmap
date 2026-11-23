"""손계산 사례: 기대값(EXPECTED)은 실행 전에 손으로 계산해 적었다 (C_INTEGRATED_PROBLEM_FORMALIZATION.md §9.2).
[합성 실험] 실행: /home/<user>/ai_env/bin/python -I hand_cases.py
"""
import copy, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integrated_model as im


def hc_base():
    v = copy.deepcopy(im.MAIN)
    v["obs"].update({"ckd": "F", "hk": "F", "age75": "F"})
    v["know_vars"] = []
    v["rules"] = [r for r in v["rules"] if r["kind"] != "UNKNOWN_INTERACTION"]
    v["bcap_options"] = [2]
    v["W"] = {"order": [("benB", "benA")], "lo": {"burden": 0.1}, "hi": {"burden": 0.5}}
    tag = {"E1": "MET", "E2": "IN", "E3": "SUPPORTED"}
    v["effects"] = {
        "A1": {"benA": [([("ckd", 0)], ("IV", 0.5, 0.6), tag), ([("ckd", 1)], ("OUT",), tag)]},
        "A2": {"benA": [([], ("IV", 0.0, 0.1), tag)]},
        "B1": {"benB": [([], ("IV", 0.5, 0.6), tag)]},
        "B2": {"benB": [([], ("IV", 0.0, 0.1), tag)]},
        "S": {"benA": [([], ("IV", 0.1, 0.2), tag)], "benB": [([], ("IV", 0.0, 0.0), tag)]},
    }
    v["synergy"][0]["interval"] = (0.0, 0.0)
    return v


def hc2():
    v = hc_base(); v["obs"]["ckd"] = "U"; return v


def hc3():
    """HC3: ⊥ 효과를 0 으로 두면 허위 확정. B1 근거 없음(⊥), 나머지 HC1 과 같음."""
    v = hc_base()
    v["effects"]["B1"] = {"benB": [([], ("NONE",), {"E1": "NO_TRIAL", "E2": "NO_TRIAL", "E3": "NO_TRIAL"})]}
    return v


EXPECTED = {
    # (case, plan, norm): category   — 손계산
    ("HC1", "A1+B1", "NORM_A"): "ALWAYS_BEST",
    ("HC1", "S", "NORM_A"): "NEVER_BEST",
    ("HC2", "A1+B1", "NORM_A"): "CLOSABLE_BY_P",   # ckd=0 확인 시 확정, ckd=1 이면 A1 금기
    ("HC2", "A1+B1", "NORM_B"): "CLOSABLE_BY_P",   # ckd=1 상태에선 부적격이라 OUT/⊥ 가 판단에 안 쓰임
    ("HC3", "A1+B1", "NORM_A"): "KNOWLEDGE_GAP_ALL_STATES",
}


def main():
    cases = {"HC1": hc_base(), "HC2": hc2(), "HC3": hc3()}
    fails = 0
    for (cn, plan, norm), exp in EXPECTED.items():
        inst = cases[cn]
        SP, SK, plans = im.clinical_states(inst), im.know_states(inst), im.all_plans(inst)
        x = frozenset(plan.split("+"))
        rec = im.categorize(inst, x, norm, plans, SP, SK)
        fl = rec["flags"]
        maa, mee = im.milp_AA(inst, x, norm), im.milp_exists(inst, x, norm, plans, ())
        mcp = im.milp_exists(inst, x, norm, plans, ("K", "Q"))
        ok = rec["category"] == exp and maa == fl["AA"] and mee == fl["PKQ"] and mcp == fl["P"]
        fails += not ok
        print(f"{cn} {plan:<6} {norm}: expected={exp} got={rec['category']} "
              f"brute(AA,EE,CP)=({int(fl['AA'])},{int(fl['PKQ'])},{int(fl['P'])}) milp=({int(maa)},{int(mee)},{int(mcp)}) {'OK' if ok else 'FAIL'}")
    # HC3 ⊥->0 기준선: 허위 확정 확인
    v = hc3(); v["effects"]["B1"] = {"benB": [([], ("IV", 0.0, 0.0), {"E1": "-"})]}
    SP, SK, plans = im.clinical_states(v), im.know_states(v), im.all_plans(v)
    r0 = im.categorize(v, frozenset(["A1", "B1"]), "NORM_A", plans, SP, SK)
    print(f"HC3 naive ⊥:=0 -> A1+B1 category={r0['category']} (정직한 판정: KNOWLEDGE_GAP_ALL_STATES)")
    print(f"hand case failures={fails}")


if __name__ == "__main__":
    main()
