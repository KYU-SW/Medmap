import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def extract(text: str) -> dict:
    response = client.post("/v1/intake/extract", json={"transcript": text})
    assert response.status_code == 200
    return response.json()


def statuses(result: dict) -> list[tuple[str, str]]:
    return [(item["name"], item["status"]) for item in result["symptoms"]]


def others(result: dict) -> list[tuple[str, str]]:
    return [(item["person"], item["symptom"]) for item in result["others_symptoms"]]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("열이 있는 것 같기도 하고 잘 모르겠어요", [("발열", "uncertain")]),
        ("기침은 잘 모르겠어요", [("기침", "uncertain")]),
        ("확실하진 않은데 열이 있어요", [("발열", "uncertain")]),
        ("열은 없는 것 같은데 잘 모르겠어요", [("발열", "uncertain")]),
        ("머리가 아프고 열은 잘 모르겠어요", [("두통", "present"), ("발열", "uncertain")]),
        ("어제부터 열이 나요 근데 기침은 있는지 없는지 헷갈려요", [("발열", "present"), ("기침", "uncertain")]),
    ],
)
def test_hedged_symptoms_are_uncertain(text: str, expected: list) -> None:
    assert statuses(extract(text)) == expected


@pytest.mark.parametrize(
    "text",
    ["열이 나는 것 같아요", "이거 때문에 그런지는 모르겠는데 어젯밤 구토도 했어요"],
)
def test_ordinary_hedges_and_doubted_causes_stay_present(text: str) -> None:
    assert all(status == "present" for _, status in statuses(extract(text)))


def test_uncertain_symptom_keeps_what_the_patient_said() -> None:
    symptom = extract("어제부터 열이 있는 것 같기도 하고 잘 모르겠어요")["symptoms"][0]
    assert symptom["status"] == "uncertain"
    assert symptom["onset"] == "어제부터"


@pytest.mark.parametrize(
    ("text", "patient", "other"),
    [
        ("남편도 기침을 해요", [], [("남편", "기침")]),
        ("아이가 열이 나요", [], [("아이", "발열")]),
        ("남편도 기침을 하고 저는 열이 나요", [("발열", "present")], [("남편", "기침")]),
        ("어제부터 머리가 아파요. 남편도 기침을 해요", [("두통", "present")], [("남편", "기침")]),
        ("동생은 기침을 안 해요", [], []),
        ("아이고 머리야 너무 아파요", [("두통", "present")], []),
    ],
)
def test_other_peoples_symptoms_are_kept_apart(text: str, patient: list, other: list) -> None:
    result = extract(text)
    assert statuses(result) == patient
    assert others(result) == other


def test_family_history_is_not_patient_history() -> None:
    result = extract("엄마가 고혈압이 있고 저는 당뇨가 있어요")
    assert result["medical_history"] == ["당뇨"]
    assert others(result) == [("엄마", "고혈압")]


@pytest.mark.parametrize(
    ("text", "name"),
    [("기침을 안 해요", "기침"), ("설사를 안 했어요", "설사")],
)
def test_object_particle_negation_is_absent(text: str, name: str) -> None:
    assert statuses(extract(text)) == [(name, "absent")]
