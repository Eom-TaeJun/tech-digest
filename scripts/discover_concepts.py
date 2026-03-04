"""
Daily Tech Digest - Step 0: New Concepts Discovery
- GitHub 스타 수 / 커뮤니티 언급량 기반 새로운 도구, 모델, 개념 자동 발견
- config.yaml의 context 섹션을 동적으로 업데이트
"""

import os
import re
import yaml
import requests
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")

BASE_URL = "https://api.perplexity.ai/chat/completions"
API_KEY = os.environ.get("PERPLEXITY_API_KEY")

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.yaml")

def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)

def discover_new_items(config: dict) -> dict:
    """Perplexity를 사용하여 새로운 아이템 발견"""
    existing_tools = config["context"].get("tools", [])
    existing_models = config["context"].get("models", [])
    existing_concepts = config["context"].get("concepts", [])
    
    prompt = f"""
    Identify the most trending NEW AI engineering tools, models, and methodology concepts from the past 7 days.
    Focus on items with high GitHub star velocity (>100 stars/day) or significant mentions on Reddit/Hacker News.
    
    EXCLUDE these items (already tracked):
    Tools: {", ".join(existing_tools)}
    Models: {", ".join(existing_models)}
    Concepts: {", ".join(existing_concepts)}
    
    Provide the response in the following JSON-like format:
    NEW_TOOLS: [item1, item2, ...]
    NEW_MODELS: [item1, item2, ...]
    NEW_CONCEPTS: [item1, item2, ...]
    
    Only include items that are genuinely new or reached a major milestone/spike this week.
    For each item, ensure it's a specific name (e.g., "OpenClaw" not "Agent Frameworks").
    """

    payload = {
        "model": "sonar-pro",
        "messages": [
            {"role": "system", "content": "You are a specialized discovery agent for AI technology trends. Extract specific names of new tools and models."},
            {"role": "user", "content": prompt},
        ],
        "search_recency_filter": "week",
    }
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    print(f"[{TODAY}] Discovering new AI concepts via Perplexity...")
    resp = requests.post(BASE_URL, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    
    new_items = {"tools": [], "models": [], "concepts": []}
    
    # 텍스트 결과에서 리스트 추출 (정규표현식 사용)
    tool_match = re.search(r"NEW_TOOLS:\s*\[(.*?)\]", content)
    model_match = re.search(r"NEW_MODELS:\s*\[(.*?)\]", content)
    concept_match = re.search(r"NEW_CONCEPTS:\s*\[(.*?)\]", content)
    
    if tool_match:
        new_items["tools"] = [i.strip().strip('"').strip("'") for i in tool_match.group(1).split(",") if i.strip()]
    if model_match:
        new_items["models"] = [i.strip().strip('"').strip("'") for i in model_match.group(1).split(",") if i.strip()]
    if concept_match:
        new_items["concepts"] = [i.strip().strip('"').strip("'") for i in concept_match.group(1).split(",") if i.strip()]
        
    return new_items

def main():
    if not API_KEY:
        print("Error: PERPLEXITY_API_KEY not found in environment.")
        return

    config = load_config()
    new_found = discover_new_items(config)
    
    updated = False
    for category in ["tools", "models", "concepts"]:
        for item in new_found[category]:
            if item and item not in config["context"][category]:
                print(f"  + New {category} found: {item}")
                config["context"][category].append(item)
                updated = True
    
    if updated:
        save_config(config)
        print(f"Successfully updated config.yaml with new items.")
    else:
        print("No new significant items found this time.")

if __name__ == "__main__":
    main()
