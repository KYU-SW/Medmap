"""STEP28.6 격리 작성 입력 준비(LLM 호출 없음).

입력 표현(고유, 원문 그대로): SILVER442(STEP25 BERT-NER-KO 증상 span) · WEAKNON903(STEP26 EXT_EVAL weak-non: 질환·신체부위·치료 등 — 비증상 오매핑 위험 측정용) ·
 SMOKE(STEP28.5 smoke 10 문장). 같은 문자열은 한 번만(출처는 data/expression_manifest.csv 에 모두 기록).
안전 검사: 개인정보 패턴(전화·주민번호·이메일·카드) 0 · 입력에 UMLS/SNOMED 영어 문자열·MedMap concept id 없음(한국어 문자열만) · 조각 ≤ 230 행·≤ 45 KB.
출력: ~/medmap_step28_6_ws/in/{expressions_c01..cNN.tsv, author_instructions.md, audit_instructions.md} · data/expression_manifest.csv · outputs/input_safety_check.json
"""
import re

import s286_common as S

PII = re.compile(r"(\d{2,3}-\d{3,4}-\d{4}|\d{6}-[1-4]\d{6}|[\w.+-]+@[\w-]+\.[\w.]+|\d{4}-\d{4}-\d{4}-\d{4})")

AUTHOR = """# 작업: 한국어 의학 표현 → 영어 의학 용어 (용어 대응표 작성)

너는 한국어와 영어에 능통한 의학 용어 전문가다. 입력 파일의 각 행은 한국어 의학 문서·상담 답변에서 잘라낸 짧은 표현이다(조사·어미가 붙어 있을 수 있음).
각 표현이 **뜻하는 의학 개념**을 표준 영어 의학 용어로 옮긴다. 다른 파일·폴더는 읽지 않는다. 입력 파일과 이 지시문만 쓴다.

## 출력 (탭 구분 TSV, UTF-8, 첫 줄 헤더, 입력과 같은 순서·같은 id, 행 추가·삭제 금지)
id	korean	expr_type	english_preferred	english_synonyms	body_site_en	confidence	note

- expr_type: SYMPTOM_OR_SIGN · DISEASE_OR_DIAGNOSIS · ANATOMY · DRUG_OR_TREATMENT · TEST_OR_PROCEDURE · OTHER · UNCLEAR 중 하나
- english_preferred: 그 개념을 가리키는 표준 영어 의학 용어 1개(임상 용어집에서 쓰는 이름, 소문자 시작 가능). 뜻을 정확히 옮길 수 없으면 비워 둔다.
- english_synonyms: 같은 뜻의 다른 표준 영어 표현 최대 3개, ';' 로 구분. 없으면 비움.
- body_site_en: 표현이 '증상 + 신체 부위'(예: 어느 부위의 통증)이면 그 부위 영어 이름. 아니면 비움.
- confidence: HIGH · MEDIUM · LOW
- note: 15 단어 이내 메모(선택). 탭·줄바꿈 금지.

## 규칙
1. 뜻을 그대로 옮긴다. 같은 단어(예: 피, 통증)나 같은 장기 계통을 공유하더라도 **다른 증상·다른 개념으로 바꾸지 않는다**. 정확한 대응어가 없으면 english_preferred 를 비우고 confidence LOW.
2. 질환·진단명이면 expr_type DISEASE_OR_DIAGNOSIS 로 하고 그 질환의 영어 이름을 쓴다(증상 이름으로 바꾸지 않는다).
3. 신체 부위만 있는 표현은 ANATOMY, 약·치료·수술은 DRUG_OR_TREATMENT, 검사는 TEST_OR_PROCEDURE.
4. 너무 짧거나 앞뒤 문맥 없이는 뜻을 정할 수 없는 조각이면 UNCLEAR, 영어 칸은 비움.
5. 조사·어미(이/가/을/를/의/은/는/로/과 …)는 무시하고 핵심 의미만 옮긴다. 수식어(예: 만성, 회전성)가 의미를 바꾸면 반영한다.
6. 추측으로 채우지 않는다. 모르면 비운다.
"""

AUDIT = """# 작업: 한국어 표현과 영어 의학 개념의 의미 일치 판정

너는 의학 용어 감사자다. 입력 파일의 각 행에는 한국어 의학 표현(조사 포함 가능)과, 그 표현에 연결된 후보 개념 하나(HPO id·영어 이름·정의)가 있다.
후보 개념이 한국어 표현의 뜻과 일치하는지 판정한다. 다른 파일·폴더는 읽지 않는다.

## 출력 (탭 구분 TSV, 첫 줄 헤더, 입력과 같은 순서·같은 row, 행 추가·삭제 금지)
row	judgement	reason

- judgement: EXACT(같은 뜻) · BROADER(개념이 한국어보다 넓음) · NARROWER(개념이 한국어보다 좁음) · RELATED_ONLY(관련 있지만 다른 개념) · WRONG(다른 뜻) · UNCLEAR(판단 불가)
- reason: 15 단어 이내. 탭·줄바꿈 금지.
- 이름이 비슷해도 정의가 다르면 EXACT 가 아니다. 같은 단어를 공유하는 다른 증상은 RELATED_ONLY 또는 WRONG.
"""


def main():
    sil = S.read_csv(S.S28.STEP / "data/external_silver_expansion.csv")
    wn = S.read_csv(S.S28.OUT / "weak_non_check.csv")
    smoke = ["코피가 나요", "머리가 아파요", "열이 없어요", "숨이 차요", "토했어요", "메스꺼워요", "목이 아파요", "고혈압", "결핵",
             "어제부터 코피가 나고 머리가 아파요. 열은 없어요."]
    man, order = {}, []
    for src, texts in (("SILVER442", [r["raw_expression"] for r in sil]), ("WEAKNON903", [r["text"] for r in wn]), ("SMOKE", smoke)):
        for t in texts:
            t = t.replace("\t", " ").replace("\n", " ").strip()
            if t not in man:
                man[t] = set()
                order.append(t)
            man[t].add(src)
    rows = [{"id": f"K{i + 1:04d}", "korean": t, "sources": ";".join(sorted(man[t]))} for i, t in enumerate(order)]
    S.wcsv(S.DATA / "expression_manifest.csv", rows)
    for f in (S.WS / "in").glob("expressions_c*.tsv"):
        f.unlink()
    chunks = []
    for c in range(0, len(rows), S.CHUNK):
        part = rows[c:c + S.CHUNK]
        p = S.WS / "in" / f"expressions_c{c // S.CHUNK + 1:02d}.tsv"
        p.write_text("id\tkorean\n" + "".join(f"{r['id']}\t{r['korean']}\n" for r in part), encoding="utf-8")
        chunks.append({"file": p.name, "rows": len(part), "bytes": p.stat().st_size})
    (S.WS / "in/author_instructions.md").write_text(AUTHOR, encoding="utf-8")
    (S.WS / "in/audit_instructions.md").write_text(AUDIT, encoding="utf-8")
    pii = [r["id"] for r in rows if PII.search(r["korean"])]
    latin = [r["korean"] for r in rows if re.search(r"[A-Za-z]{4,}", r["korean"])]
    chk = {"n_expressions": len(rows), "by_source": {s: sum(s in r["sources"] for r in rows) for s in ("SILVER442", "WEAKNON903", "SMOKE")},
           "chunks": chunks, "pii_matches": pii, "inputs_with_latin_words(검토용)": latin[:20],
           "sent_to_llm": "한국어 표현 문자열 + id + 지시문만. 모델 예측·MedMap 77 목록·UMLS/SNOMED 문자열·MDRKOR 미포함",
           "all_chunks_le_45KB_230rows": all(c["bytes"] <= 45000 and c["rows"] <= 230 for c in chunks)}
    S.dump_json(S.OUT / "input_safety_check.json", chk)
    print(S.dumps(chk))
    assert not pii and chk["all_chunks_le_45KB_230rows"]


if __name__ == "__main__":
    main()
