"""잘못 설계하기 쉬운 단순 기준선 (실패 사례 탐색용, 신규성 근거로 쓰지 않음). SYNTHETIC.

 (a) closed_world   : U -> F, 상충(C) -> 마지막 기록값(cw), 의존성 무시. 단일 상태에서 정확 LP.
 (b) ignore_unknown : 미확인 조건이 들어간 금기 규칙/점수 수정을 무시(발동 안 함), 확정 조건만 반영. 단일 상태 정확 LP.
 (c) penalty_P      : 안전 제약을 hard 가 아닌 벌점(부적격이면 효용 - P)으로 섞음. 상태 열거와 양화는 정확하게 함.
 (d) vertex_only    : exists w 판정을 W 의 꼭짓점에서만 검사 (forall w 는 정확). 상태 열거·양화 정확.
단일 상태 방법의 플래그: AA=EA=nec, EE=AE=EwAs=pos.
"""
import numpy as np
import pref_lp
import ror_combo
from exact_enum import vertices, w_constraints


def _single_state(inst, s, el):
    Wsys = pref_lp.w_system(inst)
    n = inst['n']
    flags = {}
    for o in range(n):
        nv, pv = pref_lp.state_flags(inst, s, el, o, Wsys)
        flags[o] = [int(nv), int(pv), int(pv), int(nv), int(pv)]
    return dict(flags=flags, cat=pref_lp.categorize(inst, flags, Wsys))


def closed_world(inst):
    s = []
    for i, o in enumerate(inst['obs']):
        s.append(1 if o == 'T' or (o == 'C' and inst['cw'][i] == 'T') else 0)
    return _single_state(inst, tuple(s), ror_combo.elig(inst, s))


def ignore_unknown(inst):
    known = [o in ('T', 'F') for o in inst['obs']]
    inst2 = dict(inst)
    inst2['rules'] = [r for r in inst['rules'] if all(known[i] for i, _ in r[1])]
    inst2['mods'] = [md for md in inst['mods'] if known[md[2]]]
    s = tuple(1 if o == 'T' else 0 for o in inst['obs'])
    return _single_state(inst2, s, ror_combo.elig(inst2, s))


def penalty(inst, P):
    n = inst['n']
    Wsys = pref_lp.w_system(inst)
    S = ror_combo.worlds(inst)
    if not S:
        return dict(flags={o: [0, 0, 0, 0, 0] for o in range(n)}, cat={o: 'INSUFFICIENT' for o in range(n)})
    miss = any(v is None for row in inst['base'] for v in row)
    allel = tuple([True] * n)
    per = {o: [] for o in range(n)}
    rows_all = {o: [] for o in range(n)}
    cache = {}
    for s in S:
        el = ror_combo.elig(inst, s)
        for o in range(n):
            Vn = pref_lp.scores(inst, s, o, 'nec' if miss else None)
            Vp = pref_lp.scores(inst, s, o, 'pos' if miss else None)
            for q in range(n):
                if not el[q]:
                    Vn[q] -= P; Vp[q] -= P   # sum w = 1 -> U - P
            key = (o, Vn.tobytes(), Vp.tobytes())
            if key not in cache:
                cache[key] = (pref_lp.nec(Vn, allel, o, Wsys), pref_lp.pos(Vp, allel, o, Wsys))
            per[o].append(cache[key])
            rows_all[o] += [Vp[o] - Vp[q] for q in range(n) if q != o]
    flags = {}
    for o in range(n):
        N = [x[0] for x in per[o]]; Pp = [x[1] for x in per[o]]
        AE = all(Pp)
        EwAs = AE and pref_lp.pos_multi(rows_all[o], Wsys)
        flags[o] = [int(all(N)), int(any(Pp)), int(AE), int(any(N)), int(EwAs)]
    return dict(flags=flags, cat=pref_lp.categorize(inst, flags, Wsys))


def vertex_only(inst):
    n = inst['n']
    Wsys = pref_lp.w_system(inst)
    G, h = w_constraints(inst)
    WV = vertices(G, h)
    S = ror_combo.worlds(inst)
    if not S:
        return dict(flags={o: [0, 0, 0, 0, 0] for o in range(n)}, cat={o: 'INSUFFICIENT' for o in range(n)})
    miss = any(v is None for row in inst['base'] for v in row)
    flags = {}
    for o in range(n):
        N, Pp, okv = [], [], np.ones(len(WV), bool)
        for s in S:
            el = ror_combo.elig(inst, s)
            if not el[o]:
                N.append(False); Pp.append(False); okv[:] = False; continue
            Vn = pref_lp.scores(inst, s, o, 'nec' if miss else None)
            Vp = pref_lp.scores(inst, s, o, 'pos' if miss else None)
            comps = [q for q in range(n) if q != o and el[q]]
            Un = WV @ Vn.T; Up = WV @ Vp.T
            N.append(all(np.all(Un[:, o] >= Un[:, q] - 1e-9) for q in comps))
            best_at_v = np.all([Up[:, o] >= Up[:, q] - 1e-9 for q in comps], axis=0) if comps else np.ones(len(WV), bool)
            Pp.append(bool(best_at_v.any()))
            okv &= best_at_v
        AE = all(Pp)
        flags[o] = [int(all(N)), int(any(Pp)), int(AE), int(any(N)), int(AE and okv.any())]
    return dict(flags=flags, cat=pref_lp.categorize(inst, flags, Wsys))
