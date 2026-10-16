"""원본 API 행을 사이트용 레코드로 정규화한다."""
import re
from datetime import date

SIDO = [
    "서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시",
    "울산광역시", "세종특별자치시", "경기도", "강원특별자치도", "충청북도", "충청남도",
    "전북특별자치도", "전라남도", "전남광주통합특별시", "경상북도", "경상남도", "제주특별자치도",
]
SIDO_ALIASES = {"강원도": "강원특별자치도", "전라북도": "전북특별자치도", "제주도": "제주특별자치도"}

INCOME_CODES = ["JA0201", "JA0202", "JA0203", "JA0204", "JA0205"]

# 지원조건 코드는 그룹 안의 코드가 전부 Y 이면 '제한 없음'이라는 뜻이다
# (예: 근로장려금은 가구유형 8개가 모두 Y). 그룹 중 일부만 Y 일 때만 대상 신호로 쓴다.
CODE_GROUPS = [
    ["JA0301", "JA0302", "JA0303"],                                   # 임신·출산
    ["JA0313", "JA0314", "JA0315", "JA0316", "JA0317", "JA0318",      # 직업·학생
     "JA0319", "JA0320", "JA0322", "JA0326", "JA0327"],
    ["JA0401", "JA0402", "JA0403", "JA0404", "JA0410", "JA0411",      # 가구유형
     "JA0412", "JA0413", "JA0414"],
    ["JA0328", "JA0329", "JA0330"],                                   # 장애·보훈·질환
    ["JA1101", "JA1102", "JA1103"],                                   # 창업·자영업
]
NONE_CODES = {"JA0322", "JA0410"}  # '해당사항없음'


def _yes(c, k):
    return str(c.get(k) or "").upper() == "Y"


def narrow_codes(cond):
    """대상을 실제로 좁히는 코드 집합."""
    out = set()
    for group in CODE_GROUPS:
        ys = [k for k in group if _yes(cond, k)]
        limit = 2 if len(group) <= 3 else 3
        if ys and len(ys) <= limit and not NONE_CODES & set(ys):
            out.update(ys)
    return out


def _age(c, key):
    v = c.get(key)
    try:
        return int(v) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _youth(c, n):
    a0, a1 = _age(c, "JA0110"), _age(c, "JA0111")
    return a0 is not None and a1 is not None and a0 <= 34 and a1 >= 19 and a1 <= 45


def _senior(c, n):
    a0 = _age(c, "JA0110")
    return a0 is not None and a0 >= 60


def _low_income(c, n):
    return _yes(c, "JA0201") and not _yes(c, "JA0205")


def _any(*codes):
    return lambda c, n: bool(n & set(codes))


# (slug, 이름, 판정함수(cond, narrow_codes))
TARGETS = [
    ("youth", "청년", _youth),
    ("senior", "어르신", _senior),
    ("pregnancy", "임신·출산", _any("JA0301", "JA0302", "JA0303")),
    ("student", "학생", _any("JA0317", "JA0318", "JA0319", "JA0320")),
    ("jobseeker", "구직자·실업자", _any("JA0327")),
    ("worker", "직장인", _any("JA0326")),
    ("single", "1인가구", _any("JA0404")),
    ("multichild", "다자녀가구", _any("JA0411")),
    ("homeless", "무주택자", _any("JA0412")),
    ("singleparent", "한부모·조손가정", _any("JA0403")),
    ("multicultural", "다문화·북한이탈주민", _any("JA0401", "JA0402")),
    ("lowincome", "저소득층", _low_income),
    ("smallbiz", "소상공인·창업", _any("JA1101", "JA1102", "JA1103")),
    ("farmer", "농어업인", _any("JA0313", "JA0314", "JA0315", "JA0316")),
    ("disabled", "장애인", _any("JA0328")),
    ("veteran", "국가보훈대상자", _any("JA0329")),
]
TARGET_NAMES = {slug: name for slug, name, _ in TARGETS}

_DATE_RE = re.compile(r"(20\d{2})\s*[.\-/년]\s*(\d{1,2})\s*[.\-/월]\s*(\d{1,2})")


def parse_deadline(text):
    """신청기한 자유 텍스트 → {"kind", "end"}.

    kind: always(상시) | budget(예산 소진 시) | dated(종료일 있음) | unknown
    """
    t = (text or "").strip()
    dates = []
    for y, m, d in _DATE_RE.findall(t):
        try:
            dates.append(date(int(y), int(m), int(d)))
        except ValueError:
            pass
    if dates:
        return {"kind": "dated", "end": max(dates)}
    if "상시" in t:
        return {"kind": "always", "end": None}
    if "예산" in t and ("소진" in t or "범위" in t):
        return {"kind": "budget", "end": None}
    return {"kind": "unknown", "end": None}


def extract_region(org_name):
    """소관기관명 → (시도, 시군구). 중앙부처면 (None, None)."""
    tokens = (org_name or "").split()
    if not tokens:
        return None, None
    sido = SIDO_ALIASES.get(tokens[0], tokens[0])
    if sido not in SIDO:
        return None, None
    sigungu = None
    if len(tokens) > 1 and tokens[1][-1:] in ("시", "군", "구"):
        sigungu = tokens[1]
    return sido, sigungu


def target_slugs(cond):
    if not cond:
        return []
    n = narrow_codes(cond)
    return [slug for slug, _, fn in TARGETS if fn(cond, n)]


def condition_codes(cond):
    """맞춤 찾기용: 값이 Y인 JA 코드와 연령 범위."""
    if not cond:
        return {}
    codes = sorted(k for k, v in cond.items() if k.startswith("JA") and str(v or "").upper() == "Y")
    out = {"y": codes, "n": sorted(narrow_codes(cond))}
    a0, a1 = _age(cond, "JA0110"), _age(cond, "JA0111")
    if a0 is not None:
        out["a0"] = a0
    if a1 is not None:
        out["a1"] = a1
    return out


def _clean(v):
    if v is None:
        return ""
    return str(v).replace("\r\n", "\n").strip()


def build_records(service_list, details, conditions):
    """세 엔드포인트 결과를 서비스ID 기준으로 합쳐 정규화 레코드 리스트를 반환."""
    detail_by_id = {d.get("서비스ID"): d for d in details}
    cond_by_id = {c.get("서비스ID"): c for c in conditions}
    records = []
    for row in service_list:
        sid = row.get("서비스ID")
        if not sid:
            continue
        det = detail_by_id.get(sid, {})
        cond = cond_by_id.get(sid, {})
        merged = {**{k: _clean(v) for k, v in row.items()},
                  **{k: _clean(v) for k, v in det.items() if v not in (None, "")}}
        sido, sigungu = extract_region(merged.get("소관기관명"))
        dl = parse_deadline(merged.get("신청기한"))
        try:
            views = int(row.get("조회수") or 0)
        except (TypeError, ValueError):
            views = 0
        records.append({
            "id": sid,
            "name": merged.get("서비스명", ""),
            "summary": merged.get("서비스목적요약") or merged.get("서비스목적", ""),
            "purpose": merged.get("서비스목적", ""),
            "field": merged.get("서비스분야", "") or "기타",
            "support_type": merged.get("지원유형", ""),
            "user_type": merged.get("사용자구분", ""),
            "target_text": merged.get("지원대상", ""),
            "criteria": merged.get("선정기준", ""),
            "content": merged.get("지원내용", ""),
            "how": merged.get("신청방법", ""),
            "deadline_text": merged.get("신청기한", ""),
            "deadline_kind": dl["kind"],
            "deadline_end": dl["end"].isoformat() if dl["end"] else None,
            "documents": merged.get("구비서류", ""),
            "documents_official": merged.get("공무원확인구비서류", ""),
            "documents_self": merged.get("본인확인필요구비서류", ""),
            "org": merged.get("소관기관명", ""),
            "org_type": merged.get("소관기관유형", ""),
            "dept": merged.get("부서명", ""),
            "reception": merged.get("접수기관명") or merged.get("접수기관", ""),
            "contact": merged.get("문의처") or merged.get("전화문의", ""),
            "apply_url": merged.get("온라인신청사이트URL", ""),
            "detail_url": merged.get("상세조회URL", ""),
            "laws": merged.get("법령", ""),
            "ordinances": merged.get("자치법규", ""),
            "rules": merged.get("행정규칙", ""),
            "views": views,
            "registered": merged.get("등록일시", ""),
            "modified": merged.get("수정일시", ""),
            "sido": sido,
            "sigungu": sigungu,
            "targets": target_slugs(cond),
            "cond": condition_codes(cond),
        })
    records.sort(key=lambda r: (-r["views"], r["id"]))
    return records
