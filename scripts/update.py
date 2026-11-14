"""Collect RSS discovery candidates while retaining previously seen IDs."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen
from xml.etree import ElementTree

DATA = Path(__file__).resolve().parents[1] / "data" / "notices.json"
QUERIES = (
    "독립출판 출판 지원사업 모집",
    "경기도 콘텐츠 창업 지원사업 모집",
    "청년 여성 예비창업 지원사업 모집",
)


def collect():
    existing = json.loads(DATA.read_text(encoding="utf-8"))
    items = {item["id"]: item for item in existing["items"]}
    for query in QUERIES:
        params = urlencode({"q": query + " when:30d", "hl": "ko", "gl": "KR", "ceid": "KR:ko"})
        request = Request("https://news.google.com/rss/search?" + params, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(request, timeout=25) as response:
            feed = ElementTree.fromstring(response.read())
        for article in feed.findall("./channel/item"):
            title = (article.findtext("title") or "").strip()
            url = (article.findtext("link") or "").strip()
            if not title or urlsplit(url).scheme != "https":
                continue
            identifier = article.findtext("guid") or url
            key = "news-" + hashlib.sha256(identifier.encode()).hexdigest()[:20]
            items[key] = {
                "id": key,
                "title": title,
                "agency": article.findtext("source") or "뉴스 RSS",
                "category": "발견 후보",
                "year": "뉴스 RSS",
                "url": url,
                "description": "기사에서 발견한 후보입니다. 모집 여부와 신청 조건은 주관기관 공고에서 확인하세요.",
                "published": article.findtext("pubDate") or "",
            }
    updated = {"updated_at": datetime.now(timezone.utc).isoformat(), "items": list(items.values())}
    temporary = DATA.with_suffix(".tmp")
    temporary.write_text(json.dumps(updated, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(DATA)


if __name__ == "__main__":
    collect()
