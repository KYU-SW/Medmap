"""outputs JSON 에서 VALIDATION_RESULTS.md 생성(수치 손 입력 금지)."""
import json,re
from pathlib import Path
H=Path(__file__).parent
v=json.loads((H/'outputs/validation_results.json').read_text(encoding='utf-8')); m=json.loads((H/'outputs/mutation_results.json').read_text(encoding='utf-8')); t=(H/'outputs/unit_test_tail.txt').read_text(encoding='utf-8')
L=['# 기술 검증 결과 — IMPLEMENTATION CHECK','','전문가 판단 성능·임상 정확도가 아니다. 제한 자료·외부 호출 없음.','',f"생성 {v['created']}",'']
n=re.search(r'Ran (\d+) tests',t); ok='OK' if re.search(r'^OK',t,re.M) else 'FAILED'
L+=['## 단위 테스트',f"- {n.group(1)}개, 결과 {ok}",'',f"## 변이 시험",f"- {m['n']}종 중 탐지 {m['n']-len(m['survived'])}, 생존 {m['survived']}",f"- 생존 설명: {m['equivalent_note']}",'']
s=v['sct_public'];L+=['## SCT 공개 문항(EXP-04 에서 이미 사용, 독립 평가 아님)',f"- 전체 {s['n_total']}, 최빈 등급 동률 제외 {s['n_excluded_tied_modal_grade']}",'','| 팔 | 문항 | 적용 범위 | 기권 | 미구현 |','|---|---|---|---|---|']
L+=[f"| {a} | {x['n_items']} | {x['coverage']:.3f} | {x['abstention_rate']:.3f} | {x['not_implemented_rate']:.3f} |" for a,x in s['arms'].items()]
L+=['',s['note'],'','## 합성 타임라인(지어낸 사례)',f"- 공개 집합이 기존 엔진과 다른 시점: {v['synthetic_timeline']['visible_set_differs_from_engine']}",'','| T | 공개 증거 | 엔진 상태 | 조합 판단 | 검사 상태 | 중복 후보 |','|---|---|---|---|---|---|']
L+=[f"| {x['T']} | {','.join(x['visible'])} | {x['engine_summary']} | {','.join(x['hybrid'])} | {x['test_status']} | {x['duplicate_candidate']} |" for x in v['synthetic_timeline']['steps']]
e=v['er_reason_format_dry_run'];L+=['','## ER-Reason 형식 시험(자리표시자, 실제 자료 아님)',f"- 사례 {e['stats']['n_cases']}, 문항 {e['stats']['n_items']}, 대응 실패 {e['stats']['n_rows_unmatched']}, 분할 {e['split_counts']}, 두 분할에 걸친 사례 {e['cases_in_two_splits']}",'- 지표 값은 파이프라인 동작 확인용이며 의미 없음','']
p=v['preservation'];L+=['## 원본 보존 확인',f"- EXP-01 FINAL 체크섬 일치 {p['exp01_final_ok']}, EXP-02 동결 {p['exp02_frozen_ok']}, time_v2 동결 대비 변경 {p['time_v2_code_vs_freeze_diff']}, TEST_USED 표지 {p['test_used_exists']}, EXP-MAI-003 실행 표지 {p['counted_marker_exists']}"]
(H/'docs/VALIDATION_RESULTS.md').write_text('\n'.join(L)+'\n',encoding='utf-8')
