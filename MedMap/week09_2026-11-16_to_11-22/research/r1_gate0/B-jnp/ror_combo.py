"""[4] 상태별 ROR 반복 후 forall/exists 결합 (naive 조합 기준선). SYNTHETIC.

두 변형:
  ror_pw_combo : 상태마다 ror_pairwise (가능 최선 = pairwise 근사) -> 결합.
  ror_lp_combo : 상태마다 pref_lp (가능 최선 = 정확 LP) -> 결합. "기존 상태열거 + 강건선호 LP" 조합.
결합: AA=all(nec), EE=any(pos), AE=all(pos), EA=any(nec).
EwAs (exists w forall s): naive 조합은 상태별 결과만 갖고 있어 '하나의 w' 조건을 표현할 수 없음 ->
  naive 규칙 EwAs := AE (상태별로 가능하면 공통 가중치도 있다고 간주; 흔한 혼동) 로 둔다.
상태 열거는 자체 구현, (적격, 점수) 서명 캐시 사용 (정확성 보존).
"""
import itertools
import numpy as np
import pref_lp
import ror_pairwise


def worlds(inst):
    k, obs = inst['k'], inst['obs']
    free = [i for i in range(k) if obs[i] in ('U', 'C')]
    S = []
    for bits in itertools.product((0, 1), repeat=len(free)):
        s = [1 if o == 'T' else 0 for o in obs]
        for i, b in zip(free, bits):
            s[i] = b
        if all(not (t == 'imp' and s[a] and not s[b]) and not (t == 'excl' and s[a] and s[b])
               for t, a, b in inst['deps']):
            S.append(tuple(s))
    return S


def elig(inst, s):
    el = [True] * inst['n']
    for o, lits in inst['rules']:
        if all(s[i] == v for i, v in lits):
            el[o] = False
    return tuple(el)


def solve(inst, variant='lp'):
    n = inst['n']
    Wsys = pref_lp.w_system(inst)
    S = worlds(inst)
    if not S:
        return dict(flags={o: [0, 0, 0, 0, 0] for o in range(n)},
                    cat={o: 'INSUFFICIENT' for o in range(n)}, n_worlds=0)
    miss = any(v is None for row in inst['base'] for v in row)
    cache = {}
    per = {o: [] for o in range(n)}
    for s in S:
        el = elig(inst, s)
        for o in range(n):
            Vn = pref_lp.scores(inst, s, o, 'nec' if miss else None)
            Vp = pref_lp.scores(inst, s, o, 'pos' if miss else None)
            key = (o, el, Vn.tobytes(), Vp.tobytes())
            if key not in cache:
                if variant == 'lp':
                    cache[key] = (pref_lp.nec(Vn, el, o, Wsys), pref_lp.pos(Vp, el, o, Wsys))
                else:
                    kn = ('pw', el, Vn.tobytes()); kp = ('pw', el, Vp.tobytes())
                    if kn not in cache:
                        cache[kn] = ror_pairwise.best_flags(Vn, el, Wsys)
                    if kp not in cache:
                        cache[kp] = ror_pairwise.best_flags(Vp, el, Wsys)
                    cache[key] = (cache[kn][o][0], cache[kp][o][1])
            per[o].append(cache[key])
    flags = {}
    for o in range(n):
        N = [x[0] for x in per[o]]; P = [x[1] for x in per[o]]
        AE = all(P)
        flags[o] = [int(all(N)), int(any(P)), int(AE), int(any(N)), int(AE)]
    return dict(flags=flags, cat=pref_lp.categorize(inst, flags, Wsys), n_worlds=len(S))
