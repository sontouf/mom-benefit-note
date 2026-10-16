"""Microsoft Fluent Emoji 3D (MIT) 이미지를 static/emoji/ 로 내려받는다.

시스템 이모지는 기기마다 모양이 달라 카드뉴스·웹에서 통일감이 깨진다.
Fluent 3D 는 무료(MIT)이면서 손으로 다듬은 일러스트라 'AI 티'가 나지 않는다.
"""
import sys
import urllib.request
from pathlib import Path

BASE = "https://cdn.jsdelivr.net/gh/microsoft/fluentui-emoji@main/assets/"
ASSETS = {
    "pre": "Seedling/3D/seedling_3d.png",
    "pregnancy": "Pregnant woman/Default/3D/pregnant_woman_3d_default.png",
    "birth": "Baby/Default/3D/baby_3d_default.png",
    "infant": "Baby bottle/3D/baby_bottle_3d.png",
    "elementary": "Backpack/3D/backpack_3d.png",
    "teen": "Books/3D/books_3d.png",
    "multichild": "People hugging/3D/people_hugging_3d.png",
    "singleparent": "Two hearts/3D/two_hearts_3d.png",
    "working": "Briefcase/3D/briefcase_3d.png",
    "saving": "House/3D/house_3d.png",
    "money": "Money bag/3D/money_bag_3d.png",
    "clock": "Alarm clock/3D/alarm_clock_3d.png",
    "new": "Sparkles/3D/sparkles_3d.png",
    "pin": "Round pushpin/3D/round_pushpin_3d.png",
    "fire": "Fire/3D/fire_3d.png",
    "bookmark": "Bookmark/3D/bookmark_3d.png",
    "chat": "Speech balloon/3D/speech_balloon_3d.png",
    "check": "Check mark button/3D/check_mark_button_3d.png",
    "news": "Newspaper/3D/newspaper_3d.png",
    "trophy": "Trophy/3D/trophy_3d.png",
    "bulb": "Light bulb/3D/light_bulb_3d.png",
    "gift": "Wrapped gift/3D/wrapped_gift_3d.png",
    "hospital": "Hospital/3D/hospital_3d.png",
    "mom": "Woman feeding baby/Default/3D/woman_feeding_baby_3d_default.png",
    # 따뜻한 분위기용 장식 스티커
    "teddy": "Teddy bear/3D/teddy_bear_3d.png",
    "balloon": "Balloon/3D/balloon_3d.png",
    "sparkle-heart": "Sparkling heart/3D/sparkling_heart_3d.png",
    "rainbow": "Rainbow/3D/rainbow_3d.png",
    "sun-face": "Sun with face/3D/sun_with_face_3d.png",
    "cloud": "Cloud/3D/cloud_3d.png",
    "chick": "Baby chick/3D/baby_chick_3d.png",
    "hatching": "Hatching chick/3D/hatching_chick_3d.png",
    "blossom": "Cherry blossom/3D/cherry_blossom_3d.png",
    "star": "Glowing star/3D/glowing_star_3d.png",
    "ribbon-heart": "Heart with ribbon/3D/heart_with_ribbon_3d.png",
    "love-face": "Smiling face with hearts/3D/smiling_face_with_hearts_3d.png",
    "angel": "Baby angel/Default/3D/baby_angel_3d_default.png",
    "house-garden": "House with garden/3D/house_with_garden_3d.png",
    "bouquet": "Bouquet/3D/bouquet_3d.png",
    "letter": "Love letter/3D/love_letter_3d.png",
    "party": "Party popper/3D/party_popper_3d.png",
    "hug": "Hugging face/3D/hugging_face_3d.png",
    "heart": "Red heart/3D/red_heart_3d.png",
    "pink-heart": "Pink heart/3D/pink_heart_3d.png",
    "crayon": "Crayon/3D/crayon_3d.png",
    "kite": "Kite/3D/kite_3d.png",
    "tv": "Television/3D/television_3d.png",
    "moon": "Crescent moon/3D/crescent_moon_3d.png",
    "pill": "Pill/3D/pill_3d.png",
    "ambulance": "Ambulance/3D/ambulance_3d.png",
    "stethoscope": "Stethoscope/3D/stethoscope_3d.png",
    "menu-book": "Open book/3D/open_book_3d.png",
}

out = Path(__file__).resolve().parent.parent / "static" / "emoji"
out.mkdir(parents=True, exist_ok=True)
failed = []
for name, path in ASSETS.items():
    url = BASE + urllib.request.quote(path)
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            (out / f"{name}.png").write_bytes(r.read())
    except Exception as e:  # noqa: BLE001
        failed.append((name, path, e))
for f in failed:
    print("실패:", *f)
print(f"{len(ASSETS) - len(failed)}/{len(ASSETS)}개 저장 → {out}")
sys.exit(1 if failed else 0)
