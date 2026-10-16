"""정규화 레코드 → 엄마 관점 정적 사이트(public/) 생성."""
import json
import math
import os
import re
import shutil
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup, escape

from .mom import STAGE_INFO, STAGES, format_won, is_monthly, max_amount, personal_amount, stages_for
from .normalize import SIDO, extract_region
from .reviews import search_links

ROOT = Path(__file__).resolve().parent.parent
PER_PAGE = 30
KST = timezone(timedelta(hours=9))
LOAN_RE = re.compile(r"(대출|융자|대부|보증|이자\s*지원)")
# 금액 순위에는 아이·가족 단계 혜택만 (살림 절약만 해당되는 건 제외)
FAMILY_STAGES = {"pre", "pregnancy", "birth", "infant", "elementary", "teen", "multichild", "singleparent", "working"}
SIDO_SHORT = {
    "서울특별시": "서울", "부산광역시": "부산", "대구광역시": "대구", "인천광역시": "인천",
    "광주광역시": "광주", "대전광역시": "대전", "울산광역시": "울산", "세종특별자치시": "세종",
    "경기도": "경기", "강원특별자치도": "강원", "충청북도": "충북", "충청남도": "충남",
    "전북특별자치도": "전북", "전라남도": "전남", "경상북도": "경북", "경상남도": "경남",
    "제주특별자치도": "제주", "전남광주통합특별시": "전남광주",
}
CENTRAL = ("중앙행정기관", "공공기관")


def today_kst():
    return datetime.now(KST).date()


BONUS_RE = re.compile(r"(출산|출생)\s*(장려|축하|지원|양육)\s*금")


def trend_keywords(trends):
    return [k for t in (trends or {}).get("topics", []) for k in t["keywords"]]


def enrich(records, extra_keywords=()):
    """엄마 관련 혜택(+트렌드 키워드에 걸리는 혜택)만 남기고 금액·단계 정보를 붙인다."""
    out = []
    for r in records:
        # 행정구역 개편 반영을 위해 지역은 빌드할 때 다시 뽑는다
        sido, sigungu = extract_region(r["org"])
        r = {**r, "sido": sido, "sigungu": sigungu}
        st = stages_for(r)
        if not st and not any(k in r["name"] for k in extra_keywords):
            continue
        amt = max_amount(r["content"])
        loan = bool(LOAN_RE.search(r["name"]))
        if loan or not personal_amount(r, amt):
            amt = None
        out.append({**r, "stages": st, "amount": amt, "loan": loan,
                    # 지역을 못 뽑았지만 지자체 소속 기관이면 '전국'으로 표시하지 않는다
                    "national": not r["sido"] and (r.get("org_type") or "중앙행정기관") in CENTRAL,
                    "amount_label": ("월 " if is_monthly(r["content"], amt) else "최대 ") + format_won(amt)
                    if amt else ""})
    return out


class Site:
    def __init__(self, records, events, out_dir, today=None, trends=None, clinics=None, views_history=None,
                 reviews=None, videos=None, channels=None):
        self.channels = channels or {"channels": []}
        self.reviews = reviews or {}
        self.videos = videos or {}
        self.views_history = views_history or {}
        self.trends = trends or {"topics": []}
        self.clinics = clinics or []
        self.records = enrich(records, trend_keywords(self.trends))
        self.by_id = {r["id"]: r for r in self.records}
        self.events = [e for e in events if e["id"] in self.by_id or e["type"] == "removed"]
        self.out = Path(out_dir)
        self.today = today or today_kst()
        self.base_url = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")
        self.base_path = os.environ.get("BASE_PATH", "").rstrip("/")
        self.site_name = os.environ.get("SITE_NAME", "엄마혜택노트")
        self.adsense = os.environ.get("ADSENSE_CLIENT", "")
        self.repo_url = os.environ.get("REPO_URL", "https://github.com/sontouf/mom-benefit-note")
        self.urls = []
        self.env = Environment(
            loader=FileSystemLoader(ROOT / "templates"),
            autoescape=select_autoescape(["html", "xml"]),
            trim_blocks=True, lstrip_blocks=True,
        )
        self.env.filters["text"] = _text_filter
        self.env.filters["comma"] = lambda n: f"{n:,}"
        self.env.globals.update(
            u=self.u, site_name=self.site_name, adsense=self.adsense, dday=self.dday,
            today=self.today, stages=STAGE_INFO, stage_list=[STAGE_INFO[s[0]] for s in STAGES],
            sido_short=SIDO_SHORT, site_root=self.base_url, repo_url=self.repo_url,
            google_verify=os.environ.get("GOOGLE_SITE_VERIFICATION", ""),
            naver_verify=os.environ.get("NAVER_SITE_VERIFICATION", ""),
            ga_id=os.environ.get("GA_ID", ""),
            counter_url=os.environ.get("COUNTER_URL", "").rstrip("/"),
        )

    # ---------- helpers ----------
    def u(self, path):
        return self.base_path + quote(path)

    def days_left(self, rec):
        if not rec["deadline_end"]:
            return None
        return (date.fromisoformat(rec["deadline_end"]) - self.today).days

    def is_open(self, rec):
        d = self.days_left(rec)
        return d is None or d >= 0

    def dday(self, rec):
        """(라벨, css클래스) 또는 None."""
        if rec["deadline_kind"] == "always":
            return ("상시 신청", "")
        if rec["deadline_kind"] == "budget":
            return ("예산 소진 시 마감", "")
        d = self.days_left(rec)
        if d is None:
            return None
        if d < 0:
            return ("마감", "closed")
        if d == 0:
            return ("오늘 마감", "hot")
        return (f"D-{d}", "hot" if d <= 7 else "")

    def write(self, path, template, sitemap=True, **ctx):
        target = self.out / path.lstrip("/")
        if path.endswith("/"):
            target = target / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        html = self.env.get_template(template).render(
            canonical=self.base_url + self.u(path), path=path, **ctx)
        target.write_text(html, encoding="utf-8")
        if sitemap:
            self.urls.append(path)

    def paginate(self, base, items, template, **ctx):
        pages = max(1, math.ceil(len(items) / PER_PAGE))
        for p in range(1, pages + 1):
            path = base if p == 1 else f"{base}page/{p}/"
            self.write(path, template, items=items[(p - 1) * PER_PAGE: p * PER_PAGE],
                       page=p, pages=pages, base=base, total=len(items), **ctx)

    def top_money(self, items, n):
        """금액이 확인되는 현금성 혜택을 금액 순으로 (대출 제외, 중앙부처 우선)."""
        xs = [r for r in items if r["amount"] and self.is_open(r) and FAMILY_STAGES & set(r["stages"])
              and not re.search(r"(체육인|북한이탈|보훈|장학)", r["name"])]
        return sorted(xs, key=lambda r: (-r["amount"], -r["views"]))[:n]

    # ---------- pages ----------
    def build(self):
        if self.out.exists():
            shutil.rmtree(self.out)
        self.out.mkdir(parents=True)
        shutil.copytree(ROOT / "static", self.out / "static")

        open_recs = [r for r in self.records if self.is_open(r)]
        national = [r for r in open_recs if r["national"]]
        by_stage = defaultdict(list)
        by_stage_sido = defaultdict(list)
        by_sido = defaultdict(list)
        by_sigungu = defaultdict(list)
        for r in open_recs:
            for s in r["stages"]:
                by_stage[s].append(r)
                if r["sido"]:
                    by_stage_sido[(s, r["sido"])].append(r)
            if r["sido"]:
                by_sido[r["sido"]].append(r)
                if r["sigungu"]:
                    by_sigungu[(r["sido"], r["sigungu"])].append(r)

        soon = sorted((r for r in open_recs if r["deadline_end"] and self.days_left(r) <= 30),
                      key=lambda r: (r["deadline_end"], -r["views"]))
        new_events = [e for e in self.events if e["type"] == "new" and e["id"] in self.by_id]
        stage_counts = {s: len(by_stage[s]) for s in STAGE_INFO}
        sidos = [(s, len(by_sido[s])) for s in SIDO if by_sido[s]]
        self.env.globals.update(stage_counts=stage_counts, sidos=sidos, has_clinics=True,
                                has_clinic_data=bool(self.clinics),
                                kid_channels=[c for c in self.channels.get("channels", []) if c["cat"] == "kids"])

        # 단계별 '꼭 챙길 것' = 전국 공통 혜택 중 많이 찾는 순
        must = {s: [r for r in national if s in r["stages"]][:8] for s in STAGE_INFO}

        rk = self.rankings(open_recs)
        self.env.globals["stats"] = {
            "total": len(open_recs), "soon": len(soon),
            "new_week": sum(1 for e in self.events if e["type"] == "new"
                            and (self.today - date.fromisoformat(e["date"])).days < 7),
            "regions": len(by_sigungu),
        }
        self.write("/ranking/", "ranking.html", rk=rk)
        self.write("/", "index.html", trends=self._build_trends(open_recs)[:6], rk=rk,
                   chans=self.channels.get("channels", []),
                   soon=soon[:6], soon_total=len(soon),
                   new=[self.by_id[e["id"]] for e in new_events[:6]],
                   money=self.top_money(national, 6),
                   popular=national[:6], total=len(open_recs))

        for rec in self.records:
            self.write(f"/s/{rec['id']}/", "service.html", r=rec, related=self._related(rec, by_stage),
                       review_links=search_links(rec["name"]),
                       review_items=self.reviews.get(rec["id"], {}).get("items", []),
                       video_items=self.videos.get(rec["id"], {}).get("items", []))

        for slug, info in STAGE_INFO.items():
            items = by_stage[slug]
            if not items:
                continue
            sub = [(sd, len(by_stage_sido[(slug, sd)])) for sd in SIDO if by_stage_sido[(slug, sd)]]
            self.paginate(f"/stage/{slug}/", items, "stage.html", info=info, must=must[slug],
                          money=self.top_money([r for r in items if r["national"]], 3), sub=sub, sido=None)
            for sd, _ in sub:
                local = by_stage_sido[(slug, sd)]
                # 지역 페이지 = 그 지역 혜택 + 전국 공통 상위 혜택
                self.paginate(f"/stage/{slug}/{sd}/", local, "stage.html", info=info,
                              must=must[slug][:4], money=self.top_money(local, 3), sub=sub, sido=sd)

        for sd, _ in sidos:
            items = by_sido[sd]
            subs = sorted((sg, len(v)) for (s, sg), v in by_sigungu.items() if s == sd)
            self.paginate(f"/region/{sd}/", items, "list.html",
                          title=f"{sd} 엄마·가족 지원금 총정리", heading=f"{sd} 우리 동네 혜택",
                          crumbs=[("지역별", "/region/")], subregions=subs, sido=sd,
                          desc=f"{sd}에서 임신·출산·육아·교육 가정이 받을 수 있는 지원금과 감면 혜택 {len(items):,}건.")
        for (sd, sg), items in by_sigungu.items():
            self.paginate(f"/region/{sd}/{sg}/", items, "list.html",
                          title=f"{sd} {sg} 출산·육아 지원금 총정리", heading=f"{sg} 우리 동네 혜택",
                          crumbs=[("지역별", "/region/"), (sd, f"/region/{sd}/")],
                          desc=f"{sd} {sg} 엄마들이 받을 수 있는 출산·육아·교육·살림 혜택 {len(items):,}건.")
        self.write("/region/", "regions.html",
                   sigungus={s: sorted((sg, len(v)) for (sd, sg), v in by_sigungu.items() if sd == s)
                             for s, _ in sidos})

        self.paginate("/deadline/", soon, "list.html",
                      title="마감 임박 육아·출산 지원금 (30일 이내)", heading="⏰ 마감 임박 혜택",
                      crumbs=[], sort_note="마감일이 가까운 순",
                      desc="신청 마감이 30일 이내로 다가온 엄마·가족 지원금. 매일 아침 자동 갱신됩니다.")

        trends = self._build_trends(open_recs)
        bonus = self._birth_bonus(open_recs)
        self.write("/trend/", "trends.html", trends=trends, bonus=bonus[:5])
        for t in trends:
            self.write(f"/trend/{t['slug']}/", "trend.html", t=t, checked=self.trends.get("checked"))
        if bonus:
            self.write("/trend/birth-bonus/", "bonus.html", bonus=bonus[:50], total=len(bonus))
        self.trend_cache, self.bonus_cache = trends, bonus

        self._build_clinics()
        chans = self.channels.get("channels", [])
        if chans:
            self.write("/youtube/", "youtube.html", chans=chans, checked=self.channels.get("checked"))

        self.write("/changes/", "changes.html", events=self._events_view(self.events[:300]))
        self.write("/find/", "find.html")
        self.write("/about/", "about.html")
        self.write("/privacy/", "privacy.html")
        self.write("/404.html", "404.html", sitemap=False)

        self._write_find_data(open_recs)
        self._write_rss(new_events, open_recs)
        if self.adsense:
            # AdSense 승인·수익 지급에 필요한 판매자 인증 파일
            pub = self.adsense.replace("ca-", "")
            (self.out / "ads.txt").write_text(f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8")
        self._write_sitemap()
        (self.out / "robots.txt").write_text(
            f"User-agent: *\nAllow: /\nSitemap: {self.base_url}{self.u('/sitemap.xml')}\n", encoding="utf-8")
        if os.environ.get("CNAME"):
            (self.out / "CNAME").write_text(os.environ["CNAME"] + "\n", encoding="utf-8")
        (self.out / ".nojekyll").write_text("", encoding="utf-8")
        return len(self.urls)

    def rankings(self, open_recs, n=50):
        """인기(누적 조회수) · 급상승(최근 며칠 조회수 증가) · 신규."""
        family = [r for r in open_recs if r["stages"]]
        popular = family[:n]
        hot, window = [], 0
        dates = sorted(self.views_history)
        if len(dates) >= 2:
            latest = self.views_history[dates[-1]]
            base_date = dates[max(0, len(dates) - 8)]  # 최대 7일 전과 비교
            base = self.views_history[base_date]
            window = (date.fromisoformat(dates[-1]) - date.fromisoformat(base_date)).days
            for r in family:
                if r["id"] in base and r["id"] in latest:
                    delta = latest[r["id"]] - base[r["id"]]
                    if delta > 0:
                        hot.append({**r, "delta": delta})
            hot.sort(key=lambda r: -r["delta"])
            hot = hot[:n]
        new = [self.by_id[e["id"]] for e in self.events if e["type"] == "new" and e["id"] in self.by_id][:n]
        if not new:  # 이력이 쌓이기 전에는 최근 수정된 혜택
            new = sorted((r for r in family if r["modified"]), key=lambda r: r["modified"], reverse=True)[:n]
        top = max([r["views"] for r in popular] or [1])
        top_hot = max([r["delta"] for r in hot] or [1])
        return {"popular": popular, "hot": hot, "new": new, "window": window,
                "top_views": top, "top_delta": top_hot, "new_is_events": bool(self.events)}

    def _build_clinics(self):
        if not self.clinics:
            # 병·의원 데이터가 없어도 '아이가 아플 때' 공식 안내 페이지는 항상 제공한다
            docs = [c for c in self.channels.get("channels", []) if c["cat"] == "parent"][:4]
            self.write("/clinic/", "clinic_guide.html", docs=docs)
            return
        by_sido = defaultdict(list)
        for c in self.clinics:
            by_sido[c["sido"]].append(c)
        counts = [(s, len(by_sido[s]), sum(c["sun"] or c["hol"] for c in by_sido[s])) for s in SIDO if by_sido[s]]
        self.write("/clinic/", "clinic.html", sido=None, counts=counts, groups=[], total=len(self.clinics))
        for sd, _, _ in counts:
            groups = defaultdict(list)
            for c in by_sido[sd]:
                groups[c["sigungu"] or "기타"].append(c)
            self.write(f"/clinic/{sd}/", "clinic.html", sido=sd, counts=counts,
                       groups=sorted(groups.items()), total=len(by_sido[sd]))

    def _build_trends(self, open_recs):
        out = []
        for t in self.trends.get("topics", []):
            items = [r for r in open_recs if not r["loan"] and any(k in r["name"] for k in t["keywords"])]
            items.sort(key=lambda r: (not r["national"], -r["views"]))
            out.append({**t, "items": items[:12], "count": len(items)})
        return out

    def _birth_bonus(self, open_recs):
        """시군구 출산축하금(장려금) 금액 순위 — 공공데이터로 만든 고유 콘텐츠."""
        best = {}
        for r in open_recs:
            if r["sigungu"] and r["amount"] and BONUS_RE.search(r["name"]):
                key = (r["sido"], r["sigungu"])
                if key not in best or r["amount"] > best[key]["amount"]:
                    best[key] = r
        return sorted(best.values(), key=lambda r: (-r["amount"], -r["views"]))

    def _related(self, rec, by_stage, n=6):
        out, seen = [], {rec["id"]}
        for s in rec["stages"]:
            for r in by_stage[s]:
                if r["id"] not in seen and (r["national"] or (r["sido"] and r["sido"] == rec["sido"])):
                    out.append(r)
                    seen.add(r["id"])
                    if len(out) == n:
                        return out
        return out

    def _events_view(self, events):
        grouped = defaultdict(list)
        for e in events:
            grouped[e["date"]].append({**e, "rec": self.by_id.get(e["id"])})
        return sorted(grouped.items(), reverse=True)

    def _write_find_data(self, recs):
        incomes = ("JA0201", "JA0202", "JA0203", "JA0204", "JA0205")
        rows = []
        for r in recs:
            inc = [c for c in r["cond"].get("y", []) if c in incomes]
            rows.append([r["id"], r["name"], r["sido"] or "", r["sigungu"] or "", r["stages"],
                         r["amount_label"], r["views"], r["deadline_end"] or "",
                         r["summary"][:70], inc if len(inc) < 5 else []])
        (self.out / "static" / "find.json").write_text(
            json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    def _write_rss(self, new_events, open_recs):
        """새 혜택 RSS. 네이버 서치어드바이저에 RSS 로 제출하면 수집이 빨라진다."""
        items = [(self.by_id[e["id"]], e["date"]) for e in new_events[:50]]
        if len(items) < 20:  # 신규 이력이 적은 초기엔 최근 수정된 혜택으로 채운다
            seen = {r["id"] for r, _ in items}
            recent = sorted((r for r in open_recs if r["id"] not in seen and r["modified"]),
                            key=lambda r: r["modified"], reverse=True)
            items += [(r, None) for r in recent[:50 - len(items)]]

        def pub(r, d):
            raw = d or r["modified"][:8]
            try:
                dt = datetime.strptime(raw.replace("-", "")[:8], "%Y%m%d")
            except ValueError:
                dt = datetime.combine(self.today, datetime.min.time())
            return dt.strftime("%a, %d %b %Y 06:00:00 +0900")

        body = "".join(
            f"<item><title>{escape(r['name'] + (' ' + r['amount_label'] if r['amount_label'] else ''))}</title>"
            f"<link>{escape(self.base_url + self.u('/s/' + r['id'] + '/'))}</link>"
            f"<guid>{escape(self.base_url + self.u('/s/' + r['id'] + '/'))}</guid>"
            f"<description>{escape(r['summary'])}</description><pubDate>{pub(r, d)}</pubDate></item>"
            for r, d in items)
        (self.out / "rss.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel>'
            f"<title>{escape(self.site_name)} 새 혜택</title><link>{escape(self.base_url + self.u('/'))}</link>"
            "<description>임신·출산·육아 지원금 신규·변경 소식</description><language>ko</language>"
            f"{body}</channel></rss>\n", encoding="utf-8")

    def _write_sitemap(self):
        chunk = 40000
        parts = [self.urls[i:i + chunk] for i in range(0, len(self.urls), chunk)]
        lastmod = self.today.isoformat()
        names = []
        for i, part in enumerate(parts, 1):
            name = f"sitemap-{i}.xml"
            names.append(name)
            body = "".join(f"<url><loc>{escape(self.base_url + self.u(p))}</loc><lastmod>{lastmod}</lastmod></url>"
                           for p in part)
            (self.out / name).write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{body}</urlset>\n', encoding="utf-8")
        idx = "".join(f"<sitemap><loc>{self.base_url}{self.u('/' + n)}</loc><lastmod>{lastmod}</lastmod></sitemap>"
                      for n in names)
        (self.out / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{idx}</sitemapindex>\n',
            encoding="utf-8")


_BULLET_RE = re.compile(r"^\s*([○●◦•ㅇ▶▷■□◎※\-]|\d+[.)])\s*")


def _text_filter(value):
    """공공데이터 자유 텍스트 → 안전한 HTML (줄바꿈·글머리 유지)."""
    if not value:
        return ""
    parts = []
    for ln in str(value).split("\n"):
        if not ln.strip():
            continue
        cls = "li" if _BULLET_RE.match(ln) else "p"
        parts.append(Markup('<span class="{}">{}</span>').format(cls, ln.strip()))
    return Markup("<br>").join(parts)
