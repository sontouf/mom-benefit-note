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

from hyetaek import api, history, threads
from hyetaek.build import Site, today_kst
from hyetaek.normalize import build_records

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
SERVICES = DATA / "services.json"
EVENTS = DATA / "events.json"


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
        for ep in api.ENDPOINTS:
            raw[ep] = api.fetch_all(ep, key)
            print(f"  {ep}: {len(raw[ep]):,}건")

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
    counts = {t: sum(e["type"] == t for e in events) for t in ("new", "updated", "removed")}
    print(f"서비스 {len(records):,}건 저장 · 신규 {counts['new']} / 변경 {counts['updated']} / 종료 {counts['removed']}")


def build(out, cards=False):
    records = _load(SERVICES, None)
    if records is None:
        sys.exit("data/services.json 이 없습니다. 먼저 fetch 를 실행하세요.")
    records.sort(key=lambda r: (-r["views"], r["id"]))
    site = Site(records, _load(EVENTS, []), out, trends=_load(DATA / "trends.json", None))
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
