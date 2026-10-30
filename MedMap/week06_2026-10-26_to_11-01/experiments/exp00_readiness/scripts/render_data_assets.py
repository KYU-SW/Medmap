"""data_access_report.json → data_assets_generated.md (숫자는 전부 JSON 에서 생성, 손으로 쓰지 않음).
사용: python render_data_assets.py --report <json> --out <md>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def gb(n):
    return "-" if n is None else (f"{n / 1e9:.2f} GB" if n >= 1e8 else f"{n / 1e6:.1f} MB")


def yn(b):
    return "있음" if b else "없음"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    d = json.loads(Path(a.report).read_text(encoding="utf-8"))
    L = [f"# 데이터 자산 표(자동 생성)", "",
         f"- 원본: `{a.report}` (schema `{d['schema']}`, 실행 {d['started']}, {d['elapsed_seconds']} s)",
         "- MIMIC 계열은 헤더 + 앞쪽 소량 행의 열 개수 일치만 확인. 값·식별자·원문 출력 없음.", ""]

    x = d["ddxplus"]
    ev, co, tr = x["evidences"], x["conditions"], x["train"]
    L += ["## A. DDXPlus (합성 환자, CC-BY)", "",
          "| 항목 | 값 |", "|---|---|",
          f"| 경로 | `{x['base']}` |",
          f"| 질환 수(conditions.json) | {co['n_total']} (ICD-10 있음 {co['n_with_icd10']}) |",
          f"| severity 분포 | {co['severity_counts']} |",
          f"| 근거 수(evidences.json) | {ev['n_total']} = 증상 {ev['n_symptom']} + 과거력 {ev['n_antecedent']} |",
          f"| 근거 형식 | {ev['data_type_counts']} (B=이진, C=범주, M=다중) |",
          f"| 질환별 평균 증상·과거력 | {co['mean_symptoms_per_condition']} · {co['mean_antecedents_per_condition']} |",
          f"| train 행 / 크기 | {tr['rows']:,} / {gb(tr['size_bytes'])} |",
          f"| train 열 | {', '.join(tr['columns'])} |",
          f"| train 질환 수 / 클래스 최소·최대 행 | {tr['n_pathologies']} / {tr['min_class_rows']:,} · {tr['max_class_rows']:,} |",
          f"| 환자당 근거 수 중앙값(p05–p95) | {tr['evidences_per_patient_median']} ({tr['evidences_per_patient_p05']}–{tr['evidences_per_patient_p95']}) |",
          f"| 근거 토큰 | {tr['evidence_tokens']} |",
          f"| DIFFERENTIAL_DIAGNOSIS 있는 행 | {tr['rows_with_differential']:,} |",
          f"| 명시적 음성 토큰 | {yn(tr['explicit_negative_token'])} — 음성은 '기재 없음'으로만 추론 |"]
    for s in ("release_validate_patients", "release_test_patients"):
        v = x[s]
        L.append(f"| {s} | 존재 {yn(v['exists'])}, {gb(v['size_bytes'])}, 이번 감사에서 열지 않음 |")
    L.append("")

    m = d["mimic"]
    L += ["## B·C. MIMIC-IV 3.1 hosp · Note 2.2 · ECG · ED (PhysioNet credentialed DUA)", "",
          "| 파일 | 존재 | 크기 | 읽기 | 열 수 | 표본 열 일치 | 주요 열 |", "|---|---|---|---|---|---|---|"]
    for k, v in m.items():
        if not isinstance(v, dict) or "members" in v:
            continue
        cols = v.get("columns")
        L.append(f"| {k} | {yn(v.get('exists'))} | {gb(v.get('size_bytes'))} | {v.get('readable', '-')} | "
                 f"{v.get('n_columns', '-')} | {v.get('sample_width_consistent', '-')} | "
                 f"{', '.join(cols) if cols else '-'} |")
    L.append(f"| ecg/waveforms | {yn(m.get('ecg/waveforms_present'))} | - | - | - | - | - |")
    L.append("")
    for k, v in m.items():
        if isinstance(v, dict) and "members" in v:
            L += [f"### `{k}` ({gb(v['size_bytes'])}, 읽기 {v['readable']})", "",
                  "| 멤버 | 열 수 | 표본 열 일치 | 열 |", "|---|---|---|---|"]
            for mm in v["members"]:
                if "columns" in mm:
                    L.append(f"| {mm['name']} | {mm['n_columns']} | {mm['sample_width_consistent']} | {', '.join(mm['columns'])} |")
            L.append("")
    L.append(f"- hosp 실제 보유 파일: {', '.join(m['mimic_iv_3.1_hosp_present_files'])}")
    L.append(f"- note 실제 보유 파일: {', '.join(m['note_present_files'])}")
    L.append("")

    o = d["ontology"]
    h, u, s = o["hpo"], o["umls"], o["snomed"]
    L += ["## D. 의료 온톨로지·지식 그래프", "",
          "| 자원 | 상태 |", "|---|---|",
          f"| HPO | 읽기 {h['readable']}, 노드 {h['n_nodes']:,}, is_a 간선 {h['n_edges']:,}, phenotype.hpoa {h['phenotype_hpoa_lines']:,}줄, `{h['version']}` |",
          f"| UMLS {u['version_dir']} | {gb(u['size_bytes'])}, META: {', '.join(u['meta_files'])}, mrconso_eng.parquet {yn(u['mrconso_eng_parquet'])} — {u['license']} |",
          f"| SNOMED CT {s.get('release')} | concept {s.get('concept_rows', 0):,}행, relationship {s.get('relationship_rows', 0):,}행 — {s.get('license')} |"]
    for k, v in o["other_kg_sources"].items():
        if not isinstance(v, dict):
            continue
        extra = ""
        if "edges_rows" in v:
            extra = f", 간선 {v['edges_rows']:,}"
        if "nodes_rows" in v:
            extra += f", 노드 {v['nodes_rows']:,}"
        L.append(f"| {k} | 존재 {yn(v['exists'])}, {gb(v['size_bytes'])}{extra} |")
    L.append("")

    L += ["## E. 추가 공개 데이터(로컬 검색 결과)", "", "| 데이터 | 로컬 보유 | 위치 |", "|---|---|---|"]
    for k, v in d["additional_public"].items():
        L.append(f"| {k} | {yn(v['present'])} | {', '.join(v['local_hits']) or '-'} |")
    Path(a.out).write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
