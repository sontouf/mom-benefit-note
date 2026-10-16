"""검수한 스레드 초안 하나를 Threads API로 게시한다 (카드 캐러셀 + 첫 댓글).

  export THREADS_USER_ID=...  THREADS_TOKEN=...   # Meta 개발자 앱에서 발급한 장기 토큰
  python tools/post_threads.py drafts/2026-10-17.json --list
  python tools/post_threads.py drafts/2026-10-17.json --key birth-bonus

- 매번 본문·댓글·이미지를 보여주고 'y' 를 입력해야 게시한다. 자동 대량 게시는 일부러 지원하지 않는다.
- 이미지는 공개 URL이어야 한다(배포된 사이트의 /cards/...). 게시 전에 접근 가능한지 확인한다.
- 게시 순서: 이미지 컨테이너(캐러셀 아이템) → 캐러셀 컨테이너 → 게시 → 첫 댓글(링크·출처) 게시
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://graph.threads.net/v1.0"


def call(method, path, **params):
    params["access_token"] = os.environ["THREADS_TOKEN"]
    data = urllib.parse.urlencode(params).encode()
    url = f"{API}/{path}"
    req = urllib.request.Request(url + ("?" + data.decode() if method == "GET" else ""),
                                 data=None if method == "GET" else data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"Threads API 오류 {e.code}: {e.read().decode('utf-8', 'replace')}")


def wait_ready(container_id, tries=20):
    for _ in range(tries):
        status = call("GET", container_id, fields="status,error_message")
        if status.get("status") == "FINISHED":
            return
        if status.get("status") in ("ERROR", "EXPIRED"):
            sys.exit(f"컨테이너 처리 실패: {status}")
        time.sleep(3)
    sys.exit("컨테이너 처리 대기 시간 초과")


def reachable(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=20) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def publish(user, draft):
    images = draft["images"][:20]  # 캐러셀 최대 20장
    children = []
    for url in images:
        c = call("POST", f"{user}/threads", media_type="IMAGE", image_url=url, is_carousel_item="true")
        children.append(c["id"])
    for cid in children:
        wait_ready(cid)
    carousel = call("POST", f"{user}/threads", media_type="CAROUSEL",
                    children=",".join(children), text=draft["text"])
    wait_ready(carousel["id"])
    post = call("POST", f"{user}/threads_publish", creation_id=carousel["id"])
    reply = call("POST", f"{user}/threads", media_type="TEXT", text=draft["reply"], reply_to_id=post["id"])
    wait_ready(reply["id"])
    call("POST", f"{user}/threads_publish", creation_id=reply["id"])
    link = call("GET", post["id"], fields="permalink").get("permalink")
    return post["id"], link


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drafts")
    ap.add_argument("--key", help="게시할 초안 key (예: birth-bonus)")
    ap.add_argument("--list", action="store_true", help="초안 목록만 보기")
    a = ap.parse_args()
    drafts = json.load(open(a.drafts, encoding="utf-8"))

    if a.list or not a.key:
        for d in drafts:
            print(f"- {d['key']}: {d['text'].splitlines()[0]}")
        return
    draft = next((d for d in drafts if d["key"] == a.key), None)
    if not draft:
        sys.exit(f"'{a.key}' 초안이 없습니다. --list 로 확인하세요.")
    for k in ("THREADS_USER_ID", "THREADS_TOKEN"):
        if not os.environ.get(k):
            sys.exit(f"{k} 환경변수가 필요합니다.")

    print("=" * 60, "\n[본문]\n" + draft["text"], "\n\n[첫 댓글]\n" + draft["reply"], "\n\n[이미지]")
    missing = [u for u in draft["images"] if not reachable(u)]
    for u in draft["images"]:
        print(("  ✗ " if u in missing else "  ✓ ") + u)
    if missing:
        sys.exit("접근할 수 없는 이미지가 있습니다. 사이트가 배포된 뒤(SITE_URL 설정 포함) 다시 시도하세요.")
    if input("\n이대로 게시할까요? (y/N) ").strip().lower() != "y":
        print("취소했습니다.")
        return
    pid, link = publish(os.environ["THREADS_USER_ID"], draft)
    print(f"게시 완료: {link or pid}")


if __name__ == "__main__":
    main()
