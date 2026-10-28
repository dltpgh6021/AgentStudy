"""The study's core: perspectives, scoring, and pruning. Edit this file first."""
from __future__ import annotations


def perspectives(mode: str) -> list[str]:
    common = "파일의 역할과 실행 흐름을 균형 있게 조사"
    if mode == "cot":
        return [common]
    if mode == "tot":
        return [common, common, common]
    return ["입력 → 데이터 변환 → 출력의 실행 경로를 조사",
            "설정 → 진입점 → import와 모듈 연결을 조사",
            "테스트 → 기대 동작 → 구현과 예외 처리를 조사"]


def references(observations: list[dict]) -> set[tuple[str, int]]:
    return {(ref["path"], ref["line"]) for observation in observations for ref in observation["evidence"]}


def score_candidate(assessment: dict, observations: list[dict]) -> dict:
    """Model scores are estimates. Only references actually observed are accepted."""
    seen = references(observations)
    cited = {(ref["path"], ref["line"]) for ref in assessment["evidence"]}
    invalid = sorted(cited - seen)
    eligible = bool(cited) and not invalid
    score = sum(assessment[key] for key in ("relevance", "support", "coverage")) if eligible else -1
    return {"score": score, "eligible": eligible,
            "unobserved_references": [f"{path}:{line}" for path, line in invalid]}


def choose_candidate(candidates: list[dict]) -> dict:
    """Keep one branch (beam width 1). Ties keep the first branch; log this bias."""
    eligible = [candidate for candidate in candidates if candidate["grading"]["eligible"]]
    if not eligible:
        raise ValueError("관찰한 코드 근거를 인용한 후보가 없습니다. 기록을 확인하세요.")
    return max(eligible, key=lambda candidate: candidate["grading"]["score"])


def object_schema(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties)}


def array_schema(item: dict, minimum: int, maximum: int) -> dict:
    return {"type": "array", "items": item, "minItems": minimum, "maxItems": maximum}


TEXT = {"type": "string", "minLength": 1, "maxLength": 2500}
REF = object_schema({"path": TEXT, "line": {"type": "integer", "minimum": 1, "maximum": 1000000}})
ACTION = object_schema({"name": {"type": "string", "enum": ["read_file", "search", "list_files"]},
                        "argument": {"type": "string", "maxLength": 200},
                        "start_line": {"type": "integer", "minimum": 1, "maximum": 1000000}})


def plan_schema(count: int) -> dict:
    candidate = object_schema({"plan": TEXT, "actions": array_schema(ACTION, 1, 2)})
    return object_schema({"candidates": array_schema(candidate, count, count)})


def judge_schema(ids: list[str]) -> dict:
    score = {"type": "integer", "minimum": 0, "maximum": 2}
    assessment = object_schema({"id": {"type": "string", "enum": ids}, "hypothesis": TEXT,
                               "relevance": score, "support": score, "coverage": score,
                               "evidence": array_schema(REF, 0, 10), "missing": TEXT})
    return object_schema({"assessments": array_schema(assessment, len(ids), len(ids))})


ANSWER_SCHEMA = object_schema({"answer": TEXT, "evidence": array_schema(REF, 1, 15),
                               "limitations": array_schema(TEXT, 1, 5)})
