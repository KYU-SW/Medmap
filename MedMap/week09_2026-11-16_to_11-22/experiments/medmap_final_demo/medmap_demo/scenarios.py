"""합성 환자 시나리오(실제 진료자료 아님).

1) demo_case(): 최종발표 시연용 환자 SYN-001(진단 가설: pulmonary embolism) — 요청→대기→결과→정정→과거 재생 + 중복·지연 도착·다른 환자 혼입·
   출처 모름·시각 모름·취소·가설 미연결.
2) generate(seed, n_patients): 비교 실험용 무작위 합성 사건. 각 계보는 템플릿에서 만들고, 템플릿이 조회 시점별 '예상 정답'을
   엔진 코드와 따로(템플릿 시간표만으로) 정의한다.
근거 문장은 기존 D 모델 입력 형식(영어 근거 문장)에 맞춘 합성 문장이다.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from .replay import Case

KST = timezone(timedelta(hours=9))
T0 = datetime(2026, 3, 1, 9, 0, tzinfo=KST)


def at(minutes: float | None):
    return None if minutes is None else (T0 + timedelta(minutes=minutes)).isoformat()


def demo_case():
    case = Case("SYN-001", ("ED-ENC-001",), "H-PE", "pulmonary embolism")
    P, F, H = "SYN-001", "ED-ENC-001", ["H-PE"]
    ev = [
        # D-dimer: 요청 → 대기 → 결과(10:05)
        dict(event_id="DD-ORD", lineage_id="L-DDIMER", kind="LAB", item="D-dimer", status="ORDERED", recorded_at=at(10), note="D-dimer 검사 요청"),
        dict(event_id="DD-PEN", lineage_id="L-DDIMER", kind="LAB", item="D-dimer", status="PENDING", recorded_at=at(20), observed_at=at(18),
             note="검체 채취, 결과 대기"),
        dict(event_id="DD-R1", lineage_id="L-DDIMER", kind="LAB", item="D-dimer", status="AVAILABLE", recorded_at=at(65), observed_at=at(18),
             available_at=at(65), source="Central lab", content="D-dimer elevated at 2.4 mg/L FEU.", note="결과 이용 가능"),
        # 같은 결과가 인터페이스 재전송으로 다른 계보 ID 로 다시 들어옴(중복)
        dict(event_id="DD-R1-RESEND", lineage_id="L-DDIMER-IF2", kind="LAB", item="D-dimer", status="AVAILABLE", recorded_at=at(80), observed_at=at(18),
             available_at=at(65), source="Central lab", content="D-dimer elevated at 2.4 mg/L FEU.", note="인터페이스 재전송(중복)"),
        # CT 폐동맥 조영: 요청 → 대기 → 예비 판독(11:30) → 정정 판독(13:10)
        dict(event_id="CT-ORD", lineage_id="L-CTPA", kind="IMAGING", item="CT pulmonary angiogram", status="ORDERED", recorded_at=at(75),
             note="CT 폐동맥 조영 요청"),
        dict(event_id="CT-PEN", lineage_id="L-CTPA", kind="IMAGING", item="CT pulmonary angiogram", status="PENDING", recorded_at=at(100), observed_at=at(98),
             note="촬영 완료, 판독 대기"),
        dict(event_id="CT-R1", lineage_id="L-CTPA", kind="IMAGING", item="CT pulmonary angiogram", status="AVAILABLE", recorded_at=at(150), observed_at=at(98),
             available_at=at(150), source="Radiology (preliminary read)", content="CT pulmonary angiogram: no pulmonary embolism identified.",
             note="예비 판독"),
        dict(event_id="CT-R2", lineage_id="L-CTPA", kind="IMAGING", item="CT pulmonary angiogram", status="CORRECTED", recorded_at=at(250), observed_at=at(98),
             available_at=at(250), source="Radiology (final read)", prev_version_id="CT-R1",
             content="Addendum: segmental filling defect in the right lower lobe pulmonary artery, consistent with acute pulmonary embolism.",
             note="최종 판독으로 정정"),
        # 트로포닌: 요청 후 취소
        dict(event_id="TR-ORD", lineage_id="L-TROP", kind="LAB", item="Troponin I", status="ORDERED", recorded_at=at(10), note="트로포닌 요청"),
        dict(event_id="TR-CAN", lineage_id="L-TROP", kind="LAB", item="Troponin I", status="CANCELLED", recorded_at=at(40), note="요청 취소"),
        # 심전도: 09:15 촬영·09:20 이용 가능이지만 인터페이스 지연으로 12:00 에 기록(늦은 도착)
        dict(event_id="ECG-1", lineage_id="L-ECG", kind="ECG", item="12-lead ECG", status="AVAILABLE", recorded_at=at(180), observed_at=at(15),
             available_at=at(20), source="ECG cart", content="Sinus tachycardia at 112 bpm with S1Q3T3 pattern.", note="늦게 도착한 기록"),
        # 산소포화도: 출처 모름
        dict(event_id="VS-1", lineage_id="L-SPO2", kind="VITAL", item="Pulse oximetry", status="AVAILABLE", recorded_at=at(30), observed_at=at(28),
             available_at=at(30), source=None, content="Oxygen saturation 90% on room air.", note="출처 정보 없음"),
        # 하지 정맥 초음파: 이용 가능 시각 모름
        dict(event_id="US-1", lineage_id="L-DUPLEX", kind="IMAGING", item="Lower extremity duplex", status="AVAILABLE", recorded_at=at(200),
             observed_at=at(190), available_at=None, source="Vascular lab", content="Duplex ultrasound shows thrombus in the left popliteal vein.",
             note="이용 가능 시각 누락"),
        # 다른 환자(SYN-002)의 흉부 X선이 이 환자 수신 묶음에 섞임
        dict(event_id="XR-OTHER", lineage_id="L-CXR-SYN002", kind="IMAGING", item="Chest X-ray", status="AVAILABLE", recorded_at=at(60), observed_at=at(50),
             available_at=at(60), source="Radiology", content="Right lower lobe consolidation.", patient_id="SYN-002", note="다른 환자 기록 혼입"),
        # 이 가설과 연결되지 않은 기록
        dict(event_id="NT-1", lineage_id="L-NOTE-ADMIN", kind="NOTE", item="Registration note", status="AVAILABLE", recorded_at=at(5), observed_at=at(5),
             available_at=at(5), source="Registration desk", content="Insurance card scanned at registration.", hypothesis_ids=[],
             note="가설 연결 태그 없음(시나리오 지정, 행정 기록)"),
    ]
    raws = []
    for e in ev:
        e.setdefault("patient_id", P)
        e.setdefault("feed_id", F)
        e.setdefault("hypothesis_ids", H)
        raws.append(e)
    steps = [("검사 요청", at(15)), ("결과 대기", at(30)), ("D-dimer 결과 이용 가능", at(70)), ("CT 예비 판독", at(155)), ("늦은 기록 도착", at(185)),
             ("CT 판독 정정", at(255)), ("과거 시점 재생(CT 예비 판독 시점)", at(155))]
    return case, raws, steps


# ---------------- 비교 실험용 생성기 ----------------
@dataclass
class Gold:
    """계보 하나의 조회 시점별 예상 정답. used(as_of) → 사용해야 할 event_id 또는 None, reason(as_of) → 예상 사유 코드 또는 None(계보가 아직 없음/사용)."""
    lineage_id: str
    template: str
    timeline: list            # [(분, used_event_id|None, reason|None)] — 분 이상인 조회 시점부터 적용, 앞에 없으면 '아직 없음'
    dup_group: str | None = None
    superseded_ids: tuple = ()   # (분, event_id): 그 분 이후 정정으로 대체된 버전
    other_patient: bool = False
    copy_ids: tuple = ()         # 이 계보의 중복 사본 기록 ID(지표 C 용 — ID 접미사 규칙 대신 정답에서 받음)

    def at(self, m: float):
        cur = ("ABSENT", None, None)
        for t, u, r in self.timeline:
            if m >= t:
                cur = ("PRESENT", u, r)
        return cur


SENTS = {"PE": ["D-dimer elevated at {v} mg/L FEU.", "CT angiogram shows filling defect in segmental artery.", "No pulmonary embolism identified on CT angiogram.",
                "Oxygen saturation {v}% on room air.", "Heart rate {v} bpm, sinus tachycardia."]}


def _templates():
    return ("plain", "late_release", "corrected", "dup_same_lineage", "dup_cross_lineage", "late_arrival", "time_missing", "other_patient", "cancelled",
            "source_unknown", "corrected_with_resend")


def generate(seed: int = 20261116, n_patients: int = 60):
    """반환: [(case, raws, golds, query_minutes)]. 시각은 분 단위 정수(T0 기준)로 만들고 ISO 로 변환."""
    rng = random.Random(seed)
    out = []
    for pi in range(n_patients):
        pid, feed = f"GEN-{pi:03d}", f"FEED-{pi:03d}"
        case = Case(pid, (feed,), "H-PE", "pulmonary embolism")
        raws, golds, marks = [], [], set()
        tpls = rng.sample(_templates(), rng.randint(4, 7))
        for li, tpl in enumerate(tpls):
            lid, item = f"{pid}-L{li}", f"Test{li}"
            t0 = rng.randint(0, 60)
            t1 = t0 + rng.randint(5, 30)
            t2 = t1 + rng.randint(10, 90)
            txt = rng.choice(SENTS["PE"]).format(v=rng.randint(1, 200))
            src = rng.choice(["Central lab", "Radiology", "ECG cart"])
            base = dict(patient_id=pid, feed_id=feed, lineage_id=lid, kind="LAB", item=item, hypothesis_ids=["H-PE"])

            def ev(eid, status, rec, **kw):
                d = {**base, "event_id": f"{lid}-{eid}", "status": status, "recorded_at": at(rec)}
                for k in ("observed_at", "available_at"):
                    if k in kw:
                        kw[k] = at(kw[k])
                d.update(kw)
                raws.append(d)
                return d["event_id"]

            o = ev("ORD", "ORDERED", t0)
            p = ev("PEN", "PENDING", t1, observed_at=t1)
            tl = [(t0, None, "EVIDENCE_ORDERED_ONLY"), (t1, None, "EVIDENCE_PENDING")]
            g = Gold(lid, tpl, tl)
            if tpl == "plain":
                r = ev("R1", "AVAILABLE", t2, observed_at=t1, available_at=t2, source=src, content=txt)
                tl.append((t2, r, None))
            elif tpl == "late_release":                       # 결과 기록은 t2 에 들어왔으나 이용 가능은 t3
                t3 = t2 + rng.randint(20, 120)
                r = ev("R1", "AVAILABLE", t2, observed_at=t1, available_at=t3, source=src, content=txt)
                tl += [(t2, None, "EVIDENCE_NOT_YET_AVAILABLE"), (t3, r, None)]
            elif tpl == "corrected":
                t3 = t2 + rng.randint(20, 150)
                r1 = ev("R1", "AVAILABLE", t2, observed_at=t1, available_at=t2, source=src, content=txt)
                r2 = ev("R2", "CORRECTED", t3, observed_at=t1, available_at=t3, source=src, content="Corrected report: " + txt, prev_version_id=r1)
                tl += [(t2, r1, None), (t3, r2, None)]
                g.superseded_ids = ((t3, r1),)
            elif tpl == "dup_same_lineage":
                t3 = t2 + rng.randint(1, 60)
                r1 = ev("R1", "AVAILABLE", t2, observed_at=t1, available_at=t2, source=src, content=txt)
                cp = ev("R1DUP", "AVAILABLE", t3, observed_at=t1, available_at=t2, source=src, content=txt)
                tl.append((t2, r1, None))
                g.dup_group, g.copy_ids = lid, (cp,)
            elif tpl == "dup_cross_lineage":                  # 원본 계보 + 재전송 계보(다른 lineage)
                t3 = t2 + rng.randint(1, 60)
                r1 = ev("R1", "AVAILABLE", t2, observed_at=t1, available_at=t2, source=src, content=txt)
                tl.append((t2, r1, None))
                g.dup_group = lid
                lid2 = f"{lid}-IF2"
                d = {**base, "lineage_id": lid2, "event_id": f"{lid2}-R1", "status": "AVAILABLE", "recorded_at": at(t3), "observed_at": at(t1),
                     "available_at": at(t2), "source": src, "content": txt}
                raws.append(d)
                golds.append(Gold(lid2, "dup_cross_lineage_copy", [(t3, None, "DUPLICATE_EVIDENCE")], dup_group=lid, copy_ids=(f"{lid2}-R1",)))
            elif tpl == "late_arrival":                       # 관찰·가용은 이르지만 기록 도착이 늦음
                t4 = t2 + rng.randint(60, 200)
                r = ev("R1", "AVAILABLE", t4, observed_at=t1, available_at=t2, source=src, content=txt)
                tl.append((t4, r, None))
            elif tpl == "time_missing":
                ev("R1", "AVAILABLE", t2, observed_at=t1, available_at=None, source=src, content=txt)
                tl.append((t2, None, "TIME_UNKNOWN"))
            elif tpl == "other_patient":                      # 다른 환자 기록이 이 수신 묶음으로 들어옴(별도 계보)
                raws.pop()
                raws.pop()
                tl.clear()
                oid = f"{lid}-X"
                raws.append({**base, "patient_id": f"OTHER-{pi:03d}", "lineage_id": oid, "event_id": f"{oid}-R1", "status": "AVAILABLE",
                             "recorded_at": at(t2), "observed_at": at(t1), "available_at": at(t2), "source": src, "content": txt})
                g = Gold(oid, tpl, [(t2, None, "PATIENT_MISMATCH")], other_patient=True)
            elif tpl == "cancelled":
                ev("CAN", "CANCELLED", t2)
                tl.append((t2, None, "EVIDENCE_CANCELLED"))
            elif tpl == "corrected_with_resend":              # 원본 v1 의 재전송 사본(다른 계보)이 정정 전에 도착, 이후 원본 계보가 정정됨(1차 심사 반영)
                t4 = t2 + rng.randint(1, 20)
                t3 = t4 + rng.randint(5, 120)
                r1 = ev("R1", "AVAILABLE", t2, observed_at=t1, available_at=t2, source=src, content=txt)
                r2 = ev("R2", "CORRECTED", t3, observed_at=t1, available_at=t3, source=src, content="Corrected report: " + txt, prev_version_id=r1)
                tl += [(t2, r1, None), (t3, r2, None)]
                g.superseded_ids = ((t3, r1),)
                lid2 = f"{lid}-IF2"
                cid = f"{lid2}-R1"
                raws.append({**base, "lineage_id": lid2, "event_id": cid, "status": "AVAILABLE", "recorded_at": at(t4), "observed_at": at(t1),
                             "available_at": at(t2), "source": src, "content": txt})
                golds.append(Gold(lid2, "corrected_with_resend_copy", [(t4, None, "DUPLICATE_EVIDENCE"), (t3, None, "DUPLICATE_OF_SUPERSEDED_VERSION")],
                                  dup_group=lid, superseded_ids=((t3, cid),), copy_ids=(cid,)))
                marks.update((t4, t3))
            elif tpl == "source_unknown":
                ev("R1", "AVAILABLE", t2, observed_at=t1, available_at=t2, source=None, content=txt)
                tl.append((t2, None, "SOURCE_UNKNOWN"))
            golds.append(g)
            marks.update(t for t, _, _ in g.timeline)
        for r in raws:                                        # 원시 기록의 모든 시각 경계도 조회(1차 심사 반영)
            for k in ("recorded_at", "observed_at", "available_at"):
                if r.get(k):
                    marks.add(round((datetime.fromisoformat(r[k]) - T0).total_seconds() / 60))
        qs = sorted({m + d for m in marks for d in (-1, 0, 1)} | {-5, 600})
        out.append((case, raws, golds, qs))
    return out
