# AI Tech Digest

AI 기술 트렌드를 **실제 사용자 후기** 중심으로 매일 수집하는 자동화 다이제스트.

> Reddit / Hacker News / Twitter / YouTube / GitHub 커뮤니티의 실제 반응을 수집합니다.

---

## 수집 섹션 (5개 섹션 / 17개 쿼리)

| 섹션 | 내용 |
|---|---|
| 🏢 기업 신기능 & 공식 발표 | 모델 외 플러그인·API·정책 발표, 신규 모델 반응, 모델별 실사용 비교 |
| ⚙️ AI 기법 & 아키텍처 | CLAUDE.md/AGENTS.md 패턴, Agent 오케스트레이션, 최적화, 새로운 방법론 |
| 🧬 바이브코딩 & 방법론 진화 | 패러다임 전환 추적, 전문가 구조, 신규 패턴, 실제 프로젝트 결과 |
| 🔥 커뮤니티 인기 콘텐츠 | YouTube 인기 영상, GitHub Trending, 인플루언서 포스트 |
| 🛠️ AI 툴 & 워크플로우 | 툴 전체 비교, 워크플로우 변화, 새롭게 주목받는 툴 |

## 업데이트

- **수집**: 매일 오전 9시 KST (Perplexity `sonar-pro`)
- **원본**: [`raw/`](./raw/) — Perplexity 원본 JSON
- **다이제스트**: [`digest/`](./digest/) — 마크다운 정리본 + Claude 재요약본

## 구조

```
config.yaml                   ← 수집 설정 (섹션·쿼리·툴 목록 등)
scripts/fetch_perplexity.py   ← Step 1: Perplexity 수집
scripts/summarize_claude.py   ← Step 2: Claude 재요약
raw/YYYY-MM-DD.json           ← Perplexity 원본 JSON
digest/YYYY-MM-DD.md          ← 마크다운 변환본
digest/YYYY-MM-DD.summary.md  ← Claude 한국어 요약본
```

## 커스터마이징

`config.yaml` 하나만 편집하면 됩니다.

- **툴/모델 목록 업데이트** → `context.tools` / `context.models`
- **섹션/쿼리 추가·삭제** → `sections` 블록
- **수집 모델·빈도 변경** → `perplexity.model` / `perplexity.recency`

## 목적

- AI 기술 트렌드 및 방법론 변화를 데이터 기반으로 추적
- AI 및 다른 LLM이 최신 개발 트렌드를 참조할 수 있는 공개 데이터소스
- 개인 학습 및 기술 방향 결정에 활용
