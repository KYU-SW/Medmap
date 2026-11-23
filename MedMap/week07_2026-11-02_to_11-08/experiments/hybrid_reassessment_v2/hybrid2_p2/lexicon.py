"""개념 사전. 직접 정의한 파일럿 개념 + 로컬 hp.obo 의 이름·EXACT 동의어(실행 시 읽기, 원문 저장·재배포 없음). 유사 매칭 없음."""
from __future__ import annotations

import os
import re
import sys
from functools import lru_cache
from pathlib import Path

EXP = Path(os.environ.get("HYBRID_EXP_ROOT") or Path(__file__).resolve().parents[2])
HP_OBO = Path("/home/<user>/medmap/data/hpo/hp.obo")
DEFINED = {
    "PE_DIAGNOSIS": {"graph": "DX:Pulmonary embolism", "codes": {"UMLS": "C0034065", "MeSH": "D011655", "MONDO": "MONDO:0005279"},
                     "terms": ["pulmonary embolism", "pulmonary embolisms", "pulmonary emboli", "pulmonary embolus", "pulmonary thromboembolism", "pulmonary thromboemboli", "pulmonary artery embolism", "pulmonary arterial embolism"]},
    "PERICARDITIS_DIAGNOSIS": {"graph": "DX:Pericarditis", "codes": {"UMLS": "C0031046", "MeSH": "D010493", "MONDO": "MONDO:0005904"}, "terms": ["pericarditis"]},
    "MYOCARDITIS_DIAGNOSIS": {"graph": "DX:Myocarditis", "codes": {"UMLS": "C0027059", "MeSH": "D009205", "MONDO": "MONDO:0004496"}, "terms": ["myocarditis"]},
    "TB_DIAGNOSIS": {"graph": "DX:Tuberculosis", "codes": {"UMLS": "C0041296", "MeSH": "D014376", "MONDO": "MONDO:0018076"}, "terms": ["tuberculosis"]},
    "CTPA_STUDY": {"graph": "TEST:Pulmonary_Embolism:0", "codes": {}, "terms": ["ctpa", "ct-pa", "ct pulmonary angiogram", "ct pulmonary angiography", "computed tomography pulmonary angiography", "computed tomographic pulmonary angiography",
                                                                               "cta chest", "chest cta", "ct angiography of the chest", "ct angiogram of the chest", "ct angiography chest", "chest ct angiography", "chest ct angiogram", "ct chest angiography", "ct chest angiogram", "ct angiogram of the pulmonary vasculature",
                                                                               "computed tomography ct angiogram of the pulmonary vasculature", "pe protocol", "pulmonary embolism protocol"]},
    "DDIMER": {"graph": "TEST:Pulmonary_Embolism:2", "codes": {}, "terms": ["d-dimer", "d-dimers", "d dimer", "d dimers", "ddimer"]},
    "PERFUSION_SCAN": {"graph": "", "codes": {}, "terms": ["v/q scan", "vq scan", "ventilation-perfusion scan", "ventilation perfusion scan", "ventilation/perfusion scan", "perfusion scan", "perfusion lung scan", "lung perfusion scan"]},
    "FILLING_DEFECT": {"graph": "CONCEPT:ctpa_filling_defect", "codes": {}, "terms": ["filling defect", "filling defects", "contrast-filling defect", "contrast-filling defects"]},
    "DVT": {"graph": "HP:0002625", "codes": {"HPO": "HP:0002625"}, "terms": ["deep vein thrombosis", "deep venous thrombosis", "dvt"]},
    "ULTRASOUND": {"graph": "", "codes": {}, "terms": ["compression ultrasound", "compression ultrasonography", "venous ultrasound", "venous doppler", "doppler ultrasound", "lower extremity ultrasound", "duplex ultrasound"]},
}
AMBIGUOUS = {r"\bpe\b": "PE 약어(폐색전증·신체검진·흉수 등 가능)", r"\bembol(?:ism|us|i)\b": "색전 부위 불명", r"\bthrombus\b": "혈전 부위 불명", r"\bclot\b": "혈전 부위 불명", r"\bct\b": "CT 종류 불명"}


def _graph():
    p = EXP / "exp03_reassessment"
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
    import reassess
    return reassess.graph()


@lru_cache(maxsize=1)
def hpo_terms() -> dict:
    """소문자 구문 → HP id. 이름·EXACT 동의어만. 4자 미만·대문자 약어 제외. Phenotypic abnormality(HP:0000118) 하위만 — 수식어('left', 'occasional')는 소견이 아님."""
    out: dict = {}
    cur = None
    obsolete = False
    parents: dict = {}
    for line in HP_OBO.read_text(encoding="utf-8").splitlines():
        if line == "[Term]":
            cur, obsolete = None, False
        elif line.startswith("id: HP:"):
            cur = line[4:].strip()
        elif line.startswith("is_a: HP:") and cur:
            parents.setdefault(cur, []).append(line[6:16])
        elif line.startswith("is_obsolete: true") and cur:
            for k in [k for k, v in out.items() if v == cur]:
                del out[k]
            obsolete = True
        elif cur and not obsolete and (line.startswith("name:") or (line.startswith("synonym:") and " EXACT" in line)):
            m = re.search(r'"(.+?)"', line) if line.startswith("synonym:") else None
            t = m.group(1) if m else line.split(":", 1)[1].strip()
            if len(t) >= 4 and not t.isupper():
                out.setdefault(t.lower(), cur)

    def is_phenotype(h, seen=()):
        return h == "HP:0000118" or any(p not in seen and is_phenotype(p, seen + (h,)) for p in parents.get(h, ()))
    keep = {h: is_phenotype(h) for h in set(out.values())}
    return {k: v for k, v in out.items() if keep[v]}


@lru_cache(maxsize=1)
def lexicon() -> tuple:
    """(구문 → (개념, 종류)), 그래프 노드 집합."""
    g = _graph()
    table = {}
    for c, d in DEFINED.items():
        for t in d["terms"]:
            table[t] = (c, "DEFINED")
    for t, hp in hpo_terms().items():
        table.setdefault(t, (hp, "HPO"))
    return table, set(g.nodes)


def graph_node(concept: str) -> str:
    return DEFINED[concept]["graph"] if concept in DEFINED else concept


def codes(concept: str) -> dict:
    return DEFINED[concept]["codes"] if concept in DEFINED else {"HPO": concept}


TOKEN = re.compile(r"[a-z0-9]+(?:[-/][a-z0-9]+)*")


def find_mentions(clause: str) -> list:
    """긴 구문 우선 비겹침 정확 일치. 반환 [(시작, 끝, 표현, 개념, 종류)]."""
    table, _ = lexicon()
    low = clause.lower()
    toks = list(TOKEN.finditer(low))
    out, used = [], set()
    for n in range(7, 0, -1):
        for i in range(len(toks) - n + 1):
            s, e = toks[i].start(), toks[i + n - 1].end()
            if any(x in used for x in range(s, e)):
                continue
            hit = table.get(low[s:e]) or table.get(re.sub(r"\s+", " ", low[s:e]))
            if hit:
                used.update(range(s, e))
                out.append((s, e, clause[s:e], hit[0], hit[1]))
    return sorted(out)


def find_ambiguous(clause: str, taken: list) -> list:
    """사전 개념에 포함되지 않은 모호 표현."""
    low = clause.lower()
    out = []
    for pat, why in AMBIGUOUS.items():
        for m in re.finditer(pat, low):
            if not any(s <= m.start() and m.end() <= e for s, e, *_ in taken):
                out.append((m.start(), m.end(), clause[m.start():m.end()], why))
    return out
