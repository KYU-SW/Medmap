"""STEP25 데이터셋 인벤토리 + 구조 감사.

- CANDIDATES: 2026-10-10 조사한 후보 10개(근거 URL·확인 방법 포함). PUBLIC_DOWNLOAD 는 실제 다운로드가 성공한 것만.
- 로컬에 받은 3개(KBMC · BERT-NER-KO · ko_medical_chat)를 파싱해 문장 수, 라벨 체계, 정렬, 개인정보 패턴, 부정/시점 라벨 여부를 센다.
  원문 샘플은 출력하지 않는다(개인정보 패턴 개수만).
출력: data/dataset_inventory.csv · outputs/source_coverage.json · outputs/schema_audit.json
"""
import collections

import s25_common as S

CANDIDATES = [
    {"dataset": "AIHUB_208 의료진 및 환자 음성(비대면 진료)", "url": "https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=208",
     "access": "SAFEZONE_REQUIRED", "access_evidence": "페이지: 내국인만 신청, 보건의료 데이터는 온라인/오프라인 안심존 개방, IRB·소속 증빙·보안서약 필요",
     "total_reported": "환자 음성 45만 문장(Wave) · 환자 텍스트 15만 문장", "label_reported": "페이지에 증상 라벨 필드 명시 없음('증상별 환자 발화 수집'만)",
     "speaker": "환자 역할 화자(대화 응답 시나리오 동반 수집 = 스크립트 기반)", "license": "UNKNOWN(이용약관 별도, 안심존 반출 제한)", "downloaded": False},
    {"dataset": "AIHUB_98 민원(콜센터) 질의-응답", "url": "https://aihub.or.kr/aihubdata/data/view.do?dataSetSn=98",
     "access": "APPROVAL_REQUIRED", "access_evidence": "페이지: 다운로드 승인 완료 후 API 다운로드(로그인+신청)",
     "total_reported": "질병관리본부 251,031건 중 증상/징후 카테고리 50,634건", "label_reported": "도메인→카테고리 2계층(증상/징후 = 카테고리, 개별 증상 concept 아님)",
     "speaker": "상담사·고객(실제/가공 여부 페이지에 없음)", "license": "UNKNOWN(AI-Hub 이용약관)", "downloaded": False},
    {"dataset": "KBMC (SungJoo/KBMC)", "url": "https://huggingface.co/datasets/SungJoo/KBMC",
     "access": "PUBLIC_DOWNLOAD", "access_evidence": "HF revision 9cd99c0 KBMC.tsv 1.52MB 다운로드 성공(gated=False)",
     "total_reported": "6,150 문장", "label_reported": "NER Disease/Body/Treatment (Symptom 라벨 없음)", "speaker": "의료 설명문(환자 발화 아님)",
     "license": "Apache-2.0", "downloaded": True},
    {"dataset": "BERT-NER-KO diagnosis (labihem)", "url": "https://github.com/labihem/BERT-NER-KO",
     "access": "PUBLIC_DOWNLOAD", "access_evidence": "GitHub commit 42945ce data/diagnosis shuffle1 train+eval 다운로드 성공",
     "total_reported": "2,189 문장(논문 PMC7526093)", "label_reported": "NER ST(증상)/DS(질병)/BD(신체) — 증상 '범주' 라벨, concept ID 없음",
     "speaker": "네이버 지식iN 의사 답변(환자 발화 아님)", "license": "LICENSE_UNSPECIFIED(저장소 LICENSE 없음; 논문은 CC-BY 4.0) → 로컬 분석만, 재배포 금지",
     "downloaded": True},
    {"dataset": "ko_medical_chat (squarelike)", "url": "https://huggingface.co/datasets/squarelike/ko_medical_chat",
     "access": "PUBLIC_DOWNLOAD", "access_evidence": "HF revision 4e16369 HealthCareMagic json 4.67MB 다운로드 성공",
     "total_reported": "HealthCareMagic·MedText 변환 대화", "label_reported": "라벨 없음",
     "speaker": "GPT-3.5 가 영어 ChatDoctor/MedText 를 한국어 대화로 변환한 생성문(실제 한국어 환자 발화 아님)",
     "license": "HF 카드 license 없음 · GitHub 저장소 Apache-2.0 · 원 ChatDoctor 데이터 조건 별도", "downloaded": True},
    {"dataset": "MedGPT-5k-ko (mncai)", "url": "https://huggingface.co/datasets/mncai/MedGPT-5k-ko",
     "access": "LICENSE_RESTRICTED", "access_evidence": "HF 공개(2.38MB) 이나 GPL-3.0 · 영어 GenMedGPT(ChatGPT 생성) 번역 추정 → 미다운로드",
     "total_reported": "약 5k 대화", "label_reported": "라벨 없음", "speaker": "생성 대화", "license": "GPL-3.0", "downloaded": False},
    {"dataset": "KorMedMCQA (sean0042)", "url": "https://huggingface.co/datasets/sean0042/KorMedMCQA",
     "access": "LICENSE_RESTRICTED", "access_evidence": "HF 공개 · CC-BY-NC-2.0 · 면허시험 객관식 문항(환자 발화 아님) → 미다운로드",
     "total_reported": "7,469 문항", "label_reported": "정답 보기(증상 concept 라벨 아님)", "speaker": "시험 문항", "license": "CC-BY-NC-2.0", "downloaded": False},
    {"dataset": "한양대 한국어 증상 발화(ASK 2023, 전성원 외)", "url": "https://koreascience.kr/article/CFKO202319360814158.pdf",
     "access": "UNAVAILABLE", "access_evidence": "논문: 아산병원 증상 305개, 연구원 작성 학습 21,860 + 테스트 4,183 — 본문에 공개 위치·URL 없음",
     "total_reported": "26,043 발화(305 증상)", "label_reported": "증상 분류 라벨(305) — 공개 시 가장 적합", "speaker": "연구원 작성(환자 아님)",
     "license": "UNKNOWN", "downloaded": False},
    {"dataset": "AI-Hub 초거대AI 헬스케어 질의응답(미디어젠 컨소시엄)", "url": "https://aihub.or.kr",
     "access": "APPROVAL_REQUIRED", "access_evidence": "보도: 2024 상반기 AI-Hub 공개 예정 — 실제 dataSetSn·스키마 미확인. AI-Hub 다운로드는 로그인+승인",
     "total_reported": "2억 어절 이상(보도)", "label_reported": "UNKNOWN", "speaker": "UNKNOWN", "license": "UNKNOWN", "downloaded": False},
    {"dataset": "응급의료 한국어 음성대화 DB(서강대)", "url": "https://scholarworks.sogang.ac.kr/item/0c0fbceb-b7dd-4b87-bb8b-c28740442b21",
     "access": "UNKNOWN", "access_evidence": "논문 소개만 확인(166 대화·8시간 35분, 의료 코드 전사) — 배포 경로 미확인",
     "total_reported": "166 대화", "label_reported": "의료 정보 전사(종류 미확인)", "speaker": "응급 대화", "license": "UNKNOWN", "downloaded": False},
]


def main():
    kb, nk, kmc = S.load_kbmc(), S.load_bert_ner_ko(), S.load_ko_medical_chat()
    audit = {}
    # KBMC
    tagset = collections.Counter(t for r in kb for t in r["tags"])
    sp = collections.Counter(t for r in kb for t, _ in r["spans"])
    audit["KBMC"] = {"n_rows": len(kb), "n_unique_text": len({r["text"] for r in kb}), "n_misaligned": sum(not r["aligned"] for r in kb),
                     "tagset": dict(tagset), "span_counts": dict(sp), "has_symptom_label": False, "has_negation_label": False,
                     "has_temporality_label": False, "pii_pattern_rows": S.pii_counts([r["text"] for r in kb]),
                     "unique_disease_spans": len({x for r in kb for t, x in r["spans"] if t == "Disease"}),
                     "note": "Symptom 라벨 없음. '호흡 곤란'·'근육 통증' 같은 증상 표현도 Disease 로 태깅(헤더 직후 예시 행에서 확인)"}
    # BERT-NER-KO
    tagset = collections.Counter(t for r in nk for t in r["tags"])
    sp = collections.Counter(t for r in nk for t, _ in r["spans"])
    st = [x for r in nk for t, x in r["spans"] if t == "ST"]
    audit["BERT_NER_KO"] = {"n_rows_train_plus_eval": len(nk), "n_unique_text": len({r["text"] for r in nk}), "tagset": dict(tagset),
                            "span_counts": dict(sp), "n_ST_spans": len(st), "n_unique_ST_spans": len({S.nospace(x) for x in st}),
                            "has_symptom_label": "CATEGORY_ONLY(ST)", "has_concept_id": False, "has_negation_label": False,
                            "has_temporality_label": False, "pii_pattern_rows": S.pii_counts([r["text"] for r in nk])}
    # ko_medical_chat
    first = [r["client_turns"][0] for r in kmc if r["client_turns"]]
    audit["KO_MEDICAL_CHAT"] = {"n_dialogues": len(kmc), "n_client_turns": sum(len(r["client_turns"]) for r in kmc),
                                "n_first_client_turns": len(first), "n_unique_first_client_turns": len({S.nospace(x) for x in first}),
                                "mean_first_turn_chars": round(sum(len(x) for x in first) / max(1, len(first)), 1),
                                "has_any_label": False, "pii_pattern_rows": S.pii_counts(first),
                                "provenance": "GPT-3.5 변환 생성문"}
    S.dump_json(S.OUT / "schema_audit.json", audit)

    inv = []
    for c in CANDIDATES:
        key = {"KBMC (SungJoo/KBMC)": "KBMC", "BERT-NER-KO diagnosis (labihem)": "BERT_NER_KO", "ko_medical_chat (squarelike)": "KO_MEDICAL_CHAT"}.get(c["dataset"])
        a = audit.get(key, {})
        total = a.get("n_unique_text") or a.get("n_dialogues") or ""
        sym = (a.get("n_unique_ST_spans") if key == "BERT_NER_KO" else a.get("unique_disease_spans") if key == "KBMC"
               else a.get("n_unique_first_client_turns") if key == "KO_MEDICAL_CHAT" else "")
        inv.append({**c, "local_total": total, "local_symptom_relevant_units": sym,
                    "symptom_relevant_unit": {"BERT_NER_KO": "unique ST span", "KBMC": "unique Disease span(질병+증상 혼재)",
                                              "KO_MEDICAL_CHAT": "unique 첫 client 발화(라벨 없음)"}.get(key, ""),
                    "gold_mappable": 0 if c["downloaded"] else "NOT_ACCESSIBLE", "raw_path": str(S.RAW) if c["downloaded"] else ""})
    S.write_csv(S.DATA / "dataset_inventory.csv", inv)
    cov = {"n_candidates": len(CANDIDATES), "access_counts": dict(collections.Counter(c["access"] for c in CANDIDATES)),
           "downloaded": [c["dataset"] for c in CANDIDATES if c["downloaded"]],
           "download_total_bytes": sum(p.stat().st_size for p in S.RAW.rglob("*") if p.is_file()),
           "raw_files": {str(p.relative_to(S.RAW)): S.sha256(p) for p in sorted(S.RAW.rglob("*")) if p.is_file()},
           "audit": audit}
    S.dump_json(S.OUT / "source_coverage.json", cov)
    for k, v in audit.items():
        print(k, {kk: vv for kk, vv in v.items() if kk not in ("tagset",)})
    print("download_total_bytes", cov["download_total_bytes"], cov["access_counts"])


if __name__ == "__main__":
    main()
