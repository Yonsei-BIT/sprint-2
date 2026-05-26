# Handwriting Font Lab

패드/펜슬로 영어, 숫자, 수식 기호 샘플을 입력하고, 획 좌표/시간/압력 데이터를 서버로 보내 실제 `.ttf` 폰트 파일을 생성한 뒤, 파일이나 입력 텍스트를 손글씨 스타일 PDF로 렌더링하는 기술 검증용 웹사이트입니다.

## 사용자 여정

1. 패드/펜슬로 화면에 표시되는 영어 대소문자, 숫자, 수식 기호 샘플을 작성합니다.
2. 브라우저가 각 글자의 stroke 좌표, 시간, 압력, PNG 스냅샷을 저장합니다.
3. 사용자가 TXT/PDF 파일을 넣거나 변환할 문장을 직접 입력합니다.
4. Python 서버가 저장된 stroke를 정규화해 영어/수식 glyph가 포함된 최소 TrueType 폰트를 생성합니다.
5. 웹사이트가 생성된 `.ttf`를 `FontFace`로 로드합니다.
6. 생성된 폰트로 미리보기와 PDF를 만듭니다.

## 현재 구현 범위

- 브라우저 기반 필기 캔버스
- pointer pressure/time 기반 stroke 데이터 수집
- TXT/PDF 파일 입력
- 샘플 JSON 내보내기
- 의존성 없는 Python `/api/font` 서버
- 의존성 없는 Python `/api/extract` PDF 텍스트 추출
- 영어/숫자/수식 기호 glyph를 포함한 최소 TrueType `.ttf` 생성
- 소문자 x-height, 대문자 cap-height, 숫자, 괄호, 연산자별 폰트 메트릭 정규화
- 괄호/구두점/수식 연산자 주변의 좁은 자간 처리
- 브라우저 localStorage에 샘플 저장 및 재방문 시 자동 복원
- 글자별 샘플 수정/덮어쓰기
- 12pt 문서 크기에 가까운 최종 렌더링
- 생성된 TTF를 웹폰트로 로드
- 생성 폰트를 적용한 PDF 이미지 출력

현재 버전은 AI 보간 모델이 아니라 “영어와 수식 기호를 실제 폰트 파일로 저장하고 문서/수식 텍스트를 손글씨로 변환하는 경험”을 검증하는 MVP입니다. 샘플이 없는 문자는 시스템 기본 폰트로 대체됩니다.

## 로컬 실행

정적 서버가 아니라 API 서버를 실행해야 폰트 생성이 됩니다.

```bash
python3 server.py
```

브라우저에서 `http://localhost:3000`을 열면 됩니다.

## 패드에서 테스트

패드와 Mac을 같은 Wi-Fi에 연결한 뒤, Mac에서 서버를 실행합니다.

```bash
python3 server.py
```

그 다음 패드 브라우저에서 Mac의 Wi-Fi IP와 포트를 입력합니다.

```text
http://<Mac-Wi-Fi-IP>:3000
```

예: `http://172.24.146.182:3000`

## 배포 메모

Vercel에 공개 배포할 수 있도록 `/api/font.py`, `/api/extract.py`를 포함했습니다. GitHub 저장소를 Vercel에서 Import하면 정적 웹페이지와 Python API Function이 함께 배포됩니다.

배포 절차:

1. GitHub 저장소에 이 파일들을 업로드합니다.
2. Vercel에서 `New Project`를 누릅니다.
3. `Yonsei-BIT/sprint-2` 저장소를 Import합니다.
4. Framework Preset은 `Other` 또는 기본값으로 둡니다.
5. Deploy를 누릅니다.

배포 후 Vercel이 제공하는 `https://...vercel.app` 주소가 최종 공유 URL입니다.
