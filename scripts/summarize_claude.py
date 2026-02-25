"""
Daily Tech Digest - Step 2: Claude 재요약
- raw/{date}.json 읽어서 Claude로 핵심 요약
- 결과: digest/{date}.summary.md
"""

import os
import json
import anthropic
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
MODEL = "claude-sonnet-4-6"

SUMMARY_SYSTEM = """당신은 AI 기술 트렌드 분석가입니다.
Perplexity가 Reddit, Hacker News, Twitter에서 수집한 개발자 커뮤니티 원본 데이터를 읽고,
한국어로 핵심만 간결하게 요약합니다.

요약 원칙:
- 스펙·공식 발표 제외, 실제 사용자 경험과 반응만 추출
- 긍정/부정 반응을 균형 있게 정리
- 구체적인 이유나 사례가 있으면 반드시 포함
- 중복 내용 통합
- 각 섹션 3~5개 bullet point로 압축"""

SUMMARY_USER_TEMPLATE = """아래는 오늘({date}) 수집한 AI 기술 커뮤니티 반응 원본입니다.
세 섹션으로 나눠서 한국어로 요약해주세요.

---

## 섹션 1: AI로 인한 구조/방식 변화

### 에이전트 기반 개발
{workflow_agentic}

### 바이브 코딩 / AI 주도 개발
{workflow_vibecheck}

### 팀 구조 변화
{workflow_team_structure}

---

## 섹션 2: 새로운 AI 툴 커뮤니티 반응

### Cursor vs Claude Code 전환
{tools_cursor_vs_claude}

### AI 코딩 툴 전체 비교
{tools_landscape}

### 새롭게 주목받는 툴
{tools_new_rising}

---

## 섹션 3: 신규 모델/API — 실사용 반응

### 오늘의 신규 릴리즈 반응
{model_new_release}

### 모델별 실사용 성능 비교
{model_real_perf}

---

출력 형식:
# AI Tech Digest 요약 — {date}

## 🤖 신규 모델/API — 오늘의 반응
(bullet points, 데이터 없으면 섹션 생략)

## 🔄 AI로 인한 구조/방식 변화
(bullet points)

## 🛠️ 새로운 AI 툴 — 커뮤니티 반응
(bullet points)

## 💡 오늘의 핵심 인사이트
(전체를 관통하는 1~3줄 핵심 메시지)
"""


def load_raw(date: str) -> dict:
    path = f"raw/{date}.json"
    if not os.path.exists(path):
        raise FileNotFoundError(f"raw 파일 없음: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data["results"]


def build_prompt(results: dict) -> str:
    def get(key):
        r = results.get(key, {})
        return r.get("answer", "(데이터 없음)")

    return SUMMARY_USER_TEMPLATE.format(
        date=TODAY,
        workflow_agentic=get("workflow_agentic"),
        workflow_vibecheck=get("workflow_vibecheck"),
        workflow_team_structure=get("workflow_team_structure"),
        tools_cursor_vs_claude=get("tools_cursor_vs_claude"),
        tools_landscape=get("tools_landscape"),
        tools_new_rising=get("tools_new_rising"),
        model_new_release=get("model_new_release"),
        model_real_perf=get("model_real_perf"),
    )


def main():
    print(f"[{TODAY}] Claude 재요약 시작 (model: {MODEL})")

    results = load_raw(TODAY)
    prompt = build_prompt(results)

    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=SUMMARY_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )

    summary = response.content[0].text
    usage = response.usage

    # 요약본 저장
    out_path = f"digest/{TODAY}.summary.md"
    os.makedirs("digest", exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(summary)
        f.write(f"\n\n---\n*Summarized by Claude ({MODEL}) | Input: {usage.input_tokens} / Output: {usage.output_tokens} tokens*\n")

    print(f"  → 요약 저장: {out_path}")
    print(f"  → 토큰: input {usage.input_tokens} / output {usage.output_tokens}")
    print("[완료]")


if __name__ == "__main__":
    main()
