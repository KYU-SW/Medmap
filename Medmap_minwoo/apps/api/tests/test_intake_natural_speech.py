"""Longer, natural recordings from the phone test of 2026-10-07 (turbo transcripts, numbers as the app shows them)."""
import pytest

from app.services.intake_extractor import extract_intake

COLD = (
    "사흘 전부터 목이 따끔거리고 기침이 나기 시작했어요 처음에는 기침하는 정도 있는데 어젯밤에는 잠에서 두번 깰 정도만큼 "
    "심해졌어요 오늘 아침에는 머리도 지끈 지끈 거리고 체온을 재보니까 38.2도였어요 배가 아프거나 토한 적은 없고 "
    "숨 쉬는 것도 괜찮아요 아침을 먹고 타이레놀 한 알 먹었더니 머리는 조금 나아졌지만 기침은 그대로예요"
)
STOMACH = (
    "어제 저녁을 먹은 뒤부터 배가 아프고 속이 메스꺼웠어요 밤에는 두 번 토했고 오늘 아침에는 한 번 더 토했어요 "
    "설사는 어젯밤부터 지금까지 네 번 정도 했어요 배가 아픈 정도는 처음에는 10점 만점에 7점이었는데 지금은 4점 정도로 "
    "줄었어요 머리도 아팠지만 지금은 괜찮아졌어요 열이나 기침은 없어요 물을 조금씩 조금씩 마시고 있고 약은 아직 먹지 "
    "않았어요 예전에 페니슐린을 먹고 두드러기가 생긴 적이 있어요"
)


def facts(text: str) -> dict[str, tuple]:
    return {item.name: (item.status, item.severity, item.frequency) for item in extract_intake(text).symptoms}


def test_cold_recording() -> None:
    result = extract_intake(COLD)
    found = facts(COLD)
    assert found["발열"] == ("present", "38.2℃", None)  # "체온을 재보니까 38.2도였어요"
    assert found["복통"][0] == "absent"  # "배가 아프거나 ... 없고"
    assert found["두통"][1] is None  # the cough's "심해졌어요" is in another sentence
    assert result.medications == ["타이레놀 한 알"]
    assert found["구토"][0] == "absent" and found["호흡곤란"][0] == "absent"  # "토한 적은 없고", "숨 쉬는 것도 괜찮아요"
    onsets = {item.name: item.onset for item in result.symptoms}
    assert onsets["기침"] == onsets["인후통"] == "3일 전부터"  # "사흘 전부터 목이 따끔거리고 기침이 나기 시작"


def test_stomach_recording() -> None:
    result = extract_intake(STOMACH)
    found = facts(STOMACH)
    # Said at the second mention, "배가 아픈 정도는 처음에는 ... 7점이었는데 지금은 4점".
    assert found["복통"][:2] == ("present", "7/10점 → 4/10점")
    assert extract_intake(STOMACH).symptoms[1].onset == "어제 저녁"  # "배가 아프고 속이 메스꺼웠어요" share it
    assert found["설사"][2] == "4회"
    assert found["두통"][0] == "absent"  # "아팠지만 지금은 괜찮아졌어요"
    assert found["발열"][0] == "absent" and found["기침"][0] == "absent"  # "열이나 기침은 없어요"
    assert "발진" not in found  # the hives were a past reaction to penicillin
    assert (result.medications, result.allergies) == ([], ["페니실린"])


@pytest.mark.parametrize(
    ("text", "status"),
    [
        ("열과 기침은 없어요", {"발열": "absent", "기침": "absent"}),
        ("열이 나고 기침은 없어요", {"발열": "present", "기침": "absent"}),
        ("머리가 아프고 기침은 없어요", {"두통": "present", "기침": "absent"}),
        ("두통이나 어지러움이 있어요", {"두통": "present", "어지러움": "present"}),
    ],
)
def test_only_symptoms_listed_before_the_negation_are_absent(text: str, status: dict[str, str]) -> None:
    assert {item.name: item.status for item in extract_intake(text).symptoms} == status


def test_taking_a_medicine_without_a_reaction_is_not_an_allergy() -> None:
    result = extract_intake("타이레놀을 먹고 두통이 나아졌어요")
    assert (result.medications, result.allergies) == (["타이레놀"], [])


def test_breathing_that_got_better_is_still_a_finding() -> None:
    assert [(item.name, item.status) for item in extract_intake("숨 쉬기가 괜찮아졌어요").symptoms] == [("호흡곤란", "present")]


RHINITIS_TURBO = (
    "이틀 전부터 콧물이 나고 재채기가 자주 나왔어요 어제부터는 코도 박혀서 밤에 잠을 잘 못 잤어요 기침은 없고 "
    "목이 조금 간질거리는 정도예요 오늘 아침에 알레르기 약 하나를 먹었는데 콧물은 줄었지만 코막힘은 아직 남아있어요 "
    "머리가 아픈 정도는 10점 만점 6점 아니 4점 정도예요 구토한 적은 없어요."
)


def test_rhinitis_recording() -> None:
    result = extract_intake(RHINITIS_TURBO)
    found = {item.name: item for item in result.symptoms}
    assert found["재채기"].onset == found["콧물"].onset == "2일 전부터"
    assert found["코막힘"].onset == "어제부터"  # "코도 박혀서": turbo's "막혀서"
    assert (found["콧물"].trend, found["코막힘"].trend) == ("improving", None)  # "콧물은 줄었지만 코막힘은 아직"
    assert found["두통"].severity == "4/10점"  # "6점 아니 4점"
    assert result.medications == ["알레르기약"]


def test_onset_is_not_shared_across_a_finished_sentence() -> None:
    onsets = {item.name: item.onset for item in extract_intake("어제부터 콧물이 나요 그리고 기침이 나요").symptoms}
    assert onsets == {"콧물": "어제부터", "기침": None}
