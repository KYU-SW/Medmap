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
            "frequency": None,
            "trend": None,
            "source_text": "머리가 아프",
        },
        {
            "name": "발열",
            "status": "absent",
            "body_site": None,
            "onset": None,
            "severity": None,
            "frequency": None,
            "trend": None,
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


def test_extracts_symptom_frequency_expressions() -> None:
    cases = {
        "오늘 구토를 3번 했어요": "3회",
        "두 차례 토했어요": "2회",
        "하루에 4번 구토했어요": "하루 4회",
    }
    for text, expected in cases.items():
        result = extract(text)
        assert result["symptoms"][0]["frequency"] == expected, text


def test_frequency_is_not_added_to_symptoms_that_do_not_use_counts() -> None:
    for text in (
        "머리가 아팠어요 세 번 반복됐어요",
        "배가 아팠어요 두 번 반복됐어요",
        "기침을 했어요 다섯 번 반복됐어요",
    ):
        result = extract(text)
        assert result["symptoms"][0]["frequency"] is None, text


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


def test_common_korean_day_expressions() -> None:
    cases = {
        "오늘부터": "오늘부터",
        "어제": "어제",
        "하루 전": "1일 전",
        "하루 전부터": "1일 전부터",
        "이틀": "2일",
        "이틀 전": "2일 전",
        "이틀 전부터": "2일 전부터",
        "2일 전": "2일 전",
        "2일 전부터": "2일 전부터",
        "삼일 전부터": "3일 전부터",
        "사흘째": "3일째",
        "일주일 전부터": "1주 전부터",
    }
    for spoken, expected in cases.items():
        result = extract(f"{spoken} 머리가 아파요")
        assert result["symptoms"][0]["onset"] == expected, spoken


def test_onset_between_body_site_and_pain_is_preserved() -> None:
    result = extract(
        "어제부터 머리가 너무 아프고 배는 이틀 전부터 아팠어요 "
        "그리고 사흘째 되는 날에 구토를 하기 시작했어요"
    )
    assert [item["name"] for item in result["symptoms"]] == [
        "두통", "복통", "구토"
    ]
    assert result["symptoms"][0]["severity"] == "심함"
    assert result["symptoms"][1]["onset"] == "2일 전부터"
    assert result["symptoms"][2]["onset"] == "3일째"


def test_common_variants_for_every_supported_symptom() -> None:
    variants = {
        "두통": ["머리가 아파요", "머리가 아팠어요", "두통이 있어요", "머리가 욱신거려요"],
        "발열": ["열이 나요", "열이 났어요", "발열이 있어요", "고열이 있어요"],
        "기침": ["기침이 나요", "기침을 해요", "기침이 심했어요", "계속 기침해요"],
        "호흡곤란": ["숨이 차요", "숨쉬기가 힘들어요", "숨을 쉬기가 어려워요", "호흡곤란이 있어요"],
        "가슴 답답함": ["가슴이 답답해요", "가슴이 조여요", "가슴이 눌리는 느낌이에요", "흉부 압박이 있어요"],
        "복통": ["배가 아파요", "배는 아팠어요", "복부가 많이 아파요", "복통이 있어요"],
        "구토": ["구토했어요", "토를 했어요", "토해요", "구토가 있어요"],
    }
    for expected, phrases in variants.items():
        for phrase in phrases:
            result = extract(phrase)
            assert result["symptoms"], phrase
            assert result["symptoms"][0]["name"] == expected, phrase


def test_common_negative_variants() -> None:
    cases = {
        "머리는 안 아파요": "두통",
        "열은 없어요": "발열",
        "기침은 안 해요": "기침",
        "숨은 안 차요": "호흡곤란",
        "가슴이 답답하지 않아요": "가슴 답답함",
        "배는 아프지 않아요": "복통",
        "구토는 없어요": "구토",
    }
    for phrase, expected in cases.items():
        result = extract(phrase)
        assert result["symptoms"][0]["name"] == expected, phrase
        assert result["symptoms"][0]["status"] == "absent", phrase


def test_warns_when_medical_expression_is_not_supported() -> None:
    result = extract("어제부터 허리가 아프고 손이 저려요")
    assert [item["name"] for item in result["symptoms"]] == ["요통"]
    assert result["unrecognized_fragments"] == ["손이 저려요"]


def test_repeated_intensity_words_do_not_hide_symptoms() -> None:
    phrases = [
        "머리가 너무 너무 아파요",
        "머리가 너무너무 아파요",
        "머리가 많이 많이 아파요",
        "머리가 아주 많이 아파요",
    ]
    for phrase in phrases:
        result = extract(phrase)
        assert result["symptoms"][0]["name"] == "두통", phrase
        assert result["symptoms"][0]["severity"] == "심함", phrase


def test_full_repeated_intensity_regression_sentence() -> None:
    result = extract(
        "머리가 너무 너무 아프고 배도 이틀 전부터 아팠어요 "
        "그리고 사흘 전에는 구토도 했어요"
    )
    assert [item["name"] for item in result["symptoms"]] == [
        "두통", "복통", "구토"
    ]
    assert result["symptoms"][0]["onset"] is None
    assert result["symptoms"][1]["onset"] == "2일 전부터"
    assert result["symptoms"][2]["onset"] == "3일 전"
