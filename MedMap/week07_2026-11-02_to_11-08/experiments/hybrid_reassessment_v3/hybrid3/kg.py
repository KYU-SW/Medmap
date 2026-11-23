"""기능 D: 근거 그래프. 기존 EXP-01b 그래프는 읽기만 하고(전역 캐시라 수정 금지), 그 위에 덧층 노드·간선을 둔다.
방향 판단은 이 그래프에서 '검사 노드 → 결과 상태 노드 → 가설 노드' 경로로 찾은 검증 간선의 속성(적용 조건·출처)으로만 한다.
간선을 끄면 그 간선에 기대는 판단이 사라진다(ablation 용 disabled_relations, use_base)."""
from __future__ import annotations

import json
from collections import deque
from pathlib import Path

from .concepts import LX, RLX

HERE = Path(__file__).resolve().parents[1]
OVERLAY = HERE / "knowledge" / "v3_graph_overlay.json"
VERIFIED = {"SOURCE_TEXT_CHECKED", "SOURCE_TEXT_CHECKED_SCOPE_DIFFERENT"}
BASE_ROLE = {"SUGGESTS": "ASSOCIATED_WITH", "EVALUATES": "EVALUATES_HYPOTHESIS", "RISK_FACTOR_FOR": "ASSOCIATED_WITH", "DIFFERENTIAL_OF": "DIFFERENTIAL_OF"}


class EvidenceGraph:
    def __init__(self, overlay: Path = OVERLAY, disabled_relations=(), use_base: bool = True, catalog_path: Path | None = None):
        spec = json.loads(Path(overlay).read_text(encoding="utf-8"))
        self.spec = spec
        cpath = catalog_path or (Path(overlay).parent / spec["relation_catalog"]).resolve()
        self.catalog = RLX.load(cpath)                                # P2 적재 검사(인용·출처·관계 종류) 그대로 사용
        self.catalog_path = str(cpath)
        self.base = LX._graph() if use_base else None
        self.nodes, self.edges = {}, []
        if self.base:
            for n, v in self.base.nodes.items():
                self.nodes[n] = {"kind": v.kind, "label": v.label, "origin": "EXP01B_GRAPH"}
        for n in spec["extra_nodes"]:
            self.nodes[n["id"]] = {"kind": n["kind"], "label": n["label"], "origin": "V3_OVERLAY"}
        for f, test in spec["result_states"].items():
            sid = f"STATE:{f}"
            self.nodes[sid] = {"kind": "RESULT_STATE", "label": f, "origin": "V3_OVERLAY"}
            if test in self.nodes:
                self.edges.append({"src": test, "dst": sid, "relation_type": "HAS_RESULT_STATE", "evidence_status": "STRUCTURAL", "origin": "V3_OVERLAY"})
        for f, node in spec.get("finding_links", {}).items():
            if node in self.nodes:
                self.edges.append({"src": f"STATE:{f}", "dst": node, "relation_type": "DESCRIBES_FINDING", "evidence_status": "STRUCTURAL", "origin": "V3_OVERLAY"})
        self.disabled = set(disabled_relations)
        for r in self.catalog["relations"]:
            sid = f"STATE:{r['finding']}"
            if r["id"] in self.disabled or sid not in self.nodes or r["hypothesis"] not in self.nodes:
                continue
            self.edges.append({"src": sid, "dst": r["hypothesis"], "relation_type": r["relation"], "relation_id": r["id"], "source_concept": sid, "target_concept": r["hypothesis"],
                               "clinical_context": r["applicability"], "applicability_conditions": {"by_context": r["by_context"], "requires_context": r.get("requires_context", [])},
                               "provenance": [{**self.catalog["sources"][e["source"]], **{k: e[k] for k in ("location", "summary", "quote")}} for e in r["evidence"]],
                               "evidence_status": "VERIFIED" if r["verification"] in VERIFIED else "CANDIDATE", "verification": r["verification"],
                               "exceptions": r.get("exceptions", ""), "relation": r, "origin": "VERIFIED_RELATION_CATALOG"})
        self.out = {}
        for e in self.edges:
            self.out.setdefault(e["src"], []).append(e)

    def concept_node(self, concept: str) -> str:
        n = self.spec["concept_nodes"].get(concept) or (concept if concept.startswith("HP:") else "")
        return n if n in self.nodes else ""

    def evidence_paths(self, finding: str, hypothesis: str) -> list:
        """결과를 낸 검사 노드에서 가설 노드까지 BFS. 방향 간선은 VERIFIED 만. 반환 [{path, edge}]"""
        start = self.spec["result_states"].get(finding)
        if not start or start not in self.nodes or hypothesis not in self.nodes:
            return []
        target_state = f"STATE:{finding}"
        found, q, seen = [], deque([(start, [start])]), {start}
        while q:
            n, path = q.popleft()
            for e in self.out.get(n, []):
                if e["relation_type"] == "HAS_RESULT_STATE" and e["dst"] != target_state:
                    continue                                              # 다른 결과 상태로는 가지 않음
                if e["dst"] == hypothesis and e.get("evidence_status") == "VERIFIED":
                    found.append({"path": path + [f"-{e['relation_type']}({e.get('relation_id', '')})->", e["dst"]], "edge": e})
                elif e["dst"] not in seen and e["relation_type"] in ("HAS_RESULT_STATE",):
                    seen.add(e["dst"])
                    q.append((e["dst"], path + [f"-{e['relation_type']}->", e["dst"]]))
        return found

    def base_context(self, node: str, hypothesis: str) -> list:
        """기존 그래프 간선(표시 전용, 방향 판단에 쓰지 않음)."""
        if not self.base or node not in self.base.nodes:
            return []
        return [{"src": e.src, "graph_rel": e.rel, "dst": e.dst, "v3_role": BASE_ROLE.get(e.rel, "NOT_USED"), "source": str(e.source)[:140], "used_for_direction": False}
                for e in self.base.out_edges(node) if e.dst == hypothesis]

    def stats(self) -> dict:
        from collections import Counter
        return {"nodes": len(self.nodes), "overlay_nodes": sum(v["origin"] == "V3_OVERLAY" for v in self.nodes.values()),
                "edges_v3": dict(Counter(e["relation_type"] for e in self.edges)), "verified_direction_edges": sum(e.get("evidence_status") == "VERIFIED" for e in self.edges),
                "disabled_relations": sorted(self.disabled), "base_graph": bool(self.base)}
