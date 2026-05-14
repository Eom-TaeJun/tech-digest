"""
Daily Tech Digest - Step 0.8: Hacker News AI 트렌드 수집
- HN Algolia API (무료, 인증 불필요)
- AI/LLM 관련 인기 토론 수집
- 결과: raw/{date}.json의 hackernews_trending 키에 머지
"""

import json
import os
import requests
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")

HN_SEARCH_API = "https://hn.algolia.com/api/v1/search"

# AI/개발도구 관련 검색 키워드
SEARCH_QUERIES = [
    "Claude Code",
    "LLM agent",
    "AI coding",
    "MCP protocol",
]

MIN_POINTS = 20
MIN_COMMENTS = 5
LOOKBACK_HOURS = 72
HITS_PER_QUERY = 5
MAX_RESULTS = 5


def fetch_hn_stories(query: str, lookback_hours: int = LOOKBACK_HOURS) -> list[dict]:
    """HN Algolia API로 최근 인기 스토리 검색"""
    since = int((datetime.now(timezone.utc) - timedelta(hours=lookback_hours)).timestamp())
    params = {
        "query": query,
        "tags": "story",
        "numericFilters": f"created_at_i>{since},points>{MIN_POINTS}",
        "hitsPerPage": HITS_PER_QUERY,
    }
    try:
        resp = requests.get(HN_SEARCH_API, params=params, timeout=15)
        resp.raise_for_status()
        return resp.json().get("hits", [])
    except requests.RequestException as e:
        print(f"  ! HN search failed for '{query}': {e}")
        return []


def dedupe_stories(stories: list[dict]) -> list[dict]:
    """objectID 기준 중복 제거"""
    seen = set()
    unique = []
    for s in stories:
        oid = s.get("objectID")
        if oid in seen:
            continue
        seen.add(oid)
        unique.append(s)
    return unique


def collect_hn_trending() -> list[dict]:
    """여러 쿼리로 HN 스토리 수집 → 포인트 기준 정렬"""
    all_stories = []
    for query in SEARCH_QUERIES:
        stories = fetch_hn_stories(query)
        all_stories.extend(stories)
        print(f"  HN '{query}': {len(stories)}건")

    unique = dedupe_stories(all_stories)

    # 포인트 × 댓글 가중 점수로 정렬
    for s in unique:
        s["_score"] = s.get("points", 0) + s.get("num_comments", 0) * 2

    unique.sort(key=lambda x: x["_score"], reverse=True)

    results = []
    for s in unique[:MAX_RESULTS]:
        results.append({
            "title": s.get("title", ""),
            "url": s.get("url") or f"https://news.ycombinator.com/item?id={s['objectID']}",
            "hn_url": f"https://news.ycombinator.com/item?id={s['objectID']}",
            "points": s.get("points", 0),
            "comments": s.get("num_comments", 0),
            "author": s.get("author", ""),
            "created_at": s.get("created_at", ""),
            "score": s["_score"],
        })

    return results


def merge_into_raw(hn_data: list[dict], date: str) -> None:
    raw_path = f"raw/{date}.json"
    os.makedirs("raw", exist_ok=True)

    if os.path.exists(raw_path):
        with open(raw_path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"date": date, "results": {}}

    data["hackernews_trending"] = hn_data

    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  → hackernews_trending 머지 완료: {raw_path} ({len(hn_data)}건)")


def main():
    print(f"[{TODAY}] Hacker News AI 트렌드 수집 시작")

    trending = collect_hn_trending()
    merge_into_raw(trending, TODAY)

    print(f"[완료] 수집: {len(trending)}건")
    for i, s in enumerate(trending[:5], 1):
        print(f"  {i}. [{s['points']}↑ {s['comments']}💬] {s['title'][:60]}")


if __name__ == "__main__":
    main()
