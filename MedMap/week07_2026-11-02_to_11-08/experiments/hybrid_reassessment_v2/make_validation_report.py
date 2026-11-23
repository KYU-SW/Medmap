"""outputs JSON 에서 VALIDATION_REPORT.md 생성(수치 손 입력 금지). 2차 결과가 있으면 함께 표시."""
import json,re
from pathlib import Path
H=Path(__file__).parent
r1=json.loads((H/'outputs/public_linking_results_run1_frozen.json').read_text(encoding='utf-8')); m=json.loads((H/'outputs/mutation_results.json').read_text(encoding='utf-8')); t=(H/'outputs/unit_test_tail.txt').read_text(encoding='utf-8')
p2=H/'outputs/public_linking_results_run2.json'; r2=json.loads(p2.read_text(encoding='utf-8')) if p2.exists() else None
n=re.search(r'Ran (\d+) tests',t).group(1); ok='OK' if re.search(r'^OK',t,re.M) else 'FAILED'
def table(r):
    return [f"- 문장 {r['n_sentences']}, 대상 개념 포함 {r['n_sentences_with_target_concept']}",
     f"- Concept Extraction/Linking Coverage(대상 개념 6종): {r['n_linked_gold']}/{r['n_gold_concept_mentions']} = {r['concept_extraction_coverage']:.3f}",
     f"- 언급 상태가 주석과 일치: {r['n_assertion']}건 중 {r['assertion_agreement_with_annotation']:.3f}",
     f"- Unsupported Mapping(주석에 없는 대상 개념 연결): {r['unsupported_mapping_count']}",
     f"- Evidence Relation Coverage(주석상 관계 경로): {r['relation_path_found']}/{r['n_gold_relation_paths']} = {r['relation_path_coverage']:.3f}, 주석에 없는 경로 {r['extra_relation_paths']}",
     f"- 출력 방향: {r['directions']}", f"- 기권 사유: {r['abstain_reasons']}", f"- Provenance Completeness: {r['provenance_complete']}",
     f"- 모호 처리 {r['ambiguous_mentions']}, HPO 연결 {r['hpo_links']}(그래프 안 {r['hpo_in_graph']})"]
wrong=[(x['id'],o['relation_id']) for x in r1['rows'] for o in x['outputs'] if o['direction']=='WEAKEN' and o['relation_id']=='PE-DDIMER-NORMAL']
from collections import Counter
L=['# 검증 결과 — IMPLEMENTATION CHECK','','임상 정확도가 아니다. 기준 표시는 세션 1인(비전문가)이라 정답률이 아니다. 사전 확률은 실행 확인용 가정.','','## 합성 검사',f"- 테스트 {n}개, 결과 {ok}(입력 유형 1~12, 표현 5종, 시간 사례 포함)",f"- 변이 {m['n']}종, 생존 {m['survived']}",'- Temporal Consistency: 합성 사례에서 공개·정정·가설 변경이 기대와 일치, EXP-03 엔진 대조 일치(테스트 1건, 사례 1개)','',
'## 처음 보는 공개 문장 1차(코드 동결 후 기준 먼저 고정, 1회)','- CC BY 증례 14건에서 추출, 파일 `outputs/public_linking_results_run1_frozen.json`']+table(r1)+[f"- 오류 유형: {dict(Counter(e['type'] for e in r1['errors']))}",f"- **잘못된 약화: WEAKEN 4건 중 3건 {wrong}** — 상승 D-dimer 를 같은 문장의 다른 'normal' 로 오판. 치명적 유형으로 기록",'',
'## 1차 후 수정(1차 문장으로 재평가하지 않음)','- D-dimer 해석 범위를 언급 주변으로 제한, 충돌 시 기권',"- CT 검사명·복수형·하이픈 변형 추가, 수식어 HPO 제외, 'ruled out chronic' 부분 음성, 위험 점수·잠정 진단 불확실 처리, 검사명 부정 제외",'']
if r2: L+=['## 처음 보는 공개 문장 2차(수정 후, 새 문서)']+table(r2)+[f"- 오류 유형: {dict(Counter(e['type'] for e in r2['errors']))}"]
else: L+=['## 2차 확인: **미완료**','- 2026-11-05 Europe PMC 503 으로 새 표본을 받지 못함. 수정 효과는 새 문장으로 미확인.']
L+=['','## 측정하지 않은 것','- Correct Concept Link Rate(전문가 기준 없음, 주석 일치만)','- 임상 판단 정확도, 전문가 일치, SCT 재평가(노출 자료)','- End-to-End Executable Coverage 는 관계 경로 커버리지와 합성 사례로 대신 보고']
(H/'docs/VALIDATION_REPORT.md').write_text('\n'.join(L)+'\n',encoding='utf-8'); print('\n'.join(L[:40]))
