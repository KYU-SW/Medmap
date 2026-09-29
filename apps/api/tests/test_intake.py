from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def extract(text: str) -> dict:
    response = client.post("/v1/intake/extract", json={"transcript": text})
    assert response.status_code == 200
    return response.json()


def test_extracts_present_and_absent_symptoms_with_time() -> None:
    result = extract("어제부터 머리가 아프고 열은 없어요.")
    assert result["symptoms"] == [
        {
            "name": "두통",
            "status": "present",
            "body_site": "머리",
            "onset": "어제부터",
            "severity": None,
            "source_text": "머리가 아프",
        },
        {
            "name": "발열",
            "status": "absent",
            "body_site": None,
            "onset": None,
            "severity": None,
            "source_text": "열은 없",
        },
    ]
    assert result["needs_user_confirmation"] is True


def test_extracts_severity_medication_and_allergy() -> None:
    result = extract("기침이 조금 나요. 당뇨약을 먹고 페니실린 알레르기가 있어요.")
    assert result["symptoms"][0]["name"] == "기침"
    assert result["symptoms"][0]["severity"] == "경미함"
    assert result["medications"] == ["당뇨약"]
    assert result["allergies"] == ["페니실린"]


def test_allergy_medicine_is_not_mistaken_for_an_allergen() -> None:
    result = extract(
        "머리가 아프고 복통이 있어요 그리고 알레르기약도 복용했어요"
    )
    assert [item["name"] for item in result["symptoms"]] == ["두통", "복통"]
    assert result["medications"] == ["알레르기약"]
    assert result["allergies"] == []


def test_links_nearest_time_and_severity_to_each_symptom() -> None:
    result = extract(
        "어제부터 머리가 조금 아프고 3일 전부터 기침이 심해요."
    )
    assert result["symptoms"][0]["onset"] == "어제부터"
    assert result["symptoms"][0]["severity"] == "경미함"
    assert result["symptoms"][1]["onset"] == "3일 전부터"
    assert result["symptoms"][1]["severity"] == "심함"


def test_spoken_korean_time_and_spaced_allergy_medicine() -> None:
    result = extract(
        "어제부터 머리가 조금 아프고 삼일 전부터 기침이 심해요 "
        "추가로 알레르기 약도 복용하고 있어요"
    )
    assert result["symptoms"][0]["onset"] == "어제부터"
    assert result["symptoms"][0]["severity"] == "경미함"
    assert result["symptoms"][1]["onset"] == "3일 전부터"
    assert result["symptoms"][1]["severity"] == "심함"
    assert result["medications"] == ["알레르기약"]
    assert result["allergies"] == []


def test_keeps_all_symptoms_when_intensity_is_inside_expression() -> None:
    result = extract(
        "어제부터 머리가 조금 아프고 이 일 전부터 기침이 심했어요 "
        "추가로 배도 많이 아파요"
    )
    assert [item["name"] for item in result["symptoms"]] == [
        "두통", "기침", "복통"
    ]
    assert result["symptoms"][1]["onset"] == "2일 전부터"
    assert result["symptoms"][1]["severity"] == "심함"
    assert result["symptoms"][2]["severity"] == "심함"
    assert result["symptoms"][2]["onset"] is None
