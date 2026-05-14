"""
Daily Tech Digest - direct-source markdown renderer
- raw/{date}.json의 직접 수집 결과를 읽어 digest/{date}.md 생성
- 외부 검색/LLM API 호출 없음
"""

import json
import os
from datetime import datetime, timedelta, timezone

import yaml

from confidence_utils import classify_confidence, confidence_gate

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_raw(date: str) -> dict:
    path = f"raw/{date}.json"
    if not os.path.exists(path):
        raise FileNotFoundError(f"raw 파일 없음: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def input_limits(config: dict) -> dict:
    return config.get("summary", {}).get("input_limits", {})


def is_direct_result(result: dict) -> bool:
    source = result.get("source", "")
    if source in {"official-direct", "direct-community", "direct-practice"}:
        return True
    return str(result.get("model", "")).startswith("direct-")


def compact(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 16].rstrip() + "...(truncated)"


def append_result(lines: list[str], result: dict, config: dict) -> None:
    gate = confidence_gate(config)
    limits = input_limits(config)
    confidence = classify_confidence(result, gate)
    if confidence == "LOW" and not limits.get("include_low_confidence", False):
        return
    if not is_direct_result(result):
        return

    max_chars = {
        "HIGH": limits.get("max_answer_chars_high", 900),
        "MEDIUM": limits.get("max_answer_chars_medium", 500),
    }.get(confidence, 400)
    evidence = result.get("evidence", {})
    citations = result.get("citations", [])[: limits.get("max_citations_per_result", 2)]

    lines.append(f"## {result.get('title', result.get('id', 'Untitled'))}")
    lines.append("")
    lines.append(
        f"> confidence={confidence} | official={evidence.get('official_source_count', 0)} "
        f"| community={evidence.get('community_source_count', 0)}"
    )
    lines.append("")
    answer = compact(result.get("answer", ""), max_chars)
    if answer:
        lines.append(answer)
        lines.append("")
    if citations:
        lines.append("Sources:")
        for idx, url in enumerate(citations, 1):
            lines.append(f"{idx}. {url}")
        lines.append("")


def append_github_trending(lines: list[str], raw: dict, config: dict) -> None:
    repos = raw.get("github_trending", [])[
        : input_limits(config).get("github_trending", 5)
    ]
    if not repos:
        return
    lines.append("## GitHub Trending")
    lines.append("")
    for repo in repos:
        lines.append(
            f"- [{repo['name']}]({repo['url']}) "
            f"★{repo['stars']} | {repo.get('star_velocity', 0)}★/day | {repo.get('language', 'Unknown')}"
        )
    lines.append("")


def append_hackernews(lines: list[str], raw: dict, config: dict) -> None:
    stories = raw.get("hackernews_trending", [])[
        : input_limits(config).get("hackernews", 5)
    ]
    if not stories:
        return
    lines.append("## Hacker News")
    lines.append("")
    for story in stories:
        lines.append(
            f"- [{story['title']}]({story['hn_url']}) "
            f"↑{story.get('points', 0)} | comments={story.get('comments', 0)}"
        )
    lines.append("")


def append_practice_signals(lines: list[str], raw: dict, config: dict) -> None:
    limits = input_limits(config)
    groups = raw.get("practice_signals", {}).get("groups", [])[
        : limits.get("practice_groups", 3)
    ]
    item_limit = limits.get("practice_items_per_group", 1)
    if not groups:
        return
    lines.append("## Practice Signals")
    lines.append("")
    for group in groups:
        lines.append(f"### {group.get('label', 'Unknown')}")
        for repo in group.get("github_repos", [])[:item_limit]:
            lines.append(
                f"- Repo: [{repo['name']}]({repo['url']}) "
                f"★{repo['stars']} | {repo.get('star_velocity', 0)}★/day"
            )
        for discussion in group.get("github_discussions", [])[:item_limit]:
            lines.append(
                f"- Discussion: [{discussion['title']}]({discussion['url']}) "
                f"comments={discussion.get('comments', 0)} | upvotes={discussion.get('upvotes', 0)}"
            )
        lines.append("")


def render(raw: dict, config: dict) -> str:
    lines = [
        f"# AI Tech Digest — {TODAY}",
        "",
        "> Direct-source digest. Generated without external search/LLM collection.",
        "",
    ]

    for result in raw.get("results", {}).values():
        append_result(lines, result, config)

    append_github_trending(lines, raw, config)
    append_hackernews(lines, raw, config)
    append_practice_signals(lines, raw, config)

    lines.append(f"*Generated at {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')}*")
    return "\n".join(lines).rstrip() + "\n"


def main():
    config = load_config()
    raw = load_raw(TODAY)
    out_path = f"digest/{TODAY}.md"
    os.makedirs("digest", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(render(raw, config))
    print(f"  → digest 저장: {out_path}")


if __name__ == "__main__":
    main()
