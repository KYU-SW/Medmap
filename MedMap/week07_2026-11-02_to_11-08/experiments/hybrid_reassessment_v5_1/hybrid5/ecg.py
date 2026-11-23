"""ECG 판독문 구조화(파형 분석 아님). 언급 상태는 v3 parser 로 판정.
유도는 'lead(s)' 표현이나 V·aV 유도명이 실제로 적힌 경우만 읽는다(추측 안 함). 소견만으로 진단을 만들지 않는다.
v3 HPO 연결의 'depression'→우울성향(HP:0000716) 오연결을 피하려고 v3 결과를 쓰지 않고 자체 패턴을 쓴다."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from hybrid4.graphs import CP

PS = CP.PS
FINDINGS = [
    ("ST_ELEVATION", r"\bST[- ](?:segment[- ])?elevations?\b"),
    ("ST_DEPRESSION", r"\bST[- ](?:segment[- ])?depressions?\b"),
    ("PR_DEPRESSION", r"\bPR[- ](?:segment[- ])?depressions?\b"),
    ("T_WAVE_INVERSION", r"\bT[- ]wave inversions?\b|\binverted T[- ]waves?\b"),
    ("Q_WAVES", r"\b(?:pathological\s+|new\s+)?Q[- ]waves?\b"),
    ("LBBB", r"\bleft bundle branch block\b|\bLBBB\b"),
    ("NORMAL_ECG", r"\b(?:normal|unremarkable)\s+(?:ECG|EKG|electrocardiogram)\b|\b(?:ECG|EKG|electrocardiogram)\s+(?:was\s+|is\s+)?(?:normal|unremarkable)\b"),
]
R_ECG = re.compile(r"\b(?:ECG|EKG|electrocardiogra\w*)\b", re.I)
R_DIFFUSE = re.compile(r"\b(?:diffuse|widespread|global|generali[sz]ed)\b", re.I)
R_REGION = re.compile(r"\b(inferior|anterior|lateral|septal|posterior|anteroseptal|anterolateral|inferolateral|inferoposterior)\b", re.I)
R_LEADS = re.compile(r"\b(aV[RLF]|V[1-6](?:\s*[-–]\s*V?[1-6])?|III|II|I)\b")
R_VAGUE_LEADS = re.compile(r"\b(?:some|several|multiple|few|certain)\s+leads\b", re.I)
R_MM = re.compile(r"(\d+(?:\.\d+)?)\s*mm\b", re.I)
R_RHYTHM = re.compile(r"\b(sinus rhythm|sinus tachycardia|sinus bradycardia|atrial fibrillation|atrial flutter)\b", re.I)
R_HR = re.compile(r"\b(?:heart rate|HR|ventricular rate)\D{0,12}(\d{2,3})\s*(?:bpm|beats)", re.I)
R_NEW = re.compile(r"\b(?:new|newly|new-onset)\s+$", re.I)
R_OLD = re.compile(r"\b(?:old|previous|prior|known|chronic|unchanged|stable)\b", re.I)
R_LOWCERT = re.compile(r"\b(?:possible|subtle|borderline|nonspecific|non-specific|equivocal|questionable)\b", re.I)


@dataclass
class EcgFinding:
    finding_id: str
    finding_type: str
    assertion_status: str
    lead_or_distribution: dict
    interpretation_text: str
    source_record_id: str
    observation_time: float | None
    available_time: float | None
    numeric_measurement: float | None = None
    unit: str = "UNKNOWN"
    certainty: str = "AS_STATED"
    temporal_context: str = "NOT_STATED"
    reciprocal_change_reported: bool = False
    episode_id: str = ""
    notes: list = field(default_factory=list)

    def as_row(self):
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def extract(text: str, record_id: str, observed_at, available_at, episode_id="") -> dict:
    """반환 {'findings': [...], 'rhythm': [...], 'heart_rate': [...], 'unstructured_ecg_statements': [...]}"""
    out = {"findings": [], "rhythm": [], "heart_rate": [], "unstructured_ecg_statements": []}
    n = 0
    for cl in PS.split_clauses(text):
        hits = []
        for ftype, pat in FINDINGS:
            for m in re.finditer(pat, cl.text, re.I):
                if not any(a < m.end() and m.start() < b for _, a, b in hits):
                    hits.append((ftype, m.start(), m.end()))
        hits.sort(key=lambda x: x[1])
        for i, (ftype, s, e) in enumerate(hits):
            seg = cl.text[e:hits[i + 1][1] if i + 1 < len(hits) else len(cl.text)]
            pstart = max(hits[i - 1][2] if i else 0, s - 25)                        # 앞 소견의 범위를 넘어 읽지 않음
            around = cl.text[pstart:s] + " " + seg[:60]
            a, cue = PS.classify_assertion(cl, s, e)
            leads = []
            if re.search(r"\bleads?\b", seg, re.I) or re.search(r"\b(?:aV[RLF]|V[1-6])\b", seg):
                leads = [x.replace("–", "-").replace(" ", "") for x in R_LEADS.findall(seg)]
            dist = "DIFFUSE" if R_DIFFUSE.search(around) else "REGIONAL" if (R_REGION.search(around) or leads) else "NOT_STATED"
            ld = {"leads": leads or "NOT_STATED", "territory": (R_REGION.search(around).group(1).lower() if R_REGION.search(around) else "NOT_STATED"), "distribution": dist}
            f = EcgFinding(f"ECG:{record_id}:{n}", ftype, a, ld, cl.sentence, record_id, observed_at, available_at, episode_id=episode_id)
            n += 1
            mm = R_MM.search(seg[:40]) or R_MM.search(cl.text[pstart:s])            # '2 mm ST elevation' 처럼 앞에 온 측정값
            if mm:
                f.numeric_measurement, f.unit = float(mm.group(1)), "mm"
            if R_VAGUE_LEADS.search(seg) or R_VAGUE_LEADS.search(around):
                f.notes.append("LEADS_UNSPECIFIED_TEXT(유도 추측 안 함)")
            if re.search(r"\breciprocal\b", cl.text[max(0, s - 30):e], re.I):
                f.reciprocal_change_reported = True
            if ftype == "ST_ELEVATION" and any(h[0] == "ST_DEPRESSION" and re.search(r"\breciprocal\b", cl.text[max(0, h[1] - 30):h[1]], re.I) for h in hits):
                f.reciprocal_change_reported = True
            f.temporal_context = "NEW" if R_NEW.search(cl.text[max(0, s - 20):s]) else "PRIOR_OR_UNCHANGED" if R_OLD.search(around) else "NOT_STATED"
            f.certainty = "UNCERTAIN" if a == PS.UNCERTAIN else "LOW_STATED" if R_LOWCERT.search(around) else "AS_STATED"
            out["findings"].append(f)
        for m in R_RHYTHM.finditer(cl.text):
            out["rhythm"].append({"rhythm": m.group(1).lower(), "assertion": PS.classify_assertion(cl, m.start(), m.end())[0], "source_record_id": record_id})
        for m in R_HR.finditer(cl.text):
            out["heart_rate"].append({"value": int(m.group(1)), "unit": "bpm", "source_record_id": record_id})
        if R_ECG.search(cl.text) and not hits and not R_RHYTHM.search(cl.text) and not R_HR.search(cl.text):
            out["unstructured_ecg_statements"].append({"text": cl.text, "status": "ECG_STATEMENT_NOT_STRUCTURED(지원 안 함, 추측 안 함)", "source_record_id": record_id})
    return out
