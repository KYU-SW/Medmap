"""STEP29.2 §8 검사기 v6 정답 대조(LLM·NLU 실행 없음) → outputs/evaluator_validation.json(SHA 고정). NLU 정책 구현 전에 실행.
 정상(위반 0 이어야 — EVALUATOR_FALSE_POSITIVES): (a) STEP28.8 정답 쌍 중 단일 concept 표현(문장 = 단일 mention) (b) STEP29.1 혼합 문장 정상 mention(MIXED_OK)
   (c) 지시문 §8 필수 표현·증상 성질 수식어·혼동 쌍 정상 연결(OK_V6) (d) assertion 정상(ASSERT_OK — 부정·결핍·이중 부정·개선 부정·평가형)
 오류(전부 탐지해야 — EVALUATOR_FALSE_NEGATIVES): STEP29.1 KNOWN_BAD + v6 추가(BAD_V6: 질환형 수식어·혈액 경로·양태 구토·부정 누락·부정 전파·혼합 문장 비증상 구문)
 비교: 같은 세트에서 v5 의 오판·누락 수(검사기 결함 재현: 박동성·회전성).
 [정답 대조 중 수정 기록(평가 전)] 1차: 누락 3 — '고혈압'(kiwi 접두 XPN 분리 → 핵어 이어붙여 검사) · '고혈압이 있고'(같은 원인) · '헛구역질→vomiting' BAD 항목.
   2차: 헛구역을 오심 단서로 넣자 기존 정답(pilot '헛구역질만 계속 나요'=vomiting, STEP23 학습 문항) 4건 오판 → 기존 정답 관례를 따르고 BAD 항목 제거(v5 규칙으로 복귀)."""
import s292_common as S
from evaluator_v5 import mention_violations as v5
from evaluator_v6 import EVALUATOR_VERSION, evaluator_sha, mention_violations
from validate_evaluator import gold_pairs
from validate_evaluator_v5 import KNOWN_BAD, MIXED_OK


def M(text, unit, concept, status="EXISTING_CANONICAL", **kw):
    s = text.index(unit)
    return {"source_text": text, "raw_span": unit, "span_start": s, "span_end": s + len(unit), "unit_text": unit, "source_sentence": text,
            "status": status if concept else "NON_SYMPTOM", "canonical_id": concept, **kw}


OK_V6 = [  # (문장, mention 범위, concept) — 지시문 §8 필수 + 증상 성질 수식어 + 혼동 쌍 정상
    ("박동성 두통이 있어요", "박동성 두통이 있어요", "pain"), ("박동성 두통", "박동성 두통", "pain"), ("회전성 어지럼증이 있어요", "회전성 어지럼증이 있어요", "dizziness"),
    ("회전성 어지럼증", "회전성 어지럼증", "dizziness"), ("반복성 두통이 있어요", "반복성 두통이 있어요", "pain"), ("간헐성 복통이 있어요", "간헐성 복통이 있어요", "pain"),
    ("머리가 지끈지끈 아파요", "머리가 지끈지끈 아파요", "pain"), ("쥐어짜는 듯한 흉통이 있어요", "쥐어짜는 듯한 흉통이 있어요", "pain"),
    ("고혈압이 있고 머리가 아파요", "머리가 아파요", "pain"), ("기침약을 먹었는데 기침이 계속 나요", "기침이 계속 나요", "cough"),
    ("토할 것 같아요", "토할 것 같아요", "nausea"), ("토할 것만 같아요", "토할 것만 같아요", "nausea"), ("토했어요", "토했어요", "vomiting"),
    ("먹은 걸 다 게워냈어요", "먹은 걸 다 게워냈어요", "vomiting"), ("기침하면 피가 같이 나와요", "기침하면 피가 같이 나와요", "hemoptysis"),
    ("피를 토했어요", "피를 토했어요", "hematemesis"), ("추워서 몸이 떨려요", "추워서 몸이 떨려요", "chills"), ("헛구역질이 나요", "헛구역질이 나요", "nausea"),
    ("메스꺼워요", "메스꺼워요", "nausea"), ("천식이 있는데 숨이 차요", "숨이 차요", "dyspnea"), ("두통약을 먹었는데 머리가 계속 아파요", "머리가 계속 아파요", "pain"),
    ("위염이 있는데 속이 쓰려요", "속이 쓰려요", "heartburn")]
ASSERT_OK = [  # (문장, 범위, concept, assertion)
    ("기침은 안 나요", "기침은 안 나요", "cough", "ABSENT"), ("열은 없어요", "열은 없어요", "fever", "ABSENT"), ("숨이 차요", "숨이 차요", "dyspnea", "PRESENT"),
    ("다리에 힘이 없어요", "다리에 힘이 없어요", "limb_weakness", "PRESENT"), ("입맛이 없어요", "입맛이 없어요", "decreased_appetite", "PRESENT"),
    ("열이 안 내려요", "열이 안 내려요", "fever", "PRESENT"), ("기침이 안 멈춰요", "기침이 안 멈춰요", "cough", "PRESENT"),
    ("열이 계속 안 떨어져요", "열이 계속 안 떨어져요", "fever", "PRESENT"), ("기침이 안 나는 건 아니에요", "기침이 안 나는 건 아니에요", "cough", "PRESENT"),
    ("머리는 괜찮아요", "머리는 괜찮아요", "pain", "ABSENT"), ("어지럽지는 않아요", "어지럽지는 않아요", "dizziness", "ABSENT"),
    ("냄새를 못 맡아요", "냄새를 못 맡아요", "EV:E_103", "PRESENT"), ("열이 났어요", "열이 났어요", "fever", "PRESENT"),
    ("입맛은 괜찮아요", "입맛은 괜찮아요", "decreased_appetite", "ABSENT"), ("기침이 다 나았어요", "기침이 다 나았어요", "cough", "ABSENT"),
    ("열이 나는 것 같지는 않아요", "열이 나는 것 같지는 않아요", "fever", "ABSENT"), ("기침이 나요", "기침이 나요", "cough", "PRESENT"),
    ("속은 안 메스꺼워요", "속은 안 메스꺼워요", "nausea", "ABSENT"), ("오한은 없어요", "오한은 없어요", "chills", "ABSENT")]
BAD_V6 = [  # (문장, 범위, concept, kw)
    ("혈관성 편두통", "혈관성 편두통", "pain", {}), ("알레르기성 비염", "알레르기성 비염", "cough", {}), ("천식", "천식", "dyspnea", {}),
    ("두통약", "두통약", "pain", {}), ("혈압약을 먹어요", "혈압약을 먹어요", "dizziness", {}),
    ("고혈압이 있고 머리가 아파요", "고혈압이 있고", "pain", {}), ("기침약을 먹었는데 기침이 계속 나요", "기침약을 먹었는데", "cough", {}),
    ("기침하면 피가 같이 나와요", "기침하면 피가 같이 나와요", "hematemesis", {}), ("피를 토했어요", "피를 토했어요", "hemoptysis", {}),
    ("코피가 나요", "코피가 나요", "hematemesis", {}), ("토할 것만 같아요", "토할 것만 같아요", "vomiting", {}), ("다 게워냈어요", "다 게워냈어요", "nausea", {}),
    ("손가락이 떨려요", "손가락이 떨려요", "chills", {}),
    ("기침은 안 나요", "기침은 안 나요", "cough", {"assertion": "PRESENT"}), ("열은 없어요", "열은 없어요", "fever", {"assertion": "PRESENT"}),
    ("어지럽지는 않아요", "어지럽지는 않아요", "dizziness", {"assertion": "PRESENT"}), ("속은 안 메스꺼워요", "속은 안 메스꺼워요", "nausea", {"assertion": "PRESENT"}),
    ("숨이 차요", "숨이 차요", "dyspnea", {"assertion": "ABSENT"}), ("열이 났어요", "열이 났어요", "fever", {"assertion": "ABSENT"}),
    ("기침은 없어요 숨은 차요", "숨은 차요", "dyspnea", {"assertion": "ABSENT"})]


def main():
    fp, fp5, n_ok = [], [], 0
    for src, t, cs in gold_pairs():
        if len(cs) != 1:
            continue
        n_ok += 1
        m = M(t, t, cs[0])
        if mention_violations(m):
            fp.append((src, t, cs[0], mention_violations(m)))
        if v5(m):
            fp5.append((src, t, cs[0], v5(m)))
    for t, ms in MIXED_OK:
        for u, c in ms:
            n_ok += 1
            m = M(t, u, c)
            if mention_violations(m):
                fp.append(("MIXED_OK", t, c, mention_violations(m)))
            if v5(m):
                fp5.append(("MIXED_OK", t, c, v5(m)))
    for t, u, c in OK_V6:
        n_ok += 1
        m = M(t, u, c)
        if mention_violations(m):
            fp.append(("OK_V6", t, c, mention_violations(m)))
        if v5(m):
            fp5.append(("OK_V6", t, c, v5(m)))
    for t, u, c, a in ASSERT_OK:
        n_ok += 1
        m = M(t, u, c, assertion=a)
        if mention_violations(m):
            fp.append(("ASSERT_OK", t, c, a, mention_violations(m)))
    fn, fn5, n_bad = [], [], 0
    for t, u, c, kw in [(t, u, c, kw) for t, u, c, kw in KNOWN_BAD] + BAD_V6:
        n_bad += 1
        m = M(t, u, c, **kw)
        if not mention_violations(m):
            fn.append((t, u, c, kw))
        if not v5(m):
            fn5.append((t, u, c, kw))
    out = {"EVALUATOR_V6": "PASS" if not fp and not fn else "FAIL", "evaluator_version": EVALUATOR_VERSION, "evaluator_sha256": evaluator_sha(),
           "known_correct_mentions": n_ok, "EVALUATOR_FALSE_POSITIVES": len(fp), "fp_examples": fp[:30], "known_bad": n_bad,
           "EVALUATOR_FALSE_NEGATIVES": len(fn), "fn_examples": fn,
           "v5_on_same_set": {"false_positive": len(fp5), "fp_examples": fp5[:20], "false_negative": len(fn5), "fn_examples": fn5[:30],
                              "note": "v5 는 assertion 규칙이 없어 ASSERT_OK 미적용·부정 관련 BAD 는 원래 범위 밖"},
           "note": "정상 = STEP28.8 정답 쌍 단일 concept + STEP29.1 MIXED_OK + OK_V6 + ASSERT_OK(Claude 작성). 오류 = STEP29.1 KNOWN_BAD + BAD_V6. 사람 검증 Gold 아님"}
    S.dump_json(S.OUT / "evaluator_validation.json", out)
    print(S.dumps({k: out[k] for k in ("EVALUATOR_V6", "known_correct_mentions", "EVALUATOR_FALSE_POSITIVES", "known_bad", "EVALUATOR_FALSE_NEGATIVES")}),
          {"v5_fp": len(fp5), "v5_fn": len(fn5)})
    for f in fp[:30]:
        print(" FP", f)
    for f in fn:
        print(" FN", f)


if __name__ == "__main__":
    main()
