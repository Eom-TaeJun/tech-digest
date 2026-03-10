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
import yaml

KST = timezone(timedelta(hours=9))
UTC = timezone.utc
TODAY = datetime.now(KST).strftime("%Y-%m-%d")
DEFAULT_LOOKBACK_DAYS = 14
DEFAULT_DATE_SEARCH_CHARS = 6000
DEFAULT_MODEL_SEARCH_CHARS = 8000

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
    is_within_lookback: bool = True
    selection_reason: str = "recent"


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


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


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


def unique_preserving_order(items: list[str]) -> list[str]:
    seen = set()
    unique = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique


def extract_models_from_patterns(text: str, patterns: list[str]) -> list[str]:
    found = []
    seen = set()
    for pattern in patterns:
        for model in extract_models(text, pattern):
            key = model.lower()
            if key in seen:
                continue
            seen.add(key)
            found.append(model)
    return found


def has_release_signal(text: str, patterns: list[str]) -> bool:
    if not patterns:
        return True
    return any(re.search(pattern, text, flags=re.I) for pattern in patterns)


def parse_iso_date(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str).replace(tzinfo=UTC)


def normalize_api_model_name(model_id: str, normalize_cfg: dict) -> str:
    normalized = model_id.strip()
    if normalize_cfg.get("strip_date_suffix"):
        normalized = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", normalized)
    if normalize_cfg.get("strip_latest_suffix"):
        normalized = re.sub(r"-latest$", "", normalized)
    return normalized


def dedupe_vendor_models(items: list[OfficialRelease]) -> list[OfficialRelease]:
    best_by_key: dict[tuple[str, str], OfficialRelease] = {}
    for item in items:
        key = (item.company.lower(), item.model.lower())
        current = best_by_key.get(key)
        if current is None:
            best_by_key[key] = item
            continue
        current_date = parse_iso_date(current.released_at)
        item_date = parse_iso_date(item.released_at)
        if item_date > current_date:
            best_by_key[key] = item
    return sorted(
        best_by_key.values(),
        key=lambda x: (x.released_at, x.company.lower(), x.model.lower()),
        reverse=True,
    )


def select_vendor_releases(
    vendor: dict,
    releases: list[OfficialRelease],
    cutoff: datetime,
    include_latest_if_no_recent: bool,
    latest_per_vendor: int,
) -> list[OfficialRelease]:
    deduped = dedupe_vendor_models(releases)
    recent = []
    older = []
    for item in deduped:
        release_date = parse_iso_date(item.released_at)
        if release_date >= cutoff:
            item.is_within_lookback = True
            item.selection_reason = "recent"
            recent.append(item)
        else:
            item.is_within_lookback = False
            item.selection_reason = "latest-known"
            older.append(item)

    if recent or not include_latest_if_no_recent:
        return recent
    return older[:latest_per_vendor]


def collect_vendor_releases(
    vendor: dict,
    cutoff: datetime,
    date_search_chars: int,
    model_search_chars: int,
) -> list[OfficialRelease]:
    company = vendor.get("company", "Unknown")
    note = vendor.get("note", "Official vendor release post")
    link_patterns = vendor.get("link_patterns", [])
    exclude_link_patterns = vendor.get("exclude_link_patterns", [])
    model_patterns = vendor.get("model_patterns", [])
    release_signal_patterns = vendor.get("release_signal_patterns", [])
    max_candidate_links = vendor.get("max_candidate_links", 20)
    candidate_links = []

    for list_url in vendor.get("list_urls", []):
        try:
            html = fetch_html(list_url)
        except requests.RequestException as exc:
            print(f"  ! {company} index fetch failed: {list_url} ({exc})")
            continue
        links = extract_same_host_links(list_url, html)
        if link_patterns:
            links = [
                link for link in links
                if any(pattern in link for pattern in link_patterns)
            ]
        if exclude_link_patterns:
            links = [
                link for link in links
                if not any(pattern in link for pattern in exclude_link_patterns)
            ]
        candidate_links.extend(links)

    releases: list[OfficialRelease] = []
    for link in unique_preserving_order(candidate_links)[:max_candidate_links]:
        try:
            page_html = fetch_html(link)
        except requests.RequestException as exc:
            print(f"  ! {company} release fetch failed: {link} ({exc})")
            continue
        text = html_to_text(page_html)
        release_date = find_date(text[:date_search_chars])
        if not release_date:
            continue
        if not has_release_signal(text[:model_search_chars], release_signal_patterns):
            continue
        models = extract_models_from_patterns(text[:model_search_chars], model_patterns)
        if not models:
            continue
        for model in models:
            releases.append(
                OfficialRelease(
                    company=company,
                    model=model,
                    released_at=release_date.date().isoformat(),
                    source_url=link.rstrip("/"),
                    note=note,
                )
            )
    return releases


def collect_api_listing_releases(vendor: dict, cutoff: datetime) -> list[OfficialRelease]:
    api_listing = vendor.get("api_listing")
    if not api_listing:
        return []

    auth_env = api_listing.get("auth_env")
    token = os.environ.get(auth_env) if auth_env else None
    if auth_env and not token:
        return []

    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.get(
            api_listing["url"],
            timeout=30,
            headers=headers,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  ! {vendor.get('company', 'Unknown')} API listing fetch failed: {exc}")
        return []

    data = resp.json().get("data", [])
    model_regex = api_listing.get("model_regex", "")
    source_url = api_listing.get("source_url", api_listing["url"])
    note = api_listing.get("note", "Official vendor API listing")
    normalize_cfg = api_listing.get("normalize", {})
    releases: list[OfficialRelease] = []

    for item in data:
        model_id = item.get("id", "")
        created = item.get("created")
        if not model_id or not created:
            continue
        if model_regex and not re.match(model_regex, model_id):
            continue
        release_date = datetime.fromtimestamp(created, tz=UTC)
        model_name = normalize_api_model_name(model_id, normalize_cfg)
        releases.append(
            OfficialRelease(
                company=vendor.get("company", "Unknown"),
                model=model_name,
                released_at=release_date.date().isoformat(),
                source_url=source_url,
                note=note,
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


def build_answer(releases: list[OfficialRelease], lookback_days: int) -> str:
    if not releases:
        return (
            "No official model releases were found on the configured official source pages "
            f"in the last {lookback_days} days."
        )

    lines = [
        "Verified official model releases from configured vendor pages:",
        "",
    ]
    for item in releases:
        if item.is_within_lookback:
            recency_note = f"release date: **{item.released_at}**"
        else:
            recency_note = (
                f"latest known official release outside lookback: **{item.released_at}**"
            )
        lines.append(
            f"- **{item.company} — {item.model}** | {recency_note} | source: {item.source_url}"
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
    config = load_config()
    official_config = config.get("official_sources", {})
    lookback_days = official_config.get("lookback_days", DEFAULT_LOOKBACK_DAYS)
    include_latest_if_no_recent = official_config.get("include_latest_if_no_recent", True)
    latest_per_vendor = official_config.get("latest_per_vendor", 1)
    date_search_chars = official_config.get("date_search_chars", DEFAULT_DATE_SEARCH_CHARS)
    model_search_chars = official_config.get("model_search_chars", DEFAULT_MODEL_SEARCH_CHARS)
    vendors = official_config.get("vendors", [])

    print(f"[{TODAY}] Official release sources fetch 시작")
    cutoff = datetime.now(UTC) - timedelta(days=lookback_days)
    releases = []
    for vendor in vendors:
        vendor_releases = collect_vendor_releases(
            vendor, cutoff, date_search_chars, model_search_chars
        )
        vendor_releases.extend(collect_api_listing_releases(vendor, cutoff))
        releases.extend(
            select_vendor_releases(
                vendor,
                vendor_releases,
                cutoff,
                include_latest_if_no_recent,
                latest_per_vendor,
            )
        )
    releases = dedupe_releases(releases)
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
        "answer": build_answer(releases, lookback_days),
        "citations": [item.source_url for item in releases],
        "model": "direct-official-fetch",
        "recency": "week",
        "evidence": {
            "domains": sorted({urlparse(item.source_url).netloc for item in releases}),
            "community_source_count": 0,
            "official_source_count": len(releases),
            "other_source_count": 0,
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
