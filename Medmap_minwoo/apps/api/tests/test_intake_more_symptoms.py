import pytest

from app.services.intake_extractor import extract_intake


def found(text: str) -> list[tuple[str, str, str | None]]:
    return [(item.name, item.status, item.body_site) for item in extract_intake(text).symptoms]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("혀가 아파요", ("입안 통증", "present", "입안")),
        ("입안이 헐었어요", ("입안 통증", "present", "입안")),
        ("입병이 났어요", ("입안 통증", "present", "입안")),
        ("혀가 안 아파요", ("입안 통증", "absent", "입안")),
        ("재채기가 나요", ("재채기", "present", None)),
        ("재채기는 없어요", ("재채기", "absent", None)),
        ("숨쉴 때 쌕쌕 소리가 나요", ("쌕쌕거림", "present", None)),
        ("소변이 안 나와요", ("배뇨 곤란", "present", None)),
        ("소변 보기가 힘들어요", ("배뇨 곤란", "present", None)),
        ("눈이 충혈됐어요", ("눈 충혈", "present", "눈")),
        ("눈이 빨개졌어요", ("눈 충혈", "present", "눈")),
        ("생리통이 심해요", ("생리통", "present", "아랫배")),
        ("발가락이 아파요", ("관절 통증", "present", "발가락")),
        ("턱이 아파요", ("관절 통증", "present", "턱")),
    ],
)
def test_recognizes_added_symptoms(text: str, expected: tuple[str, str, str | None]) -> None:
    assert found(text) == [expected]


@pytest.mark.parametrize(
    ("text", "name"),
    [
        # "소변" contains "변"; it used to be read as constipation.
        ("소변이 안 나와요", "변비"),
        # Red eyes are not eye pain.
        ("눈이 충혈됐어요", "눈 통증"),
    ],
)
def test_does_not_misread_as(text: str, name: str) -> None:
    assert name not in [item[0] for item in found(text)]


def test_stool_still_reads_as_constipation() -> None:
    assert found("대변이 안 나와요") == [("변비", "present", None)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("입이 말라요", ("입마름", "present", None)),
        ("목이 자주 말라요", ("입마름", "present", None)),
        ("귀가 잘 안 들려요", ("청력 저하", "present", "귀")),
        ("손이 저릿저릿해요", ("저림", "present", "손")),
    ],
)
def test_recognizes_dry_mouth_hearing_and_tingling(text: str, expected: tuple[str, str, str | None]) -> None:
    assert found(text) == [expected]


@pytest.mark.parametrize(
    ("text", "names", "onset"),
    [
        ("가슴이답답하고아파요", ["가슴 답답함", "흉통"], None),
        ("어제부터가슴이답답하고아파요", ["가슴 답답함", "흉통"], "어제부터"),
        ("허리가쑤시고다리가저려요", ["요통", "저림"], None),
        ("3일째배가아파요", ["복통"], "3일째"),
    ],
)
def test_reads_sentences_without_spaces(text: str, names: list[str], onset: str | None) -> None:
    symptoms = extract_intake(text).symptoms
    assert [item.name for item in symptoms] == names
    assert {item.onset for item in symptoms} == {onset}


def test_does_not_split_finger_or_toe_words() -> None:
    assert found("발가락이아파요") == [("관절 통증", "present", "발가락")]


@pytest.mark.parametrize(
    "text",
    ["배가 불편해요", "겨드랑이에 혹이 생겼어요", "입술이 부르텄어요"],
)
def test_asks_to_confirm_unlisted_complaints(text: str) -> None:
    result = extract_intake(text)
    assert result.symptoms == []
    assert result.unrecognized_fragments == [text]


def test_hoksi_is_not_a_lump() -> None:
    assert extract_intake("혹시 몰라서 말씀드려요 머리가 아파요").unrecognized_fragments == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("배가 빵빵해요", ("복부 팽만", "present", "복부")),
        ("가스가 차요", ("복부 팽만", "present", "복부")),
        ("트림이 자주 나와요", ("소화불량", "present", "복부")),
        ("목에 뭐가 걸린 것 같아요", ("목 이물감", "present", "목")),
        ("눈곱이 껴요", ("눈 분비물", "present", "눈")),
        ("눈물이 계속 나요", ("눈 분비물", "present", "눈")),
        ("뒷목이 당겨요", ("목 결림", "present", "뒷목")),
        ("목이 뻐근해요", ("목 결림", "present", "뒷목")),
        ("손발이 차요", ("손발 차가움", "present", None)),
        ("우울해요", ("우울감", "present", None)),
        ("불안해요", ("불안감", "present", None)),
        ("입술이 부었어요", ("부종", "present", "입술")),
        ("눈이 부었어요", ("부종", "present", "눈")),
        ("침 삼킬 때 아파요", ("인후통", "present", "목")),
        ("몸에 힘이 없어요", ("피로", "present", None)),
    ],
)
def test_recognizes_common_everyday_complaints(text: str, expected: tuple[str, str, str | None]) -> None:
    assert found(text) == [expected]


@pytest.mark.parametrize("text", ["불안정해요", "밥을 먹어서 배가 불러요"])
def test_does_not_read_ordinary_words_as_symptoms(text: str) -> None:
    assert found(text) == []


@pytest.mark.parametrize(
    ("text", "history"),
    [
        ("혈압이 높아요", ["혈압 높음"]),
        ("혈당이 높다고 했어요", ["혈당 높음"]),
        ("콜레스테롤이 높아요", ["콜레스테롤 높음"]),
        ("작년에 폐렴으로 입원했어요", ["폐렴(입원)"]),
        ("심장 스텐트 시술 받았어요", ["스텐트 시술"]),
        ("간이 안 좋다고 했어요", ["간 질환"]),
        ("혈압이 높지 않아요", []),
        ("병원으로 입원했어요", []),
    ],
)
def test_reads_history_said_without_a_disease_name(text: str, history: list[str]) -> None:
    result = extract_intake(text)
    assert result.medical_history == history
    assert result.unrecognized_fragments == []


def test_history_of_depression_is_not_a_current_symptom() -> None:
    result = extract_intake("우울증 진단 받았어요")
    assert result.medical_history == ["우울증"]
    assert result.symptoms == []


def test_spaced_cholesterol_medicine_is_a_medication() -> None:
    assert extract_intake("고지혈증 약 먹어요").medications == ["고지혈증약"]
