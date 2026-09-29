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
