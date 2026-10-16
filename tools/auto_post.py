"""스레드 자동 게시 (하루 1개). GitHub Actions 의 threads-post 워크플로가 매일 저녁 실행한다.

  THREADS_USER_ID, THREADS_TOKEN 환경변수가 있어야 하고, 없으면 아무것도 하지 않는다.
  SITE_URL 의 /cards/{오늘}/drafts.json 을 읽어, 최근 7일 안에 올리지 않은 주제 중 우선순위가 가장 높은 것 1개만 올린다.
  게시 기록은 data/threads_posted.json 에 남긴다 (중복·도배 방지).
"""
import json
import os
import sys
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import post_threads  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "threads_posted.json"
PRIORITY = ["trend-", "birth-bonus", "deadline", "stage-"]  # 위에서부터 우선
COOLDOWN_DAYS = 7


def today_kst():
    return datetime.now(timezone(timedelta(hours=9))).date()


def pick(drafts, log, today):
    recent = {e["key"] for e in log if (today - date.fromisoformat(e["date"])).days < COOLDOWN_DAYS}
    if any(e["date"] == today.isoformat() for e in log):
        return None  # 하루 1개
    for prefix in PRIORITY:
        for d in drafts:
            if d["key"].startswith(prefix) and d["key"] not in recent:
                return d
    return None


def check_token_age(today):
    """장기 토큰은 60일 유효. 발급일(THREADS_TOKEN_ISSUED)로부터 50일이 지나면 매일 경고한다."""
    issued = os.environ.get("THREADS_TOKEN_ISSUED")
    if not issued:
        return
    left = 60 - (today - date.fromisoformat(issued)).days
    print(f"스레드 토큰: 약 {left}일 남음")
    if left <= 10:
        print(f"::warning title=스레드 토큰 만료 임박::{left}일 남았어요. 토큰을 연장해 THREADS_TOKEN 과 THREADS_TOKEN_ISSUED 를 갱신하세요.")


def main():
    if not (os.environ.get("THREADS_USER_ID") and os.environ.get("THREADS_TOKEN")):
        print("THREADS_USER_ID/THREADS_TOKEN 없음 — 게시하지 않음")
        return
    if "--check" in sys.argv:  # 게시 없이 토큰만 점검
        me = post_threads.call("GET", "me", fields="id,username")
        print(f"토큰 정상: @{me.get('username')} (id {me.get('id')})")
        check_token_age(today_kst())
        return
    site = os.environ.get("SITE_URL", "https://mombenefit.co.kr").rstrip("/")
    today = today_kst()
    try:
        with urllib.request.urlopen(f"{site}/cards/{today.isoformat()}/drafts.json", timeout=30) as r:
            drafts = json.load(r)
    except Exception as e:  # noqa: BLE001
        print(f"::warning title=오늘 카드뉴스 없음::{e}")
        return
    log = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else []
    d = pick(drafts, log, today)
    if not d:
        print("오늘 올릴 새 주제가 없거나 이미 게시함 — 건너뜀")
        return
    if [u for u in d["images"] if not post_threads.reachable(u)]:
        print("::warning title=카드 이미지 접근 불가::오늘은 게시하지 않아요.")
        return
    check_token_age(today)
    pid, link = post_threads.publish(os.environ["THREADS_USER_ID"], d)
    print(f"게시 완료: {d['key']} → {link or pid}")
    log.insert(0, {"date": today.isoformat(), "key": d["key"], "id": pid, "url": link})
    LOG.write_text(json.dumps(log[:200], ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
