import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def extract(text: str) -> dict:
    response = client.post("/v1/intake/extract", json={"transcript": text})
    assert response.status_code == 200
    return response.json()


def symptoms_by_name(result: dict) -> dict[str, dict]:
    return {item["name"]: item for item in result["symptoms"]}


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("가슴이 콕콕 찌르듯이 아파요", "흉통"),
        ("흉통이 있어요", "흉통"),
        ("목이 따끔거려요", "인후통"),
        ("침 삼키기가 힘들어요", "인후통"),
        ("콧물이 계속 나요", "콧물"),
        ("코가 꽉 막혔어요", "코막힘"),
        ("가래가 끓어요", "가래"),
        ("몸이 으슬으슬 추워요", "오한"),
        ("몸살 기운이 있어요", "근육통"),
        ("온몸이 쑤셔요", "근육통"),
        ("허리가 결려요", "요통"),
        ("어지러워요", "어지러움"),
        ("머리가 핑 돌아요", "어지러움"),
        ("속이 메스꺼워요", "메스꺼움"),
        ("토할 것 같아요", "메스꺼움"),
        ("설사를 했어요", "설사"),
        ("변이 묽어요", "설사"),
        ("변비가 있어요", "변비"),
        ("팔에 두드러기가 났어요", "발진"),
        ("피부가 빨갛게 올라왔어요", "발진"),
        ("요즘 너무 피곤해요", "피로"),
        ("기운이 없어요", "피로"),
    ],
)
def test_recognizes_expanded_symptoms(text: str, name: str) -> None:
    result = extract(text)
    assert [item["name"] for item in result["symptoms"]] == [name], text
    assert result["symptoms"][0]["status"] == "present"
    assert result["unrecognized_fragments"] == []


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("가슴은 안 아파요", "흉통"),
        ("목은 아프지 않아요", "인후통"),
        ("콧물은 안 나요", "콧물"),
        ("코는 안 막혀요", "코막힘"),
        ("가래는 없어요", "가래"),
        ("오한은 없어요", "오한"),
        ("몸살은 없어요", "근육통"),
        ("허리는 안 아파요", "요통"),
        ("어지럽지 않아요", "어지러움"),
        ("메스꺼움은 없어요", "메스꺼움"),
        ("설사는 안 했어요", "설사"),
        ("두드러기는 없어요", "발진"),
        ("피곤하지 않아요", "피로"),
    ],
)
def test_recognizes_expanded_symptom_absence(text: str, name: str) -> None:
    result = extract(text)
    assert [item["name"] for item in result["symptoms"]] == [name], text
    assert result["symptoms"][0]["status"] == "absent"


def test_keeps_expanded_symptoms_apart_in_one_sentence() -> None:
    result = extract("이틀 전부터 목이 아프고 콧물이 나요. 어지럽고 설사를 하루 3번 했어요.")
    symptoms = symptoms_by_name(result)
    assert set(symptoms) == {"인후통", "콧물", "어지러움", "설사"}
    assert symptoms["인후통"]["onset"] == "2일 전부터"
    assert symptoms["인후통"]["body_site"] == "목"
    assert symptoms["설사"]["frequency"] == "하루 3회"
    assert symptoms["설사"]["onset"] is None
    assert symptoms["어지러움"]["frequency"] is None


def test_records_body_temperature_as_fever_severity() -> None:
    symptoms = symptoms_by_name(extract("어젯밤부터 열이 38.5도까지 올랐어요"))
    assert symptoms["발열"]["severity"] == "38.5℃"
    assert symptoms["발열"]["onset"] == "어젯밤부터"


@pytest.mark.parametrize(
    "text",
    ["열흘 전부터 기침을 해요", "해열제를 먹었어요", "열심히 일했더니 허리가 아파요", "구토를 열 번 했어요"],
)
def test_words_containing_yeol_are_not_fever(text: str) -> None:
    assert "발열" not in symptoms_by_name(extract(text))


def test_extracts_medical_history_and_surgery() -> None:
    result = extract("고혈압이 있고 작년에 당뇨병 진단을 받았어요. 5년 전에 맹장 수술을 받았어요.")
    assert result["medical_history"] == ["고혈압", "당뇨병", "맹장 수술"]
    assert result["unrecognized_fragments"] == []


def test_denied_medical_history_is_not_recorded() -> None:
    result = extract("천식은 없고 고혈압 약을 먹고 있어요")
    assert result["medical_history"] == []


def test_reports_only_the_unsupported_part_of_a_sentence() -> None:
    result = extract("머리가 아프고 손이 저려요")
    assert [item["name"] for item in result["symptoms"]] == ["두통"]
    assert result["unrecognized_fragments"] == ["손이 저려요"]
