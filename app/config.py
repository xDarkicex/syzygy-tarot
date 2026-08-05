"""Application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).parent
PROJECT_ROOT = BASE_DIR.parent


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: Path
    secret_key: str
    profile_cookie: str = "syzygy_profile"
    cookie_max_age: int = 60 * 60 * 24 * 365
    templates_dir: Path = BASE_DIR / "templates"
    static_dir: Path = BASE_DIR / "static"
    merge_base_url: str = "https://api-gateway.merge.dev/v1"
    merge_model: str = "deepseek-v4-flash"
    merge_api_key: str = ""

    @property
    def cookie_secure(self) -> bool:
        return os.getenv("SYZYGY_ENV", "dev") == "prod"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings(
        database_path=Path(os.getenv("SYZYGY_DB", PROJECT_ROOT / "syzygy.db")),
        # Set SYZYGY_SECRET in production; readings are not sensitive, but the profile
        # cookie is signed to keep it from being edited by hand.
        secret_key=os.getenv("SYZYGY_SECRET", "dev-only-insecure-key"),
        merge_base_url=os.getenv("SYZYGY_MERGE_BASE_URL", "https://api-gateway.merge.dev/v1"),
        merge_model=os.getenv("SYZYGY_MERGE_MODEL", "deepseek-v4-flash"),
        # Read from env at call time via the service layer; this is the fallback.
        merge_api_key=os.getenv("SYZYGY_MERGE_API_KEY", ""),
    )
