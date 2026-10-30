# 연구용 Doctor Preview 명세(preview/index.html)

- 정적 단일 HTML. outputs/end_to_end_cases.json 에서 만든 사례 데이터를 담는다(build_preview.py). 서버·8010·master 연결 없음, 외부 리소스 없음.
- 토큰: master medmap-web/src/doctor/doctor.css 의 색·반경·그림자 값을 참고(파일 복사 없음). 글꼴 파일은 넣지 않고 시스템 글꼴. 다크 모드 토큰 추가.
- 화면: 사례 선택(select, 노출 회귀/새 평가 묶음) · 블라인드 흐름 4단계(4단계 질환 후보는 Preview 에 없음) ·
  A 환자가 말한 내용(추출 구간 밑줄 + 범주 위첨자) · 의사 검토용 8칸(확인된 증상·AI 추출 후보·부정·과거·다른 사람·새 표준 후보·추가 확인 필요·증상 아닌 문맥) ·
  B·C 증상별 표준화 표(원문 위치·concept·범주·있음/시점/주체·적격) · G 모델 입력 적격(STAGE_A·STAGE_B·실제 입력 없음) · F 확인 전후 차이(dummy 확인 버튼).
- 금지: 질환 이름·점수·순위·확률, '확정' 표현, 빨간 경고색.
- 확인: Playwright 1280·375 폭 렌더링(logs/render_check). 결함 4개(F 표 열 꺾임, 같은 상태 diff 행, 확인 항목 중복, 모바일 표 첫 열) 수정 뒤 재확인 — 375 폭 페이지 가로 넘침 없음(표는 상자 안 가로 스크롤).
