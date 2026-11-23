"""다질환 개념 체계. 분류 축은 서로 다른 속성으로 둔다(하나의 계층으로 합치지 않음).
- 임상 표현 축(presentation): STEMI / NSTEMI / UNSTABLE_ANGINA (ACS 포괄 용어의 스펙트럼, UDMI5 §10·ESC 2023 §2.1)
- 기전 축(mechanism): PRIMARY / SECONDARY / PROCEDURE_RELATED (UDMI5 §7.2)
- 심근손상 상태: ACUTE / CHRONIC (UDMI5 Box 1·2) — 질병이 아니라 상태
옛 type 1~5 는 legacy_type 으로만 보존하고 새 축에 대응시키지 않는다(UDMI5 Table 1: 1:1 아님).
근거가 확인되지 않은 부모·자식 관계는 만들지 않는다."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from hybrid4.graphs import CP  # v3 concepts (parser 포함)

PS = CP.PS

CONCEPTS = {
    "DX:Pulmonary embolism": {"family": "PE", "kind": "DISEASE", "label": "Pulmonary embolism", "stages": ["SUSPECTED_ACUTE_PE_EVALUATION", "CONFIRMED_PE", "UNDER_TREATMENT", "POST_TREATMENT_FOLLOWUP", "RECURRENCE_EVALUATION", "HISTORY"]},
    "V5:DX:ACS": {"family": "ACS", "kind": "DISEASE_SPECTRUM", "label": "Acute coronary syndrome", "presentation_values": ["STEMI", "NSTEMI", "UNSTABLE_ANGINA", "UNSPECIFIED"],
                  "source": "UDMI5 §10 'umbrella term'; ESC 2023 §2.1 'spectrum'"},
    "V5:DX:UNSTABLE_ANGINA": {"family": "ACS", "kind": "DISEASE", "label": "Unstable angina", "source": "UDMI5 §10"},
    "V5:DX:MI": {"family": "MI", "kind": "DISEASE", "label": "Myocardial infarction", "presentation_values": ["STEMI", "NSTEMI", "UNSPECIFIED"],
                 "mechanism_values": ["PRIMARY", "SECONDARY", "PROCEDURE_RELATED", "UNSPECIFIED"], "source": "UDMI5 §5, §7.1.2, §7.2"},
    "V5:STATE:ACUTE_MYOCARDIAL_INJURY": {"family": "INJURY", "kind": "STATE", "label": "Acute myocardial injury", "source": "UDMI5 Box 1"},
    "V5:STATE:CHRONIC_MYOCARDIAL_INJURY": {"family": "INJURY", "kind": "STATE", "label": "Chronic myocardial injury", "source": "UDMI5 Box 2"},
    "DX:Pericarditis": {"family": "PERICARDIAL", "kind": "DISEASE", "label": "Pericarditis", "course_values": ["ACUTE", "SUBACUTE", "CHRONIC", "INCESSANT", "RECURRENT", "UNSPECIFIED"],
                        "source": "ESC 2025 §4.4, Table 3"},
}
# 확인된 포함 관계만(그 외 부모·자식 없음). MI ⊄ ACS: 속발성·시술 MI 는 ACS 가 아님(UDMI5 §7.2)
SPECTRUM = {("V5:DX:ACS", "UNSTABLE_ANGINA"): "V5:DX:UNSTABLE_ANGINA"}

DIAGNOSIS_STATUS = ("PHYSICIAN_CONFIRMED", "PHYSICIAN_SUSPECTED", "RECORD_HISTORY", "AI_CANDIDATE_UNCONFIRMED", "UNDER_EVALUATION")

# 문장 언급 → (개념, 축 속성). 긴 표현 우선. 'ACS' 약어는 다른 뜻이 있어 연결하지 않음
TERMS = [
    (r"\bnon[- ]ST[- ](?:segment[- ])?elevation myocardial infarction\b|\bNSTEMI\b", "V5:DX:MI", {"presentation": "NSTEMI"}),
    (r"\bST[- ](?:segment[- ])?elevation myocardial infarction\b|\bSTEMI\b", "V5:DX:MI", {"presentation": "STEMI"}),
    (r"\bnon[- ]ST[- ](?:segment[- ])?elevation acute coronary syndromes?\b|\bNSTE-ACS\b", "V5:DX:ACS", {"presentation": "NSTE_ACS_UNSPLIT"}),
    (r"\bunstable angina\b", "V5:DX:UNSTABLE_ANGINA", {"presentation": "UNSTABLE_ANGINA"}),
    (r"\bacute coronary syndromes?\b", "V5:DX:ACS", {"presentation": "UNSPECIFIED"}),
    (r"\bprimary myocardial infarction\b", "V5:DX:MI", {"mechanism": "PRIMARY"}),
    (r"\bsecondary myocardial infarction\b", "V5:DX:MI", {"mechanism": "SECONDARY"}),
    (r"\bprocedure[- ]related myocardial infarction\b", "V5:DX:MI", {"mechanism": "PROCEDURE_RELATED"}),
    (r"\btype\s*([1-5][abc]?)\s+(?:myocardial infarction|MI)\b", "V5:DX:MI", {"legacy_type": "$1"}),
    (r"\b(?:acute\s+)?myocardial infarction\b", "V5:DX:MI", {}),
    (r"\bacute myocardial injury\b", "V5:STATE:ACUTE_MYOCARDIAL_INJURY", {}),
    (r"\bchronic myocardial injury\b", "V5:STATE:CHRONIC_MYOCARDIAL_INJURY", {}),
    (r"\brecurrent pericarditis\b", "DX:Pericarditis", {"course": "RECURRENT"}),
    (r"\bacute pericarditis\b", "DX:Pericarditis", {"course": "ACUTE"}),
    (r"\bpericarditis\b", "DX:Pericarditis", {}),
]


@dataclass
class MultiHypothesis:
    hyp_id: str
    concept_id: str
    episode_id: str
    at: float
    diagnosis_status: str = "UNDER_EVALUATION"
    physician_confirmation_status: str = "UNCONFIRMED"
    presentation_axis: str = "UNSPECIFIED"
    mechanism_axis: str = "UNSPECIFIED"
    course_axis: str = "UNSPECIFIED"
    source_ids: list = field(default_factory=list)

    def __post_init__(self):
        if self.concept_id not in CONCEPTS:
            raise ValueError(f"지원하지 않는 개념 {self.concept_id}(다른 개념에 붙이지 않음)")
        if self.diagnosis_status not in DIAGNOSIS_STATUS:
            raise ValueError(self.diagnosis_status)
        c = CONCEPTS[self.concept_id]
        for ax, key in (("presentation_axis", "presentation_values"), ("mechanism_axis", "mechanism_values"), ("course_axis", "course_values")):
            v = getattr(self, ax)
            if v != "UNSPECIFIED" and v not in c.get(key, []):
                raise ValueError(f"{self.concept_id} 에 {ax}={v} 없음")


def find_disease_mentions(text: str) -> list:
    """문장의 다질환 언급(미확인 후보). 언급 상태는 v3 parser 로 판정. 겹치는 짧은 표현은 건너뜀."""
    out = []
    for cl in PS.split_clauses(text):
        used = []
        for pat, cid, attrs in TERMS:
            for m in re.finditer(pat, cl.text, re.I):
                if any(a < m.end() and m.start() < b for a, b in used):
                    continue
                if re.fullmatch(r"(?i)stemi|nstemi", m.group(0)) and m.group(0) != m.group(0).upper():
                    continue                                                   # 약어는 대문자 표기만
                used.append((m.start(), m.end()))
                a, cue = PS.classify_assertion(cl, m.start(), m.end())
                at = {k: (m.group(1).upper() if v == "$1" else v) for k, v in attrs.items()}
                out.append({"surface": m.group(0), "concept_id": cid, "attributes": at, "assertion": a, "cue": cue, "sentence": cl.sentence, "clause": cl.text})
    return out
