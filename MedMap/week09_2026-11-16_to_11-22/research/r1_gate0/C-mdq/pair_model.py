"""연속 W 의 정확 유한 가설(=(세계, 선호 완전응답 셀) 쌍, 라벨은 꼭짓점 인증)을 GridModel 인터페이스로 감싼 어댑터.
목적: (1) exact_grid 의 8/7 코드와 methods 의 milp 코드를 '정확 라벨' 위에서 돌려 9a/9b 와 독립 대조,
      (2) 효용이 필요 없는 기준선(무작위/고정/탐욕/EC2/hitting set)을 이산화 오차 없이 비교."""
import numpy as np
from core import GridModel, world_prior


class PairModel(GridModel):
    def __init__(self, C):
        self.inst = C.inst
        self.T = C.T
        self.nA = len(C.pairs)
        self.g = list(C.labels)
        self.ans = C.pans.copy()
        self.cost = C.cost.copy()
        self.w_unif = C.wt / C.wt.sum()
        wp = world_prior(C.inst, [tuple(s) for s in C.worlds], C.inst.prior_T)
        tv = sum(c[2] for c in C.cells)
        self.w_skew = np.array([wp[wi] * C.cells[ci][2] / tv for (wi, ci) in C.pairs])
        self.masks = []
        for t in range(self.T):
            mk = {}
            for a in range(self.nA):
                v = int(self.ans[t, a])
                mk[v] = mk.get(v, 0) | (1 << a)
            self.masks.append(mk)
        self.ALL = (1 << self.nA) - 1
        self.label_mask = {}
        for a in range(self.nA):
            self.label_mask[self.g[a]] = self.label_mask.get(self.g[a], 0) | (1 << a)
        self.nbytes = (self.nA + 7) // 8
