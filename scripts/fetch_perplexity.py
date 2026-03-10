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
API_KEY = os.getenv("PERPLEXITY_API_KEY")

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


def merge_query_config(section: dict, query: dict, config: dict) -> dict:
    merged = dict(config.get("query_defaults", {}))
    merged.update(section.get("defaults", {}))
    merged.update(query)
    merged["_section_id"] = section["id"]
    merged["_section_title"] = section["title"]
    merged["_section_emoji"] = section["emoji"]
    return merged


def iter_queries(config: dict) -> list[dict]:
    return [
        merge_query_config(section, query, config)
        for section in config["sections"]
        for query in section["queries"]
    ]


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


def classify_citations(citations: list[str], allowed_domains: set[str], official_domains: set[str]) -> dict:
    domains = []
    community_count = 0
    official_count = 0
    other_count = 0

    for url in citations:
        host = urlparse(url).netloc.lower()
        if not host:
            continue
        domains.append(host)
        if host in official_domains:
            official_count += 1
        elif host in allowed_domains:
            community_count += 1
        else:
            other_count += 1

    unique_domains = sorted(set(domains))
    return {
        "domains": unique_domains,
        "community_source_count": community_count,
        "official_source_count": official_count,
        "other_source_count": other_count,
        "has_direct_community_sources": community_count > 0,
        "has_official_sources": official_count > 0,
    }


def get_domain_group(config: dict, group_name: str) -> set[str]:
    groups = config.get("source_filters", {}).get("domain_groups", {})
    return set(groups.get(group_name, []))


def allowed_domains_for_query(query: dict, config: dict) -> tuple[set[str], set[str]]:
    filters = config.get("source_filters", {})
    policy_name = query.get("source_policy", config.get("query_defaults", {}).get("source_policy", "github-only"))
    group_names = filters.get("policies", {}).get(policy_name, [])
    allowed_domains = set()
    for group_name in group_names:
        allowed_domains.update(get_domain_group(config, group_name))
    official_group = filters.get("official_group", "official_vendor")
    official_domains = get_domain_group(config, official_group)
    return allowed_domains, official_domains


def filter_citations_for_query(citations: list[str], query: dict, config: dict) -> tuple[list[str], dict]:
    allowed_domains, official_domains = allowed_domains_for_query(query, config)
    kept = []
    rejected = []
    seen = set()

    for url in citations:
        host = urlparse(url).netloc.lower()
        if not host:
            continue
        if host in allowed_domains:
            if url not in seen:
                seen.add(url)
                kept.append(url)
        else:
            rejected.append(url)

    return kept, {
        "policy": query.get("source_policy"),
        "allowed_domains": sorted(allowed_domains),
        "official_domains": sorted(official_domains),
        "rejected_count": len(rejected),
        "rejected_domains": sorted({urlparse(url).netloc.lower() for url in rejected if urlparse(url).netloc}),
    }


def call_perplexity(query: dict, config: dict, existing_raw: dict | None = None) -> dict:
    if not API_KEY:
        raise RuntimeError("PERPLEXITY_API_KEY not found in environment.")
    resolved = resolve_query(query["query"], config)
    if existing_raw and query.get("use_official_context"):
        official_context = build_official_context(existing_raw.get("results", {}))
        if official_context:
            resolved = (
                f"{official_context}\n\n"
                "Use the verified official release context above as source of truth for model/version names.\n\n"
                f"{resolved}"
            )
    if existing_raw and query.get("use_practice_context"):
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
        "max_tokens": config["perplexity"].get("max_tokens", 800),
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    print(f"  Querying: [{query['id']}] {query['title']}")
    resp = requests.post(BASE_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    raw_citations = data.get("citations", [])
    citations, source_policy = filter_citations_for_query(raw_citations, query, config)
    allowed_domains = set(source_policy["allowed_domains"])
    official_domains = set(source_policy["official_domains"])
    raw_evidence = classify_citations(raw_citations, allowed_domains, official_domains)
    evidence = classify_citations(citations, allowed_domains, official_domains)
    evidence.update(
        {
            "citation_policy": source_policy["policy"],
            "raw_other_source_count": raw_evidence.get("other_source_count", 0),
            "raw_citation_count": len(raw_citations),
            "filtered_out_citation_count": source_policy["rejected_count"],
            "filtered_out_domains": source_policy["rejected_domains"],
        }
    )

    answer = data["choices"][0]["message"]["content"]
    if raw_citations and not citations:
        answer += (
            "\n\n[Source Quality Warning] Returned citations did not include approved direct "
            "official/GitHub sources for this query, so treat this section as weak evidence."
        )

    return {
        "id": query["id"],
        "title": query["title"],
        "query": query["query"],
        "answer": answer,
        "citations": citations,
        "model": data.get("model", config["perplexity"]["model"]),
        "recency": recency,
        "evidence": evidence,
        "usage": data.get("usage", {}),
    }


def compact_markdown_answer(answer: str, max_chars: int, max_lines: int, truncation_notice: str) -> str:
    lines = [line.rstrip() for line in answer.splitlines()]
    kept = []
    char_count = 0

    for line in lines:
        projected = char_count + len(line) + (1 if kept else 0)
        if kept and len(kept) >= max_lines:
            break
        if projected > max_chars:
            remaining = max_chars - char_count
            if remaining > 40:
                kept.append(line[: remaining - 3].rstrip() + "...")
            break
        kept.append(line)
        char_count = projected

    compact = "\n".join(kept).strip()
    if compact != answer.strip():
        compact = f"{compact}\n\n{truncation_notice}".strip()
    return compact


def build_markdown(results: dict, config: dict) -> str:
    raw_md_config = config.get("rendering", {}).get("raw_markdown", {})
    max_lines = raw_md_config.get("max_answer_lines", 12)
    max_sources = raw_md_config.get("max_sources", 3)
    truncation_notice = raw_md_config.get(
        "truncation_notice",
        "[truncated in raw md; see raw JSON for full response]",
    )
    lines = [
        f"# AI Tech Digest — {TODAY}",
        "",
        f"> **수집 방식**: Perplexity {config['perplexity']['model']} + direct fetch merge",
        "> **주의**: 이 파일은 읽기용 압축본입니다. 전체 응답은 raw JSON, 핵심 요약은 summary 파일을 확인하세요.",
        "",
        "---",
        "",
    ]

    merged_queries = iter_queries(config)
    for i, section in enumerate(config["sections"], 1):
        lines.append(f"## {i}. {section['title']}")
        lines.append("")

        for q in [item for item in merged_queries if item["_section_id"] == section["id"]]:
            if q["id"] not in results:
                continue
            r = results[q["id"]]
            lines.append(f"### {section['emoji']} {r['title']}")
            lines.append("")
            lines.append(
                compact_markdown_answer(
                    r["answer"],
                    q.get("raw_markdown_chars", config.get("query_defaults", {}).get("raw_markdown_chars", 700)),
                    max_lines,
                    truncation_notice,
                )
            )
            lines.append("")

            if r.get("evidence"):
                ev = r["evidence"]
                lines.append(
                    f"> Evidence: official={ev['official_source_count']} / "
                    f"community={ev['community_source_count']} / "
                    f"other={ev.get('other_source_count', 0)} / "
                    f"filtered={ev.get('filtered_out_citation_count', 0)} / "
                    f"recency={r.get('recency', config['perplexity']['recency'])}"
                )
                lines.append("")

            if r.get("citations"):
                lines.append("**Sources:**")
                for j, url in enumerate(r["citations"][:max_sources], 1):
                    lines.append(f"{j}. {url}")
                if len(r["citations"]) > max_sources:
                    lines.append(f"- ... {len(r['citations']) - max_sources} more")
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

    all_queries = iter_queries(config)
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
