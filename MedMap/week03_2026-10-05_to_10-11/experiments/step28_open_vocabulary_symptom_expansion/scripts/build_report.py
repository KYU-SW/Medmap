"""STEP28 판정 + 보고서 + manifest. 숫자는 outputs/·data/ 파일에서 읽는다. (판정 규칙 사전 고정 — Silver 평가 실행 전 작성)

KOREAN_ONTOLOGY_LINKING
  PASS    : 77 밖 한국어 표현의 신규 concept 연결이 검증 근거(EXACT/ACCEPTABLE)로 Silver 에서 10 입력 이상 + 경로 C gate 통과
  PARTIAL : 기존 77 concept 의 한국어 → 표준 id 연결(경로 A/B)은 동작하지만 77 밖 한국어 연결의 검증 근거가 10 입력 미만
  FAIL    : 기존 concept 연결도 Silver 에서 10 입력 미만
NEW_CONCEPT_RETRIEVAL
  PASS    : Silver 한국어 입력에서 검증된 신규 concept 10 입력 이상
  PARTIAL : 한국어 입력에서는 검증된 신규 0–9 이지만, ontology 색인·검증기가 77 밖 concept(대표 Epistaxis)을 찾아 기존과 구분(concept_relation_checks)
  FAIL    : 색인·검증기 자체가 77 밖 concept 을 찾거나 구분하지 못함
CONCEPT_DUPLICATION_CONTROL = PASS ⇔ 신규 id 의 77 충돌 0 · 대표 중복(Hemoptysis·Hematemesis·Fever·Pain)이 기존으로 해소 · Headache 가 pain+부위 속성
UNKNOWN_PRESERVATION = PASS ⇔ Silver 원문 보존율 100% · UNKNOWN 에 canonical 0 · UNKNOWN 에 표시 후보 0
STEP28_RESULT: EXPANSION_FEASIBLE = 위 네 개 모두 PASS · PARTIAL_FEASIBILITY = NEW_CONCEPT_RETRIEVAL ≥ PARTIAL 이고 중복·보존 PASS · 그 외 NOT_FEASIBLE
PRODUCT_INTEGRATION = HOLD(고정)
"""
import collections
import json

import s28_common as S


def table(rows, head):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] + ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def pct(x):
    return "—" if x is None else f"{float(x) * 100:.1f}%"


def main():
    cov = S.load_json(S.OUT / "expansion_coverage.json")
    rel = S.load_json(S.OUT / "concept_relation_checks.json")
    fz = S.load_json(S.OUT / "crosslingual_feasibility.json")
    lat = S.load_json(S.OUT / "latency.json")
    ib = S.load_json(S.OUT / "index_build.json")
    insp = S.load_json(S.OUT / "previous_inspection.json")
    sil = S.read_csv(S.DATA / "external_silver_expansion.csv")
    rep = S.read_csv(S.OUT / "representative_cases.csv")
    n = cov["n_inputs(silver)"]
    cat = collections.Counter(s["step28_category"] for s in sil)
    verified = cov["verified_mapping_candidate_count(EXACT/ACCEPTABLE new)"]
    ver_inputs = sum(1 for s in sil if s["step28_category"] == "NEW_ONTOLOGY_CONCEPT")
    existing_inputs = cat["EXISTING_CANONICAL"] + cat["EXISTING_COMPOSITE"]
    v = rel["validation_as_if_linked"]
    epi_ok = any((v["Epistaxis"][k] or {}).get("new_concept") for k in ("hpo", "snomed")) and all(
        p["relation"] == "DISTINCT" for p in rel["pairwise_relations"] if p["a_name"] in ("Epistaxis", "Bleeding from nose"))
    kol = "PASS" if ver_inputs >= 10 and fz["PATH_C_ENABLED"] else "PARTIAL" if existing_inputs >= 10 else "FAIL"
    ncr = "PASS" if ver_inputs >= 10 else "PARTIAL" if epi_ok else "FAIL"
    dup_rep = all(str((v[nm]["hpo"] or {}).get("check", "")).startswith("DUPLICATE_OF_EXISTING") for nm in ("Hemoptysis", "Hematemesis", "Fever", "Pain"))
    head_attr = all(str((v["Headache"][k] or {}).get("check", "")).startswith("NARROWER_AS_ATTRIBUTE") for k in ("hpo", "snomed"))
    dup = "PASS" if cov["concept_duplication"]["new_id_collision_with_77"] == 0 and dup_rep and head_attr else "FAIL"
    uh = cov["unsupported_concept_handling"]
    unk = "PASS" if cov["raw_text_preservation_rate"] == 1.0 and uh["UNKNOWN_with_display"] == 0 and uh["UNKNOWN_with_canonical"] == 0 else "FAIL"
    res = ("EXPANSION_FEASIBLE" if all(x == "PASS" for x in (kol, ncr, dup, unk)) else
           "PARTIAL_FEASIBILITY" if ncr in ("PASS", "PARTIAL") and dup == "PASS" and unk == "PASS" else "NOT_FEASIBLE")
    p95 = lat["single_input_cpu"]["STEP28_FULL"]["p95_ms"]
    verdict = {"STEP28_RESULT": res, "KOREAN_ONTOLOGY_LINKING": kol, "NEW_CONCEPT_RETRIEVAL": ncr, "CONCEPT_DUPLICATION_CONTROL": dup,
               "UNKNOWN_PRESERVATION": unk, "PRODUCT_INTEGRATION": "HOLD", "PRODUCTION_READY": "NO", "PATH_C_ENABLED": fz["PATH_C_ENABLED"],
               "numbers": {"inputs": n, "existing_canonical": cat["EXISTING_CANONICAL"], "existing_composite": cat["EXISTING_COMPOSITE"],
                           "new_ontology_candidates(auto)": cov["new_ontology_concept_candidate_count(auto, unverified 포함)"],
                           "needs_verification": cov["needs_semantic_verification_count"], "verified_new_inputs": ver_inputs,
                           "unknown": cat["UNKNOWN_SYMPTOM"], "non_symptom": cat["NON_SYMPTOM"], "uncertain": cat["UNCERTAIN"],
                           "unsupported_display_inputs": cov["unsupported_display_inputs"], "raw_preservation_rate": cov["raw_text_preservation_rate"],
                           "cpu_p50_ms": lat["single_input_cpu"]["STEP28_FULL"]["p50_ms"], "cpu_p95_ms": p95, "index_bytes": ib["index_bytes"]},
               "rules": __doc__}
    S.dump_json(S.OUT / "step28_verdict.json", verdict)

    grp = cov["silver_groups(§11)"]
    comp = S.read_csv(S.OUT / "comparison_step27_step28.csv")
    reprows = [[r["input"], r["set"], r["step27_status"], r["step27_candidates"] or "—", r["step28_category"], r["reason"], r["canonical_id"] or "—",
                (json.loads(r["attributes"]).get("site_ko", "") if r["attributes"] else "") or "—", r["display"] or "—", r["korean_link_path"]] for r in rep]
    pairs = [[p["source"], p["a_name"], p["b_name"], p["relation"], "; ".join(f"{x[1]}" for x in p["nearest_common_ancestors"][:2])] for p in rel["pairwise_relations"]]
    vrows = [[nm, (v[nm]["hpo"] or {}).get("candidate_concept_id", "—"), (v[nm]["hpo"] or {}).get("check", "—"),
              (v[nm]["snomed"] or {}).get("candidate_concept_id", "—"), (v[nm]["snomed"] or {}).get("check", "—")] for nm in v]
    I = cov["internal"]
    wn = cov["weak_non_eval"]
    lt = lat["single_input_cpu"]
    unk_ex = [s["raw_expression"] for s in sil if s["step28_category"] == "UNKNOWN_SYMPTOM"][:25]
    wnr = S.read_csv(S.OUT / "weak_non_check.csv")
    wn_reasons = dict(collections.Counter(r["reason"] for r in wnr if r["step28_category"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")))
    q4_reasons = dict(collections.Counter(s["step28_reason"] for s in sil if s["step27_status"] == "KNOWN_SYMPTOM"
                                          and s["step28_category"] not in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE")))
    md = f"""# STEP28 — MedMap Open-Vocabulary Symptom Expansion

- **STEP28_RESULT = {res}** · KOREAN_ONTOLOGY_LINKING = {kol} · NEW_CONCEPT_RETRIEVAL = {ncr} · CONCEPT_DUPLICATION_CONTROL = {dup} · UNKNOWN_PRESERVATION = {unk} · PRODUCT_INTEGRATION = HOLD · **PRODUCTION_READY = NO**
- 외부 Gold 없음 → 아래 수치는 매핑 정확도가 아니다. Silver 442 = BERT-NER-KO 증상(ST) span(자동 판정, 사람 검증 아님). 판정 규칙: `scripts/build_report.py` 문서열(평가 전 고정).
- 기존 모델(Linear·KoELECTRA·Hybrid B·B4·STEP27 POLICY_D)·49질환 모델·제품 코드·PatientState 미수정. 신규 다운로드·번역 API·유료 API 없음. STEP27 산출물 SHA 불변(변경 {len(insp['P2_step27']['manifest_files_changed_since(excluding latency/verdict)'])}건).

## 1. 핵심 수치(Silver 442)

| 항목 | 값 |
|---|---|
| 입력 한국어 표현 | {n} |
| 기존 canonical 연결 | {cat['EXISTING_CANONICAL']} |
| 기존 속성 조합(pain+부위) | {cat['EXISTING_COMPOSITE']} |
| 신규 ontology concept 후보(자동, 검증 전) | {cov['new_ontology_concept_candidate_count(auto, unverified 포함)']} (입력 {cov['new_concept_inputs(auto 후보가 있는 입력 수)']}) |
| 의미 검증이 필요한 후보 | {cov['needs_semantic_verification_count']} |
| 검증된 신규 concept 입력(EXACT/ACCEPTABLE) | {ver_inputs} |
| UNKNOWN(원문 보존) | {cat['UNKNOWN_SYMPTOM']} |
| NON_SYMPTOM | {cat['NON_SYMPTOM']} |
| UNCERTAIN | {cat['UNCERTAIN']} |
| 근거 없는 후보 표시(proxy) STEP27 → STEP28 | {cov['unsupported_display_inputs']['STEP27']} → {cov['unsupported_display_inputs']['STEP28']} 입력 (표시 입력 {cov['display_inputs']['STEP27']} → {cov['display_inputs']['STEP28']}) |
| 원문 보존율 | {pct(cov['raw_text_preservation_rate'])} |
| CPU p50 / p95 (STEP28 전체, 442 입력) | {lt['STEP28_FULL']['p50_ms']} / {p95} ms |
| 색인 크기 / 생성 시간 | {ib['index_bytes'] / 1e6:.1f} MB / {ib['total_seconds']} s (원본 약 {sum(ib['source_bytes'].values()) / 1e9:.2f} GB) |

§11 분류: {S.dumps(grp)}

## 2. 한국어 → ontology 연결 경로(실측)

| 경로 | 자원 | 결과 |
|---|---|---|
| A | MedMap 한국어 용어(STEP23 1,119·STEP21 294·용어집 223)·제품 매퍼 alias·STEP27 모델 | 기존 77 concept 연결 {existing_inputs} 입력 |
| B | A → STEP20 curated HPO/SNOMED/UMLS id | 기존 concept 의 표준 id 부여(신규 아님) |
| K | UMLS KOR SRL 0: LNC-KO-KR 검사명 · TKMT 약재명 ({ib['umls']['kor_rows_loaded(SRL0)']}행) | 비증상(검사·약재) 근거로만 사용 |
| C | 로컬 xlm-roberta-base 평균 풀링 → HPO 영어 | 타당성 gate hit@5 = {pct(fz['hit@k']['5'])} · hit@1 {pct(fz['hit@k']['1'])} (기준 50%, 질의 {fz['n_queries']} = 기존 증거 한국어 라벨) → PATH_C_ENABLED = {fz['PATH_C_ENABLED']} |
| D | 연결 자원 없음 | UNKNOWN(KOREAN_LINK_MISSING) |
| (제외) | UMLS KOR SRL 3: MDRKOR(MedDRA 한국어 {ib['umls']['kor_rows_not_loaded(SRL>0)'].get('MDRKOR', 0)}행) · KCD5({ib['umls']['kor_rows_not_loaded(SRL>0)'].get('KCD5', 0)}행) | 이용 조건 확인 필요 → 색인에 넣지 않음 |

경로별 입력 수: {S.dumps(cov['korean_link_path_counts'])}

## 3. 대표 사례(회귀 확인용 — 이 사례로 규칙을 만들거나 일반화 성능을 주장하지 않음)

{table(reprows, ['입력', '집합', 'STEP27', 'STEP27 후보', 'STEP28', '근거', 'canonical', '부위', '표시 후보', '연결 경로'])}

## 4. ontology 개념 관계(영어 이름 조회 — 한국어 연결 아님)

{table(pairs, ['출처', 'A', 'B', '관계', '가까운 공통 조상'])}

검증기 판정(한국어 근거가 있다고 가정): {table(vrows, ['개념', 'HPO', 'HPO 판정', 'SNOMED', 'SNOMED 판정'])}

## 5. STEP27 ↔ STEP28 (Silver 같은 입력)

{table([[c['step27_status'], c['step28_category'], c['n']] for c in comp], ['STEP27', 'STEP28', 'n'])}

- Q1 STEP27 UNKNOWN/UNCERTAIN {cov['Q1_step27_unknown_or_uncertain(n)']} 중 기존 증상으로 회수 {cov['Q1_of_those_now_existing']} · 신규 ontology 후보 {cov['Q1_of_those_new_ontology_candidate']} · 검증된 신규 {cov['Q2_of_those_verified']}
- Q4 STEP27 KNOWN 인데 STEP28 기존 아님 {cov['Q4_step27_known_now_not_existing']} · 다른 canonical {cov['Q4_step27_known_now_different_canonical']}
- 비증상(EXT_EVAL weak-non {wn['n']}): STEP28 {S.dumps(wn['categories'])} · 증상으로 연결 {wn['linked_to_symptom(existing)']} · 신규 concept {wn['new_concept']} (STEP27 {S.dumps(wn['step27_categories'])})
- 내부 합성 문장(기존 증상 차단 여부): {S.dumps({k: {kk: vv for kk, vv in x.items() if kk != 'existing_wrong'} for k, x in I.items()})}
- 중복 통제: {S.dumps(cov['concept_duplication'])} · 미지원 처리: {S.dumps(uh)}

## 6. 속도·자원

{table([[k, x['p50_ms'], x['p95_ms'], x['max_ms']] for k, x in lt.items()], ['경로', 'p50 ms', 'p95 ms', 'max ms'])}

파이프라인 적재 {lat['pipeline_load_seconds']} s · RSS 적재 후 {lat['rss_after_load_mib']} MiB · peak {lat['peak_rss_mib']} MiB · 색인 {ib['index_bytes'] / 1e6:.1f} MB(SQLite, 요청마다 원본 순회 없음).

## 7. 평가 후 발견한 결함(사후 확인 — 규칙은 고치지 않음, 다음 단계 수정 대상)

- **비증상 → 증상 연결 증가**: EXT_EVAL weak-non {wn['n']} 중 STEP28 기존 증상 연결 {wn['linked_to_symptom(existing)']} (STEP27 자동수락 {wn['step27_categories'].get('KNOWN_SYMPTOM', 0)}). 근거별 {S.dumps(wn_reasons)}. 원인 후보: (a) 어휘 근거 lexical_support 가 '입력이 학습 문장 안에 들어 있음'을 허용 → 신체 부위 단독(어깨·허벅지·머리)·약 이름('기침 억제제')이 통과 (b) 통증 합성어 규칙이 질환명 안의 '두통'(혈관성 편두통·근긴장성 두통)에도 걸림 (c) weak label 잡음('흉통' 이 비증상 태그).
- **'통증' 단독 표현 손실**: STEP27 KNOWN → STEP28 비기존 {cov['Q4_step27_known_now_not_existing']} 입력, 근거별 {S.dumps(q4_reasons)}. 원인: 용어집 라벨을 '·' 로 나눌 때 EV:E_9('림프절(멍울) 부음·통증')에서 '통증' 조각이 생겨 pain 과 겹침(EXACT_TERM_MULTI).
- **제품 매퍼 구토→오심**: 내부 합성 문장 기존 연결 오답 {S.dumps({k: x['existing_wrong'] for k, x in I.items()})} — PRODUCT_ALIAS 경로가 제품 매퍼의 기존 오매핑(E_148)을 그대로 가져옴. '구토' 단독은 SOURCE_CONFLICT(UNCERTAIN).
- 위 결함을 Silver·EXT_EVAL 결과를 본 뒤 고치면 사후 조정이므로 이번 수치는 사전 고정 규칙 그대로다.

## 8. 재현성

{S.dumps(S.load_json(S.OUT / "reproducibility.json")) if (S.OUT / "reproducibility.json").exists() else "기록 없음"}

## 9. 답

1. **77개 제한에서 얼마나 벗어났나**: 한국어 입력 기준으로는 거의 못 벗어났다. 검증된 신규 concept 입력 {ver_inputs}/{n}. 대신 STEP27 이 UNKNOWN/UNCERTAIN 으로 남긴 표현 중 {cov['Q1_of_those_now_existing']} 개가 기존 concept·속성 조합(두통 → pain+머리 등)으로 회수됐다 — 이것은 77 밖 확장이 아니라 77 안 연결 개선이다.
2. **한국어 ↔ 영어 ontology 연결**: MedMap 자체 한국어 용어(기존 77)를 거쳐 STEP20 curated id 로 연결(경로 A/B)한 것만 근거가 있다. 로컬 SRL 0 한국어 자원은 검사명·약재명뿐이고, HPO·SNOMED International 에는 한국어가 없다. 로컬 xlm-roberta-base 는 gate {'통과' if fz['PATH_C_ENABLED'] else '미달'}(hit@5 {pct(fz['hit@k']['5'])}, 기존 증거 한국어 라벨 {fz['n_queries']}개 기준).
3. **찾은 새 concept**: 영어 색인·검증기에서는 Epistaxis(HP:0000421 · SNOMED 249366005)를 77 밖 concept 으로 찾고 객혈·토혈과 DISTINCT 로 구분했으며 기존 EV:E_178(비정상 출혈·멍)의 하위임을 기록했다. 그러나 한국어 '코피' → Epistaxis 를 잇는 로컬 허용 자원이 없어 한국어 입력에서는 연결하지 않았다(UNKNOWN 원문 보존).
4. **중복 처리**: 같은 id·같은 CUI 는 기존(DUPLICATE_OF_EXISTING), 속성 칸이 있는 기존 concept 의 하위는 기존+속성(Headache → pain+E_55), 속성 칸 없는 기존 concept 의 하위는 상위 연결을 기록한 신규 후보(Epistaxis → E_178 하위). 신규 id 의 77 충돌 {cov['concept_duplication']['new_id_collision_with_77']}.
5. **코피/객혈/토혈**: 객혈·토혈은 기존 concept(hemoptysis·hematemesis), 코피는 hemoptysis 후보 표시 없이 UNKNOWN/UNCERTAIN(§3). ontology 상 세 개념은 DISTINCT(§4).
6. **두통·발열**: 두통 = pain + 부위(머리), 발열 = fever(제품 alias + KoE 어휘 근거). STEP27 의 오분류(77 밖 검색 대상)를 정정.
7. **여전히 못 찾는 증상**: UNKNOWN {cat['UNKNOWN_SYMPTOM']} — 예: {', '.join(unk_ex[:20])}. 전부 한국어 연결 자원 부재(경로 D).
8. **기존 질환 모델에 바로 못 쓰는 이유**: 49질환 모델 입력은 DDXPlus 증거 223개 고정. 신규 concept 은 모델 feature 가 아니라 MODEL_SUPPORTED = False — 쓰려면 학습 데이터에 그 증상이 기록된 환자 표본과 재학습·재검증이 필요(이번 범위 밖).
9. **MedMap 연결에 필요한 것**: (a) 한국어 ↔ ontology 연결 자원 결정 — MDRKOR(MedDRA 한국어) 이용 조건 확인 또는 라이선스 확인된 한국어 의학 용어집 (b) 사람 검증 Gold(77 안/밖 라벨) (c) 제품 매퍼 구토→오심 오매핑 정리(SOURCE_CONFLICT 원인) (d) '목' 부위 모호성(인후통 vs 목 통증) 확인 질문 UX (e) PatientState 에 미지원 증상 원문 슬롯 설계(PRODUCT_INTEGRATION = HOLD).
10. **STEP29**: `docs/step29_handoff.md` — 문장 → 언급 span 분리 → 각 span 을 STEP28 Expansion 으로 정규화 + 부정·시점·주체 slot. 자동 실행하지 않음.
"""
    (S.DOCS / "step28_expansion_report.md").write_text(md, encoding="utf-8")
    files = sorted([p for p in S.DATA.glob("*") if p.is_file()] + [p for p in S.OUT.glob("*") if p.is_file() and p.name != "manifest.json"]
                   + list((S.STEP / "scripts").glob("*.py")) + list((S.STEP / "scripts").glob("*.sh")) + [S.STEP / "run_all.sh"] + list(S.DOCS.glob("*.md")))
    S.dump_json(S.OUT / "manifest.json", {"step": "STEP28_open_vocabulary_symptom_expansion", "verdict": {k: verdict[k] for k in list(verdict)[:7]},
                                          "files_sha256": {str(p.relative_to(S.STEP)): S.sha256(p) for p in files},
                                          "local_only_licensed": ["index/ontology_index.sqlite", "index/xlmr_hpo_embeddings.npz",
                                                                  "data/ontology_expansion_candidates.csv(UMLS/SNOMED 이름·정의)", "outputs/concept_relation_checks.json"],
                                          "public_ok_candidates": ["scripts/*", "docs/*(UMLS·SNOMED 문자열 최소 사례만)"],
                                          "inputs": insp["P1_input_sha256"]})
    print(S.dumps({k: verdict[k] for k in list(verdict)[:8]}), S.dumps(verdict["numbers"]))


if __name__ == "__main__":
    main()
