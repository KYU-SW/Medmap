"""STEP29.1 §3 검사기 v5 정답 대조(LLM 없음) → outputs/evaluator_validation.json(SHA 고정).
 정상(위반 0 이어야): (a) STEP28.8 정답 쌍 중 단일 concept 표현(문장 = 단일 mention, scope = 문장) (b) 혼합 문장 정상 mention 목록(구문별 scope, 아래 MIXED_OK)
 오류(전부 탐지해야): KNOWN_BAD(지시문 §3 필수 + 약물·질환 내부 문자열 + 가드 있는데 자동 수락)
 비교: 같은 혼합 문장을 v4(문장 단위)로 검사했을 때의 오판 수도 기록(검사기 결함 재현)."""
import s291_common as S
from evaluator_v4 import violations as v4
from evaluator_v5 import EVALUATOR_VERSION, evaluator_sha, mention_violations
from validate_evaluator import gold_pairs


def M(text, unit, concept, status="EXISTING_CANONICAL", **kw):
    s = text.index(unit)
    return {"source_text": text, "raw_span": unit, "span_start": s, "span_end": s + len(unit), "unit_text": unit, "source_sentence": text,
            "status": status if concept else "NON_SYMPTOM", "canonical_id": concept, **kw}


MIXED_OK = [("고혈압이 있고 머리가 아파요", [("고혈압이 있고", None), ("머리가 아파요", "pain")]),
            ("기침약을 먹었는데 기침이 계속 나요", [("기침약을 먹었는데", None), ("기침이 계속 나요", "cough")]),
            ("천식이 있어서 숨이 차요", [("천식이 있어서", None), ("숨이 차요", "dyspnea")]),
            ("위염이 있는데 배가 아파요", [("위염이 있는데", None), ("배가 아파요", "pain")]),
            ("혈압약 먹는 중이고 어지러워요", [("혈압약 먹는 중이고", None), ("어지러워요", "dizziness")]),
            ("추워서 몸이 덜덜 떨려요", [("몸이 덜덜 떨려요", "chills")]),
            ("토할 것 같아요", [("토할 것 같아요", "nausea")]),
            ("코피가 나고 기침도 해요", [("기침도 해요", "cough")]),
            ("손이 떨리고 열이 나요", [("열이 나요", "fever")]),
            ("심장이 두근거려요", [("심장이 두근거려요", "palpitations")]),
            ("엄마는 기침하고 저는 열이 나요", [("엄마는 기침하고", "cough"), ("저는 열이 나요", "fever")]),
            ("해열제를 먹었는데 열이 안 내려요", [("열이 안 내려요", "fever")])]
KNOWN_BAD = [("코피가 나요", "코피가 나요", "hemoptysis", {}), ("코피", "코피", "hematemesis", {}), ("토했어요", "토했어요", "nausea", {}),
             ("메스꺼워요", "메스꺼워요", "vomiting", {}), ("토할 것 같아요", "토할 것 같아요", "vomiting", {}), ("떨림", "떨림", "chills", {}),
             ("손이 떨려요", "손이 떨려요", "chills", {}), ("심장 부분", "심장 부분", "palpitations", {}), ("기침약을 먹었어요", "기침약을 먹었어요", "cough", {}),
             ("기침 억제제", "기침 억제제", "cough", {}), ("고혈압", "고혈압", "dizziness", {}), ("혈관성 편두통", "혈관성 편두통", "pain", {}),
             ("위염", "위염", "pain", {}), ("속이 화끈화끈해요", "속이 화끈화끈해요", "nausea", {"guard_reasons": ["IDEOPHONE_MISMATCH"]}),
             ("치아 주위", "치아 주위", "dizziness", {"ko_tier": "PHRASE"})]


def main():
    fp, nmix = [], 0
    for src, t, cs in gold_pairs():
        if len(cs) != 1:
            continue
        m = M(t, t, cs[0])
        if mention_violations(m):
            fp.append((src, t, cs[0], mention_violations(m)))
    v4_fp = []
    for t, ms in MIXED_OK:
        allc = [c for _, c in ms if c]
        if v4(t, allc):
            v4_fp.append((t, v4(t, allc)))
        for u, c in ms:
            nmix += 1
            m = M(t, u, c)
            if mention_violations(m):
                fp.append(("MIXED_OK", t, c, mention_violations(m)))
    fn = []
    for t, u, c, kw in KNOWN_BAD:
        if not mention_violations(M(t, u, c, **kw)):
            fn.append((t, c))
    singles = sum(1 for _, _, cs in gold_pairs() if len(cs) == 1)
    out = {"EVALUATOR_V5": "PASS" if not fp and not fn else "FAIL", "evaluator_version": EVALUATOR_VERSION, "evaluator_sha256": evaluator_sha(),
           "known_correct_mentions": singles + nmix, "evaluator_false_positive": len(fp), "fp_examples": fp[:20], "known_bad": len(KNOWN_BAD),
           "evaluator_false_negative": len(fn), "fn_examples": fn, "v4_sentence_level_false_positive_on_MIXED_OK": len(v4_fp), "v4_fp_examples": v4_fp,
           "note": "정상 = STEP28.8 정답 쌍 중 단일 concept + 혼합 문장 정상 mention(Claude 작성). 오류 = 지시문 §3 필수 + 알려진 사례. 사람 검증 Gold 아님"}
    S.dump_json(S.OUT / "evaluator_validation.json", out)
    print(S.dumps({k: out[k] for k in ("EVALUATOR_V5", "known_correct_mentions", "evaluator_false_positive", "evaluator_false_negative", "fn_examples",
                                       "v4_sentence_level_false_positive_on_MIXED_OK")}))
    for f in fp[:15]:
        print(" FP", f)


if __name__ == "__main__":
    main()
