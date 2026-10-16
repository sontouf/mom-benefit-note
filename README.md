# 엄마혜택노트

행정안전부 「대한민국 공공서비스(혜택) 정보」 API(약 1.1만 건)를 매일 수집합니다. 그중 **임신·출산·육아·교육·살림** 관련 혜택(약 3,600건)을 골라 엄마 관점의 정적 사이트로 만듭니다. 같은 데이터로 **스레드 게시글 초안과 카드뉴스 이미지**도 매일 자동 생성합니다.

수익 구조: 스레드(입소문) → 사이트(검색 유입) → 광고(AdSense)

## 무엇을 만드나

| 페이지 | 내용 |
|---|---|
| `/` | 단계 타일, 요즘 엄마들 관심사, 금액 큰 혜택, 마감 임박, 신규, 인기 |
| `/stage/{단계}/` · `/stage/{단계}/{시도}/` | 임신 준비 → 임신 → 출산 → 영유아 → 초등 → 중고등 + 다자녀·한부모·워킹맘·살림. "꼭 챙길 것" 체크리스트 포함 |
| `/trend/` · `/trend/{주제}/` | 스레드·맘카페 인기 주제 + 인용 + 공공데이터로 확인된 관련 혜택 |
| `/trend/birth-bonus/` | 시군구 출산축하금 순위 (공공데이터에서 직접 집계한 고유 콘텐츠) |
| `/region/…` | 시도·시군구별 우리 동네 혜택 |
| `/find/` | 30초 맞춤 찾기 (브라우저 안에서만 처리, 개인정보 전송 없음) |
| `/clinic/` · `/clinic/{시도}/` | 밤 8시 이후·주말·공휴일 진료 소아청소년과 (국립중앙의료원 API, 활용신청 후 자동 활성화) |
| `/deadline/`, `/changes/` | 마감 D-day, 매일 신규·변경 기록 |
| `/cards/{날짜}/…png` | 스레드 카드뉴스 이미지 (1080×1350) |

## 디자인
- 규칙은 [`DESIGN.md`](DESIGN.md)에 있습니다. 웹과 카드뉴스가 같은 토큰을 씁니다(코랄 1색 + 웜그레이, 그라데이션·그림자 없음).
- 폰트: Pretendard (OFL)
- 아이콘: [Microsoft Fluent Emoji 3D](https://github.com/microsoft/fluentui-emoji) (MIT). `static/emoji/` 에 있고, 다시 받으려면 `python tools/fetch_assets.py` 를 실행하세요.
- 카드뉴스는 headless Chrome으로 HTML(`templates/card.html`)을 캡처해서 만듭니다.

## 트렌드 주제 관리
`data/trends.json` 은 사람이 고르는 큐레이션 목록입니다. 주제, 스레드 인용(짧게 + 원문 링크), 공공데이터 매칭 키워드, 주의 문구로 구성됩니다.
- 새 주제는 이 파일에 추가하면 페이지와 카드가 자동으로 생깁니다.
- `checked` 날짜를 갱신하고, 인용은 한두 문장 이내로 짧게 유지하세요.
- 스레드 소문과 공공데이터 원문이 다르면 `caution` 에 적어 둡니다. 예: 아동수당 9세 확대 vs 원문 8세.

## 실행

```bash
pip install -r requirements.txt
export DATA_GO_KR_KEY='공공데이터포털 일반 인증키(Decoding)'
python run.py all          # 수집 → 사이트 → 스레드 초안·카드
python run.py cards        # 수집 없이 사이트 + 카드만 다시
python -m http.server -d public 8000
python -m unittest discover -s tests
```

- 스레드 초안은 `drafts/{날짜}.json` 에 저장됩니다. 본문, 첫 댓글(링크·출처), 이미지 경로가 들어 있습니다.
- **자동 게시는 하지 않습니다.** 사람이 검수한 뒤 올리세요. 자동 생성 글을 그대로 대량 게시하면 스팸으로 처리될 위험이 있습니다.

## 추가 공공데이터 (활용신청 필요)
같은 인증키로 쓰려면 공공데이터포털에서 데이터셋마다 **활용신청**을 해야 합니다(자동승인, 무료). 신청 전에는 해당 기능만 건너뛰고 나머지는 정상 동작합니다.

| 기능 | 데이터셋 | 상태 |
|---|---|---|
| 지원금 전체 | [행정안전부_대한민국 공공서비스(혜택) 정보](https://www.data.go.kr/data/15113968/openapi.do) | 사용 중 |
| 밤·주말 소아과 | [국립중앙의료원_전국 병·의원 찾기 서비스](https://www.data.go.kr/data/15000736/openapi.do) | 코드 준비 완료, 활용신청 대기 |
| 어린이제품 리콜 (후보) | [국가기술표준원_제품 안전인증 및 리콜 정보](https://www.data.go.kr/data/15116894/openapi.do) | 명세 확인 후 추가 예정 |

## 스레드 게시 (검수 후 1건씩)
```bash
export THREADS_USER_ID=...  THREADS_TOKEN=...   # Meta 개발자 앱(Threads API)에서 발급
python tools/post_threads.py drafts/2026-10-17.json --list
python tools/post_threads.py drafts/2026-10-17.json --key birth-bonus
```
- 본문, 첫 댓글, 이미지를 보여준 뒤 `y` 를 입력해야 게시합니다. 카드 캐러셀을 올리고 링크·출처는 첫 댓글로 답니다.
- 이미지는 배포된 사이트의 공개 URL이어야 합니다(`SITE_URL` 설정 필수).
- 하루 1~2개 정도로 간격을 두세요. 자동 대량 게시는 일부러 지원하지 않습니다.

## 배포 (GitHub Actions + Pages, 무료)
1. public 저장소에 push → Settings → Pages → Source: **GitHub Actions**
2. Secret `DATA_GO_KR_KEY`, Variables `SITE_URL`, `BASE_PATH`(커스텀 도메인이면 비움), 선택으로 `SITE_NAME`, `CNAME`, `ADSENSE_CLIENT`
3. Actions → `daily-update` → Run workflow. 이후 매일 06:00 KST에 수집, 빌드, 카드 생성, 배포가 자동으로 실행됩니다. 스레드 초안은 실행 결과의 `threads-drafts` 아티팩트로 내려받습니다.

## 검색 노출·수익화 설정 (코드는 준비됨, 값만 넣으면 켜짐)
GitHub 저장소 → Settings → Secrets and variables → Actions → **Variables** 에 넣으면 다음 자동 실행부터 반영됩니다.

| 할 일 | 넣을 변수 | 얻는 곳 |
|---|---|---|
| 구글 검색 등록 | `GOOGLE_SITE_VERIFICATION` (meta 태그의 content 값) | [Search Console](https://search.google.com/search-console) → URL 접두어 → HTML 태그 방식. 등록 후 `sitemap.xml` 제출 |
| 네이버 검색 등록 (엄마들은 네이버 검색 비중이 큼) | `NAVER_SITE_VERIFICATION` | [네이버 서치어드바이저](https://searchadvisor.naver.com) → 사이트 등록 → HTML 태그. 등록 후 `sitemap.xml`·`rss.xml` 제출 |
| 방문 통계 | `GA_ID` (예: `G-XXXXXXX`) | [Google Analytics](https://analytics.google.com) |
| 광고 | `ADSENSE_CLIENT` (예: `ca-pub-...`) | [AdSense](https://adsense.google.com). 넣으면 광고 코드와 `ads.txt` 가 자동 생성 |
| 개인 도메인 (선택, 연 1~2만 원) | `CNAME`=도메인, `SITE_URL`=`https://도메인`, `BASE_PATH`=빈 값 | 도메인 구입 후 DNS에 GitHub Pages 연결 |

이미 들어가 있는 것: 개인정보처리방침(`/privacy/`, AdSense 심사 필수), RSS(`/rss.xml`), 링크 미리보기 이미지(`static/og.png`, 다시 만들려면 `python tools/render_og.py`).

## 로컬에서 수정할 때
자동 실행이 매일 `data/` 를 커밋하므로, 수정 전에 반드시 `git pull --rebase` 를 먼저 하세요.

## 주의
- 비공식 사이트임을 명시하고 원문 링크와 출처를 항상 표시합니다(템플릿에 반영됨).
- 금액은 지원 내용 텍스트에서 자동으로 뽑은 '최대' 값입니다. 사업비, 대출, 3천만 원 초과 금액은 표시하지 않습니다.
- 지원조건 코드는 그룹이 전부 Y이면 '제한 없음'이라는 뜻이라, 일부만 Y인 코드만 대상 분류에 씁니다.
- 수집 건수가 전날보다 20% 넘게 줄면 중단합니다(API 장애로 거짓 '종료' 기록이 생기는 것 방지).
