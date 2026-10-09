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
        ("숨 쉴 때 쎅쎅 소리가 나요", ("쌕쌕거림", "present", None)),
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


@pytest.mark.parametrize(
    ("text", "onset", "onset_date"),
    [
        ("2일 전 저녁부터 머리가 아파요", "2일 전 저녁부터", "2026-10-03"),
        ("이틀 전 저녁부터 머리가 아파요", "2일 전 저녁부터", "2026-10-03"),
        # The phone STT model writes numbers in words.
        ("이 일 전 저녁부터 머리가 아파요", "2일 전 저녁부터", "2026-10-03"),
    ],
)
def test_keeps_day_count_with_time_of_day(text: str, onset: str, onset_date: str) -> None:
    from datetime import date

    symptom = extract_intake(text, date(2026, 10, 5)).symptoms[0]
    assert (symptom.onset, symptom.onset_date) == (onset, onset_date)


@pytest.mark.parametrize(
    ("text", "severity"),
    [("열이 삼십팔 도까지 났어요", "38℃"), ("열이 삼십팔 점 오 도예요", "38.5℃"), ("열이 사십 도예요", "40℃")],
)
def test_reads_body_temperature_said_in_words(text: str, severity: str) -> None:
    assert extract_intake(text).symptoms[0].severity == severity


def test_misheard_kukkuk_still_reads_as_pain() -> None:
    # Both STT engines once wrote "쿡쿡" as "구구".
    assert [item.name for item in extract_intake("오른쪽 아랫배가 구구 쑤셔요").symptoms] == ["복통"]


def test_cold_weather_is_not_a_fever() -> None:
    assert extract_intake("오늘 영하 삼 도라 추워요").symptoms == []


@pytest.mark.parametrize(
    ("text", "severity"),
    [("오늘 아침에는 체온이 38.5도까지 올랐고 콧물도 생겼어요", "38.5℃"), ("체온이 38도예요", "38℃"), ("체온이 38.5°까지 올랐어요", "38.5℃")],
)
def test_reads_fever_from_body_temperature_alone(text: str, severity: str) -> None:
    fever = next(item for item in extract_intake(text).symptoms if item.name == "발열")
    assert (fever.status, fever.severity) == ("present", severity)


@pytest.mark.parametrize("text", ["체온은 36.5도로 정상이에요", "체온이 37.2도예요"])
def test_normal_temperature_is_not_turned_into_a_finding(text: str) -> None:
    assert extract_intake(text).symptoms == []


@pytest.mark.parametrize(
    ("text", "medications"),
    [
        # STT misheard "타이레놀"; the name is kept as said for the patient to correct, not swapped for a lookalike.
        ("테렌을 500mg을 한 번에 먹었고", ["테렌 500mg"]),
        ("타이륜을 두정 복용했어요", ["타이륜 두 정"]),
        ("어제 두 알 먹었어요", ["이름 모르는 약 두 알"]),  # no name anywhere: kept for the patient to name
        ("너무 아파서 두 알 먹었어요", ["이름 모르는 약 두 알"]),
        ("물을 500ml 마셨어요", []),
    ],
)
def test_keeps_an_unknown_name_taken_by_the_pill(text: str, medications: list[str]) -> None:
    assert extract_intake(text).medications == medications


def test_next_sentence_onset_does_not_attach_without_period():
    result = extract_intake("어제 저녁부터 머리가 아프고 기침이 심해졌어요 오늘 아침에는 체온이 38.5도까지 올랐어요")
    onsets = {s.name: s.onset for s in result.symptoms}
    assert onsets["기침"] != "오늘 아침"
    assert onsets["발열"] == "오늘 아침"


@pytest.mark.parametrize(
    ("text", "name"),
    [
        # Spellings the phone engines gave in the 2026-10-06 hard-audio tests.
        ("어제부터 폭통이 너무 심해요", "복통"),
        ("콧물과 콧막힘 때 생겼어요", "코막힘"),
        ("코 막힘이 있어요", "코막힘"),
        ("콧물과 코마킹도 생겼어요", "코막힘"),
        ("체온이 38.5度까지 올랐어요", "발열"),
    ],
)
def test_reads_stt_spellings_of_symptoms(text: str, name: str) -> None:
    assert name in [item.name for item in extract_intake(text).symptoms if item.status == "present"]


def test_comma_inside_onset_keeps_the_day() -> None:
    assert extract_intake("2일 전, 저녁부터 머리가 너무 아파요.").symptoms[0].onset == "2일 전 저녁부터"


@pytest.mark.parametrize(
    ("text", "medications"),
    [
        ("타이륜을 먹었어요", ["타이륜"]),
        ("타이레노 먹었어요", ["타이레놀"]),
        ("타이레놀 500mg을 하루 두 번 먹었어요", ["타이레놀 500mg 하루 2회"]),
        ("타이밍 맞춰 약을 먹었어요", []),
    ],
)
def test_keeps_tylenol_soundalikes_without_a_dose(text: str, medications: list[str]) -> None:
    assert extract_intake(text).medications == medications


@pytest.mark.parametrize(
    ("text", "medications", "allergies"),
    [
        # Phone recordings, 2026-10-07: one syllable off a known name reads as that name.
        ("타이레놀 500mg을 먹었고 페니슐린 알레르기가 있어요", ["타이레놀 500mg"], ["페니실린"]),
        ("헤니실린 알레르기가 있어요", [], ["페니실린"]),
        ("타이레농을 2정 복용했어요", ["타이레놀 2정"], []),
        # Short or further-off names stay as heard.
        ("타이레는 500mg을 한번에 먹었고", ["타이레 500mg"], []),
        ("타이륜을 먹었어요", ["타이륜"], []),
    ],
)
def test_reads_names_one_syllable_off_as_the_known_name(text: str, medications: list[str], allergies: list[str]) -> None:
    result = extract_intake(text)
    assert (result.medications, result.allergies) == (medications, allergies)
