import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pydantic import BaseModel

from .utils import APP_ROOT


class Config(BaseModel):
    openai_api_key: str = ""
    model_name: str = "gpt-4o"
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.7


def _env_path() -> Path:
    return APP_ROOT / ".env"


def load_config() -> Config:
    env_path = _env_path()
    if env_path.exists():
        load_dotenv(env_path, override=True)
    else:
        load_dotenv(override=True)
    return Config(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        model_name=os.getenv("MODEL_NAME", "gpt-4o"),
        base_url=os.getenv("BASE_URL", "https://api.openai.com/v1"),
        temperature=float(os.getenv("TEMPERATURE", "0.7")),
    )


def save_config(config: Config):
    env_path = _env_path()
    if not env_path.exists():
        env_path.write_text("", encoding="utf-8")

    lines = env_path.read_text(encoding="utf-8").splitlines()

    key_map = {
        "OPENAI_API_KEY": config.openai_api_key,
        "MODEL_NAME": config.model_name,
        "BASE_URL": config.base_url,
        "TEMPERATURE": str(config.temperature),
    }

    seen = set()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in key_map:
                new_lines.append(f"{key}={key_map[key]}")
                seen.add(key)
                continue
        new_lines.append(line)

    for key, value in key_map.items():
        if key not in seen:
            new_lines.append(f"{key}={value}")

    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    load_dotenv(env_path, override=True)
