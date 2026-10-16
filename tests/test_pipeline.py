import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from hyetaek import history
from hyetaek.build import Site, _text_filter
from hyetaek.mom import format_won, is_monthly, max_amount, personal_amount, stages_for
from hyetaek.normalize import build_records, extract_region, narrow_codes, parse_deadline, target_slugs

ROOT = Path(__file__).resolve().parent.parent


def load_sample():
    raw = {n: json.loads((ROOT / "sample" / f"{n}.json").read_text(encoding="utf-8"))
           for n in ("serviceList", "serviceDetail", "supportConditions")}
    return build_records(raw["serviceList"], raw["serviceDetail"], raw["supportConditions"])


class NormalizeTest(unittest.TestCase):
    def test_deadline(self):
        self.assertEqual(parse_deadline("2026.10.01 ~ 2026.10.24"), {"kind": "dated", "end": date(2026, 10, 24)})
        self.assertEqual(parse_deadline("2026년 10월 20일까지")["end"], date(2026, 10, 20))
        self.assertEqual(parse_deadline("2026-3-5")["end"], date(2026, 3, 5))
        self.assertEqual(parse_deadline("상시신청")["kind"], "always")
        self.assertEqual(parse_deadline("예산 소진 시까지")["kind"], "budget")
        self.assertEqual(parse_deadline("")["kind"], "unknown")
        self.assertEqual(parse_deadline("2026.13.40")["kind"], "unknown")

    def test_region(self):
        self.assertEqual(extract_region("서울특별시 강남구"), ("서울특별시", "강남구"))
        self.assertEqual(extract_region("경기도 수원시"), ("경기도", "수원시"))
        self.assertEqual(extract_region("강원도"), ("강원특별자치도", None))
        self.assertEqual(extract_region("보건복지부"), (None, None))
        self.assertEqual(extract_region(None), (None, None))

    def test_targets(self):
        self.assertIn("youth", target_slugs({"JA0110": 19, "JA0111": 34}))
        self.assertNotIn("youth", target_slugs({"JA0110": 0, "JA0111": 100}))
        self.assertIn("senior", target_slugs({"JA0110": "65"}))
        self.assertIn("lowincome", target_slugs({"JA0201": "Y"}))
        self.assertNotIn("lowincome", target_slugs({k: "Y" for k in ("JA0201", "JA0205")}))

    def test_build_records(self):
        recs = load_sample()
        self.assertEqual(len(recs), 8)
        rent = next(r for r in recs if r["id"] == "SAMPLE-0001")
        self.assertEqual(rent["deadline_end"], "2026-10-24")
        self.assertIn("homeless", rent["targets"])
        self.assertEqual(rent["documents"], "○ 신분증\n○ 신청서")  # detail 병합
        self.assertEqual(recs[0]["id"], "SAMPLE-0008")  # 조회수 순


class HistoryTest(unittest.TestCase):
    def test_first_run_is_baseline(self):
        self.assertEqual(history.diff(None, load_sample(), "2026-10-17"), [])

    def test_diff(self):
        prev = load_sample()
        curr = [dict(r) for r in prev[1:]]
        curr[0]["content"] = "변경됨"
        curr.append({**prev[0], "id": "NEW-1", "name": "신규"})
        types = {(e["id"], e["type"]) for e in history.diff(prev, curr, "d")}
        self.assertIn((prev[0]["id"], "removed"), types)
        self.assertIn((curr[0]["id"], "updated"), types)
        self.assertIn(("NEW-1", "new"), types)
        self.assertEqual(len(types), 3)


class BuildTest(unittest.TestCase):
    def test_text_filter_escapes(self):
        out = str(_text_filter("○ <script>x</script>\n일반"))
        self.assertNotIn("<script>", out)
        self.assertIn('class="li"', out)

    def test_site_build(self):
        recs = load_sample()
        trends = {"checked": "2026-10-17", "topics": [{
            "slug": "zero-won", "icon": "money", "title": "t", "hook": "h", "why": "w", "caution": "c",
            "keywords": ["첫만남", "내일배움"], "threads": [], "refs": []}]}
        with tempfile.TemporaryDirectory() as d:
            n = Site(recs, [], d, today=date(2026, 10, 17), trends=trends).build()
            out = Path(d)
            self.assertGreater(n, 8)
            html = (out / "s" / "SAMPLE-0001" / "index.html").read_text(encoding="utf-8")
            self.assertIn("D-7", html)
            self.assertIn("월 20만원", html)
            self.assertIn('"@type": "GovernmentService"', html)
            self.assertTrue((out / "stage" / "birth" / "index.html").exists())
            self.assertTrue((out / "region" / "경기도" / "수원시" / "index.html").exists())
            # 엄마와 무관한 혜택(어르신 교통비)은 빠지고, 트렌드 키워드에 걸린 혜택은 남는다
            self.assertFalse((out / "s" / "SAMPLE-0004").exists())
            self.assertTrue((out / "s" / "SAMPLE-0008").exists())
            self.assertIn("첫만남이용권", (out / "trend" / "zero-won" / "index.html").read_text(encoding="utf-8"))
            find = json.loads((out / "static" / "find.json").read_text(encoding="utf-8"))
            self.assertNotIn("SAMPLE-0007", [r[0] for r in find])  # 마감된 혜택 제외
            self.assertIn("sitemap-1.xml", (out / "sitemap.xml").read_text(encoding="utf-8"))


class MomTest(unittest.TestCase):
    def test_amount(self):
        self.assertEqual(max_amount("○ 첫째 200만원, 둘째 이상 300만원"), 3_000_000)
        self.assertEqual(max_amount("월 1.5만원"), 15_000)
        self.assertEqual(max_amount("50,000원 상당"), 50_000)
        self.assertIsNone(max_amount("현물 지원"))
        self.assertTrue(is_monthly("○ 월 최대 20만원", 200_000))
        self.assertFalse(is_monthly("출생순위별 차등(6월 신청) 2,500만원", 25_000_000))
        self.assertEqual(format_won(12_196_000), "1,219.6만원")
        self.assertEqual(format_won(300_000_000), "3억원")

    def test_personal_amount(self):
        self.assertTrue(personal_amount({"name": "출산축하금"}, 1_000_000))
        self.assertFalse(personal_amount({"name": "귀농 창업 지원"}, 1_000_000))
        self.assertFalse(personal_amount({"name": "출산축하금"}, 200_000_000))

    def test_narrow_codes(self):
        everyone = {k: "Y" for k in ("JA0401", "JA0402", "JA0403", "JA0404", "JA0410", "JA0411", "JA0412", "JA0413", "JA0414")}
        self.assertEqual(narrow_codes(everyone), set())
        self.assertEqual(narrow_codes({"JA0411": "Y"}), {"JA0411"})

    def test_stages(self):
        rec = {"name": "아동수당", "summary": "", "cond": {"y": []}, "user_type": "개인"}
        self.assertIn("infant", stages_for(rec))
        rec = {"name": "농기계 임대료 감면", "summary": "", "cond": {"y": ["JA0411"]}, "user_type": "개인"}
        self.assertEqual(stages_for(rec), [])


if __name__ == "__main__":
    unittest.main()
