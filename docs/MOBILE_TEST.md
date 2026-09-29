# 모바일 STT 로컬 시험

이 방식은 MedMap 화면과 음성을 같은 Wi-Fi의 개발 PC 안에서 처리한다.
개발 중에는 실제 환자정보 대신 테스트 문장만 사용한다.

## 아이폰 설정

1. 아이폰과 PC를 같은 Wi-Fi에 연결한다.
2. Safari에서 `http://192.168.35.215:8081/medmap-local-ca.cer`를 연다.
3. 인증서 프로파일 다운로드를 허용한다.
4. 설정 → 일반 → VPN 및 기기 관리에서 `MedMap Local Test CA`를 설치한다.
5. 설정 → 일반 → 정보 → 인증서 신뢰 설정에서 `MedMap Local Test CA`를 켠다.
6. Safari에서 `https://192.168.35.215:5173`을 연다.
7. 녹음 시작을 누르고 마이크 사용을 허용한다.

2026-09-29 실제 iPhone Safari에서 접속, 마이크 녹음, 한국어 변환까지 확인했다.

Windows 방화벽 안내가 나타나면 개인 네트워크만 허용한다. 주소가 열리지 않으면 PC와
아이폰이 같은 Wi-Fi인지 확인한다. PC의 주소가 바뀌면 인증서를 다시 생성해야 한다.

## 안드로이드

같은 인증서 파일을 설치하고 `https://192.168.35.215:5173`을 Chrome에서 연다.
안드로이드 버전에 따라 사용자 인증서 설치 메뉴 이름이 다를 수 있다.

## 시험 후 정리

- 아이폰·안드로이드에서 `MedMap Local Test CA` 프로파일 또는 사용자 인증서를 삭제한다.
- PC에서는 `local-cache/mobile-https/`를 삭제한다.
- 인증서 개인키는 `local-cache/mobile-https/ca-key.pem`이며 Git에서 제외한다.
- 프로젝트 전체 정리 때는 `LOCAL_STORAGE_PLAN.md`의 순서를 따른다.
