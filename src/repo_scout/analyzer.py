from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


IGNORED_DIRS = {
    ".git", ".idea", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".venv",
    ".vscode", "__pycache__", "build", "dist", "node_modules", "venv",
}

ROLE_BY_NAME = {
    "readme.md": "프로젝트 소개와 사용법을 설명하는 문서",
    "pyproject.toml": "Python 패키지 설정과 의존성을 정의하는 파일",
    "requirements.txt": "Python 의존성 목록",
    "package.json": "JavaScript 프로젝트 설정과 의존성을 정의하는 파일",
    "dockerfile": "컨테이너 실행 환경을 만드는 설정",
    "docker-compose.yml": "여러 컨테이너 서비스를 함께 실행하는 설정",
    ".gitignore": "Git이 추적하지 않을 파일을 지정하는 설정",
    "license": "프로젝트 사용 및 배포 조건을 설명하는 라이선스",
    "makefile": "반복 개발 작업을 명령으로 묶은 자동화 파일",
}

ROLE_BY_SUFFIX = {
    ".py": "Python 소스 코드",
    ".js": "JavaScript 소스 코드",
    ".ts": "TypeScript 소스 코드",
    ".tsx": "React TypeScript UI 코드",
    ".ipynb": "실험 및 분석용 Jupyter Notebook",
    ".md": "문서",
    ".yml": "설정 또는 자동화 워크플로",
    ".yaml": "설정 또는 자동화 워크플로",
    ".json": "구조화된 설정 또는 데이터",
    ".sql": "데이터베이스 질의 또는 스키마",
}


@dataclass(frozen=True)
class FileInfo:
    path: Path
    size: int
    role: str


@dataclass(frozen=True)
class Analysis:
    root: Path
    files: list[FileInfo]
    skipped_large_files: int

    @property
    def extension_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for item in self.files:
            key = item.path.suffix.lower() or "(확장자 없음)"
            counts[key] = counts.get(key, 0) + 1
        return dict(sorted(counts.items(), key=lambda pair: (-pair[1], pair[0])))


def describe_role(relative_path: Path) -> str:
    name = relative_path.name.lower()
    if name in ROLE_BY_NAME:
        return ROLE_BY_NAME[name]
    if name == "__init__.py":
        return "Python 패키지를 선언하고 공개 인터페이스를 구성하는 파일"
    if name.startswith("test_") or name.endswith("_test.py"):
        return "동작을 검증하는 자동화 테스트"
    if relative_path.parts and relative_path.parts[0].lower() in {"tests", "test"}:
        return "동작을 검증하는 테스트 자료"
    return ROLE_BY_SUFFIX.get(relative_path.suffix.lower(), "역할을 추가 확인해야 하는 파일")


def scan_repository(root: Path, max_files: int = 500, max_file_bytes: int = 1_000_000) -> Analysis:
    root = root.expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"저장소 폴더를 찾을 수 없습니다: {root}")

    files: list[FileInfo] = []
    skipped = 0
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if any(part in IGNORED_DIRS or part.startswith(".") for part in relative.parts[:-1]):
            continue
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > max_file_bytes:
            skipped += 1
            continue
        files.append(FileInfo(relative, size, describe_role(relative)))
        if len(files) >= max_files:
            break
    return Analysis(root=root, files=files, skipped_large_files=skipped)


def _tree_lines(files: list[FileInfo]) -> list[str]:
    tree: dict[str, dict] = {}
    for item in files:
        node = tree
        for part in item.path.parts:
            node = node.setdefault(part, {})

    lines: list[str] = []
    def walk(node: dict[str, dict], prefix: str = "") -> None:
        entries = list(node.items())
        for index, (name, child) in enumerate(entries):
            last = index == len(entries) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{name}")
            if child:
                walk(child, prefix + ("    " if last else "│   "))
    walk(tree)
    return lines


def render_markdown(analysis: Analysis) -> str:
    directory_counts: dict[str, int] = {}
    for item in analysis.files:
        top = item.path.parts[0] if len(item.path.parts) > 1 else "(root)"
        directory_counts[top] = directory_counts.get(top, 0) + 1
    main_areas = sorted(directory_counts.items(), key=lambda pair: (-pair[1], pair[0]))[:5]

    lines = [
        "# Repository Analysis",
        "",
        f"- 분석 경로: `{analysis.root}`",
        f"- 분석 파일 수: {len(analysis.files)}",
        f"- 크기 제한으로 제외된 파일 수: {analysis.skipped_large_files}",
        "",
        "## 한눈에 보기",
        "",
        "파일이 가장 많이 모인 영역: " + ", ".join(f"`{name}` ({count})" for name, count in main_areas),
        "",
        "주요 파일 유형: " + ", ".join(f"`{suffix}` {count}개" for suffix, count in list(analysis.extension_counts.items())[:8]),
        "",
        "## 파일 구조",
        "",
        "```text",
        *_tree_lines(analysis.files),
        "```",
        "",
        "## 파일별 추정 역할",
        "",
        "| 파일 | 크기(bytes) | 추정 역할 |",
        "|---|---:|---|",
    ]
    lines.extend(f"| `{item.path.as_posix()}` | {item.size} | {item.role} |" for item in analysis.files)
    lines += [
        "",
        "## 해석 시 주의점",
        "",
        "이 결과는 파일명과 확장자를 이용한 규칙 기반 추정이다. 실제 코드 내용과 실행 흐름은 다음 단계에서 분석한다.",
        "",
    ]
    return "\n".join(lines)

