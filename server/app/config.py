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
    cors_origins: list[str]
    public_api_base_url: str
    analyze_daily_quota: int
    docs_daily_quota: int
    outreach_daily_quota: int
    generated_file_retention_hours: int
    linkedin_discovery_enabled: bool
    allow_server_llm_fallback: bool
    db_path: Path
    database_url: str
    output_dir: Path
    packet_dir: Path
    candidate_profile_path: Path
    preferences_path: Path


settings = Settings(
    openai_api_key=os.getenv("OPENAI_API_KEY", ""),
    jac_token=os.getenv("JAC_TOKEN", ""),
    serpapi_key=os.getenv("SERPAPI_KEY", ""),
    hunter_api_key=os.getenv("HUNTER_API_KEY", ""),
    cors_origins=[
        origin.strip()
        for origin in os.getenv(
            "JAC_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000,http://localhost:3001,http://127.0.0.1:3001",
        ).split(",")
        if origin.strip()
    ],
    public_api_base_url=os.getenv("NEXT_PUBLIC_API_BASE_URL", "http://127.0.0.1:8787"),
    analyze_daily_quota=int(os.getenv("JAC_ANALYZE_DAILY_QUOTA", "25")),
    docs_daily_quota=int(os.getenv("JAC_DOCS_DAILY_QUOTA", "10")),
    outreach_daily_quota=int(os.getenv("JAC_OUTREACH_DAILY_QUOTA", "20")),
    generated_file_retention_hours=int(os.getenv("JAC_GENERATED_FILE_RETENTION_HOURS", "72")),
    linkedin_discovery_enabled=os.getenv("JAC_LINKEDIN_DISCOVERY_ENABLED", "false").strip().lower() == "true",
    allow_server_llm_fallback=os.getenv("JAC_ALLOW_SERVER_LLM_FALLBACK", "false").strip().lower() == "true",
    db_path=_resolve_path("JAC_DB_PATH", "jobapply.db"),
    database_url=os.getenv("DATABASE_URL", "").strip(),
    output_dir=_resolve_path("JAC_OUTPUT_DIR", "outputs"),
    packet_dir=_resolve_path("JAC_PACKET_DIR", str(Path.home() / "Documents" / "JobApplyCopilot")),
    candidate_profile_path=_resolve_path("JAC_CANDIDATE_PROFILE", "server/data/candidate_profile.yaml"),
    preferences_path=_resolve_path("JAC_PREFERENCES", "server/data/preferences.yaml"),
)
