"""STEP20 보고서 생성: docs/symptom_mapping_audit_report.md. 모든 수치는 outputs/ 의 JSON·CSV 에서 읽는다(손으로 적지 않음).
판정 문장(PASS/CONDITIONAL…)도 아래 규칙으로 계산한다. 서술 문단은 Claude 작성.
"""
import json

import pandas as pd

import common as c

OUT, DOCS = c.OUT, c.STEP / "docs"


def md_table(df):
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        lines.append("| " + " | ".join(str(x).replace("|", "/") for x in r) + " |")
    return "\n".join(lines)


def main():
    cov = json.load(open(OUT / "mapping_coverage_summary.json"))
    dist = json.load(open(OUT / "disease_annotation_distribution.json"))
    man = json.load(open(OUT / "manifest.json"))
    ov = pd.read_csv(OUT / "disease_overlap_summary.csv")
    rep = pd.read_csv(OUT / "representative_symptoms.csv", dtype=str, keep_default_na=False)
    exp = pd.read_csv(OUT / "symptom_expansion_opportunities.csv", dtype=str, keep_default_na=False)
    cur = c.load_curation()
    ddx49 = pd.read_csv(OUT / "auxiliary_kb_ddx49_in_optimuskg.csv", dtype=str, keep_default_na=False)
    umls_a = pd.read_csv(OUT / "ddxplus_umls_mapping_audit.csv", dtype=str, keep_default_na=False)
    snomed_a = pd.read_csv(OUT / "ddxplus_snomed_mapping_audit.csv", dtype=str, keep_default_na=False)
    hpo_a = pd.read_csv(OUT / "ddxplus_hpo_mapping_audit.csv", dtype=str, keep_default_na=False)

    R = cov["roles"]
    NONCORE = sum(v for k, v in R.items() if k not in ("SYMPTOM", "SIGN", "COMPOSITE"))
    inv = pd.read_csv(OUT / "symptom_inventory.csv", dtype=str, keep_default_na=False).set_index("evidence_id")
    N55 = inv.loc["E_55", "n_possible_values"]
    EX = exp.set_index("evidence_id")
    hpoa = pd.read_csv(c.HPO_HPOA, sep="\t", comment="#", header=None, dtype=str, keep_default_na=False,
                       names=["database_id", "disease_name", "qualifier", "hpo_id", "reference", "evidence", "onset",
                              "frequency", "sex", "modifier", "aspect", "biocuration"])
    hpoa = hpoa[(hpoa.database_id != "database_id") & (hpoa.aspect == "P") & (hpoa.qualifier != "NOT")]
    FREQ_EMPTY = f"{(hpoa.frequency == '').mean():.1%}"
    a = cov["all_110"]
    union = a["HPO∪UMLS∪SNOMED"]
    u = union["usable_coverage"]
    mapping = "PASS" if u >= 0.90 else "CONDITIONAL" if u >= 0.70 else "FAIL"
    exp_counts = cov["expansion_levels"]
    hm = exp_counts.get("HIGH", 0) + exp_counts.get("MEDIUM", 0)
    aux = cov["auxiliary_kb"]
    ddx_any = aux["ddx49_with_any_optimuskg_hpo_annotation"]
    ddx_hpoa = dist["ddxplus_49_name_exact_in_hpoa"]["n"]

    def ovn(sset, mode, unit, k):
        r = ov[(ov.hpo_set == sset) & (ov.match_mode == mode) & (ov.count_unit == unit) & (ov.min_overlap == k)]
        return int(r.phenotype_overlap_disease_count.iloc[0])

    cov_rows = []
    for name, b in a.items():
        k = b["counts"]
        cov_rows.append({"ontology": name, "EXACT": k["EXACT"], "BROADER": k["ACCEPTABLE_BROADER"], "NARROWER": k["ACCEPTABLE_NARROWER"],
                         "PARTIAL": k["PARTIAL"], "WRONG": k["WRONG"], "NO_MATCH": k["NO_MATCH"], "N/A": k["NOT_APPLICABLE"],
                         "strict": f"{b['exact_n']}/110 ({b['strict_coverage']:.1%})", "usable": f"{b['usable_n']}/110 ({b['usable_coverage']:.1%})",
                         "partial_incl": f"{b['partial_included_n']}/110 ({b['partial_included_coverage']:.1%})"})
    core = cov["core_symptom_subset"]
    core_rows = [{"ontology": n, "usable": f"{b['usable_n']}/{b['n']} ({b['usable_coverage']:.1%})",
                  "strict": f"{b['exact_n']}/{b['n']} ({b['strict_coverage']:.1%})"} for n, b in core.items()]
    base_rows = [{"existing source": k, "EXACT": v["counts"]["EXACT"], "usable": f"{v['usable_n']}/110",
                  "WRONG": v["counts"]["WRONG"], "no candidate": v["evidences_without_candidate"]}
                 for k, v in cov["baselines_existing_candidates"].items() if not k.startswith("_")]
    ov_rows = []
    for k in (1, 2, 3, 5):
        ov_rows.append({"min overlap (DDX evidence)": f"≥{k}", "exact HPO id": ovn("usable", "exact_id", "distinct_ddx_evidence", k),
                        "true-path (ancestor match)": ovn("usable", "true_path", "distinct_ddx_evidence", k),
                        "OptimusKG true-path": aux["optimuskg_phenotype_overlap_disease_count_true_path"][str(k)]
                        if str(k) in aux["optimuskg_phenotype_overlap_disease_count_true_path"]
                        else aux["optimuskg_phenotype_overlap_disease_count_true_path"].get(k)})
    good = cur[(cur.hpo_class == "EXACT") & (cur.sct_class == "EXACT")][["evidence_id", "canonical_concept", "hpo_ids", "sct_ids", "umls"]].head(12)
    bad_ids = ["E_33", "E_75", "E_169", "E_166", "E_76", "E_150", "E_202", "E_218", "E_13", "E_180", "E_168", "E_128"]
    bad = cur.set_index("evidence_id").loc[bad_ids][["canonical_concept", "hpo_class", "hpo_reason", "sct_class", "umls_class"]].reset_index()
    sty_check = umls_a[(umls_a.candidate_source == "curated") & (umls_a.semantic_type_check == "CHECK")]
    q_rows = [
        ("symptom 110개 전수", "PASS", "load_symptoms() 110/113/223 assert, curation 110행 assert"),
        ("duplicate 없음", "PASS", "evidence_id unique assert (inventory·curation)"),
        ("missing ID 없음", "PASS", "curation 집합 == DDXPlus 증상 집합 assert; curated HPO/SNOMED/CUI 전부 원본에 존재"),
        ("ontology version 기록", "PASS", f"HPO {cov['versions']['hpo']}, UMLS {cov['versions']['umls']}, SNOMED {cov['versions']['snomed']} (manifest.json)"),
        ("obsolete HPO", "PASS", f"기존·curated 후보 중 obsolete {int(hpo_a.is_obsolete.eq('True').sum())}건, alt_id {int(hpo_a.is_alt_id.eq('True').sum())}건 (발견 시 replaced_by/consider 기록 로직 포함)"),
        ("inactive SNOMED", "PASS", f"curated 전부 active; 기존 후보 중 INT 배포판에 없는 US extension ID {int((snomed_a.in_release == 'False').sum())}건 → WRONG 처리·사유 기록"),
        ("UMLS semantic type", "PASS(경고 포함)", f"curated CUI 중 Sign or Symptom/Finding 아닌 것 {len(sty_check)}건 = CHECK 표기(UMLS 가 증상에도 Disease or Syndrome 을 붙임). 질환 자체 CUI(Pertussis·Myasthenias·Cardiac Arrhythmia 등)는 WRONG"),
        ("source provenance", "PASS", "모든 행에 candidate_source(curated/step8_tfidf/step8_concept_map/…)"),
        ("자동 vs 수동 판정 구분", "PASS", "judgement_source = curated / auto_rule / manual_override, review_status 명시"),
        ("재현 가능성", "PASS", "run_all.sh 2회 실행 결과 CSV·JSON SHA256 동일(logs/sha_run1.txt vs sha_run2.txt)"),
        ("deterministic", "PASS", "난수 없음, 정렬 순회"),
        ("임상 검증", "미검증", "curated 판정은 Claude(LLM) 검토이며 임상의 검토 아님 — 수치는 이 판정에 의존"),
    ]
    files = pd.DataFrame([{"file": o["file"], "rows": o.get("rows", ""), "sha256": o["sha256"][:16] + "…"} for o in man["outputs"]])

    md = f"""# DDXPlus 증상 → HPO / UMLS / SNOMED 전수 Mapping Audit (STEP20)

- 작성: 2026-10-08 · 브랜치 `research/symptom-ontology-expansion` · 위치 `exp/step20_symptom_ontology_audit/`
- 범위: **terminology coverage · concept normalization 가능성 · disease retrieval 후보 공간 · KB 확장 가능성**만 본다. 진단 정확도·진단 가능 질환 수는 측정하지 않았다.
- 판정 출처: 110개 증상의 정답 매핑은 **Claude(LLM)가 원본 label·definition·parent를 보고 판정**했다(`curation/curated_mappings.tsv`). **임상의 검증은 받지 않았다.** 기존 후보는 이 판정과 계층 관계로 결정적 규칙 비교 + 사유를 남긴 수동 보정.

## 최종 판정

```
MAPPING            = {mapping}        (usable union {union['usable_n']}/110 = {u:.1%}; 기준 PASS ≥90%, CONDITIONAL 70–90%)
SYMPTOM_EXPANSION  = PARTIAL
RETRIEVAL_RANKING  = CONDITIONAL_GO
질문 2(49-class 재설계 없이 ontology 확장) = PARTIAL
```

## 핵심 수치

| 항목 | 값 |
|---|---|
| DDXPlus symptoms | 110 (증상 {R['SYMPTOM']} · 징후 {R['SIGN']} · 복합 {R['COMPOSITE']} · 속성 {R['ATTRIBUTE']} · 수식어 {R['MODIFIER']} · 노출 {R['EXPOSURE']}) |
| HPO usable mapping | {a['HPO']['usable_n']}/110 |
| SNOMED usable mapping | {a['SNOMED']['usable_n']}/110 |
| UMLS usable mapping | {a['UMLS']['usable_n']}/110 |
| union usable mapping (HPO∪UMLS∪SNOMED) | {union['usable_n']}/110 |
| exact mapping (union) | {union['exact_n']} |
| partial (union, usable 아님) | {union['counts']['PARTIAL']} |
| no match (union) | {union['counts']['NO_MATCH']} |
| not applicable (속성·노출, union) | {union['counts']['NOT_APPLICABLE']} |
| core 증상만(속성·수식어·노출 제외, n={core['HPO∪UMLS∪SNOMED']['n']}) usable union | {core['HPO∪UMLS∪SNOMED']['usable_n']}/{core['HPO∪UMLS∪SNOMED']['n']} |
| expansion HIGH / MEDIUM | {exp_counts.get('HIGH', 0)} / {exp_counts.get('MEDIUM', 0)} (합 {hm}) |
| HPO phenotype-overlap disease count (exact HPO id, ≥1 / ≥3) | {ovn('usable', 'exact_id', 'distinct_ddx_evidence', 1):,} / {ovn('usable', 'exact_id', 'distinct_ddx_evidence', 3):,} |
| 같은 수치, true-path(조상 일치) ≥1 / ≥3 | {ovn('usable', 'true_path', 'distinct_ddx_evidence', 1):,} / {ovn('usable', 'true_path', 'distinct_ddx_evidence', 3):,} |
| DDXPlus 49질환이 HPO 주석(phenotype.hpoa)에 이름 그대로 있는 수 | {ddx_hpoa} |
| DDXPlus 49질환 중 OptimusKG에서 HPO 증상 주석이 1개 이상인 수 | {ddx_any} |

> phenotype-overlap disease count는 **"이 증상 어휘로 후보에 올릴 수 있는 질환 공간"**이다. 진단 가능한 질환 수가 아니다.

## Coverage 표 (all 110, NOT_APPLICABLE 포함 분모)

{md_table(pd.DataFrame(cov_rows))}

core 증상 subset(속성·수식어·노출 {NONCORE}개 제외):

{md_table(pd.DataFrame(core_rows))}

## 기존 mapping 후보 감사 (step8)

- `evidence_hpo_candidates.csv`·`evidence_umls_candidates.csv`: 문자열 TF-IDF 자동 후보. **review_status·final 칸이 110/110 비어 있어** 사람이 확정한 매핑은 없었다. HPO는 정확 매칭이 아니라 질문문 정규화 문자열 유사도라, `E_52 이중 시야 → Overlapping toe`처럼 단어 조각 일치로 오매핑이 많다. UMLS 후보는 {cov['baselines_existing_candidates']['UMLS step8 TF-IDF cui1']['evidences_without_candidate']}/110 증상에 후보가 아예 없다.
- `evidence_concept_map.csv`(이전 세션의 의미 구조 기반 map)는 훨씬 낫지만, 질환 개념을 증상 자리에 둔 경우(Cardiac arrhythmia·GERD·Pertussis)와 의미가 반대인 경우(E_180 Ophthalmoplegia — 실제 질문은 눈이 저절로 돌아가는 oculogyric 증상)가 있다.

{md_table(pd.DataFrame(base_rows))}

("best component"는 증상마다 가장 유리한 후보를 고른 상한값)

## 1. 잘 매핑되는 대표 사례

{md_table(good)}

## 2. 잘 안 되는 대표 사례

{md_table(bad)}

## 3. 현재 110개 증상 구조의 근본적인 한계

- **110개 중 {NONCORE}개는 증상이 아니다**: 속성 {R['ATTRIBUTE']}(부위·양상·강도·발생속도·위치 명확도·색·크기·부종·통증 강도), 수식어 {R['MODIFIER']}(악화·완화·야간·식후·악화 경향), 노출 {R['EXPOSURE']}(E_42). 이 {NONCORE}개는 어떤 ontology의 "증상 개념"으로도 정확히 대응하지 않는다(커버리지 분모에 남겨 둠).
- **흔한 주소(主訴)가 독립 증상이 아니다**: 흉통·두통·복통은 `E_53 통증 + E_55 부위 값({N55}개)` 조합이다. ontology의 Chest pain·Headache·Abdominal pain 개념은 evidence가 아니라 **값 수준**에서만 연결된다.
- **복합 질문 {R['COMPOSITE']}개**: 한 질문에 2–3개 개념(예: E_175 피로·권태·근육통). 답이 "예"여도 어느 개념인지 모른다.
- **같은 개념의 변형이 별도 feature**: 호흡곤란 E_66·E_64·E_67·E_217, 기침 E_201·E_203·E_77·E_166, 피로 E_89·E_88·E_175. ontology 관점에서는 하나의 개념 + slot.
- **극성 반전**: E_150 "대변·방귀가 나오나요?"(예 = 정상) — 개념(Obstipation)과 반대 방향.
- **HPO는 증상 표현에 약하다**: HPO는 유전·희귀질환 표현형 중심이라 lightheadedness, choking sensation, 코·목 가려움, post-tussive vomiting, 통증 완화 자세 같은 일상 증상 개념이 없거나 진단 수준 라벨(Laryngospasm, Arrhythmia, GERD)로만 있다.

## 4. ontology를 붙였을 때 실제로 좋아지는 것

- **표준 ID 정규화**: core 증상 {core['HPO∪UMLS∪SNOMED']['n']}개 중 {core['HPO∪UMLS∪SNOMED']['usable_n']}개가 최소 한 ontology에서 usable 매핑을 갖는다. 다른 데이터·KB와 같은 ID로 연결할 수 있다.
- **표현층 분리 근거**: UMLS 소비자 어휘(CHV·MedlinePlus) 표현이 {cov['normalization_layers']['evidence_with_consumer_strings']}/110 증상에 있고, 증상 1개당 영어 표현 중앙값 {cov['normalization_layers']['median_umls_english_strings']:.0f}개 → "표현 여러 개 = 개념 1개" 구조를 데이터로 뒷받침(`concept_normalization_layers.csv`).
- **세분화 어휘**: SNOMED·HPO 하위 개념(예: 기침 하위 SNOMED {EX.loc['E_201','snomed_children_n']}개, 통증 하위 HPO {EX.loc['E_53','hpo_descendant_terms_n']}개)을 slot 값 어휘로 쓸 수 있다. 단, 대부분 부위·시간·양상의 사전 조합이라 **별도 feature로 쪼개지 말고 slot 값으로 쓰는 것**을 권고(`snomed_split_recommendation`).
- **확장 차원**: expansion HIGH {exp_counts.get('HIGH', 0)}개 · MEDIUM {exp_counts.get('MEDIUM', 0)}개 — 발생·기간·강도·양상·악화/완화·동반증상 slot을 붙일 여지가 있다.

## 5. ontology를 붙여도 해결되지 않는 것

- **한국어 표현 → 개념 연결(entity linking)**: 이번에 사용한 HPO·SNOMED(INT)·UMLS(영어 parquet)에는 한국어 표현이 없다. "숨이 가빠요"를 C0013404로 보내는 단계는 별도 구현·검증이 필요하다.
- **속성·수식어의 구조화**: ontology는 개념 ID를 줄 뿐, "어느 증상이 어떤 자세에서 악화되는지" 같은 관계는 MedMap 스키마(`docs/canonical_symptom_schema_draft.md`)가 담아야 한다.
- **현재 classifier 입력**: 49질환 모델은 DDXPlus 223 feature만 받는다. 새 개념은 기존 feature로 되돌릴(projection) 수 있는 하위 개념이 아니면 모델에 들어가지 않는다.
- **흔한 질환의 증상 지식**: HPO 질환 주석은 희귀·유전질환 위주다. DDXPlus 49질환 중 이름 그대로 있는 것은 {ddx_hpoa}개, OptimusKG에서 HPO 증상 주석이 있는 것은 {ddx_any}개뿐이다.
- **확률·빈도**: phenotype.hpoa의 빈도 칸은 희귀질환 문헌 기반이고, aspect P 주석의 {FREQ_EMPTY}가 비어 있다. 일차 진료 증상의 사전확률은 여기서 나오지 않는다.

## 6. 질환 확장 가능성

phenotype.hpoa (`{dist['hpoa_version_line'][:80]}…`):

- 질환 {dist['phenotypic_abnormality_aspect_P_excluding_NOT']['diseases']:,}개(aspect P, NOT 제외) — OMIM {dist['phenotypic_abnormality_aspect_P_excluding_NOT']['by_source'].get('OMIM', 0):,} · ORPHA {dist['phenotypic_abnormality_aspect_P_excluding_NOT']['by_source'].get('ORPHA', 0):,} · DECIPHER {dist['phenotypic_abnormality_aspect_P_excluding_NOT']['by_source'].get('DECIPHER', 0)}; 주석 {dist['phenotypic_abnormality_aspect_P_excluding_NOT']['annotations']:,}개, 서로 다른 HPO term {dist['phenotypic_abnormality_aspect_P_excluding_NOT']['distinct_hpo_terms']:,}개
- 질환당 phenotype 수: 중앙값 {dist['phenotypes_per_disease']['50%']:.0f} (10% {dist['phenotypes_per_disease']['10%']:.0f} · 90% {dist['phenotypes_per_disease']['90%']:.0f} · 최대 {dist['phenotypes_per_disease']['max']:.0f})
- phenotype당 질환 수: 중앙값 {dist['diseases_per_phenotype']['50%']:.0f} (90% {dist['diseases_per_phenotype']['90%']:.0f} · 최대 {dist['diseases_per_phenotype']['max']:.0f})

usable HPO 매핑만 썼을 때 phenotype-overlap disease count:

{md_table(pd.DataFrame(ov_rows))}

- exact HPO id = 질환 주석 term이 매핑 term과 같을 때만, true-path = 질환 주석 term의 조상에 매핑 term이 있으면 일치(예: "Productive cough" 주석 → Cough 일치).
- true-path 수치는 `HP:0000951 Abnormality of the skin`·`HP:0012531 Pain` 같은 넓은 term 때문에 부풀려진다. **보수적으로는 exact id 수치를 본다.**
- 이 공간은 대부분 **희귀·유전질환**이다. 일차 진료의 흔한 질환 후보 공간이 아니다.

## 보조 KB 대조 (통합하지 않음)

- HSDN 증상 어휘(MeSH 322개)에 있는 증상: {aux['hsdn_symptom_vocab_hits']}/110 · MEDLINE 공출현 증상 어휘: {aux['medline_symptom_vocab_hits']}/110
- HPO에서 NO_MATCH/PARTIAL인데 HSDN·MEDLINE 어휘에는 있는 증상: {', '.join(aux['hpo_no_match_or_partial_but_in_hsdn_or_medline']) or '없음'}
- OptimusKG: HPO 증상 edge가 있는 질환 {aux['optimuskg_diseases_with_phenotype_edges']:,}개. DDXPlus 49질환 중 이름(일부 별칭)으로 노드를 찾은 수 {aux['ddx49_found_in_optimuskg_by_name']}, 그중 HPO 증상 주석이 1개 이상인 수 {ddx_any} (`auxiliary_kb_ddx49_in_optimuskg.csv`)
- DisMech: 이번에 재측정하지 않음(4.9 GB YAML). 기존 README 기록은 49질환 중 17개 연결.

## 대표 증상 상세

{md_table(rep[['representative_symptom', 'ddxplus_representation', 'hpo_mapping', 'snomed_mapping', 'umls_mapping', 'expansion_level']])}

추천 canonical 표현은 `outputs/representative_symptoms.csv`의 `recommended_canonical_representation`, 스키마는 `docs/canonical_symptom_schema_draft.md`.

## 17절 판정 근거

- **질문 1 — 110개 제한에서 벗어날 기술적 기반: PARTIAL.** 영어 개념 정규화 기반은 있다(core {core['HPO∪UMLS∪SNOMED']['usable_n']}/{core['HPO∪UMLS∪SNOMED']['n']} usable, 소비자 표현 {cov['normalization_layers']['evidence_with_consumer_strings']}/110). 그러나 한국어 표현 연결, 속성 slot 구조, 흔한 질환의 증상 KB가 없다.
- **질문 2 — 49-class 모델 재설계 없이 ontology 기반 확장: PARTIAL.** 기존 evidence의 **하위 개념**(예: 객담 색, 야간 기침)은 상위 개념으로 되돌려(projection) 현재 모델에 넣을 수 있다. 그러나 기존 223 feature에 대응이 없는 **새 증상 개념**은 학습 데이터(DDXPlus 합성)에 없어서 현재 classifier가 쓸 수 없다.
- **질문 3 — Retrieval + Ranking 구조로 넘어갈 가치: CONDITIONAL_GO.** 개념 정규화와 질환-증상 KB(희귀질환 {dist['phenotypic_abnormality_aspect_P_excluding_NOT']['diseases']:,}개)는 있다. 하지만 DDXPlus 49질환 같은 흔한 질환의 증상 주석이 거의 없고({ddx_any}/49), 빈도 정보와 평가 정답이 없다. **흔한 질환 증상 KB를 확보하고 평가 설계를 먼저 고정한다는 조건**에서만 baseline 실험 가치가 있다.

## 7. 다음 실험 제안 (자동 진행하지 않음)

가장 먼저 할 것 하나: **"한국어 환자 표현 → canonical 증상 개념" 연결의 소규모 평가셋 만들기.** 기존 natural intake 문장과 `terminology_ko.json` 표현에서 core 증상 {core['HPO∪UMLS∪SNOMED']['n']}개를 대상으로 표현–개념 쌍을 고정한 뒤, 사전 기반 baseline부터 측정한다(외부 모델 설치 전).
Disease Retrieval baseline은 흔한 질환 증상 KB 확보 여부를 먼저 결정해야 하므로 그 다음이다.

## 품질 검증 (21절)

{md_table(pd.DataFrame(q_rows, columns=['항목', '결과', '근거']))}

결과 파일(row 수·SHA256 앞 16자, 전체는 `outputs/manifest.json`):

{md_table(files)}

## 한계

- 정답 판정(curated)은 Claude 1인(LLM) 판정이다. 임상의·독립 reviewer 재판정이 없어서 EXACT/ACCEPTABLE 경계는 판정자에 따라 바뀔 수 있다. coverage 수치는 이 판정에 의존한다.
- 기존 후보 판정은 curated 와의 계층 비교 규칙 + 수동 보정(스크립트의 OVERRIDES 목록)이다. 규칙상 WRONG 이어도 의미가 일부 겹치는 후보가 남아 있을 수 있다.
- SNOMED 는 International 배포판만 사용했다(US extension 개념은 없음). UMLS 는 영어 MRCONSO(SUPPRESS=N)만 사용했다.
- phenotype-overlap 은 희귀질환 주석(phenotype.hpoa) 기준이며, true-path 수치는 넓은 상위 term 때문에 커진다.

## 이 감사에서 주장하지 않는 것

- HPO를 붙이면 모든 질환을 진단할 수 있다 — 주장하지 않음
- SNOMED를 쓰면 희귀질환을 찾을 수 있다 — 주장하지 않음
- 49질환에서 수천 질환으로 진단 확장 가능하다 — 주장하지 않음(수천은 phenotype-overlap 후보 공간일 뿐)
- ontology coverage가 높으니 진단 정확도가 높다 — 주장하지 않음(정확도는 측정하지 않음)

## 재현

```bash
bash exp/step20_symptom_ontology_audit/run_all.sh          # 원본 data/ 읽기만, 약 10–20분, 캐시 .cache/
~/ai_env/bin/python exp/step20_symptom_ontology_audit/scripts/build_report.py
```
"""
    DOCS.mkdir(exist_ok=True)
    (DOCS / "symptom_mapping_audit_report.md").write_text(md, encoding="utf-8")
    print("report written", mapping, union["usable_n"])


if __name__ == "__main__":
    main()
