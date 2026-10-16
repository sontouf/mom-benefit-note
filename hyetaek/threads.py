"""스레드 게시글 초안 + 카드뉴스(1080×1350 PNG) 자동 생성.

스레드에서 반응 좋은 형식(DESIGN.md §1·§6)을 따른다:
  - 숫자로 시작하는 훅, '신청 안 하면 0원'
  - 카드 4~6장: 표지 → 혜택 1장씩 → 저장 유도
  - 링크는 본문이 아니라 첫 댓글(답글)에 (외부 링크가 본문에 있으면 노출이 줄어든다는 게 통설)

이미지는 headless Chrome 으로 HTML 템플릿을 그대로 캡처한다. 그래서 웹과 카드가 같은 디자인 토큰을 쓴다.
게시는 하지 않는다. 사람이 검수한 뒤 올리는 것을 전제로 drafts/ 에 저장한다.
"""
import glob
import json
import os
import shutil
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
FAMILY = ("pre", "pregnancy", "birth", "infant", "elementary", "teen", "multichild", "singleparent", "working")


def find_chrome():
    cands = [os.environ.get("CHROME_BIN"), shutil.which("google-chrome"), shutil.which("chromium"),
             shutil.which("chromium-browser")]
    cands += sorted(glob.glob(os.path.expanduser(
        "~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell")))
    for c in cands:
        if c and os.path.exists(c):
            return c
    return None


def _where(site, r):
    if r["sido"]:
        return f"{site.env.globals['sido_short'].get(r['sido'], r['sido'])} {r['sigungu'] or ''}".strip()
    return "전국" if r["national"] else r["org"]


def plan_posts(site):
    """오늘 올릴 만한 게시글 후보들. site 는 build() 를 마친 Site."""
    today = site.today
    posts = []

    trends = [t for t in site.trend_cache if len(t["items"]) >= 3]
    if trends:
        t = trends[today.toordinal() % len(trends)]
        items = sorted(t["items"][:8], key=lambda r: (not r["amount_label"], -r["views"]))[:4]
        posts.append({
            "key": f"trend-{t['slug']}", "icon": t["icon"],
            "eyebrow": t["hook"], "headline": t["title"],
            "sub": "엄마들 사이에서 요즘 제일 많이 이야기되는 주제",
            "items": items, "link": site.base_url + site.u(f"/trend/{t['slug']}/"),
            "hook": f"{t['title']}\n{t['hook']}",
            "quote": t["threads"][0] if t["threads"] else None,
        })

    bonus = site.bonus_cache[:4]
    if len(bonus) >= 3:
        posts.append({
            "key": "birth-bonus", "icon": "trophy",
            "eyebrow": "공공데이터로 직접 집계", "headline": "출산축하금<br><span class='accent'>가장 많이 주는</span> 동네",
            "sub": f"전국 {len(site.bonus_cache)}개 시군구 비교 · 1위 {bonus[0]['amount_label']}",
            "items": bonus, "link": site.base_url + site.u("/trend/birth-bonus/"),
            "hook": f"우리 동네 출산축하금은 전국 몇 등일까요?\n1위는 {bonus[0]['sigungu']} {bonus[0]['amount_label']}",
        })

    soon = sorted((r for r in site.records if r["deadline_end"] and site.is_open(r)
                   and site.days_left(r) <= 14 and set(r["stages"]) & set(FAMILY)),
                  key=lambda r: (-bool(r["amount_label"]), site.days_left(r), -r["views"]))[:4]
    if len(soon) >= 2:
        posts.append({
            "key": "deadline", "icon": "clock",
            "eyebrow": "2주 안에 마감", "headline": f"놓치면 끝나는<br>혜택 <span class='accent'>{len(soon)}가지</span>",
            "sub": "마감 전에 꼭 신청하세요", "items": soon,
            "link": site.base_url + site.u("/deadline/"),
            "hook": f"2주 안에 마감되는 엄마 혜택 {len(soon)}가지\n놓치면 내년까지 기다려야 해요",
        })

    stages = [s for s in FAMILY if site.env.globals["stage_counts"].get(s)]
    if stages:
        slug = stages[today.toordinal() % len(stages)]
        info = site.env.globals["stages"][slug]
        items = site.top_money([r for r in site.records if r["national"] and slug in r["stages"]], 4)
        if len(items) >= 3:
            posts.append({
                "key": f"stage-{slug}", "icon": slug,
                "eyebrow": "신청 안 하면 0원", "headline": f"{info['name']}<br>받을 수 있는 돈 <span class='accent'>TOP {len(items)}</span>",
                "sub": info["desc"], "items": items,
                "link": site.base_url + site.u(f"/stage/{slug}/"),
                "hook": f"{info['name']} 가정이 받을 수 있는 돈 TOP {len(items)}\n대부분 신청해야 받아요",
            })
    for p in posts:
        p["text"], p["reply"] = _compose(p, site)
    return posts


def _compose(p, site):
    lines = [p["hook"], ""]
    for i, r in enumerate(p["items"], 1):
        amt = f" — {r['amount_label']}" if r["amount_label"] else ""
        name = _where(site, r) if p["key"] == "birth-bonus" else r["name"]
        lines.append(f"{i}. {name}{amt}")
    lines += ["", "📌 저장해 두고 하나씩 신청하세요", "(자격·금액은 신청 전 기관 확인 필수)"]
    text = "\n".join(lines)
    if len(text) > 480:  # 스레드 본문 500자 제한
        text = text[:477] + "…"
    reply = (f"지역별·아이 단계별 전체 목록은 여기 있어요 👉 {p['link']}\n"
             f"출처: 행정안전부 공공서비스(혜택) 정보 (공공데이터포털)")
    if p.get("quote"):
        reply += f"\n참고한 글: @{p['quote']['handle']} {p['quote']['url']}"
    return text, reply


def render_cards(site, posts, out_dir):
    """posts 의 카드를 PNG 로 렌더링. Chrome 이 없으면 HTML 만 남긴다."""
    chrome = find_chrome()
    env = Environment(loader=FileSystemLoader(ROOT / "templates"), autoescape=select_autoescape(["html"]))
    env.filters["truncate"] = site.env.filters["truncate"]
    tpl = env.get_template("card.html")
    emoji = (ROOT / "static" / "emoji").as_uri()
    jobs = []
    tmp = Path(tempfile.mkdtemp(prefix="cards-"))
    for p in posts:
        pdir = Path(out_dir) / p["key"]
        pdir.mkdir(parents=True, exist_ok=True)
        rank = p["key"] == "birth-bonus"
        label = (lambda r: f"{_where(site, r)} — {r['amount_label']}") if rank else (lambda r: r["name"])
        slides = [dict(kind="cover", eyebrow=p["eyebrow"], headline=p["headline"], sub=p["sub"],
                       preview=[label(r) for r in p["items"]], icon=p["icon"])]
        slides += [dict(kind="item", n=i, r=r, dd=site.dday(r), where=_where(site, r),
                        title=f"{_where(site, r)} {r['name']}" if rank else r["name"],
                        icon=(r["stages"] or ["money"])[0]) for i, r in enumerate(p["items"], 1)]
        slides.append(dict(kind="end", icon="bookmark"))
        p["images"] = []
        for i, s in enumerate(slides, 1):
            html = tpl.render(site_name=site.site_name, idx=i, total=len(slides), emoji=emoji, **s)
            src = tmp / f"{p['key']}-{i}.html"
            src.write_text(html, encoding="utf-8")
            png = pdir / f"{i}.png"
            p["images"].append(str(png.relative_to(site.out)) if png.is_relative_to(site.out) else str(png))
            jobs.append((src, png))

    def shoot(job):
        src, png = job
        subprocess.run([chrome, "--headless", "--no-sandbox", "--hide-scrollbars", "--disable-gpu",
                        "--force-device-scale-factor=1", "--window-size=1080,1350",
                        "--virtual-time-budget=5000", f"--screenshot={png}", src.as_uri()],
                       check=True, capture_output=True, timeout=120)

    if chrome:
        with ThreadPoolExecutor(max_workers=4) as ex:
            list(ex.map(shoot, jobs))
    shutil.rmtree(tmp, ignore_errors=True)
    return bool(chrome)


def generate(site, drafts_dir):
    posts = plan_posts(site)
    card_dir = site.out / "cards" / site.today.isoformat()
    ok = render_cards(site, posts, card_dir)
    Path(drafts_dir).mkdir(parents=True, exist_ok=True)
    out = [{"key": p["key"], "text": p["text"], "reply": p["reply"],
            "images": [site.base_url + site.u("/" + i) for i in p["images"]],
            "local_images": [str(site.out / i) for i in p["images"]]} for p in posts]
    path = Path(drafts_dir) / f"{site.today.isoformat()}.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    # 자동 게시 워크플로가 읽을 수 있도록 사이트에도 함께 올린다 (게시용 본문이라 공개돼도 무방)
    public = [{k: v for k, v in d.items() if k != "local_images"} for d in out]
    (card_dir / "drafts.json").write_text(json.dumps(public, ensure_ascii=False, indent=2), encoding="utf-8")
    return path, len(posts), ok
