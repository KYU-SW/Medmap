# STT v1 기능 정의

## 목표

사용자가 웹에서 녹음한 한국어 음성을 수정 가능한 문장으로 변환한다.

```text
녹음 → 음성 파일 전송 → 한국어 문장 변환 → 입력창 표시 → 사용자 수정·확인
```

## 포함 범위

- 웹 녹음 시작·종료
- 서버로 음성 전송
- 한국어 음성 인식
- 변환 중·실패 상태 표시
- 결과를 수정 가능한 입력창에 표시
- 실제 휴대폰 브라우저 확인

## 제외 범위

- 증상 추출
- 부정·시간·중증도 해석
- 질환 후보 생성
- 사용자 확인 전 PatientState 변경
- 음성 또는 변환 문장의 영구 저장

## API 계약

요청:

```text
POST /v1/stt/transcribe
Content-Type: multipart/form-data
file: 녹음 파일
```

성공 응답:

```json
{
  "transcript": "어제부터 머리가 아프고 열은 없어요.",
  "language": "ko",
  "duration_seconds": 4.2
}
```

실패 응답은 사용자가 이해할 수 있는 `detail`을 포함한다. 내부 오류나 음성 내용은 로그에 남기지 않는다.

## 1차 완료 기준

- 컴퓨터 브라우저에서 한국어 음성 변환 확인 완료 (2026-09-29)
- 한국어 의료 테스트 문장 5개 변환 확인 완료 (2026-09-29)
- 무음·빈 파일·지원하지 않는 형식 처리
- 변환 결과 수정 가능
- 중복 제출 방지
- iPhone Safari 실기기 확인 완료 (2026-09-29)
- Android Chrome 실기기 확인
- 원본 음성과 transcript 미저장 확인

## 로컬 모델 기본값

- 엔진: `faster-whisper==1.2.1`
- 모델: `turbo` (`whisper-large-v3-turbo` 계열)
- 언어: 한국어 고정
- 기본 실행: RTX 4070 Ti SUPER, CUDA `float16`
- GPU 라이브러리가 없을 때: CPU `int8`

2026-09-29 프로젝트 전용 NVIDIA CUDA 12용 cuBLAS·cuDNN을 설치하고,
개인정보가 없는 메모리상 무음 데이터로 GPU 추론 성공을 확인했다.
서버 시작 시 모델과 GPU를 미리 준비하며, 각 요청의 실제 변환 시간을 화면에 표시한다.
2026-09-29 컴퓨터 및 iPhone 시험에서 CPU 실행 때보다 체감 변환 속도가 크게 개선된 것을 확인했다.

현재 속도와 정확도가 1차 사용 범위를 만족하므로 실시간 조각 전송은 보류한다. 이후 긴 문장이나
연속 대화에서 지연이 문제가 될 때 별도 단계로 구현한다.

모델은 첫 실행 때 내려받으므로 인터넷 연결과 추가 저장공간이 필요하다.

## 의료 용어 힌트 (2026-10-02, 기본 꺼짐)

`MEDMAP_STT_HOTWORDS=medical`로 켜면 증상·약 이름 목록(`stt_service.py`의 `MEDICAL_HOTWORDS`)을
Whisper `hotwords`로 넘긴다. 다른 글자를 넣으면 그 단어들을 그대로 쓴다. 비우면 꺼진다.

효과는 아직 측정하지 않았다. 힌트가 오히려 오인식을 늘릴 수 있으므로, 실제 녹음 파일로 켜고 끈 결과를
비교한 뒤에 기본값을 정한다.

```powershell
cd apps\api
.\.venv\Scripts\python.exe -m scripts.transcribe_file <녹음 파일> --device cuda
.\.venv\Scripts\python.exe -m scripts.transcribe_file <녹음 파일> --device cuda --hotwords medical
```
