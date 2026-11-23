"""가설별 증거 연결. 네 상태를 하나로 합치지 않는다.
  1 information_present          : 해당 에피소드에 as_of 기준 공개된 정보
  2 linked_to_evaluation_item    : 가설의 등록 기준(또는 레거시 v4 관계)이 그 항목을 입력으로 읽음
  3 criterion_evaluable          : 그 기준이 TRUE/FALSE 로 평가됨
  4 verified_directional_relation: 검증된 방향 관계 — v5-2A 에서는 항상 없음(PE 는 LEGACY_V4_UNVALIDATED 로 별도)
관련 정보 ≠ SUPPORT. 기준 충족 ≠ 확진. 한 질환의 SUPPORT ≠ 다른 질환의 WEAKEN."""
from __future__ import annotations

from hybrid5 import observations as OB

NO_DIR = "NO_VERIFIED_DIRECTIONAL_RELATION"
LEGACY = "LEGACY_V4_UNVALIDATED"
UNLINKED_CLASSES = {
    "UNMAPPED_FINDING": "A. 개념 연결 실패(현재 지식 구조에서 개념을 정하지 못함). 이상 소견·진단 모순이라는 뜻이 아님",
    "LINKED_CONCEPT_NO_VERIFIED_RULE": "B. 개념은 추출됐지만 등록 가설에 이 개념을 쓰는 검증된 판단 규칙이 없음",
    "UNSUPPORTED_EXTRACTION": "C. 추출기가 해당 표현을 지원하지 않음",
    "UNRESOLVED_EPISODE": "D. 진단 에피소드 연결 불명확",
    "RESULT_NOT_YET_AVAILABLE": "E. as_of 시점에 아직 공개되지 않은 결과(ID 만 표시, 내용 미사용)",
    "TEST_NAME_MENTION_ONLY": "F. 검사명만 언급(결과 없음) — 이상 소견 아님",
    "DIAGNOSIS_MENTION_NOT_FINDING": "진단명 언급(소견 아님). 가설로 자동 등록하지 않음",
    "EXCLUDED_KNOWN_MISLINK": "알려진 오연결(ECG 'depression'→우울 HPO) — 원본·추출 이력은 보존, 비교에서 제외",
    "ABBREVIATION_DEFINITION_ONLY": "약어 정의 목록 안 언급",
}


def catalog(inp: dict) -> dict:
    """에피소드 입력 → 항목 ID 별 행(그래프·평면표 공통 형식)."""
    out = {}
    for e in inp["evidence"]:
        out[e["evidence_id"]] = {"item_id": e["evidence_id"], "item_kind": "EVIDENCE", "record_key": e["source_record_id"], "source_record_id": e["source_record_id"],
                                 "episode_id": e["diagnosis_episode_id"], "observation_time": e["observation_time"], "available_time": e["available_time"],
                                 "finding_key": ["EVIDENCE", e.get("base_concept") or e.get("concept_id") or "", e["assertion_status"], (e.get("finding_state") or {}).get("finding") or ""],
                                 "label": e["surface"], "concept": e.get("base_concept") or "", "evidence_type": e["evidence_type"], "extraction_status": e["extraction_status"],
                                 "role": (e.get("rec") or {}).get("role", ""), "v5_override": e.get("v5_override"), "assertion": e["assertion_status"]}
    for f in inp["ecg"]:
        out[f["finding_id"]] = {"item_id": f["finding_id"], "item_kind": "ECG_FINDING", "record_key": f["source_record_id"], "source_record_id": f["source_record_id"],
                                "episode_id": f["episode_id"], "observation_time": f["observation_time"], "available_time": f["available_time"],
                                "finding_key": ["ECG", f["finding_type"], f["assertion_status"], f["lead_or_distribution"].get("distribution", "")],
                                "label": f["finding_type"], "concept": f["finding_type"], "evidence_type": "ECG_FINDING", "extraction_status": "EXTRACTED",
                                "role": "", "v5_override": None, "assertion": f["assertion_status"]}
    for o in inp["obs"]:
        key = o.obs_id if o.source_type == "STRUCTURED_LAB" else o.source_record_id
        out[o.obs_id] = {"item_id": o.obs_id, "item_kind": "LAB_OBSERVATION", "record_key": key, "source_record_id": key, "episode_id": o.episode_id,
                         "observation_time": o.observation_time, "available_time": o.available_time,
                         "finding_key": ["OBS", o.analyte, o.comparator, o.numeric_value, o.unit], "label": o.raw_value, "concept": o.analyte,
                         "evidence_type": "LAB_OBSERVATION", "extraction_status": o.extraction_status, "role": "", "v5_override": None, "assertion": "MEASURED"}
    return out


def link(spec, cat: dict, rows: list, legacy_items: list) -> dict:
    links = {}
    for r in rows:
        for iid in r["input_item_ids"]:
            l_ = links.setdefault(iid, {"item_id": iid, "criteria": [], "evaluable_criteria": [], "link_basis": [], "legacy_relations": []})
            l_["criteria"].append(r["criterion_id"])
            if "CRITERION_INPUT" not in l_["link_basis"]:
                l_["link_basis"].append("CRITERION_INPUT")
            if r["evaluation_result"] in ("TRUE", "FALSE"):
                l_["evaluable_criteria"].append(r["criterion_id"])
    for li in legacy_items:
        l_ = links.setdefault(li["evidence_id"], {"item_id": li["evidence_id"], "criteria": [], "evaluable_criteria": [], "link_basis": [], "legacy_relations": []})
        if LEGACY not in l_["link_basis"]:
            l_["link_basis"].append(LEGACY)
        l_["legacy_relations"].append({"relation_id": li["relation_id"], "legacy_direction": li["direction"], "hold_reason": li["hold_reason"], "label": LEGACY})
    out = {}
    for iid in sorted(links):
        l_ = links[iid]
        out[iid] = {**l_, "criteria": sorted(set(l_["criteria"])), "evaluable_criteria": sorted(set(l_["evaluable_criteria"])),
                    "information_present": iid in cat or ":" in iid and iid.rsplit(":", 1)[1] in ("CMR", "text"),
                    "linked_to_evaluation_item": True, "criterion_evaluable": bool(l_["evaluable_criteria"]),
                    "verified_directional_relation": LEGACY if l_["legacy_relations"] else NO_DIR}
    return out


def classify_unlinked(it: dict) -> str:
    if it.get("v5_override"):
        return "EXCLUDED_KNOWN_MISLINK"
    if it["item_kind"] == "EVIDENCE":
        if it["role"] == "DEFINITION_ONLY":
            return "ABBREVIATION_DEFINITION_ONLY"
        if it["extraction_status"] == "AMBIGUOUS":
            return "UNMAPPED_FINDING"
        if it["extraction_status"] == "UNSUPPORTED":
            return "UNSUPPORTED_EXTRACTION"
        if it["evidence_type"] == "TEST" and not it["finding_key"][3]:
            return "TEST_NAME_MENTION_ONLY"
        if it["evidence_type"] == "DISEASE":
            return "DIAGNOSIS_MENTION_NOT_FINDING"
    return "LINKED_CONCEPT_NO_VERIFIED_RULE"


def record_level_findings(inp: dict) -> list:
    """기록 단위: 결과 없는 트로포닌 검사명 언급, 추출 미지원 ECG 문장."""
    out = []
    for r in sorted(inp["records"], key=lambda r: r["record_id"]):
        if OB.R_TROP.search(r["text"]) and not any(o.source_record_id == r["record_id"] for o in inp["obs"]):
            out.append({"item_id": f"{r['record_id']}:TROPONIN_MENTION", "class": "TEST_NAME_MENTION_ONLY", "source_record_id": r["record_id"],
                        "meaning": UNLINKED_CLASSES["TEST_NAME_MENTION_ONLY"]})
        for u in r.get("unstructured_ecg", []):
            out.append({"item_id": f"{r['record_id']}:ECG_STATEMENT", "class": "UNSUPPORTED_EXTRACTION", "source_record_id": r["record_id"], "text": u,
                        "meaning": UNLINKED_CLASSES["UNSUPPORTED_EXTRACTION"]})
    return out
