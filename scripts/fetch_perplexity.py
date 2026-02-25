"""
Daily Tech Digest - Step 1: Perplexity 수집
- sonar-pro 모델로 AI 커뮤니티 실사용 후기 수집
- 결과: raw/{date}.json + digest/{date}.md
"""

import os
import json
import requests
from datetime import datetime, timezone, timedelta

API_KEY = os.environ["PERPLEXITY_API_KEY"]
BASE_URL = "https://api.perplexity.ai/chat/completions"
MODEL = "sonar-pro"

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")

SYSTEM_PROMPT = """You are a researcher collecting real user opinions and experiences from developer communities.

Focus ONLY on:
- Reddit posts/comments (r/LocalLLaMA, r/programming, r/MachineLearning, r/ClaudeAI, r/cursor, r/OpenAI, r/GoogleGemini, r/singularity, r/artificial)
- Hacker News discussions and Show HN posts
- Twitter/X threads from actual developers
- GitHub Issues, Discussions, and trending repositories

Exclude:
- Official press releases and marketing copy
- Paywalled content

Include:
- Community reactions and first impressions of new model/tool releases
- Real-world usage comparisons between models (specific tasks, not benchmark scores)
- Honest frustrations, unexpected discoveries, and workflow changes

For each topic, find what real users are saying: what's working, what's frustrating, what surprised them, and why they switched.
Format your answer in clear sections with source citations."""

QUERIES = {
    "ai_workflow_change": [
        {
            "id": "workflow_agentic",
            "title": "에이전트 기반 개발 - 실제 팀 사용 경험",
            "query": "How are real developers and teams actually using AI agents to build software in 2025-2026? What changed in their daily workflow? Focus on Reddit and Hacker News discussions with honest experiences, not marketing.",
        },
        {
            "id": "workflow_vibecheck",
            "title": "바이브 코딩 / AI 주도 개발 - 솔직한 후기",
            "query": "Real developer experiences with 'vibe coding' or AI-driven development in 2026. What actually works, what fails, and how teams restructured around AI coding tools. Focus on Reddit r/LocalLLaMA, r/programming, Hacker News.",
        },
        {
            "id": "workflow_team_structure",
            "title": "AI로 인한 팀 구조 변화",
            "query": "How has AI changed software team structure and roles in 2025-2026? Are companies replacing junior developers? Real experiences from engineers on Reddit, Hacker News, or Twitter about job market and team dynamics.",
        },
    ],
    "new_tools": [
        {
            "id": "tools_cursor_vs_claude",
            "title": "Cursor vs Claude Code - 실제 전환 이유",
            "query": "Why are developers switching from Cursor to Claude Code in 2026? Real user comparisons, honest pros and cons from Reddit, Hacker News, and Twitter. What made people switch and what do they miss?",
        },
        {
            "id": "tools_landscape",
            "title": "AI 코딩 툴 전체 지형 - 커뮤니티 평가",
            "query": "What AI coding tools are developers actually recommending in 2026? Compare Claude Code, Cursor, Windsurf, Cline, Aider based on real Reddit and Hacker News community votes and honest reviews. What are the hidden pros and cons?",
        },
        {
            "id": "tools_new_rising",
            "title": "새롭게 주목받는 AI 개발 툴",
            "query": "What new AI development tools or frameworks gained the most positive community reception in the past week? Focus on GitHub trending repos with high stars, Reddit posts with high upvotes, or Hacker News Show HN with top comments. Real user reactions only.",
        },
    ],
    "model_reactions": [
        {
            "id": "model_new_release",
            "title": "신규 모델/API 릴리즈 — 커뮤니티 즉각 반응",
            "query": "What new AI models, APIs, or major updates were released or announced in the past 48 hours? What is the immediate community reaction on Reddit (r/LocalLLaMA, r/OpenAI, r/ClaudeAI, r/GoogleGemini, r/singularity), Hacker News, and Twitter? Capture first impressions, surprises, and disappointments — real user reactions only, not press releases.",
        },
        {
            "id": "model_real_perf",
            "title": "모델별 실사용 성능 — 개발자 직접 비교",
            "query": "What are developers saying about real-world differences between current AI models (Claude, GPT-4o, Gemini, Llama, Mistral, DeepSeek, etc.) this week? Focus on practical comparisons people share on Reddit r/LocalLLaMA, r/ClaudeAI, Hacker News — specific tasks where one model clearly beats another, not benchmark scores but actual 'I tried X and it did better/worse at Y than Z' experiences.",
        },
    ],
    "token_cost": [
        {
            "id": "token_reduction_tips",
            "title": "토큰 절약 — 실제 개발자 팁과 경험",
            "query": "What are developers actually doing to reduce LLM token usage and API costs in 2026? Real tips and experiences from Reddit (r/ClaudeAI, r/LocalLLaMA, r/MachineLearning), Hacker News, Twitter. Focus on practical tricks: prompt caching, CLAUDE.md optimization, context management, model routing. What surprised people? What actually worked vs. what didn't?",
        },
        {
            "id": "token_context_management",
            "title": "컨텍스트 윈도우 관리 — 커뮤니티 실전 패턴",
            "query": "How are developers managing context window limits and preventing token cost blowups in AI agent systems in 2026? Real discussions from Reddit and Hacker News about sliding windows, session summarization, AGENTS.md/CLAUDE.md sizing, and prompt compression tools like LLMLingua. What are the hidden gotchas people discovered?",
        },
    ],
}


def call_perplexity(query: dict) -> dict:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": query["query"]},
        ],
        "search_recency_filter": "day",
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
        "model": data.get("model", MODEL),
        "usage": data.get("usage", {}),
    }


def build_markdown(results: dict) -> str:
    lines = [
        f"# AI Tech Digest — {TODAY}",
        "",
        "> **수집 방식**: Perplexity sonar-pro / 실제 커뮤니티 후기 중심 (Reddit, HN, Twitter)",
        "> **주의**: 이 파일은 원본 수집 결과입니다. Claude 재요약본은 별도 파일로 생성됩니다.",
        "",
        "---",
        "",
    ]

    section_meta = {
        "ai_workflow_change": ("## 1. AI로 인한 구조/방식 변화", "🔄"),
        "new_tools": ("## 2. 새로운 AI 툴 — 커뮤니티 반응", "🛠️"),
        "model_reactions": ("## 3. 신규 모델/API — 실사용 반응", "🤖"),
        "token_cost": ("## 4. 토큰 비용 & 컨텍스트 관리", "💰"),
    }

    for section_key, queries in QUERIES.items():
        heading, emoji = section_meta[section_key]
        lines.append(f"{heading}")
        lines.append("")

        for q in queries:
            qid = q["id"]
            if qid not in results:
                continue

            r = results[qid]
            lines.append(f"### {emoji} {r['title']}")
            lines.append("")
            lines.append(r["answer"])
            lines.append("")

            if r.get("citations"):
                lines.append("**Sources:**")
                for i, url in enumerate(r["citations"], 1):
                    lines.append(f"{i}. {url}")
                lines.append("")

            lines.append("---")
            lines.append("")

    lines.append(f"*Generated at {datetime.now(KST).strftime('%Y-%m-%d %H:%M KST')} by [tech-digest](https://github.com)*")
    return "\n".join(lines)


def main():
    print(f"[{TODAY}] Daily Tech Digest 수집 시작 (model: {MODEL})")

    raw_results = {}
    all_queries = [q for qs in QUERIES.values() for q in qs]

    for q in all_queries:
        try:
            result = call_perplexity(q)
            raw_results[q["id"]] = result
            print(f"    ✓ {q['id']} ({result['usage'].get('total_tokens', '?')} tokens)")
        except Exception as e:
            print(f"    ✗ {q['id']}: {e}")

    # Step 1: raw JSON 저장
    raw_path = f"raw/{TODAY}.json"
    os.makedirs("raw", exist_ok=True)
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(
            {"date": TODAY, "model": MODEL, "results": raw_results},
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"  → raw 저장: {raw_path}")

    # Step 2: 마크다운 다이제스트 생성
    md_path = f"digest/{TODAY}.md"
    os.makedirs("digest", exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(build_markdown(raw_results))
    print(f"  → digest 저장: {md_path}")

    print(f"[완료] 수집된 쿼리: {len(raw_results)}/{len(all_queries)}")


if __name__ == "__main__":
    main()
