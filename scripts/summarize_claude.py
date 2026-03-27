"""
Daily Tech Digest - Step 2: Claude 재요약
- config.yaml에서 설정/프롬프트 로드
- raw/{date}.json 읽어서 Claude로 핵심 요약
- 전날 summary를 로드해 중복 항목 필터링
- 결과: digest/{date}.summary.md
"""

import os
import json
import yaml
import anthropic
from datetime import datetime, timezone, timedelta, date

from confidence_utils import classify_confidence, confidence_gate

KST = timezone(timedelta(hours=9))
TODAY = datetime.now(KST).strftime("%Y-%m-%d")


def load_config() -> dict:
    config_path = os.path.join(os.path.dirname(__file__), "..", "config.yaml")
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_raw(date: str) -> tuple[dict, list, list, dict]:
    path = f"raw/{date}.json"
    if not os.path.exists(path):
        raise FileNotFoundError(f"raw 파일 없음: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return (
        data["results"],
        data.get("github_trending", []),
        data.get("hackernews_trending", []),
        data.get("practice_signals", {}),
    )


def load_prev_summary(today_str: str) -> str:
    """전날 summary.md를 읽어 반환. 없으면 빈 문자열."""
    today_date = datetime.strptime(today_str, "%Y-%m-%d").date()
    prev_date = today_date - timedelta(days=1)
    path = f"digest/{prev_date.strftime('%Y-%m-%d')}.summary.md"
    if not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read()


def build_github_section(trending: list[dict]) -> str:
    if not trending:
        return ""
    lines = [
        "## [GitHub Trending] 최근 7일 급등 레포 (star velocity 기준)",
        "",
    ]
    for i, r in enumerate(trending, 1):
        lang = r.get("language") or "Unknown"
        desc = r.get("description") or ""
        lines.append(
            f"{i}. **[{r['name']}]({r['url']})** "
            f"★{r['stars']:,} ({r['star_velocity']}★/일) | {lang} | {r['days_old']}일차"
        )
        if desc:
            lines.append(f"   > {desc}")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def build_hackernews_section(hn_trending: list[dict]) -> str:
    if not hn_trending:
        return ""
    lines = [
        "## [Hacker News] AI 관련 인기 토론 (최근 72시간)",
        "",
    ]
    for i, s in enumerate(hn_trending[:10], 1):
        lines.append(
            f"{i}. **[{s['title']}]({s['hn_url']})** "
            f"↑{s['points']} 💬{s['comments']}"
        )
        if s.get("url") and s["url"] != s["hn_url"]:
            lines.append(f"   원문: {s['url']}")
    lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def build_practice_section(practice_signals: dict) -> str:
    groups = practice_signals.get("groups", [])
    if not groups:
        return ""
    lines = [
        "## [Practice Signals] GitHub 방법론 신호",
        "",
    ]
    for g in groups[:6]:
        repos = g.get("github_repos", [])
        discussions = g.get("github_discussions", [])
        if not repos and not discussions:
            continue
        lines.append(f"### {g.get('label', 'Unknown')}")
        for r in repos[:2]:
            lines.append(
                f"- Repo: [{r['name']}]({r['url']}) ★{r['stars']} ({r.get('star_velocity', 0)}★/일)"
            )
        for d in discussions[:2]:
            lines.append(
                f"- Discussion: [{d['title']}]({d['url']}) ↑{d.get('upvotes', 0)} 💬{d.get('comments', 0)}"
            )
        lines.append("")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def format_result_for_summary(result: dict, config: dict) -> tuple[str, str]:
    gate = confidence_gate(config)
    confidence = classify_confidence(result, gate)
    answer = result.get("answer", "(데이터 없음)")
    notice = gate.get(
        "low_confidence_notice",
        "LOW confidence 항목은 승인된 공식/직접 커뮤니티 근거가 부족하므로 배경 정보로만 사용",
    )

    max_chars = 2000
    if confidence == "LOW":
        max_chars = gate.get("low_confidence_max_chars", 900)

    if confidence == "LOW" and gate.get("low_confidence_prompt_mode") == "note_only":
        return confidence, f"[LOW CONFIDENCE] {notice}"

    if len(answer) > max_chars:
        answer = answer[:max_chars] + "...(truncated)"

    if confidence == "LOW":
        answer = f"[LOW CONFIDENCE] {notice}\n\n{answer}"

    return confidence, answer


def build_prompt(results: dict, github_trending: list, config: dict, prev_summary: str = "",
                 hn_trending: list = None, practice_signals: dict = None) -> str:
    gate = confidence_gate(config)
    lines = [
        f"아래는 오늘({TODAY}) 수집한 AI 기술 커뮤니티 반응 원본입니다.",
        "섹션별로 나눠서 한국어로 요약해주세요.",
        "",
        "중요 규칙:",
        "1. 최신 모델 버전/출시일은 official source가 있는 항목을 우선 사실로 사용하세요.",
        "2. community source가 부족하면 '직접 커뮤니티 반응 부족'이라고 명시하세요.",
        "3. benchmark chatter나 서드파티 요약만 있는 항목을 최신 공식 출시처럼 쓰지 마세요.",
        "4. 공식 출시 체크와 커뮤니티 반응이 충돌하면 공식 출시 체크를 기준으로 정리하세요.",
        "5. github.com discussion 링크가 직접 소스로 있으면 GitHub Discussions 반응도 명시하세요.",
        "6. 전날 요약에 이미 등장한 항목(모델명, 레포, 이슈, 방법론 등)은 오늘 유의미한 업데이트가 없으면 생략하세요.",
        "7. 오늘 처음 등장하거나 전날 대비 수치·상태·반응이 크게 바뀐 항목은 '신규' 또는 '업데이트'로 명시하세요.",
        "8. HIGH confidence만 headline/오늘의 핵심/액션 아이템의 직접 근거로 사용하세요.",
        "9. MEDIUM confidence는 보조 설명으로만 사용하고, 단정적 표현은 피하세요.",
        "10. LOW confidence는 headline/키워드/액션 아이템에 올리지 말고, 필요하면 '근거 약함' 또는 '직접 커뮤니티 반응 부족'으로만 짧게 언급하세요.",
        "",
        "---",
        "",
    ]

    if prev_summary:
        lines += [
            "## [전날 요약 — 중복 판단 기준]",
            "아래 내용은 어제 이미 다룬 항목입니다. 오늘 유의미한 변화가 없으면 반복하지 마세요.",
            "",
            prev_summary[:2000],  # 앞 2000자만 사용 (input 토큰 절약)
            "",
            "---",
            "",
        ]

    for i, section in enumerate(config["sections"], 1):
        lines.append(f"## 섹션 {i}: {section['title']}")
        lines.append("")
        for q in section["queries"]:
            result = results.get(q["id"], {})
            confidence, answer = format_result_for_summary(result, config)
            evidence = result.get("evidence", {})
            citations = result.get("citations", [])[:5]  # 출처 최대 5개
            if confidence == "LOW" and not gate.get("include_low_confidence_sources", False):
                citations = []
            lines.append(f"### {q['title']}")
            lines.append(f"Confidence: {confidence}")
            if confidence == "LOW" and gate.get("suppress_low_confidence_headlines", True):
                lines.append("Summary Rule: 이 항목은 headline/오늘의 핵심/액션 아이템에 사용 금지")
            if evidence:
                lines.append(
                    "Evidence Summary: "
                    f"official={evidence.get('official_source_count', 0)}, "
                    f"community={evidence.get('community_source_count', 0)}, "
                    f"other={evidence.get('other_source_count', 0)}, "
                    f"filtered={evidence.get('filtered_out_citation_count', 0)}, "
                    f"has_official={evidence.get('has_official_sources', False)}, "
                    f"has_community={evidence.get('has_direct_community_sources', False)}"
                )
            if citations:
                lines.append("Sources:")
                for idx, url in enumerate(citations, 1):
                    lines.append(f"{idx}. {url}")
            lines.append(answer)
            lines.append("")
        lines.append("---")
        lines.append("")

    github_block = build_github_section(github_trending)
    if github_block:
        lines.append(github_block)

    hn_block = build_hackernews_section(hn_trending or [])
    if hn_block:
        lines.append(hn_block)

    practice_block = build_practice_section(practice_signals or {})
    if practice_block:
        lines.append(practice_block)

    lines.append(config["summary"]["output_format"].format(date=TODAY))
    return "\n".join(lines)


def main():
    config = load_config()
    model = config["claude"]["model"]
    max_tokens = config["claude"]["max_tokens"]

    print(f"[{TODAY}] Claude 재요약 시작 (model: {model})")

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    results, github_trending, hn_trending, practice_signals = load_raw(TODAY)
    prev_summary = load_prev_summary(TODAY)
    print(f"  → GitHub Trending: {len(github_trending)}개 레포")
    print(f"  → Hacker News: {len(hn_trending)}건")
    print(f"  → Practice Signals: {len(practice_signals.get('groups', []))}개 그룹")
    print(f"  → 전날 요약: {'로드됨' if prev_summary else '없음'}")
    prompt = build_prompt(results, github_trending, config, prev_summary, hn_trending, practice_signals)

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
