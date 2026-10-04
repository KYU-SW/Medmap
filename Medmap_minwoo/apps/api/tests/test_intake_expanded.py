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
    result = extract("머리가 아프고 엉덩이가 아파요")
    assert [item["name"] for item in result["symptoms"]] == ["두통"]
    assert result["unrecognized_fragments"] == ["엉덩이가 아파요"]


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("머리통증이 있어요", "두통"),
        ("머리 통증이 있어요", "두통"),
        ("허리통증이 있어요", "요통"),
        ("가슴통증이 있어요", "흉통"),
        ("복부통증이 있어요", "복통"),
        ("배 통증이 심해요", "복통"),
        ("목감기에 걸렸어요", "인후통"),
        ("코감기 기운이 있어요", "콧물"),
        ("배탈이 났어요", "복통"),
        ("위경련이 왔어요", "복통"),
        ("배가 살살 아파요", "복통"),
        ("배가 쿡쿡 쑤셔요", "복통"),
        ("머리가 욱신욱신 아파요", "두통"),
        ("허리가 뻐근해요", "요통"),
        ("숨이 가빠요", "호흡곤란"),
        ("몸이 무거워요", "피로"),
        ("머리아파요", "두통"),
        ("허리아파요", "요통"),
    ],
)
def test_recognizes_compound_and_colloquial_expressions(text: str, name: str) -> None:
    result = extract(text)
    assert [item["name"] for item in result["symptoms"]] == [name], text
    assert result["symptoms"][0]["status"] == "present"
    assert result["unrecognized_fragments"] == []


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("가슴이 두근거려요", "두근거림"),
        ("가슴이 벌렁벌렁해요", "두근거림"),
        ("손발이 저려요", "저림"),
        ("체했어요", "소화불량"),
        ("소화가 안 돼요", "소화불량"),
        ("속이 더부룩해요", "소화불량"),
        ("속이 쓰려요", "속쓰림"),
        ("속쓰려요", "속쓰림"),
        ("입맛이 없어요", "식욕부진"),
        ("잠을 못 자요", "불면"),
        ("다리가 퉁퉁 부었어요", "부종"),
        ("귀가 아파요", "귀 통증"),
        ("눈이 따가워요", "눈 통증"),
        ("이가 시려요", "치통"),
        ("식은땀이 나요", "식은땀"),
    ],
)
def test_recognizes_new_common_symptoms(text: str, name: str) -> None:
    result = extract(text)
    assert [item["name"] for item in result["symptoms"]] == [name], text
    assert result["symptoms"][0]["status"] == "present"


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("두근거림은 없어요", "두근거림"),
        ("저리지 않아요", "저림"),
        ("소화는 잘 돼요", "소화불량"),
        ("입맛은 괜찮아요", "식욕부진"),
        ("잠은 잘 자요", "불면"),
        ("부기는 빠졌어요", "부종"),
        ("귀는 안 아파요", "귀 통증"),
        ("땀은 안 나요", "식은땀"),
        ("머리 통증은 없어요", "두통"),
    ],
)
def test_recognizes_new_symptom_absence(text: str, name: str) -> None:
    result = extract(text)
    assert [item["name"] for item in result["symptoms"]] == [name], text
    assert result["symptoms"][0]["status"] == "absent"


@pytest.mark.parametrize(
    ("text", "medication"),
    [("두통약을 먹었어요", "두통약"), ("기침약을 먹었어요", "기침약"), ("설사약을 먹었어요", "설사약")],
)
def test_medicine_names_are_not_symptoms(text: str, medication: str) -> None:
    result = extract(text)
    assert result["symptoms"] == []
    assert result["medications"] == [medication]


@pytest.mark.parametrize("text", ["두통이 약간 있어요", "기침이 약해졌어요"])
def test_yak_words_that_are_not_medicine_keep_the_symptom(text: str) -> None:
    assert len(extract(text)["symptoms"]) == 1


@pytest.mark.parametrize("text", ["아이가 아파요", "감기에 걸렸어요"])
def test_vague_expressions_are_flagged_for_review(text: str) -> None:
    result = extract(text)
    assert result["symptoms"] == []
    assert result["unrecognized_fragments"] == [text]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("허리가 뻐근하고 아파요", [("요통", "present")]),
        ("어제부터는 허리가 뻐근하고 아파요", [("요통", "present")]),
        ("가슴이 답답하고 아파요", [("가슴 답답함", "present"), ("흉통", "present")]),
        ("가슴이 답답하지만 아프진 않아요", [("가슴 답답함", "present"), ("흉통", "absent")]),
        ("배가 더부룩하고 아파요", [("소화불량", "present"), ("복통", "present")]),
        ("속이 쓰리고 아파요", [("속쓰림", "present"), ("복통", "present")]),
        ("목이 칼칼하고 따끔거려요", [("인후통", "present")]),
        ("눈이 따갑고 아파요", [("눈 통증", "present")]),
    ],
)
def test_predicate_without_subject_borrows_previous_subject(text: str, expected: list) -> None:
    result = extract(text)
    assert [(item["name"], item["status"]) for item in result["symptoms"]] == expected, text
    assert result["unrecognized_fragments"] == []


def test_borrowed_subject_keeps_real_source_text() -> None:
    symptoms = symptoms_by_name(extract("이틀 전부터 가슴이 답답하고 많이 아파요"))
    assert symptoms["흉통"]["source_text"] == "가슴이 답답하고 많이 아파요"
    assert symptoms["흉통"]["severity"] == "심함"


@pytest.mark.parametrize(("text", "fragment"), [("열이 나고 아파요", "아파요"), ("코가 막히고 답답해요", "답답해요")])
def test_ambiguous_predicate_without_subject_is_flagged(text: str, fragment: str) -> None:
    assert extract(text)["unrecognized_fragments"] == [fragment]


def test_time_adverb_before_borrowed_predicate() -> None:
    result = extract("가슴이 답답하고 지금은 아파요")
    assert [item["name"] for item in result["symptoms"]] == ["가슴 답답함", "흉통"]
    assert result["unrecognized_fragments"] == []
