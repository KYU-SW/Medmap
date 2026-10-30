"""EXP-00 데이터 접근 가능성 검사 (read-only).

원칙
  - 원본 파일은 읽기만 한다. 쓰기는 --out 경로 하나뿐.
  - MIMIC 계열: 헤더 + 앞쪽 소량 행의 '열 개수 일치'만 확인한다. 값·식별자·원문은 출력하지 않는다.
  - DDXPlus: train 은 집계(행 수·질환 수·근거 인코딩 형태)만. validate/test 는 열지 않는다
    (과거 이력: validate = STEP14~16A 반복 사용, test = STEP13B 1회 개봉 → 존재·크기만 기록).
  - UMLS·SNOMED: 라이선스 자료 → 파일 목록·행 수만, 문자열은 출력하지 않는다.
  - 봉인 폴더(사용자 제한 경로)는 접근하지 않는다.
사용: python check_data_access.py --out <json>
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import os
import sys
import time
import zipfile
from collections import Counter
from pathlib import Path

csv.field_size_limit(sys.maxsize)

MEDMAP_DATA = Path("/home/<user>/medmap/data")
DL = Path("/mnt/c/Users/<user>/Downloads")
MIMIC_RAW = DL / "mimic_raw"
SAMPLE_ROWS = 50


def fsize(p: Path):
    try:
        return p.stat().st_size
    except OSError:
        return None


def dir_size(p: Path):
    total = 0
    for root, _, files in os.walk(p):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def csv_probe(fh, n=SAMPLE_ROWS):
    """헤더와 앞쪽 n 행의 열 개수 일치만 본다. 값은 반환하지 않는다."""
    reader = csv.reader(fh)
    header = next(reader)
    widths = Counter()
    rows = 0
    for row in reader:
        widths[len(row)] += 1
        rows += 1
        if rows >= n:
            break
    return {"columns": header, "n_columns": len(header), "sample_rows_parsed": rows,
            "sample_width_consistent": set(widths) <= {len(header)} and rows > 0}


def probe_gz_csv(p: Path):
    rec = {"path": str(p), "exists": p.exists(), "size_bytes": fsize(p)}
    if not p.exists():
        return rec
    try:
        with gzip.open(p, "rt", encoding="utf-8", newline="") as fh:
            rec.update(csv_probe(fh))
        rec["readable"] = True
    except Exception as e:  # noqa: BLE001
        rec["readable"] = False
        rec["error"] = type(e).__name__
    return rec


def probe_plain_csv(p: Path):
    rec = {"path": str(p), "exists": p.exists(), "size_bytes": fsize(p)}
    if not p.exists():
        return rec
    try:
        with open(p, encoding="utf-8", newline="") as fh:
            rec.update(csv_probe(fh))
        rec["readable"] = True
    except Exception as e:  # noqa: BLE001
        rec["readable"] = False
        rec["error"] = type(e).__name__
    return rec


def probe_zip(p: Path):
    rec = {"path": str(p), "exists": p.exists(), "size_bytes": fsize(p)}
    if not p.exists():
        return rec
    try:
        with zipfile.ZipFile(p) as z:
            members = []
            for info in z.infolist():
                m = {"name": info.filename, "size_bytes": info.file_size}
                low = info.filename.lower()
                if low.endswith(".csv") or low.endswith(".csv.gz"):
                    with z.open(info) as raw:
                        stream = gzip.open(raw, "rt", encoding="utf-8", newline="") if low.endswith(".gz") \
                            else io.TextIOWrapper(raw, encoding="utf-8", newline="")
                        try:
                            m.update(csv_probe(stream))
                        except Exception as e:  # noqa: BLE001
                            m["error"] = type(e).__name__
                members.append(m)
        rec["readable"] = True
        rec["members"] = members
    except Exception as e:  # noqa: BLE001
        rec["readable"] = False
        rec["error"] = type(e).__name__
    return rec


def count_lines(p: Path):
    n = 0
    with open(p, "rb") as fh:
        for _ in fh:
            n += 1
    return n


# ---------------------------------------------------------------- DDXPlus
def audit_ddxplus():
    base = MEDMAP_DATA / "ddxplus" / "en"
    out = {"base": str(base)}
    ev = json.load(open(base / "release_evidences.json", encoding="utf-8"))
    dt = Counter(v["data_type"] for v in ev.values())
    out["evidences"] = {
        "n_total": len(ev),
        "data_type_counts": dict(dt),            # B=binary, C=categorical, M=multi
        "n_antecedent": sum(1 for v in ev.values() if v.get("is_antecedent")),
        "n_symptom": sum(1 for v in ev.values() if not v.get("is_antecedent")),
        "n_with_default_value": sum(1 for v in ev.values() if v.get("default_value") not in (None, "")),
        "fields": sorted(next(iter(ev.values())).keys()),
    }
    cond = json.load(open(base / "release_conditions.json", encoding="utf-8"))
    sev = Counter(str(v.get("severity")) for v in cond.values())
    out["conditions"] = {
        "n_total": len(cond),
        "fields": sorted(next(iter(cond.values())).keys()),
        "severity_counts": dict(sorted(sev.items())),
        "n_with_icd10": sum(1 for v in cond.values() if v.get("icd10-id")),
        "mean_symptoms_per_condition": round(sum(len(v.get("symptoms", {})) for v in cond.values()) / len(cond), 2),
        "mean_antecedents_per_condition": round(sum(len(v.get("antecedents", {})) for v in cond.values()) / len(cond), 2),
        "note": "simulator knowledge base — DDXPlus 환자는 이 표로 생성됨(그래프 지식원으로 쓰면 순환 위험)",
    }
    # train: 전체 집계(합성 데이터, 개인정보 없음)
    p = base / "release_train_patients"
    t0 = time.time()
    rows = 0
    path_counter = Counter()
    n_ev = []
    enc = Counter()
    has_ddx = 0
    with open(p, encoding="utf-8", newline="") as fh:
        r = csv.DictReader(fh)
        cols = r.fieldnames
        for row in r:
            rows += 1
            path_counter[row["PATHOLOGY"]] += 1
            evs = eval_list(row["EVIDENCES"])
            n_ev.append(len(evs))
            for e in evs:
                enc["value_coded(E_x_@_V)" if "_@_" in e else "binary_present"] += 1
            if row.get("DIFFERENTIAL_DIAGNOSIS", "").strip() not in ("", "[]"):
                has_ddx += 1
    n_ev.sort()
    out["train"] = {
        "path": str(p), "size_bytes": fsize(p), "columns": cols, "rows": rows,
        "n_pathologies": len(path_counter),
        "min_class_rows": min(path_counter.values()), "max_class_rows": max(path_counter.values()),
        "evidence_tokens": dict(enc),
        "evidences_per_patient_median": n_ev[len(n_ev) // 2],
        "evidences_per_patient_p05": n_ev[int(len(n_ev) * 0.05)],
        "evidences_per_patient_p95": n_ev[int(len(n_ev) * 0.95)],
        "rows_with_differential": has_ddx,
        "explicit_negative_token": False,  # EVIDENCES 에는 양성/값만 기록됨 → 음성은 '미기재' 로만 추론
        "seconds": round(time.time() - t0, 1),
    }
    for split in ("release_validate_patients", "release_test_patients"):
        q = base / split
        out[split] = {"path": str(q), "exists": q.exists(), "size_bytes": fsize(q),
                      "opened": False, "reason": "과거 사용 이력 보호(validate 반복 사용, test 1회 개봉) — 이번 감사에서 열지 않음"}
    out["fr_copy_exists"] = (MEDMAP_DATA / "ddxplus" / "fr").exists()
    return out


def eval_list(s: str):
    s = s.strip()
    if not s or s == "[]":
        return []
    return [x.strip().strip("'\"") for x in s.strip("[]").split(",") if x.strip()]


# ---------------------------------------------------------------- MIMIC
def audit_mimic():
    out = {}
    hosp = MIMIC_RAW / "mimiciv_3.1" / "hosp"
    out["mimic_iv_3.1_hosp_present_files"] = sorted(x.name for x in hosp.iterdir()) if hosp.exists() else []
    for name in ("patients", "admissions", "d_labitems", "labevents"):
        out[f"hosp/{name}"] = probe_gz_csv(hosp / f"{name}.csv.gz")
    for name in ("diagnoses_icd", "d_icd_diagnoses", "procedures_icd", "prescriptions", "microbiologyevents"):
        out[f"hosp/{name}"] = {"exists": (hosp / f"{name}.csv.gz").exists()}
    out["mimic_iv_sha_list_present"] = (MIMIC_RAW / "mimiciv_3.1_SHA256SUMS.txt").exists()
    note = MIMIC_RAW / "mimic-iv-note_2.2" / "note"
    out["note_present_files"] = sorted(x.name for x in note.iterdir()) if note.exists() else []
    for name in ("radiology", "radiology_detail"):
        out[f"note/{name}"] = probe_gz_csv(note / f"{name}.csv.gz")
    out["note/discharge"] = {"exists": (note / "discharge.csv.gz").exists()}
    ecg = MIMIC_RAW / "mimic-iv-ecg_1.0"
    for name in ("record_list", "machine_measurements"):
        out[f"ecg/{name}"] = probe_plain_csv(ecg / f"{name}.csv")
    out["ecg/waveforms_present"] = any(ecg.glob("files")) if ecg.exists() else False
    for z in ("mimic-iv-ed-2.2.zip", "mimic-iv-ecg-ext-icd-diagnostic-labels-for-mimic-iv-ecg-1.0.1.zip",
              "mimic-iv-ext-cardiac-disease-1.0.0.zip"):
        out[z] = probe_zip(DL / z)
    return out


# ---------------------------------------------------------------- ontology / KG
def audit_ontology():
    out = {}
    hpo = MEDMAP_DATA / "hpo"
    try:
        hj = json.load(open(hpo / "hp.json", encoding="utf-8"))
        g = hj["graphs"][0]
        out["hpo"] = {"path": str(hpo), "size_bytes": dir_size(hpo), "readable": True,
                      "n_nodes": len(g.get("nodes", [])), "n_edges": len(g.get("edges", [])),
                      "version": g.get("meta", {}).get("version"),
                      "phenotype_hpoa_lines": count_lines(hpo / "phenotype.hpoa")}
    except Exception as e:  # noqa: BLE001
        out["hpo"] = {"path": str(hpo), "readable": False, "error": type(e).__name__}

    umls = MEDMAP_DATA / "umls"
    meta = umls / "2026AA" / "META"
    out["umls"] = {"path": str(umls), "size_bytes": dir_size(umls), "version_dir": "2026AA",
                   "meta_files": sorted(x.name for x in meta.iterdir()) if meta.exists() else [],
                   "mrconso_eng_parquet": (umls / "mrconso_eng.parquet").exists(),
                   "license": "UMLS Metathesaurus License — 문자열 외부 전송·공개 push 금지"}
    sn = next(iter((MEDMAP_DATA / "snomed").glob("SnomedCT_*/Snapshot/Terminology")), None)
    if sn:
        c = sn / "sct2_Concept_Snapshot_INT_20260901.txt"
        r = sn / "sct2_Relationship_Snapshot_INT_20260901.txt"
        out["snomed"] = {"path": str(sn), "release": "INT 20260901", "readable": True,
                         "concept_rows": count_lines(c) - 1, "relationship_rows": count_lines(r) - 1,
                         "license": "SNOMED CT Affiliate — 문자열 외부 전송·공개 push 금지"}
    else:
        out["snomed"] = {"readable": False}

    others = {}
    for name in ("hsdn", "optimuskg", "dismech", "disease_profiles", "disease_profiles_v2",
                 "medline_disease_symptom", "wikidata", "cde"):
        p = MEDMAP_DATA / name
        others[name] = {"path": str(p), "exists": p.exists(), "size_bytes": dir_size(p) if p.exists() else None}
    try:
        import pyarrow.parquet as pq
        e = pq.ParquetFile(MEDMAP_DATA / "hsdn" / "processed" / "hsdn_edges_mesh.parquet")
        others["hsdn"]["edges_rows"] = e.metadata.num_rows
        others["hsdn"]["edges_columns"] = e.schema_arrow.names
        n = pq.ParquetFile(MEDMAP_DATA / "optimuskg" / "gold" / "nodes.parquet")
        ed = pq.ParquetFile(MEDMAP_DATA / "optimuskg" / "gold" / "edges.parquet")
        others["optimuskg"].update({"nodes_rows": n.metadata.num_rows, "edges_rows": ed.metadata.num_rows,
                                    "nodes_columns": n.schema_arrow.names, "edges_columns": ed.schema_arrow.names})
    except Exception as e:  # noqa: BLE001
        others["parquet_error"] = type(e).__name__
    out["other_kg_sources"] = others
    return out


# ---------------------------------------------------------------- 추가 공개 데이터
def audit_missing():
    names = {
        "MIMIC-IV-Ext-DiReCT": ["*direct*", "*DiReCT*"],
        "MIMIC-IV-Ext-PE": ["*ext-pe*", "*Ext-PE*"],
        "MIMIC-IV-ED": ["mimic-iv-ed*"],
        "MIMIC-IV-Ext-Note-Extract": ["*note*extract*"],
        "EHRNote-ChatQA": ["*ehrnote*", "*EHRNote*"],
    }
    roots = [DL, MIMIC_RAW, MEDMAP_DATA]
    out = {}
    for k, pats in names.items():
        hits = []
        for r in roots:
            for pat in pats:
                hits += [str(x) for x in r.glob(pat)]
        out[k] = {"local_hits": sorted(set(hits)), "present": bool(hits)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    t0 = time.time()
    report = {"schema": "exp00-data-access-v1", "started": time.strftime("%Y-%m-%d %H:%M:%S")}
    for key, fn in (("ddxplus", audit_ddxplus), ("mimic", audit_mimic), ("ontology", audit_ontology),
                    ("additional_public", audit_missing)):
        s = time.time()
        try:
            report[key] = fn()
        except Exception as e:  # noqa: BLE001
            report[key] = {"error": f"{type(e).__name__}: {e}"}
        print(f"[{key}] {time.time() - s:.1f}s", flush=True)
    report["elapsed_seconds"] = round(time.time() - t0, 1)
    out = Path(a.out)
    tmp = out.with_suffix(".tmp")
    tmp.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    json.loads(tmp.read_text(encoding="utf-8"))
    tmp.replace(out)
    print(f"END rc=0 elapsed={report['elapsed_seconds']}s out={out}", flush=True)


if __name__ == "__main__":
    main()
