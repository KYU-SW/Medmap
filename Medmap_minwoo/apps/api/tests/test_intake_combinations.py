import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def extract(text: str) -> dict:
    response = client.post("/v1/intake/extract", json={"transcript": text})
    assert response.status_code == 200
    return response.json()


@pytest.mark.parametrize(
    ("expected_name", "text"),
    [
        ("두통", "머리가 어제부터 아파요"),
        ("발열", "열은 어제부터 나요"),
        ("기침", "기침은 어제부터 나요"),
        ("호흡곤란", "숨이 어제부터 차요"),
        ("가슴 답답함", "가슴이 어제부터 답답해요"),
        ("복통", "배가 어제부터 아파요"),
        ("구토", "구토는 어제부터 있었어요"),
    ],
)
def test_onset_after_each_supported_symptom(expected_name: str, text: str) -> None:
    result = extract(text)
    assert len(result["symptoms"]) == 1
    assert result["symptoms"][0]["name"] == expected_name
    assert result["symptoms"][0]["onset"] == "어제부터"


@pytest.mark.parametrize(
    ("expected_name", "text"),
    [
        ("두통", "3일 전부터 머리가 조금 아파요"),
        ("발열", "3일 전부터 열이 조금 나요"),
        ("기침", "3일 전부터 기침이 조금 나요"),
        ("호흡곤란", "3일 전부터 숨이 조금 차요"),
        ("가슴 답답함", "3일 전부터 가슴이 조금 답답해요"),
        ("복통", "3일 전부터 배가 조금 아파요"),
        ("구토", "3일 전부터 구토를 조금 했어요"),
    ],
)
def test_onset_before_and_mild_severity_for_every_symptom(
    expected_name: str, text: str
) -> None:
    result = extract(text)
    assert len(result["symptoms"]) == 1
    assert result["symptoms"][0]["name"] == expected_name
    assert result["symptoms"][0]["onset"] == "3일 전부터"
    assert result["symptoms"][0]["severity"] == "경미함"


def test_all_supported_symptoms_keep_their_own_fields_in_one_record() -> None:
    result = extract(
        "머리가 어제부터 조금 아프고, 열은 없고, "
        "기침은 3일 전부터 심하고, 숨은 차지 않고, "
        "가슴이 오늘부터 답답하고, 배는 이틀 전부터 많이 아프고, "
        "구토는 없어요. 알레르기약을 먹고 페니실린 알레르기가 있어요."
    )
    symptoms = {item["name"]: item for item in result["symptoms"]}
    assert set(symptoms) == {
        "두통", "발열", "기침", "호흡곤란", "가슴 답답함", "복통", "구토"
    }
    assert symptoms["두통"]["status"] == "present"
    assert symptoms["두통"]["onset"] == "어제부터"
    assert symptoms["두통"]["severity"] == "경미함"
    assert symptoms["발열"]["status"] == "absent"
    assert symptoms["기침"]["onset"] == "3일 전부터"
    assert symptoms["기침"]["severity"] == "심함"
    assert symptoms["호흡곤란"]["status"] == "absent"
    assert symptoms["가슴 답답함"]["onset"] == "오늘부터"
    assert symptoms["복통"]["onset"] == "2일 전부터"
    assert symptoms["복통"]["severity"] == "심함"
    assert symptoms["구토"]["status"] == "absent"
    assert result["medications"] == ["알레르기약"]
    assert result["allergies"] == ["페니실린"]


@pytest.mark.parametrize(
    ("text", "expected_onsets"),
    [
        ("어제부터 머리가 아프고 2일 전부터 배가 아파요", ["어제부터", "2일 전부터"]),
        ("머리는 어제부터 아프고 배는 이틀 전부터 아파요", ["어제부터", "2일 전부터"]),
        ("머리가 아픈 건 어제부터고 배가 아픈 건 2일 전부터예요", ["어제부터", "2일 전부터"]),
    ],
)
def test_reordered_time_expressions_do_not_cross_between_symptoms(
    text: str, expected_onsets: list[str]
) -> None:
    result = extract(text)
    assert [item["name"] for item in result["symptoms"]] == ["두통", "복통"]
    assert [item["onset"] for item in result["symptoms"]] == expected_onsets
