"""행정안전부 대한민국 공공서비스(혜택) 정보 API 클라이언트.

명세: https://www.data.go.kr/data/15113968/openapi.do (sample/api-spec.json)
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "https://api.odcloud.kr/api/gov24/v3"
ENDPOINTS = ("serviceList", "serviceDetail", "supportConditions")


class ApiError(RuntimeError):
    pass


def _get(url, retries=4):
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code in (401, 403):
                body = e.read().decode("utf-8", "replace")
                raise ApiError(f"인증 실패 ({e.code}): {body}") from e
            if attempt == retries - 1:
                raise ApiError(f"요청 실패: {e}") from e
            time.sleep(2 ** attempt)


def fetch_all(endpoint, service_key, per_page=500, pause=0.3):
    """엔드포인트의 전체 페이지를 모아 data 행 리스트를 반환한다.

    service_key 는 공공데이터포털의 '일반 인증키(Decoding)' 값이어야 한다.
    """
    if endpoint not in ENDPOINTS:
        raise ValueError(endpoint)
    rows, page = [], 1
    while True:
        qs = urllib.parse.urlencode({
            "page": page, "perPage": per_page,
            "returnType": "JSON", "serviceKey": service_key,
        })
        data = _get(f"{BASE}/{endpoint}?{qs}")
        if "data" not in data:
            raise ApiError(f"{endpoint} 응답 오류: {data}")
        batch = data["data"]
        rows.extend(batch)
        total = data.get("totalCount") or 0
        if not batch or len(rows) >= total:
            break
        page += 1
        time.sleep(pause)
    return rows
