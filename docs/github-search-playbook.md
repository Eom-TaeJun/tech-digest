# GitHub Search Playbook

다음 수집에서도 `harness`, `skills`, `CLAUDE.md` 같은 구조 신호와 직접 링크를 다시 찾기 위한 플레이북.

---

## 목적

Perplexity 요약만으로 놓치기 쉬운 GitHub 직접 신호를 재현 가능하게 찾는다.

특히 아래 세 가지를 놓치지 않는다:

- `CLAUDE.md` / `AGENTS.md` / memory / hooks / subagents 구조
- `skills` 생태계, `SKILL.md`, registry, cross-tool skill 패턴
- `harness` / `repo-backed workflow` / mechanical verification / eval harness

---

## 우선순위 소스

1. **GitHub Search API** — 레포 링크, 생성일, stars, topics
2. **GitHub GraphQL Discussions** — 메인테이너/사용자 직접 언급
3. **공식 레포 README** — 구조 확인용
4. **공식 문서** — 현재 접근 방식 확인용

---

## 고정 탐색 그룹

이 그룹은 `config.yaml -> github.practice_signal_groups` 에도 반영되어 있다.

### 1. `CLAUDE.md / Router Stack`

사용 쿼리:

- `CLAUDE.md`
- `AGENTS.md`
- `project memory`
- `claude code hooks`
- `claude code subagents`

### 2. `Agent Skills Ecosystem`

사용 쿼리:

- `claude code skill`
- `codex skill`
- `SKILL.md`
- `agent skill registry`
- `skillhub`

### 3. `Harness Engineering`

사용 쿼리:

- `harness engineering`
- `repo-backed workflow`
- `.harness state`
- `PRD architecture progress`
- `orchestrator skill`

### 4. `Mechanical Verification Loops`

사용 쿼리:

- `autoresearch`
- `mechanical verification`
- `eval harness`
- `agent benchmark`
- `pass 3`

---

## 선별 기준

다음 조건을 만족하는 링크를 우선 채택한다.

- GitHub 레포 또는 GitHub Discussion 직접 링크가 있다
- 설명/토픽/본문에 `skill`, `harness`, `CLAUDE.md`, `AGENTS.md`, `memory`, `hook`, `subagent`, `verify`, `benchmark` 중 핵심 단어가 실제로 들어 있다
- README를 열면 구조가 바로 보인다
- 단순 AI 홍보가 아니라 설치 구조, 파일 구조, 검증 방법, 운영 방식이 드러난다

---

## 저장해야 하는 메타데이터

링크만 남기지 말고 아래를 같이 남긴다.

- URL
- `created_at`
- `updated_at` 또는 `pushed_at`
- stars
- 왜 relevant 한지 한 줄
- 어떤 query에서 잡혔는지

---

## 수동 확인용 명령 예시

레포 검색:

```bash
curl -L 'https://api.github.com/search/repositories?q=created:>2026-03-10+claude-code&sort=stars&order=desc&per_page=10'
```

특정 구조 검색:

```bash
curl -L 'https://api.github.com/search/repositories?q=pushed:>2026-03-10+%22CLAUDE.md%22&sort=stars&order=desc&per_page=10'
curl -L 'https://api.github.com/search/repositories?q=pushed:>2026-03-10+%22SKILL.md%22&sort=stars&order=desc&per_page=10'
curl -L 'https://api.github.com/search/repositories?q=pushed:>2026-03-10+%22harness+engineering%22&sort=stars&order=desc&per_page=10'
```

README 직접 확인:

```bash
curl -L 'https://raw.githubusercontent.com/<owner>/<repo>/main/README.md' | sed -n '1,220p'
```

---

## 이번에 잘 잡힌 대표 사례

- `garrytan/gstack`
- `uditgoenka/autoresearch`
- `twostraws/Swift-Agent-Skills`
- `iflytek/skillhub`
- `Phlegonlabs/Harness-Engineering-skills`
- `claw-eval/claw-eval`

이 레포들은 앞으로도 "현재 구조가 어디로 가는지" 판단하는 기준점으로 재확인한다.
