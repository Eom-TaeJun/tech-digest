"""
Daily Tech Digest - GitHub Trending 수집
- GitHub Search API로 최근 N일 내 급등 레포 수집
- star velocity (star/일) 기준 재정렬
- 결과: raw/{date}.json의 github_trending 키에 머지
"""

import os
import json
import yaml
import requests
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")
GITHUB_API = "https://api.github.com/search/repositories"


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def fetch_trending(config: dict) -> list[dict]:
    gh = config.get("github", {})
    lookback_days = gh.get("lookback_days", 7)
    min_stars = gh.get("min_stars", 50)
    limit = gh.get("limit", 30)
    top_n = gh.get("top_n", 15)

    since = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"

    params = {
        "q": f"created:>{since} stars:>{min_stars}",
        "sort": "stars",
        "order": "desc",
        "per_page": min(limit, 100),
    }

    print(f"  GitHub Trending 수집 중... (최근 {lookback_days}일, 최소 {min_stars}★)")
    resp = requests.get(GITHUB_API, headers=headers, params=params, timeout=30)
    resp.raise_for_status()

    items = resp.json().get("items", [])
    now = datetime.now(timezone.utc)

    results = []
    for r in items:
        created = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00"))
        days_old = max((now - created).total_seconds() / 86400, 0.1)
        stars = r["stargazers_count"]
        velocity = round(stars / days_old, 1)

        results.append({
            "name": r["full_name"],
            "description": r.get("description") or "",
            "stars": stars,
            "forks": r["forks_count"],
            "language": r.get("language") or "Unknown",
            "url": r["html_url"],
            "created_at": r["created_at"],
            "days_old": round(days_old, 1),
            "star_velocity": velocity,
            "topics": r.get("topics", []),
        })

    # star velocity 기준 재정렬
    results.sort(key=lambda x: x["star_velocity"], reverse=True)
    return results[:top_n]


def merge_into_raw(trending: list[dict], date: str) -> None:
    raw_path = f"raw/{date}.json"
    os.makedirs("raw", exist_ok=True)

    if os.path.exists(raw_path):
        with open(raw_path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"date": date, "results": {}}

    data["github_trending"] = trending

    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  → github_trending 머지 완료: {raw_path} ({len(trending)}개 레포)")


def main():
    config = load_config()
    print(f"[{TODAY}] GitHub Trending 수집 시작")

    trending = fetch_trending(config)
    merge_into_raw(trending, TODAY)

    print(f"[완료] 수집된 레포: {len(trending)}개")
    for i, r in enumerate(trending[:5], 1):
        print(f"  {i}. {r['name']} ★{r['stars']} ({r['star_velocity']}★/일) — {r['description'][:60]}")


if __name__ == "__main__":
    main()
