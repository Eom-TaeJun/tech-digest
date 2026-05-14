"""
Daily Tech Digest - Step 0: New Concepts Discovery
- GitHub Trending 데이터에서 새로운 도구/모델/개념 자동 발견
- 외부 검색 의존 제거 → raw/{date}.json의 github_trending 기반
- config.yaml의 context 섹션을 동적으로 업데이트
"""

import os
import json
import re
import yaml
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.yaml")

# AI/개발도구 관련 여부 판별 — topics 기반 (가장 정확)
AI_TOPICS = {
    "ai", "llm", "gpt", "claude", "gemini", "agent", "mcp", "prompt",
    "embedding", "rag", "transformer", "openai", "anthropic", "langchain",
    "machine-learning", "deep-learning", "nlp", "chatbot", "copilot",
    "ai-agent", "llm-agent", "coding-assistant",
}
# description 기반 보조 키워드 (최소 2개 이상 매칭)
AI_DESC_KEYWORDS = {
    "ai", "llm", "agent", "claude", "gpt", "prompt", "model",
    "embedding", "mcp", "anthropic", "openai",
}

# 카테고리 분류용 키워드
TOOL_SIGNALS = {"tool", "framework", "cli", "sdk", "editor", "ide", "agent", "plugin", "extension", "mcp", "skill"}
MODEL_SIGNALS = {"model", "llm", "gpt", "claude", "gemini", "llama", "mistral", "deepseek", "embedding", "fine-tun"}
CONCEPT_SIGNALS = {"pattern", "methodology", "architecture", "protocol", "workflow", "paradigm", "harness"}


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)


def load_trending(date: str) -> list[dict]:
    raw_path = f"raw/{date}.json"
    if not os.path.exists(raw_path):
        return []
    with open(raw_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("github_trending", [])


def classify_repo(repo: dict) -> str:
    """레포 이름/설명/토픽에서 카테고리 추론"""
    text = f"{repo.get('name', '')} {repo.get('description', '')} {' '.join(repo.get('topics', []))}".lower()

    model_score = sum(1 for kw in MODEL_SIGNALS if kw in text)
    tool_score = sum(1 for kw in TOOL_SIGNALS if kw in text)
    concept_score = sum(1 for kw in CONCEPT_SIGNALS if kw in text)

    if model_score > tool_score and model_score > concept_score:
        return "models"
    if concept_score > tool_score:
        return "concepts"
    return "tools"


def extract_name(repo: dict) -> str:
    """레포에서 프로젝트명 추출 (org/repo → repo)"""
    name = repo.get("name", "")
    if "/" in name:
        name = name.split("/")[-1]
    return name


def is_ai_relevant(repo: dict) -> bool:
    """AI/개발도구 관련 레포인지 판별 — topics 우선, description 보조"""
    topics = {t.lower() for t in repo.get("topics", [])}
    if topics & AI_TOPICS:
        return True
    # topics 없으면 description에서 키워드 2개 이상 매칭
    desc = f"{repo.get('name', '')} {repo.get('description', '')}".lower()
    matches = sum(1 for kw in AI_DESC_KEYWORDS if kw in desc)
    return matches >= 2


def discover_from_trending(trending: list[dict], config: dict) -> dict:
    """GitHub Trending 데이터에서 새 아이템 발견"""
    existing = {
        "tools": set(config["context"].get("tools", [])),
        "models": set(config["context"].get("models", [])),
        "concepts": set(config["context"].get("concepts", [])),
    }

    new_items = {"tools": [], "models": [], "concepts": []}

    for repo in trending:
        velocity = repo.get("star_velocity", 0)
        if velocity < 200:  # 높은 기준으로 노이즈 제거
            continue

        if not is_ai_relevant(repo):
            continue

        name = extract_name(repo)
        category = classify_repo(repo)

        # 기존 context에 이미 있는지 체크 (대소문자 무시)
        existing_lower = {item.lower() for item in existing[category]}
        if name.lower() in existing_lower:
            continue

        new_items[category].append(name)

    return new_items


def main():
    config = load_config()

    # 먼저 오늘의 GitHub trending 데이터 확인
    trending = load_trending(TODAY)

    if not trending:
        print(f"[{TODAY}] GitHub Trending 데이터 없음 — Step 0.6 이후 실행 필요")
        print("Skip: discover_concepts (no trending data yet)")
        return

    print(f"[{TODAY}] GitHub Trending 기반 신규 개념 탐색 ({len(trending)}개 레포)")

    new_found = discover_from_trending(trending, config)

    updated = False
    for category in ["tools", "models", "concepts"]:
        for item in new_found[category]:
            if item and item not in config["context"][category]:
                print(f"  + New {category} found: {item}")
                config["context"][category].append(item)
                updated = True

    if updated:
        save_config(config)
        print("Successfully updated config.yaml with new items.")
    else:
        print("No new significant items found this time.")


if __name__ == "__main__":
    main()
