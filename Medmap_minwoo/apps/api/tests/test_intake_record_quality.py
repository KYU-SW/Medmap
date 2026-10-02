import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)
# 2026-10-02 is a Friday.
REFERENCE_DATE = "2026-10-02"


def extract(text: str, reference_date: str | None = REFERENCE_DATE) -> dict:
    body = {"transcript": text}
    if reference_date:
        body["reference_date"] = reference_date
    response = client.post("/v1/intake/extract", json=body)
    assert response.status_code == 200
    return response.json()


def first(result: dict) -> dict:
    return result["symptoms"][0]


@pytest.mark.parametrize(
    ("text", "onset", "onset_date"),
    [
        ("어제부터 머리가 아파요", "어제부터", "2026-10-01"),
        ("오늘 아침부터 열이 나요", "오늘 아침부터", "2026-10-02"),
        ("그저께부터 기침해요", "그저께부터", "2026-09-30"),
        ("이틀 전부터 목이 아파요", "2일 전부터", "2026-09-30"),
        ("3일째 설사를 해요", "3일째", "2026-09-30"),
        ("10월 1일부터 열이 나요", "10월 1일부터", "2026-10-01"),
        ("9월 30일쯤부터 기침해요", "9월 30일쯤부터", "2026-09-30"),
        ("12월 25일부터 두통이 있어요", "12월 25일부터", "2025-12-25"),
        ("월요일부터 배가 아파요", "월요일부터", "2026-09-28"),
        ("지난주 월요일부터 기침해요", "지난주 월요일부터", "2026-09-21"),
        ("2주 전부터 기침해요", "2주 전부터", None),
        ("엊그제부터 콧물이 나요", "엊그제부터", None),
    ],
)
def test_onset_becomes_a_date_only_when_it_names_one_day(text: str, onset: str, onset_date: str | None) -> None:
    symptom = first(extract(text))
    assert symptom["onset"] == onset
    assert symptom["onset_date"] == onset_date


def test_onset_date_needs_the_patients_reference_date() -> None:
    assert first(extract("어제부터 머리가 아파요", reference_date=None))["onset_date"] is None


def test_borrowed_subject_also_borrows_the_onset() -> None:
    symptoms = {item["name"]: item for item in extract("어제부터 가슴이 답답하고 아파요")["symptoms"]}
    assert symptoms["흉통"]["onset"] == "어제부터"
    assert symptoms["흉통"]["onset_date"] == "2026-10-01"


@pytest.mark.parametrize(
    ("text", "severity"),
    [
        ("머리가 아픈데 참을 만해요", "경미함"),
        ("배가 참을 만하게 아파요", "경미함"),
        ("허리가 심하진 않은데 아파요", "경미함"),
        ("목이 살짝 아파요", "경미함"),
        ("기침이 보통 정도예요", "중간"),
        ("배가 너무 아파서 못 참겠어요", "심함"),
        ("머리가 아파서 잠을 못 잘 정도예요", "심함"),
        ("배가 죽을 것 같이 아파요", "심함"),
        ("배가 데굴데굴 구를 정도로 아파요", "심함"),
    ],
)
def test_everyday_severity_words(text: str, severity: str) -> None:
    result = extract(text)
    assert first(result)["severity"] == severity, text
    assert result["unrecognized_fragments"] == []


@pytest.mark.parametrize(
    ("text", "name", "site"),
    [
        ("오른쪽 아랫배가 아파요", "복통", "오른쪽 아랫배"),
        ("윗배가 쓰려요", "속쓰림", "윗배"),
        ("명치가 아파요", "복통", "명치"),
        ("오른쪽 옆구리가 아파요", "복통", "오른쪽 옆구리"),
        ("왼쪽 가슴이 찌르듯이 아파요", "흉통", "왼쪽 가슴"),
        ("뒷머리가 지끈거려요", "두통", "뒷머리"),
        ("우측 귀가 아파요", "귀 통증", "오른쪽 귀"),
        ("왼쪽 무릎이 아파요", "관절 통증", "왼쪽 무릎"),
        ("어깨가 쑤셔요", "관절 통증", "어깨"),
        ("왼쪽 다리가 퉁퉁 부었어요", "부종", "왼쪽 다리"),
        ("오른손이 떨려요", "떨림", "오른쪽 손"),
        ("배가 아파요", "복통", "복부"),
        ("오른쪽으로 누우면 배가 아파요", "복통", "복부"),
    ],
)
def test_side_and_sub_site(text: str, name: str, site: str) -> None:
    symptom = first(extract(text))
    assert (symptom["name"], symptom["body_site"]) == (name, site)


def test_body_part_for_numbness_comes_from_its_subject() -> None:
    symptoms = {item["name"]: item for item in extract("가슴이 답답하고 왼쪽 팔이 저려요")["symptoms"]}
    assert symptoms["저림"]["body_site"] == "왼쪽 팔"
    assert symptoms["가슴 답답함"]["body_site"] == "가슴"


@pytest.mark.parametrize(
    ("text", "medications"),
    [
        ("타이레놀 500mg을 하루 두 번 먹었어요", ["타이레놀 500mg 하루 2회"]),
        ("타이레놀 두 알 먹었어요", ["타이레놀 두 알"]),
        ("혈압약 먹고 있고 아스피린도 하루 한 알 먹어요", ["혈압약", "아스피린 하루 한 알"]),
        ("감기약을 아침 저녁으로 먹어요", ["감기약 아침 저녁"]),
        ("아목시실린 먹고 있어요", ["아목시실린"]),
        ("병원에서 아지트로마이신을 처방받았어요", ["아지트로마이신"]),
        ("벤토린 흡입기를 필요할 때 써요", ["벤토린 필요할 때"]),
        ("후시딘을 발랐어요", ["후시딘"]),
        ("구토는 한 7번 정도 한 것 같아요 약은 타이레놀 먹었어요", ["타이레놀"]),
    ],
)
def test_medication_names_dose_and_timing(text: str, medications: list[str]) -> None:
    result = extract(text)
    assert result["medications"] == medications
    assert result["unrecognized_fragments"] == []


def test_allergy_drug_is_not_a_medication_taken() -> None:
    result = extract("혈압약을 복용하고 페니실린 알레르기가 있어요")
    assert result["medications"] == ["혈압약"]
    assert result["allergies"] == ["페니실린"]
