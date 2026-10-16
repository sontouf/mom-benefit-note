# 방문자 카운터 (Cloudflare Workers + D1, 무료)

사이트에 "지금 보는 사람"과 "오늘 이 페이지 방문 수"를 보여주는 아주 작은 서버입니다.
- 개인정보를 저장하지 않습니다. IP나 쿠키는 쓰지 않고, 브라우저 탭마다 임의의 세션 ID만 씁니다.
- 무료 한도: D1 하루 쓰기 10만 행. 하루 방문 수만 건 수준까지는 충분합니다.

## 배포 (한 번만)
```bash
cd counter
npx wrangler login                          # 브라우저로 Cloudflare 로그인
npx wrangler d1 create mombenefit-counter   # 나온 database_id 를 wrangler.toml 에 입력
npx wrangler d1 execute mombenefit-counter --remote --file=schema.sql
npx wrangler deploy                         # 주소 예: https://mombenefit-counter.<계정>.workers.dev
```
배포 주소를 GitHub 저장소 Variables 의 `COUNTER_URL` 에 넣으면, 다음 자동 실행부터 사이트에 표시됩니다.
카운터가 꺼져 있거나 장애가 나면 위젯만 숨겨지고 사이트는 그대로 동작합니다. 가짜 숫자는 절대 표시하지 않습니다.
