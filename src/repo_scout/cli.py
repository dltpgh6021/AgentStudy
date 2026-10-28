from __future__ import annotations

import argparse
from pathlib import Path

from .analyzer import render_markdown, scan_repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="로컬 저장소의 구조와 파일 역할을 분석합니다.")
    parser.add_argument("repository", type=Path, help="분석할 로컬 저장소 폴더")
    parser.add_argument("-o", "--output", type=Path, default=Path("repo-analysis.md"), help="결과 파일")
    parser.add_argument("--max-files", type=int, default=500, help="분석할 최대 파일 수")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        analysis = scan_repository(args.repository, max_files=args.max_files)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_markdown(analysis), encoding="utf-8")
    print(f"분석 완료: {args.output.resolve()}")


if __name__ == "__main__":
    main()

