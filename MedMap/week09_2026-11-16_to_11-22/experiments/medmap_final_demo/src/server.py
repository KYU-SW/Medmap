"""최종발표 로컬 시연 서버(파이썬 표준 라이브러리 http.server, 127.0.0.1 전용). 화면은 web/index.html.
노출 정책(1차·2차 심사 반영, 요청 시점 기준): 타임라인은 조회 시점까지 도착한 기록의 메타데이터(항목·상태·시각·출처, 다른 환자 기록은 항목명·시각만)만,
근거 문장은 AI 입력으로 실제 사용한 버전(used_content)만 보낸다. prev 가 as_of 보다 나중이면 diff 에 그 시점 정보가 들어간다(요청자가 직접 조회 가능한 정보).
모든 연구용 점수는 요청마다 실제 엔진(replay·assess)과 기존 D 모델(겹 0, 읽기 전용)로 계산한다. 미리 계산한 값을 보여주지 않는다.
사용: python server.py [port] [--no-model] [--compare RUN_ID]   (--no-model: 모델 없이 MODEL_UNAVAILABLE 시연)
"""
from __future__ import annotations

import json
import mimetypes
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from medmap_demo.assess import assess, counterfactual, diff, kg_status, provenance_graph  # noqa: E402
from medmap_demo.events import EventStore  # noqa: E402
from medmap_demo.model_adapter import DModel  # noqa: E402
from medmap_demo.naive import naive_inputs  # noqa: E402
from medmap_demo.replay import replay  # noqa: E402
from medmap_demo.scenarios import demo_case  # noqa: E402

WEB = ROOT / "web"
FONTS = ROOT.parents[1] / "medmap-web" / "src" / "doctor" / "fonts" / "wanted-sans"    # 기존 의사 화면 폰트(읽기 전용)
CASE, RAWS, STEPS = demo_case()
STORE = EventStore().extend(RAWS)
MODEL = None
KG = None
COMPARE_RUN = None


def checks(t: datetime) -> dict:
    """현재 조회 시점의 기술 검증(실제 계산)."""
    rp = replay(STORE, CASE, t)
    a = assess(rp, MODEL)
    snap = assess(replay(STORE.snapshot(t), CASE, t), MODEL)
    again = assess(replay(EventStore().extend(list(reversed(RAWS))), CASE, t), MODEL)
    used_future = sum(1 for i in rp.usable() if i.used.recorded_at > t or i.used.available_at > t)
    held_scored = sum(1 for r in a["rows"] if r["state"] != "USABLE" and r["assessment"]["status"] == "SCORED")
    held_no_reason = sum(1 for r in a["rows"] if r["state"] != "USABLE" and not r["reasons"])
    sup = sum(1 for i in rp.items for _, role in i.versions if role == "SUPERSEDED")
    dup = sum(1 for i in rp.items for _, role in i.versions if role == "DUPLICATE")
    base_used = naive_inputs(STORE, CASE, t)
    base_bad = {"future": sum(1 for e, _ in base_used if e.recorded_at > t or (e.available_at and e.available_at > t)),
                "pending_or_order": sum(1 for e, _ in base_used if e.status in ("ORDERED", "PENDING", "CANCELLED")),
                "other_patient": sum(1 for e, _ in base_used if e.patient_id != CASE.patient_id), "n_inputs": len(base_used)}
    return {"future_records_hidden": rp.n_unknown_future_records, "future_info_used": used_future, "duplicates_removed": dup,
            "superseded_versions": sup, "past_replay_matches_snapshot": a == snap, "input_order_independent": a == again,
            "held_with_score": held_scored, "held_without_reason": held_no_reason, "base_same_time": base_bad}


def api(path: str, q: dict):
    g = lambda k: q.get(k, [None])[0]   # noqa: E731
    if path == "/api/case":
        return {"patient_id": CASE.patient_id, "hypothesis": CASE.hypothesis_text, "feeds": CASE.feed_ids, "synthetic": True,
                "steps": [{"name": n, "as_of": t} for n, t in STEPS], "n_records_total": len(STORE.events),
                "model": {"status": MODEL.status if MODEL else "MODEL_UNAVAILABLE",
                                                        "id": MODEL.model_id if MODEL and MODEL.pipe else None,
                                                        "error": MODEL.error if MODEL else "시연 옵션 --no-model"},
                "kg": KG}
    if path == "/api/replay":
        t = datetime.fromisoformat(g("as_of"))
        rp = replay(STORE, CASE, t)
        a = assess(rp, MODEL)
        known = sorted((e for e in STORE.events.values() if e.recorded_at <= t and (e.patient_id == CASE.patient_id or e.feed_id in CASE.feed_ids)),
                       key=lambda e: (e.recorded_at, e.event_id))
        role = {v["event_id"]: v["role"] for i in rp.to_dict()["items"] for v in i["versions"]}
        timeline = [{"event_id": e.event_id, "item": e.item, "status": e.status, "recorded_at": e.recorded_at.isoformat(),
                     "available_at": e.available_at.isoformat() if e.available_at else None, "has_result": e.status in ("AVAILABLE", "CORRECTED", "INVALID"),
                     "source": e.source if e.patient_id == CASE.patient_id else None, "other_patient": e.patient_id != CASE.patient_id,
                     "prev_version_id": e.prev_version_id, "role": role.get(e.event_id)} for e in known]
        out = {"assessment": a, "timeline": timeline, "n_unknown_future_records(감사용 건수, 내용 미전송)": rp.n_unknown_future_records,
               "checks": checks(t), "graph": provenance_graph(rp)["stats"]}
        if g("prev"):
            out["diff"] = diff(assess(replay(STORE, CASE, datetime.fromisoformat(g("prev"))), MODEL), a)
            out["prev_as_of"] = g("prev")
        return out
    if path == "/api/counterfactual":
        return counterfactual(STORE, CASE, datetime.fromisoformat(g("as_of")), MODEL, g("exclude"))
    if path == "/api/compare":
        f = ROOT / "outputs" / f"compare_{COMPARE_RUN}" / "compare.json" if COMPARE_RUN else None
        return json.loads(f.read_text(encoding="utf-8")) if f and f.exists() else {"status": "NOT_RUN", "run_id": COMPARE_RUN}
    raise KeyError(path)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        try:
            if u.path.startswith("/api/"):
                body = json.dumps(api(u.path, parse_qs(u.query)), ensure_ascii=False, default=str).encode()
                return self._send(200, body, "application/json; charset=utf-8")
            if u.path.startswith("/fonts/"):
                f = (FONTS / u.path[len("/fonts/"):]).resolve()
                if FONTS.resolve() not in f.parents or not f.is_file():
                    return self._send(404, b"not found", "text/plain")
                return self._send(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "font/woff2")
            f = WEB / ("index.html" if u.path in ("/", "") else u.path.lstrip("/"))
            f = f.resolve()
            if WEB.resolve() not in f.parents or not f.is_file():
                return self._send(404, b"not found", "text/plain")
            return self._send(200, f.read_bytes(), (mimetypes.guess_type(f.name)[0] or "text/plain") + "; charset=utf-8")
        except Exception as ex:                                     # noqa: BLE001 — 오류를 화면에 그대로 노출
            self._send(500, json.dumps({"error": f"{type(ex).__name__}: {ex}"}, ensure_ascii=False).encode(), "application/json; charset=utf-8")


def main():
    global MODEL, KG, COMPARE_RUN
    args = sys.argv[1:]
    if "--compare" in args:
        COMPARE_RUN = args[args.index("--compare") + 1]
        args = [a for a in args if a not in ("--compare", COMPARE_RUN)]
    port = int(next((a for a in args if a.isdigit()), 8765))
    MODEL = None if "--no-model" in args else DModel().load()
    KG = kg_status()
    print("model:", MODEL.status if MODEL else "MODEL_UNAVAILABLE(--no-model)", MODEL.error if MODEL else "")
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    print(f"MedMap 시연: http://127.0.0.1:{port}/  (127.0.0.1 전용)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
