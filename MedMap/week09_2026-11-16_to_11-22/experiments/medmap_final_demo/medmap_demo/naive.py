"""비교용 단순 처리(BASE). 의도적으로 약하게 정의한 부분(공개):
1) 시각 필터를 '관찰 시각(observed_at) <= 조회 시점'으로 한다(관찰 시각이 없으면 기록 시각). 이용 가능 시각·기록 시각을 보지 않는다.
2) 상태를 보지 않는다: 요청·대기·취소 기록도 '항목 + 상태' 문장으로 근거에 넣는다.
3) 중복을 제거하지 않는다. 정정 계보를 보지 않아 이전 버전과 정정본을 모두 쓴다.
4) 환자 ID 를 확인하지 않고 수신 묶음(feed) 소속만으로 환자 자료로 본다.
5) 보류 사유를 내지 않는다(모든 근거를 사용).
이는 흔한 구현 실수를 모은 기준선이며, 실제 의료 AI 전체를 대표하지 않는다.
"""
from __future__ import annotations


def naive_inputs(store, case, as_of, snapshot_only: bool = False) -> list:
    """BASE 가 AI 입력으로 쓰는 (event, text) 목록. snapshot_only 는 재생 일치 검사용(그 당시 저장소)."""
    evs = store.snapshot(as_of).events.values() if snapshot_only else store.events.values()
    out = []
    for e in evs:
        if e.feed_id not in case.feed_ids:
            continue
        t = e.observed_at or e.recorded_at
        if t <= as_of:
            out.append((e, e.content if e.content else f"{e.item} {e.status.lower()}"))
    return sorted(out, key=lambda x: x[0].event_id)
