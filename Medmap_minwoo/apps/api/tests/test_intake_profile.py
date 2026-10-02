import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def profile(text: str) -> dict:
    response = client.post("/v1/intake/extract", json={"transcript": text})
    assert response.status_code == 200
    return {key: value for key, value in response.json()["profile"].items() if value is not None}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("저는 34살 여자예요", {"age": 34, "sex": "female"}),
        ("나이는 70이고 남자입니다", {"age": 70, "sex": "male"}),
        ("20세 남성이고 기침을 해요", {"age": 20, "sex": "male"}),
        ("담배를 하루에 반 갑 피워요", {"smoking": "current"}),
        ("담배는 3년 전에 끊었어요", {"smoking": "former"}),
        ("담배는 안 피워요", {"smoking": "never"}),
        ("술은 가끔 마셔요", {"drinking": "yes"}),
        ("술은 안 마셔요", {"drinking": "no"}),
        ("임신 중이에요", {"sex": "female", "pregnancy": "yes"}),
        ("임신은 아니에요", {"sex": "female", "pregnancy": "no"}),
        ("임신인지 잘 모르겠어요", {"sex": "female", "pregnancy": "unknown"}),
    ],
)
def test_basic_information_from_speech(text: str, expected: dict) -> None:
    assert profile(text) == expected


@pytest.mark.parametrize(
    "text",
    ["남편이 담배를 피워요", "아이가 5살이에요", "3살 때 수술을 받았어요", "여자친구가 기침을 해요", "어제부터 머리가 아파요"],
)
def test_no_basic_information_from_other_people_or_symptoms(text: str) -> None:
    assert profile(text) == {}


@pytest.mark.parametrize("text", ["저는 34살이에요", "아이가 5살이에요"])
def test_age_sentences_are_not_flagged_as_unrecognized(text: str) -> None:
    response = client.post("/v1/intake/extract", json={"transcript": text})
    assert response.json()["unrecognized_fragments"] == []
