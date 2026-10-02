"""MedMap 다음 정보 선택 엔진 demo (대화형/스크립트 겸용).

  ~/ai_env/bin/python -m medmap.demo_cli --age 45 --sex M --initial E_53 \
      --observed E_55=V_89 --observed E_56=2 --observed E_204=V_10 --answers V_181,POS,NEG

--answers 를 주면 비대화형으로 그 답들을 순서대로 사용하고, 없으면 입력을 받는다.
확률은 저장된 MODEL_k 로 실제 계산한다(하드코딩 없음).
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .diagnosis import DiagnosisEngine
from .evidence import EvidenceCatalog
from .next_information import NextInformationEngine
from .patient_state import PatientState, negative, not_applicable, positive, unknown, value
from .question_presentation import QuestionPresenter
from .serialization import dumps_patient_state, loads_patient_state


def parse_answer(catalog: EvidenceCatalog, evidence_id: str, raw: str):
    raw = raw.strip()
    upper = raw.upper()
    if upper in ("POS", "Y", "YES", "예"): return positive()
    if upper in ("NEG", "N", "NO", "아니오"): return negative()
    if upper in ("UNKNOWN", "?", "모름"): return unknown()
    if upper in ("NA", "NOT_APPLICABLE"): return not_applicable()
    return value(*[v.strip() for v in raw.split("|") if v.strip()])


def render(turn, max_choices: int = 12) -> str:
    lines = ["현재 진단 후보"]
    for i, (disease, prob) in enumerate(turn.diagnoses.top3, 1):
        lines.append(f"  {i}. {disease} {prob*100:.1f}%")
    if turn.next_question is None:
        lines.append(f"종료: {turn.stop_reason}")
        return "\n".join(lines)
    view = turn.next_question.to_dict()
    lines.append("")
    lines.append(f'다음으로 확인할 정보: "{view.get("question_ko", view["question_text"])}"')
    flags = [view["question_id"], view["answer_type"]] + (["원문 fallback"] if view.get("is_fallback") else [])
    lines.append(f"  [{' / '.join(flags)}]  정보 가치: {view['information_gain']:.4f} bits")
    for i, choice in enumerate(view.get("choices", [])[:max_choices], 1):
        lines.append(f"    {i}. {choice['label']}")
    if len(view.get("choices", [])) > max_choices:
        lines.append(f"    … (총 {len(view['choices'])}개)")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="MedMap next-information engine demo")
    parser.add_argument("--age", type=int, default=None)
    parser.add_argument("--sex", choices=["M", "F"], default=None)
    parser.add_argument("--initial", default=None, help="초기 evidence id (binary POSITIVE)")
    parser.add_argument("--observed", action="append", default=[], help="E_55=V_89 / E_91=NEG 형식, 반복 가능")
    parser.add_argument("--model-context", choices=["k3", "k5", "k10"], default="k3")
    parser.add_argument("--max-questions", type=int, default=3)
    parser.add_argument("--answers", default=None, help="비대화형 답변 목록(쉼표 구분, 선택지 번호 또는 값 코드)")
    parser.add_argument("--save-session", default=None, help="종료 시 PatientState 를 JSON 으로 저장")
    parser.add_argument("--load-session", default=None, help="저장된 세션 JSON 에서 이어서 진행")
    args = parser.parse_args(argv)

    catalog = EvidenceCatalog()
    presenter = QuestionPresenter(catalog)
    model_context = args.model_context
    if args.load_session:
        snapshot = loads_patient_state(Path(args.load_session).read_text(), catalog)
        state, model_context = snapshot.state, snapshot.model_context
        print(f"[세션 복원] {args.load_session} (model_context={model_context}, 답변 {state.n_asked}개)")
    else:
        if args.age is None or args.sex is None:
            parser.error("--age 와 --sex 는 새 세션에 필요합니다 (또는 --load-session 사용)")
        observed = {}
        for item in args.observed:
            evidence_id, _, raw = item.partition("=")
            observed[evidence_id] = parse_answer(catalog, evidence_id, raw)
        state = PatientState.new(args.age, args.sex, args.initial, observed)
    engine = NextInformationEngine(DiagnosisEngine(catalog, model_context), max_questions=args.max_questions,
                                   presenter=presenter)

    turn = engine.start(state)
    print(f"[관측] 나이 {state.age} / 성별 {state.sex} / 확인된 항목 {state.n_asked}개 "
          f"(model_context={turn.diagnoses.model_context}, 학습 뷰와 일치={turn.model_context_match})")
    print(render(turn))
    scripted = [a for a in (args.answers.split(",") if args.answers else [])]
    while turn.next_question is not None:
        qid = turn.next_question.evidence_id
        if scripted:
            raw = scripted.pop(0)
            print(f"\n선택: {raw}")
        else:
            try:
                raw = input("\n선택 (번호, 여러 개는 '|' 로 구분, 빈 줄이면 종료): ")
            except EOFError:
                break
            if not raw.strip():
                break
        answer = selection_to_answer(presenter, turn, raw)
        turn = engine.answer(turn, qid, answer)
        print(render(turn))
    if args.save_session:
        Path(args.save_session).write_text(dumps_patient_state(turn.state, model_context, indent=1))
        print(f"\n[세션 저장] {args.save_session}")
    return 0


def selection_to_answer(presenter: QuestionPresenter, turn, raw: str):
    """demo 입력(선택지 번호 또는 값 코드/라벨) → PatientState Answer."""
    choices = turn.next_question.to_dict().get("choices", [])
    picks = []
    for token in [t.strip() for t in raw.split("|") if t.strip()]:
        if token.isdigit() and 1 <= int(token) <= len(choices):
            picks.append(choices[int(token) - 1]["value"])
        else:
            picks.append(token)
    if len(picks) == 1:
        return presenter.to_answer(turn.next_question.evidence_id, picks[0])
    return presenter.to_answer(turn.next_question.evidence_id, picks)


if __name__ == "__main__":
    raise SystemExit(main())
