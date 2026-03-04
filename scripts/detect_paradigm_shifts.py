import os
import yaml
import glob
from anthropic import Anthropic
from datetime import datetime

# 설정 로드
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
with open("config.yaml", "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)
with open("baseline_architecture.yaml", "r", encoding="utf-8") as f:
    baseline = yaml.safe_load(f)

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

def get_latest_digest():
    files = sorted(glob.glob("digest/*.md"))
    # 요약본(.summary.md) 제외하고 원본 다이제스트 선택
    files = [f for f in files if not f.endswith(".summary.md")]
    return files[-1] if files else None

def detect():
    digest_path = get_latest_digest()
    if not digest_path:
        print("다이제스트 파일을 찾을 수 없습니다.")
        return

    with open(digest_path, "r", encoding="utf-8") as f:
        today_news = f.read()

    print(f"  [Detecting] {digest_path} 분석 중...")

    prompt = f"""
당신은 '하니스 엔지니어링' 아키텍처 전문가입니다.
아래의 [현재 설계 기준(Baseline)]과 [오늘의 기술 다이제스트]를 비교하여, 
우리의 기준이 구식이 되었거나(Obsolescence) 새로운 더 나은 패턴(New Pattern)이 등장했는지 분석하세요.

[현재 설계 기준(Baseline)]
{yaml.dump(baseline, allow_unicode=True)}

[오늘의 기술 다이제스트]
{today_news}

---
결과는 반드시 다음 형식의 한국어 마크다운으로 작성하세요:

### 🚨 아키텍처 패러다임 변화 감지

#### 1. 직접적인 충돌 (Contradictions)
- (우리의 기준과 정반대되는 최신 트렌드가 있다면 기술)

#### 2. 신규 등장 패턴 (Emerging Patterns)
- (기존 기준에는 없지만 새롭게 주목받는 설계 방식)

#### 3. 하드코딩 업데이트 권고
- (구체적으로 어떤 설계를 변경해야 하는지 제안)
"""

    response = client.messages.create(
        model=config["claude"]["model"],
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )

    alert_content = response.content[0].text
    
    # 요약본 파일 하단에 추가
    summary_path = digest_path.replace(".md", ".summary.md")
    if os.path.exists(summary_path):
        with open(summary_path, "a", encoding="utf-8") as f:
            f.write("\n\n---\n" + alert_content)
        print(f"  ✓ 패러다임 변화 감지 결과가 {summary_path}에 추가되었습니다.")
    else:
        print(f"  [Error] 요약본 파일을 찾을 수 없습니다: {summary_path}")
        print("\n[감지 결과]\n")
        print(alert_content)

if __name__ == "__main__":
    detect()
