import pytest
from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def extract(text: str) -> dict:
    response = client.post("/v1/intake/extract", json={"transcript": text})
    assert response.status_code == 200
    return response.json()


def names(result: dict) -> list[tuple[str, str]]:
    return [(item["name"], item["status"]) for item in result["symptoms"]]


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("몸이 자꾸 가려워요", "가려움"),
        ("피부가 간지러워요", "가려움"),
        ("눈이 침침해요", "시야 이상"),
        ("눈앞이 흐릿해요", "시야 이상"),
        ("물건이 겹쳐 보여요", "시야 이상"),
        ("손이 덜덜 떨려요", "떨림"),
        ("귀에서 삐 소리가 나요", "이명"),
        ("코피가 났어요", "코피"),
        ("가래에 피가 섞여 나와요", "객혈"),
        ("변에 피가 묻어 나와요", "혈변"),
        ("짜장 같은 변을 봤어요", "혈변"),
        ("소변이 빨갛게 나와요", "혈뇨"),
        ("소변 볼 때 따끔해요", "배뇨통"),
        ("화장실을 너무 자주 가요", "빈뇨"),
        ("어제 갑자기 쓰러졌어요", "기절"),
        ("정신을 잃었어요", "기절"),
        ("한쪽 팔에 힘이 빠져요", "마비"),
        ("말이 자꾸 어눌해요", "말 어눌함"),
        ("목이 쉬었어요", "쉰 목소리"),
        ("한 달 사이에 살이 많이 빠졌어요", "체중 감소"),
        ("몸이 뻣뻣해지면서 발작을 했어요", "경련"),
    ],
)
def test_recognizes_red_flag_symptoms(text: str, name: str) -> None:
    result = extract(text)
    assert (name, "present") in names(result), text
    assert result["unrecognized_fragments"] == []


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("피를 토했어요", [("토혈", "present"), ("구토", "present")]),
        ("기침할 때 피가 나와요", [("기침", "present"), ("객혈", "present")]),
    ],
)
def test_bleeding_with_its_base_symptom(text: str, expected: list) -> None:
    assert names(extract(text)) == expected


@pytest.mark.parametrize(
    ("text", "name"),
    [
        ("가려움은 없어요", "가려움"),
        ("코피는 멈췄어요", "코피"),
        ("쓰러진 적은 없어요", "기절"),
        ("마비는 없어요", "마비"),
        ("말은 괜찮아요", "말 어눌함"),
    ],
)
def test_recognizes_red_flag_absence(text: str, name: str) -> None:
    assert names(extract(text)) == [(name, "absent")]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("위경련이 왔어요", [("복통", "present")]),
        ("몸이 으슬으슬 떨려요", [("오한", "present")]),
        ("어지러워서 쓰러질 것 같아요", [("어지러움", "present")]),
        ("목이 아프고 목소리가 쉬었어요", [("인후통", "present"), ("쉰 목소리", "present")]),
    ],
)
def test_red_flags_do_not_steal_other_symptoms(text: str, expected: list) -> None:
    assert names(extract(text)) == expected


@pytest.mark.parametrize(
    ("text", "history"),
    [
        ("위염으로 진단받았어요", ["위염"]),
        ("섬유근육통이라고 진단받았어요", ["섬유근육통"]),
        ("작년에 당뇨병 진단을 받았어요", ["당뇨병"]),
        ("녹내장이 있어요", ["녹내장"]),
        ("작년에 대상포진을 앓았어요", ["대상포진"]),
    ],
)
def test_medical_history_from_diagnosis_phrases(text: str, history: list[str]) -> None:
    result = extract(text)
    assert result["medical_history"] == history
    assert result["unrecognized_fragments"] == []


def test_diagnosis_without_condition_name_is_flagged() -> None:
    result = extract("병원에서 진단을 받았어요")
    assert result["medical_history"] == []
    assert result["unrecognized_fragments"] == ["병원에서 진단을 받았어요"]
