"""무작위 합성 소규모 자료 생성기(지어낸 행 — 실제 MIMIC 없음). 관계 발견·역산 공격 시험용.

범주를 골고루 섞는다(도달 못 한 칸은 relations 의 generator_constant 로 분류 — '모든 칸이 달라진다'고 가정하지 않음): 체류 겹침·시각 불명·짧은 체류, 검사 시각 결측·역전·퇴실 후·중복(동일/충돌)·
창 밖, 영상 유형(CTA·CT CHEST·흉부 X선·exam 없음)·RR/AR·v3b 분류 5종 문장·연결(양방향·한 방향·다른 환자·부모 둘)·중복,
triage 활력징후 유무·이상, ECG 체류 키(코호트 안·밖·없음).
2026-11-03 보강: 연결 분기 전부 도달(이전 죽은 분기 수정) · charttime = storetime = intime 동점 · 영상 시각 충돌 중복 · addendum 이 원 판독보다 먼저 기록된 경우.
"""
from __future__ import annotations

import random
from pathlib import Path

import pandas as pd

T0 = pd.Timestamp("2150-01-01 00:00")
TEXTS = {"ACUTE": "FINDINGS: Filling defects in the right lower lobe segmental arteries.\nIMPRESSION: Acute pulmonary embolism.",
         "NEG": "FINDINGS: The pulmonary arteries are well opacified.\nIMPRESSION: No evidence of pulmonary embolism.",
         "NOM": "ADDENDUM: Findings were discussed with the referring team by telephone.",
         "CHR": "IMPRESSION: Chronic pulmonary embolism in the right lower lobe, unchanged.",
         "UNC": "IMPRESSION: Possible small subsegmental pulmonary embolism, cannot be excluded due to motion artifact."}
EXAMS = ["CTA CHEST W&W/O C&RECONS, NON-CORONARY", "CTA CHEST", "CT CHEST W/CONTRAST", "CHEST (PORTABLE AP)", None]
LAB_ITEMS = [51003, 50915, 51002, 50889]
CC = ["SOB", "Chest pain", "Fever", "Abd pain", "cough", None]


def ts(h):
    return None if h is None else T0 + pd.Timedelta(minutes=int(round(h * 60)))


def make(seed: int, d: Path) -> Path:
    R = random.Random(seed)
    stays, labs, rads, ecgs, det = [], [], [], [], []
    n_subj = R.randint(6, 18)
    # 자료마다 구성비를 크게 바꿈 — 소규모 자료 구성비에서 생기는 우연한 대소 관계를 줄임(2026-11-04)
    p_vit, lab_max, rad_max = R.choice([0.05, 0.7, 1.0]), R.choice([1, 6, 25]), R.choice([1, 4, 10])
    p_ecg, p_ar = R.choice([0.05, 0.5, 0.95]), R.choice([0.1, 0.35, 0.7])
    sid, lid, nid_n, eid = 1000, 1, {}, 1
    windows = {}
    for subj in range(1, n_subj + 1):
        base = R.uniform(0, 500)
        for j in range(R.choice([1, 1, 1, 2, 2, 3])):
            sid += 1
            start = base + j * R.choice([0.5, 3, 30, 100])                # 0.5·3 이면 겹침 가능
            dur = R.choice([1, 2, 2.5, 4, 6, 8, 12])
            i, o = start, start + dur
            if R.random() < 0.06:
                i = None
            if R.random() < 0.03 and i is not None:
                o = i - 1                                              # 역전
            vit = {c: None for c in ("temperature", "heartrate", "resprate", "o2sat", "sbp", "dbp", "pain", "acuity")}
            if R.random() < p_vit:
                vit["heartrate"] = R.choice([80, 115, 300])
                vit["temperature"] = R.choice([98.6, 101.5, None])
                vit["resprate"] = R.choice([16, 24, None])
                vit["o2sat"] = R.choice([97, 88, None])
            stays.append({"subject_id": subj, "hadm_id": None, "stay_id": sid, "intime": ts(i), "outtime": ts(o), "gender": "F",
                          "cohort_diseases": "", **vit, "chiefcomplaint": R.choice(CC)})
            windows[sid] = (subj, i if i is not None else start, o if i is not None else start + dur)
            ref = start
            for _ in range(R.randint(0, lab_max)):
                c = ref + R.uniform(-1, dur + 2)
                st = c + R.choice([0.3, 1, 2, dur + 3, -0.5])
                if R.random() < 0.08:
                    c, st = ref, ref                                    # 분 단위 동점: charttime = storetime = intime(T0 사용 칸 도달)
                if R.random() < 0.08:
                    st = None
                item = R.choice(LAB_ITEMS)
                row = {"labevent_id": lid, "subject_id": subj, "hadm_id": None, "specimen_id": lid, "itemid": item, "charttime": ts(c),
                       "storetime": ts(st), "value": R.choice(["900", "<0.01", None]), "valuenum": R.choice([900.0, 0.005, None]),
                       "valueuom": "ng/mL", "ref_range_lower": None, "ref_range_upper": R.choice([500.0, 0.01, None]), "flag": None,
                       "priority": "STAT", "comments": None}
                labs.append(row)
                if R.random() < 0.07:
                    labs.append(dict(row))                              # 동일 중복
                if R.random() < 0.05:
                    labs.append({**row, "storetime": ts((st or c) + 5)})  # 시각 충돌 중복
                lid += 1
            parents = []
            for _ in range(R.randint(0, rad_max)):
                c = ref + R.uniform(-1, dur + 1)
                st = c + R.choice([0.5, 1.5, dur + 2, -0.3])
                if R.random() < 0.08:
                    c, st = ref, ref                                    # 분 단위 동점
                if R.random() < 0.06:
                    st = None
                nid = f"{subj:08d}-RR-{len(nid_n.setdefault(subj, [])) + 1}"
                nid_n[subj].append(nid)
                ex = R.choice(EXAMS)
                row = {"note_id": nid, "subject_id": subj, "hadm_id": None, "note_type": "RR", "note_seq": 1, "charttime": ts(c),
                       "storetime": ts(st), "text": TEXTS[R.choice(list(TEXTS))], "exam_name": ex}
                rads.append(row)
                if R.random() < 0.05:
                    rads.append(dict(row))
                if R.random() < 0.04:
                    rads.append({**row, "storetime": ts((st if st is not None else c) + 4)})   # 영상 시각 충돌 중복
                parents.append((nid, c, st))
            for pnid, pc, pst in parents:
                if R.random() < p_ar:
                    anid = f"{subj:08d}-AR-{len(nid_n[subj]) + 1}"
                    nid_n[subj].append(anid)
                    c = pc + R.choice([0.2, 2, dur + 30])
                    ast = c + R.choice([0.3, 1, -0.2])
                    if pst is not None and R.random() < 0.8:
                        ast = max(ast, pst + 0.1)
                    elif pst is not None:
                        c, ast = pc - R.choice([0, 0.5]), pst - R.choice([0, 0.2, 0.7])   # 원 판독보다 이른 기록(§5-1 제외 규칙 시험)
                    rads.append({"note_id": anid, "subject_id": subj, "hadm_id": None, "note_type": "AR", "note_seq": 2,
                                 "charttime": ts(c), "storetime": ts(ast), "text": TEXTS[R.choice(list(TEXTS))],
                                 "exam_name": R.choice([None, EXAMS[0], EXAMS[2]])})
                    mode = R.random()
                    if mode < 0.55:
                        det += [(anid, "parent_note_id", pnid), (pnid, "addendum_note_id", anid)]
                    elif mode < 0.65:
                        det += [(anid, "parent_note_id", pnid)]
                    elif mode < 0.72:
                        det += [(pnid, "addendum_note_id", anid)]                 # addendum 필드만
                    elif mode < 0.76:
                        det += [(anid, "parent_note_id", f"{subj:08d}-RR-999"), (f"{subj:08d}-RR-999", "addendum_note_id", anid)]  # 부모 추출 없음
                    elif mode < 0.8 and len(parents) > 1:
                        q = parents[-1][0] if parents[-1][0] != pnid else parents[0][0]
                        det += [(q, "parent_note_id", pnid), (pnid, "addendum_note_id", q)]   # 자식이 AR 아님
                    elif mode < 0.9 and subj > 1:
                        other = f"{subj - 1:08d}-RR-1"
                        det += [(anid, "parent_note_id", other), (other, "addendum_note_id", anid)]
                    elif len(parents) > 1:
                        q = parents[0][0] if parents[0][0] != pnid else parents[-1][0]
                        det += [(anid, "parent_note_id", pnid), (pnid, "addendum_note_id", anid),
                                (anid, "parent_note_id", q), (q, "addendum_note_id", anid)]
            if R.random() < p_ecg:
                for _ in range(R.choice([1, 1, 2, 3])):                 # 체류당 ECG 여러 건(기록 수 ≠ 체류 수)
                    ecgs.append({"study_id": eid, "ed_stay_id": float(sid), "ecg_time_ext": ts(ref)})
                    eid += 1
    for _ in range(R.randint(0, 2)):
        ecgs.append({"study_id": eid, "ed_stay_id": R.choice([None, 99999.0]), "ecg_time_ext": ts(1)})
        eid += 1
    if ecgs and R.random() < 0.3:
        ecgs.append({**ecgs[0], "ecg_time_ext": ts(77)})                       # ECG 시각 충돌 중복
    if ecgs and R.random() < 0.2:
        ecgs.append(dict(ecgs[-1]))                                           # ECG 동일 중복
    if R.random() < 0.2:
        ecgs.append({"study_id": None, "ed_stay_id": 1001.0, "ecg_time_ext": ts(1)})   # 키 결측
    if labs and R.random() < 0.2:
        labs.append({**labs[0], "labevent_id": None})                          # 키 결측
    if rads and R.random() < 0.2:
        rads.append({**rads[0], "note_id": None})                              # 키 결측
    d.mkdir(parents=True)
    pd.DataFrame(stays).to_parquet(d / "cohort.parquet")
    cols_l = ["labevent_id", "subject_id", "hadm_id", "specimen_id", "itemid", "charttime", "storetime", "value", "valuenum", "valueuom",
              "ref_range_lower", "ref_range_upper", "flag", "priority", "comments"]
    pd.DataFrame(labs, columns=cols_l).astype({"value": object, "labevent_id": "Int64"}).to_parquet(d / "labs.parquet")
    cols_r = ["note_id", "subject_id", "hadm_id", "note_type", "note_seq", "charttime", "storetime", "text", "exam_name"]
    pd.DataFrame(rads, columns=cols_r).to_parquet(d / "radiology.parquet")
    pd.DataFrame(ecgs, columns=["study_id", "ed_stay_id", "ecg_time_ext"]).astype({"study_id": "Int64"}).to_parquet(d / "ecg.parquet")
    pd.DataFrame(det, columns=["note_id", "field_name", "field_value"]).to_parquet(d / "radiology_detail.parquet")
    return d
