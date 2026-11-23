"""가설별 조건 평가. 기준 사실은 v5-1 criterion_facts_* 를, 평가는 v5-1 eval5/eval_kofn 을 그대로 호출한다.
기준 구조는 v5-1 pericarditis_classification(crit5)·injury_classification(acute) 과 같다(일치 여부를 consistency_with_v51 로 검사).
- UNKNOWN 을 FALSE 로, CONFLICT 를 임의 해결로 바꾸지 않는다.
- 미확정 조건의 이유를 MISSING_INFORMATION / PENDING_RESULT / CONFLICTING_INFORMATION / UNRESOLVED_EPISODE / UNSUPPORTED_EXTRACTION / NO_VERIFIED_RULE / NOT_APPLICABLE 로 나눈다.
- 부족 정보를 검사 처방·주문으로 바꾸지 않는다. 중요도·우선순위 점수 없음."""
from __future__ import annotations

from types import SimpleNamespace

from hybrid.temporal import test_status          # v1 검사 상태(ORDERED/PENDING/RESULT_AVAILABLE/...)
from hybrid5 import classification as CL
from hybrid5 import logic as L
from hybrid5 import observations as OB

T, F, U, C = L.T, L.F, L.U, L.C
GAP = ("MISSING_INFORMATION", "PENDING_RESULT", "CONFLICTING_INFORMATION", "UNRESOLVED_EPISODE", "UNSUPPORTED_EXTRACTION", "NO_VERIFIED_RULE", "NOT_APPLICABLE")
NO_RULE_RESULT = "NOT_EVALUATED_NO_VERIFIED_RULE"


def _A(k):
    return L.Atom(k, (True,))


PERI_ITEMS = (("PERI_RUB", _A("PERI_RUB")), ("PERI_ECG", L.Or((_A("ECG_PR_DEPRESSION"), _A("ECG_WIDESPREAD_STE")))), ("PERI_CRP", _A("PERI_CRP")),
              ("PERI_EFFUSION", _A("PERI_EFFUSION_NEW_OR_WORSENING")), ("PERI_CMR", _A("PERI_CMR_OEDEMA_LGE")))      # = v5-1 crit5
CRITERIA = {
    "PERICARDITIS_RESEARCH": {
        "source": "ESC 2025 Table 4(v5-1 pericarditis_classification 과 같은 구조) — RESEARCH_ONLY_NOT_VALIDATED",
        "atomic": [("CLINICAL_PRESENTATION", _A("CLINICAL_PRESENTATION"), "PREREQUISITE")] + [(c, n, "ADDITIONAL_CRITERION") for c, n in PERI_ITEMS],
        "composite": [("PERI_ADDITIONAL_AT_LEAST_2", L.KofN("PERI_ADDITIONAL_AT_LEAST_2", "AT_LEAST_K", 2, PERI_ITEMS))],
        "prerequisite": "CLINICAL_PRESENTATION"},
    "MYOCARDIAL_INJURY_RESEARCH": {
        "source": "UDMI5 Box 1(v5-1 injury_classification 과 같은 구조) — RESEARCH_ONLY_NOT_VALIDATED",
        "atomic": [("INJ_ABOVE_SEX_SPECIFIC_URL", _A("INJ_ABOVE_SEX_SPECIFIC_URL"), "COMPONENT"), ("INJ_RISE_OR_FALL_REPORTED", _A("INJ_RISE_OR_FALL_REPORTED"), "COMPONENT")],
        "composite": [("ACUTE_INJURY_RESEARCH", L.And((_A("INJ_ABOVE_SEX_SPECIFIC_URL"), _A("INJ_RISE_OR_FALL_REPORTED"))))],
        "prerequisite": None},
}
FAMILY_SETS = {"PERICARDIAL": ("PERICARDITIS_RESEARCH",), "ACS": ("MYOCARDIAL_INJURY_RESEARCH",), "MI": ("MYOCARDIAL_INJURY_RESEARCH",),
               "INJURY": ("MYOCARDIAL_INJURY_RESEARCH",), "PE": ()}
NO_RULE = {
    "ACS": [("ACS_DIAGNOSTIC_CRITERIA", "ACS 진단 기준·방향 관계: v5-0B 후보만 있고 엔진 규칙 없음(전문의 검토 전, CRQ-06·07·09)")],
    "MI": [("MI_ISCHEMIA_EVIDENCE", "MI = 급성 손상 + 허혈 근거(UDMI5 §5). 허혈 근거 판단 규칙 미구현·미검증 — 손상 기준 충족은 MI 판정이 아님")],
    "PE": [("PE_V5_CRITERIA", "PE 는 v5 검증 기준 없음. v4 레거시 판단은 LEGACY_V4_UNVALIDATED 로 별도 표시")],
    "PERICARDIAL": [], "INJURY": []}
NEEDED = {
    "CLINICAL_PRESENTATION": "흉통 기록(HPO 흉통·흉막성 흉통)", "PERI_RUB": "심낭 마찰음 청진 결과(있음/없음 명시)",
    "ECG_PR_DEPRESSION": "ECG PR 하강 판독(있음/없음/정상 ECG)", "ECG_WIDESPREAD_STE": "ECG ST 상승 분포(광범위/국소/없음)",
    "PERI_CRP": "CRP 결과(질적 판정 또는 기준값 포함 수치)", "PERI_EFFUSION_NEW_OR_WORSENING": "심낭삼출 유무와 새로 생김·악화 여부",
    "PERI_CMR_OEDEMA_LGE": "CMR 심낭 부종·LGE 판독", "INJ_ABOVE_SEX_SPECIFIC_URL": "트로포닌 수치 + 환자 성별에 맞는 99백분위 기준값",
    "INJ_RISE_OR_FALL_REPORTED": "트로포닌 상승·하강이 기록에 명시됐는지(수치 변화만으로 판정하지 않음)"}
# 검사 종류 → 그 결과가 들어가는 기준 원자(구조 연결표: classification.py 가 어떤 입력을 읽는지와 같음. 의학 관계 아님)
TEST_FEEDS = {"TROPONIN": ("INJ_ABOVE_SEX_SPECIFIC_URL", "INJ_RISE_OR_FALL_REPORTED"), "CRP": ("PERI_CRP",), "ECG": ("ECG_PR_DEPRESSION", "ECG_WIDESPREAD_STE"),
              "ECHO": ("PERI_EFFUSION_NEW_OR_WORSENING",), "CMR": ("PERI_CMR_OEDEMA_LGE",), "CTPA": ("LEGACY_V4:CTPA_RESULT",)}
WAITING = ("ORDERED", "PENDING")


def atoms_of(node) -> list:
    if isinstance(node, L.Atom):
        return [node.key]
    if isinstance(node, L.Not):
        return atoms_of(node.item)
    if isinstance(node, L.KofN):
        return [a for _, n in node.items for a in atoms_of(n)]
    return [a for i in node.items for a in atoms_of(i)]


def criterion_facts(set_name: str, inp: dict, sex: str, as_of: float) -> dict:
    """v5-1 evaluate_common 과 같은 입력 정렬로 v5-1 기준 사실 함수를 호출."""
    ev = sorted(inp["evidence"], key=lambda x: x["evidence_id"])
    ecg = sorted(inp["ecg"], key=lambda x: x["finding_id"])
    obs = sorted(inp["obs"], key=lambda x: x.obs_id)
    if set_name == "PERICARDITIS_RESEARCH":
        return CL.criterion_facts_pericarditis(ev, ecg, [o.as_row() for o in obs], inp["records"])
    return CL.criterion_facts_injury(OB.build_series(obs, as_of, sex), inp["records"])


def atom_inputs(set_name: str, facts: dict, inp: dict) -> dict:
    """원자 기준별 입력 항목 ID: 사실의 출처 + 그 기준 함수가 읽은 측정값(존재 기준은 TRUE 출처만 남기므로 측정값 전체를 더함)."""
    out = {k: set(f.sources) for k, f in facts.items() if not k.startswith("_")}
    if set_name == "PERICARDITIS_RESEARCH":
        out["PERI_CRP"] |= {o.obs_id for o in inp["obs"] if o.analyte == "CRP"}
    else:
        out["INJ_ABOVE_SEX_SPECIFIC_URL"] |= {o.obs_id for o in inp["obs"] if o.analyte.startswith("TROPONIN")}
    return {k: sorted(v) for k, v in out.items()}


def _reason(v, r) -> str:
    return {T: "기준 사실 TRUE(출처 기록 있음)", F: "평가 기록에 음성·해당 없음이 명시됨", U: "기준 사실 없음 — 기록 없음을 FALSE 로 바꾸지 않음",
            C: "같은 기준에 서로 다른 값이 기록됨 — 임의로 해결하지 않음"}.get(v, str(v))


def evaluate(spec, inp: dict, sex: str, as_of: float, item_meta: dict) -> tuple:
    """반환 (rows, facts_by_set). item_meta: 항목 ID → {source_record_id, available_time}."""
    rows, facts_by = [], {}
    for set_name in FAMILY_SETS[spec.family]:
        cfg = CRITERIA[set_name]
        facts = criterion_facts(set_name, inp, sex, as_of)
        ins = atom_inputs(set_name, facts, inp)
        facts_by[set_name] = facts
        vals = {}
        for cid, node, role in cfg["atomic"] + [(c, n, "COMPOSITE") for c, n in cfg["composite"]]:
            r = L.eval5(node, facts)
            atoms = sorted(set(atoms_of(node)))
            inputs = sorted({i for a in atoms for i in ins.get(a, [])})
            srcs = sorted(set(L._sources(r)))
            vals[cid] = r["value"]
            row = {"condition_id": f"{spec.hypothesis_id}:{cid}", "hypothesis_id": spec.hypothesis_id, "criterion_id": cid, "criterion_set": set_name,
                   "criterion_role": role, "criterion_source": cfg["source"], "condition_tree": node.to_dict(), "atoms": atoms, "evaluation_result": r["value"],
                   "source_evidence_ids": srcs, "input_item_ids": inputs,
                   "source_record_ids": sorted({_rec(i, item_meta) for i in inputs}), "episode_id": spec.diagnosis_episode_id,
                   "available_time": max([item_meta[i]["available_time"] for i in inputs if i in item_meta and isinstance(item_meta[i]["available_time"], (int, float))], default=None),
                   "missing_requirements": r.get("missing", []), "conflicting_sources": sorted({str(x) for x in r.get("conflicts", [])}),
                   "evaluation_reason": _reason(r["value"], r), "gap": None}
            if role == "COMPOSITE" and isinstance(node, L.KofN):
                row["kofn"] = {k: r[k] for k in ("op", "k", "n", "confirmed_true_count", "confirmed_false_count", "unknown_count", "conflict_count",
                                                 "minimum_true", "maximum_possible_true", "undetermined_reason", "criteria")}
            rows.append(row)
        pre = cfg["prerequisite"]
        if pre:
            for row in rows:
                if row["criterion_set"] == set_name and row["criterion_role"] == "COMPOSITE":
                    row["gated_by_prerequisite"] = {"criterion_id": pre, "value": vals[pre],
                                                    "effect": "연구용 등급 생성" if vals[pre] == T else "연구용 등급 NOT_GENERATED(v5-1 과 같음)"}
    for cid, why in NO_RULE[spec.family]:
        rows.append({"condition_id": f"{spec.hypothesis_id}:{cid}", "hypothesis_id": spec.hypothesis_id, "criterion_id": cid, "criterion_set": "NONE",
                     "criterion_role": "NO_VERIFIED_RULE", "criterion_source": "없음", "condition_tree": None, "atoms": [], "evaluation_result": NO_RULE_RESULT,
                     "source_evidence_ids": [], "input_item_ids": [], "source_record_ids": [], "episode_id": spec.diagnosis_episode_id, "available_time": None,
                     "missing_requirements": [], "conflicting_sources": [], "evaluation_reason": why,
                     "gap": {"category": "NO_VERIFIED_RULE", "reason": why, "needed_data": "자료가 아니라 검증된 의학 판단 규칙이 필요(전문의 검토)"}})
    return rows, facts_by


def _rec(item_id: str, item_meta: dict) -> str:
    if item_id in item_meta:
        return item_meta[item_id]["source_record_id"]
    return item_id.rsplit(":", 1)[0]                                     # 'n1:CMR', 'n2:text' 형 문장 패턴 출처


def test_states(tests: list, as_of: float) -> dict:
    """에피소드 검사 사건 → {test_id: (test_kind, 상태)} (v1 test_status 재사용)."""
    ev = [SimpleNamespace(test_id=t["test_id"], event=t["event"], at=t["at"]) for t in tests]
    kinds = {t["test_id"]: t["test_kind"] for t in tests}
    return {tid: (kinds[tid], test_status(ev, tid, as_of).value) for tid in sorted(kinds)}


def attach_gaps(rows: list, facts_by: dict, spec, inp: dict, unres: dict, sex: str, as_of: float) -> None:
    """UNKNOWN·CONFLICT 원자 기준에 부족 정보 분류를 붙인다. 복합 기준은 하위 기준의 분류를 참조만 한다."""
    tstat = test_states(inp.get("tests", []), as_of)
    merged = {k: inp[k] + unres.get(k, []) for k in ("evidence", "ecg", "obs", "records")}
    cf = {s: criterion_facts(s, merged, sex, as_of) for s in facts_by}
    ep_recs = sorted(r["record_id"] for r in inp["records"])
    trop_mention = sorted(r["record_id"] for r in inp["records"] if OB.R_TROP.search(r["text"]) and not any(o.source_record_id == r["record_id"] for o in inp["obs"]))
    for row in rows:
        if row["criterion_role"] in ("NO_VERIFIED_RULE",) or row["evaluation_result"] not in (U, C):
            continue
        if row["criterion_role"] == "COMPOSITE":
            row["gap"] = {"category": "SEE_COMPONENT_CRITERIA", "reason": "하위 기준의 미확정 때문", "component_gaps": [
                r["criterion_id"] for r in rows if r["criterion_set"] == row["criterion_set"] and r["criterion_role"] != "COMPOSITE" and r["evaluation_result"] in (U, C)]}
            continue
        facts, atoms = facts_by[row["criterion_set"]], row["atoms"]
        feeding = {tid: st for tid, (kind, st) in tstat.items() if set(TEST_FEEDS.get(kind, ())) & set(atoms)}
        unres_new = [a for a in atoms if facts[a].status == "NOT_FOUND" and cf[row["criterion_set"]][a].status in ("FOUND", "CONFLICT")]
        unres_items = sorted({s for a in unres_new for s in cf[row["criterion_set"]][a].sources} - set(row["input_item_ids"]))
        unsupported = [u for r in inp["records"] for u in r.get("unstructured_ecg", [])] if any(a.startswith("ECG_") for a in atoms) else []
        cats = []
        if row["evaluation_result"] == C:
            cats.append("CONFLICTING_INFORMATION")
        if any(st in WAITING for st in feeding.values()):
            cats.append("PENDING_RESULT")
        if unres_new:
            cats.append("UNRESOLVED_EPISODE")
        if unsupported:
            cats.append("UNSUPPORTED_EXTRACTION")
        if not cats:
            cats.append("MISSING_INFORMATION")
        notes = []
        if "INJ_ABOVE_SEX_SPECIFIC_URL" in atoms and row["input_item_ids"]:
            notes += facts.get("_notes", []) or ["트로포닌 값은 있으나 성별 99백분위 기준값 적용을 확인하지 못함"]
        if trop_mention and any(a.startswith("INJ_") for a in atoms):
            notes.append(f"검사명만 언급된 기록(결과 없음): {trop_mention}")
        row["gap"] = {"category": cats[0], "also": cats[1:], "reason": _gap_reason(cats[0]), "needed_data": "; ".join(NEEDED.get(a, a) for a in atoms),
                      "existing_records": ep_recs, "test_status": feeding, "related_sources": row["input_item_ids"] + unres_items,
                      "unresolved_episode_items": unres_items, "unsupported_statements": unsupported, "notes": notes,
                      "action": "NONE(검사 처방·주문으로 바꾸지 않음)"}


def _gap_reason(cat: str) -> str:
    return {"CONFLICTING_INFORMATION": "서로 모순되는 원본 기록", "PENDING_RESULT": "검사가 주문·시행됐고 결과 대기(검사 안 함이 아님)",
            "UNRESOLVED_EPISODE": "관련 기록이 있으나 진단 에피소드 연결이 불명확해 사용하지 않음", "UNSUPPORTED_EXTRACTION": "기록 표현을 현재 추출기가 구조화하지 못함",
            "MISSING_INFORMATION": "필요한 정보가 기록에 없음(음성으로 간주하지 않음)"}[cat]


def legacy_gaps(spec, inp: dict, as_of: float) -> list:
    """PE: v5 기준은 없고, 레거시 v4 판단 입력(CTPA) 결과 대기만 표시."""
    out = []
    for tid, (kind, st) in test_states(inp.get("tests", []), as_of).items():
        if kind == "CTPA" and st in WAITING:
            out.append({"condition_id": f"{spec.hypothesis_id}:LEGACY_V4:CTPA_RESULT", "criterion_id": "LEGACY_V4:CTPA_RESULT", "category": "PENDING_RESULT",
                        "reason": _gap_reason("PENDING_RESULT") + " — 레거시 v4 PE 판단 입력(LEGACY_V4_UNVALIDATED)", "needed_data": "CTPA 판독 결과",
                        "test_status": {tid: st}, "action": "NONE(검사 처방·주문으로 바꾸지 않음)"})
    return out


def consistency_with_v51(rows: list, classifications: list) -> list:
    """v5-1 연구용 분류 결과와 이 모듈의 기준 상태가 같은지(다르면 목록 반환)."""
    bad = []
    by = {r["criterion_id"]: r["evaluation_result"] for r in rows}
    for c in classifications:
        if c["target_concept"] == "DX:Pericarditis" and c.get("criteria_states"):
            for k, v in c["criteria_states"].items():
                if by.get(k) != v:
                    bad.append(("PERI", k, v, by.get(k)))
            if (c["guideline_classification"] == "DEFINITE") != (by.get("PERI_ADDITIONAL_AT_LEAST_2") == T):
                bad.append(("PERI", "AT_LEAST_2", c["guideline_classification"], by.get("PERI_ADDITIONAL_AT_LEAST_2")))
        if c["target_concept"] == "V5:STATE:ACUTE_MYOCARDIAL_INJURY":
            m = {T: "MEETS_CRITERIA_RESEARCH", F: "CRITERIA_NOT_MET", U: "UNDETERMINED_UNKNOWN", C: "UNDETERMINED_CONFLICT"}
            if m[by["ACUTE_INJURY_RESEARCH"]] != c["acute_injury"]:
                bad.append(("INJ", "acute", c["acute_injury"], by["ACUTE_INJURY_RESEARCH"]))
    return bad
