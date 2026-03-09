"""
Daily Tech Digest - Step 1: Perplexity 수집
- config.yaml에서 섹션/쿼리 로드
- 결과: raw/{date}.json + digest/{date}.md
"""

import os
import json
import yaml
import requests
from urllib.parse import urlparse
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")

BASE_URL = "https://api.perplexity.ai/chat/completions"
API_KEY = os.environ["PERPLEXITY_API_KEY"]

COMMUNITY_DOMAINS = {
    "reddit.com",
    "www.reddit.com",
    "news.ycombinator.com",
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "github.com",
    "www.github.com",
}

OFFICIAL_DOMAINS = {
    "openai.com",
    "www.openai.com",
    "help.openai.com",
    "platform.openai.com",
    "anthropic.com",
    "www.anthropic.com",
    "docs.anthropic.com",
    "ai.google.dev",
    "deepmind.google",
    "blog.google",
    "developers.googleblog.com",
    "meta.com",
    "ai.meta.com",
    "mistral.ai",
    "docs.mistral.ai",
    "x.ai",
    "www.x.ai",
    "cohere.com",
    "docs.cohere.com",
}

PRACTICE_CONTEXT_QUERY_IDS = {
    "technique_md_patterns",
    "technique_agent_architecture",
    "technique_optimization",
    "technique_new_patterns",
    "vibedev_shifting_consensus",
    "vibedev_expert_vs_beginner",
    "vibedev_new_structures",
    "vibedev_real_project_outcomes",
    "community_github",
    "tools_new_rising",
    "tools_workflow_change",
}


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_query(query_text: str, config: dict) -> str:
    """config.context 변수를 쿼리 문자열에 치환. {tools}, {models} 등."""
    ctx = config.get("context", {})
    vars = {
        key: ", ".join(val) if isinstance(val, list) else str(val)
        for key, val in ctx.items()
    }
    try:
        return query_text.format(**vars)
    except KeyError:
        return query_text  # 치환 변수가 없으면 원문 그대로


def load_existing_raw(date: str) -> dict:
    path = f"raw/{date}.json"
    if not os.path.exists(path):
        return {"date": date, "results": {}}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def build_official_context(results: dict) -> str:
    official = results.get("model_release_official_watch")
    if not official:
        return ""
    answer = official.get("answer", "").strip()
    citations = official.get("citations", [])
    lines = [
        "Verified official release context from direct official-source fetch:",
        answer,
    ]
    if citations:
        lines.append("Official source URLs:")
        lines.extend(f"- {url}" for url in citations[:10])
    return "\n".join(lines)


def build_practice_context(existing_raw: dict) -> str:
    groups = existing_raw.get("practice_signals", {}).get("groups", [])
    if not groups:
        return ""

    lines = [
        "Direct high-signal practice evidence from GitHub and GitHub Discussions:",
    ]
    for group in groups[:8]:
        repos = group.get("github_repos", [])
        discussions = group.get("github_discussions", [])
        if not repos and not discussions:
            continue
        lines.append(
            f"- {group.get('label')}: source={group.get('source', 'unknown')} "
            f"discovery_score={group.get('discovery_score', 0)}"
        )
        if repos:
            repo = repos[0]
            lines.append(
                f"  GitHub repo: {repo['name']} | stars={repo['stars']} | "
                f"velocity={repo.get('star_velocity', 0)}★/day | {repo['url']}"
            )
        if discussions:
            discussion = discussions[0]
            lines.append(
                f"  GitHub Discussion: {discussion['title']} | repo={discussion.get('repository', '')} | "
                f"comments={discussion.get('comments', 0)} | upvotes={discussion.get('upvotes', 0)} | {discussion['url']}"
            )
    return "\n".join(lines)


def classify_citations(citations: list[str]) -> dict:
    domains = []
    community_count = 0
    official_count = 0

    for url in citations:
        host = urlparse(url).netloc.lower()
        if not host:
            continue
        domains.append(host)
        if host in COMMUNITY_DOMAINS:
            community_count += 1
        if host in OFFICIAL_DOMAINS:
            official_count += 1

    unique_domains = sorted(set(domains))
    return {
        "domains": unique_domains,
        "community_source_count": community_count,
        "official_source_count": official_count,
        "has_direct_community_sources": community_count > 0,
        "has_official_sources": official_count > 0,
    }


def call_perplexity(query: dict, config: dict, existing_raw: dict | None = None) -> dict:
    resolved = resolve_query(query["query"], config)
    official_context = ""
    if existing_raw and query["id"] in {
        "company_features_plugins",
        "model_new_release",
    }:
        official_context = build_official_context(existing_raw.get("results", {}))
        if official_context:
            resolved = (
                f"{official_context}\n\n"
                "Use the verified official release context above as source of truth for model/version names.\n\n"
                f"{resolved}"
            )
    if existing_raw and query["id"] in PRACTICE_CONTEXT_QUERY_IDS:
        practice_context = build_practice_context(existing_raw)
        if practice_context:
            resolved = (
                f"{practice_context}\n\n"
                "Use the direct GitHub and GitHub Discussions evidence above as higher-priority signal for "
                "emerging methodologies, patterns, guides, and practical usage. Prefer items with strong "
                "star velocity, comments, or discussion activity.\n\n"
                f"{resolved}"
            )
    recency = query.get("recency", config["perplexity"]["recency"])
    payload = {
        "model": config["perplexity"]["model"],
        "messages": [
            {"role": "system", "content": config["system_prompt"]},
            {"role": "user", "content": resolved},
        ],
        "search_recency_filter": recency,
        "return_citations": True,
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    print(f"  Querying: [{query['id']}] {query['title']}")
    resp = requests.post(BASE_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    citations = data.get("citations", [])
    evidence = classify_citations(citations)

    return {
        "id": query["id"],
        "title": query["title"],
        "query": query["query"],
        "answer": data["choices"][0]["message"]["content"],
        "citations": citations,
        "model": data.get("model", config["perplexity"]["model"]),
        "recency": recency,
        "evidence": evidence,
        "usage": data.get("usage", {}),
    }


def build_markdown(results: dict, config: dict) -> str:
    lines = [
        f"# AI Tech Digest — {TODAY}",
        "",
        f"> **수집 방식**: Perplexity {config['perplexity']['model']} / GitHub 기반 실제 사용자 신호 중심",
        "> **주의**: 이 파일은 원본 수집 결과입니다. Claude 재요약본은 별도 파일로 생성됩니다.",
        "",
        "---",
        "",
    ]

    for i, section in enumerate(config["sections"], 1):
        lines.append(f"## {i}. {section['title']}")
        lines.append("")

        for q in section["queries"]:
            if q["id"] not in results:
                continue
            r = results[q["id"]]
            lines.append(f"### {section['emoji']} {r['title']}")
            lines.append("")
            lines.append(r["answer"])
            lines.append("")

            if r.get("evidence"):
                ev = r["evidence"]
                lines.append(
                    f"> Evidence: official={ev['official_source_count']} / "
                    f"community={ev['community_source_count']} / recency={r.get('recency', config['perplexity']['recency'])}"
                )
                lines.append("")

            if r.get("citations"):
                lines.append("**Sources:**")
                for j, url in enumerate(r["citations"], 1):
                    lines.append(f"{j}. {url}")
                lines.append("")

            lines.append("---")
            lines.append("")

    lines.append(
        f"*Generated at {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')} "
        "by [tech-digest](https://github.com)*"
    )
    return "\n".join(lines)


def main():
    config = load_config()
    model = config["perplexity"]["model"]
    print(f"[{TODAY}] Daily Tech Digest 수집 시작 (model: {model})")

    all_queries = [q for section in config["sections"] for q in section["queries"]]
    existing_raw = load_existing_raw(TODAY)
    raw_results = existing_raw.get("results", {})
    for q in all_queries:
        if q["id"] in raw_results:
            print(f"    ↷ skip existing: {q['id']}")
            continue
        try:
            result = call_perplexity(q, config, existing_raw)
            raw_results[q["id"]] = result
            print(f"    ✓ {q['id']} ({result['usage'].get('total_tokens', '?')} tokens)")
        except Exception as e:
            print(f"    ✗ {q['id']}: {e}")

    raw_path = f"raw/{TODAY}.json"
    os.makedirs("raw", exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                **{k: v for k, v in existing_raw.items() if k != "results"},
                "date": TODAY,
                "model": model,
                "results": raw_results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"  → raw 저장: {raw_path}")

    md_path = f"digest/{TODAY}.md"
    os.makedirs("digest", exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_markdown(raw_results, config))
    print(f"  → digest 저장: {md_path}")

    print(f"[완료] 수집된 쿼리: {len(raw_results)}/{len(all_queries)}")


if __name__ == "__main__":
    main()
