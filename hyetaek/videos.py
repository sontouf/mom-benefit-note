"""혜택별 관련 유튜브 영상 (YouTube Data API v3, YOUTUBE_API_KEY 가 있을 때만).

search.list 는 1회 100 유닛, 하루 무료 할당량은 10,000 유닛이다.
그래서 하루 최대 90회만 부르고(9,000 유닛), 인기 혜택부터 14일마다 돌아가며 갱신한다.
영상 자체는 복제하지 않고 썸네일·제목·채널과 YouTube 임베드(youtube-nocookie)만 쓴다.
"""
import html
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

from .reviews import clean_name, core_name

API = "https://www.googleapis.com/youtube/v3/search"
REFRESH_DAYS = 14
MAX_CALLS = 90


def _call(query, key):
    params = {"part": "snippet", "q": query, "type": "video", "maxResults": 8, "regionCode": "KR",
              "relevanceLanguage": "ko", "safeSearch": "strict", "key": key}
    with urllib.request.urlopen(API + "?" + urllib.parse.urlencode(params), timeout=30) as r:
        return json.load(r).get("items", [])


def fetch(records, cache, key, today=None, limit=400):
    today = today or date.today()
    calls = 0
    for r in records[:limit]:
        old = cache.get(r["id"])
        if old and (today - date.fromisoformat(old["fetched"])).days < REFRESH_DAYS:
            continue
        if calls >= MAX_CALLS:
            break
        core = core_name(r["name"])
        try:
            calls += 1
            items = _call(f"{clean_name(r['name'])} 신청 방법", key)
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403):
                body = e.read().decode("utf-8", "replace")
                if "quota" in body.lower():
                    break
                raise RuntimeError(f"YouTube API 오류 {e.code} — YOUTUBE_API_KEY 와 'YouTube Data API v3' 사용 설정을 확인하세요.") from e
            continue
        vids = []
        for it in items:
            sn, vid = it.get("snippet", {}), it.get("id", {}).get("videoId")
            title = html.unescape(sn.get("title", ""))
            if not vid or core not in title.replace(" ", ""):
                continue
            vids.append({"id": vid, "title": title, "channel": html.unescape(sn.get("channelTitle", "")),
                         "date": (sn.get("publishedAt") or "")[:10]})
        vids.sort(key=lambda v: v["date"], reverse=True)
        cache[r["id"]] = {"fetched": today.isoformat(), "items": vids[:4]}
    return cache, calls
