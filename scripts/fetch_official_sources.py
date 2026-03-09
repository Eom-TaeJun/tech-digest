"""
Daily Tech Digest - Step 0.5: 공식 모델 릴리즈 직접 수집
- OpenAI / Anthropic 공식 페이지에서 최근 모델 릴리즈를 직접 수집
- 결과: raw/{date}.json 의 model_release_official_watch 결과를 직접 채움
"""

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

KST = timezone(timedelta(hours=9))
UTC = timezone.utc
TODAY = datetime.now(KST).strftime("%Y-%m-%d")
LOOKBACK_DAYS = 14

MONTH_PATTERNS = [
    "%B %d, %Y",
    "%b %d, %Y",
]


@dataclass
class OfficialRelease:
    company: str
    model: str
    released_at: str
    source_url: str
    note: str


class LinkExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if href:
            self.links.append(href)


def fetch_html(url: str) -> str:
    resp = requests.get(
        url,
        timeout=30,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
        },
    )
    resp.raise_for_status()
    return resp.text


def html_to_text(html: str) -> str:
    html = re.sub(r"<script.*?</script>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<style.*?</style>", " ", html, flags=re.I | re.S)
    html = re.sub(r"</(p|div|h1|h2|h3|h4|li|section|article|br)>", "\n", html, flags=re.I)
    html = re.sub(r"<[^>]+>", " ", html)
    text = unescape(html)
    text = text.replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def extract_same_host_links(base_url: str, html: str) -> list[str]:
    parser = LinkExtractor()
    parser.feed(html)
    base_host = urlparse(base_url).netloc
    results = []
    seen = set()

    for href in parser.links:
        full = urljoin(base_url, href)
        host = urlparse(full).netloc
        if host != base_host:
            continue
        if full in seen:
            continue
        seen.add(full)
        results.append(full)
    return results


def find_date(text: str) -> datetime | None:
    for match in re.finditer(
        r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)\s+\d{1,2},\s+\d{4}\b",
        text,
    ):
        raw = match.group(0).replace("Sept", "Sep")
        for fmt in MONTH_PATTERNS:
            try:
                return datetime.strptime(raw, fmt).replace(tzinfo=UTC)
            except ValueError:
                continue
    return None


def normalize_model_name(raw: str) -> str:
    cleaned = raw.replace("‑", "-").replace("–", "-").replace("—", "-").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def extract_models(text: str, pattern: str) -> list[str]:
    found = []
    seen = set()
    for match in re.finditer(pattern, text, flags=re.I):
        model = normalize_model_name(match.group(0))
        key = model.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(model)
    return found


def collect_openai_releases() -> list[OfficialRelease]:
    releases: list[OfficialRelease] = []
    cutoff = datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return releases

    resp = requests.get(
        "https://api.openai.com/v1/models",
        timeout=30,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])

    for item in data:
        model_id = item.get("id", "")
        created = item.get("created")
        if not model_id or not created:
            continue
        if not re.match(r"^(gpt-\d|o\d|codex)", model_id):
            continue
        release_date = datetime.fromtimestamp(created, tz=UTC)
        if release_date < cutoff:
            continue
        releases.append(
            OfficialRelease(
                company="OpenAI",
                model=model_id,
                released_at=release_date.date().isoformat(),
                source_url="https://api.openai.com/v1/models",
                note="Official OpenAI models API listing",
            )
        )
    return releases


def collect_anthropic_releases() -> list[OfficialRelease]:
    news_url = "https://www.anthropic.com/news"
    html = fetch_html(news_url)
    links = extract_same_host_links(news_url, html)
    candidate_links = [
        link
        for link in links
        if "/news/claude" in link or "/news/introducing" in link
    ]

    releases: list[OfficialRelease] = []
    cutoff = datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)

    for link in candidate_links[:25]:
        page_html = fetch_html(link)
        text = html_to_text(page_html)
        release_date = find_date(text[:6000])
        if not release_date or release_date < cutoff:
            continue
        models = extract_models(
            text[:8000],
            r"\bClaude\s+(?:Sonnet|Opus)\s+\d+(?:\.\d+)?\b",
        )
        if not models:
            continue
        for model in models:
            releases.append(
                OfficialRelease(
                    company="Anthropic",
                    model=model,
                    released_at=release_date.date().isoformat(),
                    source_url=link.rstrip("/"),
                    note="Official Anthropic news post",
                )
            )
    return releases


def dedupe_releases(items: list[OfficialRelease]) -> list[OfficialRelease]:
    seen = set()
    unique = []
    for item in sorted(items, key=lambda x: (x.released_at, x.company, x.model), reverse=True):
        key = (item.company.lower(), item.model.lower(), item.released_at)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def build_answer(releases: list[OfficialRelease]) -> str:
    if not releases:
        return (
            "No official model releases were found on the configured official source pages "
            f"in the last {LOOKBACK_DAYS} days."
        )

    lines = [
        "Verified official model releases from configured vendor pages:",
        "",
    ]
    for item in releases:
        lines.append(
            f"- **{item.company} — {item.model}** | release date: **{item.released_at}** | source: {item.source_url}"
        )
    lines.append("")
    lines.append(
        "Use these official releases as source of truth for latest model/version names. "
        "Treat later benchmark chatter and third-party recaps separately."
    )
    return "\n".join(lines)


def load_raw(path: str) -> dict:
    if not os.path.exists(path):
        return {"date": TODAY, "results": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_raw(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    print(f"[{TODAY}] Official release sources fetch 시작")
    releases = dedupe_releases(collect_openai_releases() + collect_anthropic_releases())
    print(f"  → official releases found: {len(releases)}")

    raw_path = os.path.join("raw", f"{TODAY}.json")
    data = load_raw(raw_path)
    data.setdefault("results", {})
    data["official_releases"] = [
        {
            "company": item.company,
            "model": item.model,
            "released_at": item.released_at,
            "source_url": item.source_url,
            "note": item.note,
        }
        for item in releases
    ]
    data["results"]["model_release_official_watch"] = {
        "id": "model_release_official_watch",
        "title": "공식 모델 릴리즈 체크 — 최신 버전/날짜 확인",
        "query": "Official sources direct fetch",
        "answer": build_answer(releases),
        "citations": [item.source_url for item in releases],
        "model": "direct-official-fetch",
        "recency": "week",
        "evidence": {
            "domains": sorted({urlparse(item.source_url).netloc for item in releases}),
            "community_source_count": 0,
            "official_source_count": len(releases),
            "has_direct_community_sources": False,
            "has_official_sources": bool(releases),
        },
        "usage": {},
        "source": "official-direct",
    }
    save_raw(raw_path, data)
    print(f"  → raw 저장/업데이트: {raw_path}")
    for item in releases:
        print(f"    {item.company}: {item.model} ({item.released_at})")


if __name__ == "__main__":
    main()
