"""EXP-03-TIME v2 기록 계층(PROTOCOL_TIME_v2.md §3–§6) — 파이프라인 쪽 경로.

v1 대비 변경(1차 gate 지적 대응):
- 고유 원본 기록 키로 전역 1회 중복 처리·귀속(체류마다 반복 투입 금지) [F-record-denominator·S-denominator·M-unit]
- 비CTA·유형 불명 영상은 증거 미투입(참고 집계만) [MINOR·M-rad]
- addendum(AR) 연결 규칙 [M-rad] — 양방향 연결 확인된 것만 '연결', 그 외 ADDENDUM_UNLINKED
- 내부 키 = 실행마다 새 salt 의 HMAC 가명(원 note_id·labevent_id·stay_id 비노출) [B-privacy-traceback]
time_policy.py(v1)·reassess.py·mimic_adapter·ct_bridge 는 수정 없이 import.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
EXP03 = HERE.parent
V1 = EXP03 / "time_v1"
EXP02 = Path(os.environ.get("EXP03_EXP02") or EXP03.parent / "exp02_mimic_graph")
for _p in (str(V1), str(EXP03), str(EXP02)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import mimic_adapter as MA  # noqa: E402  (EXP-02, 읽기 전용)
import time_policy as TP  # noqa: E402  (v1, 수정 없음)
from ct_bridge import classify  # noqa: E402  (v3b 동결 분류기)

DECISIVE = {"ACUTE_POS", "NEGATIVE", "CHRONIC_OR_PERSISTENT", "UNCERTAIN"}
STATUS_OF = {"NEGATIVE": "NEGATIVE", "UNCERTAIN": "UNCERTAIN", "NO_MENTION": "NOT_ASSESSABLE"}   # 그 외(급성·만성) POSITIVE
LAB_TIME_COLS = ["subject_id", "charttime", "storetime"]
TYPES = ("CTA", "OTHER", "UNKNOWN_TYPE")
PE_CLASSES = ("ACUTE_POS", "CHRONIC_OR_PERSISTENT", "UNCERTAIN", "NEGATIVE", "NO_MENTION")
LINK_KEYS = ("link_pairs_parent_field_only", "link_pairs_addendum_field_only", "link_pairs_both_fields", "child_multiple_parents",
             "child_not_AR", "parent_not_in_extract", "link_subject_mismatch", "verified_links")
PAIR_KEYS = tuple(f"replace_pair:{a}->{b}" for a in ("ACUTE_POS", "CHRONIC_OR_PERSISTENT", "UNCERTAIN", "NEGATIVE", "NO_MENTION")
                  for b in ("ACUTE_POS", "CHRONIC_OR_PERSISTENT", "UNCERTAIN", "NEGATIVE")) + \
    tuple(f"nomention_addendum_parent_class:{a}" for a in ("ACUTE_POS", "CHRONIC_OR_PERSISTENT", "UNCERTAIN", "NEGATIVE", "NO_MENTION",
                                                          "PARENT_NOT_INPUT"))
RAD_KEYS = (("attributed", "ambiguous", "unattributed", "cta_input", "addendum_type_from_parent", "addendum_ineligible_time",
             "addendum_parent_not_in_inputs_or_ineligible", "addendum_linked_no_decisive_not_input", "addendum_linked_replacing",
             "addendum_stored_before_parent_excluded", "addendum_charted_before_parent_excluded", "addendum_order_undeterminable_excluded",
             "addendum_unlinked_AR_input", "linked_addendum_stay_ne_parent_stay",
             "linked_addendum_parent_ambiguous_or_unattributed") + LINK_KEYS + tuple(f"{a}{t}" for a in ("type:", "attributed:", "ambiguous:", "unattributed:")
                                                              for t in TYPES) + tuple(f"class:{c}" for c in PE_CLASSES))


def zeros(keys) -> Counter:
    return Counter({k: 0 for k in keys})
RAD_TIME_COLS = ["subject_id", "charttime", "storetime"]


def minutes(x):
    return None if x is None or pd.isna(x) else pd.Timestamp(x).timestamp() / 60.0


class Pseudo:
    """원 키 → 'src:hmac16' 가명. salt 는 실행마다 새로 만들고 저장하지 않음. 역방향 표는 메모리에만."""

    def __init__(self, salt: bytes | None = None):
        self.salt = salt or secrets.token_bytes(16)
        self.native: dict = {}
        self._fwd: dict = {}

    def __call__(self, src: str, native) -> str:
        k = (src, str(native))
        if k in self._fwd:
            return self._fwd[k]
        pid = f"{src}:{hmac.new(self.salt, f'{src}:{native}'.encode(), hashlib.sha256).hexdigest()[:16]}"
        if pid in self.native:
            raise RuntimeError("PSEUDO_COLLISION")
        self.native[pid] = k
        self._fwd[k] = pid
        return pid


def dedupe(df: pd.DataFrame, key: str, tcols: list) -> tuple[pd.DataFrame, dict, set]:
    """같은 키 여러 행: 시각·subject 열이 모두 같으면 1행 유지(DUP_IDENTICAL), 다르면 그 키 전체 제외(DUP_TIME_CONFLICT, 등급 C)."""
    miss = df[key].isna()
    d = df[~miss]
    size = d.groupby(key)[key].transform("size")
    single, multi = d[size == 1], d[size > 1]
    keep, ident, conf = [single], [], []
    if len(multi):
        nun = multi.groupby(key)[tcols].nunique(dropna=False).max(axis=1)
        ident = list(nun[nun <= 1].index)
        conf = list(nun[nun > 1].index)
        keep.append(multi[multi[key].isin(ident)].drop_duplicates(key, keep="first"))
    out = pd.concat(keep, ignore_index=True)
    st = {"input_rows": int(len(df)), "missing_key_rows": int(miss.sum()), "unique_keys": int(d[key].nunique()),
          "dup_key_groups_identical": len(ident), "dup_key_groups_time_conflict": len(conf),
          "dup_extra_rows": int(len(multi) - multi[key].nunique()) if len(multi) else 0,
          "kept_unique": int(len(out))}
    return out, st, set(conf)


def rad_type(exam_name) -> str:
    if exam_name is None or (isinstance(exam_name, float) and pd.isna(exam_name)) or not str(exam_name).strip():
        return "UNKNOWN_TYPE"
    return "CTA" if MA.classify_exam(exam_name) == "CTA_CHEST" else "OTHER"


def addendum_links(detail: pd.DataFrame, note_type: dict, subj_of: dict | None = None) -> tuple[dict, Counter]:
    """radiology_detail parent_note_id·addendum_note_id → {child: parent}. 양방향 일치 + child note_type AR + parent 가 추출에 있음 일 때만 '연결'.
    child 가 부모 둘 이상이면 연결 안 함. 공식 문서는 '부모 보고–addendum 연결이 있다'만 명시(필드 방향 의미는 확인 필요) → 양방향 요구로 보수 처리."""
    c = zeros(LINK_KEYS)
    if detail is None or detail.empty:
        return {}, c
    p = detail[detail["field_name"] == "parent_note_id"]
    a = detail[detail["field_name"] == "addendum_note_id"]
    fwd = set(zip(p["note_id"].astype(str), p["field_value"].astype(str)))
    back = set(zip(a["field_value"].astype(str), a["note_id"].astype(str)))
    both = fwd & back
    c["link_pairs_parent_field_only"] = len(fwd - back)
    c["link_pairs_addendum_field_only"] = len(back - fwd)
    c["link_pairs_both_fields"] = len(both)
    par = defaultdict(set)
    for ch, pa in both:
        par[ch].add(pa)
    out = {}
    for ch, ps in par.items():
        if len(ps) > 1:
            c["child_multiple_parents"] += 1
            continue
        pa = next(iter(ps))
        if note_type.get(ch) != "AR":
            c["child_not_AR"] += 1
            continue
        if pa not in note_type:
            c["parent_not_in_extract"] += 1
            continue
        if subj_of is not None and subj_of.get(ch) != subj_of.get(pa):
            c["link_subject_mismatch"] += 1                     # 다른 환자 연결 = 자료 오류 의심 → 연결 안 함
            continue
        out[ch] = pa
    c["verified_links"] = len(out)
    return out, c


@dataclass
class Prepared:
    stays: dict                                   # stay_id → TP.Stay (시각 정의된 체류)
    undefined_stays: set                          # intime/outtime 결측·역전
    subj_of_stay: dict
    per_stay: dict                                # stay_id → [RawRecord] (입력 순서: 원 보고 → addendum 사슬 순)
    pseudo: Pseudo
    audit: dict = field(default_factory=dict)     # 공개 전 정확 집계(마스킹은 run 에서)
    cls: dict = field(default_factory=dict)       # note_id → v3b 클래스(공유 입력, 독립 감사도 사용)
    links: dict = field(default_factory=dict)     # child note_id → parent note_id


def prepare(co: pd.DataFrame, labs: pd.DataFrame, rad: pd.DataFrame, ecg: pd.DataFrame, detail: pd.DataFrame | None,
            text_of, pseudo: Pseudo | None = None) -> Prepared:
    """text_of(note_id) → 판독 원문(로컬 메모리, 출력 금지). 분류는 CTA 입력 후보에만."""
    P = pseudo or Pseudo()
    A = {}
    # --- 체류 ---
    stays, undefined, subj_of = {}, set(), {}
    by_subj = defaultdict(list)
    for s in co.itertuples(index=False):
        sid, subj = str(s.stay_id), str(s.subject_id)
        subj_of[sid] = subj
        i, o = minutes(s.intime), minutes(s.outtime)
        if i is None or o is None or o < i:
            undefined.add(sid)
            continue
        st = TP.Stay(sid, subj, i, o)
        stays[sid] = st
        by_subj[subj].append(st)
    A["stays"] = {"cohort_stays": len(subj_of), "time_defined": len(stays), "time_undefined": len(undefined),
                  "t1_equals_t2": sum(1 for s in stays.values() if s.outtime <= s.intime + 180)}
    per_stay = defaultdict(list)

    def attr(subj, obs, stay_key=None):
        r = TP.RawRecord("x", subj, "lab", "x", stay_id=stay_key, observed_at=obs)
        return TP.attribute(r, by_subj.get(subj, []))

    # --- 검사(lab): labevent_id ---
    lab_u, lab_st, lab_conf = dedupe(labs, "labevent_id", LAB_TIME_COLS)
    la = zeros(("attributed", "ambiguous", "unattributed"))
    for r in lab_u.itertuples(index=False):
        subj = str(r.subject_id)
        sid = attr(subj, minutes(r.charttime))
        if sid == "AMBIGUOUS":
            la["ambiguous"] += 1
            continue
        if sid is None:
            la["unattributed"] += 1
            continue
        la["attributed"] += 1
        item = int(r.itemid)
        if item in MA.HIV_ITEMS:
            node, status = "CONCEPT:hiv_infection", MA.hiv_status(MA.HIV_ITEMS[item], r.value).value
        else:
            node = MA.LAB_NODE[item]
            status = MA.lab_status(r.value, r.valuenum, r.ref_range_upper, getattr(r, "comments", None))[0].value
        rid = P("lab", r.labevent_id)
        per_stay[sid].append(TP.RawRecord(rid, subj, "lab", f"hosp.labevents:{rid}",
                                          observed_at=minutes(r.charttime), charted_at=minutes(r.charttime),
                                          signed_or_stored_at=minutes(r.storetime), evidence_type="LAB",
                                          evidence_status=status, concept=node))
    A["lab"] = {**lab_st, **dict(la)}

    # --- 영상(radiology): note_id ---
    rad_u, rad_st, rad_conf = dedupe(rad, "note_id", RAD_TIME_COLS)
    note_type = {str(n): (None if pd.isna(t) else str(t)) for n, t in zip(rad_u["note_id"], rad_u["note_type"])}
    exam = {str(n): e for n, e in zip(rad_u["note_id"], rad_u["exam_name"])}
    links, lc = addendum_links(detail, note_type, {str(n): str(x) for n, x in zip(rad_u["note_id"], rad_u["subject_id"])})
    ra = zeros(RAD_KEYS + PAIR_KEYS)
    ra.update(lc)
    rows = []
    own_sid = {str(r.note_id): attr(str(r.subject_id), minutes(r.charttime)) for r in rad_u.itertuples(index=False)}
    for r in rad_u.itertuples(index=False):
        nid, subj = str(r.note_id), str(r.subject_id)
        own = rad_type(r.exam_name)
        typ = own
        if own == "UNKNOWN_TYPE" and nid in links:
            typ = rad_type(exam.get(links[nid]))
            ra["addendum_type_from_parent"] += typ != "UNKNOWN_TYPE"
        sid = own_sid[nid]
        if nid in links:                                           # 연결 addendum = 가족 단위 귀속(원 판독의 체류)
            psid = own_sid.get(links[nid])
            if psid in ("AMBIGUOUS", None):
                ra["linked_addendum_parent_ambiguous_or_unattributed"] += 1
            elif sid != psid:
                ra["linked_addendum_stay_ne_parent_stay"] += 1
            sid = psid
        ra[f"type:{typ}"] += 1
        ra[f"note_type:{note_type.get(nid)}"] += 1
        if sid == "AMBIGUOUS":
            ra["ambiguous"] += 1
            ra[f"ambiguous:{typ}"] += 1
            continue
        if sid is None:
            ra["unattributed"] += 1
            ra[f"unattributed:{typ}"] += 1
            continue
        ra["attributed"] += 1
        ra[f"attributed:{typ}"] += 1
        if typ != "CTA":
            continue                                               # 비CTA·유형 불명 = 증거 미투입(참고 집계)
        rows.append((sid, nid, subj, r))
    # 연결 가족(원 보고 + 연결 addendum) 사슬 순서: 원 보고 → addendum(storetime, note_id 순)
    store_of = {nid: minutes(r.storetime) for _, nid, _, r in rows}
    chart_of = {nid: minutes(r.charttime) for _, nid, _, r in rows}
    eligible = {nid for nid in store_of if store_of[nid] is not None and chart_of[nid] is not None and store_of[nid] >= chart_of[nid]}
    children = defaultdict(list)
    for ch, pa in links.items():
        children[pa].append(ch)
    rank, sup_of, skip, cls = {}, {}, set(), {}
    raw_store = {str(r.note_id): minutes(r.storetime) for r in rad_u.itertuples(index=False)}
    raw_chart = {str(r.note_id): minutes(r.charttime) for r in rad_u.itertuples(index=False)}
    for nid in store_of:
        cls[nid] = classify(text_of(nid), "v3b")[0]
        ra[f"class:{cls[nid]}"] += 1
        if nid in links and cls[nid] not in DECISIVE:
            skip.add(nid)                                          # 연결 addendum NO_MENTION → 원 판독을 지우지 않음(미투입)
    # 시간 순서 규칙(PROTOCOL §5-1): 연결 addendum 이 원 판독보다 이른 시각으로 기록됐거나 원 판독의 이용 가능 시각이 불명확하면
    # 대체 관계를 만들지 않고 증거에서 제외(별도 집계). 원 판독은 그대로 — 과거 상태를 소급 수정하지 않음.
    order_excl = set()
    for nid in store_of:
        if nid not in links or nid in skip:
            continue
        pa = links[nid]
        ps, pc, cs, cc = raw_store.get(pa), raw_chart.get(pa), store_of[nid], chart_of[nid]
        reason = None
        if ps is None or pc is None or ps < pc:
            reason = "addendum_order_undeterminable_excluded"
        elif nid in eligible and cs < ps:
            reason = "addendum_stored_before_parent_excluded"
        elif nid in eligible and cc < pc:
            reason = "addendum_charted_before_parent_excluded"
        if reason:
            ra[reason] += 1
            order_excl.add(nid)
    for nid in skip:
        ra[f"nomention_addendum_parent_class:{cls.get(links[nid], 'PARENT_NOT_INPUT')}"] += 1
    for pa, chs in children.items():
        chain = [pa] if pa in eligible and pa in store_of else []
        if not chain:
            ra["addendum_parent_not_in_inputs_or_ineligible"] += 1
        order = sorted((c for c in chs if c in store_of and c not in skip and c not in order_excl),
                       key=lambda c: (store_of[c] if store_of[c] is not None else float("inf"), c))
        for k, ch in enumerate(order, start=1):
            rank[ch] = k
            if ch not in eligible:
                ra["addendum_ineligible_time"] += 1
                continue
            sup_of[ch] = chain[-1] if chain else None
            if sup_of[ch] is not None:
                ra[f"replace_pair:{cls[sup_of[ch]]}->{cls[ch]}"] += 1
            chain.append(ch)
    ra["addendum_linked_no_decisive_not_input"] = len(skip)
    ra["addendum_linked_replacing"] = sum(1 for v in sup_of.values() if v is not None)
    ra["addendum_unlinked_AR_input"] = sum(1 for _, nid, _, _ in rows if note_type.get(nid) == "AR" and nid not in links)
    for sid, nid, subj, r in sorted(rows, key=lambda x: (rank.get(x[1], 0), x[1])):
        if nid in skip or nid in order_excl:
            continue
        cl = cls[nid]
        rid = P("rad", nid)
        sup = P("rad", sup_of[nid]) if sup_of.get(nid) else None
        unc = "ADDENDUM_UNLINKED" if note_type.get(nid) == "AR" and nid not in links else ("ADDENDUM_LINKED" if nid in links else "")
        per_stay[sid].append(TP.RawRecord(rid, subj, "radiology", f"note.radiology:{rid}", stay_id=sid if nid in links else None,
                                          observed_at=minutes(r.charttime), charted_at=minutes(r.charttime),
                                          signed_or_stored_at=minutes(r.storetime), evidence_type="IMAGING_REPORT",
                                          evidence_status=STATUS_OF.get(cl, "POSITIVE"), concept="CONCEPT:ctpa_filling_defect",
                                          pe_class=cl, supersedes=sup, uncertainty_status=unc))
        ra["cta_input"] += 1
    A["radiology"] = {**rad_st, **dict(ra)}

    # --- triage: stay 행(파생 증거 수 별도) ---
    ta = zeros(("rows", "rows_with_derived_evidence", "derived_evidence", "rows_on_time_undefined_stay"))
    for st in co.to_dict("records"):
        sid, subj = str(st["stay_id"]), str(st["subject_id"])
        tid = P("triage", sid)
        ev = MA.triage_records(tid, st, 0.0)
        ta["rows"] += 1
        ta["rows_with_derived_evidence"] += bool(ev)
        ta["derived_evidence"] += len(ev)
        if sid not in stays:
            ta["rows_on_time_undefined_stay"] += 1
            continue
        for e in ev:
            per_stay[sid].append(TP.RawRecord(e.evidence_id, subj, "triage", f"ed.triage:{tid}", stay_id=sid,
                                              evidence_type="VITAL" if e.source_type == "triage_vital" else "SYMPTOM",
                                              evidence_status=e.status.value, concept=e.node_id))
    A["triage"] = dict(ta)

    # --- ECG: study_id, ed_stay_id(dtype 정규화 후 매칭 건수 확인) ---
    ea = zeros(("no_stay_key", "stay_key_not_in_cohort", "on_time_undefined_stay", "matched"))
    ecg_u, ecg_st, _ = dedupe(ecg, "study_id", ["ed_stay_id", "ecg_time_ext"])
    key = pd.to_numeric(ecg_u["ed_stay_id"], errors="coerce").astype("Int64")
    for r, k in zip(ecg_u.itertuples(index=False), key):
        if pd.isna(k):
            ea["no_stay_key"] += 1
            continue
        sid = str(int(k))
        if sid not in subj_of:
            ea["stay_key_not_in_cohort"] += 1
            continue
        if sid not in stays:
            ea["on_time_undefined_stay"] += 1
            continue
        ea["matched"] += 1
        rid = P("ecg", r.study_id)
        per_stay[sid].append(TP.RawRecord(rid, subj_of[sid], "ecg_machine", f"ecg.machine_measurements:{rid}", stay_id=sid,
                                          observed_at=minutes(r.ecg_time_ext), concept="ECG:machine_read"))
    A["ecg"] = {**ecg_st, "ed_stay_id_dtype": str(ecg["ed_stay_id"].dtype), **dict(ea)}
    # 고유 기록 수(위 집계)와 별도로, 기록이 연결된 체류 수·환자 수(같은 기록을 체류마다 다시 세지 않음)
    for name, src in (("lab", "lab"), ("radiology", "radiology"), ("ecg", "ecg_machine"), ("triage", "triage")):
        sids = {sid for sid, recs in per_stay.items() if any(x.source == src for x in recs)}
        A[name]["stays_with_records"] = len(sids)
        A[name]["patients_with_records"] = len({subj_of[s] for s in sids})
    return Prepared(stays, undefined, subj_of, dict(per_stay), P, A, cls, links)
