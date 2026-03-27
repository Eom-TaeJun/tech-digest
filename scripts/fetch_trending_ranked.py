"""
Daily Tech Digest - fetch_trending_ranked
- 일별(1d) / 주별(7d) GitHub top 5 수집, 세 레이어 간 중복 없음
- 결과: raw/{date}.json의 trending_ranked 키에 머지

Usage:
  cd ~/projects/tech-digest
  python scripts/fetch_trending_ranked.py

Output:
  raw/{date}.json  trending_ranked 키 갱신
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")
YESTERDAY = (datetime.now(KST) - timedelta(days=1)).strftime("%Y-%m-%d")
GITHUB_API = "https://api.github.com/search/repositories"


def get_headers() -> dict:
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"token {token}"
    return headers


def load_yesterday_names() -> set:
    """전날 raw/{yesterday}.json에서 trending_ranked의 모든 레포 이름 추출."""
    raw_path = f"raw/{YESTERDAY}.json"
    if not os.path.exists(raw_path):
        return set()

    with open(raw_path, encoding="utf-8") as f:
        data = json.load(f)

    tr = data.get("trending_ranked", {})
    names = set()
    for entry in tr.get("daily_top5", []):
        names.add(entry.get("name", ""))
    for entry in tr.get("weekly_top5", []):
        names.add(entry.get("name", ""))
    names.discard("")
    return names


def search_repos(query: str, candidate_limit: int) -> list[dict]:
    """GitHub Search API 호출 후 star_velocity 계산 및 정렬."""
    params = {
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": min(candidate_limit, 100),
    }

    resp = requests.get(GITHUB_API, headers=get_headers(), params=params, timeout=30)
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
            "stars": stars,
            "star_velocity": velocity,
            "url": r["html_url"],
            "description": r.get("description") or "",
            "language": r.get("language") or "Unknown",
            "created_at": r["created_at"],
        })

    results.sort(key=lambda x: x["star_velocity"], reverse=True)
    return results


def fetch_daily_top5(yesterday_names: set) -> list[dict]:
    """
    daily_top5: created:>YESTERDAY stars:>10
    - top 10 candidates by star_velocity
    - 전날 raw에 이미 등장한 레포 제외
    - 최종 top 5
    """
    since = YESTERDAY
    print(f"  [daily] 쿼리: created:>{since} stars:>10")

    candidates = search_repos(f"created:>{since} stars:>10", candidate_limit=10)

    filtered = [r for r in candidates if r["name"] not in yesterday_names]
    return filtered[:5]


def fetch_weekly_top5(daily_names: set, yesterday_names: set) -> list[dict]:
    """
    weekly_top5: created:>7DAYS_AGO stars:>30
    - top 20 candidates by star_velocity
    - daily_top5에 이미 있는 레포 제외
    - 전날 raw에 이미 등장한 레포 제외
    - 최종 top 5
    """
    since = (datetime.now(KST) - timedelta(days=7)).strftime("%Y-%m-%d")
    print(f"  [weekly] 쿼리: created:>{since} stars:>30")

    candidates = search_repos(f"created:>{since} stars:>30", candidate_limit=20)

    exclude = daily_names | yesterday_names
    filtered = [r for r in candidates if r["name"] not in exclude]
    return filtered[:5]


def merge_into_raw(result: dict, date: str) -> None:
    raw_path = f"raw/{date}.json"
    os.makedirs("raw", exist_ok=True)

    if os.path.exists(raw_path):
        with open(raw_path, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = {"date": date, "results": {}}

    data["trending_ranked"] = result

    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"  → trending_ranked 머지 완료: {raw_path}")


def main():
    print(f"[{TODAY}] trending_ranked 수집 시작 (KST 기준)")
    print(f"  전날 기준일: {YESTERDAY}")

    yesterday_names = load_yesterday_names()
    print(f"  전날 dedup set: {len(yesterday_names)}개")

    daily = fetch_daily_top5(yesterday_names)
    daily_names = {r["name"] for r in daily}

    weekly = fetch_weekly_top5(daily_names, yesterday_names)

    excluded_count = len(yesterday_names)

    result = {
        "daily_top5": daily,
        "weekly_top5": weekly,
        "excluded_yesterday_count": excluded_count,
    }

    merge_into_raw(result, TODAY)

    print(f"\n[완료] daily_top5 {len(daily)}개 / weekly_top5 {len(weekly)}개")
    print("\n  ── daily_top5 ──")
    for i, r in enumerate(daily, 1):
        print(f"  {i}. {r['name']} ★{r['stars']} ({r['star_velocity']}★/일)")
    print("\n  ── weekly_top5 ──")
    for i, r in enumerate(weekly, 1):
        print(f"  {i}. {r['name']} ★{r['stars']} ({r['star_velocity']}★/일)")


if __name__ == "__main__":
    main()
