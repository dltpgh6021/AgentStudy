"""Read-only, bounded repository tools over a frozen text snapshot."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "node_modules", "__pycache__", "outputs", "work", "build", "dist"}
TEXT_SUFFIXES = {".py", ".md", ".toml", ".json", ".yaml", ".yml", ".txt", ".js", ".ts", ".tsx", ".go", ".rs", ".java", ".sql"}


class RepoTools:
    def __init__(self, root: Path, include: list[str] | None = None, redact=lambda text: text):
        self.root = root.resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("분석할 저장소 폴더가 필요합니다.")
        allowed = None
        if include:
            allowed = set()
            for relative in include:
                resolved = (self.root / relative).resolve(strict=True)
                if not resolved.is_relative_to(self.root):
                    raise ValueError("저장소 밖의 파일은 포함할 수 없습니다.")
                allowed.add(resolved.relative_to(self.root).as_posix())
        self.files: dict[str, dict] = {}
        used_bytes = 0
        self.truncated = False
        for directory, dirs, names in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(name for name in dirs if name not in SKIP_DIRS and not name.startswith(".")
                             and not (Path(directory) / name).is_symlink()
                             and (Path(directory) / name).resolve().is_relative_to(self.root))
            for name in sorted(names):
                path = Path(directory) / name
                relative = path.relative_to(self.root).as_posix()
                if allowed is not None and relative not in allowed:
                    continue
                if name.startswith(".") or path.is_symlink() or not path.resolve().is_relative_to(self.root):
                    continue
                if path.suffix.lower() not in TEXT_SUFFIXES or any(word in name.lower() for word in ("credential", "secret", "token")):
                    continue
                size = path.stat().st_size
                if size > 64_000:
                    continue
                if len(self.files) >= 200 or used_bytes + size > 2_000_000:
                    self.truncated = True
                    continue
                data = path.read_bytes()
                try:
                    text = data.decode("utf-8-sig")
                except UnicodeError:
                    continue
                if "\x00" in text:
                    continue
                self.files[relative] = {"text": redact(text), "sha256": hashlib.sha256(data).hexdigest()}
                used_bytes += len(data)
        if allowed is not None and allowed != set(self.files):
            raise ValueError("선택한 파일 중 분석에서 제외된 항목이 있습니다. 숨김·비밀·대용량 파일은 사용할 수 없습니다.")
        if not self.files:
            raise ValueError("분석할 UTF-8 코드·문서 파일이 없습니다.")

    def overview(self) -> dict:
        return {"files": list(self.files), "truncated": self.truncated,
                "tools": {"read_file": "argument=파일 경로, start_line=시작 줄. 최대 60줄/6000자.",
                          "search": "argument=코드에서 찾을 문자열. 최대 10개 일치 줄.",
                          "list_files": "현재 스냅샷의 파일 목록. 내용은 포함하지 않음."}}

    def execute(self, action: dict) -> dict:
        name, argument = action["name"], action["argument"]
        result = {"action": action, "evidence": [], "note": ""}
        if name == "list_files":
            result["note"] = ", ".join(self.files)
        elif name == "read_file":
            if argument not in self.files:
                result["note"] = "스냅샷에 없는 파일입니다. 파일 목록의 정확한 경로를 사용하세요."
                return result
            lines = self.files[argument]["text"].splitlines()
            start = action["start_line"]
            if start < 1 or start > len(lines):
                result["note"] = "파일의 줄 번호 범위를 벗어났습니다."
                return result
            budget = 6000
            for index in range(start - 1, min(start + 59, len(lines))):
                text = lines[index][:400]
                if len(text) > budget:
                    break
                result["evidence"].append({"path": argument, "line": index + 1, "text": text})
                budget -= len(text)
            result["note"] = f"총 {len(lines)}줄 중 요청 범위. 긴 줄은 400자로 제한."
        elif name == "search":
            if not argument.strip() or len(argument) > 120:
                result["note"] = "검색 문자열은 1~120자로 지정하세요."
                return result
            for path, item in self.files.items():
                for index, text in enumerate(item["text"].splitlines(), 1):
                    if argument.casefold() in text.casefold():
                        result["evidence"].append({"path": path, "line": index, "text": text[:400]})
                        if len(result["evidence"]) == 10:
                            return result
        else:
            raise ValueError("허용하지 않은 도구입니다.")
        return result
