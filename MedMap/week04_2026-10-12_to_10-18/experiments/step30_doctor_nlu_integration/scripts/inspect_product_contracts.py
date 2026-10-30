"""§1 제품 계약 확인(읽기 전용) — 코드에서 실제 값을 읽어 기록. 출력: outputs/product_contracts.json"""
from __future__ import annotations

import json
import subprocess

import s30_common as S


def main():
    S.product()
    from medmap import config, doctor_view, serialization
    from medmap.evidence import EvidenceCatalog
    from medmap.patient_state import AnswerStatus
    import medmap.api_handoff as AH
    cat = EvidenceCatalog()
    raw = json.loads(config.EVIDENCES_JSON.read_text())
    types = {}
    for v in raw.values():
        types[v["data_type"]] = types.get(v["data_type"], 0) + 1
    g = lambda *a: subprocess.run(["git", "-C", str(S.PRODUCT), *a], capture_output=True, text=True).stdout.strip()  # noqa: E731
    import pickle
    with open(config.MODEL_PATHS["k3"], "rb") as fh:
        model = pickle.load(fh)
    out = {
        **S.RESEARCH_BANNER,
        "product_root": str(S.PRODUCT), "git_head": g("rev-parse", "HEAD"), "git_branch": g("rev-parse", "--abbrev-ref", "HEAD"),
        "git_log_3": g("log", "--oneline", "-3").splitlines(),
        "doctor_design_commits": [x for x in g("log", "--oneline", "-8").splitlines() if "design" in x.lower() or "doctor" in x.lower()],
        "evidence_catalog": {"total": len(raw), "by_data_type": types, "excluded": list(config.EXCLUDED_QUESTIONS),
                             "with_parent": sorted(e for e, v in raw.items() if v["code_question"] != e), "encoding_columns": len(cat.columns)},
        "disease_model": {"contexts": list(config.MODEL_CONTEXTS), "k3_classes": len(model.classes_), "k3_n_features": int(getattr(model, "n_features_in_", -1)),
                          "runtime_fit": "없음(DiagnosisEngine 은 predict_proba 만)"},
        "patient_state": {"answer_statuses": [s.value for s in AnswerStatus], "unasked": "키 없음(NEGATIVE 와 다름)", "frozen_dataclass": True,
                          "session_schema": serialization.SESSION_SCHEMA_VERSION, "turn_schema": serialization.TURN_SCHEMA_VERSION},
        "doctor_view": {"schema": doctor_view.DOCTOR_VIEW_SCHEMA_VERSION, "keys": list(doctor_view.DOCTOR_VIEW_KEYS), "wd_states": list(doctor_view.WD_STATES),
                        "blind_rule": "working_diagnosis.state == PENDING → independent_assessment·next_information = {'status':'LOCKED'}",
                        "candidates_max": doctor_view.DOCTOR_CANDIDATES_MAX, "scores_shown": False,
                        "answer_endpoint_rule": "/v1/doctor/answer 는 PENDING 이면 409 MEDMAP_WORKING_DIAGNOSIS_PENDING"},
        "pre_visit_handoff": {"cache_statuses": sorted(AH.CACHE_STATUSES), "cache_item": "{evidence_id, status}", "cache_auto_applied": False,
                              "doctor_summary_groups": ["감별 후보 계산에 반영된 정보(PatientState)", "환자가 확인했지만 반영되지 않은 정보(cache)", "확인되지 않은 정보(UNKNOWN)"],
                              "opt_in_env": "MEDMAP_HANDOFF_CODES=1"},
        "intake_mapper": {"module": "medmap/intake/mapper.py", "kind": "결정적 regex alias → binary evidence 후보(HIGH 만)", "relation_to_step30": "STEP30 은 이 매퍼를 바꾸거나 대체하지 않음"},
        "servers": {"note": "상태만 확인(종료·재시작 없음)", "listen": __import__("protect_check").servers()},
    }
    S.dump_json(S.OUT / "product_contracts.json", out)
    print(S.dumps({k: out[k] for k in ("git_head", "git_branch", "servers")}), out["evidence_catalog"]["total"], out["disease_model"])


if __name__ == "__main__":
    main()
