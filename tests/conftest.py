"""Shared fixtures: redirect every module-level data path at a tmp dir.

The modules in src/ capture DATA_DIR / DB_PATH at import time, so they have to
be patched per-module rather than once globally.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Point all persistence at tmp_path so tests never touch real user data."""
    import src.utils as utils
    import src.config as config
    import src.knowledge as knowledge
    import src.sessions as sessions
    import src.dynamic_profile as dynamic_profile

    # summary.py and course_plan.py do not own a DATA_DIR name -- they call
    # utils.read_json/write_json/daily_log_path, which resolve DATA_DIR at call
    # time, so patching utils covers them.
    patches = {
        utils: {"DATA_DIR": tmp_path, "APP_ROOT": tmp_path},
        config: {"APP_ROOT": tmp_path},
        knowledge: {"DATA_DIR": tmp_path, "DB_PATH": tmp_path / "knowledge.db"},
        sessions: {"DATA_DIR": tmp_path, "SESSION_FILE": tmp_path / "session.json"},
        dynamic_profile: {"PROFILE_PATH": tmp_path / "dynamic_profile.json"},
    }
    for module, attrs in patches.items():
        for name, value in attrs.items():
            monkeypatch.setattr(module, name, value)

    return tmp_path
