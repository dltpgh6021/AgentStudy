import tempfile
import unittest
from pathlib import Path

from repo_scout.analyzer import describe_role, render_markdown, scan_repository


class AnalyzerTests(unittest.TestCase):
    def test_describe_known_files(self) -> None:
        self.assertIn("소개", describe_role(Path("README.md")))
        self.assertIn("테스트", describe_role(Path("tests/test_app.py")))

    def test_scan_and_render(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "README.md").write_text("# Sample", encoding="utf-8")
            source = root / "src"
            source.mkdir()
            (source / "app.py").write_text("print('hello')", encoding="utf-8")

            result = scan_repository(root)
            report = render_markdown(result)

            self.assertEqual(2, len(result.files))
            self.assertIn("README.md", report)
            self.assertIn("src/app.py", report)


if __name__ == "__main__":
    unittest.main()

