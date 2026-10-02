"""STEP16B core — 안전한 질문-답 의미(V2), 80/20 결정론적 split, 뷰 프로토콜, 모델, IG, pool, selector.
읽기 허용: release_evidences.json, release_train_patients, STEP16A 04b contrast table(읽기 전용).
영구 금지: release_validate_patients, release_test_patients, release_conditions.json.
"""
import json, os, hashlib, collections
import numpy as np, pandas as pd, scipy.sparse as sp
from sklearn.linear_model import LogisticRegression

ROOT = os.environ.get("MEDMAP_ROOT", os.path.expanduser("~/medmap")); D = f"{ROOT}/data/ddxplus/en"  # MEDMAP_ROOT=<MedMap/code 경로>로 바꿀 수 있음
O = f"{ROOT}/exp/step16b_next_information_validation"; A16 = f"{ROOT}/exp/step16a_next_information"
TRAIN_PATH = f"{D}/release_train_patients"; VAL_PATH = f"{D}/release_validate_patients"; TEST_PATH = f"{D}/release_test_patients"
EXCLUDED = ("E_134", "E_152")
SPLIT_ID = {"step16b_train": 11, "step16b_holdout": 12, "smoke": 91}
READ_LOG = []
class Step16BInvalid(Exception): pass

def guarded_path(path):
    p = os.path.abspath(os.path.expanduser(path))
    if p in (os.path.abspath(VAL_PATH), os.path.abspath(TEST_PATH)): raise Step16BInvalid("STEP16B_INVALID_SPLIT_ACCESS")
    if p.endswith("release_conditions.json"): raise Step16BInvalid("STEP16B_CONDITIONS_FILE_FORBIDDEN")
    READ_LOG.append(p); return p

def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 24), b""): h.update(c)
    return h.hexdigest()

# ---------------- 분할 (사전등록 §2) ----------------
def split_key(row_index, age, sex, pathology, evidences):
    return hashlib.sha256(f"{row_index}|{age}|{sex}|{pathology}|{evidences}".encode()).hexdigest()
def is_holdout(key): return int(key[:8], 16) % 10 < 2

# ---------------- 답변 의미 V2 ----------------
class Semantics:
    def __init__(self):
        self.ev = json.load(open(guarded_path(f"{D}/release_evidences.json")))
        self.qids = sorted(self.ev, key=lambda e: int(e[2:]))
        self.parent = {e: v["code_question"] for e, v in self.ev.items() if v["code_question"] != e and v["code_question"] in self.ev}
        self.dtype = {e: v["data_type"] for e, v in self.ev.items()}
        self.values = {e: [str(x) for x in v["possible-values"]] for e, v in self.ev.items()}
        self.answer_space = {e: (["POS", "NEG"] if self.dtype[e] == "B" else [f"VALUE::{x}" for x in self.values[e]] + ["NA"]) for e in self.ev}
        self.excluded = set(EXCLUDED)
        self.safe = {e: (e not in self.excluded) for e in self.ev}
        self.unsafe_encounters = collections.Counter()
    def reconstruct(self, qid, full_tokens):
        """hidden full record → 답변 상태. 시뮬레이터만 호출. default 생성 금지."""
        base = {t.partition("_@_")[0] for t in full_tokens}
        if self.dtype[qid] == "B": return ("POS",) if qid in base else ("NEG",)
        vals = tuple(sorted(t.partition("_@_")[2] for t in full_tokens if t.partition("_@_")[0] == qid))
        if vals: return tuple(f"VALUE::{v}" for v in vals)
        par = self.parent.get(qid)
        if par and par not in base: return ("NA",)
        self.unsafe_encounters[qid] += 1
        raise Step16BInvalid(f"STEP16B_INVALID_ANSWER_SEMANTICS:UNSAFE:{qid}")  # parent positive/no parent + 토큰 없음
    def currently_eligible(self, qid, visible):
        if qid in visible or not self.safe[qid]: return False
        par = self.parent.get(qid)
        if par: return visible.get(par) == ("POS",)
        return True

class Encoder:
    def __init__(self, sem):
        cols = [f"Q::{e}::{a}" for e in sem.qids for a in sem.answer_space[e]] + [f"AGE_{a}" for a in range(10)] + ["SEX_M", "SEX_F"]
        self.cols = cols; self.idx = {c: i for i, c in enumerate(cols)}
    def transform(self, states, ages, sexes):
        rows, cols = [], []
        for i, st in enumerate(states):
            for q, ans in st.items():
                for a in ans:
                    j = self.idx.get(f"Q::{q}::{a}")
                    if j is None: raise Step16BInvalid(f"STEP16B_INVALID_ENCODING:{q}:{a}")
                    rows.append(i); cols.append(j)
            rows.append(i); cols.append(self.idx[f"AGE_{min(int(ages[i]) // 10, 9)}"]); rows.append(i); cols.append(self.idx[f"SEX_{sexes[i]}"])
        return sp.csr_matrix((np.ones(len(rows), np.float32), (rows, cols)), shape=(len(states), len(self.cols)))

# ---------------- 뷰 프로토콜 ----------------
def make_view(sem, full_tokens, initial, k, split, seed, idx):
    rng = np.random.default_rng([SPLIT_ID[split], seed, idx]); visible = {initial: sem.reconstruct(initial, full_tokens)}
    children = collections.defaultdict(list)
    for ch, par in sem.parent.items():
        if sem.safe[ch]: children[par].append(ch)
    top = [q for q in sem.qids if q not in sem.parent and q != initial and sem.safe[q]]
    open_children = [ch for ch in children.get(initial, []) if visible[initial] == ("POS",)]
    for _ in range(k):
        elig = top + open_children
        if not elig: break
        q = elig[rng.integers(len(elig))]; visible[q] = sem.reconstruct(q, full_tokens)
        (top if q in top else open_children).remove(q)
        if visible[q] == ("POS",): open_children += [ch for ch in children.get(q, []) if ch not in visible]
    return visible

def load_train(nrows=None):
    df = pd.read_csv(guarded_path(TRAIN_PATH), nrows=nrows)
    df["row_index"] = np.arange(len(df))
    df["split_key"] = [split_key(i, a, s, p, e) for i, a, s, p, e in zip(df.row_index, df.AGE, df.SEX, df.PATHOLOGY, df.EVIDENCES)]
    df["holdout"] = df.split_key.map(is_holdout)
    df["tokens"] = df["EVIDENCES"].map(lambda s: json.loads(s.replace("'", '"')))
    return df

MODEL_CFG = dict(C=1.0, max_iter=300, solver="lbfgs", random_state=42)
def fit_model(X, y): m = LogisticRegression(**MODEL_CFG); m.fit(X, y); return m

# ---------------- Internal IG (STEP16B_TRAIN only) ----------------
def fit_ig_table(sem, tokens_list, labels, classes, alpha=1.0):
    cidx = {c: i for i, c in enumerate(classes)}; nC = len(classes)
    aidx = {e: {a: i for i, a in enumerate(sem.answer_space[e])} for e in sem.qids}
    tab = {e: np.zeros((nC, len(sem.answer_space[e]))) for e in sem.qids}
    has_any = {e: np.zeros(nC) for e in sem.qids}; parent_pos = {e: np.zeros(nC) for e in sem.qids}; n_d = np.zeros(nC)
    for toks, y in zip(tokens_list, labels):
        d = cidx[y]; n_d[d] += 1; base = set()
        for t in toks:
            e, _, v = t.partition("_@_"); base.add(e)
            if sem.dtype[e] == "B": tab[e][d, aidx[e]["POS"]] += 1
            else: tab[e][d, aidx[e][f"VALUE::{v}"]] += 1
        for e in base: has_any[e][d] += 1
        for e, par in sem.parent.items():
            if par in base: parent_pos[e][d] += 1
    missing = {}
    for e in sem.qids:
        if sem.dtype[e] == "B": tab[e][:, aidx[e]["NEG"]] = n_d - tab[e][:, aidx[e]["POS"]]
        else:
            par = sem.parent.get(e)
            pp = parent_pos[e] if par else n_d
            miss = np.maximum(pp - has_any[e], 0); missing[e] = float(miss.sum())
            if sem.safe[e] and missing[e] > 0: raise Step16BInvalid(f"STEP16B_INVALID_ANSWER_SEMANTICS:IG:{e}:{missing[e]}")
            tab[e][:, aidx[e]["NA"]] = np.maximum(n_d - has_any[e] - miss, 0)
    return {e: (tab[e] + alpha) / (tab[e].sum(1, keepdims=True) + alpha * tab[e].shape[1]) for e in sem.qids}, missing

def pack_ig(sem, ig_table):
    """질문별 P(a|d)를 (nC, total_answers) 하나로 스택 + 열→질문 그룹. 뷰당 1회 행렬연산으로 모든 질문 IG."""
    qs = [e for e in sem.qids if sem.safe[e]]
    M = np.concatenate([ig_table[e] for e in qs], 1); grp = np.concatenate([np.full(ig_table[e].shape[1], i) for i, e in enumerate(qs)])
    return qs, {q: i for i, q in enumerate(qs)}, M, grp

def ig_all(post, M, grp, nq):
    Pa = post @ M
    W = post[:, None] * M
    s = W.sum(0); s[s <= 0] = 1.0; W = W / s
    L = np.where(W > 0, np.log2(np.where(W > 0, W, 1.0)), 0.0)
    Hcol = -(W * L).sum(0)
    expH = np.bincount(grp, weights=Pa * Hcol, minlength=nq)
    p = post[post > 0]; H0 = float(-(p * np.log2(p)).sum())
    return H0 - expH

def qnum(q): return int(q[2:])

FORBIDDEN_KEYS = {"true_diagnosis", "truth", "PATHOLOGY", "full_patient_evidence", "hidden_answers", "future_answer", "tokens", "EVIDENCES"}
def selector_input(visible, post, top, pool, seed):
    payload = {"visible": {q: list(a) for q, a in visible.items()}, "posterior": post, "top": top, "pool": pool, "seed": seed}
    assert not (set(payload) & FORBIDDEN_KEYS); return payload
