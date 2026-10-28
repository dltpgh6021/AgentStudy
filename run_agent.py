"""Run Repo Scout's Gemini agent without installing the package."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))
from repo_scout.agent import main

if __name__ == "__main__":
    main()
