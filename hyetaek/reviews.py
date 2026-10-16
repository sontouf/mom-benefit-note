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


API_HUB = "https://naverapihub.apigw.ntruss.com/search/v1/{kind}"
KAKAO = "https://dapi.kakao.com/v2/search/{kind}"


def _http_json(url, headers):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
        return json.load(r)


def _call(kind, query, cid, secret):
    """네이버 검색. cid 가 'hub:' 로 시작하면 NAVER API HUB(2026.8~ 신규 발급 키), 아니면 기존 개발자센터 키."""
    if cid.startswith("hub:"):
        url = API_HUB.format(kind=kind) + "?" + urllib.parse.urlencode(
            {"query": query, "display": 10, "sort": "sim", "format": "json"})
        return _http_json(url, {"X-NCP-APIGW-API-KEY-ID": cid[4:], "X-NCP-APIGW-API-KEY": secret}).get("items", [])
    url = API.format(kind=kind) + "?" + urllib.parse.urlencode({"query": query, "display": 10, "sort": "sim"})
    return _http_json(url, {"X-Naver-Client-Id": cid, "X-Naver-Client-Secret": secret}).get("items", [])


def _kakao(kind, query, key):
    """카카오(다음) 블로그·카페 검색. 결과에 썸네일이 들어 있다."""
    url = KAKAO.format(kind=kind) + "?" + urllib.parse.urlencode({"query": query, "size": 10, "sort": "accuracy"})
    docs = _http_json(url, {"Authorization": f"KakaoAK {key}"}).get("documents", [])
    out = []
    for d in docs:
        out.append({"title": d.get("title", ""), "link": d.get("url", ""), "description": d.get("contents", ""),
                    "bloggername": d.get("blogname") or d.get("cafename") or "",
                    "postdate": (d.get("datetime") or "")[:10].replace("-", ""),
                    "thumbnail": d.get("thumbnail", "")})
    return out


def _relevant(item, core):
    text = f"{item['title']} {item['desc']}"
    return core in text.replace(" ", "") and ("후기" in text or "신청" in text or "받았" in text or "받은" in text)


def fetch(records, cache, cid, secret, today=None, limit=300, kakao_key=None):
    """인기 순 records 상위 limit 개의 후기를 갱신해 cache(dict)를 돌려준다.

    cid/secret: 네이버(개발자센터 또는 'hub:'+API HUB 키). kakao_key: 카카오 REST API 키. 둘 중 있는 것만 쓴다.
    """
    today = today or date.today()
    calls = 0
    sources = []
    if cid and secret:
        sources += [("naver", "blog", "블로그"), ("naver", "cafearticle", "카페")]
    if kakao_key:
        sources += [("kakao", "blog", "블로그"), ("kakao", "cafe", "카페")]
    for r in records[:limit]:
        old = cache.get(r["id"])
        if old and (today - date.fromisoformat(old["fetched"])).days < REFRESH_DAYS:
            continue
        if calls + len(sources) > MAX_CALLS:
            break
        name = clean_name(r["name"])
        core = core_name(name)
        items, seen = [], set()
        for prov, kind, src in sources:
            calls += 1
            try:
                raw = _call(kind, f"{name} 후기", cid, secret) if prov == "naver" else _kakao(kind, f"{name} 후기", kakao_key)
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    raise RuntimeError(f"{'네이버' if prov == 'naver' else '카카오'} API 인증 실패 ({e.code}) — 키와 사용 설정을 확인하세요.") from e
                if e.code == 429:
                    return cache, calls
                continue
            except (urllib.error.URLError, TimeoutError):
                continue
            for it in raw:
                item = {"src": src, "title": _strip(it.get("title")), "link": it.get("link", ""),
                        "desc": _strip(it.get("description"))[:120],
                        "by": _strip(it.get("bloggername") or it.get("cafename")),
                        "date": it.get("postdate", "")}
                if it.get("thumbnail", "").startswith("http"):
                    item["thumb"] = it["thumbnail"].replace("http://", "https://", 1)
                if item["link"].startswith("http") and item["link"] not in seen and _relevant(item, core):
                    seen.add(item["link"])
                    items.append(item)
            time.sleep(0.12)
        items.sort(key=lambda x: x["date"], reverse=True)
        items = items[:6]
        for it in items:
            if it["src"] == "블로그" and not it.get("thumb"):
                it["thumb"] = og_image(it["link"])
        cache[r["id"]] = {"fetched": today.isoformat(), "items": items}
    return cache, calls
