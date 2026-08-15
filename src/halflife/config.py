"""Runtime configuration.

Everything here is environment-driven so that step 3 (FastAPI + Postgres) is a
change of values, not a change of code.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_db_path() -> Path:
    return Path.home() / ".halflife" / "halflife.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HALFLIFE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Left unset by default: the anthropic SDK resolves ANTHROPIC_API_KEY,
    # ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile on its own. Only set
    # this when you need to inject a specific key.
    anthropic_api_key: str | None = None

    db_url: str | None = None

    # Generation. Thinking is on by default on claude-opus-5; depth of reasoning
    # is controlled by effort, not by a token budget.
    model_id: str = "claude-opus-5"
    effort: str = "high"
    max_tokens: int = 16000

    # Roughly how many words a reader gets through in a minute of technical prose.
    words_per_minute: int = 200

    # How many issues the series plan sketches out at subscribe time.
    series_plan_length: int = 10

    def resolved_db_url(self) -> str:
        if self.db_url:
            return self.db_url
        path = _default_db_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite+pysqlite:///{path}"


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
