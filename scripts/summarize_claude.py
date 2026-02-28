"""
Daily Tech Digest - Step 2: Claude 재요약
- config.yaml에서 설정/프롬프트 로드
- raw/{date}.json 읽어서 Claude로 핵심 요약
- 결과: digest/{date}.summary.md
"""

import os
import json
import yaml
import anthropic
from datetime import datetime, timezone, timedelta

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
        data = json.load(f)
    return data["results"]


def build_prompt(results: dict, config: dict) -> str:
    lines = [
        f"아래는 오늘({TODAY}) 수집한 AI 기술 커뮤니티 반응 원본입니다.",
        "섹션별로 나눠서 한국어로 요약해주세요.",
        "",
        "---",
        "",
    ]

    for i, section in enumerate(config["sections"], 1):
        lines.append(f"## 섹션 {i}: {section['title']}")
        lines.append("")
        for q in section["queries"]:
            answer = results.get(q["id"], {}).get("answer", "(데이터 없음)")
            lines.append(f"### {q['title']}")
            lines.append(answer)
            lines.append("")
        lines.append("---")
        lines.append("")

    lines.append(config["summary"]["output_format"].format(date=TODAY))
    return "\n".join(lines)


def main():
    config = load_config()
    model = config["claude"]["model"]
    max_tokens = config["claude"]["max_tokens"]

    print(f"[{TODAY}] Claude 재요약 시작 (model: {model})")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    results = load_raw(TODAY)
    prompt = build_prompt(results, config)

    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=config["summary"]["system"],
        messages=[{"role": "user", "content": prompt}],
    )

    summary = response.content[0].text
    usage = response.usage

    out_path = f"digest/{TODAY}.summary.md"
    os.makedirs("digest", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(summary)
        f.write(
            f"\n\n---\n*Summarized by Claude ({model}) "
            f"| Input: {usage.input_tokens} / Output: {usage.output_tokens} tokens*\n"
        )

    print(f"  → 요약 저장: {out_path}")
    print(f"  → 토큰: input {usage.input_tokens} / output {usage.output_tokens}")
    print("[완료]")


if __name__ == "__main__":
    main()
