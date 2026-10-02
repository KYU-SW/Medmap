"""STEP17A core — split(STEP16B_TRAIN 내부), 시작 상태 R0~R3/R3-MASK, 평가 함수.
STEP16B 코어(s16b_core)는 수정 없이 import해 답 의미 V2·Encoder·make_view·IG·가드를 그대로 재사용한다.
영구 금지: 원본 VALIDATION/TEST/conditions(코어 가드), STEP16B_HOLDOUT 행의 토큰·라벨 사용.
"""
import os, sys, json, hashlib, collections, time
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
S16 = os.path.expanduser("~/medmap/exp/step16b_next_information_validation")
sys.path.insert(0, S16)
import s16b_core as c  # noqa: E402

c.SPLIT_ID.update({"step17a_dev": 21, "step17a_holdout": 22, "step17a_smoke": 93})
SEEDS = (42, 43, 44)
RSEEDS = list(range(1000, 1050))
STEPS = 3
CONDS = ("R0", "R1", "R2", "R3", "R3MASK")
COND_CODE = {"R1": 101, "R3": 103, "R3MASK": 113}
FIXED = ["E_91", "E_53", "E_66"]
BACKUP = ["E_201", "E_175", "E_88"]
MASK_KEEP = 0.6834
MAPPER_SUPPORTED_41 = ("E_0 E_9 E_33 E_45 E_50 E_53 E_66 E_69 E_70 E_77 E_78 E_79 E_88 E_89 E_91 E_104 E_105 E_112 E_116 "
                       "E_120 E_123 E_124 E_129 E_148 E_151 E_155 E_169 E_175 E_181 E_182 E_189 E_194 E_201 E_209 E_212 "
                       "E_214 E_216 E_218 E_220 E_221 E_226").split()
NEVER_INITIAL_14 = "E_0 E_69 E_70 E_78 E_79 E_104 E_105 E_116 E_120 E_123 E_124 E_189 E_209 E_226".split()
KO27 = [e for e in MAPPER_SUPPORTED_41 if e not in NEVER_INITIAL_14]
assert len(MAPPER_SUPPORTED_41) == 41 and len(KO27) == 27
S16_MAN = json.load(open(f"{S16}/01_split_manifest.json"))


class Step17AInvalid(Exception):
    pass


def log(t0, m):
    print(f"[{time.time() - t0:7.0f}s] {m}", flush=True)


def sha_str(s):
    return hashlib.sha256(s.encode()).hexdigest()


def key17(split_key16):
    return sha_str("step17a|" + split_key16)


def is_holdout17(k):
    return int(k[:8], 16) % 5 == 0


def load_step16b_train():
    """원본 TRAIN 로드 → STEP16B_HOLDOUT 소속만 판정해 즉시 제거(토큰·라벨 미사용) → key17 부여."""
    df = c.load_train()
    ho16 = df.holdout.values
    n16 = int(ho16.sum())
    ho_idx_sha = sha_str(",".join(map(str, df.row_index.values[ho16])))
    if n16 != S16_MAN["holdout_rows"] or ho_idx_sha != S16_MAN["holdout_row_index_sha256"]:
        raise Step17AInvalid("STEP17A_INVALID_STEP16B_HOLDOUT_MEMBERSHIP")
    tr = df[~df.holdout].reset_index(drop=True)
    del df
    tr["key17"] = [key17(k) for k in tr.split_key.values]
    tr["ho17"] = [is_holdout17(k) for k in tr.key17.values]
    return tr, {"step16b_holdout_rows_dropped": n16, "step16b_holdout_row_index_sha256_verified": ho_idx_sha}


def split_manifest(tr):
    dev = tr[~tr.ho17]
    ho = tr[tr.ho17]
    return {
        "source": "STEP16B_TRAIN (release_train_patients minus STEP16B_HOLDOUT)",
        "step16b_train_rows": int(len(tr)), "dev_rows": int(len(dev)), "holdout_rows": int(len(ho)),
        "holdout_fraction": float(tr.ho17.mean()),
        "rule": 'key17 = sha256("step17a|" + step16b_split_key); holdout iff int(key17[:8],16) % 5 == 0',
        "key17_stream_sha256": sha_str("".join(tr.key17.values)),
        "dev_row_index_sha256": sha_str(",".join(map(str, dev.row_index.values))),
        "holdout_row_index_sha256": sha_str(",".join(map(str, ho.row_index.values))),
    }


# ---------------- 시작 상태 ----------------
class ViewBuilder:
    def __init__(self, sem):
        self.sem = sem
        self.children = collections.defaultdict(list)
        for ch, par in sem.parent.items():
            if sem.safe[ch]:
                self.children[par].append(ch)
        self.top = [q for q in sem.qids if q not in sem.parent and sem.safe[q]]
        self.supported = set(MAPPER_SUPPORTED_41)

    def _pos_binary(self, toks, initial):
        base = {t.partition("_@_")[0] for t in toks}
        return sorted([q for q in base if self.sem.dtype[q] == "B" and self.sem.safe[q] and q != initial
                       and q not in self.sem.parent], key=c.qnum)

    def _reveal(self, visible, q, toks):
        visible[q] = self.sem.reconstruct(q, toks)

    def _fill_random(self, visible, toks, rng, n):
        for _ in range(n):
            open_ch = [ch for par, a in visible.items() if a == ("POS",) for ch in self.children.get(par, []) if ch not in visible]
            elig = [q for q in self.top if q not in visible] + open_ch
            if not elig:
                return
            self._reveal(visible, elig[rng.integers(len(elig))], toks)

    def _fill_fixed(self, visible, toks, n):
        for q in FIXED + BACKUP:
            if n == 0:
                return
            if q in visible:
                continue
            self._reveal(visible, q, toks)
            n -= 1

    def build(self, cond, toks, initial, split, seed, idx):
        """→ (visible dict, valid bool). valid = 추가 정확히 3개."""
        if cond == "R0":
            v = c.make_view(self.sem, toks, initial, 3, split, seed, idx)
            return v, len(v) == 4
        visible = {initial: self.sem.reconstruct(initial, toks)}
        if cond == "R2":
            self._fill_fixed(visible, toks, 3)
            return visible, len(visible) == 4
        rng = np.random.default_rng([c.SPLIT_ID[split], seed, idx, COND_CODE[cond]])
        pool = self._pos_binary(toks, initial)
        if cond in ("R3", "R3MASK"):
            pool = [q for q in pool if q in self.supported]
        if cond == "R3MASK":
            u = rng.random(len(pool))
            pool = [q for q, x in zip(pool, u) if x < MASK_KEEP]
        pool = [pool[i] for i in rng.permutation(len(pool))][:3]
        for q in pool:
            self._reveal(visible, q, toks)
        need = 4 - len(visible)
        if cond == "R1":
            self._fill_random(visible, toks, rng, need)
        else:
            self._fill_fixed(visible, toks, need)
        return visible, len(visible) == 4


# ---------------- 평가 ----------------
def evaluate(rows, sim_n, model, ig_table, classes, split, t0, conds=CONDS, seeds=SEEDS):
    """rows: DataFrame(tokens, INITIAL_EVIDENCE, AGE, SEX, PATHOLOGY, row_index, key17), key17 오름차순.
    반환: (initial DataFrame, sim DataFrame(1Q/3Q), audit Counter)"""
    sem = c.Semantics()
    enc = c.Encoder(sem)
    vb = ViewBuilder(sem)
    qs, qpos, MIG, grp = c.pack_ig(sem, ig_table)
    NQ = len(qs)
    QN = {q: c.qnum(q) for q in sem.qids}
    CI = {cc: i for i, cc in enumerate(classes)}
    if list(model.classes_) != list(classes):
        raise Step17AInvalid("STEP17A_CLASS_ORDER_MISMATCH")
    aud = collections.Counter()
    toks = rows.tokens.tolist()
    ini = rows.INITIAL_EVIDENCE.values
    ridx = rows.row_index.values
    ages, sexes = rows.AGE.values, rows.SEX.values
    truth = np.array([CI[p] for p in rows.PATHOLOGY.values])
    agents = [("RANDOM", s) for s in RSEEDS] + [("INTERNAL_IG", 0)]
    init_out, sim_out = [], []
    for cond in conds:
        for seed in seeds:
            t = time.time()
            built = [vb.build(cond, toks[i], ini[i], split, seed, int(ridx[i])) for i in range(len(rows))]
            views = [b[0] for b in built]
            valid = np.array([b[1] for b in built])
            aud[f"invalid_start_{cond}"] += int((~valid).sum())
            P = model.predict_proba(enc.transform(views, ages, sexes))
            order = np.argsort(-P, 1)
            rank = np.argmax(order == truth[:, None], 1) + 1
            p_truth = P[np.arange(len(P)), truth]
            init_out.append(pd.DataFrame({
                "cond": cond, "seed": seed, "row_index": ridx, "initial": ini, "valid": valid,
                "top1": rank == 1, "top3": rank <= 3, "rank": rank, "p_truth": p_truth.astype(np.float64),
                "n_additional": [len(v) - 1 for v in views]}))
            log(t0, f"{cond} s{seed} initial top1 {(rank[valid] == 1).mean():.4f} top3 {(rank[valid] <= 3).mean():.4f} "
                    f"invalid {(~valid).sum()} ({time.time() - t:.0f}s)")
            # ---- SIM ----
            sidx = [i for i in range(min(sim_n, len(rows))) if valid[i]]
            n = len(sidx)
            cv = [views[i] for i in sidx]
            cP = P[sidx]
            ctruth = truth[sidx]
            cwrong = order[sidx, 0] != ctruth
            base_pool = [sorted([q for q in sem.qids if sem.currently_eligible(q, v)], key=QN.get) for v in cv]
            st = {ag: [dict(v) for v in cv] for ag in agents}
            pl = {ag: [list(p) for p in base_pool] for ag in agents}
            post = {ag: cP.copy() for ag in agents}
            for step in range(1, STEPS + 1):
                chosen = {}
                for ag in agents:
                    name, s = ag
                    ch = [None] * n
                    u = np.random.default_rng([s, step]).random(n) if name == "RANDOM" else None
                    for j in range(n):
                        pool = pl[ag][j]
                        if not pool:
                            continue
                        if name == "RANDOM":
                            ch[j] = pool[int(u[j] * len(pool))]
                        else:
                            ig = c.ig_all(post[ag][j].astype(np.float64), MIG, grp, NQ)
                            idx = np.fromiter((qpos[q] for q in pool), int, len(pool))
                            ch[j] = qs[idx[int(np.argmax(np.round(ig[idx], 12)))]]
                    chosen[ag] = ch
                bs, bi = [], []
                for ag in agents:
                    for j in range(n):
                        q = chosen[ag][j]
                        if q is None:
                            aud["abstain"] += 1
                            continue
                        if q in st[ag][j]:
                            aud["repeated_question"] += 1
                            continue
                        if not sem.safe[q]:
                            aud["unsafe_question_access"] += 1
                            continue
                        ans = sem.reconstruct(q, toks[sidx[j]])
                        aud["reveal_calls"] += 1
                        st[ag][j][q] = ans
                        pl[ag][j].remove(q)
                        if ans == ("POS",) and q in vb.children:
                            pl[ag][j] = sorted(set(pl[ag][j]) | {x for x in vb.children[q] if x not in st[ag][j]}, key=QN.get)
                        bs.append(st[ag][j])
                        bi.append((ag, j))
                if bs:
                    Pb = model.predict_proba(enc.transform(bs, np.array([ages[sidx[j]] for _, j in bi]),
                                                           np.array([sexes[sidx[j]] for _, j in bi]))).astype(np.float32)
                    for k, (ag, j) in enumerate(bi):
                        post[ag][j] = Pb[k]
                if step in (1, STEPS):
                    for ag in agents:
                        o = np.argsort(-post[ag], 1)
                        sim_out.append(pd.DataFrame({
                            "cond": cond, "seed": seed, "step": step, "row_index": ridx[sidx], "selector": ag[0], "draw": ag[1],
                            "initial_wrong": cwrong, "correct_after": o[:, 0] == ctruth}))
            log(t0, f"{cond} s{seed} sim n={n} done ({time.time() - t:.0f}s)")
    aud["unsafe_state_encounters"] = int(sum(sem.unsafe_encounters.values()))
    return pd.concat(init_out, ignore_index=True), pd.concat(sim_out, ignore_index=True), aud


def boot_patient_mean(pid, d, n_boot=1000, seed=42):
    """환자 cluster paired bootstrap: 환자별 합/개수로 재표집 → 가중 평균 차이."""
    u, inv = np.unique(pid, return_inverse=True)
    s = np.bincount(inv, weights=d, minlength=len(u))
    cnt = np.bincount(inv, minlength=len(u))
    rng = np.random.default_rng(seed)
    out = np.empty(n_boot)
    for t in range(n_boot):
        k = rng.integers(0, len(u), len(u))
        out[t] = s[k].sum() / cnt[k].sum()
    return {"point": float(d.mean()), "ci_lo": float(np.percentile(out, 2.5)), "ci_hi": float(np.percentile(out, 97.5)),
            "n_units": int(len(d)), "n_patients": int(len(u))}


def summarize(ini, sim, ko27_mask_rows=None):
    """초기 지표·paired 비교·IG 지표. ko27_mask_rows: 보조 subset row_index 집합."""
    out = {"initial": {}, "paired_initial_vs_R0": {}, "ig": {}}
    v = ini[ini.valid]
    for cond, g in v.groupby("cond"):
        out["initial"][cond] = {
            "n_views": int(len(g)), "top1": float(g.top1.mean()), "top3": float(g.top3.mean()),
            "log_loss": float(-np.log(np.clip(g.p_truth.values, 1e-15, 1)).mean()),
            "rank_mean": float(g["rank"].mean()), "rank_median": float(g["rank"].median()),
            "invalid_views": int((~ini[ini.cond == cond].valid).sum()),
            "exact_k_completion": float(ini[ini.cond == cond].valid.mean())}
    per = v.groupby(["cond", "row_index"]).agg(top1=("top1", "mean"), top3=("top3", "mean")).reset_index()
    base = per[per.cond == "R0"].set_index("row_index")
    for cond in [x for x in per.cond.unique() if x != "R0"]:
        g = per[per.cond == cond].set_index("row_index")
        common = g.index.intersection(base.index)
        for m in ("top3", "top1"):
            d = g.loc[common, m].values - base.loc[common, m].values
            out["paired_initial_vs_R0"][f"{cond}-R0:{m}"] = boot_patient_mean(common.values, d)
    for cond, g in sim.groupby("cond"):
        res = {}
        for step in (1, STEPS):
            gs = g[g.step == step]
            view = gs.groupby(["seed", "row_index", "selector"]).agg(p=("correct_after", "mean"),
                                                                      wrong=("initial_wrong", "first")).reset_index()
            piv = view.pivot_table(index=["seed", "row_index", "wrong"], columns="selector", values="p").reset_index()
            w, r = piv[piv.wrong], piv[~piv.wrong]
            tag = f"{step}Q"
            res[f"recovery@{tag}"] = {"RANDOM": float(w.RANDOM.mean()), "INTERNAL_IG": float(w.INTERNAL_IG.mean()),
                                      "n_wrong_views": int(len(w))}
            res[f"correct_to_wrong@{tag}"] = {"RANDOM": float(1 - r.RANDOM.mean()), "INTERNAL_IG": float(1 - r.INTERNAL_IG.mean()),
                                              "n_correct_views": int(len(r))}
            res[f"boot_recovery@{tag}:IG-RANDOM"] = boot_patient_mean(w.row_index.values, (w.INTERNAL_IG - w.RANDOM).values)
            res[f"boot_c2w@{tag}:IG-RANDOM"] = boot_patient_mean(r.row_index.values, ((1 - r.INTERNAL_IG) - (1 - r.RANDOM)).values)
        out["ig"][cond] = res
    if ko27_mask_rows is not None:
        k = ini[ini.valid & ini.row_index.isin(ko27_mask_rows)]
        out["ko27_initial"] = {cond: {"n_views": int(len(g)), "top1": float(g.top1.mean()), "top3": float(g.top3.mean())}
                               for cond, g in k.groupby("cond")}
    return out


def gates(S):
    A = S["paired_initial_vs_R0"]["R3-R0:top3"]
    B = S["ig"]["R3"]["boot_recovery@1Q:IG-RANDOM"]
    C = S["ig"]["R3"]["boot_c2w@3Q:IG-RANDOM"]
    D1 = S["initial"]["R3"]["exact_k_completion"]
    g = {"A": {"rule": "R3-R0 top3 CI lo > -0.05", "value": A, "pass": A["ci_lo"] > -0.05},
         "B": {"rule": "R3 IG-RANDOM Recovery@1Q CI lo > +0.10", "value": B, "pass": B["ci_lo"] > 0.10},
         "C": {"rule": "R3 IG-RANDOM Correct->Wrong@3Q CI hi <= 0", "value": C, "pass": C["ci_hi"] <= 0},
         "D1": {"rule": "R3 exact-k completion >= 0.95", "value": D1, "pass": D1 >= 0.95}}
    g["decision"] = "NATURAL_INTAKE_K3_GO" if all(g[x]["pass"] for x in ("A", "B", "C", "D1")) else "NATURAL_INTAKE_K3_NO_GO"
    return g
