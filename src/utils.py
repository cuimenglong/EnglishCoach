import json
import sys
from pathlib import Path


def get_app_root() -> Path:
    """Return the writable application root.

    - Frozen exe: directory containing the executable
    - Source run: project root (parent of src/)
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_ROOT = get_app_root()
DATA_DIR = APP_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def read_json(filename: str, default=None):
    path = DATA_DIR / filename
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(filename: str, data):
    path = DATA_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def daily_log_path(date_str: str | None = None) -> Path:
    from datetime import date

    date_str = date_str or date.today().isoformat()
    log_dir = DATA_DIR / "daily_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir / f"{date_str}.md"
