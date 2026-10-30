# STEP25 — 외부 데이터 접근 보고 (2026-10-10 조사)

후보 10개 · 접근 상태 {"SAFEZONE_REQUIRED": 1, "APPROVAL_REQUIRED": 2, "PUBLIC_DOWNLOAD": 3, "LICENSE_RESTRICTED": 2, "UNAVAILABLE": 1, "UNKNOWN": 1} · 실제 다운로드 3개, 총 6.68 MB(한도 100 MB).
PUBLIC_DOWNLOAD 는 실제 다운로드가 성공한 경우만 표기. 로그인·신청 자동 시도 없음. 원본은 git 밖 `~/medmap_external_data/step25/raw/`.

| dataset | access | access_evidence | total_reported | label_reported | speaker | license | downloaded |
|---|---|---|---|---|---|---|---|
| AIHUB_208 의료진 및 환자 음성(비대면 진료) | SAFEZONE_REQUIRED | 페이지: 내국인만 신청, 보건의료 데이터는 온라인/오프라인 안심존 개방, IRB·소속 증빙·보안서약 필요 | 환자 음성 45만 문장(Wave) · 환자 텍스트 15만 문장 | 페이지에 증상 라벨 필드 명시 없음('증상별 환자 발화 수집'만) | 환자 역할 화자(대화 응답 시나리오 동반 수집 = 스크립트 기반) | UNKNOWN(이용약관 별도, 안심존 반출 제한) | False |
| AIHUB_98 민원(콜센터) 질의-응답 | APPROVAL_REQUIRED | 페이지: 다운로드 승인 완료 후 API 다운로드(로그인+신청) | 질병관리본부 251,031건 중 증상/징후 카테고리 50,634건 | 도메인→카테고리 2계층(증상/징후 = 카테고리, 개별 증상 concept 아님) | 상담사·고객(실제/가공 여부 페이지에 없음) | UNKNOWN(AI-Hub 이용약관) | False |
| KBMC (SungJoo/KBMC) | PUBLIC_DOWNLOAD | HF revision 9cd99c0 KBMC.tsv 1.52MB 다운로드 성공(gated=False) | 6,150 문장 | NER Disease/Body/Treatment (Symptom 라벨 없음) | 의료 설명문(환자 발화 아님) | Apache-2.0 | True |
| BERT-NER-KO diagnosis (labihem) | PUBLIC_DOWNLOAD | GitHub commit 42945ce data/diagnosis shuffle1 train+eval 다운로드 성공 | 2,189 문장(논문 PMC7526093) | NER ST(증상)/DS(질병)/BD(신체) — 증상 '범주' 라벨, concept ID 없음 | 네이버 지식iN 의사 답변(환자 발화 아님) | LICENSE_UNSPECIFIED(저장소 LICENSE 없음; 논문은 CC-BY 4.0) → 로컬 분석만, 재배포 금지 | True |
| ko_medical_chat (squarelike) | PUBLIC_DOWNLOAD | HF revision 4e16369 HealthCareMagic json 4.67MB 다운로드 성공 | HealthCareMagic·MedText 변환 대화 | 라벨 없음 | GPT-3.5 가 영어 ChatDoctor/MedText 를 한국어 대화로 변환한 생성문(실제 한국어 환자 발화 아님) | HF 카드 license 없음 · GitHub 저장소 Apache-2.0 · 원 ChatDoctor 데이터 조건 별도 | True |
| MedGPT-5k-ko (mncai) | LICENSE_RESTRICTED | HF 공개(2.38MB) 이나 GPL-3.0 · 영어 GenMedGPT(ChatGPT 생성) 번역 추정 → 미다운로드 | 약 5k 대화 | 라벨 없음 | 생성 대화 | GPL-3.0 | False |
| KorMedMCQA (sean0042) | LICENSE_RESTRICTED | HF 공개 · CC-BY-NC-2.0 · 면허시험 객관식 문항(환자 발화 아님) → 미다운로드 | 7,469 문항 | 정답 보기(증상 concept 라벨 아님) | 시험 문항 | CC-BY-NC-2.0 | False |
| 한양대 한국어 증상 발화(ASK 2023, 전성원 외) | UNAVAILABLE | 논문: 아산병원 증상 305개, 연구원 작성 학습 21,860 + 테스트 4,183 — 본문에 공개 위치·URL 없음 | 26,043 발화(305 증상) | 증상 분류 라벨(305) — 공개 시 가장 적합 | 연구원 작성(환자 아님) | UNKNOWN | False |
| AI-Hub 초거대AI 헬스케어 질의응답(미디어젠 컨소시엄) | APPROVAL_REQUIRED | 보도: 2024 상반기 AI-Hub 공개 예정 — 실제 dataSetSn·스키마 미확인. AI-Hub 다운로드는 로그인+승인 | 2억 어절 이상(보도) | UNKNOWN | UNKNOWN | UNKNOWN | False |
| 응급의료 한국어 음성대화 DB(서강대) | UNKNOWN | 논문 소개만 확인(166 대화·8시간 35분, 의료 코드 전사) — 배포 경로 미확인 | 166 대화 | 의료 정보 전사(종류 미확인) | 응급 대화 | UNKNOWN | False |

## 다운로드 파일 SHA256

| file | sha256 |
|---|---|
| bert_ner_ko/eval_diagnosis_shuffle1.txt | d7f90c50e10cb421c68c593621ad86f218cd078371015595a796604e76797c9d |
| bert_ner_ko/train_diagnosis_shuffle1.txt | 609c4105e0468fc024607bb956525f08cd3a20fa91df6553b754b8f98f38bbe7 |
| kbmc/KBMC.tsv | 075cf4384654b5777c5f615f55d59c3af04692d806d1f5aa22b9922b79bd3ce1 |
| kbmc/README.md | dd8b173f2973d95c444da5a9333fd06276600eba878f6b7f00d6b0ac85815306 |
| ko_medical_chat/medical_conversation_HealthCareMagic.json | e2657fb8cf31e5f554716ae4a93182c46f89dccbf36c349d1a4dbc6e8af3ef59 |

## 사용자 승인이 필요한 경로
- AIHUB_208: 내국인 신청 + 안심존 + IRB·소속·보안서약 → 사용자가 직접 신청해야 함(자동 신청 금지). 승인돼도 원본 반출 제한 가능.
- AIHUB_98: AI-Hub 로그인 + 다운로드 신청 승인 → 사용자 계정으로만 가능. '증상/징후'는 카테고리 단위.
- 한양대 증상 발화(305 증상): 공개 위치 없음 → 저자 문의만 가능(이번 단계에서 연락하지 않음).
