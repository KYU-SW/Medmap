"""STEP27 공통 — Safe Symptom Routing v2(실험용). STEP23–26 산출물·모델은 읽기만 한다(재학습·덮어쓰기 없음).

재사용(고정): LINEAR_CHAR(STEP23 EXPANDED) · KoELECTRA-small(STEP24-v2 seed42, CPU) · Hybrid B · B4{a 0.0, b 0.98, s 0.6}
             · STEP26 비증상 점수 분류기(models/status_classifier.joblib, T_non 0.65) · STEP26 features.csv / model_cache.npz / 분할.
weak label(외부 NER 범주)은 MedMap concept 정답이 아니다 — 위험 탐지용 proxy.

[사전 고정 어휘 단서 — 평가 실행 전 작성. 일반 한국어 의료 형태(접미·서술어)만, 개별 평가 사례 표현(고혈압·결핵·코피 등)은 넣지 않음]
NON_TYPE_CUE: 조사 제거 stem 의 끝(한국어 핵어 = 마지막 명사)이 질환·약물·치료·검사 유형 접미/어휘일 때. '증상이 아닌 유형'의 적극적 근거.
SYMPTOM_CUE: 문장 어디든 증상 서술어·증상 형태소가 있을 때. NON 판정을 막는 근거(낮은 confidence 는 NON 근거가 아님).
노출 기록: 이 세션은 STEP26 보고서 §4 우선 사례(고혈압·결핵·코피가·호흡곤란이·기침을·발열의·오심·구토·눈·뼈·귀·혈관·신장·수술·약물 치료·전립선)를
           본 뒤 어휘를 썼다 → 그 표현의 결과는 탐색적(exploratory)으로만 보고. HELD_OUT 오류 목록(STEP26 weak-symptom→NON 26건)은 보지 않았다.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

STEP = Path(__file__).resolve().parents[1]
REPO = STEP.parents[1]
S26_DIR = REPO / "exp/step26_ood_safe_normalizer"
sys.path.insert(0, str(S26_DIR / "scripts"))
import s26_common as S26  # noqa: E402
import policy_lib as P26  # noqa: E402

S23 = S26.S23
DATA, OUT, DOCS, LOGS = STEP / "data", STEP / "outputs", STEP / "docs", STEP / "logs"
for _d in (DATA, OUT, DOCS, LOGS):
    _d.mkdir(exist_ok=True)
read_csv, write_csv, sha256, norm, nospace, rnd, load_json, dump_json, dumps = (S26.read_csv, S26.write_csv, S26.sha256, S26.norm, S26.nospace,
                                                                                S26.rnd, S26.load_json, S26.dump_json, S26.dumps)
stem_key, complex_flags = S26.stem_key, S26.complex_flags
SEED = 42

NON_TYPE_CUE = {
    "disease": re.compile(r"(염|암|종양|증후군|병|질환|질병|감염|감염증|경색|부전|협착|경화|결석|바이러스|세균|균)$"),
    "drug": re.compile(r"(약|약물|항[가-힣]*제|진통제|해열제|소염제|수면제|안정제|억제제|차단제|이뇨제|주사제|스테로이드|호르몬제|영양제)$"),
    "treatment": re.compile(r"(치료|수술|시술|요법|절제술|절제|이식|투여|복용|처방|재활|입원|접종|백신|주사)$"),
    "test": re.compile(r"(검사|촬영|내시경|초음파|조영|판독|CT|MRI|엑스레이|x-?ray|수치)$", re.I),
}
SYMPTOM_CUE = re.compile(
    r"(통증|아프|아파|아픔|아팠|쑤시|쑤셔|쓰리|쓰림|쓰려|저리|저림|저려|가렵|가려|어지|메스|울렁|구역|구토|토하|토했|토할|토해|기침|가래|콧물|코막|"
    r"오한|발열|열이|열나|미열|고열|떨림|떨려|부종|부었|붓고|붓는|부어|숨이|숨쉬|숨차|호흡곤란|답답|피로|피곤|무기력|기운이|설사|변비|두근|마비|경련|"
    r"쥐가|불면|잠을 못|출혈|피가|피를|혈변|혈뇨|발진|두드러기|더부룩|따갑|따가|화끈|시리|뻐근|결리|땡기|당기|이물감|피로감|압박감|팽만|작열|"
    r"통$|감각이|감각 저하|식욕|입맛|체중이|소화가|체했|속이 |트림|어눌|흐려|침침|이명|귀울림|두통|복통|요통|흉통)")


def non_type(text: str) -> str:
    k = stem_key(text)
    for name, pat in NON_TYPE_CUE.items():
        if pat.search(k):
            return name
    return ""


def symptom_cue(text: str) -> bool:
    return bool(SYMPTOM_CUE.search(norm(text)))


def bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)} or {s}


def load_train_by_concept():
    import collections
    tr = collections.defaultdict(list)
    for r in read_csv(S23 / "data/expanded_train_expressions.csv"):
        tr[r["canonical_id"]].append(bigrams(nospace(r["expression"])))
    return tr


def cand_sim(text: str, concept: str, tr_by_c) -> float:
    """입력 ↔ 해당 concept 학습 표현 최대 bigram Jaccard(STEP26 lex_overlap 과 같은 정의, concept 별)."""
    bx = bigrams(nospace(text))
    return max((len(bx & t) / len(bx | t) for t in tr_by_c.get(concept, [])), default=0.0)
