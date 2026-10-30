"""STEP28.6 평가(정답 없음 — 정확도 계산 안 함, 탐색적). 규칙은 작성 결과를 보기 전에 고정(2026-10-11), 사후 변경은 '변경 기록'에 별도 기록.

신규 후보 등급(SILVER, 임상 검증 아님):
 G3_SILVER_AUDITED   : A·B 같은 신규 concept(AGREE) + HPO 정의 대비 감사 EXACT
 G2_SILVER_AGREED    : A·B 같은 신규 concept(AGREE), 감사 없음(SNOMED 전용 — 라이선스로 미전송) 또는 BROADER/NARROWER
 G1_SINGLE_AUTHOR    : 한 작성자만 신규 concept(다른 작성자 결과 없음·다름) — 후보 보존, 확정·표시 없음
 REJECTED            : 감사 RELATED_ONLY·WRONG → UNKNOWN 으로 되돌림(원문 보존)
 A·B 일치는 필요조건일 뿐(같은 오류 가능 — 사용자 조건 3).
지표: 영어 변환 수 · ontology 완전일치 연결 수 · 77 밖 신규 후보(입력·고유 concept, 등급별) · 한→영 연결률(STEP28.5 대비) · A·B 충돌 ·
 감사 WRONG/RELATED · 비증상 오매핑 위험(WEAKNON903 → EXISTING/NEW, 작성자별·최종) · 구별 위반(코피→객혈·토혈, 구토→오심, 오심·메스꺼움→구토) ·
 STEP28.5 와 기존 concept 이 다른 의미 충돌 · 실패 원인 · 처리 시간(대응표 조회 + ontology 조회, CPU) · LLM 사용량(정가 환산, 청구액 아님).
모드: 작성자 B 가 없으면(주간 한도) A 단독 탐색 지표를 따로 낸다(INTERIM).
출력: outputs/{linking_metrics.json, new_concept_candidates.csv, conflict_cases.csv, failure_analysis.csv, comparison_step28_5.csv, distinction_checks.csv, latency.json}
"""
from __future__ import annotations

import collections
import csv
import json
import time

import s286_common as S


def read_audit():
    out = {}
    man = {r["row"]: r for r in S.read_csv(S.DATA / "audit_manifest.csv")} if (S.DATA / "audit_manifest.csv").exists() else {}
    for f in sorted((S.WS / "out").glob("audit_c*.tsv")):
        with f.open(encoding="utf-8") as fh:
            for r in csv.DictReader(fh, delimiter="\t"):
                m = man.get((r.get("row") or "").strip())
                if m and (r.get("judgement") or "").strip() in S.AUDIT_LABELS:
                    out[(m["id"], m["concept_id"])] = (r["judgement"].strip(), (r.get("reason") or "").strip())
    status = {(m["id"], m["concept_id"]): m["audit_status"] for m in man.values()}
    return out, status


def violations(text, concepts):
    x = S.nospace(text)
    v = []
    if "코피" in x and {"hemoptysis", "hematemesis"} & set(concepts):
        v.append("EPISTAXIS_AS_HEMOPTYSIS/HEMATEMESIS")
    if ("구토" in x or "토하" in x or "토했" in x) and "nausea" in concepts and "vomiting" not in concepts:
        v.append("VOMITING_AS_NAUSEA")
    if any(t in x for t in ("메스꺼", "메스껍", "오심", "구역")) and "vomiting" in concepts and "nausea" not in concepts:
        v.append("NAUSEA_AS_VOMITING")
    return v


def main():
    L = S.read_csv(S.DATA / "ontology_links.csv")
    tab = S.read_csv(S.DATA / "silver_ko_en_table.csv")
    audit, astatus = read_audit()
    hasB = any(t["author"] == "B" for t in tab)
    rows = []
    for l in L:
        g, final_cat = "", l["final_cat"]
        cand_by = {w: l[f"{w}_concept"] for w in ("A", "B") if l[f"{w}_cat"] == "NEW_ONTOLOGY_CANDIDATE"}
        if final_cat == "NEW_ONTOLOGY_CANDIDATE":
            j = audit.get((l["id"], l["final_concept"]))
            if j and j[0] in ("RELATED_ONLY", "WRONG"):
                g, final_cat = "REJECTED", "UNKNOWN"
            elif j and j[0] == "EXACT":
                g = "G3_SILVER_AUDITED"
            else:
                g = "G2_SILVER_AGREED"
        elif cand_by:
            g = "G1_SINGLE_AUTHOR"
        rows.append({**l, "grade": g, "final_cat2": final_cat, "audit": S.dumps({c: audit.get((l["id"], c)) for c in cand_by.values()}),
                     "audit_status": S.dumps({c: astatus.get((l["id"], c)) for c in cand_by.values()})})
    # 신규 후보 표
    newc = []
    for r in rows:
        if not r["grade"]:
            continue
        for w in ("A", "B"):
            if r[f"{w}_cat"] == "NEW_ONTOLOGY_CANDIDATE":
                newc.append({"id": r["id"], "korean": r["korean"], "sources": r["sources"], "author": w, "english": r[f"{w}_english"], "concept_id": r[f"{w}_concept"],
                             "check": r[f"{w}_reason"], "grade": r["grade"], "audit": r["audit"], "audit_status": r["audit_status"],
                             "status": "NEW_ONTOLOGY_CANDIDATE(SILVER, 검증 전)", "model_supported": False})
    S.wcsv(S.OUT / "new_concept_candidates.csv", newc, ["id", "korean", "sources", "author", "english", "concept_id", "check", "grade", "audit", "audit_status",
                                                          "status", "model_supported"])
    conf = [r for r in rows if r["agreement"] == "CONFLICT"]
    S.wcsv(S.OUT / "conflict_cases.csv", conf, list(rows[0]) if rows else None)

    # STEP28.5 비교
    r285 = collections.defaultdict(list)
    for x in S.read_csv(S.S285_DIR / "data/retrieval_results.csv"):
        if x["mode"] == "PARALLEL":
            r285[x["input"]].append(x)
    wn285 = {x["text"]: x for x in S.read_csv(S.S285_DIR / "outputs/weak_non_risk.csv") if x["mode"] == "PARALLEL"}
    comp, sem_conf, dist = [], [], []
    for r in rows:
        if "SILVER442" in r["sources"]:
            prev = r285.get(r["korean"], [])
            pc = ";".join(p["category"] for p in prev)
            pcon = ";".join(p["concept"] for p in prev if p["concept"])
            comp.append({"id": r["id"], "korean": r["korean"], "step28_5_category": pc, "step28_5_concept": pcon, "step28_6_A": f"{r['A_cat']}:{r['A_concept']}",
                         "step28_6_B": f"{r['B_cat']}:{r['B_concept']}", "step28_6_final": f"{r['final_cat2']}:{r['final_concept']}", "grade": r["grade"]})
            for w in ("A", "B"):
                if r[f"{w}_cat"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE") and pcon and r[f"{w}_concept"] and r[f"{w}_concept"] not in pcon.split(";"):
                    sem_conf.append({"id": r["id"], "korean": r["korean"], "author": w, "step28_6_concept": r[f"{w}_concept"], "step28_5_concept": pcon})
        for w in ("A", "B"):
            cs = [r[f"{w}_concept"]] if r[f"{w}_concept"] else []
            for v in violations(r["korean"], cs):
                dist.append({"id": r["id"], "korean": r["korean"], "author": w, "concept": r[f"{w}_concept"], "violation": v})
    S.wcsv(S.OUT / "comparison_step28_5.csv", comp)
    S.wcsv(S.OUT / "semantic_conflicts_vs_step28_5.csv", sem_conf, ["id", "korean", "author", "step28_6_concept", "step28_5_concept"])
    S.wcsv(S.OUT / "distinction_checks.csv", dist, ["id", "korean", "author", "concept", "violation"])

    # 실패 원인(증상으로 보이나 연결 못 함)
    fa = []
    for r in rows:
        if r["final_cat2"] in ("UNKNOWN", "UNCERTAIN") and "SILVER442" in r["sources"]:
            code = ("AUDIT_REJECTED" if r["grade"] == "REJECTED" else "AUTHOR_CONFLICT" if r["agreement"] == "CONFLICT" else
                    "SINGLE_AUTHOR_ONLY" if r["agreement"] == "SINGLE" else
                    "LLM_NO_ENGLISH" if "NO_ENGLISH" in r["A_reason"] + r["B_reason"] else
                    "ONTOLOGY_NO_EXACT_MATCH" if "ONTOLOGY_NO_EXACT_MATCH" in r["A_reason"] + r["B_reason"] else
                    "SEMANTIC_TYPE_MISMATCH" if "SEMANTIC_TYPE_MISMATCH" in r["final_reason"] else r["final_reason"][:40])
            fa.append({"id": r["id"], "korean": r["korean"], "A_english": r["A_english"], "B_english": r["B_english"], "failure_code": code,
                       "A_reason": r["A_reason"], "B_reason": r["B_reason"]})
    S.wcsv(S.OUT / "failure_analysis.csv", fa, ["id", "korean", "A_english", "B_english", "failure_code", "A_reason", "B_reason"])

    def stats(sel, key):
        return dict(collections.Counter(r[key] for r in sel))
    sil = [r for r in rows if "SILVER442" in r["sources"]]
    wn = [r for r in rows if "WEAKNON903" in r["sources"]]

    def author_view(w, sel):
        conv = sum(1 for r in sel if r[f"{w}_english"])
        linked = sum(1 for r in sel if r[f"{w}_cat"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "NEW_ONTOLOGY_CANDIDATE"))
        new = [r for r in sel if r[f"{w}_cat"] == "NEW_ONTOLOGY_CANDIDATE"]
        return {"n": len(sel), "converted_to_english": conv, "linked_to_ontology_symptom": linked, "categories": stats(sel, f"{w}_cat"),
                "new_inputs": len(new), "new_distinct_concepts": len({r[f"{w}_concept"] for r in new})}
    llm = []
    for f in sorted((S.LOGS / "authoring").glob("*.result.json")):
        r = json.loads(f.read_text() or "{}")
        llm.append({"tag": f.stem.replace(".result", ""), "models": list((r.get("modelUsage") or {}).keys()), "list_price_usd": r.get("total_cost_usd"),
                    "duration_s": round((r.get("duration_ms") or 0) / 1000, 1), "output_tokens": sum(v.get("outputTokens", 0) for v in (r.get("modelUsage") or {}).values()),
                    "is_error": r.get("is_error"), "result": (r.get("result") or "")[:80]})
    S.wcsv(S.OUT / "llm_usage.csv", llm)
    met = {"mode": "FULL(A+B)" if hasB else "INTERIM(A only — 작성자 B 없음, 주간 한도)", "n_inputs_authored": len(rows),
           "by_source": {"SILVER442": len(sil), "WEAKNON903": len(wn), "SMOKE": sum("SMOKE" in r["sources"] for r in rows)},
           "author_A": {"silver": author_view("A", sil), "weaknon": author_view("A", wn)},
           "author_B": {"silver": author_view("B", sil), "weaknon": author_view("B", wn)} if hasB else None,
           "final(silver)": {"categories": stats(sil, "final_cat2"), "agreement": stats(sil, "agreement"), "grades": stats([r for r in sil if r["grade"]], "grade")},
           "new_distinct_concepts_by_grade": {g: len({c["concept_id"] for c in newc if c["grade"] == g}) for g in ("G3_SILVER_AUDITED", "G2_SILVER_AGREED", "G1_SINGLE_AUTHOR", "REJECTED")},
           "nonsymptom_mismapping_risk(weak-non)": {"A": sum(r["A_cat"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "NEW_ONTOLOGY_CANDIDATE") for r in wn),
                                                    "B": sum(r["B_cat"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "NEW_ONTOLOGY_CANDIDATE") for r in wn) if hasB else None,
                                                    "final": sum(r["final_cat2"] in ("EXISTING_CANONICAL", "EXISTING_COMPOSITE", "NEW_ONTOLOGY_CANDIDATE") for r in wn),
                                                    "n": len(wn), "step28_5_parallel_on_same_inputs": sum(1 for r in wn if wn285.get(r["korean"], {}).get("risk") == "True")},
           "ko_en_link_rate(silver)": {"step28_5_parallel": f"{sum(1 for r in sil if any(p['en_category'] and p['en_reason'] not in ('BILINGUAL_BRIDGE_MISSING', 'MODEL_CANDIDATE_ONLY') for p in r285.get(r['korean'], [])))}/{len(sil)}",
                                       "step28_6_A_exact_ontology": f"{author_view('A', sil)['linked_to_ontology_symptom']}/{len(sil)}"},
           "author_conflicts": len(conf), "semantic_conflicts_vs_step28_5": len(sem_conf), "distinction_violations": len(dist),
           "failure_codes(silver unresolved)": dict(collections.Counter(f["failure_code"] for f in fa)),
           "llm_list_price_usd_total(청구액 아님)": round(sum(x["list_price_usd"] or 0 for x in llm), 3), "llm_calls": len(llm)}
    # 처리 시간(런타임 = 대응표 조회 + ontology 조회·검증, LLM 생성은 오프라인 작성 단계)
    from link_english_to_ontology import Linker, read_author
    A, _ = read_author("A")
    lk = Linker()
    lk.fast = True
    texts = [r["id"] for r in sil][:300]
    same_cat = all(Linker().judge(A.get(i))["cat"] == lk.judge(A.get(i))["cat"] for i in texts[:300])
    lk.cache.clear()
    for i in texts[:20]:
        lk.judge(A.get(i))
    lk.cache.clear()
    ms = []
    for i in texts:
        t0 = time.perf_counter()
        lk.judge(A.get(i))
        ms.append((time.perf_counter() - t0) * 1000)
    ms.sort()
    lat = {"n": len(ms), "p50_ms": round(ms[len(ms) // 2], 3), "p95_ms": round(ms[int(round(0.95 * (len(ms) - 1)))], 3), "max_ms": round(ms[-1], 3),
           "note": "대응표에 있는 표현만 해당(조회+완전일치 검색+검증, 캐시 비움). 대응표에 없는 새 표현은 LLM 이 필요 — 병원 런타임 오프라인 원칙과 충돌",
           "llm_authoring_seconds_per_230_rows": [x["duration_s"] for x in llm if x["tag"].startswith("author")],
           "runtime_path_same_category_as_analysis_path": same_cat}
    S.dump_json(S.OUT / "latency.json", lat)
    met["latency"] = lat
    S.dump_json(S.OUT / "linking_metrics.json", met)
    print(S.dumps(met))


if __name__ == "__main__":
    main()
