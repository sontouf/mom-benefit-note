"""혜택레이더 파이프라인.

  python run.py fetch            # API 수집 → data/ 갱신 (DATA_GO_KR_KEY 필요)
  python run.py fetch --sample   # sample/ 의 예시 데이터로 수집 단계 흉내
  python run.py build            # data/ → public/ 정적 사이트 생성
  python run.py all [--sample]   # fetch + build + 스레드 카드
  python run.py cards            # build + 스레드 게시글 초안·카드뉴스(drafts/, public/cards/)
"""
import argparse
import json
import os
import sys
from pathlib import Path

from hyetaek import api, clinic, history, reviews, threads, videos
from hyetaek.mom import stages_for
from hyetaek.build import Site, today_kst
from hyetaek.normalize import build_records

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SERVICES = DATA / "services.json"
EVENTS = DATA / "events.json"
CLINICS = DATA / "clinics.json"
VIEWS = DATA / "views_history.json"
REVIEWS = DATA / "reviews.json"
VIDEOS = DATA / "videos.json"
VIEW_DAYS = 8  # 급상승 계산용 조회수 스냅샷 보관 일수


def _dump_lines(path, items):
    """한 줄에 레코드 하나 → git diff 가 변경분만 보여준다."""
    body = ",\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in items)
    path.write_text("[\n" + body + "\n]\n", encoding="utf-8")


def _load(path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def fetch(sample=False):
    if sample:
        raw = {ep: json.loads((ROOT / "sample" / f"{ep}.json").read_text(encoding="utf-8"))
               for ep in api.ENDPOINTS}
    else:
        key = os.environ.get("DATA_GO_KR_KEY")
        if not key:
            sys.exit("DATA_GO_KR_KEY 환경변수가 없습니다. 공공데이터포털 '일반 인증키(Decoding)'를 넣어주세요.")
        raw = {}
        try:
            for ep in api.ENDPOINTS:
                raw[ep] = api.fetch_all(ep, key)
                print(f"  {ep}: {len(raw[ep]):,}건")
        except api.ApiError as e:
            # 혜택 API 장애·키 문제여도 사이트는 어제 데이터로 계속 배포한다 (GitHub 에 경고 표시)
            msg = " ".join(str(e).split())
            print(f"::warning title=공공서비스 API 실패::{msg} — 어제 데이터로 계속 진행합니다. 인증키를 확인하세요.")
            fetch_extras(_load(SERVICES, []), sample)
            return
    records = build_records(raw["serviceList"], raw["serviceDetail"], raw["supportConditions"])
    if not records:
        sys.exit("수집 결과가 0건입니다. 기존 데이터를 보존하고 중단합니다.")
    prev = _load(SERVICES, None)
    if prev and len(records) < len(prev) * 0.8:
        # API 장애로 일부만 받아진 경우 대량 '종료' 이벤트가 생기는 것을 막는다.
        sys.exit(f"수집 건수가 급감했습니다 ({len(prev):,} → {len(records):,}). 중단합니다.")

    events = history.diff(prev, records, today_kst().isoformat())
    DATA.mkdir(exist_ok=True)
    _dump_lines(SERVICES, sorted(records, key=lambda r: r["id"]))
    _dump_lines(EVENTS, history.merge(_load(EVENTS, []), events))
    _save_views(records)
    counts = {t: sum(e["type"] == t for e in events) for t in ("new", "updated", "removed")}
    print(f"서비스 {len(records):,}건 저장 · 신규 {counts['new']} / 변경 {counts['updated']} / 종료 {counts['removed']}")
    fetch_extras(records, sample)


def fetch_extras(records, sample=False):
    """부가 데이터(소아과·후기·영상). 각각 실패해도 서로 막지 않는다."""
    fetch_clinics(sample)
    if not sample:
        fetch_reviews(records)
        fetch_videos(records)


def _family(records):
    return sorted((r for r in records if stages_for(r)), key=lambda r: -r["views"])


def fetch_reviews(records):
    """네이버 블로그·카페 후기 (NAVER_CLIENT_ID/SECRET 이 있을 때만). 인기 혜택부터 7일마다 갱신."""
    cid, secret = os.environ.get("NAVER_CLIENT_ID"), os.environ.get("NAVER_CLIENT_SECRET")
    if not (cid and secret):
        print("  후기: 건너뜀 — NAVER_CLIENT_ID/SECRET 없음 (검색 링크만 표시)")
        return
    try:
        cache, calls = reviews.fetch(_family(records), _load(REVIEWS, {}), cid, secret, today_kst())
    except RuntimeError as e:
        print(f"::warning title=네이버 후기 수집 실패::{e}")
        return
    REVIEWS.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    print(f"  후기: API {calls}회 호출 · 후기 있는 혜택 {sum(1 for v in cache.values() if v['items'])}개")


def fetch_videos(records):
    """관련 유튜브 영상 (YOUTUBE_API_KEY 가 있을 때만). 하루 할당량 안에서 인기 혜택부터 14일마다 갱신."""
    key = os.environ.get("YOUTUBE_API_KEY")
    if not key:
        print("  영상: 건너뜀 — YOUTUBE_API_KEY 없음 (유튜브 검색 링크만 표시)")
        return
    try:
        cache, calls = videos.fetch(_family(records), _load(VIDEOS, {}), key, today_kst())
    except RuntimeError as e:
        print(f"::warning title=유튜브 영상 수집 실패::{e}")
        return
    VIDEOS.write_text(json.dumps(cache, ensure_ascii=False, indent=0, sort_keys=True), encoding="utf-8")
    print(f"  영상: API {calls}회 호출 · 영상 있는 혜택 {sum(1 for v in cache.values() if v['items'])}개")


def _save_views(records):
    """날짜별 정부24 조회수 스냅샷. 며칠 사이 증가분으로 '요즘 뜨는 혜택'을 계산한다."""
    hist = _load(VIEWS, {})
    hist[today_kst().isoformat()] = {r["id"]: r["views"] for r in records}
    keep = sorted(hist)[-VIEW_DAYS:]
    body = ",\n".join(f"{json.dumps(d)}: {json.dumps(hist[d], separators=(',', ':'), sort_keys=True)}" for d in keep)
    VIEWS.write_text("{\n" + body + "\n}\n", encoding="utf-8")


def fetch_clinics(sample=False):
    """밤·주말 소아과. 활용신청 전이거나 장애면 기존 데이터를 유지하고 넘어간다."""
    try:
        if sample:
            _, items = clinic.parse((ROOT / "sample" / "clinics.xml").read_bytes())
        else:
            items = clinic.fetch_all(os.environ["DATA_GO_KR_KEY"])
    except clinic.NotRegistered as e:
        print(f"  소아과: 건너뜀 — {e}")
        return
    except Exception as e:  # noqa: BLE001 - 부가 기능이라 본 파이프라인을 막지 않는다
        print(f"  소아과: 건너뜀 — {e}")
        return
    rows = clinic.normalize(items)
    if rows:
        _dump_lines(CLINICS, rows)
    print(f"  소아과: 전체 {len(items):,}곳 중 밤·주말 진료 {len(rows):,}곳 저장")


def build(out, cards=False):
    records = _load(SERVICES, None)
    if records is None:
        sys.exit("data/services.json 이 없습니다. 먼저 fetch 를 실행하세요.")
    records.sort(key=lambda r: (-r["views"], r["id"]))
    site = Site(records, _load(EVENTS, []), out, trends=_load(DATA / "trends.json", None),
                clinics=_load(CLINICS, []), views_history=_load(VIEWS, {}), reviews=_load(REVIEWS, {}),
                videos=_load(VIDEOS, {}), channels=_load(DATA / "channels.json", {}))
    n = site.build()
    print(f"페이지 {n:,}개 생성 → {out}")
    if cards:
        path, count, rendered = threads.generate(site, ROOT / "drafts")
        print(f"스레드 초안 {count}개 → {path}" + ("" if rendered else " (Chrome 없음: 이미지 생략)"))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["fetch", "build", "cards", "all"])
    p.add_argument("--sample", action="store_true")
    p.add_argument("--out", default=str(ROOT / "public"))
    a = p.parse_args()
    if a.cmd in ("fetch", "all"):
        fetch(a.sample)
    if a.cmd in ("build", "cards", "all"):
        build(a.out, cards=a.cmd in ("cards", "all"))


if __name__ == "__main__":
    main()
