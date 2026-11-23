"""EXP-03 §12: 실제 MIMIC(EXP-02 봉인 추출 extract_v2_20261030_1139) 시간정보 적합성 — 집계만(원문·식별자 비출력, 10 미만 '<10').
측정: 판독·검사의 시행(charttime)/확인(storetime) 결측·역전·지연 분위수, ED 체류 창 안 사건의 확인 시각 보유 비율, triage·ECG 시각 성격."""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

EXP02 = Path(__file__).resolve().parents[1] / "exp02_mimic_graph"
sys.path.insert(0, str(EXP02))
from mimic_adapter import classify_exam  # noqa: E402
from mimic_paths import SEALED, cell  # noqa: E402

SRC = SEALED / "extract_v2_20261030_1139"


def timing(df: pd.DataFrame, label: str) -> dict:
    ct, st = pd.to_datetime(df["charttime"]), pd.to_datetime(df["storetime"])
    d = (st - ct).dt.total_seconds() / 60
    ok = d.dropna()
    return {f"{label}_rows": cell(len(df)), f"{label}_charttime_missing": cell(ct.isna().sum()),
            f"{label}_storetime_missing": cell(st.isna().sum()),
            f"{label}_storetime_missing_rate": round(float(st.isna().mean()), 4) if len(df) else None,
            f"{label}_inversion_store_before_chart": cell((d < 0).sum()),
            f"{label}_delay_min_quantiles(p10,p50,p90)": [round(float(ok.quantile(q)), 1) for q in (0.1, 0.5, 0.9)] if len(ok) else None}


def main():
    co = pd.read_parquet(SRC / "cohort.parquet", columns=["subject_id", "stay_id", "intime", "outtime", "cohort_diseases"])
    co["intime"], co["outtime"] = pd.to_datetime(co["intime"]), pd.to_datetime(co["outtime"])
    rad = pd.read_parquet(SRC / "radiology.parquet", columns=["subject_id", "charttime", "storetime", "exam_name"])
    lab = pd.read_parquet(SRC / "labs.parquet", columns=["subject_id", "charttime", "storetime", "itemid"])
    ecg = pd.read_parquet(SRC / "ecg.parquet", columns=["ed_stay_id", "ecg_time_ext"])
    res = {"source": SRC.name, "created": datetime.now().isoformat(timespec="seconds")}
    res.update(timing(rad, "radiology_all"))
    rad["cls"] = rad["exam_name"].map(classify_exam)
    res.update(timing(rad[rad["cls"] == "CTA_CHEST"], "radiology_cta_chest"))
    res.update(timing(lab, "lab_target_items"))
    # ED 체류 창 안 사건
    win = []
    for name, df in (("radiology", rad), ("lab", lab)):
        m = df.merge(co[["subject_id", "stay_id", "intime", "outtime"]], on="subject_id")
        m["charttime"] = pd.to_datetime(m["charttime"])
        m = m[(m["charttime"] >= m["intime"]) & (m["charttime"] <= m["outtime"])]
        m["storetime"] = pd.to_datetime(m["storetime"])
        res[f"{name}_in_ed_window_events"] = cell(len(m))
        res[f"{name}_in_ed_window_storetime_missing"] = cell(m["storetime"].isna().sum())
        res[f"{name}_in_ed_window_available_after_ed_out"] = cell((m["storetime"] > m["outtime"]).sum())
        win.append(m.assign(miss=m["storetime"].isna())[["stay_id", "miss"]])
    w = pd.concat(win)
    per = w.groupby("stay_id")["miss"].any()
    res["stays_union"] = cell(len(co))
    res["stays_with_in_window_rad_or_lab"] = cell(len(per))
    res["stays_all_in_window_events_have_available_time"] = cell(int((~per).sum()))
    res["stays_all_in_window_events_have_available_time_rate"] = round(float((~per).mean()), 4) if len(per) else None
    res["ecg_rows"] = cell(len(ecg))
    res["ecg_time_missing"] = cell(pd.to_datetime(ecg["ecg_time_ext"]).isna().sum())
    res["notes"] = {"triage": "시각 열 없음 — EXP-02 는 ED 도착 시각 근사, EXP-03 P-AVAIL 엄격 적용 시 사용 불가(정책 결정 필요)",
                    "ecg": "기계 판독 시각(ecg_time, 기기 시계) 1개뿐 — 이용 가능 시각 = 시행 시각 가정 필요(정책 결정 필요)",
                    "working_diagnosis": "실제 WD 없음 — 재검토 알림의 의학적 정오 채점 불가"}
    out = Path(__file__).resolve().parent / "outputs" / f"mimic_time_audit_{datetime.now():%Y%m%d_%H%M}"
    out.mkdir(parents=True, exist_ok=False)
    (out / "mimic_time_audit_public.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
