"""Natural Intake v1 매퍼: 한국어 자유문장 → DDXPlus binary evidence 후보.

원칙(v1):
  - deterministic regex alias 사전만 사용한다(임베딩·LLM 없음). 같은 입력 → 항상 같은 출력.
  - HIGH confidence만 반환한다. 애매하면 반환하지 않는다(그 evidence는 UNASKED로 남는다).
  - 카탈로그 밖 evidence는 만들 수 없다(alias가 실재 ID만 가리키도록 로드 시 검증).
    단, 카탈로그 안에서 잘못 매칭(false positive)하는 것은 가능하다.
  - 부정은 문장 전체가 아니라 mention 뒤의 좁은 범위(scope)에만 적용한다.
    scope = mention 끝 → (다음 mention 시작 | 문장 끝 | 연결어미로 끝나는 어절) 중 먼저 오는 곳.
  - 기존 진단 엔진·PatientState·API와 분리된 독립 모듈이다(엔진 상태를 바꾸지 않는다).
"""
from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .. import config

ALIASES_JSON = Path(__file__).resolve().parent / "aliases_ko.json"
NEGATIVE_POLICY_JSON = Path(__file__).resolve().parent / "negative_policy.json"
STATUSES = ("POSITIVE", "NEGATIVE")


class AliasValidationError(ValueError):
    """alias 사전이 카탈로그 계약을 어겼다(없는 ID·제외 ID·non-binary·잘못된 regex 등)."""


# ---------------------------------------------------------------------------
# 부정·불확실 단서 (mention scope 안에서만 검사)
# ---------------------------------------------------------------------------
NEG_CUES = (
    re.compile(r"없"),
    re.compile(r"않"),
    re.compile(r"(?<![가-힣])안(?=[ 가-힣])(?!녕|경|쪽|전|심|정|과|에|의|내|개|이|으로|색|부)"),
    re.compile(r"아니|아닌|아닙|아뇨"),
    # B: 긴 부정 "V-지 못하다"만 부정. 짧은 "못 V"(숨을 못 쉬어요)는 증상일 수 있어 부정 아님
    re.compile(r"지 ?(?:는|도|를)? ?못"),
    re.compile(r"괜찮"),
    re.compile(r"멀쩡"),
    # D(v1.2): 짧은 '못'은 지각 동사일 때만 부정("통증은 못 느꼈어요", "피는 못 봤어요")
    re.compile(r"(?<![가-힣])못 ?(?:느끼|느꼈|느껴|봤|보았|본 ?적|들었)"),
)
# B(v1.2): 부정 글자를 품은 관용 표현은 부정 단서 검사 전에 지운다
#   "장난 아니게", "끊임없이", "쉴 새 없이" 등은 오히려 강조(POSITIVE)
IDIOM = re.compile(r"장난 ?아니\w*|아닌 ?게 ?아니라|끊임없\w*|쉴 ?새 ?없\w*|틀림없\w*|어김없\w*|정신없\w*|하염없\w*"
                   r"|어이없\w*|대책 ?없\w*|한없\w*|말할 ?수 ?없\w*|말도 ?안 ?되\w*|안 ?그래도")
# 부정 + 지속 동사 = 증상이 계속됨(POSITIVE): "열이 안 떨어져요", "기침이 멈추지 않아요"
PERSIST = re.compile(
    r"(?:안|못) ?(?:멈|그치|그쳐|떨어|내려|낫|나아|가라앉|줄어|사라|멎|빠지|빠져|풀리|풀려|가시|가셔|없어지|없어져)"
    r"|(?:멈추|멈춰|그치|떨어지|내려가|낫|나아지|가라앉|줄어들|사라지|멎|빠지|풀리|가시|없어지)지 ?(?:는|도|가)? ?않"
)
# 부분 부정("별로 안", "많이는 안")·호전("나아졌")·대조("아니라") → 불확실
PARTIAL = re.compile(r"별로|그다지|많이는|심하게는|심하지는|그렇게|크게는|딱히")
# "기침만 있는 게 아니라 열도" = '~뿐 아니라'(긍정) → 부정으로 읽지 않고 버림
NOT_ONLY = re.compile(r"(?:만|뿐) ?(?:[가-힣]+ )?(?:게|것|건|거)? ?아니|뿐만 ?아니")
# A: mention 바로 앞의 동사 앞 부정 "안 (울렁거려요|기침해요)"
PRE_NEG = re.compile(r"(?<![가-힣])안 ?$")
# 호전 표현("나아졌어요", "좀 덜해요")은 현재 있음/없음이 불확실 → 부정 여부와 무관하게 버림
IMPROVED = re.compile(r"괜찮아지|괜찮아졌|나아지|나아졌|나았|좋아졌|좋아지|덜해|덜하|줄었|줄어들")
HEDGE = re.compile(r"것 ?같|거 ?같|듯|지도 ?몰|지 ?모르|모르겠|잘 ?모르|같기도|애매|싶기도|나 ?싶|인가|려나|[을ㄹ]까|을지|는지|까 ?봐|까 ?싶|까 ?걱정")
EVER = re.compile(r"(?:한|은|던|난|었던|었는|ㄴ) ?적")
QUESTION_END = re.compile(r"\?|까요|까\s*$")
OTHER_PERSON = re.compile(
    r"(?<![가-힣])(?:엄마|아빠|어머니|아버지|어머님|아버님|부모님|동생|남동생|여동생|형|누나|언니|오빠|아이|애|아기|"
    r"아들|딸|남편|아내|와이프|친구|가족|할머니|할아버지|동료|애인|남자 ?친구|여자 ?친구|남친|여친|룸메이트|조카|사촌|"
    r"시어머니|장모님|옆 ?사람|직장 ?동료|반 ?친구)(?:가|이|는|은|도|께서|께선|랑|하고|의|네|들|들이|들도)(?![가-힣])"
)
SENT_HEDGE = re.compile(r"(?<![가-힣])(?:혹시|아마|아마도|글쎄|글쎄요)(?![가-힣])")
PAST = re.compile(r"예전|옛날|작년|재작년|어릴 ?때|었었|았었|했었|전에는|전엔|아까는|그저께|엊그제|그땐|그때는|그 ?당시|까지는|까지만 ?해도"
                  r"|(?:어제|며칠 ?전|저번 ?(?:주|달)|지난 ?(?:주|달|번|해|밤|주말))(?:엔|에는|는|까지|에)?(?! ?부터|에서부터)(?=[ ,]|$)")
NOW_CONTRAST = re.compile(r"(?<![가-힣])(?:지금은|이제는|현재는|요즘은|오늘은)(?![가-힣])")
PAST_VERB = re.compile(r"(?:었|았|였|했)(?:는데|지만|고|어요|습니다|다)")
# 어절 끝 연결어미/종결어미 → scope 경계
CLAUSE_END = re.compile(r"(?:고|서|데|지만|며|면서|니까|더니|요|다|죠|음|함|네|구요|는데요)[,]?$")
CONJ_WORDS = {"그리고", "그런데", "근데", "하지만", "그래도", "반면", "그러나", "또", "및", "그리고요"}
CONDITIONAL_WORD = re.compile(r"(?:(?<!면서)면|면은|때|때는|때도|때마다|때만|경우|경우에|해도|여도|어도|아도)$")
# A(v1.2): "-거나" 병렬. 뒤 mention이 NEGATIVE로 명확할 때만 같이 NEGATIVE, 그 외는 버림
DISJ_END = re.compile(r"(?:거나|든지|든가|든)[,]?$")
PARTICLES = {"", "이", "가", "은", "는", "을", "를", "도", "만", "랑", "이랑", "하고", "하구", "와", "과", "및", "그리고",
             "또", "이나", "나", "까지", "에", "이며", ","}
COORD_WEAK = {"하고", "하구"}   # "기침하고 열은 없어요" — 동사/병렬 모호 → NEGATIVE 상속 금지


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    return re.sub(r"\s+", " ", text).strip()


@dataclass(frozen=True)
class Alias:
    alias_id: str
    evidence_id: str
    regex: re.Pattern
    kind: str
    allow: frozenset
    status: str | None
    implies_positive: tuple


@dataclass
class _Mention:
    start: int
    end: int
    h_end: int
    alias: Alias
    order: int


def _load_catalog_types(evidences_json=None) -> dict:
    path = config.check_path(evidences_json or config.EVIDENCES_JSON)
    raw = json.loads(Path(path).read_text())
    return {e: v["data_type"] for e, v in raw.items()}


def load_aliases(aliases_json=None, evidences_json=None) -> tuple[list[Alias], frozenset]:
    """alias 사전을 읽고 계약을 검증한다. 하나라도 어기면 AliasValidationError."""
    spec = json.loads(Path(aliases_json or ALIASES_JSON).read_text())
    dtype = _load_catalog_types(evidences_json)
    excluded = set(config.EXCLUDED_QUESTIONS)
    macros = spec.get("macros", {})
    history_ok = frozenset(spec.get("history_ok", []))

    def check_id(eid, where):
        if eid not in dtype:
            raise AliasValidationError(f"{where}: unknown evidence_id {eid!r}")
        if eid in excluded:
            raise AliasValidationError(f"{where}: excluded evidence_id {eid!r}")
        if dtype[eid] != "B":
            raise AliasValidationError(f"{where}: non-binary evidence_id {eid!r} (v1은 binary만)")

    for eid in history_ok:
        check_id(eid, "history_ok")
    aliases, seen = [], set()
    for i, ent in enumerate(spec.get("entries", [])):
        aid = ent.get("id") or f"#{i}"
        if aid in seen:
            raise AliasValidationError(f"duplicate alias id {aid!r}")
        seen.add(aid)
        eid = ent.get("evidence_id")
        check_id(eid, aid)
        pat = ent.get("pattern")
        if not isinstance(pat, str) or not pat:
            raise AliasValidationError(f"{aid}: empty pattern")
        for name, val in macros.items():
            pat = pat.replace("{" + name + "}", val)
        if re.search(r"\{[A-Z]+\}", pat):
            raise AliasValidationError(f"{aid}: unresolved macro in pattern")
        try:
            rx = re.compile(pat, re.IGNORECASE)
        except re.error as exc:
            raise AliasValidationError(f"{aid}: invalid regex ({exc})") from exc
        if rx.search("") is not None:
            raise AliasValidationError(f"{aid}: pattern matches empty string")
        kind = ent.get("kind", "noun")
        if kind not in ("noun", "phrase"):
            raise AliasValidationError(f"{aid}: bad kind {kind!r}")
        allow = frozenset(ent.get("allow", STATUSES))
        if not allow or not allow <= set(STATUSES):
            raise AliasValidationError(f"{aid}: bad allow {sorted(allow)}")
        status = ent.get("status")
        if status is not None and status not in STATUSES:
            raise AliasValidationError(f"{aid}: bad status {status!r}")
        implies = tuple(ent.get("implies_positive", ()))
        for j in implies:
            check_id(j, f"{aid}.implies_positive")
        aliases.append(Alias(aid, eid, rx, kind, allow, status, implies))
    if not aliases:
        raise AliasValidationError("no alias entries")
    return aliases, history_ok


def load_negative_policy(supported: frozenset, path=None) -> frozenset:
    """NEGATIVE 허용 evidence 집합. 지원 evidence 전부를 정확히 한 번씩 명시해야 한다(누락·초과·중복 금지)."""
    spec = json.loads(Path(path or NEGATIVE_POLICY_JSON).read_text())
    if spec.get("default") != "ABSTAIN":
        raise AliasValidationError("negative_policy default must be ABSTAIN")
    seen, allowed = set(), set()
    for ent in spec.get("evidence", []):
        eid = ent.get("evidence_id")
        if eid in seen:
            raise AliasValidationError(f"negative_policy: duplicate {eid!r}")
        seen.add(eid)
        if not isinstance(ent.get("negative_allowed"), bool) or not ent.get("reason"):
            raise AliasValidationError(f"negative_policy: {eid!r} needs bool negative_allowed and reason")
        if ent["negative_allowed"]:
            allowed.add(eid)
    if seen != set(supported):
        raise AliasValidationError(f"negative_policy must cover supported evidence exactly: "
                                   f"missing={sorted(set(supported) - seen)} extra={sorted(seen - set(supported))}")
    return frozenset(allowed)


def _sentences(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in re.finditer(r"[.!?\n]+|(?<=[가-힣][요다죠]) ", text):
        if text[start:m.end()].strip():
            spans.append((start, m.end()))
        start = m.end()
    if text[start:].strip():
        spans.append((start, len(text)))
    return spans


def _scope_after(text: str, pos: int, bound: int) -> str:
    """mention 끝(pos)부터 bound까지 중 첫 절 경계까지의 텍스트."""
    seg = text[pos:bound]
    words = seg.split(" ")
    out = []
    for k, w in enumerate(words):
        if k > 0 and w in CONJ_WORDS:
            break
        out.append(w)
        if w and (CLAUSE_END.search(w) or DISJ_END.search(w) or w.endswith(",")):
            break
    return " ".join(out)


class IntakeMapper:
    def __init__(self, aliases_json=None, evidences_json=None, negative_policy_json=None):
        self.aliases, self.history_ok = load_aliases(aliases_json, evidences_json)
        self.supported = frozenset(a.evidence_id for a in self.aliases)
        self.negative_allowed = load_negative_policy(self.supported, negative_policy_json)

    # ---- 1) alias 매칭: 겹치면 (시작 빠른 것, 긴 것, 사전 순) 우선 ----
    def _mentions(self, text: str) -> list[_Mention]:
        cands = []
        for order, a in enumerate(self.aliases):
            for m in a.regex.finditer(text):
                if m.end() <= m.start():
                    continue
                h_end = m.end("h") if "h" in a.regex.groupindex and m.group("h") is not None else m.end()
                cands.append(_Mention(m.start(), m.end(), h_end, a, order))
        cands.sort(key=lambda c: (c.start, -(c.end - c.start), c.order))
        kept, last_end = [], -1
        for c in cands:
            if c.start >= last_end:
                kept.append(c)
                last_end = c.end
        return kept

    # ---- 2) mention 하나의 status 판정: "POSITIVE" | "NEGATIVE" | "INHERIT" | "INHERIT_POS_ONLY" | None(버림) ----
    def _judge(self, text: str, m: _Mention, bound: int, sent: str, s_start: int, is_question: bool,
               has_next: bool) -> str | None:
        a = m.alias
        if is_question or OTHER_PERSON.search(sent) or SENT_HEDGE.search(sent):
            return None
        if a.evidence_id not in self.history_ok and (
                PAST.search(sent) or (NOW_CONTRAST.search(sent) and PAST_VERB.search(sent))):
            return None
        inner = text[m.h_end:m.end]
        after = _scope_after(text, m.end, bound)
        zone = IDIOM.sub(" ", (inner + " " + after)).strip()
        if HEDGE.search(zone) or "?" in zone:
            return None
        if any(CONDITIONAL_WORD.search(w.rstrip(",")) for w in after.split(" ") if w):
            return None
        if EVER.search(zone) and a.evidence_id not in self.history_ok:
            return None
        if PERSIST.search(zone):
            if a.status == "NEGATIVE":
                return None
            return "POSITIVE"
        if IMPROVED.search(zone):
            return None
        if NOT_ONLY.search(zone):
            return None
        after_words = [w for w in after.split(" ") if w]
        if after_words and DISJ_END.search(after_words[-1]):
            # "A하거나 B하지는 않아요": 뒤 mention이 NEGATIVE일 때만 상속, 없거나 POSITIVE면 버림
            return "INHERIT_NEG_ONLY" if has_next else None
        pre_neg = bool(PRE_NEG.search(text[:m.start]))
        n_neg = sum(1 for cue in NEG_CUES if cue.search(zone)) + pre_neg
        if n_neg and PARTIAL.search(zone):
            return None
        if n_neg >= 2:                                   # 이중부정("없지 않아요") → 불확실
            return None
        if a.status is not None:
            return None if n_neg else a.status
        if n_neg == 1:
            return "NEGATIVE"
        # 부정 단서 없음: 명사 alias 뒤가 조사·병렬어뿐이면 다음 mention의 술어를 상속
        if a.kind == "noun":
            toks = [t for t in re.split(r"[ ,.!]+", after) if t]
            if has_next and all(t in PARTICLES for t in toks):
                return "INHERIT_POS_ONLY" if any(t in COORD_WEAK for t in toks) else "INHERIT"
            # 도치("안나요 열은", "없어요, 열은"): 문장 끝 명사인데 술어가 앞에 있음 → 극성 판단 불가, 버림
            before = text[:m.start].rstrip()
            if not has_next and all(t in PARTICLES for t in toks) and before and before[-1] not in ".!?\n":
                return None
        return "POSITIVE"

    def extract(self, text: str) -> list[dict]:
        text = normalize(text)
        if not text:
            return []
        mentions = self._mentions(text)
        results: list[tuple[int, dict]] = []
        for s_start, s_end in _sentences(text):
            sent = text[s_start:s_end]
            is_question = bool(QUESTION_END.search(sent.rstrip()))
            ms = [m for m in mentions if s_start <= m.start < s_end]
            judged: list[str | None] = [None] * len(ms)
            for i in range(len(ms) - 1, -1, -1):                     # 오른쪽부터: 병렬 상속용
                bound = ms[i + 1].start if i + 1 < len(ms) else s_end
                st = self._judge(text, ms[i], bound, sent, s_start, is_question, i + 1 < len(ms))
                if st in ("INHERIT", "INHERIT_POS_ONLY", "INHERIT_NEG_ONLY"):
                    nxt = judged[i + 1] if i + 1 < len(ms) else None
                    if nxt is None or (st == "INHERIT_POS_ONLY" and nxt != "POSITIVE") \
                            or (st == "INHERIT_NEG_ONLY" and nxt != "NEGATIVE"):
                        st = None
                    else:
                        st = nxt
                judged[i] = st
            for i, (m, st) in enumerate(zip(ms, judged)):
                if st is None or st not in m.alias.allow:
                    continue
                if st == "NEGATIVE" and m.alias.evidence_id not in self.negative_allowed:
                    continue                                   # v1.2: NEGATIVE는 allowlist evidence만
                bound = ms[i + 1].start if i + 1 < len(ms) else s_end
                span_end = m.end if st == "POSITIVE" else m.end + len(_scope_after(text, m.end, bound).rstrip(" ,"))
                matched = text[m.start:span_end].strip(" ,.")
                src = "ALIAS_NEGATION" if st == "NEGATIVE" else "ALIAS"
                results.append((m.start, dict(evidence_id=m.alias.evidence_id, status=st, matched_text=matched,
                                              source=src, confidence="HIGH", alias_id=m.alias.alias_id)))
                if st == "POSITIVE":
                    for j in m.alias.implies_positive:
                        results.append((m.start, dict(evidence_id=j, status="POSITIVE", matched_text=matched,
                                                      source="ALIAS_IMPLIED", confidence="HIGH",
                                                      alias_id=m.alias.alias_id)))
        # ---- 3) 같은 evidence 중복 제거, status 충돌이면 둘 다 버림 ----
        by_id: dict[str, list[tuple[int, dict]]] = {}
        for pos, r in results:
            by_id.setdefault(r["evidence_id"], []).append((pos, r))
        out = []
        for eid, lst in by_id.items():
            if len({r["status"] for _, r in lst}) > 1:
                continue
            lst.sort(key=lambda x: (x[0], x[1]["source"] == "ALIAS_IMPLIED"))
            out.append(lst[0])
        out.sort(key=lambda x: (x[0], int(x[1]["evidence_id"][2:])))
        return [r for _, r in out]


_DEFAULT: IntakeMapper | None = None


def extract(text: str) -> list[dict]:
    """기본 alias 사전으로 추출(모듈 단위 캐시)."""
    global _DEFAULT
    if _DEFAULT is None:
        _DEFAULT = IntakeMapper()
    return _DEFAULT.extract(text)
