"""§10 연구용 Doctor Preview(정적 HTML, 단일 파일) — outputs/end_to_end_cases.json 을 그대로 담아 보여 준다. 제품·8010·master 와 연결 없음.
디자인 토큰은 master medmap-web/src/doctor/doctor.css 의 값을 참고(파일 복사·import 없음, 글꼴 파일 미포함 — 시스템 글꼴 대체).
질환 이름·점수·순위는 넣지 않는다(블라인드 4단계는 제품 Doctor 화면 공개 단계에서만). 출력: preview/index.html"""
from __future__ import annotations

import json

import s30_common as S

KEEP = ("item_id", "category", "category_name", "category_reasons", "raw_span", "span_start", "span_end", "canonical_id", "ontology_id", "label_ko",
        "assertion", "temporality", "onset_text", "current_status", "experiencer", "model_supported", "mapping_status", "uncertainty_reason")


def slim(case: dict) -> dict:
    p = case["packet_before_confirmation"]
    items = [{**{k: it.get(k) for k in KEEP},
              "stage_a": it["eligibility"]["eligible"], "target": it["eligibility"]["target_evidence"],
              "blocking": it["eligibility"]["blocking_reasons"]} for it in p["items"]]
    return {"id": case["case_id"], "set": case["set"], "type": case["type"], "text": case["text"], "items": items,
            "sections_before": p["sections"], "sections_after": case["sections_after_policy_stage_a"],
            "mi_before": {k: p["model_input"][k] for k in ("applied", "auto_input_count", "stage_a_technically_eligible", "stage_b_clinician_confirmed", "patient_state_delta")},
            "mi_after": {k: case["model_input_after_policy_stage_a"][k] for k in ("applied", "auto_input_count", "stage_a_technically_eligible", "stage_b_clinician_confirmed", "patient_state_delta")},
            "diff": case["confirmation_diff_policy_stage_a"],
            "blind": {k: case["blind_workflow"][k] for k in ("stage2_pending_assessment", "stage2_pending_next_information", "stage3_wd_unchanged", "violations")}}


HTML = r"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>STEP30 Doctor Preview</title>
<style>
:root{--dr-canvas:#F3F4F7;--dr-surface:#FFFFFF;--dr-surface-2:#F7F8FA;--dr-hairline:#E3E6EB;--dr-hairline-strong:#CBD0D8;--dr-ink:#141A2E;--dr-ink-muted:#3E4659;--dr-ink-subtle:#5E6678;--dr-accent:#4B3FC9;--dr-accent-strong:#3A2FA8;--dr-accent-soft:#EFEDFC;--dr-accent-line:#C9C3F3;--dr-neutral-soft:#EDF0F4;--dr-r:14px;--dr-r-sm:10px;--dr-shadow:0 1px 2px rgba(20,26,46,.04),0 4px 16px rgba(20,26,46,.04)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--dr-canvas:#11131A;--dr-surface:#191C25;--dr-surface-2:#1F2330;--dr-hairline:#2B3040;--dr-hairline-strong:#3A4054;--dr-ink:#E8EAF2;--dr-ink-muted:#C2C7D6;--dr-ink-subtle:#9AA1B5;--dr-accent:#9C93F2;--dr-accent-strong:#B9B2F7;--dr-accent-soft:#272447;--dr-accent-line:#4A4390;--dr-neutral-soft:#232838}}
:root[data-theme="dark"]{--dr-canvas:#11131A;--dr-surface:#191C25;--dr-surface-2:#1F2330;--dr-hairline:#2B3040;--dr-hairline-strong:#3A4054;--dr-ink:#E8EAF2;--dr-ink-muted:#C2C7D6;--dr-ink-subtle:#9AA1B5;--dr-accent:#9C93F2;--dr-accent-strong:#B9B2F7;--dr-accent-soft:#272447;--dr-accent-line:#4A4390;--dr-neutral-soft:#232838}
*{box-sizing:border-box}
body{margin:0;background:var(--dr-canvas);color:var(--dr-ink);font-family:system-ui,-apple-system,'Apple SD Gothic Neo','Malgun Gothic',sans-serif;font-size:16px;line-height:1.55;font-variant-numeric:tabular-nums}
header{position:sticky;top:0;z-index:2;background:color-mix(in srgb,var(--dr-surface) 94%,transparent);border-bottom:1px solid var(--dr-hairline);padding:12px 32px;display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
header h1{font-size:18px;margin:0;letter-spacing:-.01em}
.notice{font-size:13px;color:var(--dr-ink-subtle);margin:0}
main{max-width:1280px;margin:0 auto;padding:20px 32px 40px;display:grid;gap:16px}
.card{background:var(--dr-surface);border:1px solid var(--dr-hairline);border-radius:var(--dr-r);box-shadow:var(--dr-shadow);padding:18px 20px;min-width:0}
.card h2{font-size:16px;margin:0 0 10px}
.card h3{font-size:14px;margin:14px 0 6px;color:var(--dr-ink-muted)}
.row{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
label{font-size:14px;color:var(--dr-ink-muted)}
select,button{font:inherit;font-size:15px;color:var(--dr-ink);background:var(--dr-surface);border:1px solid var(--dr-hairline-strong);border-radius:var(--dr-r-sm);padding:7px 12px;min-height:40px}
select{max-width:100%}
button{cursor:pointer}
button[aria-pressed="true"]{background:var(--dr-accent);border-color:var(--dr-accent);color:#fff}
:focus-visible{outline:3px solid var(--dr-accent);outline-offset:2px}
.steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;list-style:none;padding:0;margin:0}
.steps li{border:1px solid var(--dr-hairline);border-radius:var(--dr-r-sm);padding:10px 12px;font-size:14px;background:var(--dr-surface-2)}
.steps li b{display:block;font-size:12px;color:var(--dr-ink-subtle);font-weight:600}
.steps li[data-on="1"]{border-color:var(--dr-accent-line);background:var(--dr-accent-soft)}
.said{font-size:20px;line-height:1.9;margin:4px 0 0;word-break:keep-all;overflow-wrap:anywhere}
.said mark{background:none;color:inherit;border-bottom:3px solid var(--dr-hairline-strong);padding:0 1px}
.said mark[data-c="A"]{border-color:var(--dr-accent)}
.said mark[data-c="C"],.said mark[data-c="D"],.said mark[data-c="E"]{border-bottom-style:dashed}
.said mark sup{font-size:11px;color:var(--dr-ink-subtle);margin-left:2px}
.grid2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px}
.tbl{width:100%;border-collapse:collapse;font-size:14px}
.tbl th,.tbl td{text-align:left;vertical-align:top;padding:8px 8px;border-top:1px solid var(--dr-hairline)}
.tbl th{font-size:12px;color:var(--dr-ink-subtle);font-weight:600;border-top:none}
.tblwrap{overflow-x:auto}
.tblwrap .tbl{min-width:720px}.tbl td:first-child{min-width:104px}
.chip{display:inline-block;font-size:12px;line-height:1.4;padding:2px 8px;border-radius:999px;border:1px solid var(--dr-hairline-strong);background:var(--dr-surface-2);white-space:nowrap;margin:0 4px 4px 0}
.chip.acc{background:var(--dr-accent-soft);border-color:var(--dr-accent-line);color:var(--dr-accent-strong)}
.chip.dash{border-style:dashed}
.sec{border:1px solid var(--dr-hairline);border-radius:var(--dr-r-sm);padding:10px 12px;background:var(--dr-surface-2);min-width:0}
.sec h3{margin:0 0 6px;font-size:14px;color:var(--dr-ink)}
.sec .empty{font-size:13px;color:var(--dr-ink-subtle)}
.sec ul{margin:0;padding-left:18px;font-size:14px}
.secs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}

.difflist{list-style:none;margin:0;padding:0;font-size:14px}.difflist li{padding:10px 0;border-top:1px solid var(--dr-hairline);overflow-wrap:anywhere}.difflist li:first-child{border-top:none}.difflist .chip{white-space:normal}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px}
.muted{color:var(--dr-ink-subtle);font-size:13px}
pre{margin:0;white-space:pre-wrap;word-break:break-all}
@media (max-width:900px){.secs{grid-template-columns:repeat(2,minmax(0,1fr))}.grid2{grid-template-columns:1fr}}
@media (max-width:600px){header{padding:10px 16px}main{padding:16px}.steps{grid-template-columns:repeat(2,minmax(0,1fr))}.secs{grid-template-columns:1fr}.said{font-size:18px}}
</style>
</head>
<body>
<header>
 <h1>연구용 Doctor Preview · STEP30</h1>
 <p class="notice">연구 시뮬레이션입니다. 실제 Doctor 화면(8010)·환자 상태와 연결되지 않았고, 임상 검증·실제 의사 확인이 아닙니다(확인은 dummy).</p>
</header>
<main>
 <section class="card" aria-labelledby="h-case">
  <h2 id="h-case">사례 선택</h2>
  <div class="row">
   <label for="case">미리 계산한 합성 사례</label>
   <select id="case"></select>
   <button id="confirm" type="button" aria-pressed="false">dummy 의사 확인 적용</button>
  </div>
  <p class="muted">이 화면은 정적 파일이라 직접 입력 분석은 하지 않습니다. 새 문장은 <span class="mono">python scripts/doctor_integration_adapter.py "문장"</span> 으로 분석합니다.</p>
 </section>
 <section class="card" aria-labelledby="h-flow">
  <h2 id="h-flow">블라인드 판단 흐름</h2>
  <ol class="steps" id="steps"></ol>
  <p class="muted" id="blindnote"></p>
 </section>
 <section class="card" aria-labelledby="h-said">
  <h2 id="h-said">A. 환자가 말한 내용</h2>
  <p class="said" id="said"></p>
  <p class="muted">밑줄 = AI 추출 구간(실선 보라 = 기존 지원 증상 후보, 점선 = 부정·과거·다른 사람). 위첨자 = 범주.</p>
 </section>
 <section class="card" aria-labelledby="h-groups">
  <h2 id="h-groups">의사 검토용 정보 구분</h2>
  <div class="secs" id="secs"></div>
 </section>
 <section class="card" aria-labelledby="h-tbl">
  <h2 id="h-tbl">B·C. 증상별 표준화 결과와 부정·시점·주체</h2>
  <div class="tblwrap"><table class="tbl" id="tbl"></table></div>
 </section>
 <div class="grid2">
  <section class="card" aria-labelledby="h-mi">
   <h2 id="h-mi">G. 모델 입력 적격 여부</h2>
   <div id="mi"></div>
  </section>
  <section class="card" aria-labelledby="h-diff">
   <h2 id="h-diff">F. 의사 확인 전후 데이터 차이</h2>
   <div id="diff"></div>
  </section>
 </div>
</main>
<script id="data" type="application/json">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('data').textContent);
const SECT = [["confirmed","확인된 증상"],["ai_candidates","AI 추출 후보(미확인)"],["negated","부정된 증상"],["historical","과거 증상"],["other_person","가족 등 다른 사람"],["new_standard_candidates","새로운 표준 증상 후보(모델 미사용)"],["needs_confirmation","추가 확인 필요"],["non_symptom_context","증상 아닌 문맥"]];
const CAT = {A:"기존 지원 증상",B:"새 표준 후보",C:"부정",D:"과거·해소",E:"다른 사람",F:"확인 필요",G:"증상 아님",H:"표준화 실패"};
const KO = {PRESENT:"있음",ABSENT:"없음",POSSIBLE:"가능성",UNKNOWN:"모름",CURRENT:"현재",ONGOING:"지속",PAST:"과거",PATIENT:"환자",OTHER_PERSON:"다른 사람",MULTIPLE:"여러 사람",RESOLVED:"해소",IMPROVING:"호전",PERSISTING:"지속",UNSPECIFIED:"-"};
const sel = document.getElementById('case'), btn = document.getElementById('confirm');
const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let groups = {};
D.cases.forEach((c, i) => { const g = c.set === 'REGRESSION_EXPOSED' ? '노출 회귀 사례(지시문 §11)' : '새 통합 평가 사례';
  (groups[g] = groups[g] || []).push(`<option value="${i}">${esc(c.id)} · ${esc(c.text)}</option>`); });
sel.innerHTML = Object.entries(groups).map(([g, o]) => `<optgroup label="${esc(g)}">${o.join('')}</optgroup>`).join('');
let after = false;
function render() {
  const c = D.cases[+sel.value], byId = Object.fromEntries(c.items.map(it => [it.item_id, it]));
  const sections = after ? c.sections_after : c.sections_before, mi = after ? c.mi_after : c.mi_before;
  const steps = [["1단계","환자 원문·문진 사실 검토",1],["2단계","의사의 독립 working diagnosis 입력",after?1:0],["3단계","AI 추출 증상 확인(dummy)",after?1:0],["4단계","질환 후보 공개 — 이 Preview에는 없음",0]];
  document.getElementById('steps').innerHTML = steps.map(s => `<li data-on="${s[2]}"><b>${s[0]}</b>${s[1]}</li>`).join('');
  document.getElementById('blindnote').textContent = `제품 Doctor 화면 재사용 시험: working diagnosis 입력 전 질환 후보 ${c.blind.stage2_pending_assessment === 'LOCKED' ? '잠김' : '열림'} · 다음 질문 ${c.blind.stage2_pending_next_information === 'LOCKED' ? '잠김' : '열림'} · 확인 단계 뒤 working diagnosis ${c.blind.stage3_wd_unchanged ? '그대로' : '바뀜'} · 위반 ${c.blind.violations.length}건. 이 화면은 질환 이름·점수·순위를 담지 않습니다.`;
  let t = c.text, out = '', pos = 0;
  const spans = c.items.filter(it => it.span_start != null).sort((a, b) => a.span_start - b.span_start);
  for (const it of spans) { if (it.span_start < pos) continue;
    out += esc(t.slice(pos, it.span_start)) + `<mark data-c="${it.category}" title="${esc(CAT[it.category])}">${esc(t.slice(it.span_start, it.span_end))}<sup>${it.category}</sup></mark>`; pos = it.span_end; }
  document.getElementById('said').innerHTML = out + esc(t.slice(pos));
  const confirmed = new Set(after ? (sections.confirmed || []) : []);
  document.getElementById('secs').innerHTML = SECT.map(([k, name]) => { const ids = (sections[k] || []).filter(id => k !== 'ai_candidates' || !confirmed.has(id));
    const li = ids.map(id => byId[id]).map(it => `<li>'${esc(it.raw_span)}' → ${esc(it.label_ko)}</li>`).join('');
    return `<div class="sec"><h3>${name} <span class="muted">${ids.length}</span></h3>${li ? `<ul>${li}</ul>` : '<p class="empty">없음</p>'}</div>`; }).join('');
  document.getElementById('tbl').innerHTML = `<thead><tr><th>원문</th><th>표준 증상</th><th>범주</th><th>있음·시점·주체</th><th>모델 입력 적격</th></tr></thead><tbody>` +
    c.items.map(it => `<tr><td>'${esc(it.raw_span)}'<div class="muted mono">${it.span_start ?? '-'}–${it.span_end ?? '-'}</div></td>
      <td>${esc(it.label_ko)}<div class="muted mono">${esc(it.canonical_id ?? '')} ${esc(it.ontology_id ?? '')}</div></td>
      <td><span class="chip ${it.category === 'A' ? 'acc' : 'dash'}">${it.category} ${esc(CAT[it.category])}</span></td>
      <td>${[it.assertion, it.temporality, it.experiencer].map(x => `<span class="chip">${esc(KO[x] ?? x ?? '-')}</span>`).join('')}${it.onset_text ? `<span class="chip">시작 '${esc(it.onset_text)}'</span>` : ''}${it.current_status && it.current_status !== 'UNSPECIFIED' ? `<span class="chip">${esc(KO[it.current_status] ?? it.current_status)}</span>` : ''}</td>
      <td>${it.stage_a ? `<span class="chip acc">STAGE_A · ${esc(it.target)}</span><div class="muted">확인 전에는 입력하지 않음</div>` : `<span class="chip">적격 아님</span><div class="muted mono">${esc((it.blocking || []).slice(0, 3).join(' · '))}</div>`}</td></tr>`).join('') + '</tbody>';
  const sa = mi.stage_a_technically_eligible.map(r => `<li>${esc(byId[r.item_id].raw_span)} → <span class="mono">${esc(r.evidence_id)}</span></li>`).join('');
  const sb = mi.stage_b_clinician_confirmed.map(r => `<li>${esc(byId[r.item_id].raw_span)} → <span class="mono">${esc(r.evidence_id)}=POSITIVE</span> (${esc(r.confirmer)})</li>`).join('');
  document.getElementById('mi').innerHTML = `<p><span class="chip ${mi.applied ? '' : 'acc'}">모델에 실제 입력: ${mi.applied ? '있음' : '없음'}</span><span class="chip">자동 입력 ${mi.auto_input_count}건</span></p>
    <h3>STAGE_A 기술적 적격(표시만)</h3>${sa ? `<ul>${sa}</ul>` : '<p class="muted">없음</p>'}
    <h3>STAGE_B 의사 확인 뒤 모델 입력 후보</h3>${sb ? `<ul>${sb}</ul>` : '<p class="muted">없음 — 의사 확인 전</p>'}
    <p class="muted">부정된 증상의 음성 입력, 신규 표준 후보, 과거·다른 사람·불확실 항목은 자동 입력하지 않습니다.</p>`;
  const rows = c.diff.filter(d => d.before !== d.after);
  document.getElementById('diff').innerHTML = !after ? '<p class="muted">‘dummy 의사 확인 적용’을 누르면 확인 뒤 바뀐 항목이 표시됩니다(정책: STAGE_A 항목만 있음 확인, 부정 항목은 없음 확인, 나머지 보류).</p>' :
    (rows.length ? `<ul class="difflist">${rows.map(d => `<li><b>'${esc(byId[d.item_id].raw_span)}'</b> <span class="mono muted">${esc(d.field)}</span><div><span class="chip">${esc(d.before ?? '없음')}</span> → <span class="chip acc">${esc(d.after)}</span></div><div class="muted">확인자 ${esc(d.by)} · 순서 ${d.sim_step}</div></li>`).join('')}</ul>` : '<p class="muted">바뀐 항목 없음</p>');
}
sel.addEventListener('change', render);
btn.addEventListener('click', () => { after = !after; btn.setAttribute('aria-pressed', String(after)); render(); });
render();
</script>
</body>
</html>
"""


def main():
    e2e = S.load_json(S.OUT / "end_to_end_cases.json")
    data = {**S.RESEARCH_BANNER, "cases": [slim(c) for c in e2e["cases"]]}
    blob = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (S.PREVIEW / "index.html").write_text(HTML.replace("__DATA__", blob), encoding="utf-8")
    print("preview cases", len(data["cases"]), "bytes", len(blob))


if __name__ == "__main__":
    main()
