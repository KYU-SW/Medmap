# MedMap: DDXPlus 첫 분석

사용자가 제공한 프로젝트 기준안은 PROJECT_BRIEF.txt에 보존했다. 현재 범위는 데이터 확보·구조 확인·통계·부분 관찰 설계다.

## 실행 준비

일반 Python 환경에서는 Python 3.11 이상을 준비하고 이 폴더에서 다음을 실행한다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -X utf8 01_download.py
.\.venv\Scripts\python.exe -X utf8 02_inspect.py
.\.venv\Scripts\python.exe -X utf8 03_audit.py
```

현재 PC에는 `python` 명령이 PATH에 없어, 이번 검증에는 Codex에 포함된 Python과 pandas 3.0.1을 사용했다.
이 PC에서 설치 없이 다시 실행하려면 다음과 같이 실행한다.

```powershell
$medmapPython = 'C:\Users\alsdn\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $medmapPython -X utf8 'C:\Users\alsdn\Documents\Codex\2026-09-28\files-pasted-by-the-user-it\outputs\MedMap\02_inspect.py'
```

마지막 파일명을 01_download.py 또는 03_audit.py로 바꿔 각 단계를 실행할 수 있다. 앱 번들 경로는 다른 PC에서는 다를 수 있다.

## 1단계 — 공식 파일 확보

**무엇을 하는지:** 영문 v2의 파일 5개를 다운로드하고 크기와 MD5를 확인한다.

**왜 필요한지:** 같은 이름의 파일도 배포 버전이 바뀔 수 있다. 재현을 위해 버전·파일 ID·해시가 필요하다.

**코드:** 01_download.py. 이미 일치하는 파일이 있으면 다시 받지 않는다. 총 다운로드는 약 179 MB다.

|파일|역할|직접 다운로드|
|---|---|---|
|release_evidences.json|소견 ID, 질문, 자료형, 기본값, 값의 의미|https://ndownloader.figshare.com/files/40278013|
|release_conditions.json|질환명, ICD-10, 증상·과거력 연결 목록|https://ndownloader.figshare.com/files/62561569|
|release_train_patients.zip|학습 환자 CSV|https://ndownloader.figshare.com/files/40278019|
|release_validate_patients.zip|검증 환자 CSV|https://ndownloader.figshare.com/files/40278022|
|release_test_patients.zip|최종 평가 환자 CSV|https://ndownloader.figshare.com/files/40278016|

**예상 결과:** `All five files verified.` 및 data 폴더의 파일 5개. 이번 실행에서 확인 완료.

**다음 단계:** evidences → conditions → train의 첫 3행 순서로 연다. ZIP을 풀지 않아도 pandas가 읽는다.

실제 ZIP 안의 파일명은 각각 `release_train_patients`, `release_validate_patients`, `release_test_patients`이며 `.csv` 확장자가 없다. 내용은 CSV이므로 확장자만으로 파일 형식을 판단하지 않는다.

배포 출처: https://figshare.com/articles/dataset/DDXPlus_Dataset_English_/22687585/2

DOI: https://doi.org/10.6084/m9.figshare.22687585.v2

공식 설명: https://github.com/mila-iqia/ddxplus

API: https://api.figshare.com/v2/articles/22687585/versions/2

2026-09-28 확인한 라이선스는 CC BY 4.0이다. 이번 다운로드에는 로그인·신청·결제가 필요하지 않았다.
논문과 데이터셋을 인용하고 가공 여부를 표시한다. 라이선스 원문: https://creativecommons.org/licenses/by/4.0/
실제 응답 메타데이터는 source_manifest.json에 저장했다.

## 2단계 — 실제 샘플 열기

**무엇을 하는지:** train 첫 3행을 읽고 EVIDENCES와 감별진단 문자열을 리스트로 변환한다.

**왜 필요한지:** 문자열을 리스트로 착각하면 증상 대신 문자 하나씩 처리할 수 있다.

**코드:** 02_inspect.py. 핵심 부분은 다음과 같다.

```python
df = pd.read_csv(DATA / 'release_train_patients.zip', nrows=3)
print(df.shape)
print(df.columns.tolist())
tokens = ast.literal_eval(df.loc[0, 'EVIDENCES'])
```

`ast.literal_eval`을 사용한다. 임의 코드를 실행할 수 있는 `eval`은 쓰지 않는다.

**예상 결과:** 샘플 shape는 (3, 6). 이는 전체 train 크기가 아니다.

|컬럼|해석|첫 실험에서의 용도|
|---|---|---|
|AGE|나이|모델 배경정보|
|DIFFERENTIAL_DIAGNOSIS|합성 데이터의 감별진단 목록과 가중치|평가용으로 격리|
|SEX|성별 코드|모델 배경정보|
|PATHOLOGY|주질환 정답|train의 학습 목표, 평가 정답|
|EVIDENCES|소견 토큰 목록|관찰된 부분만 모델 입력|
|INITIAL_EVIDENCE|최초 제시 소견|초기 관찰 출발점|

직접 확인한 train 첫 3행:

|0부터 시작하는 행 번호|나이|성별|정답|최초 소견|원본 소견 토큰 수|
|---|---:|---|---|---|---:|
|0|18|M|URTI|E_91|19|
|1|21|M|HIV (initial infection)|E_50|31|
|2|19|F|Pneumonia|E_77|34|

samples.json에는 이 세 환자의 소견을 영문 질문과 값으로 해독한 결과를 저장했다.
표의 진단은 정답 라벨이며 모델이 생성한 working diagnosis가 아니다.

**다음 단계:** 소견의 자료형을 이해한 뒤 전체 통계를 읽는다.

## 3단계 — 소견과 질환 관계 해석

**무엇을 하는지:** `_@_`를 기준으로 ID와 값을 분리하고 JSON 정의에 연결한다.

**왜 필요한지:** 토큰 개수와 소견 개수가 다르다. 여러 통증 부위는 하나의 소견 ID에 속할 수 있다.

**코드:** 02_inspect.py의 `token.partition('_@_')`와 `value_meaning` 조회.

```python
code, separator, value = token.partition('_@_')
definition = evidences[code]
meaning = definition['value_meaning'].get(value, {}).get('en', value)
```

**예상 결과:** E_91은 발열 관련 이진 소견. E_55는 복수 선택형 통증 위치이며 E_55_@_V_89는 forehead 값이다.
숫자형 범주값도 있으므로 모든 값이 V_로 시작한다고 가정하지 않는다.
223개 정의는 B 208개, C 10개, M 5개다. 증상 110개, 과거력 등 antecedent 113개다.

conditions의 symptoms/antecedents는 질환과 연결된 ID 목록이며 실제 확인한 연결 값은 빈 객체다.
여기에는 P(소견|질환) 수치가 제공되지 않으므로 희귀도·우도비를 직접 읽을 수 없다.
목록에 없다는 것만으로 그 질환에서 소견이 불가능하다고 단정하지 않는다.

CSV 빈칸과 미관찰 상태는 다르다. 이 파일에는 소견마다 '질문했는지'를 표시하는 컬럼이 없다.
MedMap에서 관찰 마스크를 추가해야 한다. 기본값이 NA인 항목도 있기 때문에 미기재를 일괄적인 임상적 음성으로 바꾸면 안 된다.

**다음 단계:** 전체 split 통계 및 중복 검사.

## 4단계 — 전체 통계와 누수 후보 확인

**무엇을 하는지:** 20,000행씩 읽어 shape, 라벨 분포, 결측, 소견 수, 감별진단 수, 코드 유효성, 중복을 계산한다.

**왜 필요한지:** 샘플 몇 개만으로 전체 자료의 일관성이나 split 독립성을 판단할 수 없다.

**코드:** 03_audit.py. 전체 실행에는 몇 분 걸릴 수 있다. 청크 단위 입력이지만 중복 해시와 길이 목록은 메모리에 유지한다.

```python
for chunk in pd.read_csv(path, chunksize=20000):
    print(chunk.shape)
    print(chunk['PATHOLOGY'].value_counts())
```

이 짧은 예제는 청크별 출력이다. 제공한 스크립트는 Counter로 전체 라벨 분포를 합산한다.

**예상 결과:** audit.json. 실제 실행 결과 요약은 RESULTS.md에 정리한다.

중복 기준은 두 종류다. full은 여섯 컬럼을 포함하되 소견·감별 목록의 순서를 정규화한 값이고,
features는 AGE+SEX+전체 소견이다. split 내 중복은 첫 행을 제외한 행 수, split 간 중복은 공통 고유 패턴 수다.
후자는 공유 환자 수가 아니다. 환자 식별자가 없으므로 같은 실제 인물인지 판단할 수 없다.
완전 일치 검사는 유사 환자·공통 생성 지식·숨은 생성기 의존성까지 배제하지 못한다.
test를 열어본 것은 구조·무결성 감사에 한정한다. 모델·임계값 선택은 validation에서 수행한다.

**다음 단계:** 04_partial_observation_design.md에 따라 관찰 상태와 시뮬레이터를 구현한다.

## 5단계 — 부분 관찰 설계

**무엇을 하는지:** 초기 소견을 포함한 3/5개 관찰과 이후 최대 1/3개의 순차 추가정보를 정의한다.

**왜 필요한지:** 전체 소견·정답을 탐지기나 질문 선택기에 노출하면 연구 질문을 제대로 평가할 수 없다.

**코드:** 이번 단계는 설계만 완료했다. 후속 구현의 인터페이스는 아래처럼 분리한다.

```python
# 아직 구현하지 않은 인터페이스 예시
observation = observe(patient_id, selected_evidence_ids)
working_diagnosis = baseline.predict(observation)
alert = detector.check(observation, working_diagnosis)
next_id = nbinfo.select(observation, working_diagnosis, alternatives)
```

**예상 결과:** 모델에는 공개된 정보만 전달되고, 정답과 미관찰 응답은 평가기·시뮬레이터에만 남는다.

**다음 단계:** 중복 처리 정책을 고정한 뒤 관찰 인코더를 구현한다. 상세 통제조건과 회복률 분모는 설계 문서를 따른다.

아직 기본 진단 모델, 외부 독립 의료지식 탐지, NBInfo 실험 결과는 없다.
이번 자료는 합성 데이터 분석이며 실제 환자 성능 또는 임상적 오진 감소를 입증하지 않는다.
