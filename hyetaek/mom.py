"""엄마·주부 관점 분류: 생애주기 단계, 지원 금액 추출.

스레드에서 반응이 좋은 육아 지원금 글은 (1) 아이 나이·단계별로 묶고
(2) 금액을 맨 앞에 세우고 (3) '신청 안 하면 0원'을 강조한다. 그 구조를 데이터로 만든다.
"""
import re

from .normalize import narrow_codes

# (slug, 이름, 이모지, 한 줄 설명, 조건 코드, 이름·요약 키워드, 본문 키워드)
# 이름/요약 키워드는 강한 신호, 본문 키워드는 조건 코드가 없을 때만 보조로 쓴다.
STAGES = [
    ("pre", "임신 준비·난임", "🌱", "난임 시술비, 임신 준비 검사",
     ["JA0301"], ["난임", "임신준비", "임신 준비", "가임력", "예비부부", "예비부모", "신혼부부"], []),
    ("pregnancy", "임신 중", "🤰", "임신 바우처, 산전검사, 임산부 교통비",
     ["JA0302"], ["임신", "임산부", "산전", "태아", "임부"], []),
    ("birth", "출산·산후", "👶", "첫만남이용권, 산후조리, 출산축하금",
     ["JA0303"], ["출산", "출생", "산후", "산모", "신생아", "첫만남", "입양"], []),
    ("infant", "영유아 (0~5세)", "🍼", "부모급여, 아동수당, 보육료, 아이돌봄",
     [], ["영유아", "영아", "유아", "보육", "어린이집", "유치원", "부모급여", "아동수당", "양육수당",
          "기저귀", "분유", "아이돌봄", "누리과정", "육아", "아기", "아이맘", "장난감도서관", "공동육아"], []),
    ("elementary", "초등학생", "🎒", "돌봄교실, 입학 축하금, 방과후",
     ["JA0317"], ["초등", "돌봄교실", "늘봄", "입학", "방과후", "지역아동센터"], []),
    ("teen", "중·고등학생", "📚", "교복비, 수학여행비, 교육비",
     ["JA0318", "JA0319"], ["중학", "고등학", "교복", "수학여행", "청소년", "교육비", "학습"], []),
    ("multichild", "다자녀", "👨‍👩‍👧‍👦", "다자녀 감면·할인, 우선 혜택",
     ["JA0411"], ["다자녀", "셋째", "둘째"], []),
    ("singleparent", "한부모·조손", "🤝", "한부모 양육비, 생활 지원",
     ["JA0403"], ["한부모", "조손", "미혼모", "양육비"], []),
    ("working", "워킹맘·육아휴직", "💼", "육아휴직 급여, 근로시간 단축, 출산휴가",
     [], ["육아휴직", "출산전후휴가", "근로시간 단축", "육아기", "배우자 출산휴가", "경력단절", "경단녀",
          "새일", "여성 재취업"], []),
    ("saving", "살림 절약", "🏠", "공과금·통신비 감면, 에너지바우처",
     [], ["에너지바우처", "전기요금", "도시가스", "가스요금", "상수도", "수도요금", "통신비", "통신요금",
          "난방비", "냉방비", "공과금", "감면", "할인", "주거급여", "월세", "전세자금", "주택구입"], []),
]
STAGE_NAMES = {s[0]: s[1] for s in STAGES}
STAGE_INFO = {s[0]: {"slug": s[0], "name": s[1], "emoji": s[2], "desc": s[3]} for s in STAGES}

# 엄마 관심사와 무관한데 키워드에 걸리기 쉬운 것들 (예: '할인'이 들어간 사업자 대출)
EXCLUDE = re.compile(r"(법인|기업체|사업장|농기계|어선|축사|가축|임업|선박|공장|산단)")


def _has(text, words):
    return any(w in text for w in words)


def stages_for(rec):
    """레코드 → 해당 생애주기 slug 리스트."""
    title = f"{rec.get('name', '')} {rec.get('summary', '')}"
    y = narrow_codes({k: "Y" for k in rec.get("cond", {}).get("y", [])})
    if EXCLUDE.search(title):
        return []
    out = []
    for slug, _, _, _, codes, title_kw, _ in STAGES:
        if (codes and y & set(codes)) or _has(title, title_kw):
            out.append(slug)
    # 살림 절약은 개인 대상일 때만 (사업자 감면 제외)
    if "saving" in out and rec.get("user_type") and "개인" not in rec["user_type"] and "가구" not in rec["user_type"]:
        out.remove("saving")
    return out


_MAN = re.compile(r"(\d{1,3}(?:,\d{3})*|\d+)(?:\.(\d+))?\s*만\s*원")
_EOK = re.compile(r"(\d+)(?:\.(\d+))?\s*억\s*원")
_WON = re.compile(r"(\d{1,3}(?:,\d{3})+|\d{5,})\s*원")


# 개인이 받는 돈이 아니라 사업비·시설비·창업자금인 경우
NOT_PERSONAL = re.compile(r"(개소|사업비|구축|창업|귀농|귀촌|귀산|귀어|시설|법인|단체|기관당|업체)")
PER_MONTH = re.compile(r"(월|매월|매달|월\s*최대)\s*$")


def _amounts(text):
    """(금액, 시작위치) 목록. '최대 200만원', '월 100만원', '1억원', '50,000원' 형태."""
    out = []
    for m in _EOK.finditer(text):
        out.append((int(m.group(1)) * 10 ** 8 + int((m.group(2) or "0")[:1] or 0) * 10 ** 7, m.start()))
    for m in _MAN.finditer(text):
        frac = m.group(2)
        out.append((int(m.group(1).replace(",", "")) * 10_000 + (int(frac[:4].ljust(4, "0")) if frac else 0), m.start()))
    for m in _WON.finditer(text):
        out.append((int(m.group(1).replace(",", "")), m.start()))
    return [(v, i) for v, i in out if 1_000 <= v <= 5 * 10 ** 8]


def max_amount(text):
    """지원내용에서 가장 큰 금액(원). 없으면 None."""
    vals = _amounts(text or "")
    return max(vals)[0] if vals else None


def is_monthly(text, amount):
    """가장 큰 금액 바로 앞에 '월'이 붙어 있으면 매달 받는 돈."""
    for v, i in _amounts(text or ""):
        if v == amount:
            before = text[max(0, i - 8):i].replace("최대", "").strip()
            return bool(PER_MONTH.search(before))
    return False


def personal_amount(rec, amount):
    """엄마가 '받는 돈'으로 보여줘도 되는 금액인지 (사업비·대출·고액 제외)."""
    if not amount or amount > 30_000_000:
        return False
    return not NOT_PERSONAL.search(f"{rec.get('name', '')} {rec.get('summary', '')} {rec.get('content', '')[:200]}")


def format_won(v):
    if v is None:
        return ""
    if v >= 10 ** 8:
        eok, rest = divmod(v, 10 ** 8)
        man = rest // 10_000
        return f"{eok}억 {man:,}만원" if man else f"{eok}억원"
    if v >= 10_000:
        man, rest = divmod(v, 10_000)
        return f"{man:,}만원" if rest == 0 else f"{v / 10_000:,.1f}만원".replace(".0만", "만")
    return f"{v:,}원"
