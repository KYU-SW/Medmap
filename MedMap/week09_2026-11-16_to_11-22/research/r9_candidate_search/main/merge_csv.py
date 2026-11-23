"""에이전트 CSV + 메인 확인 행 병합 -> 폴더 최상위 산출 CSV. 사용: python3 -I main/merge_csv.py
값을 새로 만들지 않는다. 메인 행은 이번 세션에서 메인이 직접 원문/API 로 확인한 내용만.
"""
import csv
import os

R = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def rd(p):
    with open(os.path.join(R, p), encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def wr(p, rows, extra):
    keys = list(rows[0].keys())
    for e in extra:
        for k in e:
            if k not in keys:
                keys.append(k)
    with open(os.path.join(R, p), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys + ["added_by"], restval="")
        w.writeheader()
        for r in rows:
            w.writerow(dict(r, added_by=r.get("added_by") or "agent"))
        for e in extra:
            w.writerow(dict(e, added_by="main"))


pain = rd("agentA/CLINICIAN_PAIN_EVIDENCE.csv")
wr("CLINICIAN_PAIN_EVIDENCE.csv", pain, [
    {"problem_id": "P02", "problem": "퇴원 후 도착하는 검사 결과", "who": "입원 담당의·1차 진료의·환자", "when": "퇴원 시점~결과 도착",
     "info_lost": "퇴원 시 미결 검사의 존재·결과", "harm": "조치 가능 결과 미인지",
     "source_title": "Patient safety concerns arising from test results that return after hospital discharge", "authors": "Roy CL, Poon EG, Karson AS, et al.",
     "year": "2005", "doi_url": "10.7326/0003-4819-143-2-200507190-00011", "evidence_level": "[초록] 메인 PubMed 확인",
     "quantitative_evidence": "2,644명 중 1,095명(41%) 퇴원 후 결과 2,033건; 조치 가능 191건(9.4%, 의사 검토자 판정); 응답 105건 중 의사 미인지 65건(61.6%)"},
])

pa = rd("agentB/PRIOR_ART_MATRIX.csv")
wr("PRIOR_ART_MATRIX.csv", pa, [
    {"candidate_area": "PG", "id": "M1", "title": "Identifying Imaging Follow-Up in Radiology Reports: A Comparative Analysis of Traditional ML and LLM Approaches",
     "authors": "Park N, Ramachandran GK, Lybarger K, Xia F, Uzuner O, Yetisgen M, Gunn M", "year": "2025 (LREC 2026)", "doi_or_url": "arXiv:2511.11867",
     "problem": "권고 후 실제 후속 영상 시행 판정(adherence)", "input": "지표 판독문 + 같은 환자 이후 판독문(+모달리티·일수 차이)",
     "output": "가장 이른 적격 후속 판독문", "method": "LR·SVM·Longformer·Llama3-8B·GPT-4o", "ground_truth_creator": "의대생 2인 + 영상의학 전문의 조정(IAA F1 0.846)",
     "eval_data": "단일 학술의료기관 비공개(7백만 판독문 DB에서 586명 6,393건), MIMIC 아님", "public_code": "자리표시자 링크(github.com/XXX)",
     "public_data": "공개 언급 없음", "reproducible": "아니오(데이터 비공개)", "limitations": "시간 창 없음, 단일 기관",
     "medmap_difference": "공개 MIMIC 재현·퇴원 기록 언급 여부·as-of 상태 분리 정도", "verification_level": "[본문] 메인 확인"},
    {"candidate_area": "PC", "id": "M2", "title": "EHRCon: Dataset for Checking Consistency between Unstructured Notes and Structured Tables in Electronic Health Records",
     "authors": "Kwon Y, Kim J, Lee G, Bae S, Kyung D, Cha W, Pollard T, Johnson A, Choi E", "year": "2024", "doi_or_url": "arXiv:2406.16341",
     "problem": "노트 언급 ↔ 구조화 표 일치 판정", "input": "MIMIC-III 노트 105건(퇴원·의사·간호) + 표", "output": "Consistent/Inconsistent",
     "method": "주석 + LLM 프레임워크 CheckEHR", "ground_truth_creator": "저자(연구자) 수작업, 임상 실무자는 지침 설계 참여",
     "eval_data": "MIMIC-III, 4,101 개체", "public_code": "github.com/dustn1259/EHRCon", "public_data": "PhysioNet 라이선스",
     "reproducible": "조건부(자격 인증)", "limitations": "시간 처리 = 명시 시각 정확 일치 또는 ±1일; 오래된 정보(stale)·복사 전달 라벨 없음",
     "medmap_difference": "작성 시점 이미 대체된 값(as-of 대체)·작성 후 확정 결과 구분", "verification_level": "[본문] 메인 확인(앞 100k자)"},
    {"candidate_area": "PB", "id": "M3", "title": "The Atoms of the Score: Record-Level versus In-Engine Composite Evaluation of Clinical Quality Language",
     "authors": "Kastroulis A", "year": "2026", "doi_or_url": "arXiv:2607.23619", "problem": "CQL 엔진 구조 성능 비교",
     "ground_truth_creator": "해당 없음", "eval_data": "Synthea 10만 명", "limitations": "LLM·변환 충실도·공식 테스트 대조 없음(성능 벤치마크)",
     "medmap_difference": "직접 경쟁 아님", "verification_level": "[초록] 메인 확인"},
    {"candidate_area": "PC", "id": "M4", "title": "A Living Benchmark for Information Retrieval from Electronic Health Records (BRIE)", "year": "2026", "doi_or_url": "arXiv:2609.30205",
     "problem": "H&P 시점 정보 검색, 복사 전달은 최신 언급만 유지해 처리", "limitations": "오래된 정보 탐지 자체는 목표 아님(검색 요약 기준)",
     "verification_level": "[검색요약] 메인"},
    {"candidate_area": "PC", "id": "M5", "title": "VeriFact: Verifying Facts in LLM-Generated Clinical Text with Electronic Health Records", "year": "2025", "doi_or_url": "arXiv:2501.16672",
     "problem": "생성 임상 문장 ↔ EHR 사실 검증", "limitations": "관련도 정렬에서 오래된 정보가 앞설 수 있음(저자 언급, 검색 요약 기준)", "verification_level": "[검색요약] 메인"},
    {"candidate_area": "PF/P02", "id": "M6", "title": "Improving Management of Test Results that Return After Hospital Discharge (AHRQ 과제)", "doi_or_url": "https://digital.ahrq.gov/ahrq-funded-projects/improving-management-test-results-return-after-hospital-discharge",
     "problem": "퇴원 시 미결 검사 자동 표시·퇴원 요약 삽입", "limitations": "운영 도구, 공개 재현 데이터 없음(검색 요약 기준)", "medmap_difference": "기능 자체는 선점; 차이는 공개 재현 감사뿐",
     "verification_level": "[검색요약] 메인"},
])

do = rd("agentC/DATA_ORACLE_FEASIBILITY.csv")
wr("DATA_ORACLE_FEASIBILITY.csv", do, [
    {"candidate_area": "PB", "dataset": "cqframework/ecqm-content-qicore-2024", "url": "https://github.com/cqframework/ecqm-content-qicore-2024",
     "access": "공개", "user_has": "아니오(다운로드 가능)", "oracle_type": "2(측정 개발자 작성 테스트 기대값)", "oracle_independent": "예(구현자와 독립)",
     "expert_needed": "아니오", "objective_eval_without_expert": "예", "reuse_ai_terms": "CC0-1.0",
     "notes": "메인 GitHub API 확인: license CC0-1.0, input/tests/measure 하위 항목 72(측정 폴더 71 + .DS_Store), 마지막 push 2026-05-13", "evidence_level": "[API] 메인"},
    {"candidate_area": "PC/P02", "dataset": "MIMIC-IV-Note 2.2 discharge (로컬)", "access": "자격 인증", "user_has": "예(1.1 GB, 사용 승인 필요)",
     "fields": "note_id,subject_id,hadm_id,note_type,note_seq,charttime,storetime,text", "event_times": "charttime·storetime",
     "oracle_type": "1(구조화 시각과 대조)", "oracle_independent": "시각은 예 / 노트 속 수치 추출은 아니오(4)",
     "notes": "메인 헤더만 확인(내용 미열람). MIMIC-IV-Note 는 날짜가 비식별 처리될 수 있음 — 노트 안 시각 고정 가능 비율은 실측 필요", "evidence_level": "[스키마] 메인"},
    {"candidate_area": "PC/P02", "dataset": "MIMIC-IV 3.1 hosp labevents·admissions (로컬)", "access": "자격 인증", "user_has": "예(사용 승인 필요)",
     "fields": "labevents: charttime,storetime,value,valuenum,flag,priority,comments / admissions: admittime,dischtime",
     "event_times": "채취(charttime)·결과 저장(storetime)·퇴원(dischtime)", "oracle_type": "1", "oracle_independent": "예",
     "notes": "메인 헤더만 확인", "evidence_level": "[스키마] 메인"},
])
print("merged")
