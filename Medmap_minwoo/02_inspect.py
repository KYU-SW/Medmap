"""작은 샘플부터 열어 실제 구조를 확인합니다."""
from pathlib import Path
import ast
import json
import pandas as pd

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
evidences = json.loads((DATA / "release_evidences.json").read_text(encoding="utf-8"))
conditions = json.loads((DATA / "release_conditions.json").read_text(encoding="utf-8"))

if __name__ == "__main__":
    print("질환 수:", len(conditions), "소견 수:", len(evidences))
    df = pd.read_csv(DATA / "release_train_patients.zip", nrows=3)
    print("샘플 shape:", df.shape, "컬럼:", df.columns.tolist())
    samples = []
    for index, row in df.iterrows():
        # CSV의 리스트 모양 문자열을 안전하게 리스트로 변환합니다. eval은 사용하지 않습니다.
        tokens = ast.literal_eval(row["EVIDENCES"])
        decoded = []
        for token in tokens:
            code, separator, value = token.partition("_@_")
            definition = evidences[code]
            meaning = definition["value_meaning"].get(value, {}).get("en", value)
            decoded.append({"raw": token, "code": code,
                            "question": definition["question_en"],
                            "type": definition["data_type"],
                            "value": meaning if separator else True})
        sample = {"row_index": int(index), "age": int(row["AGE"]),
                  "sex": row["SEX"], "label": row["PATHOLOGY"],
                  "initial_evidence": row["INITIAL_EVIDENCE"],
                  "evidences": decoded,
                  "differential": ast.literal_eval(row["DIFFERENTIAL_DIAGNOSIS"])}
        samples.append(sample)
        print(json.dumps(sample, ensure_ascii=False, indent=2))
    (ROOT / "samples.json").write_text(
        json.dumps(samples, ensure_ascii=False, indent=2), encoding="utf-8")
