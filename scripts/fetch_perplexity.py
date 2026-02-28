"""
Daily Tech Digest - Step 1: Perplexity 수집
- config.yaml에서 섹션/쿼리 로드
- 결과: raw/{date}.json + digest/{date}.md
"""

import os
import json
import yaml
import requests
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")

BASE_URL = "https://api.perplexity.ai/chat/completions"
API_KEY = os.environ["PERPLEXITY_API_KEY"]


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


def call_perplexity(query: dict, config: dict) -> dict:
    resolved = resolve_query(query["query"], config)
    payload = {
        "model": config["perplexity"]["model"],
        "messages": [
            {"role": "system", "content": config["system_prompt"]},
            {"role": "user", "content": resolved},
        ],
        "search_recency_filter": config["perplexity"]["recency"],
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

    return {
        "id": query["id"],
        "title": query["title"],
        "query": query["query"],
        "answer": data["choices"][0]["message"]["content"],
        "citations": data.get("citations", []),
        "model": data.get("model", config["perplexity"]["model"]),
        "usage": data.get("usage", {}),
    }


def build_markdown(results: dict, config: dict) -> str:
    lines = [
        f"# AI Tech Digest — {TODAY}",
        "",
        f"> **수집 방식**: Perplexity {config['perplexity']['model']} / 실제 커뮤니티 후기 중심 (Reddit, HN, Twitter)",
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

    raw_results = {}
    for q in all_queries:
        try:
            result = call_perplexity(q, config)
            raw_results[q["id"]] = result
            print(f"    ✓ {q['id']} ({result['usage'].get('total_tokens', '?')} tokens)")
        except Exception as e:
            print(f"    ✗ {q['id']}: {e}")

    raw_path = f"raw/{TODAY}.json"
    os.makedirs("raw", exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(
            {"date": TODAY, "model": model, "results": raw_results},
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
