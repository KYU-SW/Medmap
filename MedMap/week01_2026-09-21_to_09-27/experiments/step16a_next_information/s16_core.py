"""STEP16A core: 답변 의미(closed-world binary, 부모조건부 C/M), 인코더, 뷰 프로토콜, 모델, pool, selector, 시뮬레이터.
읽기 허용: release_evidences.json, TRAIN, Step8 evidence_concept_map(질환 무관 개념 매핑), Step14 taxonomy, frozen v2 profile facts/concepts.
금지: release_conditions.json의 symptoms/antecedents(어디에서도 읽지 않음), TEST(존재 확인만), VALIDATION(게이트 전).
"""
import json, os, hashlib, re, collections, math
import numpy as np, pandas as pd, scipy.sparse as sp
from dataclasses import dataclass, field
from sklearn.linear_model import LogisticRegression

ROOT = os.path.expanduser("~/medmap"); D = f"{ROOT}/data/ddxplus/en"; O = f"{ROOT}/exp/step16a_next_information"
TEST_PATH = f"{D}/release_test_patients"; VAL_PATH = f"{D}/release_validate_patients"; TRAIN_PATH = f"{D}/release_train_patients"
READ_LOG = []
class Step16AInvalid(Exception): pass
def guarded_path(path, phase):
    p = os.path.abspath(os.path.expanduser(path))
    if p == os.path.abspath(TEST_PATH): raise Step16AInvalid("STEP16A_INVALID_TEST_ACCESS")
    if p == os.path.abspath(VAL_PATH) and phase != "POST_FREEZE_APPROVED": raise Step16AInvalid("STEP16A_INVALID_PREREGISTRATION_ORDER")
    if p.endswith("release_conditions.json"): raise Step16AInvalid("STEP16A_CONDITIONS_FILE_FORBIDDEN")
    READ_LOG.append((phase, p)); return p
def test_exists_only(): return os.path.exists(TEST_PATH)  # Boolean만
def sha(p): h = hashlib.sha256(); f = open(p, "rb"); [h.update(c) for c in iter(lambda: f.read(1 << 24), b"")]; return h.hexdigest()

# ---------------- 답변 의미 ----------------
class Semantics:
    def __init__(self, phase="PRE_FREEZE"):
        self.ev = json.load(open(guarded_path(f"{D}/release_evidences.json", phase)))
        self.qids = sorted(self.ev, key=lambda e: int(e[2:]))
        self.parent = {e: v["code_question"] for e, v in self.ev.items() if v["code_question"] != e and v["code_question"] in self.ev}  # 실존 부모만 gate
        self.dtype = {e: v["data_type"] for e, v in self.ev.items()}
        self.default = {e: (str(v["default_value"]) if v["data_type"] != "B" else None) for e, v in self.ev.items()}
        self.values = {e: [str(x) for x in v["possible-values"]] for e, v in self.ev.items()}
        self.answer_space = {e: (["POS", "NEG"] if self.dtype[e] == "B" else [f"VALUE::{x}" for x in self.values[e]] + ["NA"]) for e in self.ev}
        self.global_simulatable = {e: True for e in self.ev}  # 감사 결과: binary=closed-world, C/M=토큰 또는 default/NA 복원 가능
    def reconstruct(self, qid, full_tokens):
        """hidden full record → 답변 상태. 시뮬레이터만 호출."""
        base = {t.split("_@_")[0]: t for t in full_tokens}
        if self.dtype[qid] == "B": return ("POS",) if qid in base else ("NEG",)
        vals = tuple(sorted(t.split("_@_")[1] for t in full_tokens if t.split("_@_")[0] == qid))
        if vals: return tuple(f"VALUE::{v}" for v in vals)
        par = self.parent.get(qid)
        if par and par not in base: return ("NA",)
        return (f"VALUE::{self.default[qid]}",)  # 부모 양성인데 토큰 없음 → default (구조감사: 부모 양성 시 자식 토큰은 항상 기록됨)
    def currently_eligible(self, qid, visible):
        """현재 visible state만 사용. 부모 gate: 부모 POS일 때만 자식 후보."""
        if qid in visible: return False
        par = self.parent.get(qid)
        if par: return visible.get(par) == ("POS",)
        return True

# ---------------- 인코더 ----------------
class Encoder:
    def __init__(self, sem):
        cols = []
        for e in sem.qids:
            for a in sem.answer_space[e]: cols.append(f"Q::{e}::{a}")
        for a in range(10): cols.append(f"AGE_{a}")
        for s in ["M", "F"]: cols.append(f"SEX_{s}")
        self.cols = cols; self.idx = {c: i for i, c in enumerate(cols)}
    def transform(self, states, ages, sexes):
        rows, cols = [], []
        for i, st in enumerate(states):
            for q, ans in st.items():
                for a in ans:
                    j = self.idx.get(f"Q::{q}::{a}")
                    if j is not None: rows.append(i); cols.append(j)
            rows.append(i); cols.append(self.idx[f"AGE_{min(int(ages[i])//10, 9)}"]); rows.append(i); cols.append(self.idx[f"SEX_{sexes[i]}"])
        return sp.csr_matrix((np.ones(len(rows), np.float32), (rows, cols)), shape=(len(states), len(self.cols)))

# ---------------- 뷰 프로토콜 (STEP16A_NEW_VIEW_PROTOCOL) ----------------
def make_view(sem, full_tokens, initial, k, split, seed, idx):
    """initial 공개 → 현재 eligible(부모 POS일 때만 자식) 집합에서 1개씩 k회 샘플, 공개 후 eligibility 갱신. 샘플 프레임은 hidden 답변을 보지 않음."""
    SPLIT_ID = {"train": 1, "validate": 2, "syn": 9}
    rng = np.random.default_rng([SPLIT_ID.get(split, 7), seed, idx]); visible = {initial: sem.reconstruct(initial, full_tokens)}
    top = [q for q in sem.qids if q not in sem.parent and q != initial]; children = collections.defaultdict(list)
    for ch, par in sem.parent.items(): children[par].append(ch)
    open_children = [ch for par in list(visible) for ch in children.get(par, []) if visible[par] == ("POS",)]
    for _ in range(k):
        elig = top + open_children
        if not elig: break
        q = elig[rng.integers(len(elig))]; visible[q] = sem.reconstruct(q, full_tokens)
        if q in top: top.remove(q)
        else: open_children.remove(q)
        if visible[q] == ("POS",): open_children += [ch for ch in children.get(q, []) if ch not in visible]
    return visible

def load_patients(path, phase, nrows=None):
    df = pd.read_csv(guarded_path(path, phase), nrows=nrows); df["tokens"] = df["EVIDENCES"].map(lambda s: json.loads(s.replace("'", '"'))); return df

# ---------------- 모델 ----------------
MODEL_CFG = dict(C=1.0, max_iter=300, solver="lbfgs", random_state=42)
def fit_model(X, y): m = LogisticRegression(**MODEL_CFG); m.fit(X, y); return m
def predict(model, enc, states, ages, sexes):
    P = model.predict_proba(enc.transform(states, ages, sexes)); order = np.argsort(-P, 1); return P, order

# ---------------- Internal IG (TRAIN-only) ----------------
def fit_ig_table(sem, train_df, classes, alpha=1.0):
    """P(a|d) = (count(d,a)+α)/(n_d+α|A_q|). TRAIN 전체 record를 closed-world로 복원해 계수(벡터화): binary POS=토큰 존재, NEG=n_d−POS;
    C/M: 각 값 토큰 계수, NA = 부모 gate 질문에서 부모 음성인 환자 수, default = 부모 양성(또는 gate 없음)인데 토큰 없는 환자 수. 다중값 M형은 값별 계수."""
    cidx = {c: i for i, c in enumerate(classes)}; n_d = np.zeros(len(classes)); aidx = {e: {a: i for i, a in enumerate(sem.answer_space[e])} for e in sem.qids}
    tab = {e: np.zeros((len(classes), len(sem.answer_space[e]))) for e in sem.qids}; has_any = {e: np.zeros(len(classes)) for e in sem.qids}; parent_pos = {e: np.zeros(len(classes)) for e in sem.qids}
    for toks, y in zip(train_df["tokens"], train_df["PATHOLOGY"]):
        d = cidx[y]; n_d[d] += 1; base = set()
        for t in toks:
            e, _, v = t.partition("_@_"); base.add(e)
            if sem.dtype[e] == "B": tab[e][d, aidx[e]["POS"]] += 1
            else: tab[e][d, aidx[e][f"VALUE::{v}"]] += 1
        for e in base: has_any[e][d] += 1
        for e, par in sem.parent.items():
            if par in base: parent_pos[e][d] += 1
    for e in sem.qids:
        if sem.dtype[e] == "B": tab[e][:, aidx[e]["NEG"]] = n_d - tab[e][:, aidx[e]["POS"]]
        else:
            par = sem.parent.get(e)
            if par: tab[e][:, aidx[e]["NA"]] += n_d - parent_pos[e]; tab[e][:, aidx[e][f"VALUE::{sem.default[e]}"]] += np.maximum(parent_pos[e] - has_any[e], 0)
            else: tab[e][:, aidx[e][f"VALUE::{sem.default[e]}"]] += n_d - has_any[e]
    return {e: (tab[e] + alpha) / (tab[e].sum(1, keepdims=True) + alpha * tab[e].shape[1]) for e in sem.qids}, alpha
def entropy(p): p = p[p > 0]; return float(-(p * np.log2(p)).sum())
def ig_scores(post, cands, ig_table):
    H0 = entropy(post); out = {}
    for q in cands:
        Pa_d = ig_table[q]; Pa = post @ Pa_d; exp_H = 0.0
        for j in range(Pa_d.shape[1]):
            if Pa[j] <= 0: continue
            post_a = post * Pa_d[:, j]; post_a /= post_a.sum(); exp_H += Pa[j] * entropy(post_a)
        out[q] = H0 - exp_H
    return out

# ---------------- Profile contrasts (PRIMARY: fact-only 일반 규칙) ----------------
ATTR_FIELDS = ["location", "severity", "onset", "duration", "frequency", "progression", "trigger", "aggravating_factor", "relieving_factor"]
ATTR_TO_TYPE = {"location": {"ANATOMICAL_LOCATION"}, "severity": {"SEVERITY"}, "onset": {"TEMPORAL"}, "duration": {"TEMPORAL"}, "frequency": {"FREQUENCY", "TEMPORAL"}, "progression": {"TEMPORAL"}, "trigger": {"TEMPORAL"}, "aggravating_factor": {"TEMPORAL"}, "relieving_factor": {"TEMPORAL"}}
def build_fact_evidence_map(facts, concepts, ev_map, taxonomy):
    """질환 무관 기계 매핑: fact base concept CUI/HPO == evidence concept CUI/HPO (Step8, 질환 무관). 이름 일치는 보조(partial)."""
    C = concepts.set_index("fact_id"); rows = []
    ev_cui = {e: {r.concept_1_cui, r.concept_2_cui} - {""} for e, r in ev_map.iterrows()}; ev_hpo = {e: {r.concept_1_hpo.split(";")[0], r.concept_2_hpo.split(";")[0]} - {""} for e, r in ev_map.iterrows()}; ev_name = {e: {r.concept_1.lower(), r.concept_2.lower()} - {""} for e, r in ev_map.iterrows()}
    for f in facts.itertuples():
        c = C.loc[f.fact_id]; cui, hpo = c.umls_cui, c.hpo_id
        for e in ev_map.index:
            direct = (cui and cui in ev_cui[e]) or (hpo and hpo in ev_hpo[e]); fb = f.base_concept.lower()
            partial = (not direct) and any(fb == n or (len(fb) >= 5 and (fb in n or n in fb)) for n in ev_name[e])  # 일반 규칙: 개념명 동일 또는 부분문자열(≥5자) 포함
            if not (direct or partial): continue
            e_types = {taxonomy.loc[e, "primary_type"]} | set(taxonomy.loc[e, "secondary_types"].split(";")) - {""}
            f_attrs = [a for a in ATTR_FIELDS if getattr(f, a)]; attr_level = any(ATTR_TO_TYPE[a] & e_types for a in f_attrs)
            rows.append({"fact_id": f.fact_id, "disease": f.disease, "evidence_id": e, "match": "DIRECT" if direct else "PARTIAL", "attribute_level": attr_level, "fact_attrs": ";".join(f"{a}={getattr(f, a)}" for a in f_attrs), "polarity": f.positive_or_negative, "base_concept": f.base_concept})
    return pd.DataFrame(rows)
def contrast_priority(fe_map, A, B, e):
    """일반 규칙(모든 pair 동일): EXPLICIT_POSITIVE_NEGATIVE 또는 EXPLICIT_CONTRAST(동일 개념·속성값 상이·evidence가 속성 수준) → 2; 개념 partial 매칭으로만 대비 → 1; one-sided(UNKNOWN) → 0."""
    fa = fe_map[(fe_map.disease == A) & (fe_map.evidence_id == e)]; fb = fe_map[(fe_map.disease == B) & (fe_map.evidence_id == e)]
    if len(fa) == 0 or len(fb) == 0: return 0, "ONE_SIDED_UNKNOWN"
    pa, pb = set(fa.polarity), set(fb.polarity)
    if ("positive" in pa and "negative" in pb) or ("negative" in pa and "positive" in pb): return 2, "EXPLICIT_POSITIVE_NEGATIVE"
    aa, ab = set(fa.fact_attrs) - {""}, set(fb.fact_attrs) - {""}
    if aa != ab and (fa.attribute_level.any() or fb.attribute_level.any()): return 2, "EXPLICIT_CONTRAST"
    if aa != ab: return 1, "ATTRIBUTE_DIFF_NOT_OBSERVABLE_AS_ATTRIBUTE"
    return 0, "SAME_ON_BOTH"

# ---------------- pools & selectors ----------------
def full_pool(sem, visible): return [q for q in sem.qids if sem.global_simulatable[q] and sem.currently_eligible(q, visible)]
def common_pool(sem, visible, fe_map, A, B): return [q for q in full_pool(sem, visible) if contrast_priority(fe_map, A, B, q)[0] > 0]
def qnum(q): return int(q[2:])
def select_random(pool, rng): return pool[rng.integers(len(pool))] if pool else None
def select_ig(pool, post, ig_table):
    if not pool: return None
    s = ig_scores(post, pool, ig_table); return sorted(pool, key=lambda q: (-round(s[q], 12), qnum(q)))[0]
def select_profile(pool, fe_map, A, B):
    scored = [(contrast_priority(fe_map, A, B, q)[0], q) for q in pool]; scored = [x for x in scored if x[0] > 0]
    return sorted(scored, key=lambda x: (-x[0], qnum(x[1])))[0][1] if scored else None  # None = ABSTAIN
def select_hybrid(pool, fe_map, A, B, post, ig_table):
    sub = [q for q in pool if contrast_priority(fe_map, A, B, q)[0] > 0]; return select_ig(sub, post, ig_table)

FORBIDDEN_KEYS = {"true_diagnosis", "truth", "PATHOLOGY", "full_patient_evidence", "hidden_answers", "future_answer", "tokens", "EVIDENCES"}
def selector_input(visible, post, top, pool, seed):
    payload = {"visible": {q: list(a) for q, a in visible.items()}, "posterior": post.tolist(), "top": top, "pool": pool, "seed": seed}
    assert not (set(payload) & FORBIDDEN_KEYS); return payload
