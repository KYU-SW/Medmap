# MedMap 로컬 저장공간 관리

프로젝트 종료 후 한 번에 정리할 수 있도록 프로젝트 전용 파일을 가능한 한 이 저장소 아래에 둔다.
이 문서는 삭제 명령이 아니라 위치 기록이다. 실제 삭제 전에는 GitHub 업로드와 미커밋 파일을 다시 확인한다.

## 프로젝트 전용 저장 위치

|항목|경로|GitHub 보관|복원 방법|
|---|---|---|---|
|프로젝트 코드·문서|MedMap 저장소 루트|예|GitHub clone|
|DDXPlus 원본|`data/`|아니오|`01_download.py`|
|Python 환경|`apps/api/.venv/`|아니오|`scripts/setup_api.ps1`|
|Frontend 패키지|`apps/web/node_modules/`|아니오|추후 lockfile 기준 설치|
|Whisper 모델|`local-cache/huggingface/`|아니오|첫 모델 실행 시 재다운로드|
|모바일 시험용 인증서|`local-cache/mobile-https/`|아니오|`scripts/setup_mobile_https.ps1`|
|pip 캐시|`local-cache/pip/`|아니오|패키지 설치 시 재생성|
|pnpm 캐시|`local-cache/pnpm-store/`|아니오|lockfile 기준 재생성|
|실험 결과|`runs/`|선별|재현 코드 또는 최종 결과 보존|
|모델 체크포인트|`checkpoints/`|아니오|필요 시 별도 원격 보관|

## 프로젝트 밖에서 사용하는 항목

- Git for Windows와 NVIDIA 드라이버는 공용 프로그램이므로 MedMap 종료 시 삭제하지 않는다.
- Codex에 포함된 Python은 다른 작업도 사용하는 공용 런타임이므로 삭제하지 않는다.
- 사용자에게 받은 원본 문서는 OneDrive/카카오톡 받은 파일에 있으며 프로젝트 파일과 별도로 관리된다.
- GitHub 인증정보는 Windows 자격 증명 관리자에 있다. 프로젝트 폴더 삭제와 별개다.

## 용량 확인

일반 PowerShell에서 다음을 실행한다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\storage_report.ps1
```

프로젝트가 끝나면 다음 순서로 정리한다.

1. `git status`로 미커밋 파일 확인
2. 필요한 코드·문서·최종 결과를 GitHub에 push
3. 원격 커밋과 복원 방법 기록
4. `storage_report.ps1`로 실제 삭제 대상과 용량 확인
5. 사용자가 삭제 범위를 승인한 뒤 프로젝트 전용 경로만 삭제

현재는 어떤 파일도 삭제하지 않는다.

## 2026-09-29 현재 용량

|항목|대략적인 용량|
|---|---:|
|저장소 전체|5.45 GB|
|DDXPlus 원본|0.17 GB|
|Python 환경|2.25 GB|
|웹 패키지|0.07 GB|
|Whisper·패키지 캐시|2.95 GB|

용량은 실행할 때마다 달라질 수 있으므로 삭제 직전에 `storage_report.ps1`로 다시 확인한다.
현재 패키지 캐시에는 GPU 라이브러리 설치 파일이 포함되어 있다. 설치 완료 후에는
`local-cache/pip/`를 삭제해도 실행에 영향이 없으며, 필요하면 다시 받을 수 있다.
