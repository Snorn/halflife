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
        # utf-8-sig, not utf-8: Windows tooling writes .env with a BOM by
        # default (`Out-File -Encoding utf8`, Notepad), which otherwise makes
        # the first key parse as "﻿HALFLIFE_..." and silently not match.
        # This encoding strips a BOM when present and is identical without one.
        env_file_encoding="utf-8-sig",
        extra="ignore",
    )

    # Left unset by default: the anthropic SDK resolves ANTHROPIC_API_KEY,
    # ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile on its own. Only set
    # this when you need to inject a specific key.
    anthropic_api_key: str | None = None

    db_url: str | None = None

    # Generation. Thinking is on by default on claude-opus-5; depth of reasoning
    # is controlled by effort, not by a token budget.
    #
    # medium, not high: two depth-eval runs at medium each scored 11/12 against
    # high's 9/12, with depth 5 clean both times, at $0.077 a call against
    # roughly $0.19. Higher effort explores more before answering, which a
    # tightly-rubric-constrained task does not want. Raise it if a workload
    # shows otherwise — but measure, because the intuition is wrong here.
    model_id: str = "claude-opus-5"
    effort: str = "medium"
    # Thinking bills as output on this model and is the bulk of it: a 1,000-word
    # issue is some 1,400 tokens of prose behind ten times that of reasoning. A
    # depth-5 eval generation hit the old 16,000 ceiling mid-run, which fails the
    # whole call and takes the run with it. Raised with room, and it costs
    # nothing to carry — billing is per token produced, not per token allowed.
    max_tokens: int = 32000

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
