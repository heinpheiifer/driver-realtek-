"""
Update .env file values from Python (used for auto-detected MT5 Wine paths).
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from loguru import logger

_ENV_PATH = Path(__file__).parent.parent / ".env"


def env_file_path() -> Path:
    return _ENV_PATH


def update_env_file(key: str, value: str, *, reload: bool = True) -> bool:
    """
    Set or replace an environment variable in .env and optionally os.environ.

    Returns True if the file was updated.
    """
    env_path = env_file_path()
    if not env_path.exists():
        example = env_path.parent / ".env.example"
        if example.exists():
            env_path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            env_path.write_text("", encoding="utf-8")

    text = env_path.read_text(encoding="utf-8")
    line = f"{key}={value}"
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)

    if pattern.search(text):
        new_text = pattern.sub(line, text)
    else:
        new_text = text.rstrip("\n") + ("\n" if text else "") + line + "\n"

    if new_text != text:
        env_path.write_text(new_text, encoding="utf-8")
        logger.info(f"Updated {key} in .env")

    os.environ[key] = value
    if reload:
        try:
            from dotenv import load_dotenv

            load_dotenv(env_path, override=True)
        except ImportError:
            pass
    return True


def get_env_file_value(key: str) -> Optional[str]:
    """Read a key from .env without loading all of dotenv."""
    env_path = env_file_path()
    if not env_path.exists():
        return None
    prefix = f"{key}="
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        if raw.startswith(prefix):
            return raw[len(prefix) :].strip().strip('"')
    return None
