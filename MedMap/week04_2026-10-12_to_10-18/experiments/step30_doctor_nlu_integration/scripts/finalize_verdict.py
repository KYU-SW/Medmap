"""§13·§18 최종 판정 — 사전 고정 규칙(data/prereg_gates.json verdict_rule)을 산출 파일에 그대로 적용. 출력: outputs/integration_verdict.json · outputs/manifest.json"""
from __future__ import annotations

import time

import doctor_integration_adapter as AD
import s30_common as S
import validate_schema as VS


def gate_status(core, prot, lic, tests, wf):
    h = core["gate_hits"]
    has = lambda *ks: any(k in h for k in ks)  # noqa: E731
    g = {
        "G1": not has("G1"), "G2": not has("G2"),
        "G3": not has("G3", "AUTO_APPLY"), "G4": not has("G4", "AUTO_APPLY"), "G5": not has("G5", "AUTO_APPLY"),
        "G6": not has("G6", "AUTO_APPLY"), "G7": not has("G7", "AUTO_APPLY"),
        "G8": core["mapping_summary"]["G8"] == "PASS" and not has("G8"),
        "G9": not has("G9", "CONFIRM_POLICY_MISMATCH", "STAGE_B_PRODUCT_CONTRACT"),
        "G10": not has("G10") and wf["violations_total"] == 0,
        "G11": prot["G11"] == "PASS",
        "G12": lic["G12"] == "PASS",
        "G13": not has("G13", "SCHEMA_MISSING", "SCHEMA_VERSION", "ITEM_ID_DUPLICATE", "SECTION_ITEM_MISMATCH", "CATEGORY_INVALID", "STAGE_A_NON_A"),
        "G14": not has("G14"),
        "G15": core["freeze_verify"].get("verify") == "PASS",
    }
    out = {k: "PASS" if v else "FAIL" for k, v in g.items()}
    out["UNIT_TESTS"] = "PASS" if tests["PASS"] else "FAIL"
    return out


def main():
    core = S.load_json(S.OUT / "evaluation_core.json")
    prot = S.load_json(S.OUT / "protected_check.json")
    lic = S.load_json(S.OUT / "license_scan.json")
    tests = S.load_json(S.OUT / "unit_tests.json")
    wf = S.load_json(S.OUT / "workflow_safety.json")
    av = S.load_json(S.OUT / "adapter_validation.json")
    lat = S.load_json(S.OUT / "latency.json")
    rep = S.load_json(S.LOGS / "repro_check.json") if (S.LOGS / "repro_check.json").exists() else {"status": "NOT_RUN"}
    gates = gate_status(core, prot, lic, tests, wf)
    m = core["metrics_integration_new"]
    mr = core["metrics_regression_exposed"]
    fail = [k for k, v in gates.items() if v != "PASS"]
    if "G11" in fail or "G12" in fail:
        result = "BLOCKED"
    elif fail:
        result = "REGRESSION"
    else:
        ntr = m["normal_transfer_rate"]["value"] or 0
        if (m["stage_a_marking_errors"] == 0 and ntr >= 0.85 and (m["missing_rate"]["value"] or 0) <= 0.10
                and (m["wrong_display_rate"]["value"] or 0) <= 0.10):
            result = "INTEGRATION_FEASIBLE"
        elif ntr < 0.50:
            result = "NO_GAIN"
        else:
            result = "PARTIAL_FEASIBILITY"
    readiness = {"INTEGRATION_FEASIBLE": "GO_FOR_RESEARCH", "PARTIAL_FEASIBILITY": "CONDITIONAL_GO"}.get(result, "NO_GO")
    h = core["gate_hits"]
    cnt = lambda k: len(h.get(k, []))  # noqa: E731
    cpu = lat["condition_A_low_load"]["pilot274"]["full_pipeline"]
    v = {
        **S.RESEARCH_BANNER,
        "STEP30_RESULT": result,
        "NLU_SCHEMA_VALIDITY": f"{'PASS' if av['schema_violations_total'] == 0 else 'FAIL'}(위반 {av['schema_violations_total']} · 사례 {av['cases']} · NLU mention {av['nlu_mentions']} · 필수 {len(AD.REQUIRED_FIELDS)}필드 중 NLU 직접 {len(VS.NLU_NATIVE)}, 어댑터 생성 {len(VS.ADAPTER_DERIVED)})",
        "DOCTOR_ADAPTER_VALIDITY": f"{'PASS' if gates['G13'] == 'PASS' and gates['G1'] == 'PASS' else 'FAIL'}(packet item {av['packet_items']}, 범주 {av['items_by_category']})",
        "RAW_PRESERVATION": f"{gates['G1']}(G1 위반 {cnt('G1')}) · offset {gates['G2']}(G2 위반 {cnt('G2')})",
        "MODEL_INPUT_ISOLATION": f"{'PASS' if all(gates[g] == 'PASS' for g in ('G3', 'G4', 'G5', 'G6', 'G7', 'G9')) else 'FAIL'}(자동 모델 입력 0 — applied=false 전 사례 · STAGE_A {av['stage_a_items']}건은 표시만)",
        "SILVER_ISOLATION": f"{gates['G3']}(위반 {cnt('G3')})",
        "NEGATED_INPUT_VIOLATIONS": cnt("G5"),
        "HISTORICAL_INPUT_VIOLATIONS": cnt("G6"),
        "OTHER_PERSON_INPUT_VIOLATIONS": cnt("G4"),
        "UNKNOWN_INPUT_VIOLATIONS": cnt("G7"),
        "EVIDENCE_MAPPING_CONFLICTS": len(core["mapping_summary"]["G8_conflicts"]),
        "BLIND_WORKFLOW_VIOLATIONS": wf["violations_total"],
        "MULTI_SPAN_PRESERVATION": f"복수 기대 사례 {av['multi_span']['multi_expected_cases']} 중 기대 구문이 서로 다른 item 에 대응 {av['multi_span']['multi_expected_all_matched_distinct']}",
        "END_TO_END_TESTS": f"사례 {av['cases']}(노출 회귀 {mr['cases']} + 새 통합 {m['cases']}) 실행 · 단위 테스트 {tests['tests_run']}개 {gates['UNIT_TESTS']}",
        "CPU_P95": f"{cpu['p95_ms']} ms(조건 A pilot274 전체 경로 NLU+검색+어댑터+직렬화, p50 {cpu['p50_ms']} ms)",
        "STEP31_READINESS": readiness,
        "PRODUCTION_READY": "NO",
        "HUMAN_VERIFIED_GOLD": 0,
        "gates": gates,
        "gate_hit_counts": {k: len(x) for k, x in h.items()},
        "performance_integration_new": {k: m[k] for k in ("normal_transfer_rate", "unnecessary_confirmation_rate", "missing_rate", "wrong_display_rate",
                                                         "context_preservation_rate", "stage_a_marking_errors", "concept_mismatch_on_A", "extra_items_by_category")},
        "performance_regression_exposed": {k: mr[k] for k in ("normal_transfer_rate", "unnecessary_confirmation_rate", "missing_rate", "wrong_display_rate",
                                                              "context_preservation_rate", "stage_a_marking_errors")},
        "mapping": {k: core["mapping_summary"][k] for k in ("existing_concepts", "existing_concepts_with_allowed_conversion", "evidence_ids_in_inventory",
                                                            "evidence_ids_convertible", "catalog_evidence_total")},
        "reproducibility": rep,
        "verdict_rule_source": "data/prereg_gates.json verdict_rule(평가 전 고정)",
        "disclaimer": "연구용 통합 가능성에 대한 엔지니어링 판단 — 임상적 사용 승인과 무관. 평가 문장·규칙 작성자 동일, 합성 문장, 사람 검증 0.",
    }
    S.dump_json(S.OUT / "integration_verdict.json", v)
    files = sorted(p for d in (S.OUT, S.DATA) for p in d.glob("*") if p.is_file() and p.name != "manifest.json")
    S.dump_json(S.OUT / "manifest.json", {**S.RESEARCH_BANNER, "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                          "files": {str(p.relative_to(S.STEP)): S.sha256(p) for p in files},
                                          "nlu_policy": S.NLU_POLICY, "product_head": prot["product_head_after"],
                                          "inputs": {"step29_3_policy_freeze": S.sha256(S.S293_DIR / "data/policy_freeze.json"),
                                                     "existing_concept_inventory": S.sha256(S.S28_DIR / "data/existing_concept_inventory.csv")}})
    print(S.dumps({k: v[k] for k in ("STEP30_RESULT", "STEP31_READINESS", "gates", "CPU_P95")}))


if __name__ == "__main__":
    main()
