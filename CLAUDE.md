# tech-digest — Claude 작업 규칙

## 파일 구조

```
digest/YYYY-MM-DD.summary.md  ← 매일 읽는 파일 (중복 제거 + 핵심 압축)
digest/YYYY-MM-DD.md          ← 원문 전체 (레퍼런스용, 필요 시만 확인)
raw/YYYY-MM-DD.json           ← 수집 원본 데이터
scripts/                      ← 수집·요약 파이프라인
config.yaml                   ← 쿼리·모델·섹션 설정
docs/github-search-playbook.md ← GitHub 직접 탐색 쿼리와 링크 수집 기준
```

---

## 콘텐츠 확인 순서 (필수)

1. **summary 먼저 읽기** — `digest/YYYY-MM-DD.summary.md`
   - ⚡ 오늘의 핵심 ([신규]/[업데이트] 태그) 확인
   - 🔑 핵심 키워드 & 방향성 확인
   - 대부분의 판단은 summary만으로 충분

2. **압축 원문(.md)은 이유가 있을 때만** — `digest/YYYY-MM-DD.md`
   - summary에 수치·출처가 없는데 정확한 데이터가 필요한 경우
   - 특정 레포·모델·기법의 세부 내용을 깊이 파악해야 하는 경우
   - 사용자가 특정 항목에 대해 추가 질문을 하는 경우
   - 이 파일은 읽기용 압축본이므로, 전체 응답이 필요하면 `raw/YYYY-MM-DD.json` 확인

> **원칙**: summary로 중요성을 먼저 판단 → 원문 접근이 필요한 이유가 명확할 때만 .md 열기

---

## 파이프라인 실행 순서

```
python scripts/discover_concepts.py       # Step 0:   신규 툴·모델·개념 발견
python scripts/fetch_official_sources.py  # Step 0.5: 공식 릴리즈 직접 확인
python scripts/fetch_github.py            # Step 0.6: GitHub Trending 수집
python scripts/fetch_practice_signals.py  # Step 0.75: GitHub 방법론 신호 수집
python scripts/fetch_perplexity.py        # Step 1:   Perplexity 수집 (직접 신호 context 주입)
python scripts/fetch_community_sources.py # Step 1.5: GitHub Discussions 직접 반응
python scripts/summarize_claude.py        # Step 2:   Claude 한국어 요약 (전날 대비 delta)
python scripts/detect_paradigm_shifts.py  # Step 3:   패러다임 변화 탐지
```

자동 실행: GitHub Actions (매일 KST 09:00)
수동 실행: `gh workflow run "Daily Tech Digest"`

`harness`, `skills`, `CLAUDE.md`, `AGENTS.md` 관련 직접 링크를 다시 찾을 때는:

1. `config.yaml -> github.practice_signal_groups`
2. `docs/github-search-playbook.md`

를 먼저 본다. 요약이 아니라 **GitHub 직접 링크 재수집 기준**이 들어 있다.

---

## summary 구조

| 섹션 | 내용 |
|------|------|
| ⚡ 오늘의 핵심 | 전날 대비 신규/업데이트 항목만, [신규]/[업데이트] 태그 |
| 🔑 핵심 키워드 & 방향성 | 반복 키워드 + 방향성 요약 |
| 🏢 기업 신기능 | 전날과 다른 내용만 |
| 🤖 신규 모델 | 전날과 다른 내용만 |
| ⚙️ AI 기법 & 아키텍처 | 전날과 다른 내용만 |
| 🧬 바이브코딩 & 방법론 | 전날과 다른 내용만 |
| 🔥 커뮤니티 인기 콘텐츠 | GitHub Trending 전날 대비 신규 레포만 |
| 🛠️ AI 툴 & 워크플로우 | 전날과 다른 내용만 |
| 💡 오늘의 액션 아이템 | 당장 써먹을 수 있는 것 2~3가지 |
