"""EXP-03-TIME 정상 사례 테스트(합성 — 실제 환자·시각 없음). 사례 표 = (ID, 정책, 질의 시점, 기대, 이유) 를 실행 전 고정."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import time_policy as TP  # noqa: E402
from reassess import PE, assess  # noqa: E402

ST = "STRICT_AVAILABLE_TIME"
S1 = "S1_TRIAGE_AT_INTIME_APPROX"
S2 = "S2_STRICT_A_ONLY"
STAY = TP.Stay("st1", "p1", 1000.0, 1480.0)                   # 도착 1000, 퇴실 1480(분 단위 가상)
STAY2 = TP.Stay("st2", "p1", 5000.0, 5400.0)                  # 같은 환자 다른 체류
HYP = [("h1", PE, 1000.0)]

CASES = [
    ("TP01", ST, 1000, "triage 미사용(UNKNOWN_AVAILABILITY)", "triage 표에 시각 없음 — 공식 문서"),
    ("TP02", S1, 990, "triage 미사용(도착 전)", "근사 정책도 intime 이전에는 이용 불가"),
    ("TP02b", S1, 1000, "triage 사용(APPROX 표시)", "근사 가정 — intime 부터"),
    ("TP03", ST, 1000, "요약 INSUFFICIENT / S1 에서는 SUPPORTED", "triage 주입 여부가 상태를 바꿈(근사 비교)"),
    ("TP04", ST, 1480, "ECG 장비 시각이 도착 전 → 미사용(NOT_IDENTIFIABLE)", "장비 시계 비동기"),
    ("TP05", S1, 1480, "ECG 장비 시각 크게 앞/뒤 → 모든 정책 미사용", "보정 근거 없음 — 비교 만들지 않음"),
    ("TP06", ST, 1480, "ECG 파형·기계 해석·의사 판독 3종 각각 미사용, 별개 기록", "구성요소 분리"),
    ("TP07", ST, 1100, "영상 charttime 1050 ≠ storetime 1150 → 1100 미사용, 1150 사용(PROXY)", "storetime 보수적 대리"),
    ("TP07b", S2, 1480, "S2 에서는 영상 판독 미사용(EXCLUDED_BY_POLICY)", "대리 시각 제외 민감도"),
    ("TP08", ST, 1480, "storetime 없음 → UNKNOWN_AVAILABILITY, storetime<charttime → TIME_CONFLICT, 둘 다 미사용", "시각 생성·대체 금지"),
    ("TP09", ST, 1480, "퇴실 후 서명 판독 → ED 체크포인트 미사용(POST_ED), 이후 1600 에서만 사용", "ED 시점 판단에서 보류"),
    ("TP10", ST, 5100, "같은 subject 두 체류 — 관찰 시각 창으로 귀속, 다른 체류 기록 제외, 겹치는 창 AMBIGUOUS", "hadm/subject 만으로 합치지 않음"),
    ("TP11", ST, 1400, "명시 정정 → 원 판독 무효·알림 / 연결 없는 추가 판독은 별도 증거", "addendum 자동 대체 없음"),
    ("TP12", ST, 1200, "의뢰만 있고 결과 없음 → PENDING", "대기 ≠ 음성"),
    ("TP13", ST, 1300, "급성 → SUPPORTED / 만성 → INSUFFICIENT / 불확실 → UNKNOWN", "의미 보존"),
    ("TP14", ST, 1100, "검사 charttime 1050·storetime 1120 → 1100 미사용, 1120 사용(A, PROXY 아님)", "labevents storetime = 이용 가능 시각"),
    ("TP15", ST, 1480, "vitalsign charttime → 주 분석 미사용", "기록 시각, 소급 여부 불명"),
    ("TP16", ST, 1300, "급성 PE 명시 음성 CT + 다른 질환 가설 → CONFLICT 아님", "급성 PE 부재 ≠ 다른 질환 부재"),
    ("TP17", ST, 1480, "출처 없는 기록 거부(REJECTED_NO_SOURCE)", "근거 추적 필수"),
]


def rad(rid, cls, obs, store, **kw):
    return TP.RawRecord(rid, "p1", "radiology", f"synthetic:{rid}", observed_at=obs, charted_at=obs, signed_or_stored_at=store,
                        evidence_type="IMAGING_REPORT", evidence_status="POSITIVE" if cls != "NEGATIVE" else "NEGATIVE",
                        concept="CONCEPT:ctpa_filling_defect", pe_class=cls, **kw)


TRIAGE = TP.RawRecord("tri1", "p1", "triage", "synthetic:tri1", stay_id="st1", evidence_type="VITAL", concept="HP:0001649")


class TimePolicy(unittest.TestCase):
    def test_case_table_complete(self):
        self.assertEqual(len({c[0] for c in CASES}), len(CASES))

    def test_TP01_TP02_triage(self):
        b = TP.build(STAY, [STAY], [TRIAGE], ST, HYP)
        self.assertEqual(TP.used_at(b, 1000), [])
        self.assertEqual(b.audit["flag:UNKNOWN_AVAILABILITY"], 1)
        b1 = TP.build(STAY, [STAY], [TRIAGE], S1, HYP)
        self.assertEqual(TP.used_at(b1, 990), [])
        self.assertEqual(TP.used_at(b1, 1000), ["tri1"])
        self.assertTrue(b1.meta["tri1"].approx)

    def test_TP03_triage_injection_changes_state(self):
        st = assess(TP.build(STAY, [STAY], [TRIAGE], ST, HYP).timeline, 1000)
        s1 = assess(TP.build(STAY, [STAY], [TRIAGE], S1, HYP).timeline, 1000)
        self.assertEqual((st.summary, s1.summary), ("INSUFFICIENT", "SUPPORTED"))

    def test_TP04_TP05_TP06_ecg(self):
        recs = [TP.RawRecord("ecg_early", "p1", "ecg_machine", "synthetic:e1", stay_id="st1", observed_at=900.0, concept="HP:0012251"),
                TP.RawRecord("ecg_far", "p1", "ecg_machine", "synthetic:e2", stay_id="st1", observed_at=9000.0, concept="HP:0012251"),
                TP.RawRecord("ecg_wave", "p1", "ecg_waveform", "synthetic:e3", stay_id="st1", observed_at=1100.0),
                TP.RawRecord("ecg_cardio", "p1", "ecg_cardiologist", "synthetic:e4", stay_id="st1", observed_at=1100.0)]
        for pol in TP.POLICIES:
            b = TP.build(STAY, [STAY], recs, pol, HYP)
            self.assertEqual(TP.used_at(b, 1480), [], pol)
            self.assertEqual(b.audit["flag:NOT_IDENTIFIABLE"], 4, pol)

    def test_TP07_radiology_storetime_proxy(self):
        b = TP.build(STAY, [STAY], [rad("r1", "ACUTE_POS", 1050.0, 1150.0)], ST, HYP)
        self.assertEqual(TP.used_at(b, 1100), [])
        self.assertEqual(TP.used_at(b, 1150), ["r1"])
        self.assertTrue(b.meta["r1"].proxy)
        self.assertEqual(TP.policy_counts(b, 1150)["proxy_used"], 1)
        b2 = TP.build(STAY, [STAY], [rad("r1", "ACUTE_POS", 1050.0, 1150.0)], S2, HYP)
        self.assertEqual(TP.used_at(b2, 1480), [])
        self.assertEqual(b2.audit["flag:EXCLUDED_BY_POLICY"], 1)

    def test_TP08_missing_or_inverted_storetime(self):
        b = TP.build(STAY, [STAY], [rad("r1", "ACUTE_POS", 1050.0, None), rad("r2", "ACUTE_POS", 1100.0, 1090.0)], ST, HYP)
        self.assertEqual(TP.used_at(b, 1480), [])
        self.assertEqual((b.audit["flag:UNKNOWN_AVAILABILITY"], b.audit["flag:TIME_CONFLICT"]), (1, 1))

    def test_TP09_signed_after_ed_out(self):
        b = TP.build(STAY, [STAY], [rad("r1", "ACUTE_POS", 1400.0, 1600.0)], ST, HYP)
        self.assertEqual(TP.used_at(b, 1480), [])
        self.assertEqual(TP.used_at(b, 1600), ["r1"])
        self.assertEqual(b.meta["r1"].flag, "POST_ED")

    def test_TP10_multiple_stays(self):
        recs = [rad("r_s1", "ACUTE_POS", 1100.0, 1150.0), rad("r_s2", "NEGATIVE", 5100.0, 5150.0)]
        b2 = TP.build(STAY2, [STAY, STAY2], recs, ST, [("h1", PE, 5000.0)])
        self.assertEqual(TP.used_at(b2, 5400), ["r_s2"])
        self.assertEqual(b2.audit["OTHER_OR_NO_STAY"], 1)
        overlap = TP.Stay("st3", "p1", 1400.0, 1600.0)
        b = TP.build(STAY, [STAY, overlap], [rad("r_ov", "ACUTE_POS", 1450.0, 1460.0)], ST, HYP)
        self.assertEqual(b.audit["AMBIGUOUS_STAY"], 1)
        self.assertEqual(TP.used_at(b, 1480), [])

    def test_TP11_correction_and_unlinked_addendum(self):
        recs = [rad("r1", "ACUTE_POS", 1050.0, 1100.0), rad("r1c", "NEGATIVE", 1050.0, 1300.0, supersedes="r1"),
                rad("ad1", "UNCERTAIN", 1050.0, 1350.0)]
        a = assess(TP.build(STAY, [STAY], recs, ST, HYP).timeline, 1400)
        self.assertEqual(a.summary, "CONFLICT")
        self.assertEqual({x["rule"] for x in a.alerts}, {"AL1_NEW_CONFLICT", "AL2_SUPPORT_RETRACTED"})
        self.assertIn("ad1", [r[0] for r in a.relations])                  # 연결 없는 추가 판독 = 별도 증거
        self.assertNotIn("r1", [r[0] for r in a.relations])

    def test_TP12_order_pending(self):
        o = TP.RawRecord("o1", "p1", "order", "synthetic:o1", observed_at=1100.0, evidence_type="IMAGING_ORDER",
                         evidence_status="PENDING", concept="CONCEPT:ctpa_filling_defect")
        a = assess(TP.build(STAY, [STAY], [o], ST, HYP).timeline, 1200)
        self.assertEqual(a.summary, "PENDING")
        self.assertFalse(a.flags["conflict"])

    def test_TP13_acute_chronic_uncertain(self):
        for cls, want in (("ACUTE_POS", "SUPPORTED"), ("CHRONIC_OR_PERSISTENT", "INSUFFICIENT"), ("UNCERTAIN", "UNKNOWN")):
            a = assess(TP.build(STAY, [STAY], [rad("r1", cls, 1100.0, 1200.0)], ST, HYP).timeline, 1300)
            self.assertEqual(a.summary, want, cls)

    def test_TP14_lab_storetime_documented(self):
        lab = TP.RawRecord("l1", "p1", "lab", "synthetic:l1", observed_at=1050.0, signed_or_stored_at=1120.0, evidence_type="LAB",
                           concept="HP:0033106")
        b = TP.build(STAY, [STAY], [lab], ST, HYP)
        self.assertEqual(TP.used_at(b, 1100), [])
        self.assertEqual(TP.used_at(b, 1120), ["l1"])
        self.assertEqual((b.meta["l1"].grade, b.meta["l1"].proxy), (TP.A, False))

    def test_TP15_vitalsign_not_used(self):
        v = TP.RawRecord("v1", "p1", "vitalsign", "synthetic:v1", stay_id="st1", observed_at=1100.0, charted_at=1100.0,
                         evidence_type="VITAL", concept="HP:0001649")
        self.assertEqual(TP.used_at(TP.build(STAY, [STAY], [v], ST, HYP), 1480), [])

    def test_TP16_pe_negative_not_conflict_for_other_dx(self):
        a = assess(TP.build(STAY, [STAY], [rad("r1", "NEGATIVE", 1100.0, 1200.0)], ST, [("h1", "DX:Tuberculosis", 1000.0)]).timeline, 1300)
        self.assertNotEqual(a.summary, "CONFLICT")
        self.assertEqual(a.alerts, [])

    def test_TP17_no_source_rejected(self):
        r = TP.RawRecord("x", "p1", "lab", "", observed_at=1050.0, signed_or_stored_at=1100.0, evidence_type="LAB", concept="HP:0033106")
        b = TP.build(STAY, [STAY], [r], ST, HYP)
        self.assertEqual(b.audit["REJECTED_NO_SOURCE"], 1)
        self.assertEqual(TP.used_at(b, 1480), [])

    def test_strict_safety_properties(self):
        """주 분석 안전 조건: 등급 C 사용 0, 이용 전 사용 0(누출), 사용 기록 출처 100%."""
        recs = [TRIAGE, rad("r1", "ACUTE_POS", 1050.0, 1150.0), rad("r2", "ACUTE_POS", 1100.0, None),
                TP.RawRecord("e", "p1", "ecg_machine", "synthetic:e", stay_id="st1", observed_at=1010.0),
                TP.RawRecord("l1", "p1", "lab", "synthetic:l1", observed_at=1050.0, signed_or_stored_at=1120.0, evidence_type="LAB",
                             concept="HP:0033106")]
        b = TP.build(STAY, [STAY], recs, ST, HYP)
        for T in (1000, 1100, 1120, 1150, 1480):
            used = TP.used_at(b, T)
            self.assertTrue(all(b.meta[i].grade in (TP.A, TP.B) for i in used))
            self.assertTrue(all(b.meta[i].available_at <= T for i in used))
            self.assertTrue(all(e.source_reference for e in b.timeline.evidence))
            self.assertEqual(assess(b.timeline, T).key(), assess(b.timeline.truncated(T), T).key())


if __name__ == "__main__":
    unittest.main()
