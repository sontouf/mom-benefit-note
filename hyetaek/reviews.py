"""혜택별 후기: 플랫폼 검색 링크 + (선택) 네이버 검색 API로 실제 블로그·카페 후기 수집.

- 스레드·인스타·X·유튜브는 남의 글을 가져오는 무료 공식 API가 없고 스크래핑은 약관 위반이라,
  혜택 이름으로 '후기 검색 결과'가 바로 열리는 링크만 만든다.
- 네이버 블로그·카페(맘카페 포함)는 공식 검색 API(https://developers.naver.com/docs/serviceapi/search/blog/blog.md)
  로 제목·요약·원문 링크를 받아 보여준다. NAVER_CLIENT_ID / NAVER_CLIENT_SECRET 가 있을 때만 동작한다.
  API 약관에 따라 원문 전체를 복제하지 않고 제목·짧은 요약·원문 링크만 쓴다.
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

API = "https://openapi.naver.com/v1/search/{kind}.json"
REFRESH_DAYS = 7
MAX_CALLS = 600  # 하루 무료 한도 25,000회 중 아주 일부만 쓴다


def clean_name(name):
    """'[샘플] 해운대구 산모 지원(확대)' → '해운대구 산모 지원'"""
    s = re.sub(r"\[[^\]]*\]|\([^)]*\)|（[^）]*）", " ", name or "")
    return re.sub(r"\s+", " ", s).strip()


def search_links(name):
    """플랫폼별 '후기 검색' 링크. 항상 유효하고 로그인 없이 열린다(인스타·X는 앱/로그인 필요할 수 있음)."""
    q = clean_name(name)
    qq = urllib.parse.quote(f"{q} 후기")
    tag = urllib.parse.quote(re.sub(r"[^0-9A-Za-z가-힣]", "", q))
    return [
        ("cafe", "맘카페 후기", f"https://search.naver.com/search.naver?ssc=tab.cafe.all&query={qq}"),
        ("blog", "블로그 후기", f"https://search.naver.com/search.naver?ssc=tab.blog.all&query={qq}"),
        ("threads", "스레드 이야기", f"https://www.threads.com/search?q={qq}&serp_type=default"),
        ("insta", "인스타 #태그", f"https://www.instagram.com/explore/tags/{tag}/"),
        ("youtube", "유튜브 영상", f"https://www.youtube.com/results?search_query={qq}"),
        ("x", "X 실시간", f"https://x.com/search?q={qq}&f=live"),
    ]


GENERIC = re.compile(r"(지원사업|지원금|지원|사업|서비스|신청|지급|제도|운영|확대)+$")


def core_name(name):
    """후기 관련성 판정용 핵심어: '첫만남이용권 지원' → '첫만남이용권'"""
    s = clean_name(name).replace(" ", "")
    core = GENERIC.sub("", s) or s
    return core[:8]


def _strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


_OG = re.compile(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', re.I)


def og_image(url):
    """블로그 글의 대표 이미지(og:image). 링크 미리보기용으로 메타태그만 읽는다. 실패하면 ''."""
    if "blog.naver.com" in url and "m.blog.naver.com" not in url:
        url = url.replace("blog.naver.com", "m.blog.naver.com", 1)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (link preview)"})
        with urllib.request.urlopen(req, timeout=10) as r:
            head = r.read(200_000).decode("utf-8", "replace")
        m = _OG.search(head)
        img = html.unescape(m.group(1)) if m else ""
        return img if img.startswith("https://") else ""
    except Exception:  # noqa: BLE001 - 썸네일은 없어도 된다
        return ""


def _call(kind, query, cid, secret):
    url = API.format(kind=kind) + "?" + urllib.parse.urlencode({"query": query, "display": 10, "sort": "sim"})
    req = urllib.request.Request(url, headers={"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r).get("items", [])


def _relevant(item, core):
    text = f"{item['title']} {item['desc']}"
    return core in text.replace(" ", "") and ("후기" in text or "신청" in text or "받았" in text or "받은" in text)


def fetch(records, cache, cid, secret, today=None, limit=300):
    """인기 순 records 상위 limit 개의 후기를 갱신해 cache(dict)를 돌려준다."""
    today = today or date.today()
    calls = 0
    for r in records[:limit]:
        old = cache.get(r["id"])
        if old and (today - date.fromisoformat(old["fetched"])).days < REFRESH_DAYS:
            continue
        if calls + 2 > MAX_CALLS:
            break
        name = clean_name(r["name"])
        core = core_name(name)
        items = []
        try:
            for kind, src in (("blog", "블로그"), ("cafearticle", "카페")):
                calls += 1
                for it in _call(kind, f"{name} 후기", cid, secret):
                    item = {"src": src, "title": _strip(it.get("title")), "link": it.get("link", ""),
                            "desc": _strip(it.get("description"))[:120],
                            "by": _strip(it.get("bloggername") or it.get("cafename")),
                            "date": it.get("postdate", "")}
                    if item["link"].startswith("http") and _relevant(item, core):
                        items.append(item)
                time.sleep(0.12)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise RuntimeError("네이버 API 인증 실패 — NAVER_CLIENT_ID/SECRET 과 '검색' API 사용 설정을 확인하세요.") from e
            if e.code == 429:
                break
            continue
        items.sort(key=lambda x: x["date"], reverse=True)
        items = items[:6]
        for it in items:
            if it["src"] == "블로그":
                it["thumb"] = og_image(it["link"])
        cache[r["id"]] = {"fetched": today.isoformat(), "items": items}
    return cache, calls
