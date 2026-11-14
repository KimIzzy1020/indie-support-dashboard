import json
import os
import re
from datetime import date, datetime, timezone
from html import unescape
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlsplit
from urllib.request import urlopen

BASE = "https://www.bizinfo.go.kr"
DATA = Path(__file__).resolve().parents[1] / "data" / "notices.json"


def clean(value):
    return unescape(re.sub(r"<[^>]+>", " ", str(value or ""))).strip()


def application_dates(period):
    match = re.fullmatch(r"\s*(\d{8})\s*[~～]\s*(\d{8})\s*", period)
    if match:
        try:
            start, end = (date.fromisoformat(value) for value in match.groups())
            if start <= end:
                return start.isoformat(), end.isoformat()
        except ValueError:
            pass
    return "", ""


def main():
    key = os.environ.get("BIZINFO_API_KEY", "").strip()
    if not key:
        raise SystemExit("BIZINFO_API_KEY가 전달되지 않았습니다.")

    query = urlencode({
        "crtfcKey": key,
        "dataType": "json",
        "searchCnt": "100",
    })
    try:
        with urlopen(f"{BASE}/uss/rss/bizinfoApi.do?{query}", timeout=30) as response:
            payload = json.load(response)
    except (OSError, ValueError):
        raise SystemExit("기업마당 API 요청 또는 JSON 읽기에 실패했습니다.") from None

    rows = payload.get("jsonArray") or payload.get("item") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        raise SystemExit("기업마당 응답에서 공고 목록을 찾지 못했습니다.")

    existing = json.loads(DATA.read_text(encoding="utf-8-sig"))
    items = {item["id"]: item for item in existing["items"]}
    count = 0
    for row in rows:
        if not isinstance(row, dict):
            continue
        notice_id = clean(row.get("pblancId") or row.get("seq"))
        title = clean(row.get("pblancNm") or row.get("title"))
        raw_link = row.get("pblancUrl") or row.get("link")
        if not notice_id or not title or not raw_link:
            continue
        url = urljoin(BASE, raw_link)
        if urlsplit(url).scheme not in ("https", "http"):
            continue

        period = clean(row.get("reqstBeginEndDe") or row.get("reqstDt"))
        start, deadline = application_dates(period)
        item_id = f"bizinfo-{notice_id}"
        items[item_id] = {
            "id": item_id,
            "title": title,
            "agency": clean(row.get("jrsdInsttNm") or row.get("author")) or "기업마당",
            "category": clean(row.get("pldirSportRealmLclasCodeNm") or row.get("lcategory")) or "기타",
            "year": "기업마당 공식 공고",
            "url": url,
            "start": start,
            "deadline": deadline,
            "description": clean(row.get("bsnsSumryCn") or row.get("description")),
            "eligibilityText": clean(row.get("trgetNm")),
            "source": "bizinfo",
        }
        count += 1

    if not count:
        raise SystemExit("제목과 링크가 있는 기업마당 공고를 찾지 못했습니다.")
    updated = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "items": list(items.values()),
    }
    temporary = DATA.with_suffix(".tmp")
    temporary.write_text(json.dumps(updated, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(DATA)
    print(f"기업마당 공식 공고 {count}건 수집 완료")


if __name__ == "__main__":
    main()
