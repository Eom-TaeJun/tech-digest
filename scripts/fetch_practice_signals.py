"""
Daily Tech Digest - Step 0.75: 직접 방법론/활용 신호 수집
- GitHub/GitHub Discussions에서 방법론, harness, skills, MCP 패턴을 직접 수집
- 별/댓글/업보트 기반으로 높은 신호만 남겨 raw/{date}.json에 저장
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone

import requests
import yaml

KST = timezone(timedelta(hours=9))
UTC = timezone.utc
TODAY = datetime.now(KST).strftime("%Y-%m-%d")
LOOKBACK_DAYS = 7

GITHUB_SEARCH_API = "https://api.github.com/search/repositories"
GITHUB_GRAPHQL_API = "https://api.github.com/graphql"

MIN_REPO_STARS = 10
MIN_DISCUSSION_UPVOTES = 1
MIN_DISCUSSION_COMMENTS = 1
REQUEST_TIMEOUT = 20

FALLBACK_GROUPS = [
    {
        "id": "harness_engineering",
        "label": "Harness Engineering",
        "terms": ["agent harness", "eval harness", "coding harness", "test harness"],
    },
    {
        "id": "agent_skills",
        "label": "AI Agent Skills",
        "terms": ["agent skills", "claude code skill", "codex skill", "subagents"],
    },
    {
        "id": "agents_md",
        "label": "AGENTS.md / CLAUDE.md Patterns",
        "terms": ["AGENTS.md", "CLAUDE.md", "agents md", "claude md"],
    },
    {
        "id": "mcp_patterns",
        "label": "Model Context Protocol",
        "terms": ["Model Context Protocol", "MCP server", "MCP"],
    },
    {
        "id": "spec_driven",
        "label": "Spec-Driven Development",
        "terms": ["spec-driven development", "spec first", "spec-driven"],
    },
]

ANCHOR_WORDS = {
    "agent",
    "agents",
    "subagent",
    "subagents",
    "mcp",
    "protocol",
    "context",
    "prompt",
    "workflow",
    "workflows",
    "harness",
    "eval",
    "evals",
    "skill",
    "skills",
    "spec",
    "memory",
    "orchestration",
    "claude",
    "codex",
    "cursor",
}

STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "from",
    "that",
    "this",
    "your",
    "into",
    "using",
    "build",
    "built",
    "open",
    "source",
    "tool",
    "tools",
    "framework",
    "frameworks",
    "developer",
    "developers",
    "coding",
    "code",
    "project",
    "projects",
    "new",
    "latest",
    "best",
    "real",
    "practical",
}

GENERIC_PHRASES = {
    "agent",
    "agents",
    "ai agent",
    "skill",
    "skills",
    "agent skill",
    "agent skills",
    "ai agent skill",
    "ai agent skills",
    "workflow",
    "workflows",
    "context",
    "prompt",
}

BUCKET_RULES = [
    ("AGENTS.md / CLAUDE.md Patterns", ("agents.md", "claude.md")),
    ("Model Context Protocol", ("mcp", "model context protocol", "mcp server")),
    ("Harness / Eval Patterns", ("harness", "eval")),
    ("AI Agent Skills", ("skill", "subagent")),
    ("Spec-Driven Development", ("spec", "spec-driven")),
    ("Context Engineering", ("context engineering", "memory", "context")),
    ("Agent Workflow / Orchestration", ("workflow", "orchestration")),
]

GITHUB_DISCUSSION_QUERY = """
query($query:String!) {
  search(query:$query, type:DISCUSSION, first:8) {
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


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def configured_groups(config: dict) -> list[dict]:
    github = config.get("github", {})
    groups = []
    for raw_group in github.get("practice_signal_groups", []):
        label = raw_group.get("label") or raw_group.get("id") or "Unnamed"
        terms = [term for term in raw_group.get("terms", []) if term]
        if not terms:
            continue
        groups.append(
            {
                "id": raw_group.get("id") or slugify(label)[:40],
                "label": label,
                "terms": terms,
                "source": "configured",
                "score": 0.0,
                "require_any": raw_group.get("require_any", []),
                "exclude_any": raw_group.get("exclude_any", []),
            }
        )
    return groups


def load_raw() -> dict:
    path = os.path.join("raw", f"{TODAY}.json")
    if not os.path.exists(path):
        return {"date": TODAY, "results": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_raw(data: dict) -> None:
    os.makedirs("raw", exist_ok=True)
    path = os.path.join("raw", f"{TODAY}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())


def group_text_matches(text: str, keywords: list[str]) -> bool:
    return any(term_matches_text(text, keyword) for keyword in keywords)


def term_matches_text(text: str, term: str) -> bool:
    hay = text.lower()
    compact = slugify(hay)
    term_compact = slugify(term)
    if term_compact and term_compact in compact:
        return True
    tokens = [t for t in re.split(r"[^a-z0-9]+", term.lower()) if len(t) > 1]
    return bool(tokens) and all(token in hay for token in tokens)


def normalize_phrase(text: str) -> str:
    text = text.strip().replace("-", " ").replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"^ai\s+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bskills\b", "skill", text, flags=re.IGNORECASE)
    text = re.sub(r"\bagents\b", "agent", text, flags=re.IGNORECASE)
    text = re.sub(r"\bworkflows\b", "workflow", text, flags=re.IGNORECASE)
    return text


def is_interesting_phrase(phrase: str) -> bool:
    normalized = normalize_phrase(phrase)
    lowered = normalized.lower()
    if not lowered or len(lowered) < 3:
        return False
    if lowered in STOPWORDS:
        return False
    if lowered in GENERIC_PHRASES:
        return False
    if lowered.endswith(".md"):
        return True
    tokens = [t for t in re.split(r"[^a-z0-9.+#]+", lowered) if t]
    if not tokens:
        return False
    if len(tokens) > 3:
        return False
    if any(token in STOPWORDS for token in tokens):
        return False
    if len(tokens) == 1 and tokens[0] not in {"mcp", "subagent", "harness"}:
        return False
    return any(token in ANCHOR_WORDS for token in tokens)


def extract_phrases_from_text(text: str) -> set[str]:
    phrases = set()
    if not text:
        return phrases

    for match in re.findall(r"\b[A-Z][A-Z0-9.+/-]{1,12}(?:\.md)?\b", text):
        if is_interesting_phrase(match):
            phrases.add(normalize_phrase(match))

    patterns = [
        r"\b[A-Za-z0-9.+#/-]{2,20}\.md\b",
        r"\b(?:MCP|AGENTS\.md|CLAUDE\.md|spec-driven development|context engineering|model context protocol|subagents?|eval harness|agent harness)\b",
    ]
    for pattern in patterns:
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            phrase = normalize_phrase(match)
            if is_interesting_phrase(phrase):
                phrases.add(phrase)
    return phrases


def discover_dynamic_groups(raw: dict) -> list[dict]:
    scored: dict[str, dict] = {}
    for repo in raw.get("github_trending", []):
        phrases = set()
        for topic in repo.get("topics", []):
            phrase = normalize_phrase(topic)
            if is_interesting_phrase(phrase):
                phrases.add(phrase)
        phrases.update(extract_phrases_from_text(repo.get("name", "")))
        phrases.update(extract_phrases_from_text(repo.get("description", "")))

        for phrase in phrases:
            bucket_name = bucket_for_phrase(phrase)
            if not bucket_name:
                continue
            bucket = scored.setdefault(
                bucket_name,
                {
                    "score": 0.0,
                    "repo_refs": 0,
                    "label": bucket_name,
                    "terms": set(),
                },
            )
            bucket["score"] += repo.get("star_velocity", 0) + repo.get("stars", 0) / 100
            bucket["repo_refs"] += 1
            bucket["terms"].add(phrase)

    ranked = sorted(
        scored.values(),
        key=lambda x: (x["repo_refs"], x["score"], x["label"].lower()),
        reverse=True,
    )
    groups = []
    seen = set()
    for item in ranked:
        label = item["label"]
        if label.lower() in seen:
            continue
        seen.add(label.lower())
        groups.append(
            {
                "id": slugify(label)[:40],
                "label": label,
                "terms": [label] + sorted(item["terms"])[:2],
                "source": "dynamic",
                "score": round(item["score"], 1),
            }
        )
        if len(groups) >= 5:
            break
    return groups


def bucket_for_phrase(phrase: str) -> str | None:
    lowered = normalize_phrase(phrase).lower()
    for label, matches in BUCKET_RULES:
        if any(match in lowered for match in matches):
            return label
    return None


def github_headers() -> dict:
    headers = {"Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def safe_get(url: str, **kwargs):
    try:
        return requests.get(url, **kwargs)
    except requests.RequestException as exc:
        print(f"    ! GET failed: {url} ({exc})")
        return None


def safe_post(url: str, **kwargs):
    try:
        return requests.post(url, **kwargs)
    except requests.RequestException as exc:
        print(f"    ! POST failed: {url} ({exc})")
        return None


def repo_matches_group(item: dict, term: str, group: dict) -> bool:
    searchable = " ".join(
        [
            item.get("full_name", ""),
            item.get("name", ""),
            item.get("description") or "",
            " ".join(item.get("topics", [])),
        ]
    )
    if not term_matches_text(searchable, term):
        return False

    require_any = group.get("require_any", [])
    exclude_any = group.get("exclude_any", [])
    if require_any and not group_text_matches(searchable, require_any):
        return False
    if exclude_any and group_text_matches(searchable, exclude_any):
        return False
    return True


def discussion_matches_group(title: str, body: str, repository: str, term: str, group: dict) -> bool:
    searchable = f"{title} {body} {repository}"
    if not term_matches_text(searchable, term):
        return False

    require_any = group.get("require_any", [])
    exclude_any = group.get("exclude_any", [])
    if require_any and not group_text_matches(searchable, require_any):
        return False
    if exclude_any and group_text_matches(searchable, exclude_any):
        return False
    return True


def fetch_github_repos(term: str, group: dict) -> list[dict]:
    since = (datetime.now(UTC) - timedelta(days=30)).strftime("%Y-%m-%d")
    resp = safe_get(
        GITHUB_SEARCH_API,
        timeout=REQUEST_TIMEOUT,
        headers=github_headers(),
        params={
            "q": f'"{term}" pushed:>={since} stars:>={MIN_REPO_STARS}',
            "sort": "stars",
            "order": "desc",
            "per_page": 8,
        },
    )
    if resp is None:
        return []
    if resp.status_code == 429:
        print(f"    ! GitHub repo rate limited for term: {term}")
        return []
    resp.raise_for_status()
    items = resp.json().get("items", [])

    results = []
    now = datetime.now(UTC)
    for item in items:
        if not repo_matches_group(item, term, group):
            continue
        created = datetime.fromisoformat(item["created_at"].replace("Z", "+00:00"))
        days_old = max((now - created).total_seconds() / 86400, 0.1)
        results.append(
            {
                "source": "github_repo",
                "term": term,
                "group_id": group.get("id", ""),
                "name": item["full_name"],
                "title": item["full_name"],
                "description": item.get("description") or "",
                "url": item["html_url"],
                "stars": item["stargazers_count"],
                "forks": item["forks_count"],
                "topics": item.get("topics", []),
                "created_at": item["created_at"],
                "updated_at": item["updated_at"],
                "star_velocity": round(item["stargazers_count"] / days_old, 1),
            }
        )
    return results


def fetch_github_discussions(term: str, group: dict) -> list[dict]:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        return []
    since = (datetime.now(UTC) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    resp = safe_post(
        GITHUB_GRAPHQL_API,
        timeout=REQUEST_TIMEOUT,
        headers=github_headers(),
        json={
            "query": GITHUB_DISCUSSION_QUERY,
            "variables": {"query": f'"{term}" created:>={since} sort:updated-desc'},
        },
    )
    if resp is None:
        return []
    if resp.status_code == 429:
        print(f"    ! GitHub discussion rate limited for term: {term}")
        return []
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("errors"):
        raise RuntimeError(f"GitHub GraphQL error: {payload['errors']}")

    results = []
    for edge in payload.get("data", {}).get("search", {}).get("edges", []):
        node = edge.get("node") or {}
        title = node.get("title") or ""
        body = node.get("bodyText") or ""
        repository = (node.get("repository") or {}).get("nameWithOwner", "")
        if not discussion_matches_group(title, body, repository, term, group):
            continue
        results.append(
            {
                "source": "github_discussion",
                "term": term,
                "group_id": group.get("id", ""),
                "title": title,
                "url": node.get("url"),
                "repository": repository,
                "comments": node.get("comments", {}).get("totalCount", 0),
                "upvotes": node.get("upvoteCount", 0),
                "author": (node.get("author") or {}).get("login", ""),
                "created_at": node.get("createdAt") or "",
            }
        )
    return results


def rank_repos(items: list[dict]) -> list[dict]:
    seen = set()
    ranked = []
    for item in sorted(
        items,
        key=lambda x: (x.get("star_velocity", 0), x.get("stars", 0), x.get("updated_at", "")),
        reverse=True,
    ):
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        ranked.append(item)
    return ranked


def rank_posts(items: list[dict], score_keys: tuple[str, ...]) -> list[dict]:
    seen = set()
    ranked = []
    for item in sorted(
        items,
        key=lambda x: tuple(x.get(k, 0) for k in score_keys) + (x.get("created_at", ""),),
        reverse=True,
    ):
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        ranked.append(item)
    return ranked


def summarize_groups(groups: list[dict]) -> tuple[str, list[str], dict]:
    lines = [
        "Direct practice/methodology signals from GitHub repos and GitHub Discussions.",
        "",
    ]
    citations = []
    total_items = 0

    for group in groups:
        repo_count = len(group["github_repos"])
        discussion_count = len(group["github_discussions"])
        total_items += repo_count + discussion_count

        lines.append(f"### {group['label']}")
        lines.append(f"- Tracked queries: {', '.join(group['terms'])}")
        lines.append(
            f"- Signal counts: GitHub repos={repo_count}, GitHub Discussions={discussion_count}"
        )

        if group["github_repos"]:
            top_repo = group["github_repos"][0]
            lines.append(
                f"- Repo: {top_repo['name']} | stars={top_repo['stars']} | velocity={top_repo['star_velocity']}★/day | {top_repo['url']}"
            )
            citations.append(top_repo["url"])
        if group["github_discussions"]:
            top_discussion = group["github_discussions"][0]
            lines.append(
                f"- GitHub Discussions: {top_discussion['title']} | repo={top_discussion['repository']} | comments={top_discussion['comments']} | upvotes={top_discussion['upvotes']} | {top_discussion['url']}"
            )
            citations.append(top_discussion["url"])
        lines.append("")

    evidence = {
        "domains": sorted({requests.utils.urlparse(url).netloc for url in citations}),
        "community_source_count": total_items,
        "official_source_count": 0,
        "has_direct_community_sources": total_items > 0,
        "has_official_sources": False,
    }
    return "\n".join(lines).strip(), citations[:30], evidence


def main():
    print(f"[{TODAY}] Direct practice signals fetch 시작")
    config = load_config()
    raw = load_raw()

    static_groups = configured_groups(config)
    dynamic_groups = discover_dynamic_groups(raw)
    fallback_groups = [
        {**group, "source": "fallback", "score": 0.0} for group in FALLBACK_GROUPS
    ]

    groups_to_scan = []
    seen_ids = set()
    seen_labels = set()
    for group in static_groups:
        gid = group["id"]
        label = group["label"].lower()
        if gid in seen_ids or label in seen_labels:
            continue
        seen_ids.add(gid)
        seen_labels.add(label)
        groups_to_scan.append(group)

    for group in dynamic_groups:
        gid = group["id"]
        label = group["label"].lower()
        if gid in seen_ids or label in seen_labels:
            continue
        seen_ids.add(gid)
        seen_labels.add(label)
        groups_to_scan.append(group)
        if len(groups_to_scan) >= max(5, len(static_groups) + 3):
            break

    for group in fallback_groups:
        if len(groups_to_scan) >= max(7, len(static_groups) + 5):
            break
        gid = group["id"]
        label = group["label"].lower()
        if gid in seen_ids or label in seen_labels:
            continue
        seen_ids.add(gid)
        seen_labels.add(label)
        groups_to_scan.append(group)

    groups = []
    for group in groups_to_scan:
        github_repos = []
        github_discussions = []

        for term in group["terms"]:
            github_repos.extend(fetch_github_repos(term, group))
            github_discussions.extend(fetch_github_discussions(term, group))

        github_repos = [
            item for item in rank_repos(github_repos) if item["stars"] >= MIN_REPO_STARS
        ][:5]
        github_discussions = [
            item
            for item in rank_posts(github_discussions, ("comments", "upvotes"))
            if item["comments"] >= MIN_DISCUSSION_COMMENTS
            or item["upvotes"] >= MIN_DISCUSSION_UPVOTES
        ][:5]

        groups.append(
            {
                "id": group["id"],
                "label": group["label"],
                "terms": group["terms"],
                "source": group.get("source", "fallback"),
                "discovery_score": group.get("score", 0.0),
                "github_repos": github_repos,
                "github_discussions": github_discussions,
            }
        )
        print(
            f"  → {group['label']} ({group.get('source', 'fallback')}): repos={len(github_repos)} "
            f"discussions={len(github_discussions)}"
        )

    answer, citations, evidence = summarize_groups(groups)
    raw["practice_signals"] = {
        "groups": groups,
        "configured_groups": static_groups,
    }

    results = raw.setdefault("results", {})
    results["community_practice_signals"] = {
        "id": "community_practice_signals",
        "title": "직접 커뮤니티 방법론 신호",
        "query": "Direct GitHub/GitHub Discussions signals for AI engineering methodologies",
        "answer": answer,
        "citations": citations,
        "model": "direct-practice-fetch",
        "recency": "week",
        "evidence": evidence,
        "usage": {},
        "source": "direct-practice",
    }

    save_raw(raw)
    print(f"  → raw 업데이트: raw/{TODAY}.json")


if __name__ == "__main__":
    main()
