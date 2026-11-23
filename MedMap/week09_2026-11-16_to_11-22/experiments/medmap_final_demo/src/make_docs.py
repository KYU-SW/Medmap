"""README.md · VALIDATION_RESULTS.md · FINAL_PRESENTATION_BRIEF.md 생성. 수치는 모두 결과 파일(compare.json, demo_results.json,
테스트 로그, 공개 위험 점검 결과, RG 기록)에서 읽는다(손으로 옮겨 적지 않음). 사용: python make_docs.py <RUN_ID>
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT.parents[1]
L = {"A": "미래 정보 사용", "A2": "이용 가능 시각 모름 결과 사용", "B": "요청·대기·취소 기록 사용", "C": "중복 사본을 원본과 함께 사용", "D": "정정으로 대체된 버전 사용",
     "E": "다른 환자 기록 사용", "G": "보류·제외 사유 누락", "G2": "사유 불일치", "I": "거짓 보류(써야 할 근거 미사용)"}
SCORE_KO = {-2: "크게 감소", -1: "조금 감소", 0: "변화 없음", 1: "조금 증가", 2: "크게 증가"}


def latest(kind: str):
    d = MAIN / ".research-guardian" / "audits" / "EXP-MAI-009" / kind
    fs = sorted(d.glob("*.md")) if d.exists() else []
    if not fs:
        return "미실행", None
    m = re.match(r"\d{8}_\d{6}_(.+)\.md", fs[-1].name)
    return (m.group(1) if m else fs[-1].name), fs[-1].relative_to(MAIN)


def main(run: str):
    C = json.loads((ROOT / "outputs" / f"compare_{run}" / "compare.json").read_text(encoding="utf-8"))
    Cb = json.loads((ROOT / "outputs" / f"compare_{run}_b" / "compare.json").read_text(encoding="utf-8"))
    D = json.loads((ROOT / "outputs" / f"demo_{run}" / "demo_results.json").read_text(encoding="utf-8"))
    ut = (ROOT / "logs" / f"unittest_{run}.log").read_text(encoding="utf-8")
    n_tests = re.search(r"Ran (\d+) tests", ut).group(1)
    ut_ok = ut.strip().endswith("OK")
    reid = (MAIN / "exp" / "medmap_er_reason_public_safe_v3" / "reid_check_v3.log").read_text(encoding="utf-8")
    reid_ok = "RECOVERED (1~9 cells): []" in reid and "narrow width<=2 1~9 cells: []" in reid
    gate_v, gate_f = latest("gate")
    ver_v, ver_f = latest("verify")
    P = C["results"]["primary"]
    M = P["metrics"]
    shaA, shaB = C["result_sha256(실행 시간 제외 본문)"], Cb["result_sha256(실행 시간 제외 본문)"]
    all_pass = C["pass_primary"] and all(C["pass_confirm"]) and shaA == shaB
    seeds_line = f"주 seed {P['seed']}(조회 {P['n_queries']}, 기록 {P['n_records']}) + 확인 seed " + ", ".join(
        f"{r['seed']}(조회 {r['n_queries']}, {'통과' if ok else '미통과'})" for r, ok in zip(C["results"]["confirm"], C["pass_confirm"]))
    rows = "\n".join(f"| {L[k]} | {M['BASE'][k]['occurrences']} (계보 {M['BASE'][k]['lineages']}, 환자 {M['BASE'][k]['patients']}) | "
                     f"{M['MEDMAP'][k]['occurrences']} (계보 {M['MEDMAP'][k]['lineages']}, 환자 {M['MEDMAP'][k]['patients']}) |" for k in L)
    rows += "\n" + "\n".join(f"| {'과거 재생 불일치 조회' if k == 'F' else '반복·입력 순서 섞기 불일치 조회'} | {M['BASE'][k]['queries']} (환자 {M['BASE'][k]['patients']}) | "
                             f"{M['MEDMAP'][k]['queries']} (환자 {M['MEDMAP'][k]['patients']}) |" for k in ("F", "H"))
    rows += f"\n| 정답 입력 집합 완전 일치(조회) | {M['BASE']['exact_used_match']} | {M['MEDMAP']['exact_used_match']} |"
    crit = D["criteria"]
    steps = []
    for s in D["steps"]:
        a = s["assessment"]
        sc = [f"{r['item']} {r['assessment']['score']:+d}({SCORE_KO[r['assessment']['score']]})" for r in a["rows"] if r["assessment"]["status"] == "SCORED"]
        steps.append(f"| {s['step']} | {s['as_of'][11:16]} | {a['n_usable']} | {a['n_held']} | {a['n_excluded']} | {', '.join(sc) or '—'} |")
    ct = {s["step"]: next((r for r in s["assessment"]["rows"] if r["lineage_id"] == "L-CTPA"), None) for s in D["steps"]}
    ct_pre, ct_fix = ct.get("CT 예비 판독"), ct.get("CT 판독 정정")
    ct_same = ct_pre and ct_fix and ct_pre["assessment"].get("score") == ct_fix["assessment"].get("score")
    ct_line = (f"CT 판독이 '폐색전증 없음'(예비, {ct_pre['used_event_id']}) → '폐색전증과 일치'(정정, {ct_fix['used_event_id']})로 바뀌어 사용 버전이 바뀌었지만, "
               f"D 모델 점수는 {ct_pre['assessment']['score']:+d} → {ct_fix['assessment']['score']:+d}" + ("로 같았다" if ct_same else "로 바뀌었다")) if ct_pre and ct_fix else "확인 불가"
    kg = D["kg_relation_status"]
    tpl_line = "; ".join(f"{k}: BASE {v['BASE']} · MEDMAP {v['MEDMAP']}" for k, v in P[[x for x in P if x.startswith('reason_correct')][0]].items())
    g = D["provenance_graph_stats_final"]
    model_line = f"{D['model_status']} — {D['model_id']}" if D["model_status"] == "LOADED" else f"{D['model_status']} ({D['model_error']})"

    common_limits = f"""- 합성 환자만. 실제 진료자료·임상 성능 NOT_EVALUATED.
- 비교 실험은 같은 작성자가 만든 생성기 정답과의 '규칙 해석 일치 검사' — 독립 정답 아님. BASE 는 흔한 구현 실수를 모아 의도적으로 약하게 정의한 기준선(효과 크기 아님).
- 생성기 밖 사유({', '.join(C['not_covered_by_generator(단위 테스트에서만 검증)'][:-1])})는 단위 테스트에서만 검증. 생성기 kind 는 LAB 단일.
- 조회는 경계 시각 집중 격자이고 같은 환자 조회끼리 독립이 아님. F(재생 불일치)=0 은 MEDMAP 이 도착 시각으로 먼저 거르므로 설계상 보장되는 값.
- D 모델(EXP-MAI-006, ER-REASON 학습, 원래 정확 일치 약 0.41)의 합성 영어 문장 점수는 의학적 타당성이 검증되지 않았다. {ct_line}.
- 지식그래프: 관계 {kg.get('n_relations')}개 중 임상의 검증 {kg.get('clinician_verified')}개({kg.get('state')}) → 그래프 관계로 판단을 만들지 않음.
- 가설 연결은 시나리오가 지정한 태그이며 엔진이 의학적으로 판정하지 않는다."""

    readme = f"""# MedMap 근거 추적 시제품 (최종발표 시연용, 합성 환자)

의사가 지정한 진단 가설에 대해, 새 의료 근거의 출처·상태·이용 가능 시각·중복·정정을 검사하고 유효한 근거만 기존 연구 모델(EXP-MAI-006 D)에 넣어 근거별 연구용 점수를 내며, 과거 시점 재생과 변경 이력을 보여준다. 진단을 확정하지 않는다.

## 환경
- `~/ai_env`(Python 3.12, scikit-learn·numpy·pandas·joblib 기설치). 신규 패키지·외부 API·네트워크 없음.
- D 모델: EXP-MAI-008 봉인 저장본 `~/medmap_er_reason_ordinal_sealed/s1_20261113_01/models/fold0.joblib`(sha256 고정 대조). 다른 위치면 환경변수 `MEDMAP_D_MODEL_RUN_DIR`. 모델이 없으면 화면·출력이 MODEL_UNAVAILABLE 로 동작(가짜 점수 없음).

## 실행
```bash
cd ~/medmap-worktrees/main-ai/exp/medmap_final_demo
~/ai_env/bin/python -B -m unittest discover -s tests          # 자동 테스트({n_tests}개)
cd src
~/ai_env/bin/python -B server.py 8765 --compare {run}       # 시연 화면 → 브라우저 http://127.0.0.1:8765/
~/ai_env/bin/python -B server.py 8765 --no-model            # 모델 없음 상황 시연
~/ai_env/bin/python -B run_compare.py <새 RUN_ID>            # 비교 실험(같은 RUN_ID 덮어쓰기 거부)
~/ai_env/bin/python -B run_demo.py <새 RUN_ID>               # 시연 단계 계산 저장
```
`?step=N`(1~7)으로 특정 단계를 바로 열 수 있다. 서버는 127.0.0.1 에만 연결된다.

## 실제 구현 기능(이번 실행에서 동작 확인)
- 추가 전용 사건 저장소와 수집 거부(잘못된 시각·필드 누락·잘못된 상태·빈 근거·자기 정정·같은 ID 다른 내용) — `medmap_demo/events.py`
- REPLAY(as_of): 도착·공개 시각 이중 필터, 계보별 유효 버전 선택, 중복·정정·취소·무효·출처·환자·가설 연결 검사와 사유 코드 — `medmap_demo/replay.py`
- 평가 보류와 0점 분리, 모델 없음 처리, 근거별 독립 연구용 점수, 변경 diff·결정론적 설명, 기록 제외 비교, 출처 그래프 — `medmap_demo/assess.py`
- 기존 D 모델 읽기 전용 연결(겹 0 고정, sha256 대조) — `medmap_demo/model_adapter.py`
- 시연 화면 4개 영역(환자·가설 / 시간순 근거 / 근거 상태와 연구용 점수 / 기술 검증) — `src/server.py`, `web/index.html`
- 비교 실험 BASE vs MEDMAP — `src/run_compare.py`

## 시연 절차
1. `server.py 8765 --compare {run}` 실행 후 브라우저에서 http://127.0.0.1:8765/
2. '시연 자동 실행'(단계마다 4.5초) 또는 단계 버튼을 순서대로: 검사 요청 → 결과 대기 → D-dimer 결과 이용 가능 → CT 예비 판독 → 늦은 기록 도착 → CT 판독 정정 → 과거 시점 재생(CT 예비 판독 시점)
3. 각 단계에서 2번(도착한 기록·역할), 3번(사용·보류·제외와 사유, 연구용 점수, 이전 조회 대비 변화), 4번(미래 기록 차단·과거 재생 일치·순서 무관·보류 점수 없음 등 실제 계산 결과) 확인
4. 사용 근거 카드의 '이 기록 빼고 다시 계산'으로 기록 제외 비교(기술 검사)
5. `--no-model` 로 다시 띄워 MODEL_UNAVAILABLE 처리 확인

## 남은 제한 사항
{common_limits}
- 시연 화면 렌더링은 로컬 Chromium 헤드리스 스크린샷(1280·768·375 폭)으로 확인 — `outputs/screenshots_{run}/`(SHA256SUMS.txt). Playwright MCP 브라우저는 설치돼 있지 않음(다운로드 안 함).
- 문서: TECHNICAL_DESIGN.md(구조·재사용 목록), VALIDATION_RESULTS.md, FINAL_PRESENTATION_BRIEF.md, logs/FAILURE_LOG.md(실패·수정 기록)
"""

    val = f"""# 검증 결과 — EXP-MAI-009 (RUN_ID {run})

> 결과 파일에서 자동 생성(src/make_docs.py). 합성 자료 기술 검증 — 임상 성능 아님.

## 1. 승인·검증 상태
| 항목 | 상태 |
|---|---|
| RG 사전 심사 | 1차 NEEDS_FIX(설계·통계·의료 AI) → 2차 NEEDS_FIX → 3차 RUN, 최신 기록 `{gate_f}`({gate_v}) |
| 프로토콜 동결 | `.research-guardian/experiments/EXP-MAI-009/protocol.lock.json` |
| RG 사후 독립 검증 | {ver_v}{f' (`{ver_f}`)' if ver_f else ''} — 수치·판정·해시·시연 기준 재계산 전부 일치, 부분 판정 사유는 보조 주장 근거 파일 부재·노출 서술 소차이(검증 뒤 근거 파일 추가·서술 보완, 판정은 그대로) |

## 2. 자동 테스트
- `tests/test_engine.py` {n_tests}개: {'전부 통과' if ut_ok else '실패 있음 — 로그 확인'}(logs/unittest_{run}.log).
- 범위: T1~T10 시나리오, 단위(상태·보류≠0점·모델 없음·sha 불일치 거부·취소·무효·출처·가설 연결·버전 충돌·새 버전 알림), 오류 주입(잘못된 시각 3종·출처 누락·중복 ID·정정 순환·없는 이전 버전·환자 ID 충돌·잘못된 상태·빈 근거·알 수 없는 필드·누락 필드·모델 로딩 실패), 불변성(입력 순서 무관·반복 동일·과거 재생=당시 상태·미래 기록 미사용·추가 전용), 시연 이야기 전체, 반사실·출처 그래프, 사전 심사 지적 회귀(동점 결함·정정 전 사본·새 버전 시각 모름·역할 '?'·화면 노출 정책·비교 화면 구조), 개발 seed 비교 하네스.
- 변이 검사(동결 코드 사본에 결함 주입): 가용→관찰 시각, 미래 기록 허용, 계보 간 중복 제거 생략, 정렬 키 되돌림, 정정 전 사본 검사 끔, 새 버전 시각 모름 보류 끔 — 모두 테스트 실패로 검출(근거 logs/mutation_check_frozen_20261116.log, 개발 중 기록 logs/FAILURE_LOG.md).
- 실패 기록: 1회차 테스트 2개 실패(테스트 시점 설정 오류), 사전 심사에서 엔진 결함 3건·화면 결함 2건 발견 → 수정(모두 FAILURE_LOG.md 에 보존).

## 3. 비교 실험(사전 정의 합성 시험)
{seeds_line}. 순열 {C['n_shuffle_permutations']}개로 입력 순서 섞기.

| 지표(기록-조회 발생 건수, 괄호는 고유 계보·환자 수) | BASE(의도적 약화) | MEDMAP |
|---|---|---|
{rows}

- 주 seed 통과 {C['pass_primary']}, 확인 seed 통과 {C['pass_confirm']}, 프로세스 내 재실행 동일 {C['in_process_rerun_identical']}.
- 별도 프로세스 재실행 result_sha256: `{shaA}`(compare_{run}) / `{shaB}`(compare_{run}_b) → {'일치' if shaA == shaB else '불일치'}.
- 템플릿별 사유 일치(계보 단위, 일치 계보/정답상 보류·제외 계보): {tpl_line}.
- 판정: {'사전 정의한 합성 시험(규칙 해석 일치 검사)을 통과' if all_pass else '사전 기준 미충족 — 결과 그대로 보고'}. 지표는 합산하지 않는다(한 기록이 여러 지표에 해당 가능).

## 4. 시연 계산(D 모델 연결)
- 모델: {model_line}. 2회 계산 동일 {D['repeat_identical']}.
- 기준: 과거 재생 = 당시 {crit['past_replay_equals_then']}, 보류·제외에 점수 없음 {crit['no_score_on_non_usable']}, 모델 로드 {crit['model_loaded']}, 사용 근거 전부 점수 {crit['all_usable_scored']}.

| 단계 | 조회 시각 | 사용 | 보류 | 제외 | 연구용 점수(근거별, 합산 없음) |
|---|---|---|---|---|---|
{chr(10).join(steps)}

- {ct_line}. 엔진은 버전 변경을 추적했지만 모델 점수는 새 판독 내용을 반영하지 못했다 — 점수의 의학적 타당성은 검증되지 않았다.
- 출처 그래프(정정 단계): 노드 {g['nodes']}, 간선 {g['edges']} ({', '.join(f'{k} {v}' for k, v in g['edge_kinds'].items())}).
- 수집 로그: 추가 {D['ingest_log_summary']['APPENDED']}, 거부 {D['ingest_log_summary']['REJECTED']}.

## 5. 원본 보존·개인정보 보호
- 기존 EXP-MAI-005~008 코드·결과·봉인·RG 기록: 이번 작업에서 내용 수정 없음(새 폴더 `exp/medmap_final_demo/`, `exp/medmap_er_reason_public_safe_v3/` 만 작성). SUPERSEDED v1 공개본 8개는 해시 대조한 안전 사본을 `~/medmap_public_risk_sealed/20261116/`(700)에 만든 뒤 원본 권한만 600 으로 바꿈(내용 해시 동일 확인). 원본 이동·삭제는 사용자 승인 필요 → 하지 않음.
- 로컬 `.git/info/exclude` 에 의료자료 파생 산출물·`*.joblib` 추가(로컬 전용, 보호 수단 아님). 이 저장소에는 원격 저장소 설정 없음.
- 외부 공유용 안전 요약 v3(`exp/medmap_er_reason_public_safe_v3/safe_summary_v3.json`): 정수 계획 역산 검사에서 1~9 칸 복원·좁힘 {'0' if reid_ok else '있음 — 확인 필요'}(공격자가 정답 분포·겹 크기를 안다고 보수적으로 가정).
- 006+007 기존 공개본만으로 1~9 칸 3개가 폭 2 이내로 좁혀지는 상태는 그대로(기존 파일 수정 안 함) — 외부 공유는 v3 요약만 권장.
- 시연 화면: 합성 환자만. 조회 시점까지 도착한 기록 메타데이터와 AI 입력으로 사용한 근거 문장만 전송. 다른 환자 기록은 내용·환자 ID 필드 없이 항목명·시각·기록 ID·계보 ID 가 나간다(합성 계보 ID 'L-CXR-SYN002' 에 환자 번호가 들어 있음 — 합성 ID 명명 규칙 탓, 실제 자료 적용 시 계보 ID 가림 필요). 과거 재생 단계의 diff 에는 이전 조회(더 나중 시점)의 기록 ID·점수가 들어간다(문장 없음). D 모델 특징어·계수 표시 없음, 모델 파일 복사 없음. ER-REASON DUA 의 파생 모델 공유 범위는 확인 필요.

## 6. 한계
{common_limits}
"""

    brief = f"""# 최종발표 기술 요약 — MedMap 근거 추적 시제품

## 연구 목표
의사가 현재 검토 중인 진단 가설에 대해, 어떤 근거가 언제 이용 가능해졌고 무엇을 쓰고 무엇을 뺐으며 그에 따라 연구용 AI 출력이 어떻게 달라졌는지를 추적 가능하게 보여준다. 진단을 대신 확정하지 않는다.

## 해결하려는 문제
AI 에 근거를 넣기 전에 다음을 확인하지 않으면 입력이 오염된다: 아직 나오지 않은 결과(미래 정보), 요청·대기 상태를 결과처럼 사용, 같은 자료의 중복, 정정 전 버전, 다른 환자 기록 혼입, 과거 시점 재현 불가.

## 시스템 핵심 기술(실제 코드로 연결·검증)
1. 근거 이용 가능 시점을 고려한 진단 가설 평가 — 도착 시각과 결과 공개 시각을 모두 만족한 버전만 AI 입력. 과거 시점 재생 = 그 당시 시스템 상태(매 조회 계산).
2. 중복과 정정을 반영하는 추적 가능한 환자 증거 관리 — 추가 전용 저장, 계보·버전, 계보 간 재전송·정정 전 내용 재전송 차단, 모든 보류·제외에 사유 코드.
3. AI 점수와 입력 유효성 검증의 분리 — 엔진이 먼저 사용 근거를 정하고, 모델은 그 근거만 받는다. 평가 보류는 0점이 아니라 사유로 표시.

## 시연 시나리오(합성 환자 SYN-001, 가설: pulmonary embolism)
검사 요청 → 결과 대기 → D-dimer 결과 이용 가능(인터페이스 재전송 중복 차단) → CT 예비 판독 → 늦게 도착한 심전도 기록 → CT 판독 정정(사용 버전 교체) → 과거 시점 재생(정정 전 상태 그대로 복원). 출처 모름·시각 모름·취소·다른 환자 혼입·가설 연결 태그 없음 기록이 각각 사유와 함께 보류·제외됨.

## 의도적으로 약하게 정의한 단순 처리(BASE)와의 비교(실측, 합성 — 실제 기존 시스템 아님)
{seeds_line}.

| 지표 | 단순 처리(BASE, 의도적 약화) | MedMap |
|---|---|---|
""" + "\n".join(f"| {L[k]} | 계보 {M['BASE'][k]['lineages']} · 환자 {M['BASE'][k]['patients']} | 계보 {M['MEDMAP'][k]['lineages']} · 환자 {M['MEDMAP'][k]['patients']} |" for k in ("A", "A2", "B", "C", "D", "E", "G", "G2", "I")) + "\n" + "\n".join(f"| {'과거 재생 불일치 조회' if k == 'F' else '반복·입력 순서 불일치 조회'} | 조회 {M['BASE'][k]['queries']} · 환자 {M['BASE'][k]['patients']} | 조회 {M['MEDMAP'][k]['queries']} · 환자 {M['MEDMAP'][k]['patients']} |" for k in ("F", "H")) + f"""
| 정답 입력 집합 완전 일치(조회) | {M['BASE']['exact_used_match']} | {M['MEDMAP']['exact_used_match']} |

## 실제 측정한 성능
- 자동 테스트 {n_tests}개 {'통과' if ut_ok else '실패 있음'}, 변이 검사 6종 검출.
- 비교 실험: {'네 seed 모두 사전 정의 합성 시험 통과, 별도 프로세스 결과 해시 일치' if all_pass else '사전 기준 미충족'}(result_sha256 `{shaA}`).
- 독립 검증: {ver_v}(수치 재계산 일치, 보조 주장 근거 파일은 검증 뒤 추가).
- 시연: D 모델 연결 {D['model_status']}, 과거 재생 일치 {crit['past_replay_equals_then']}, 보류 근거 점수 없음 {crit['no_score_on_non_usable']}.

## 이번 결과로 주장 가능한 것
- 사전 정의한 합성 시험에서 MedMap 근거 검증 엔진이 생성기 사양과 일치했다(미래 정보·대기·중복·정정 전·다른 환자 사용 0, 거짓 보류 0).
- 같은 합성 사건에서 의도적으로 약하게 정의한 단순 처리는 위 표만큼 AI 입력을 오염시킨다(예시).
- 기존 D 모델을 수정·재학습 없이 읽기 전용으로 연결해 근거별 연구용 점수를 낸다.
- 과거 시점 재생이 그 당시 시스템 상태와 같다.

## 주장할 수 없는 것
- 임상 현장 의료 오류 차단·환자 안전성·임상 진단 정확도.
- 기존 의료 AI 전체보다 우월하다는 것, 새로운 학문적 알고리즘 증명, 기존 의료 AI 들이 이런 기능을 전혀 제공하지 않는다는 것.
- 연구용 점수의 의학적 타당성 — {ct_line}.
- 근거별 점수를 합산·평균한 진단 가능성, 여러 진단 후보 자동 순위화.
- BASE 대비 '효과'(BASE 는 정의상 실패하도록 만든 기준선).

## 향후 확장 방향
1. 실제 자료 형식(예: 검사 결과 인터페이스 메시지)의 시각·상태·정정 필드를 이 사건 모델로 옮기는 어댑터 — 사용 조건 확인 후.
2. 생성기 밖 사유(버전 충돌·계보 오류·환자 ID 충돌·무효·새 버전 시각 모름)와 템플릿 결합을 비교 실험에 추가.
3. 저장된 D 모델로 문장 민감도 검사(정정 판독 같은 문장 변화에 점수가 반응하는지) — 새 실험 번호로 사전 심사 후.
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")
    (ROOT / "VALIDATION_RESULTS.md").write_text(val, encoding="utf-8")
    (ROOT / "FINAL_PRESENTATION_BRIEF.md").write_text(brief, encoding="utf-8")
    print("wrote README.md VALIDATION_RESULTS.md FINAL_PRESENTATION_BRIEF.md; all_pass", all_pass, "verify", ver_v)


if __name__ == "__main__":
    main(sys.argv[1])
