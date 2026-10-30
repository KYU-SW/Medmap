"""§4 NLU 실제 반환 구조 확인(읽기 전용) — 지시문 §11 사례(노출 회귀)를 R2 에 넣어 mention 키·값 종류를 기록. 스키마를 가정하지 않는다.
출력: outputs/nlu_interface_inventory.json"""
from __future__ import annotations

import collections

import s30_common as S
import validate_schema as VS


def main():
    A = S.nlu()
    cases = [c for c in S.load_json(S.DATA / "integration_contract_cases.json")["cases"] if c["set"] == "REGRESSION_EXPOSED"]
    keys = collections.Counter()
    vals = collections.defaultdict(collections.Counter)
    ctx_keys = collections.Counter()
    n = 0
    for c in cases:
        out = A.analyze(c["text"], S.NLU_POLICY)
        ctx_keys.update((out.get("context") or {}).keys())
        for m in out["mentions"]:
            n += 1
            keys.update(m.keys())
            for f in ("status", "assertion", "temporality", "current_status", "experiencer", "evidence_level", "evidence_sources", "ko_tier", "time_scope"):
                vals[f][str(m.get(f))] += 1
    res = {**S.RESEARCH_BANNER, "entry": "exp/step29_3_concept_retrieval_repair/scripts/step29_2_adapter.analyze(text, 'R2')",
           "top_level_keys": ["source_text", "level", "mentions", "context"], "context_keys": dict(ctx_keys), "mentions": n,
           "mention_keys": dict(sorted(keys.items())), "observed_values": {k: dict(v) for k, v in vals.items()},
           "required_fields": {f: ("NLU" if f in VS.NLU_NATIVE else "ADAPTER " + VS.ADAPTER_DERIVED[f]) for f in
                               __import__("doctor_integration_adapter").REQUIRED_FIELDS},
           "missing_in_nlu": [f for f in VS.ADAPTER_DERIVED]}
    S.dump_json(S.OUT / "nlu_interface_inventory.json", res)
    print("mentions", n, "keys", len(keys), "missing_in_nlu", res["missing_in_nlu"])


if __name__ == "__main__":
    main()
