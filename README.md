# Repo Scout

Gemini API를 사용해 로컬 공개 저장소를 분석하는 Python Agent입니다.
파일 읽기·검색 행동을 제안하고, 수집한 코드 근거로 후보를 평가한 뒤 선택한 경로를 확장합니다.
현재 학습 주제는 Cognitive Architecture / CoALA, CoT, ToT, Reasoning Diversity입니다.

## 시작

Python 3.10 이상이 필요하며 외부 Python 패키지 설치는 필요 없습니다.
처음 환경을 만드는 경우에만 가상환경을 생성합니다.

```powershell
py -m venv .venv
```

`.env.example`을 참고해 프로젝트 루트의 `.env`에 `GEMINI_API_KEY`를 설정합니다.
기존 `.env`가 있으면 그대로 사용합니다. 키는 코드나 실행 결과에 넣지 않습니다.

```powershell
.\.venv\Scripts\python.exe run_agent.py check
.\.venv\Scripts\python.exe run_agent.py analyze . --include src/repo_scout/analyzer.py src/repo_scout/cli.py pyproject.toml --mode diverse -o outputs/agent-diverse-02
```

기존 실행 결과는 `outputs/agent-diverse-01/report.md`에 있습니다.
새 실행에는 새로운 출력 폴더를 사용합니다. 기본 질문은 repo-scout 명령에서 Markdown 저장까지의 실행 흐름입니다.
기본 설정은 깊이 2·분기 3·유지 후보 1이며 API 요청 시도를 5회로 제한합니다.

## 학습과 실행 안내

- `AGENT_START.md`: 실행 방법, 개념과 구현의 연결, 후보 점수 해석
- `experiments/week-04-agent.md`: 현재 실험 질문과 결과 기록 양식
- `outputs/agent-diverse-01/`: 실제 diverse 실행의 보고서·후보 트리·요청 기록·소스 스냅샷

지원하는 모드는 단일 경로의 단계적 분석 `cot`, 같은 관점의 후보 탐색 `tot`, 다른 관점의 후보 탐색 `diverse`입니다.
이름이 다른 관점이 실제로 다른 탐색을 만드는지는 실행 기록으로 확인합니다.
점수는 모델의 자체 평가이며, 인용이 실제 주장을 뒷받침하는지는 사람이 코드와 대조해야 합니다.

## 코드 구성

| 파일 | 역할 |
|---|---|
| run_agent.py | 설치 없이 실행하는 진입점 |
| src/repo_scout/agent.py | 작업 기억, 후보 생성·평가·확장 순환과 결과 저장 |
| src/repo_scout/policy.py | 관점 정의, 후보 점수와 선택 정책 |
| src/repo_scout/repo_tools.py | 고정된 소스 자료에서 파일 읽기·검색 |
| src/repo_scout/gemini.py | .env 설정, Gemini 호출, 응답 검증과 호출 한도 |
| src/repo_scout/cli.py, analyzer.py | 현재 Agent가 분석하는 작은 예제 프로그램 |

`cli.py`, `analyzer.py`, `pyproject.toml`은 실제 실행 결과의 분석 대상이므로 함께 보존합니다.
CoALA에서 착안한 작업 기억·행동·의사결정 구조를 적용했으며 장기 기억 자동 회상·학습과 원 논문 전체 재현은 포함하지 않습니다.

## 결과 파일

각 실행의 출력 폴더에 다음 파일이 생성됩니다.

- `report.md`: 최종 답변, 코드 근거, 후보별 평가와 선택 경로
- `trace.json`: 작업 기억, 부모·자식 후보와 도구 관찰
- `calls.json`: 키를 제외한 프롬프트, 모델 응답, 사용량과 응답 시간
- `snapshot.json`: 분석에 사용한 코드와 파일 해시

과거 실행의 스냅샷과 보고서는 실행 당시의 기록이므로 현재 코드를 정리해도 수정하지 않습니다.
`docs/`의 PDF는 학습 자료입니다. 실행에 필요한 파일은 아닙니다.

## 테스트와 로컬 재현

```powershell
$env:PYTHONPATH = "src"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe run_agent.py replay outputs/agent-diverse-01
```

현재 테스트 11개는 모의 모델로 도구 제한·후보 선택·인용 검사·오류 처리 등을 확인합니다. 실제 모델 성능 측정은 별도입니다.
replay는 저장된 평가로 선택 정책만 다시 실행하므로 API를 호출하지 않습니다.

`.env`와 `.venv`, 캐시는 Git에서 제외합니다. 실제 실행 산출물은 비교와 재현을 위해 보존합니다.
