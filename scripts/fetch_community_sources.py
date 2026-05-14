"""
Daily Tech Digest - Step 1.5: 직접 커뮤니티 반응 수집
- 공식 릴리즈 결과를 기준으로 GitHub Discussions 직접 검색
- 결과: raw/{date}.json 의 model_new_release를 직접 커뮤니티 데이터로 대체
"""

import json
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

import requests

KST = timezone(timedelta(hours=9))
UTC = timezone.utc
TODAY = datetime.now(KST).strftime("%Y-%m-%d")
LOOKBACK_DAYS = 7
GITHUB_GRAPHQL_API = "https://api.github.com/graphql"
MIN_GH_DISCUSSION_COMMENTS = 1
MIN_GH_DISCUSSION_UPVOTES = 1
MAX_RELEASE_FAMILIES = 2
MAX_DISCUSSIONS_PER_FAMILY = 3
MAX_CITATIONS = 10
GITHUB_DISCUSSION_QUERY = """
query($query:String!) {
  search(query:$query, type:DISCUSSION, first:5) {
    edges {
      node {
        ... on Discussion {
          title
          bodyText
          url
          createdAt
          upvoteCount
          comments(first: 0) {
            totalCount
          }
          repository {
            nameWithOwner
          }
          author {
            login
          }
        }
      }
    }
  }
}
"""


def load_raw() -> dict:
    path = os.path.join("raw", f"{TODAY}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"raw 파일 없음: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_raw(data: dict) -> None:
    path = os.path.join("raw", f"{TODAY}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def extract_release_families(official_releases: list[dict]) -> list[dict]:
    cutoff = datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)
    families: dict[str, dict] = {}

    for item in official_releases:
        company = item.get("company", "")
        model = item.get("model", "")
        released_at = item.get("released_at")
        if not company or not model or not released_at:
            continue
        dt = datetime.fromisoformat(released_at).replace(tzinfo=UTC)
        if dt < cutoff:
            continue

        family = normalize_family(model)
        current = families.get(family)
        if not current or current["released_at"] < released_at:
            families[family] = {
                "company": company,
                "family": family,
                "model": model,
                "released_at": released_at,
            }

    return sorted(
        families.values(), key=lambda x: x["released_at"], reverse=True
    )[:MAX_RELEASE_FAMILIES]


def normalize_family(model: str) -> str:
    if model.startswith("gpt-5.4-pro"):
        return "gpt-5.4-pro"
    if model.startswith("gpt-5.4"):
        return "gpt-5.4"
    if model.startswith("gpt-5.3"):
        return "gpt-5.3"
    return re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model)


def query_terms(family: str) -> list[str]:
    terms = [family]
    if family.startswith("gpt-"):
        terms.append(family.replace("-", " ").upper())
    return list(dict.fromkeys(terms))


def family_tokens(family: str) -> list[str]:
    return [tok for tok in re.split(r"[^a-z0-9]+", family.lower()) if tok]


def text_matches_family(text: str, family: str) -> bool:
    hay = text.lower()
    compact = re.sub(r"[^a-z0-9]+", "", hay)
    family_compact = re.sub(r"[^a-z0-9]+", "", family.lower())
    if family_compact in compact:
        return True
    tokens = family_tokens(family)
    return all(tok in hay for tok in tokens)


def title_matches_family(title: str, family: str) -> bool:
    title_lower = title.lower()
    normalized = re.sub(r"[_/]+", " ", title_lower)
    gpt54_pattern = r"\b(?:chatgpt|gpt)\s*[- ]?5(?:[.\- ]?4)\b|\bgpt54\b"
    gpt54_pro_pattern = (
        r"\b(?:chatgpt|gpt)\s*[- ]?5(?:[.\- ]?4)\b.{0,24}\bpro\b|\bgpt54pro\b"
    )

    if family == "gpt-5.4-pro":
        return bool(re.search(gpt54_pro_pattern, normalized))
    if family == "gpt-5.4":
        return bool(re.search(gpt54_pattern, normalized)) and not bool(
            re.search(gpt54_pro_pattern, normalized)
        )
    return text_matches_family(title, family)


def fetch_github_discussions(query: str) -> list[dict]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return []

    since = (datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    search_query = f'"{query}" created:>={since} sort:updated-desc'
    resp = requests.post(
        GITHUB_GRAPHQL_API,
        timeout=30,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        },
        json={
            "query": GITHUB_DISCUSSION_QUERY,
            "variables": {"query": search_query},
        },
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {payload['errors']}")

    results = []
    for edge in payload.get("data", {}).get("search", {}).get("edges", []):
        node = edge.get("node") or {}
        if not node.get("url"):
            continue
        results.append(
            {
                "source": "github_discussion",
                "query": query,
                "title": node.get("title") or "(no title)",
                "url": node["url"],
                "comments": node.get("comments", {}).get("totalCount", 0),
                "upvotes": node.get("upvoteCount", 0),
                "author": (node.get("author") or {}).get("login", ""),
                "repository": (node.get("repository") or {}).get("nameWithOwner", ""),
                "created_at": node.get("createdAt") or "",
                "text": (node.get("bodyText") or "")[:500],
            }
        )
    return results


def filter_github_discussion_items(items: list[dict], family: str) -> list[dict]:
    filtered = []
    for item in items:
        title = item.get("title", "")
        if not title_matches_family(title, family):
            continue
        if (
            item.get("comments", 0) < MIN_GH_DISCUSSION_COMMENTS
            and item.get("upvotes", 0) < MIN_GH_DISCUSSION_UPVOTES
        ):
            continue
        filtered.append(item)
    return filtered


def rank_items(items: list[dict]) -> list[dict]:
    def exactness(item: dict) -> int:
        query = item.get("query", "")
        searchable = f"{item.get('title', '')} {item.get('text', '')}"
        return 1 if text_matches_family(searchable, query) else 0

    def score(item: dict) -> tuple:
        return (
            exactness(item),
            item.get("comments", 0),
            item.get("points", 0) + item.get("score", 0) + item.get("upvotes", 0),
            item.get("created_at", ""),
        )

    seen = set()
    ranked = []
    for item in sorted(items, key=score, reverse=True):
        url = item["url"]
        if url in seen:
            continue
        seen.add(url)
        ranked.append(item)
    return ranked


def build_answer(families: list[dict], grouped_items: dict[str, list[dict]]) -> str:
    lines = [
        "Direct community reactions collected from GitHub Discussions.",
        "",
    ]
    for family in families:
        key = family["family"]
        items = grouped_items.get(key, [])
        gh_count = sum(1 for item in items if item["source"] == "github_discussion")
        lines.append(
            f"### {key} (official release: {family['released_at']})"
        )
        lines.append(
            f"- Direct source counts: GitHub Discussions={gh_count}"
        )
        if not items:
            lines.append(
                "- No direct GitHub Discussions posts found in current search results. Community reaction remains unconfirmed."
            )
            lines.append("")
            continue

        for item in items[:MAX_DISCUSSIONS_PER_FAMILY]:
            lines.append(
                f"- [GitHub Discussions/{item.get('repository', '')}] {item['title']} | comments={item.get('comments', 0)} | upvotes={item.get('upvotes', 0)} | {item['url']}"
            )
        lines.append("")

    lines.append(
        "Use this direct community list for first-impression evidence. If counts are low, state that reaction coverage is weak."
    )
    return "\n".join(lines)


def summarize_sources(items: list[dict]) -> dict:
    domains = sorted({urlparse(item["url"]).netloc for item in items})
    return {
        "domains": domains,
        "community_source_count": len(items),
        "official_source_count": 0,
        "has_direct_community_sources": bool(items),
        "has_official_sources": False,
    }


def main():
    print(f"[{TODAY}] Direct community fetch 시작")
    data = load_raw()
    official_releases = data.get("official_releases", [])
    families = extract_release_families(official_releases)
    print(f"  → release families: {[f['family'] for f in families]}")

    grouped_items: dict[str, list[dict]] = defaultdict(list)
    for family in families:
        key = family["family"]
        collected = []
        for term in query_terms(key):
            collected.extend(
                filter_github_discussion_items(fetch_github_discussions(term), key)
            )
        grouped_items[key] = rank_items(collected)
        print(f"    {key}: {len(grouped_items[key])} direct items")

    all_items = [item for items in grouped_items.values() for item in items]
    answer = build_answer(families, grouped_items)
    citations = [item["url"] for item in all_items[:MAX_CITATIONS]]

    results = data.setdefault("results", {})
    if "model_new_release" in results:
        results["model_new_release_previous_backup"] = results["model_new_release"]

    results["model_new_release"] = {
        "id": "model_new_release",
        "title": "신규 모델 릴리즈 — 커뮤니티 즉각 반응",
        "query": "Direct community fetch from GitHub Discussions",
        "answer": answer,
        "citations": citations,
        "model": "direct-community-fetch",
        "recency": "week",
        "evidence": summarize_sources(all_items),
        "usage": {},
        "source": "direct-community",
    }
    data["community_release_reactions"] = {
        family["family"]: grouped_items.get(family["family"], [])
        for family in families
    }
    save_raw(data)
    print(f"  → raw 업데이트: raw/{TODAY}.json")


if __name__ == "__main__":
    main()
