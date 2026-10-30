# STEP29 Clinical NLU Architecture(연구용)

```
환자 원문 ─▶ clause_segmenter(kiwi: 문장 SF · 절 EC/‘-는데’ · 트리거 ‘…때마다’)
          ─▶ symptom_span_extractor(관계절 ASSOCIATED/PRIMARY · 병렬 JC · P5 질의 시작점 · 대체 질의)
          ─▶ p5_normalizer_adapter(STEP28.8 P5 그대로, 단위별 호출) ─▶ mention 보존 기준(keep)
          ─▶ negation_scope(단위 술어 범위) · temporality_analyzer(절 시점·해소 단서·time_scope) · experiencer_analyzer(절 주체·문장 내 승계)
          ─▶ semantic_conflict_guard(의성어 불일치·양태 구토·사지 떨림·코피·부위 단독, SILVER 보호)
          ─▶ symptom_context_builder(model_input 표시만) ─▶ JSON {source_text, mentions[], context}
```

- 증상 찾기(P5 정규화)와 의미 해석(부정·시점·주체)을 분리: 부정된 증상도 mention 으로 남기고 assertion 만 바꾼다.
- 오프셋은 원문 code point. 모든 구간은 kiwi 토큰 start/len 의 합집합 → raw_span = source_text[start:end].
- P5 원본(STEP28.8 `policies.py`)은 import 만. NLU 전처리(질의 시작점·대체 질의)로 P5 실패를 피하되 결과는 P5 의 것.
- 비교군 NLU_P0–P5 는 `clinical_nlu_pipeline.py` 문서열. 게이트·판정은 `build_report.py` 문서열(평가 전 고정).
- 금지: LLM·다운로드·설치·재학습·P5/제품/PatientState/49질환 모델 변경. model_input 은 표시만(applied=false).
