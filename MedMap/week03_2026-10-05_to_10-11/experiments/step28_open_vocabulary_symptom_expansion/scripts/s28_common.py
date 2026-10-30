"""STEP28 공통 — Open-Vocabulary Symptom Expansion(연구용 프로토타입). 기존 모델·정책·산출물·원본 ontology 는 읽기만 한다.

[자원 — 실제 경로·버전은 inspect_previous_steps.py 가 원본 메타데이터에서 읽어 기록]
 HPO      ~/medmap/data/hpo/hp.obo (data-version hp/releases/2026-09-01)                         SRL 해당 없음(HPO 라이선스, 로컬 연구용)
 SNOMED   ~/medmap/data/snomed/SnomedCT_InternationalRF2_PRODUCTION_20260901T120000Z (RF2 Snapshot) 라이선스 데이터 — 로컬 전용
 UMLS     ~/medmap/data/umls/2026AA/{META/MRCONSO.RRF, relations/MRSTY.RRF, MRSAB.RRF}           UTS 라이선스 — 로컬 전용
 한국어   MedMap 자체: STEP23 학습 표현 1,119 · STEP21 사전 294 · terminology_ko.json(증거 223·값 199·질환 49) ·
          제품 매퍼 aliases_ko.json(검증된 동의어, read-only 실행) · UMLS KOR 중 SRL 0 출처(LNC-KO-KR 검사명 · TKMT 약재명)
 제외     UMLS KOR 의 MDRKOR(MedDRA 한국어, SRL 3) · KCD5(SRL 3) — 이용 범위 확인 필요 → 기본 경로에서 쓰지 않음(사용자 결정 대기)
 다국어   로컬 캐시 xlm-roberta-base(신규 다운로드 없음) — 경로 C. 사전 고정 타당성 gate 를 통과할 때만 후보 생성에 사용.

[판정 순서 — 사전 고정(입력 1개당), 모든 범주에서 원문 보존]
 0 COMPLEX(STEP26 정규식) → UNCERTAIN(reason COMPLEX_INPUT, 단일 표현 정규화 범위 밖)
 1 EXISTING_COMPOSITE: 통증 형태소(통증·아프·아파·아픔·쑤시) 또는 부위 합성어(두통·흉통·복통·요통·치통 등) + 부위 → pain(E_53) + site(E_55 후보값)
   - '목' 단독 부위는 인후통(sore_throat)과 목 통증(pain+neck)이 갈려서 UNCERTAIN(후보 두 개 표시). 목구멍·인후·편도 → sore_throat 로 1 단계 처리.
 2 EXISTING_CANONICAL(EXACT_TERM): 조사 제거 stem 이 MedMap 한국어 용어(77 concept 의 학습 표현·사전·용어집 라벨) stem 과 같다(concept 1개일 때)
 3 EXISTING_CANONICAL(MODEL_AUTO): STEP27 POLICY_D 가 KNOWN
 4 EXISTING_CANONICAL(PRODUCT_ALIAS): 제품 매퍼가 POSITIVE 로 잡은 증거가 77 crosswalk 에 있음
   EXISTING_CANONICAL(MODEL_LEXICAL): KoE top1 conf ≥ T_KOE(0.9530, STEP24-v2 고정) AND 그 concept 에 한국어 어휘 근거(lexical_support)
   두 근거가 서로 다른 concept 이면 UNCERTAIN(후보 둘 다 표시, reason SOURCE_CONFLICT)
 5 NON_SYMPTOM: 제품 매퍼가 병력·노출 증거(77 crosswalk 밖, 예 E_104 고혈압 병력) · 49 질환 한국어 라벨 일치 · LNC-KO-KR 검사명/TKMT 약재명 일치 ·
   STEP27 POLICY_D NON(보수적 NON) 중 하나
 6 NEW_ONTOLOGY_CONCEPT: 한국어 → ontology 연결 근거가 있을 때만(경로 B/C). 후보는 validate_concept_candidates 로 검증, 미검증 후보는 표시하지 않음
 7 그 외: 증상 근거(STEP27 SYMPTOM_CUE 또는 p_non<0.5) → UNKNOWN_SYMPTOM(KOREAN_LINK_MISSING) · 없으면 UNCERTAIN
 표시 후보: EXISTING 결과의 canonical 과 1 단계 '목' 후보만. 영어 ontology 후보·모델 후보는 검증 전 표시 안 함(candidate_ids=[]).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
S27_DIR = REPO / "exp/step27_safe_symptom_routing"
sys.path.insert(0, str(S27_DIR / "scripts"))
import s27_common as S27  # noqa: E402

S26 = S27.S26
S23 = S27.S23
S20 = REPO / "exp/step20_symptom_ontology_audit"
S21 = REPO / "exp/step21_korean_symptom_entity_linking"
MAIN = Path.home() / "medmap"                      # 제품 저장소(master fb2d7f0) — 읽기만
ONT = MAIN / "data"
HPO_OBO = ONT / "hpo/hp.obo"
SCT_DIR = ONT / "snomed/SnomedCT_InternationalRF2_PRODUCTION_20260901T120000Z/Snapshot/Terminology"
UMLS_CONSO = ONT / "umls/2026AA/META/MRCONSO.RRF"
UMLS_STY = ONT / "umls/2026AA/relations/MRSTY.RRF"
UMLS_SAB = ONT / "umls/2026AA/relations/MRSAB.RRF"
TERMINOLOGY = MAIN / "medmap/data/terminology_ko.json"
XLMR = Path.home() / ".cache/huggingface/hub/models--xlm-roberta-base"

DATA, OUT, DOCS, LOGS = STEP / "data", STEP / "outputs", STEP / "docs", STEP / "logs"
INDEX = STEP / "index"            # LOCAL_ONLY_LICENSED — UMLS/SNOMED 문자열 포함, 공개 저장소 금지
for _d in (DATA, OUT, DOCS, LOGS, INDEX):
    _d.mkdir(exist_ok=True)
read_csv, write_csv, sha256, norm, nospace, rnd, load_json, dump_json, dumps = (S27.read_csv, S27.write_csv, S27.sha256, S27.norm, S27.nospace,
                                                                                S27.rnd, S27.load_json, S27.dump_json, S27.dumps)
stem_key, complex_flags, symptom_cue, non_type = S27.stem_key, S27.complex_flags, S27.symptom_cue, S27.non_type
T_KOE = S26.T_KOE
SRL_ALLOWED_KOR = ("LNC-KO-KR", "TKMT")       # SRL 0
SRL_EXCLUDED_KOR = ("MDRKOR", "KCD5")          # SRL 3 — 사용 안 함
UMLS_EN_SABS = ("HPO", "MTH", "MSH", "MEDLINEPLUS", "CHV", "NCI", "SNOMEDCT_US")
SYMPTOM_STY = {"T184", "T033"}                 # Sign or Symptom · Finding
DISEASE_STY = {"T047", "T191", "T019", "T020", "T037", "T048", "T049", "T050", "T190"}   # T046 Pathologic Function 은 출혈 등 증상도 포함 → 제외
ATTRIBUTE_SLOT_CONCEPTS = {"pain": "E_55(site)"}   # 하위 개념을 속성으로 표현할 수 있는 기존 concept
HPO_PHENO_ROOT = "HP:0000118"
SCT_FINDING_ROOT = "404684003"

# 1 단계 — 통증 부위(사전 고정 일반 해부 어휘. 값 후보는 terminology_ko.json E_55 V_* 한국어 라벨에서 부분 일치로 찾는다)
PAIN_COMPOUND = {"두통": "머리", "편두통": "머리", "흉통": "가슴", "복통": "배", "요통": "허리", "치통": "치아", "관절통": "관절",
                 "요추통": "허리", "위통": "윗배", "견통": "어깨", "경부통": "목", "안구통": "눈", "이통": "귀", "측복통": "옆구리"}
PAIN_MORPH = re.compile(r"(통증|아프|아파|아픔|아팠|쑤시|쑤셔|결리|욱신)")
SORE_THROAT_SITE = re.compile(r"(목구멍|인후|편도|목 안|목안)")
NECK_SITE = re.compile(r"(뒷목|목덜미|목뒤|목 뒤)")


def josa_strip(text: str) -> str:
    return stem_key(text)


def load_terminology():
    return json.loads(TERMINOLOGY.read_text(encoding="utf-8"))


def evidence_crosswalk() -> dict[str, str]:
    """DDXPlus evidence → MedMap canonical(77). STEP21 사전의 evidence_id·concept_id 쌍(일대일 확인)."""
    m = {}
    for r in read_csv(S21 / "data/dictionary_expressions.csv"):
        if r["evidence_id"]:
            assert m.get(r["evidence_id"], r["concept_id"]) == r["concept_id"]
            m[r["evidence_id"]] = r["concept_id"]
    return m


def body_parts() -> list[str]:
    """제품 매퍼 aliases_ko.json 의 BP 매크로(부위 어휘) — 긴 것 우선."""
    a = json.loads((MAIN / "medmap/intake/aliases_ko.json").read_text(encoding="utf-8"))
    bp = a["macros"]["BP"]
    inner = bp[bp.index(":") + 1: bp.rindex(")")]
    return sorted(inner.split("|"), key=len, reverse=True)
