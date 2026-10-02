"""발화 완결(Turn Completion) 등급 — Adaptive Endpoint 의 한 신호(확정 판정 아님).

"문법적으로 완전한 문장인가"가 아니라 "화자가 지금 발화 차례를 끝낸 것 같은가"를 등급으로만 낸다.
대기 시간·가중치 같은 정책 값은 여기 없다(실제 사람 녹음 baseline 후 결정 — plan M2b).

- 1순위: Kiwi(kiwipiepy, ~/ai_env 에 이미 설치, 모델 패키지 내장·오프라인 동작 확인) 마지막 형태소 태그.
- fallback: 정규식 어미 규칙(Kiwi 로드 실패·오류·MEDMAP_STT_TURN_KIWI=0).
오프라인: 외부 API·LLM·다운로드 없음. 텍스트는 로그에 남기지 않는다(등급·사유 코드만).

등급: complete · continuing(연결어미·접속사) · incomplete(조사·간투사·관형형·숫자 꼬리) · ambiguous(데이터로 정함) · unknown(빈 텍스트)
"""
from __future__ import annotations

import logging
import os
import re
import threading
from dataclasses import dataclass

LOG = logging.getLogger("medmap.stt_turn")

ANSWER_WORDS = {"네", "예", "응", "아니요", "아뇨", "아니", "아니오", "맞아요"}
FILLERS = {"어", "음", "으음", "그", "저", "뭐", "아", "에", "흠", "막"}
CONJUNCTIONS = {"그리고", "근데", "그런데", "그래서", "그러다가", "아니면", "그러니까", "하지만", "그러면", "또"}
HESITATION_EF = {"랄까", "더라"}                    # EF 로 태깅되지만 말을 고르는 중("뭐랄까")
SOFT_FINAL = {"고요", "구요"}                       # EF 태깅이지만 이어지는 경우가 많음("잤고요, …")
SKIP_TAGS = {"SF", "SP", "SS", "SE", "SO", "SW"}   # 문장부호·말줄임표
NUMBER_TAGS = {"NR", "SN"}
PARTICLE_TAGS = {"JKS", "JKC", "JKG", "JKO", "JKB", "JKV", "JKQ", "JX", "JC"}
NOUN_TAGS = {"NNG", "NNP", "NNB", "NP"}


@dataclass(frozen=True)
class TurnCompletion:
    label: str        # complete | continuing | incomplete | ambiguous | unknown
    reason: str       # 사유 코드(텍스트 아님)
    source: str       # kiwi | regex | none


_analyzer = None       # None = 아직 로드 안 함, False = 사용 안 함(로드 실패·끔), 그 외 = Kiwi
_lock = threading.Lock()
_override = None       # 테스트: None(실제) · False(Kiwi 끔) · 객체(tokenize 가짜)


def set_analyzer_for_tests(analyzer) -> None:
    global _override
    _override = analyzer


def _get_analyzer():
    global _analyzer
    if _override is not None:
        return _override
    if _analyzer is None:
        with _lock:
            if _analyzer is None:
                if os.environ.get("MEDMAP_STT_TURN_KIWI", "1") == "0":
                    _analyzer = False
                else:
                    try:
                        from kiwipiepy import Kiwi
                        _analyzer = Kiwi(num_workers=-1)
                    except Exception as exc:          # 종류만 기록, regex 로 계속
                        LOG.info("stt_turn kiwi_unavailable kind=%s", type(exc).__name__)
                        _analyzer = False
    return _analyzer


def warm() -> bool:
    """서버 시작 시 미리 로드(첫 발화에서 ~0.7 s 로드 지연 방지). Kiwi 사용 가능 여부를 돌려준다."""
    return bool(_get_analyzer())


def classify(text: str) -> TurnCompletion:
    if not text or not text.strip():
        return TurnCompletion("unknown", "empty", "none")
    analyzer = _get_analyzer()
    if analyzer:
        try:
            return _classify_tokens(analyzer.tokenize(text))
        except Exception as exc:
            LOG.info("stt_turn kiwi_failed kind=%s", type(exc).__name__)
    return classify_regex(text)


def _classify_tokens(tokens) -> TurnCompletion:
    toks = [t for t in tokens if t.tag not in SKIP_TAGS]
    if not toks:
        return TurnCompletion("unknown", "no_tokens", "kiwi")
    last = toks[-1]
    prev = toks[-2] if len(toks) > 1 else None
    form, tag = last.form, last.tag

    def done(label, reason):
        return TurnCompletion(label, reason, "kiwi")

    if form in HESITATION_EF:                                  # "뭐랄까" — 말줄임표가 붙으면 EC, 아니면 EF 로 태깅된다
        return done("incomplete", "hesitation")
    if form == "요" and prev is not None:                      # "전부터요"·"정도요"·"아팠는데요"
        if prev.tag == "EC":
            return done("ambiguous", "ec_yo")                  # "-는데요"·"-고요" 류: 공손한 끝맺음일 수도, 이어질 수도
        return done("complete", "short_answer_yo")
    if form == "이요" and tag in PARTICLE_TAGS:                 # "두 번이요"·"오른쪽이요"
        return done("complete", "short_answer_yo")
    if tag == "EF":
        if form in SOFT_FINAL:
            return done("ambiguous", "soft_final")
        return done("complete", "final_ending")
    if tag == "IC":
        if form in ANSWER_WORDS:
            return done("complete", "answer_word")
        return done("incomplete", "filler")
    if tag == "EC":
        return done("continuing", "connective_ending")
    if tag == "MAJ" or form in CONJUNCTIONS:
        return done("continuing", "conjunction")
    if tag in NUMBER_TAGS:
        return done("incomplete", "numeric_tail")
    if form == "점" and prev is not None and prev.tag in NUMBER_TAGS:
        return done("incomplete", "numeric_point")             # "삼십팔 점" — 소수점 뒤가 남음
    if tag in PARTICLE_TAGS:
        return done("incomplete", "particle")
    if tag in ("MM", "ETM", "ETN", "EP", "XPN") or tag.startswith(("VV", "VA", "VX", "VCP", "VCN", "XS")):
        return done("incomplete", "open_word")
    if tag in NOUN_TAGS:
        if prev is not None and prev.tag == "ETM":
            return done("incomplete", "adnominal_clause")      # "쟀을 때"
        if prev is not None and prev.tag in NUMBER_TAGS:
            return done("ambiguous", "numeric_unit")           # "삼십팔 도" — 답으로 끝날 수도
        return done("ambiguous", "nominal")
    return done("ambiguous", f"tag_{tag}"[:16])


_RE_CLEAN = re.compile(r"[\s.,!?·…~\"'()\-]+$")
_RE_AMBIGUOUS = re.compile(r"(는데요|은데요|고요|구요)$")
_RE_COMPLETE = re.compile(r"(요|다|죠|니다|네요|거든요|어|아)$")
_RE_CONTINUING = re.compile(r"(고|는데|은데|지만|면|해서|어서|아서|다가|면서|거나|니까)$")
_RE_NUMERIC = re.compile(r"(점|[0-9])$")


def classify_regex(text: str) -> TurnCompletion:
    """Kiwi 없이 쓰는 거친 규칙(fallback). 마지막 어절 기준."""
    stripped = _RE_CLEAN.sub("", text or "").strip()
    if not stripped:
        return TurnCompletion("unknown", "empty", "regex")
    word = stripped.split()[-1]

    def done(label, reason):
        return TurnCompletion(label, reason, "regex")

    if word in ANSWER_WORDS:
        return done("complete", "answer_word")
    if word in FILLERS:
        return done("incomplete", "filler")
    if word in CONJUNCTIONS:
        return done("continuing", "conjunction")
    if _RE_NUMERIC.search(word):
        return done("incomplete", "numeric_tail")
    if _RE_AMBIGUOUS.search(word):
        return done("ambiguous", "ec_yo")
    if _RE_COMPLETE.search(word):
        return done("complete", "final_ending")
    if _RE_CONTINUING.search(word):
        return done("continuing", "connective_ending")
    return done("ambiguous", "other")
