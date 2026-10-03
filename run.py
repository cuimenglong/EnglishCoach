"""Launcher script for the English Coach application.

Works both as source (python run.py) and as frozen PyInstaller exe.
"""
import sys
import os
import logging


def main():
    # Determine project root
    if getattr(sys, "frozen", False):
        project_root = os.path.dirname(os.path.abspath(sys.executable))
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))

    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    os.chdir(project_root)

    # Logs go next to the app so a failed LLM call is diagnosable after the fact.
    log_dir = os.path.join(project_root, "data")
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(log_dir, "englishcoach.log"), encoding="utf-8"),
        ],
    )

    from src.app import EnglishCoachApp

    app = EnglishCoachApp()
    app.run()


if __name__ == "__main__":
    main()
