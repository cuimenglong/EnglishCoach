"""Launcher script for the English Coach application.

Works both as source (python run.py) and as frozen PyInstaller exe.
"""
import sys
import os


def main():
    # Determine project root
    if getattr(sys, "frozen", False):
        project_root = os.path.dirname(os.path.abspath(sys.executable))
    else:
        project_root = os.path.dirname(os.path.abspath(__file__))

    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    os.chdir(project_root)

    from src.app import EnglishCoachApp

    app = EnglishCoachApp()
    app.run()


if __name__ == "__main__":
    main()
