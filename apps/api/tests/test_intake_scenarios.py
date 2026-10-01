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


def test_category_1_multiple_symptoms_in_one_sentence() -> None:
    result = extract(
        "머리가 아프고 열이 나면서 기침을 해요. 숨도 차고 가슴이 답답하고 "
        "배가 아프면서 구토도 했어요."
    )
    assert set(symptoms_by_name(result)) == {
        "두통", "발열", "기침", "호흡곤란", "가슴 답답함", "복통", "구토"
    }


@pytest.mark.parametrize(
    ("text", "present", "absent"),
    [
        ("열은 없고 기침만 있어요", {"기침"}, {"발열"}),
        ("머리는 안 아픈데 배는 아파요", {"복통"}, {"두통"}),
        ("숨은 차지 않고 가슴만 답답해요", {"가슴 답답함"}, {"호흡곤란"}),
    ],
)
def test_category_2_mixed_present_and_absent_symptoms(
    text: str, present: set[str], absent: set[str]
) -> None:
    symptoms = symptoms_by_name(extract(text))
    assert {name for name, item in symptoms.items() if item["status"] == "present"} == present
    assert {name for name, item in symptoms.items() if item["status"] == "absent"} == absent


def test_category_3_each_symptom_keeps_its_own_onset() -> None:
    symptoms = symptoms_by_name(
        extract("두통은 어제부터 있고 기침은 3일 전부터, 복통은 오늘 아침부터 있어요")
    )
    assert symptoms["두통"]["onset"] == "어제부터"
    assert symptoms["기침"]["onset"] == "3일 전부터"
    assert symptoms["복통"]["onset"] == "오늘 아침부터"


def test_onset_between_head_and_pain_keeps_headache_and_severity_separate() -> None:
    result = extract(
        "머리가 어제부터 너무 아프고요 배는 3일 전부터 아팠어요 "
        "그리고 알레르기약도 먹었어요"
    )
    symptoms = symptoms_by_name(result)
    assert set(symptoms) == {"두통", "복통"}
    assert symptoms["두통"]["onset"] == "어제부터"
    assert symptoms["두통"]["severity"] == "심함"
    assert symptoms["복통"]["onset"] == "3일 전부터"
    assert symptoms["복통"]["severity"] is None
    assert result["medications"] == ["알레르기약"]
    assert result["allergies"] == []


@pytest.mark.parametrize(
    ("text", "medications", "allergies"),
    [
        ("알레르기약을 먹고 있어요", ["알레르기약"], []),
        ("그리고 알레르기 약도 먹었어요", ["알레르기약"], []),
        ("혈압약과 당뇨약을 복용하고 페니실린 알레르기가 있어요", ["혈압약", "당뇨약"], ["페니실린"]),
        ("꽃가루 알레르기가 있고 비염약도 먹어요", ["비염약"], ["꽃가루"]),
    ],
)
def test_category_4_distinguishes_medications_and_allergies(
    text: str, medications: list[str], allergies: list[str]
) -> None:
    result = extract(text)
    assert result["medications"] == medications
    assert result["allergies"] == allergies


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("배가 아파요", "복통"),
        ("속이 아파요", "복통"),
        ("머리가 지끈거려요", "두통"),
        ("토했어요", "구토"),
        ("숨쉬기 힘들어요", "호흡곤란"),
    ],
)
def test_category_5_common_everyday_expressions(text: str, expected: str) -> None:
    result = extract(text)
    assert [item["name"] for item in result["symptoms"]] == [expected]


@pytest.mark.parametrize(
    ("text", "expected_severity"),
    [
        ("두통이 조금 있어요", "경미함"),
        ("기침이 너무 심해요", "심함"),
        ("복통이 처음에는 약했는데 오늘은 많이 심해졌어요", "심함"),
    ],
)
def test_category_6_current_severity_and_change(text: str, expected_severity: str) -> None:
    result = extract(text)
    assert result["symptoms"][0]["severity"] == expected_severity


@pytest.mark.parametrize(
    ("text", "expected_severity"),
    [
        ("복통이 있고 아픈 강도로 따지면 90점 정도예요", "90/100점"),
        ("두통이 있고 10점 만점에 8점이에요", "8/10점"),
        ("배가 아프고 통증 점수는 7점이에요", "7/10점"),
        ("배가 아프고 아픈 정도는 10중에 8정도로 아팠어요", "8/10점"),
    ],
)
def test_numeric_pain_scores(text: str, expected_severity: str) -> None:
    result = extract(text)
    assert result["symptoms"][0]["severity"] == expected_severity


def test_numeric_score_stays_with_the_nearest_symptom() -> None:
    result = extract(
        "어제부터 머리가 너무 아프고요 배는 2일 전부터 아팠는데 "
        "아픈 강도로 따지면 90점 정도예요"
    )
    symptoms = {item["name"]: item for item in result["symptoms"]}
    assert symptoms["두통"]["severity"] == "심함"
    assert symptoms["복통"]["severity"] == "90/100점"


def test_coordinated_pain_shares_onset_score_and_extracts_named_medicine() -> None:
    result = extract(
        "어제 밤부터 머리랑 배가 너무 아팠어요 고통의 정도는 한 10 정도 되는 것 같아요 "
        "그리고 머리가 아파서 타이레놀 먹었어요"
    )
    symptoms = symptoms_by_name(result)
    assert set(symptoms) == {"두통", "복통"}
    assert symptoms["두통"]["onset"] == "어제 밤부터"
    assert symptoms["복통"]["onset"] == "어제 밤부터"
    assert symptoms["두통"]["severity"] == "10/10점"
    assert symptoms["복통"]["severity"] == "10/10점"
    assert result["medications"] == ["타이레놀"]
    assert all(item["onset"] != "7일" for item in result["symptoms"])


def test_medicine_name_does_not_become_native_day_expression() -> None:
    result = extract("머리가 아파서 타이레놀을 먹었어요")
    assert result["symptoms"][0]["onset"] is None
    assert result["medications"] == ["타이레놀"]


def test_relative_day_and_time_of_day_are_kept_together() -> None:
    result = extract("어제 밤부터 머리가 아파요")
    assert result["symptoms"][0]["onset"] == "어제 밤부터"


def test_compact_yesterday_night_and_together_expression() -> None:
    result = extract(
        "어제부터 배가 아팠어요 아픈 정도는 10중에 8정도로 아팠고 "
        "머리도 같이 아팠어요 이거 때문에 그런지는 모르겠는데 어젯밤 구토도 했어요"
    )
    symptoms = {item["name"]: item for item in result["symptoms"]}
    assert set(symptoms) == {"복통", "두통", "구토"}
    assert symptoms["복통"]["onset"] == "어제부터"
    assert symptoms["복통"]["severity"] == "8/10점"
    assert symptoms["두통"]["status"] == "present"
    assert symptoms["두통"]["severity"] is None
    assert symptoms["구토"]["onset"] == "어젯밤"


def test_follow_up_improvement_resolution_and_medicine_are_linked_correctly() -> None:
    first = extract(
        "어제부터 머리가 너무 아프고 배도 아팠어요 그리고 구토는 한 7번 정도 한 것 같아요 "
        "약은 타이레놀 먹었어요"
    )
    assert first["medications"] == ["타이레놀"]
    assert symptoms_by_name(first)["구토"]["frequency"] == "7회"

    follow_up = extract(
        "이제 머리는 조금 괜찮아졌고 구토 횟수도 3회로 줄었어요 복통은 사라졌어요"
    )
    symptoms = symptoms_by_name(follow_up)
    assert set(symptoms) == {"두통", "구토", "복통"}
    assert symptoms["두통"]["status"] == "present"
    assert symptoms["두통"]["severity"] == "경미함"
    assert symptoms["구토"]["status"] == "present"
    assert symptoms["구토"]["frequency"] == "3회"
    assert symptoms["복통"]["status"] == "absent"


@pytest.mark.parametrize(
    "text",
    [
        "복통은 없어졌어요",
        "복통은 사라졌어요",
        "복통은 완전히 가라앉았어요",
        "복통은 다 나았어요",
        "배가 더 이상 안 아파요",
        "배가 아프지 않아요",
    ],
)
def test_abdominal_pain_resolution_expressions(text: str) -> None:
    symptom = extract(text)["symptoms"][0]
    assert symptom["name"] == "복통"
    assert symptom["status"] == "absent"


@pytest.mark.parametrize(
    "text",
    [
        "어지럽고 설사를 해요",
        "허리가 아프고 손이 저려요",
        "목이 붓고 피부에 발진이 생겼어요",
    ],
)
def test_category_7_unsupported_symptoms_are_not_forced_into_supported_names(text: str) -> None:
    result = extract(text)
    assert result["symptoms"] == []
    assert result["unrecognized_fragments"]
