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
