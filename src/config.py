import json
from pathlib import Path
from pydantic import BaseModel

from .utils import APP_ROOT


class Config(BaseModel):
    openai_api_key: str = ""
    model_name: str = "gpt-4o"
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.7


def _settings_path() -> Path:
    return APP_ROOT / "settings.json"


def load_config() -> Config:
    path = _settings_path()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return Config(**data)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
    return Config()


def save_config(config: Config):
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(config.model_dump_json(indent=2), encoding="utf-8")
