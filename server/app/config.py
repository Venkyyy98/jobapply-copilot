from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parents[2]


def _resolve_path(env_name: str, default_relative: str) -> Path:
    value = os.getenv(env_name)
    if value:
        path = Path(value)
        return path if path.is_absolute() else (BASE_DIR / path)
    return BASE_DIR / default_relative


@dataclass(frozen=True)
class Settings:
    openai_api_key: str
    jac_token: str
    serpapi_key: str
    hunter_api_key: str
    db_path: Path
    output_dir: Path
    packet_dir: Path
    candidate_profile_path: Path
    preferences_path: Path


settings = Settings(
    openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    jac_token=os.getenv("JAC_TOKEN", ""),
    serpapi_key=os.getenv("SERPAPI_KEY", ""),
    hunter_api_key=os.getenv("HUNTER_API_KEY", ""),
    db_path=_resolve_path("JAC_DB_PATH", "jobapply.db"),
    output_dir=_resolve_path("JAC_OUTPUT_DIR", "outputs"),
    packet_dir=_resolve_path("JAC_PACKET_DIR", str(Path.home() / "Documents" / "JobApplyCopilot")),
    candidate_profile_path=_resolve_path("JAC_CANDIDATE_PROFILE", "server/data/candidate_profile.yaml"),
    preferences_path=_resolve_path("JAC_PREFERENCES", "server/data/preferences.yaml"),
)
