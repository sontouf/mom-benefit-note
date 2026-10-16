"""이전 스냅샷과 비교해 신규/변경/종료 이벤트를 기록한다.

정부24에는 '무엇이 언제 바뀌었는지' 이력이 없으므로, 이 변경 이력이
사이트만의 고유 데이터가 된다.
"""
import hashlib
import json

# 이 필드가 바뀌었을 때만 '변경'으로 본다 (조회수 같은 잡음 제외).
TRACKED = ("name", "target_text", "criteria", "content", "how", "deadline_text", "apply_url")
MAX_EVENTS = 3000


def _fingerprint(rec):
    raw = json.dumps([rec.get(k) for k in TRACKED], ensure_ascii=False)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def diff(prev_records, curr_records, today):
    """prev 가 None(최초 실행)이면 이벤트 없이 기준선만 만든다."""
    if prev_records is None:
        return []
    prev = {r["id"]: r for r in prev_records}
    curr = {r["id"]: r for r in curr_records}
    events = []
    for sid, rec in curr.items():
        old = prev.get(sid)
        if old is None:
            events.append({"date": today, "id": sid, "name": rec["name"], "type": "new"})
        elif _fingerprint(old) != _fingerprint(rec):
            changed = [k for k in TRACKED if old.get(k) != rec.get(k)]
            events.append({"date": today, "id": sid, "name": rec["name"],
                           "type": "updated", "fields": changed})
    for sid, old in prev.items():
        if sid not in curr:
            events.append({"date": today, "id": sid, "name": old["name"], "type": "removed"})
    return events


def merge(existing_events, new_events):
    return (new_events + existing_events)[:MAX_EVENTS]
