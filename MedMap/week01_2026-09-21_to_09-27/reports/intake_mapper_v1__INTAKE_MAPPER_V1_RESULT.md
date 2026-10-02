# MedMap Intake Mapper v1 — 평가 결과 (2026-09-23)

제품 engineering gate. 임상 성능 주장 아님. 1회 평가, 결과를 보고 alias를 고치지 않음.

- fixture: `tests/fixtures/intake_mapper_eval.json` 266문장 / gold 363(POS 273, NEG 90). 매퍼와 분리된 서브에이전트(sonnet)가 alias 사전을 보지 않고 작성. SHA 1f5e1a42… 는 매퍼 작성 전 동결(`00_fixture_sha256_frozen_before_mapper.txt`).
- 매퍼 SHA 동결 후 평가(`00b_…`): aliases 6c7e2556…, mapper.py 2dff09b1….
- 결과 원본: `01_eval_result.json`(지표·카테고리별·오류 전체·예측 전체).

## 공식 결과 (primary = 266문장 전체)
| 지표 | 값 |
|---|---|
| precision / recall / F1 | 0.9386 / 0.7163 / 0.8125 (TP 260, FP 17, FN 103) |
| POSITIVE P / R | 0.9263 / 0.7363 |
| NEGATIVE P / R | 0.9833 / 0.6556 |
| negation accuracy | 0.9077 (59/65) |
| exact sentence match | 0.6316 (168/266) |
| **Gate** 전체 P ≥ 0.95 | **FAIL** |
| **Gate** NEG P ≥ 0.95 | **PASS** |

temporal_ambiguous(5) 제외 민감도: P 0.9489 → 여전히 FAIL.

## FP 17건 분류 (작성자 판독, 비공식)
- 매퍼 오류 8: 부정 누락 4(S066 "맞지는 못했어요", S102 "아닌데"의 '아닌' 미탐지, S172 동사 앞 "안 울렁거려요", S198 지속 동사 '안 빠져요' 누락) · 과거 시간표현 누락 3(S263/265/266 "며칠 전엔", "저번주까지", "어제는…") · 과확장 alias 1(S255 "숨소리가 거칠어요"→E_112).
- gold 누락 의심 9: 명시적 기침인데 E_201 없음(S012, S110, S163, S186 — S1xx "가래 없는 마른기침"에는 E_201을 붙여 규칙이 불일치) · 통증이 명시됐는데 E_53 없음(S034/035/036/095/096 — fixture 규칙 5와 불일치).
- 비공식 민감도: 9건을 gold로 인정하면 P = 269/277 = 0.9711. **공식 판정은 FAIL 유지**, gold 재판정은 제3자 몫.

## gold 노이즈(FN 쪽)
plain "가래 나오고"→E_77 POS, "피곤해요"→E_89 POS(규칙 6과 불일치), "콧물나고"→E_182 POS(색 언급 없음) 등 매퍼 정책(precision 우선)과 다른 라벨이 있음.
