"""[합성] 인스턴스 생성기. 모든 조건(c0..), 행동(a0..), 효과, 부담, 시험 점, 선호는 형식 검증용 가상 값이며
의학적 사실과 무관하다. 출력: inputs/instances.json
사용: python -I gen_instances.py
"""
import json, random, os
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__))
S = lambda x: str(F(x))
BIG = lambda x0, x1lo, x1hi: [[x0 - 30, x1lo - 15], [x0 + 30, x1lo - 15], [x0 - 30, x1hi + 15], [x0 + 30, x1hi + 15]]
CENTER = [F(2, 5), F(3, 10), F(3, 10)]


def W(center=CENTER, r=F(1, 5)):
    return {"center": [S(c) for c in center], "r": S(r)}


def act(i, eff, pills, visits, trial):
    return {"id": i, "effect": eff, "pills": pills, "visits": visits, "trial": trial}


def base(iid, exp, k, obs, guidelines, actions, rules, cov, w, deps=None, params=None):
    return {"id": iid, "exp": exp, "k": k, "obs": obs, "deps": deps or [], "guidelines": guidelines,
            "actions": actions, "rules": rules, "patient_cov": cov, "W": w, "params": params or {}}


def hand_cases():
    """손 사례 A~K. 기대 라벨은 frozen/SPEC.md 7절에 GT 계산 전에 적어 둠."""
    out = []
    cov0 = {"x0": 60, "x1_base": 5, "x1_delta": 0, "x1_var": None}
    big0 = BIG(60, 5, 5)
    # A 실제 충돌 (대체 없음)
    out.append(base("case_A", "case", 1, ["F"],
        [{"app": [], "options": [0]}, {"app": [], "options": [1]}],
        [act(0, 3, 1, 0, big0), act(1, 3, 1, 0, big0)],
        [{"a": 0, "b": 1, "cond": [], "type": "conflict"}], cov0, W()))
    # B 겉보기 충돌 -> 대체 행동으로 해소
    out.append(base("case_B", "case", 1, ["F"],
        [{"app": [], "options": [0]}, {"app": [], "options": [1, 2]}],
        [act(0, 3, 1, 0, big0), act(1, 3, 1, 0, big0), act(2, 2, 1, 1, big0)],
        [{"a": 0, "b": 1, "cond": [], "type": "conflict"}], cov0, W()))
    # C 조건부 충돌 (c0 미확인)
    out.append(base("case_C", "case", 1, ["U"],
        [{"app": [], "options": [0]}, {"app": [], "options": [1]}],
        [act(0, 3, 1, 0, big0), act(1, 3, 1, 0, big0)],
        [{"a": 0, "b": 1, "cond": [[0, 1]], "type": "conflict"}], cov0, W()))
    # D 선호 의존
    out.append(base("case_D", "case", 1, ["F"],
        [{"app": [], "options": [0, 1]}],
        [act(0, 4, 4, 0, big0), act(1, 2, 1, 0, big0)], [], cov0, W()))
    # E 근거 범위 부족: 주변 범위 안, 결합 볼록 껍질 밖
    band = [[50, 9], [55, 8], [60, 6], [65, 4], [70, 2], [52, 8], [68, 3]]
    covE = {"x0": 68, "x1_base": 8, "x1_delta": 0, "x1_var": None}
    out.append(base("case_E", "case", 1, ["F"],
        [{"app": [], "options": [0, 1]}],
        [act(0, 2, 1, 0, BIG(68, 8, 8)), act(1, 4, 2, 0, band)], [], covE, W()))
    # F 지식 부족: 시험 항목 없음
    out.append(base("case_F", "case", 1, ["F"],
        [{"app": [], "options": [0, 1]}],
        [act(0, 2, 1, 0, big0), act(1, 4, 2, 0, None)], [], cov0, W()))
    # G 공유 변수: c0 가 g1 적용 조건과 a1 지지 판정에 동시에 등장
    covG = {"x0": 60, "x1_base": 3, "x1_delta": 5, "x1_var": 0}
    bigG = BIG(60, 3, 8)
    a1_trial = [[50, 6], [70, 6], [50, 10], [70, 10]]  # x1=8(c0=1)만 포함
    out.append(base("case_G", "case", 1, ["U"],
        [{"app": [], "options": [0]}, {"app": [[0, 1]], "options": [1, 2]}],
        [act(0, 2, 1, 0, bigG), act(1, 4, 1, 0, a1_trial), act(2, 2, 1, 0, bigG)], [], covG, W()))
    # H 혼합 양화: 상태마다 가능 최적이지만 하나의 w 로 모든 상태 최적은 불가
    out.append(base("case_H", "case", 1, ["U"],
        [{"app": [], "options": [0, 1, 2]}, {"app": [], "options": [3]}],
        [act(0, 2, 2, 0, big0), act(1, 4, 5, 0, big0), act(2, 1, 0, 0, big0), act(3, 1, 1, 0, big0)],
        [{"a": 1, "b": 3, "cond": [[0, 1]], "type": "conflict"},
         {"a": 2, "b": 3, "cond": [[0, 0]], "type": "conflict"}], cov0, W()))
    # I 세 요소 동시: G + H 를 같은 숨은 변수 c0 로 결합
    out.append(base("case_I", "case", 1, ["U"],
        [{"app": [], "options": [0, 1, 2]}, {"app": [], "options": [3]}, {"app": [[0, 1]], "options": [4, 5]}],
        [act(0, 2, 2, 0, bigG), act(1, 4, 5, 0, bigG), act(2, 1, 0, 0, bigG), act(3, 1, 1, 0, bigG),
         act(4, 4, 1, 0, a1_trial), act(5, 2, 1, 0, bigG)],
        [{"a": 1, "b": 3, "cond": [[0, 1]], "type": "conflict"},
         {"a": 2, "b": 3, "cond": [[0, 0]], "type": "conflict"}], covG, W()))
    # J 정답 없음: 같은 쌍에 충돌 규칙과 양립 규칙이 우선순위 없이 공존
    out.append(base("case_J", "case", 1, ["F"],
        [{"app": [], "options": [0]}, {"app": [], "options": [1]}],
        [act(0, 3, 1, 0, big0), act(1, 3, 1, 0, big0)],
        [{"a": 0, "b": 1, "cond": [], "type": "conflict"}, {"a": 0, "b": 1, "cond": [], "type": "compatible"}],
        cov0, W()))
    # K 수렴: 규칙 없음, 지배 선택지
    out.append(base("case_K", "case", 1, ["F"],
        [{"app": [], "options": [0, 1]}, {"app": [], "options": [2]}],
        [act(0, 4, 1, 0, big0), act(1, 2, 2, 1, big0), act(2, 3, 1, 0, big0)], [], cov0, W()))
    return out


def gen_random(rng, iid, exp, n_unknown=1, n_known=3, G=3, opts=(1, 2, 3), n_rules=3, p_rule_cond=0.5,
               rule_on_unknown=0.6, r=F(1, 10), ev_mode="varied", p_entry=0.93, p_shared=0.5,
               p_contra=0.0, app_on_unknown=0.6, p_dep=0.3, family=None, level=None):
    k = n_unknown + n_known
    obs = ["U"] * n_unknown + [rng.choice("TF") for _ in range(n_known)]
    unk = list(range(n_unknown))
    deps = []
    if k >= 2 and rng.random() < p_dep:
        a, b = rng.sample(range(k), 2)
        # 관측과 모순 없는 의존만 추가
        if not (obs[a] == "T" and obs[b] == "F"):
            deps.append([a, b])

    def lit(p_unk):
        v = rng.choice(unk) if (unk and rng.random() < p_unk) else rng.randrange(k)
        return [v, rng.randint(0, 1)]

    guidelines, actions, aid = [], [], 0
    for g in range(G):
        L = rng.choice([0, 1, 1, 2])
        app = []
        for _ in range(L):
            l = lit(app_on_unknown)
            if all(l[0] != x[0] for x in app):
                app.append(l)
        no = rng.choice(opts)
        guidelines.append({"app": app, "options": list(range(aid, aid + no))})
        aid += no
    x0 = rng.randint(55, 75); x1b = rng.randint(2, 6)
    x1var = rng.choice(unk) if (unk and rng.random() < p_shared) else None
    x1d = rng.choice([3, 4, 5]) if x1var is not None else 0
    cov = {"x0": x0, "x1_base": x1b, "x1_delta": x1d, "x1_var": x1var}
    for a in range(aid):
        if ev_mode == "all_supported":
            trial = BIG(x0, x1b, x1b + x1d)
        elif rng.random() < p_entry:
            cx = x0 + rng.randint(-5, 5); cy = x1b + rng.randint(-1, 3)
            slope = rng.choice([-1, 0, 1]); n = 10
            trial = []
            for _ in range(n):
                t = rng.randint(-15, 15)
                trial.append([cx + t, cy + (slope * t) // 3 + rng.randint(-3, 3)])
        else:
            trial = None
        actions.append(act(a, rng.randint(1, 4), rng.randint(0, 4), rng.randint(0, 3), trial))
    rules, seen = [], set()
    tries = 0
    while len(rules) < n_rules and tries < 50 and G >= 2:
        tries += 1
        g1, g2 = rng.sample(range(G), 2)
        a = rng.choice(guidelines[g1]["options"]); b = rng.choice(guidelines[g2]["options"])
        key = (min(a, b), max(a, b))
        if key in seen:
            continue
        seen.add(key)
        cond = [lit(rule_on_unknown)] if rng.random() < p_rule_cond else []
        rules.append({"a": key[0], "b": key[1], "cond": cond, "type": "conflict"})
    if rules and rng.random() < p_contra:
        r0 = rng.choice(rules)
        rules.append({"a": r0["a"], "b": r0["b"], "cond": [], "type": "compatible"})
    j1, j2 = rng.randint(-1, 1), rng.randint(-1, 1)
    c = [F(2, 5) + F(j1, 20), F(3, 10) + F(j2, 20)]
    c.append(1 - c[0] - c[1])
    params = dict(n_unknown=n_unknown, G=G, n_rules=n_rules, r=S(r), ev_mode=ev_mode, p_entry=p_entry,
                  p_shared=p_shared, p_contra=p_contra, family=family, level=level)
    return base(iid, exp, k, obs, guidelines, actions, rules, cov, W(c, r), deps, params)


def main():
    insts = hand_cases()
    # E1 B7만: 결측 없음, 점 선호, 근거 모두 지지
    rng = random.Random(1001)
    for i in range(100):
        insts.append(gen_random(rng, f"e1_{i}", "E1", n_unknown=0, n_known=4, r=F(0), ev_mode="all_supported", n_rules=4))
    rng = random.Random(1002)
    for i in range(100):  # E2 B7+B9
        insts.append(gen_random(rng, f"e2_{i}", "E2", n_unknown=0, n_known=4, r=F(1, 5), ev_mode="all_supported", n_rules=4))
    rng = random.Random(1003)
    for i in range(100):  # E3 B7+B10
        insts.append(gen_random(rng, f"e3_{i}", "E3", n_unknown=0, n_known=4, r=F(0), ev_mode="varied", n_rules=4))
    rng = random.Random(1004)
    for i in range(150):  # E4 B7+B9+B10
        insts.append(gen_random(rng, f"e4_{i}", "E4", n_unknown=2, n_known=2, r=F(1, 5), ev_mode="varied", n_rules=4))
    # E5 결측 수준: 같은 family seed 로 결측 수만 변화
    for fam in range(40):
        for nu in range(0, 6):
            rng = random.Random(5000 + fam)
            insts.append(gen_random(rng, f"e5_f{fam}_u{nu}", "E5", n_unknown=nu, n_known=5 - nu, r=F(1, 10),
                                    ev_mode="varied", n_rules=4, family=fam, level=nu))
    # E6 선호 범위: 같은 family 에서 r 만 변화
    for fam in range(40):
        for r in [F(0), F(1, 20), F(1, 10), F(1, 5), F(1, 3)]:
            rng = random.Random(6000 + fam)
            insts.append(gen_random(rng, f"e6_f{fam}_r{S(r).replace('/', '_')}", "E6", n_unknown=1, n_known=3, r=r,
                                    ev_mode="varied", n_rules=4, family=fam, level=S(r)))
    # E7 근거 정보량: 시험 항목 비율 / 공유 변수 비율 변화
    for fam in range(40):
        for lv, (pe, ps) in enumerate([(1.0, 0.0), (0.9, 0.0), (0.9, 1.0), (0.6, 1.0)]):
            rng = random.Random(7000 + fam)
            insts.append(gen_random(rng, f"e7_f{fam}_l{lv}", "E7", n_unknown=1, n_known=3, r=F(1, 10),
                                    ev_mode="varied", p_entry=pe, p_shared=ps, n_rules=4, family=fam, level=lv))
    # E8 확장성 (GT 계산 가능한 범위)
    for G in [2, 3, 4, 5]:
        for nu in [1, 3, 5]:
            for rep in range(5):
                rng = random.Random(8000 + 100 * G + 10 * nu + rep)
                insts.append(gen_random(rng, f"e8_G{G}_u{nu}_{rep}", "E8", n_unknown=nu, n_known=2, G=G, opts=(2, 3),
                                        n_rules=G + 1, r=F(1, 10), ev_mode="varied", family=f"G{G}", level=nu))
    rng = random.Random(1009)
    for i in range(60):  # E9 실제 충돌 없는 조합(수렴 후보)
        insts.append(gen_random(rng, f"e9_{i}", "E9", n_unknown=1, n_known=3, n_rules=0, r=F(1, 20), ev_mode="all_supported",
                                opts=(1, 2)))
    rng = random.Random(1010)
    for i in range(80):  # E10 겉보기 충돌(조건부 규칙, 대체 가능)
        insts.append(gen_random(rng, f"e10_{i}", "E10", n_unknown=2, n_known=2, n_rules=4, p_rule_cond=1.0,
                                rule_on_unknown=1.0, r=F(1, 10), ev_mode="all_supported", opts=(2, 3)))
    rng = random.Random(1011)
    for i in range(30):  # 정답 없음 후보(모순 규칙 주입)
        insts.append(gen_random(rng, f"enogt_{i}", "ENOGT", n_unknown=1, n_known=3, n_rules=3, p_contra=1.0,
                                r=F(1, 10), ev_mode="varied"))
    ids = [x["id"] for x in insts]
    assert len(ids) == len(set(ids))
    with open(os.path.join(HERE, "inputs", "instances.json"), "w") as f:
        json.dump({"note": "[합성] 형식 검증용 가상 입력. 의학적 사실 아님.", "instances": insts}, f, indent=0)
    print("instances", len(insts))


if __name__ == "__main__":
    main()
