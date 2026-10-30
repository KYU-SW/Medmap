"""STEP28 1단계 — 이전 단계 산출물·ontology 원본 메타데이터 확인 + 기존 77 concept 목록(read-only 입력).

검사:
 P1 입력 SHA256(STEP20 curated·STEP21 사전·STEP23 학습 표현·STEP27 routing·silver·terminology·aliases·DDXPlus evidences)
 P2 STEP27 결과 확인(step27_verdict.json 값) · STEP27 manifest 의 산출물 SHA 가 지금도 같은지(덮어쓰기 없음)
 P3 ontology 원본 메타데이터: hp.obo data-version · SNOMED RF2 파일명 release 일자 · UMLS MRSAB 의 SAB 별 버전·SRL
 P4 77 concept ↔ DDXPlus evidence crosswalk(87 evidence) · STEP20 curated HPO/SNOMED/UMLS id · 한국어 용어 수
출력: outputs/previous_inspection.json · data/existing_concept_inventory.csv
"""
import collections
import csv
import json

import s28_common as S


def main():
    files = [S.S20 / "curation/curated_mappings.tsv", S.S21 / "data/dictionary_expressions.csv", S.S23 / "data/expanded_train_expressions.csv",
             S.S27_DIR / "outputs/step27_verdict.json", S.S27_DIR / "outputs/routing_selection.json", S.S27_DIR / "outputs/routing_decisions.csv",
             S.S27_DIR / "data/external_silver_candidates.csv", S.TERMINOLOGY, S.MAIN / "medmap/intake/aliases_ko.json",
             S.MAIN / "data/ddxplus/en/release_evidences.json", S.HPO_OBO, S.UMLS_SAB]
    sha = {str(f): S.sha256(f) for f in files}
    man27 = S.load_json(S.S27_DIR / "outputs/manifest.json")
    changed27 = [k for k, v in man27["files_sha256"].items() if (S.S27_DIR / k).exists() and S.sha256(S.S27_DIR / k) != v
                 and not k.startswith("outputs/latency") and k not in ("outputs/step27_verdict.json",)]
    v27 = S.load_json(S.S27_DIR / "outputs/step27_verdict.json")

    hpo_ver = next(ln.split(":", 1)[1].strip() for ln in S.HPO_OBO.open(encoding="utf-8") if ln.startswith("data-version:"))
    sct_files = sorted(p.name for p in S.SCT_DIR.glob("*.txt"))
    sab = {}
    for ln in S.UMLS_SAB.open(encoding="utf-8"):
        f = ln.rstrip("\n").split("|")
        if f[21] == "Y":
            sab[f[3]] = {"version": f[6], "srl": int(f[13]), "language": f[19], "name": f[4]}
    used = {k: sab.get(k) for k in S.UMLS_EN_SABS + S.SRL_ALLOWED_KOR + S.SRL_EXCLUDED_KOR}

    cw = S.evidence_crosswalk()
    ev = json.loads((S.MAIN / "data/ddxplus/en/release_evidences.json").read_text(encoding="utf-8"))
    term = S.load_terminology()
    with (S.S20 / "curation/curated_mappings.tsv").open(encoding="utf-8") as fh:
        cur = {r["evidence_id"]: r for r in csv.DictReader(fh, delimiter="\t")}
    train = collections.Counter(r["canonical_id"] for r in S.read_csv(S.S23 / "data/expanded_train_expressions.csv"))
    names = {r["canonical_id"]: r["canonical_name"] for r in S.read_csv(S.S23 / "data/expanded_train_expressions.csv")}
    by_c = collections.defaultdict(list)
    for e, c in cw.items():
        by_c[c].append(e)
    inv = []
    for c in sorted(names):
        es = sorted(by_c.get(c, []), key=lambda x: int(x.split("_")[1]))
        ids = {"hpo": set(), "sct": set(), "umls": set()}
        cls = []
        for e in es:
            r = cur.get(e)
            if r:
                for k, col in (("hpo", "hpo_ids"), ("sct", "sct_ids"), ("umls", "umls")):
                    ids[k] |= {x.strip() for x in r[col].replace(";", "|").split("|") if x.strip()}
                cls.append(f"{e}:{r['hpo_class']}/{r['sct_class']}/{r['umls_class']}")
        inv.append({"canonical_id": c, "canonical_name": names[c], "ddxplus_evidence_ids": ";".join(es),
                    "evidence_label_ko": ";".join(term["evidence_short"].get(e, {}).get("label_ko", "") for e in es),
                    "n_korean_train_expressions": train[c], "hpo_ids": ";".join(sorted(ids["hpo"])), "snomed_ids": ";".join(sorted(ids["sct"])),
                    "umls_cuis": ";".join(sorted(ids["umls"])), "step20_mapping_classes": ";".join(cls),
                    "model_supported": all(e in ev for e in es) and bool(es), "attributes": "E_55(site);E_54;E_56;E_57;E_58;E_59" if c == "pain" else ""})
    S.write_csv(S.DATA / "existing_concept_inventory.csv", inv)
    out = {"P1_input_sha256": sha, "P2_step27": {"STEP27_RESULT": v27["STEP27_RESULT"], "BEST_POLICY": v27["BEST_POLICY"], "FALSE_NON_RATE": v27["FALSE_NON_RATE"],
                                                  "WEAK_NEGATIVE_AUTO_ACCEPT_RATE": v27["WEAK_NEGATIVE_AUTO_ACCEPT_RATE"], "SUPPORTED_AUTO_COVERAGE": v27["SUPPORTED_AUTO_COVERAGE"],
                                                  "manifest_files_changed_since(excluding latency/verdict)": changed27},
           "P3_ontology_versions": {"hpo_obo_data_version": hpo_ver, "snomed_rf2_snapshot_files": sct_files, "umls_release": "2026AA",
                                    "umls_sabs": used, "note": "UMLS 안 HPO SAB 버전은 MRSAB 값, 로컬 hp.obo 와 다를 수 있음(색인의 HPO 정본 = hp.obo)"},
           "P4_inventory": {"n_canonical": len(inv), "n_crosswalk_evidences": len(cw), "n_ddxplus_evidences": len(ev),
                            "n_canonical_without_hpo": sum(not r["hpo_ids"] for r in inv),
                            "n_ddxplus_symptomlike_not_in_77": sum(1 for e, x in ev.items() if not x["is_antecedent"] and e not in cw)}}
    S.dump_json(S.OUT / "previous_inspection.json", out)
    print(S.dumps({k: v for k, v in out.items() if k != "P1_input_sha256"}))
    assert not changed27, f"STEP27 산출물이 바뀜: {changed27}"
    assert len(inv) == 77


if __name__ == "__main__":
    main()
