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


# Scripts read aloud for the 2026-10-07 recordings (the ground truth for those recordings).
def test_score_said_in_the_next_sentence_with_a_correction() -> None:
    text = "엊그제부터 머리가 지끈지끈 아파요. 아픈 정도는 10점 만점에 6점, 아니 7점 정도예요. 어지럽거나 토한 적은 없어요."
    found = {item.name: (item.status, item.severity) for item in extract_intake(text).symptoms}
    assert found == {"두통": ("present", "7/10점"), "어지러움": ("absent", None), "구토": ("absent", None)}


def test_pain_that_eased_and_a_reaction_to_aspirin() -> None:
    result = extract_intake(
        "오늘 새벽부터 설사를 다섯 번 정도 했고 속이 메스꺼워요. 배는 처음엔 많이 아팠는데 지금은 조금 나아졌어요. "
        "예전에 아스피린을 먹고 두드러기가 난 적이 있어요."
    )
    found = {item.name: item for item in result.symptoms}
    assert (found["복통"].status, found["복통"].trend) == ("present", "improving")
    assert found["설사"].frequency == "5회"
    assert result.allergies == ["아스피린"] and "발진" not in found


def test_listed_conditions_and_normal_temperature() -> None:
    result = extract_intake("체온은 37.2도로 정상이었어요. 고혈압이랑 당뇨가 있어서 약을 먹고 있어요.")
    assert result.symptoms == []
    assert sorted(result.medical_history) == ["고혈압", "당뇨"]


def test_fever_then_and_now_and_diarrhoea_denied() -> None:
    result = extract_intake(
        "그제 밤에는 열이 39도까지 올라서 해열제를 먹었는데 지금은 37.8도 정도로 내렸어요. "
        "배가 아프거나 설사한 적은 없어요."
    )
    found = {item.name: (item.status, item.severity) for item in result.symptoms}
    assert found == {"발열": ("present", "39℃ → 37.8℃"), "복통": ("absent", None), "설사": ("absent", None)}


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("이부프로펜 200밀리그램을 하루 두 번 먹고 있어요", {"medications": ["이부프로펜 200mg 하루 2회"]}),
        ("콧가루 알레르기가 있어요", {"allergies": ["꽃가루"]}),  # turbo
        ("채채기가 자주 나와요", {"symptoms": ["재채기"]}),  # turbo
        ("목이 따끈거리고 기침이 나요", {"symptoms": ["인후통", "기침"]}),  # on-device
    ],
)
def test_recording_spellings(text: str, expected: dict) -> None:
    result = extract_intake(text)
    got = {"medications": result.medications, "allergies": result.allergies,
           "symptoms": [item.name for item in result.symptoms]}
    assert all(got[key] == value for key, value in expected.items())


def test_comma_between_name_and_allergy() -> None:
    # turbo with a comma-separated word list as its prompt wrote "페니실린, 알레르기" (2026-10-07).
    result = extract_intake("테레놀 500mg을 한 번에 먹었고, 페니실린, 알레르기가 있어요.")
    assert (result.medications, result.allergies) == (["테레놀 500mg"], ["페니실린"])


# Phrases from docs/RECORDING_BACKLOG.md section 2, checked as text before recording them (2026-10-09).
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("열은 났었는데 지금은 내렸어요", {"발열": ("absent", None, None)}),
        ("어제까지 설사했는데 오늘은 안 했어요", {"설사": ("absent", None, None)}),
        ("배가 아파요. 처음엔 7점이었는데 지금은 4점이에요", {"복통": ("present", "7/10점 → 4/10점", None)}),
        ("배가 아파요 처음엔 7점이었는데 지금은 4점이에요", {"복통": ("present", "7/10점 → 4/10점", None)}),
        ("배가 아파요. 참기 힘들 정도예요", {"복통": ("present", "심함", None)}),
        ("처음엔 하루 다섯 번 토했는데 오늘은 두 번 했어요", {"구토": ("present", None, "하루 5회 → 2회")}),
        ("하루에 서너 번 설사해요", {"설사": ("present", None, "하루 3~4회")}),
        ("한두 번 토했어요", {"구토": ("present", None, "1~2회")}),
        ("허리 아래쪽이 아파요", {"요통": ("present", None, None)}),
    ],
)
def test_backlog_phrases(text: str, expected: dict) -> None:
    assert facts(text) == expected


def test_onset_after_a_meal_and_until_yesterday() -> None:
    assert extract_intake("아까 점심 먹고 나서부터 배가 아파요").symptoms[0].onset == "아까 점심 먹고 나서부터"
    assert extract_intake("어제까지 설사했는데 오늘은 안 했어요").symptoms[0].onset is None


def test_corrected_dose_and_age_in_words() -> None:
    assert extract_intake("타이레놀 한 알, 아니 두 알 먹었어요").medications == ["타이레놀 두 알"]
    assert extract_intake("저는 서른다섯 살 여자예요").profile.age == 35
    assert extract_intake("스무 살이에요").profile.age == 20


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("2주 전부터 피곤하고 입맛이 없어요", {"피로": "present", "식욕부진": "present"}),  # 하고 ends a verb here
        ("일주일 전부터 귀에서 삐 소리가 나고 잘 안 들려요", {"이명": "present", "청력 저하": "present"}),
        ("열은 어제 39도까지 났었는데 지금은 내렸어요", {"발열": "absent"}),
        # turbo drops the full stop: only the headache is gone, not the cough before it.
        ("기침이 계속 나요 머리는 아팠는데 지금은 괜찮아졌어요", {"기침": "present", "두통": "absent"}),
    ],
)
def test_script_phrases_of_2026_10_09(text: str, expected: dict) -> None:
    assert {item.name: item.status for item in extract_intake(text).symptoms} == expected


# Recordings of 2026-10-09 (scripts 28~36), as the phone heard them.
def test_score_now_stays_with_its_symptom() -> None:
    # turbo; the "now" score went to 저림, the next symptom, before.
    text = "사흘 전부터 허리 아래쪽이 아파요 처음에는 7점이었는데 지금은 4점이에요 다리가 저려요"
    assert facts(text) == {"요통": ("present", "7/10점 → 4/10점", None), "저림": ("present", None, None)}
    assert "요통" in facts("사흘 전부터 허리 아래쪽에 아파요")  # on-device


def test_corrected_dose_across_a_question_mark_and_allergy_with_에() -> None:
    turbo = extract_intake("타이레놀 한 알? 아니, 두 알 먹었어요. 페니실린 알레르기가 있어요.")
    device = extract_intake("타이레놀 한알 아니 두알 먹었어요 페니실린에 알레르기가 있어요")
    assert (turbo.medications, device.medications) == (["타이레놀 두 알"], ["타이레놀 두 알"])
    assert device.allergies == ["페니실린"]


def test_meal_onset_without_부터_and_a_count_is_not_an_onset() -> None:
    symptoms = {item.name: item.onset for item in
                extract_intake("아까 점심 먹고 나서 명치가 아파요 참기 힘들 정도예요 하루 서너 번 토했어요").symptoms}
    assert symptoms == {"복통": "아까 점심 먹고 나서", "구토": None}


def test_on_device_spelling_of_메스꺼워요() -> None:
    assert "메스꺼움" in facts("속이 매스꺼워요")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Said by the user without a script: patients do not always speak politely to a recorder.
        ("어제부터 머리가 많이 아픔 그리고 오한도 좀 있음", {"두통": ("present", "심함", None), "오한": ("present", None, None)}),
        ("열 없음. 기침함. 코가 막힘", {"발열": ("absent", None, None), "기침": ("present", None, None),
                                     "코막힘": ("present", None, None)}),
        ("배가 아팠는데 지금은 괜찮음", {"복통": ("absent", None, None)}),
        ("콧막힘 있음", {"코막힘": ("present", None, None)}),  # the name itself ends in 힘
    ],
)
def test_plain_음슴체_endings(text: str, expected: dict) -> None:
    assert facts(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("소변에 피가 섞여 나와", {"혈뇨": "present"}),  # 소변, not 변
        ("눈이 아프고 흐릿하게 보여요", {"눈 통증": "present", "시야 이상": "present"}),
        ("입이 자주 마름", {"입마름": "present"}),
    ],
)
def test_phrases_checked_before_the_third_recordings(text: str, expected: dict) -> None:
    assert {item.name: item.status for item in extract_intake(text).symptoms} == expected


def test_not_pregnant_said_with_중() -> None:
    assert extract_intake("임신 중은 아니에요").profile.pregnancy == "no"


# Third recordings of 2026-10-09 (scripts 37~47), as the phone heard them.
@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("배가 빵빵하고 속이 매스꺼워 가래는 없어", {"복부 팽만": "present", "메스꺼움": "present", "가래": "absent"}),
        ("눈이 아프고 허릿하게 보여요", {"눈 통증": "present", "시야 이상": "present"}),
        ("목에 뭐가 걸린 거 같고 목이 아파요", {"목 이물감": "present", "인후통": "present"}),
    ],
)
def test_third_recordings(text: str, expected: dict) -> None:
    assert {item.name: item.status for item in extract_intake(text).symptoms} == expected


def test_contrast_medium_allergy_and_metformin_heard_wrong() -> None:
    result = extract_intake("갑상선 약을 먹고 있고 조영제 알레르기가 있어요")
    assert (result.medications, result.allergies) == (["갑상선약"], ["조영제"])
    for heard in ("매트프로민을 하루 두 번 먹고 있어요", "매트 프로면 하루 두 번 먹고 있어요"):
        assert extract_intake(heard).medications == ["메트포르민 하루 2회"]
