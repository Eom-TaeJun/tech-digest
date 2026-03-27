# AI Tech Digest

AI 기술 트렌드를 **GitHub 기반 실제 사용자 신호** 중심으로 매일 수집하는 자동화 다이제스트.

> GitHub Trending, GitHub Discussions, README, 이슈/토론의 실제 반응을 수집합니다.

---

## 수집 섹션 (5개 섹션 / 17개 쿼리)

| 섹션 | 내용 |
|---|---|
| 🏢 기업 신기능 & 공식 발표 | 모델 외 플러그인·API·정책 발표, 신규 모델 반응, 모델별 실사용 비교 |
| ⚙️ AI 기법 & 아키텍처 | CLAUDE.md/AGENTS.md 패턴, Agent 오케스트레이션, 최적화, 새로운 방법론 |
| 🧬 바이브코딩 & 방법론 진화 | 패러다임 전환 추적, 전문가 구조, 신규 패턴, 실제 프로젝트 결과 |
| 🔥 커뮤니티 인기 콘텐츠 | GitHub Discussions, GitHub Trending, 메인테이너 활동 |
| 🛠️ AI 툴 & 워크플로우 | 툴 전체 비교, 워크플로우 변화, 새롭게 주목받는 툴 |

## 업데이트

- **수집**: 매일 오전 9시 KST (Perplexity `sonar-pro`)
- **원본**: [`raw/`](./raw/) — 공식 소스 + GitHub 직접 신호 + Perplexity 결과가 합쳐진 원본 JSON
- **다이제스트**: [`digest/`](./digest/) — 읽기용 압축 마크다운 + Claude 재요약본

## 구조

```
config.yaml                        ← 수집 설정 (섹션·쿼리·툴 목록 등)
baseline_architecture.yaml         ← 아키텍처 설계 기준점 (탐지용)
scripts/discover_concepts.py       ← Step 0: 신규 툴/모델/개념 발견
scripts/fetch_official_sources.py  ← Step 0.5: 공식 릴리즈 직접 확인
scripts/fetch_github.py            ← Step 0.6: GitHub Trending 수집
scripts/fetch_practice_signals.py  ← Step 0.75: GitHub 직접 방법론 신호 수집
scripts/fetch_perplexity.py        ← Step 1: Perplexity 수집
scripts/fetch_community_sources.py ← Step 1.5: GitHub Discussions 직접 반응 수집
scripts/summarize_claude.py        ← Step 2: Claude 재요약
scripts/detect_paradigm_shifts.py  ← Step 3: 패러다임 변화 탐지
docs/github-search-playbook.md     ← GitHub 직접 링크 재수집 플레이북
raw/YYYY-MM-DD.json                ← 병합 원본 JSON (전체 응답 보관)
digest/YYYY-MM-DD.md               ← 읽기용 압축 마크다운
digest/YYYY-MM-DD.summary.md       ← Claude 한국어 요약본 + 패러다임 감지 결과
```

## 실행 순서

1. `python scripts/discover_concepts.py` # Step 0: 신규 툴·모델·개념 자동 발견 (config.yaml 업데이트)
2. `python scripts/fetch_official_sources.py` # Step 0.5: 공식 모델 릴리즈 직접 확인
3. `python scripts/fetch_github.py` # Step 0.6: GitHub Trending/star velocity 수집
4. `python scripts/fetch_practice_signals.py` # Step 0.75: GitHub 직접 방법론 신호 수집
5. `python scripts/fetch_perplexity.py`   # Step 1: Perplexity 데이터 수집 (직접 신호 기반 맥락 보강)
6. `python scripts/fetch_community_sources.py` # Step 1.5: GitHub Discussions 직접 반응 수집
7. `python scripts/summarize_claude.py`    # Step 2: Claude 한국어 요약
8. `python scripts/detect_paradigm_shifts.py` # Step 3: 아키텍처 위기 및 패러다임 변화 탐지

## 핵심 분석 대상

- **Harness Engineering**: AI 에이전트의 안정성을 위한 테스트 및 검증 환경
- **AI Agent Skills**: 재사용 가능한 에이전트 모듈 및 스킬 셋
- **AGENTS.md / CLAUDE.md**: 프로젝트별 AI 지침 표준화 패턴
- **MCP (Model Context Protocol)**: 모델과 도구 간의 연결 표준
- **Vibe Coding**: 실시간 프롬프트 기반 개발의 패러다임 변화 및 한계 탐색

## 커스터마이징

`config.yaml` 하나만 편집하면 됩니다.

- **툴/모델 목록 업데이트** → `context.tools` / `context.models`
- **섹션/쿼리 추가·삭제** → `sections` 블록
- **수집 모델·빈도 변경** → `perplexity.model` / `perplexity.recency`
- **GitHub 직접 탐색 그룹 조정** → `github.practice_signal_groups`

## 목적

- AI 기술 트렌드 및 방법론 변화를 데이터 기반으로 추적
- AI 및 다른 LLM이 최신 개발 트렌드를 참조할 수 있는 공개 데이터소스
- 개인 학습 및 기술 방향 결정에 활용
