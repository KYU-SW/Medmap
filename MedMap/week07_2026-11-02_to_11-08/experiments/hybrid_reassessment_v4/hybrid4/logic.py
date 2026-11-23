"""4값 조건 논리(TRUE/FALSE/UNKNOWN/CONFLICT)와 관계 카탈로그의 선언형 변환.
의학 조건을 새로 만들지 않는다. P2 카탈로그의 우선순위 규칙 목록을 다음으로 나눈다.
  EXCLUSION GATE  : 방향 규칙보다 앞선 비방향 규칙(적용 제외·불확실 처리). TRUE 면 그 결과로 차단
  REQUIRED        : 모든 방향 경로에 공통인 조건(AND)
  ALTERNATIVE     : 방향 경로별 나머지 조건(OR of AND)
  FALLBACK        : 방향 규칙 뒤의 비방향 규칙(방향 경로가 성립하지 않을 때만)
판단 결과(SUPPORT 등)는 논리값과 별개로 관리한다."""
from __future__ import annotations

from dataclasses import dataclass, field

T, F, U, C = "TRUE", "FALSE", "UNKNOWN", "CONFLICT"
DIRECTIONAL = ("SUPPORT", "WEAKEN")


# ---------- 조건 노드 ----------
@dataclass(frozen=True)
class Atom:
    key: str
    allowed: tuple

    def to_dict(self):
        return {"op": "ATOM", "key": self.key, "allowed": list(self.allowed)}


@dataclass(frozen=True)
class And:
    items: tuple

    def to_dict(self):
        return {"op": "AND", "items": [i.to_dict() for i in self.items]}


@dataclass(frozen=True)
class Or:
    items: tuple

    def to_dict(self):
        return {"op": "OR", "items": [i.to_dict() for i in self.items]}


@dataclass(frozen=True)
class Not:
    item: object

    def to_dict(self):
        return {"op": "NOT", "item": self.item.to_dict()}


def from_dict(d):
    op = d["op"]
    if op == "ATOM":
        return Atom(d["key"], tuple(d["allowed"]))
    if op == "AND":
        return And(tuple(from_dict(x) for x in d["items"]))
    if op == "OR":
        return Or(tuple(from_dict(x) for x in d["items"]))
    if op == "NOT":
        return Not(from_dict(d["item"]))
    raise ValueError(op)


# ---------- 평가 ----------
@dataclass
class Fact:
    """조건 키 하나의 환자 사실. status: FOUND/NOT_FOUND/CONFLICT. sources: 근거 증거·기록 ID."""
    key: str
    status: str
    value: object = None
    values: tuple = ()
    sources: tuple = ()


def eval_cond(node, facts: dict) -> dict:
    """반환 {value, op, children|key..., used, missing, conflicts}. 단락이 일어나도 다른 자식의 UNKNOWN/CONFLICT 기록은 남긴다."""
    if isinstance(node, Atom):
        f = facts.get(node.key) or Fact(node.key, "NOT_FOUND")
        if f.status == "CONFLICT":
            v = C
        elif f.status != "FOUND" or f.value is None:
            v = U
        else:
            v = T if f.value in node.allowed else F
        return {"op": "ATOM", "key": node.key, "allowed": list(node.allowed), "value": v, "observed": f.value if f.status == "FOUND" else list(f.values),
                "sources": list(f.sources), "missing": [node.key] if v == U else [], "conflicts": [{"key": node.key, "values": list(f.values), "sources": list(f.sources)}] if v == C else []}
    if isinstance(node, Not):
        r = eval_cond(node.item, facts)
        return {"op": "NOT", "value": {T: F, F: T}.get(r["value"], r["value"]), "children": [r], "missing": r["missing"], "conflicts": r["conflicts"]}
    kids = [eval_cond(i, facts) for i in node.items]
    vals = [k["value"] for k in kids]
    if isinstance(node, And):
        v = F if F in vals else C if C in vals else U if U in vals else T                 # FALSE 가 결정적. 그 외엔 CONFLICT > UNKNOWN
    else:
        v = T if T in vals else C if C in vals else U if U in vals else F                 # TRUE 가 결정적. 모두 FALSE 일 때만 FALSE
    out = {"op": "AND" if isinstance(node, And) else "OR", "value": v, "children": kids,
           "missing": sorted({m for k in kids for m in k["missing"]}), "conflicts": [c for k in kids for c in k["conflicts"]]}
    if v == T and isinstance(node, Or):
        out["true_paths"] = [i for i, k in enumerate(kids) if k["value"] == T]
    return out


def depends_on_conflict(res: dict) -> bool:
    """TRUE 로 판정된 경로가 CONFLICT 사실에 기대는가(TRUE 자식 안에 CONFLICT 원자가 있으면 그 경로 결론을 쓰지 않는다)."""
    if res["op"] == "ATOM":
        return res["value"] == C
    if res["op"] == "OR" and res["value"] == T:
        return all(depends_on_conflict(res["children"][i]) for i in res["true_paths"])
    return any(depends_on_conflict(k) for k in res.get("children", []) if res["op"] != "OR" or k["value"] == T)


# ---------- 카탈로그 변환 ----------
def _rule_cond(rule) -> tuple:
    return tuple(Atom(k, tuple(v)) for k, v in rule["when"].items())


@dataclass
class Structured:
    relation_id: str
    gates: list = field(default_factory=list)        # [{cond, outcome, note, unknown_policy, origin}]
    required: list = field(default_factory=list)     # [Atom]
    alternatives: list = field(default_factory=list) # [[Atom]] (경로별 AND)
    directional_outcome: str | None = None
    fallbacks: list = field(default_factory=list)    # [{cond, outcome, note}]
    unconditional: dict | None = None                # 조건 없는 단일 결과(평가 관계 등)

    def tree(self):
        req = And(tuple(self.required)) if self.required else None
        alt = Or(tuple(And(tuple(p)) for p in self.alternatives)) if self.alternatives else None
        return req, alt

    def to_dict(self):
        req, alt = self.tree()
        return {"relation_id": self.relation_id, "exclusion_gates": [{"cond": And(tuple(g["cond"])).to_dict(), "outcome": g["outcome"], "note": g["note"], "unknown_policy": g["unknown_policy"], "origin": g["origin"]} for g in self.gates],
                "required": req.to_dict() if req else None, "alternatives": alt.to_dict() if alt else None, "directional_outcome": self.directional_outcome,
                "fallbacks": [{"cond": And(tuple(f["cond"])).to_dict(), "outcome": f["outcome"], "note": f["note"]} for f in self.fallbacks], "unconditional": self.unconditional}


def structure(rel: dict, extra_gates=()) -> Structured:
    """P2 by_context(우선순위 목록) → 분리 구조. 규칙 내용(키·허용값·결과)은 그대로 옮긴다."""
    rules = rel["by_context"]
    s = Structured(rel["id"])
    s.gates.extend(extra_gates)
    di = [i for i, r in enumerate(rules) if r["direction"] in DIRECTIONAL]
    if not di:
        if len(rules) == 1 and not rules[0]["when"]:
            s.unconditional = {"outcome": rules[0]["direction"], "note": rules[0].get("note", "")}
        else:
            s.fallbacks = [{"cond": list(_rule_cond(r)), "outcome": r["direction"], "note": r.get("note", "")} for r in rules]
        return s
    if len({rules[i]["direction"] for i in di}) != 1:
        raise ValueError(f"{rel['id']}: 방향 규칙의 결과가 둘 이상")
    s.directional_outcome = rules[di[0]]["direction"]
    for r in rules[:di[0]]:
        s.gates.append({"cond": list(_rule_cond(r)), "outcome": r["direction"], "note": r.get("note", ""), "unknown_policy": "HOLD", "origin": "CATALOG_PRIORITY_RULE"})
    paths = [list(_rule_cond(rules[i])) for i in di]
    common = [a for a in paths[0] if all(a in p for p in paths[1:])]
    s.required = common
    s.alternatives = [[a for a in p if a not in common] for p in paths] if len(paths) > 1 else []
    if len(paths) == 1:
        s.alternatives = []
    for r in rules[di[-1] + 1:]:
        s.fallbacks.append({"cond": list(_rule_cond(r)), "outcome": r["direction"], "note": r.get("note", "")})
    if any(not (di[0] <= i <= di[-1]) for i in range(len(rules)) if rules[i]["direction"] in DIRECTIONAL) or any(rules[i]["direction"] not in DIRECTIONAL for i in range(di[0], di[-1] + 1)):
        raise ValueError(f"{rel['id']}: 방향 규칙 사이에 비방향 규칙이 끼어 있음(분리 불가)")
    return s


def decide(s: Structured, facts: dict) -> dict:
    """분리 구조 평가. 반환 {direction, stage, gates, required, alternatives, fallbacks, missing, conflicts, note}."""
    out = {"relation_id": s.relation_id, "gates": [], "required": None, "alternatives": None, "fallbacks": [], "missing": [], "conflicts": [], "note": "", "stage": ""}

    def fin(direction, stage, note=""):
        out.update(direction=direction, stage=stage, note=note)
        allr = [g["eval"] for g in out["gates"] if g["unknown_policy"] == "HOLD"] + [x for x in (out["required"], out["alternatives"]) if x] + [f["eval"] for f in out["fallbacks"]]
        out["missing"] = sorted({m for r in allr for m in r["missing"]})
        out["optional_unchecked"] = sorted({m for g in out["gates"] if g["unknown_policy"] != "HOLD" for m in g["eval"]["missing"]})   # 명시된 경우만 막는 조건: 부족 정보 아님
        allr = allr + [g["eval"] for g in out["gates"] if g["unknown_policy"] != "HOLD"]
        seen = []
        for r in allr:
            for c in r["conflicts"]:
                if c not in seen:
                    seen.append(c)
        out["conflicts"] = seen
        return out
    if s.unconditional:
        return fin(s.unconditional["outcome"], "UNCONDITIONAL", s.unconditional["note"])
    hold = []
    for g in s.gates:
        r = eval_cond(And(tuple(g["cond"])), facts)
        out["gates"].append({"outcome": g["outcome"], "note": g["note"], "unknown_policy": g["unknown_policy"], "origin": g["origin"], "eval": r})
        if r["value"] == T:                                                      # 비방향 결과만 반환하므로 앞 게이트 미결이어도 방향 판단은 생기지 않음
            return fin(g["outcome"], "EXCLUSION_GATE_TRUE" + ("_EARLIER_GATE_UNRESOLVED" if hold else ""), g["note"])
        if r["value"] in (U, C) and g["unknown_policy"] == "HOLD":
            hold.append(r["value"])
    if s.directional_outcome:
        req, alt = s.tree()
        rr = eval_cond(req, facts) if req else {"op": "AND", "value": T, "children": [], "missing": [], "conflicts": []}
        ar = eval_cond(alt, facts) if alt else {"op": "OR", "value": T, "children": [], "missing": [], "conflicts": []}
        out["required"], out["alternatives"] = rr, (ar if alt else None)
        v = F if F in (rr["value"], ar["value"]) else C if C in (rr["value"], ar["value"]) else U if U in (rr["value"], ar["value"]) else T
        if v == T:
            if depends_on_conflict(rr) or (alt and depends_on_conflict(ar)):
                return fin("INSUFFICIENT_EVIDENCE", "TRUE_PATH_DEPENDS_ON_CONFLICT")
            if hold:
                return fin("INSUFFICIENT_EVIDENCE", "EXCLUSION_GATE_UNRESOLVED")          # 제외 여부를 모르면 방향 판단 안 함
            return fin(s.directional_outcome, "DIRECTIONAL_PATH_TRUE")
        if v in (U, C):
            for f in s.fallbacks:                                                    # 방향 경로 미결이어도 대체 비방향 결과가 확정되면 사용
                fr = eval_cond(And(tuple(f["cond"])), facts)
                out["fallbacks"].append({"outcome": f["outcome"], "note": f["note"], "eval": fr})
                if fr["value"] == T:
                    return fin(f["outcome"], "FALLBACK_TRUE", f["note"])
            return fin("INSUFFICIENT_EVIDENCE", "DIRECTIONAL_PATH_CONFLICT" if v == C else "DIRECTIONAL_PATH_UNKNOWN")
    for f in s.fallbacks:
        fr = eval_cond(And(tuple(f["cond"])), facts)
        out["fallbacks"].append({"outcome": f["outcome"], "note": f["note"], "eval": fr})
        if fr["value"] == T:
            return fin(f["outcome"], "FALLBACK_TRUE", f["note"])
    pend = [f["eval"]["value"] for f in out["fallbacks"]]
    if C in pend:
        return fin("INSUFFICIENT_EVIDENCE", "FALLBACK_CONFLICT")
    if U in pend:
        return fin("INSUFFICIENT_EVIDENCE", "FALLBACK_UNKNOWN")
    return fin("NOT_APPLICABLE", "NO_PATH_MATCHED", "관계의 적용 범위 밖")
