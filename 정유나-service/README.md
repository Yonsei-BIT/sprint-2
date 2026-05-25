# LearnUs Slack 마감 알림 봇

런어스(ys.learnus.org) 과제 및 동영상 강의 마감일을 Slack으로 알려주는 봇

## 기능
- 과제 마감 D-3, D-1, D-0 알림 (오전 9시)
- 당일 마감 D-0 재알림 (오후 9시)
- 동영상 강의 마감 알림 (시청 완료된 항목 자동 제외)
- 세션 만료 시 갱신 안내 알림

## 기술 스택
- Python 3.11
- GitHub Actions (자동 스케줄 실행)
- Slack Incoming Webhooks
- BeautifulSoup4 (HTML 스크래핑)

## 실행 방식
GitHub Actions에서 매일 오전 9시·오후 9시 KST 자동 실행
세션 유지를 위해 6시간마다 keep-alive 실행

## 환경변수 (GitHub Secrets)
- `LEARNUS_SESSION` : MoodleSession 쿠키 값
- `SLACK_WEBHOOK_URL` : Slack Incoming Webhook URL
