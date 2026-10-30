"""STEP29.3 G3·G10 의미 구별 회귀 사례(지시문 3절 예시 + STEP29.2 HOLDOUT 비증상 오연결 — 모두 노출 회귀 자료). 평가 전 1회 작성·SHA 고정.
[작성 중 정정(정책 구현 전, 2026-10-14)] '기침하면 피가 같이 나와요' 의 허용 목록에 cough 누락 → 추가(기침은 실제로 언급된 증상 — 이전 정책 출력 확인 중 발견).
각 사례: allowed = 자동 연결(EXISTING)로 허용되는 concept 집합(빈 집합이면 EXISTING 금지), forbidden = 어느 mention 이든 EXISTING 이면 위반, must_any = 하나라도 있어야 하는 concept(선택)."""
import s293_common as S

V, H, N = "vomiting", "hematemesis", "nausea"
CASES = [
    ("토했어요", [V], [H, N]), ("토했", [V], [H, N]), ("오바이트했어요", [V], [H, N]), ("피를 토했어요", [H], [N, "hemoptysis"]),
    ("토할 것 같아요", [N], [V, H]), ("속이 메스꺼워요", [N], [V, "heartburn"]),
    ("목이 아파요", ["sore_throat", "pain"], []), ("목이 아프고", ["sore_throat", "pain"], []), ("목이 따끔거려요", ["sore_throat"], []),
    ("목 뒤가 아파요", ["pain"], ["sore_throat"]), ("목을 움직이면 아파요", ["pain"], ["sore_throat"]), ("침 삼킬 때 목이 아파요", ["sore_throat", "pain"], []),
    ("속이 울렁거려요", [N], ["heartburn", V]), ("속이 화끈거려요", ["heartburn", "pain"], [N]), ("속이 쓰려요", ["heartburn", "pain"], [N]),
    ("손이 떨려요", [], ["chills"]), ("몸이 덜덜 떨려요", ["chills"], []), ("추워서 몸이 떨려요", ["chills"], []),
    ("심장 부분", [], ["palpitations", "pain"]), ("머리 주위", [], ["pain"]), ("왼쪽 팔", [], ["limb_weakness", "pain"]), ("가슴 부근", [], ["pain", "palpitations"]),
    ("기침약을 먹었어요", [], ["cough"]), ("혈관성 편두통 진단을 받았어요", [], ["pain"]), ("날씨가 많이 추워요", [], ["chills"]),
    ("목은 괜찮은지 헷갈려요", ["sore_throat", "pain"], ["confusion"]), ("누런 가래가 나오는 기침을 해요.", ["cough", "EV:E_182"], [], ["cough"]),
    ("기침하고 열이 나요", ["cough", "fever"], [], ["cough", "fever"]), ("목이 아프고 숨이 차요", ["sore_throat", "pain", "dyspnea"], [], ["dyspnea"]),
    ("코피가 나요", [], ["hemoptysis", "hematemesis"]), ("기침하면 피가 같이 나와요", ["hemoptysis", "cough"], [H]), ("토할 것만 같아요", [N], [V, H]),
]


def main():
    P = S.DATA / "regression_cases.json"
    if P.exists():
        print("exists", S.sha256(P)[:16])
        return
    rows = [{"text": c[0], "allowed": c[1], "forbidden": c[2], "must_any": c[3] if len(c) > 3 else []} for c in CASES]
    S.dump_json(P, {"label": "EXPOSED_REGRESSION(지시문 3절·STEP29.2 HOLDOUT 사례, 반복 노출)", "rules": __doc__, "cases": rows})
    print(len(rows), S.sha256(P)[:16])


if __name__ == "__main__":
    main()
