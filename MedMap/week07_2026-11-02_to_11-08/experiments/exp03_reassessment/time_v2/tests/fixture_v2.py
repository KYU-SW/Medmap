"""v2 합성 parquet(지어낸 행 — 실제 MIMIC 없음). note_id 는 MIMIC 형식을 흉내 낸 가짜 값(비노출 시험용).

설계(시각 = 2150-01-01 10:00 기준 시간 h):
 체류: 11(p1, 0–8, triage 빈맥·SOB) · 12(p1, 20–22, T1=T2) · 22(p2, 0–4) · 31·32(p3, 0–5·4–9 겹침) · 41(p4, intime 결측)
       · 51(p5, 0–10) · 61(p6, 0–10) · 71(p7, 0–10) · 81(p8, 0–10) · 91(p9, 0–10)
 검사: L1(11, 1→2, 음성) L2(11, storetime 없음) L3(11, 역전 3→2) L4×2(11, 동일 중복 2→2.5) L5×2(시각 충돌 중복)
       L6(12, 21→21.5) L7(p3, 4.5 → AMBIGUOUS) L8(p1, 15 → 미귀속) L9(11, 7→9 POST_ED)
 영상: n1(11 CTA 급성 2→3) n2(22 CTA 3→6 POST_ED) n3(11 CTA 역전) n4×2(11 CT CHEST 비CTA, 동일 중복) n5(11 exam 없음)
       p1(51 CTA 음성 1→2) + a1(51 AR 급성 5→6, exam 없음 → 부모 유형, 양방향 연결 → p1 대체)
       p2(61 CTA 급성) + a2(61 AR NO_MENTION 연결 → 미투입)
       a3(71 AR 음성 2→2.5, 한 방향 연결만 → 미연결 별도 증거)
       p4(81 CTA 급성 1→2) + a4(81 AR 음성 5→6 연결 → p4 대체, AL2)
       n6(p3 CTA 4.5 → AMBIGUOUS) + a6(AR 음성, 연결 — 원 판독 AMBIGUOUS → 가족 미사용, 자기 시각 6h 는 체류 32 창)
       a7(p2 AR NO_MENTION 1→5 POST_ED, p1(환자 5)과 양방향 연결 — 다른 환자 → 연결 안 함, 체류 22 의 미연결 AR 증거)
       n7(91 CTA 만성 1→2 — STRICT=INSUFFICIENT_R3 → S2=INSUFFICIENT_NO_DECISIVE: 요약 상태 같고 범주만 다른 비대각 칸)
       a5(p1 AR 음성 21→21.5, n1 에 양방향 연결 — 자기 시각은 체류 12 창이지만 가족 귀속으로 체류 11, POST_ED)
 ECG: 7(ed_stay_id 11.0 float) · 8(코호트 밖 99) · 9(키 없음)
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

T0 = pd.Timestamp("2150-01-01 10:00")
POS = "FINDINGS: Filling defects in the right lower lobe segmental arteries.\nIMPRESSION: Acute pulmonary embolism."
NEG = "FINDINGS: The pulmonary arteries are well opacified.\nIMPRESSION: No evidence of pulmonary embolism."
NOM = "ADDENDUM: Findings were discussed with the referring team by telephone."
CHR = "IMPRESSION: Chronic pulmonary embolism in the right lower lobe, unchanged."
CTA = "CTA CHEST W&W/O C&RECONS, NON-CORONARY"
NIDS = {"n1": "90000001-RR-1", "n2": "90000002-RR-1", "n3": "90000001-RR-2", "n4": "90000001-RR-3", "n5": "90000001-RR-4",
        "p1": "90000005-RR-1", "a1": "90000005-AR-2", "p2": "90000006-RR-1", "a2": "90000006-AR-2", "a3": "90000007-AR-1",
        "p4": "90000008-RR-1", "a4": "90000008-AR-2", "n6": "90000003-RR-1", "a5": "90000001-AR-5", "a6": "90000003-AR-2", "a7": "90000002-AR-3", "n7": "90000009-RR-1"}


def ts(h):
    return None if h is None else T0 + pd.Timedelta(hours=h)


def stay(subj, sid, i, o, hr=None, cc=None):
    return {"subject_id": subj, "hadm_id": None, "stay_id": sid, "intime": ts(i), "outtime": ts(o), "gender": "F", "cohort_diseases": "",
            "temperature": None, "heartrate": hr, "resprate": None, "o2sat": None, "sbp": None, "dbp": None, "pain": None,
            "acuity": None, "chiefcomplaint": cc}


def lab(lid, subj, item, c, s, value=None, valuenum=None, upper=None, comments=None):
    return {"labevent_id": lid, "subject_id": subj, "hadm_id": None, "specimen_id": lid, "itemid": item, "charttime": ts(c),
            "storetime": ts(s), "value": value, "valuenum": valuenum, "valueuom": "ng/mL", "ref_range_lower": None,
            "ref_range_upper": upper, "flag": None, "priority": "STAT", "comments": comments}


def dd(lid, subj, c, s):
    return lab(lid, subj, 50915, c, s, "900", 900.0, 500.0)


def rad(k, subj, ntype, c, s, exam, text):
    return {"note_id": NIDS[k], "subject_id": subj, "hadm_id": None, "note_type": ntype, "note_seq": 1, "charttime": ts(c),
            "storetime": ts(s), "text": text, "exam_name": exam}


def frames():
    co = pd.DataFrame([stay(1, 11, 0, 8, hr=120, cc="SOB"), stay(1, 12, 20, 22), stay(2, 22, 0, 4), stay(3, 31, 0, 5), stay(3, 32, 4, 9),
                       stay(4, 41, None, 5), stay(5, 51, 0, 10), stay(6, 61, 0, 10), stay(7, 71, 0, 10), stay(8, 81, 0, 10), stay(9, 91, 0, 10)])
    labs = pd.DataFrame([lab(1, 1, 51003, 1, 2, None, None, 0.01, "<0.01.  cTropnT > 0.10 ng/mL"), dd(2, 1, 1, None), dd(3, 1, 3, 2),
                         dd(4, 1, 2, 2.5), dd(4, 1, 2, 2.5), dd(5, 1, 2, 2.5), dd(5, 1, 2, 4), dd(6, 1, 21, 21.5), dd(7, 3, 4.5, 5),
                         dd(8, 1, 15, 16), dd(9, 1, 7, 9)])
    rd = pd.DataFrame([rad("n1", 1, "RR", 2, 3, CTA, POS), rad("n2", 2, "RR", 3, 6, "CTA CHEST", POS), rad("n3", 1, "RR", 4, 3.5, CTA, POS),
                       rad("n4", 1, "RR", 1, 1.5, "CT CHEST W/CONTRAST", POS), rad("n4", 1, "RR", 1, 1.5, "CT CHEST W/CONTRAST", POS),
                       rad("n5", 1, "RR", 1, 1.5, None, POS), rad("p1", 5, "RR", 1, 2, CTA, NEG), rad("a1", 5, "AR", 5, 6, None, POS),
                       rad("p2", 6, "RR", 1, 2, CTA, POS), rad("a2", 6, "AR", 5, 6, CTA, NOM), rad("a3", 7, "AR", 2, 2.5, CTA, NEG),
                       rad("p4", 8, "RR", 1, 2, CTA, POS), rad("a4", 8, "AR", 5, 6, CTA, NEG), rad("n6", 3, "RR", 4.5, 5, CTA, POS),
                       rad("a5", 1, "AR", 21, 21.5, CTA, NEG), rad("a6", 3, "AR", 6, 7, CTA, NEG),
                       rad("a7", 2, "AR", 1, 5, CTA, NOM), rad("n7", 9, "RR", 1, 2, CTA, CHR)])
    ecg = pd.DataFrame([{"study_id": 7, "ed_stay_id": 11.0, "ecg_time_ext": ts(-2)}, {"study_id": 8, "ed_stay_id": 99.0, "ecg_time_ext": ts(1)},
                        {"study_id": 9, "ed_stay_id": None, "ecg_time_ext": ts(1)}])
    n = NIDS
    det = pd.DataFrame([(n["a1"], "parent_note_id", n["p1"]), (n["p1"], "addendum_note_id", n["a1"]),
                        (n["a2"], "parent_note_id", n["p2"]), (n["p2"], "addendum_note_id", n["a2"]),
                        (n["a4"], "parent_note_id", n["p4"]), (n["p4"], "addendum_note_id", n["a4"]),
                        (n["a3"], "parent_note_id", n["n1"]),                       # 한 방향만 → 미연결
                        (n["a5"], "parent_note_id", n["n1"]), (n["n1"], "addendum_note_id", n["a5"]),   # 자기 시각은 체류 12 창 → 가족 귀속 11
                        (n["a6"], "parent_note_id", n["n6"]), (n["n6"], "addendum_note_id", n["a6"]),   # 원 판독 AMBIGUOUS → 가족 미사용
                        (n["a7"], "parent_note_id", n["p1"]), (n["p1"], "addendum_note_id", n["a7"]),   # 다른 환자(p2 ↔ p5) → 연결 안 함
                        (n["n1"], "exam_name", CTA)], columns=["note_id", "field_name", "field_value"])
    return co, labs, rd, ecg, det


def write(d: Path) -> Path:
    co, labs, rd, ecg, det = frames()
    d.mkdir(parents=True)
    co.to_parquet(d / "cohort.parquet")
    labs.to_parquet(d / "labs.parquet")
    rd.to_parquet(d / "radiology.parquet")
    ecg.to_parquet(d / "ecg.parquet")
    det.to_parquet(d / "radiology_detail.parquet")
    return d
