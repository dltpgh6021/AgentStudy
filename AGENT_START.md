# Gemini Repository 분석 Agent — 여기부터 시작

## 지금 확인된 상태

- .env의 GEMINI_API_KEY를 자동으로 읽는다. 기존 운영체제 환경변수가 있으면 그것을 우선한다.
- 같은 PC의 VS Code 터미널에서 gemini-3.5-flash-lite 연결 검사가 성공했다.
- 이 채팅의 명령 실행 환경에서는 DNS 조회가 실패했다. 실제 모델을 사용하는 명령은 VS Code의 일반 터미널에서 실행한다.
- 후보 생성 → 파일 도구 → 평가 → 선택 → 확장을 구현했다. 기본값은 깊이 2, 분기 3, 유지 후보 1이다.
- 현재 Agent와 분석 예제의 자동 테스트 11개가 통과했다. 모델 응답은 모의 데이터로 테스트한다.
- 실제 diverse 실행도 완료됐다. `outputs/agent-diverse-01/report.md`에 요청·응답 5회와 선택 경로가 기록돼 있다. 설명의 정확성은 코드와 별도로 대조한다.
- 결과 정리는 [experiments/week-04-agent.md](experiments/week-04-agent.md)에 작성했다. 전체 25,284토큰·약 50.469초의 실행이며, tot/cot 비교와 가중치 변경 실험은 아직 하지 않았다.

## 먼저 기존 결과 읽기

실험 정리 → 원본 report.md → trace.json·calls.json 순서로 읽는다.
report.md의 completed는 프로그램 처리 완료이지, 모든 설명의 정확성 검증 완료가 아니다.
이번 선택 경로는 cli.py 30줄과 analyzer.py 60줄을 관찰했다. 핵심 함수는 그 이후에 있어 본문까지 확인하지 못했다.
세 파일만 허용한 실행이라 테스트 파일도 읽을 수 없었다. 관점 다양성의 효과는 아직 결론 내릴 수 없다.

## 1. 실제 분석 한 번 실행

VS Code에서 작업 폴더를 열고 터미널에서 실행한다. 추가 설치는 필요 없다.
기존 구조 분석기의 세 파일만 대상으로 삼아 작게 시작한다.
기존 결과는 `outputs/agent-diverse-01/report.md`에서 볼 수 있다. 아래 새 실행은 다른 폴더에 저장한다.

```powershell
.\.venv\Scripts\python.exe run_agent.py analyze . --include src/repo_scout/analyzer.py src/repo_scout/cli.py pyproject.toml --mode diverse -o outputs/agent-diverse-02
```

질문 기본값은 "repo-scout 명령을 실행하면 저장소 경로가 어떤 함수를 거쳐 Markdown 파일로 저장되는가?"이다.
모델이 파일 목록을 보고 필요한 파일 읽기·검색을 선택한다. 사람이 후보를 고르거나 챗봇 응답을 복사하지 않는다.
기본 요청 수는 5회이며 요청 시작 사이 간격은 12초 이상이다. 전체 실행은 모델 응답 시간에 따라 몇 분 걸릴 수 있다.
이미 같은 출력 폴더가 있으면 다른 이름으로 실행한다. 기존 결과를 덮어쓰지 않는다.

완료되면 `outputs/agent-diverse-02/report.md`를 연다.

| 파일 | 들어 있는 것 |
|---|---|
| report.md | 최종 답변, 근거 경로·줄, 후보 점수와 선택 경로 |
| trace.json | 부모·자식 후보, 작업 기억, 실제 도구 관찰과 평가 |
| calls.json | 키를 제외한 요청 프롬프트·JSON Schema·응답·사용량·시간 |
| snapshot.json | 분석에 사용한 텍스트와 원본 파일 해시 |

Gemini의 비공개 사고 과정은 수집하지 않는다. 기록하는 중간 상태는 짧은 분석 결론과 실제 코드 관찰이다.
최종 인용이 선택 경로에서 관찰한 파일·줄에 속하는지 검사한다. 설명의 사실성은 사람이 추가 확인한다.

## 2. 공부한 개념이 들어 있는 부분

| 개념 | 구현 | 먼저 볼 곳 |
|---|---|---|
| Cognitive Architecture / CoALA에서 착안한 구조 | 작업 기억, 허용된 행동, 의사결정 순환 분리 | agent.py의 run_agent, repo_tools.py |
| CoT에서 착안한 단일 경로 | cot 모드로 중간 분석을 이어가며 도구 관찰 누적 | policy.py의 perspectives |
| ToT | 후보 상태 생성, 모델 평가, 가지 선택 후 후속 상태 확장 | run_agent, choose_candidate |
| Reasoning Diversity | 후보별로 데이터 흐름·모듈 연결·검증 관점을 부여 | policy.py의 perspectives |

CoALA는 설계 틀이며 별도 라이브러리를 설치하는 기능이 아니다. 이 버전은 작업 기억·행동·의사결정 부분을 적용했다.
장기 기억 자동 회상·학습, 되돌아가기, 여러 부모를 유지하는 탐색은 이후 확장 대상이다.
cot 모드나 다른 관점 지시가 모델의 내부 추론을 통제·관측한다는 뜻은 아니다. 원 논문 전체 재현으로 주장하지 않는다.

## 3. 후속 학습 작업 (약 2시간, 아래 비교는 아직 미실행)

1. policy.py의 perspectives, score_candidate, choose_candidate를 읽고 선택 방식을 설명한다 — 25분.
2. 위 명령으로 실제 분석을 실행하고 후보 하나의 도구 호출·평가·선택 과정을 따라간다 — 25분.
3. 같은 질문과 같은 파일로 tot 모드를 실행해 관점 지시의 효과를 관찰한다 — 30분.
4. 새로 관찰한 차이와 코드 근거를 experiments/week-04-agent.md의 기존 결과와 구분해서 추가한다 — 30분. 원본 실행 로그는 덮어쓰지 않는다.

```powershell
.\.venv\Scripts\python.exe run_agent.py analyze . --include src/repo_scout/analyzer.py src/repo_scout/cli.py pyproject.toml --mode tot -o outputs/agent-tot-01
```

비교할 두 실행의 모델·질문·자료·깊이·후보 수를 동일하게 유지하고 trace.json의 파일 해시를 확인한다.
테스트 관점을 제대로 조사하려면 테스트 파일을 허용하는 별도 실험이 필요하다. 이때 모든 비교 모드의 자료를 함께 바꾼다.

선택 기준은 관련성·근거·질문 해결 범위 각 0~2점의 합이다. 관찰하지 않은 위치를 인용한 후보는 선택 대상에서 제외한다.
동점이면 먼저 생성된 후보를 유지한다. 모델의 자체 점수는 정답률이 아니므로 코드와 대조한다.
예를 들어 score_candidate의 근거 항목 가중치를 바꾸고 이유를 설명하는 것이 네가 직접 해볼 작은 구현 과제다.

저장된 점수로 선택 정책만 다시 실행할 때는 API를 사용하지 않는다.

```powershell
.\.venv\Scripts\python.exe run_agent.py replay outputs/agent-diverse-01
```

정책 변경으로 이전에 버린 부모를 선택하면 그 부모의 후손은 저장돼 있지 않다. 후속 탐색까지 보려면 새 실행이 필요하다.

## 4. 다른 공개 저장소와 질문

```powershell
.\.venv\Scripts\python.exe run_agent.py analyze "C:\path\to\public-repository" --question "이 프로젝트의 주요 실행 흐름과 파일 역할을 설명해 줘" --mode diverse
```

include를 생략하면 읽을 수 있는 코드·문서 목록을 최대 200개까지 만든다. 파일당 64 KB, 전체 2 MB로 제한한다.
도구는 이 고정된 자료 안에서만 읽거나 문자열을 검색한다. 대상 코드를 실행하지 않는다.
.env 등 숨김 파일, 자격 증명으로 보이는 파일, .git·가상환경·outputs 등은 제외한다.

## 5. 연결 문제 확인

```powershell
.\.venv\Scripts\python.exe run_agent.py diagnose
.\.venv\Scripts\python.exe run_agent.py check
```

diagnose는 키를 읽거나 API를 호출하지 않고 DNS만 확인한다. check는 작은 모델 요청 1회를 시도한다.
"요청 시도 1/1"은 호출 성공을 뜻하지 않는다. 뒤의 "연결 성공"이나 오류 종류를 확인한다.

- DNS 조회 실패: 서버 주소를 찾지 못한 네트워크 단계. 키 인증 전에 실패했다.
- HTTP 400/403: 요청 형식, 키, 모델 접근 권한 등을 오류 본문과 함께 확인한다.
- HTTP 429: 사용량·속도 제한. 자동 재시도하지 않고 기록을 남긴다.
- JSON 형식 또는 관찰하지 않은 인용 오류: 요청·응답과 트리를 확인한 뒤 모델 출력이나 프롬프트를 개선한다.

무료 티어 상태와 호출 가능 모델·한도는 AI Studio에서 확인한다. 모델을 바꿀 때는 비교 조건에서도 동일하게 유지한다.
실패해도 기존 분석은 성공한 것으로 표시하지 않으며, 생성된 출력 폴더에 부분 기록이 남는다.
다시 실행할 때는 새 출력 폴더를 지정한다. .env는 공유하거나 ZIP에 넣지 않는다.

## 해석 범위와 출처

tot와 diverse는 같은 단계 수·후보 수·모델을 사용하지만 선택한 파일·응답 토큰 수는 달라질 수 있다.
모델 기본 추론 설정도 영향을 주므로 결과 차이를 오직 관점 다양성 때문이라고 단정하지 않는다.
같은 응답에 생성된 후보들은 독립 표본이 아니며, 한 저장소의 결과를 일반화하지 않는다.

문서 수정 후 GitHub 업로드 명령은 [README의 업로드 절차](README.md#변경-내용을-github에-업로드)를 참고한다.

- [Gemini Interactions API](https://ai.google.dev/gemini-api/docs/interactions-overview)
- [Gemini Structured Outputs](https://ai.google.dev/gemini-api/docs/structured-output)
- [Gemini 가격·무료 티어](https://ai.google.dev/gemini-api/docs/pricing)
- [CoALA](https://arxiv.org/abs/2309.02427), [CoT](https://arxiv.org/abs/2201.11903), [ToT](https://arxiv.org/abs/2305.10601)
