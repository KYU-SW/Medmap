"""EXP-03-TIME v2 독립 데이터 감사(계층 B) — PROTOCOL_TIME_v2.md §7.

파이프라인(records_v2·time_policy·reassess)을 import 하지 않고 원 parquet 열만으로(pandas 병합·벡터 연산) 다시 계산한다.
- 체류×정책×T 허용 기록 집합(원 키) → 파이프라인이 실제 사용한 집합과 대조(누락·초과 모두 위반)
- 사용 기록 available_at == 원 storetime(lab·rad) / == intime(S1 triage)
- 같은 subject, 전역 원 키가 둘 이상 체류에 사용 0, ECG 사용 0, triage 는 S1 에서만
- 입력 행 수 = 결측 키 + 고유 키(유지 + 시각 충돌) + 중복 잉여 행, 유지 = 귀속 + AMBIGUOUS + 미귀속
공유 입력(독립 계산 아님): v3b 판독 분류 결과(cls) — 동결 분류기 출력이며 시간 안전성 검사 대상이 아님.
검증 불가(NOT_VERIFIABLE): 실제 열람 시각, storetime 의 'usually' 예외, 코호트 밖 체류와의 창 겹침.
"""
from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
import pandas as pd

POLICY_GRADES = {"STRICT_AVAILABLE_TIME": {"lab", "rad"}, "S1_TRIAGE_AT_INTIME_APPROX": {"lab", "rad", "triage"},
                 "S2_STRICT_A_ONLY": {"lab"}}
DECISIVE = {"ACUTE_POS", "NEGATIVE", "CHRONIC_OR_PERSISTENT", "UNCERTAIN"}
TOL = 1e-6
NOT_VERIFIABLE = ["실제 의료진 열람 시각(자료 없음)", "radiology storetime 'usually' 예외·예비 구두 보고(자료 없음)",
                  "코호트 밖 ED 체류와의 창 겹침(코호트 체류끼리만 판정)", "lab storetime 이 실제 이용 시각과 다른 경우(문서 정의 가정)"]


def _min(s: pd.Series) -> pd.Series:
    # 실제 추출본 시각 열은 문자열(large_string) — 형식이 섞여도 첫 행 형식으로 강제하지 않음
    return (pd.to_datetime(s, format="mixed") - pd.Timestamp("1970-01-01")).dt.total_seconds() / 60.0


def _dedup(df: pd.DataFrame, key: str, cols: list) -> tuple[pd.DataFrame, dict]:
    d = df[df[key].notna()]
    g = d.groupby(key)
    n = g[key].size()
    var = g[cols].nunique(dropna=False).max(axis=1)
    ok_keys = var.index[var <= 1]
    kept = d[d[key].isin(ok_keys)].groupby(key, as_index=False).first()
    return kept, {"input_rows": len(df), "missing_key_rows": int(df[key].isna().sum()), "unique_keys": int(len(n)),
                  "dup_extra_rows": int((n - 1).sum()), "time_conflict_keys": int((var > 1).sum()), "kept_unique": int(len(kept))}


def _attribute(rows: pd.DataFrame, key: str, windows: pd.DataFrame) -> pd.DataFrame:
    """rows: key, subject_id(str), t_obs(분). windows: stay_id, subject_id, i, o. 반환 key → stay_id 또는 AMBIGUOUS/NONE."""
    m = rows[[key, "subject_id", "t_obs"]].merge(windows, on="subject_id", how="inner")
    m = m[(m["t_obs"] >= m["i"]) & (m["t_obs"] <= m["o"])]
    cnt = m.groupby(key)["stay_id"].agg(["size", "first"])
    out = rows[[key]].copy()
    out["stay"] = out[key].map(cnt["first"].where(cnt["size"] == 1, "AMBIGUOUS")).fillna("NONE")
    return out


class IndependentAudit:
    def __init__(self, co, labs, rad, ecg, detail, cls: dict):
        c = co.assign(stay_id=co["stay_id"].astype(str), subject_id=co["subject_id"].astype(str),
                      i=_min(co["intime"]), o=_min(co["outtime"]))
        ok = c["i"].notna() & c["o"].notna() & (c["o"] >= c["i"])
        self.win = c.loc[ok, ["stay_id", "subject_id", "i", "o"]]
        self.intime = dict(zip(self.win["stay_id"], self.win["i"]))
        self.subj = dict(zip(c["stay_id"], c["subject_id"]))
        self.recon = {}
        self.allowed = defaultdict(list)            # stay → [(src, native, avail)]
        # lab
        lk, ls = _dedup(labs, "labevent_id", ["subject_id", "charttime", "storetime"])
        lk = lk.assign(subject_id=lk["subject_id"].astype(str), native=lk["labevent_id"].astype(str),
                       t_obs=_min(lk["charttime"]), t_av=_min(lk["storetime"]))
        la = _attribute(lk.rename(columns={"native": "k"}), "k", self.win)
        lk["stay"] = la["stay"].values
        ls.update({"attributed": int((~lk["stay"].isin(["AMBIGUOUS", "NONE"])).sum()),
                   "ambiguous": int((lk["stay"] == "AMBIGUOUS").sum()), "unattributed": int((lk["stay"] == "NONE").sum())})
        la_st = lk[~lk["stay"].isin(["AMBIGUOUS", "NONE"])]
        ls.update({"stays_with_records": int(la_st["stay"].nunique()), "patients_with_records": int(la_st["subject_id"].nunique())})
        self.recon["lab"] = ls
        el = lk[~lk["stay"].isin(["AMBIGUOUS", "NONE"]) & lk["t_av"].notna() & (lk["t_av"] >= lk["t_obs"])]
        for s, n, a in zip(el["stay"], el["native"], el["t_av"]):
            self.allowed[s].append(("lab", n, a))
        self.lab_subj = dict(zip(lk["native"], lk["subject_id"]))
        self.lab_store = dict(zip(lk["native"], lk["t_av"]))
        # radiology
        rk, rs = _dedup(rad, "note_id", ["subject_id", "charttime", "storetime"])
        rk = rk.assign(subject_id=rk["subject_id"].astype(str), native=rk["note_id"].astype(str),
                       t_obs=_min(rk["charttime"]), t_av=_min(rk["storetime"]))
        ntype = dict(zip(rk["native"], rk["note_type"]))
        links = self._links(detail, ntype, dict(zip(rk["native"], rk["subject_id"])))
        exam = dict(zip(rk["native"], rk["exam_name"].fillna("").astype(str)))

        def is_cta(n):
            e = exam.get(n, "")
            if not e.strip() and n in links:
                e = exam.get(links[n], "")
            return e.upper().startswith("CTA CHEST")
        rk["cta"] = rk["native"].map(is_cta)
        ra = _attribute(rk.rename(columns={"native": "k"}), "k", self.win)
        own = dict(zip(rk["native"], ra["stay"].values))
        rk["stay"] = [own[links[n]] if n in links else own[n] for n in rk["native"]]   # 연결 addendum = 원 판독 체류(가족 귀속)
        rs.update({"attributed": int((~rk["stay"].isin(["AMBIGUOUS", "NONE"])).sum()),
                   "ambiguous": int((rk["stay"] == "AMBIGUOUS").sum()), "unattributed": int((rk["stay"] == "NONE").sum()),
                   "attributed_cta": int((rk["cta"] & ~rk["stay"].isin(["AMBIGUOUS", "NONE"])).sum()), "verified_links": len(links)})
        drop = {n for n in links if cls.get(n) not in DECISIVE}
        # 시간 순서 규칙(PROTOCOL §5-1) 독립 구현 — 원 parquet 시각 열만 사용
        t_av, t_obs = dict(zip(rk["native"], rk["t_av"])), dict(zip(rk["native"], rk["t_obs"]))

        def order_excluded(n):
            pa, ca = links[n], t_av.get(n)
            po, co_ = t_obs.get(links[n]), t_obs.get(n)
            pv = t_av.get(pa)
            if pd.isna(pv) or pd.isna(po) or pv < po:
                return True
            if pd.isna(ca) or pd.isna(co_) or ca < co_:
                return False                                       # 자기 시각 부적격은 기존 경로(UNKNOWN·역전 — 사용 안 됨)
            return bool(ca < pv or co_ < po)
        order = {n for n in links if n in cls and n not in drop and order_excluded(n)}
        rs["addendum_order_excluded"] = len(order)
        drop |= order
        er = rk[rk["cta"] & ~rk["stay"].isin(["AMBIGUOUS", "NONE"]) & ~rk["native"].isin(drop)]
        rs["cta_input"] = int(len(er))
        rs.update({"stays_with_records": int(er["stay"].nunique()), "patients_with_records": int(er["subject_id"].nunique())})
        self.recon["radiology"] = rs
        er = er[er["t_av"].notna() & (er["t_av"] >= er["t_obs"])]
        for s, n, a in zip(er["stay"], er["native"], er["t_av"]):
            self.allowed[s].append(("rad", n, a))
        self.rad_subj = dict(zip(rk["native"], rk["subject_id"]))
        self.rad_store = dict(zip(rk["native"], rk["t_av"]))
        # ecg
        e, es = _dedup(ecg, "study_id", ["ed_stay_id", "ecg_time_ext"])
        k = pd.to_numeric(e["ed_stay_id"], errors="coerce").astype("Int64").astype(str)
        ek = k[k.isin(set(self.win["stay_id"]))]
        self.recon["ecg"] = {**es, "matched": int(len(ek)), "stays_with_records": int(ek.nunique()),
                             "patients_with_records": len({self.subj[x] for x in ek})}
        self.used_global = defaultdict(set)         # (src, native) → {stay}
        self.v = Counter()

    @staticmethod
    def _links(detail, ntype, subj) -> dict:
        if detail is None or detail.empty:
            return {}
        p = detail[detail["field_name"] == "parent_note_id"][["note_id", "field_value"]].astype(str)
        a = detail[detail["field_name"] == "addendum_note_id"][["note_id", "field_value"]].astype(str)
        both = p.merge(a.rename(columns={"note_id": "field_value", "field_value": "note_id"}), on=["note_id", "field_value"])
        both = both.drop_duplicates()
        if both.empty:                                                 # 양방향 쌍 0 — 빈 열 dtype 문제로 아래 & 연산 실패 방지(관계 발견 중 발견)
            return {}
        multi = both.groupby("note_id")["field_value"].transform("size") > 1
        both = both[~multi]
        nts = set(ntype)
        both = both.loc[np.array([ntype.get(n) == "AR" and f in nts for n, f in zip(both["note_id"], both["field_value"])], dtype=bool)]
        both = both.loc[np.array([subj.get(c) == subj.get(p) for c, p in zip(both["note_id"], both["field_value"])], dtype=bool)]   # 같은 환자만
        return dict(zip(both["note_id"], both["field_value"]))

    def check_stay(self, stay_id: str, policy: str, T: float, used: list) -> Counter:
        """used: [(src, native, available_at)] 파이프라인이 T 에 사용한 기록. src ∈ lab·rad·triage·ecg."""
        v = Counter()
        want = {(s, n) for s, n, a in self.allowed.get(stay_id, []) if s in POLICY_GRADES[policy] and a <= T + TOL}
        got = set()
        subj = self.subj.get(stay_id)
        for s, n, a in used:
            if s == "ecg":
                v["B_ecg_used"] += 1
                continue
            if s == "triage":
                if "triage" not in POLICY_GRADES[policy]:
                    v["B_triage_outside_S1"] += 1
                elif a is None or abs(a - self.intime[stay_id]) > TOL:
                    v["B_triage_available_not_intime"] += 1
                continue
            store = (self.lab_store if s == "lab" else self.rad_store).get(n)
            if store is None or a is None or abs(a - store) > TOL:
                v["B_available_at_ne_raw_storetime"] += 1
            if (self.lab_subj if s == "lab" else self.rad_subj).get(n) != subj:
                v["B_subject_mismatch"] += 1
            got.add((s, n))
            self.used_global[(s, n)].add(stay_id)
        v["B_used_not_allowed"] += len(got - want)
        v["B_allowed_not_used"] += len(want - got)
        if "triage" in POLICY_GRADES[policy]:
            pass                                        # 완전성은 run 에서 파생 증거 있는 체류 기준으로 대조
        return v

    def finish(self) -> Counter:
        v = Counter()
        v["B_record_used_in_multiple_stays"] = sum(len(s) > 1 for s in self.used_global.values())
        return v

    def reconcile(self, pipeline_audit: dict) -> Counter:
        """입력 행·귀속 대조(파이프라인 집계 vs 독립 계산)."""
        v = Counter()
        for src, keys in (("lab", ("input_rows", "missing_key_rows", "unique_keys", "dup_extra_rows", "kept_unique",
                                   "attributed", "ambiguous", "unattributed", "stays_with_records", "patients_with_records")),
                          ("radiology", ("input_rows", "missing_key_rows", "unique_keys", "dup_extra_rows", "kept_unique",
                                         "attributed", "ambiguous", "unattributed", "verified_links", "cta_input", "stays_with_records", "patients_with_records"))):
            ind, pip = self.recon[src], pipeline_audit[src]
            for k in keys:
                if int(ind.get(k, 0)) != int(pip.get(k, 0)):
                    v[f"B_reconcile_{src}_{k}"] += 1
            if ind["input_rows"] != ind["missing_key_rows"] + ind["unique_keys"] + ind["dup_extra_rows"]:
                v[f"B_reconcile_{src}_row_identity"] += 1
            if ind["kept_unique"] != ind["attributed"] + ind["ambiguous"] + ind["unattributed"]:
                v[f"B_reconcile_{src}_attribution_identity"] += 1
        pipe_order = sum(int(pipeline_audit["radiology"].get(k, 0)) for k in ("addendum_stored_before_parent_excluded",
                         "addendum_charted_before_parent_excluded", "addendum_order_undeterminable_excluded"))
        if int(self.recon["radiology"].get("addendum_order_excluded", 0)) != pipe_order:
            v["B_reconcile_radiology_addendum_order_excluded"] += 1
        if int(self.recon["ecg"]["matched"]) != int(pipeline_audit["ecg"].get("matched", 0)):
            v["B_reconcile_ecg_matched"] += 1
        for k in ("stays_with_records", "patients_with_records"):
            if int(self.recon["ecg"][k]) != int(pipeline_audit["ecg"].get(k, 0)):
                v[f"B_reconcile_ecg_{k}"] += 1
        return v
