"""밤·주말에 여는 소아청소년과 (국립중앙의료원 전국 병·의원 찾기 서비스).

공공데이터포털에서 '국립중앙의료원_전국 병·의원 찾기 서비스' 활용신청이 되어 있어야 한다.
신청 전이면 '등록되지 않은 서비스키'가 오므로 조용히 건너뛰고 기존 데이터를 유지한다.

요청: HsptlAsembySearchService/getHsptlMdcncListInfoInqire, QD=D002(소아청소년과)
응답 필드: hpid, dutyName, dutyAddr, dutyTel1, dutyDivNam, wgs84Lat, wgs84Lon,
          dutyTime{1..8}s / dutyTime{1..8}c (1=월 … 7=일, 8=공휴일, HHMM)
"""
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from .normalize import extract_region

URL = "https://apis.data.go.kr/B552657/HsptlAsembySearchService/getHsptlMdcncListInfoInqire"
DAYS = ["월", "화", "수", "목", "금", "토", "일", "공휴일"]
NIGHT_FROM = 2000  # 20:00 이후까지 진료하면 '야간'


class NotRegistered(RuntimeError):
    pass


def _get(params, retries=3):
    url = URL + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise NotRegistered("국립중앙의료원 병·의원 API 활용신청이 필요합니다 "
                                    "(https://www.data.go.kr/data/15000736/openapi.do).") from e
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
        except (urllib.error.URLError, TimeoutError):
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)


def parse(xml_bytes):
    """XML 응답 → (총건수, 아이템 dict 리스트)."""
    root = ET.fromstring(xml_bytes)
    code = root.findtext(".//resultCode") or root.findtext(".//returnReasonCode")
    if code == "30" or "NOT_REGISTERED" in (root.findtext(".//errMsg") or ""):
        raise NotRegistered("국립중앙의료원 병·의원 API 활용신청이 필요합니다.")
    if code not in (None, "00"):
        raise RuntimeError(f"병·의원 API 오류 {code}: {root.findtext('.//resultMsg')}")
    total = int(root.findtext(".//totalCount") or 0)
    items = [{c.tag: (c.text or "").strip() for c in it} for it in root.iter("item")]
    return total, items


def fetch_all(service_key, per_page=1000):
    rows, page = [], 1
    while True:
        total, items = parse(_get({"serviceKey": service_key, "QD": "D002",
                                   "pageNo": page, "numOfRows": per_page}))
        rows.extend(items)
        if not items or len(rows) >= total:
            return rows
        page += 1
        time.sleep(0.3)


def _hhmm(v):
    try:
        return int(str(v).strip()[:4])
    except (TypeError, ValueError):
        return None


def _fmt(v):
    return f"{v // 100:02d}:{v % 100:02d}"


def normalize(items):
    """야간 또는 주말·공휴일에 진료하는 곳만 남긴다."""
    out = []
    for it in items:
        hours = []
        for i, day in enumerate(DAYS, 1):
            s, c = _hhmm(it.get(f"dutyTime{i}s")), _hhmm(it.get(f"dutyTime{i}c"))
            hours.append([day, _fmt(s), _fmt(c)] if s is not None and c is not None else [day, None, None])
        closes = [_hhmm(it.get(f"dutyTime{i}c")) or 0 for i in range(1, 6)]
        night = max(closes) >= NIGHT_FROM
        sat, sun, hol = (hours[5][1] is not None), (hours[6][1] is not None), (hours[7][1] is not None)
        if not (night or sun or hol):
            continue
        sido, sigungu = extract_region(it.get("dutyAddr", ""))
        if not sido:
            continue
        tags = []
        if night:
            tags.append(f"평일 {_fmt(max(closes))}까지")
        if sat:
            tags.append("토요일")
        if sun:
            tags.append("일요일")
        if hol:
            tags.append("공휴일")
        out.append({
            "id": it.get("hpid", ""), "name": it.get("dutyName", ""), "addr": it.get("dutyAddr", ""),
            "tel": it.get("dutyTel1", ""), "div": it.get("dutyDivNam", ""),
            "lat": it.get("wgs84Lat", ""), "lon": it.get("wgs84Lon", ""),
            "sido": sido, "sigungu": sigungu, "night": night, "sun": sun, "hol": hol,
            "tags": tags, "hours": hours, "score": (sun or hol) * 2 + night,
        })
    out.sort(key=lambda r: (r["sido"], r["sigungu"] or "", -r["score"], r["name"]))
    return out
