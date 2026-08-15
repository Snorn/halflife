"""Run Alembic programmatically so the CLI has one schema source of truth.

Alembic owns the schema — there is no ``create_all`` shortcut, because a second
path for creating tables is a second thing to keep in sync.
"""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config

from halflife.config import get_settings


def _repo_root() -> Path:
    # src/halflife/migrations_runner.py -> src/halflife -> src -> repo root
    return Path(__file__).resolve().parents[2]


def alembic_config() -> Config:
    root = _repo_root()
    ini = root / "alembic.ini"
    if not ini.exists():
        raise FileNotFoundError(
            f"Could not find alembic.ini at {ini}. Run the CLI from a checkout of the repo."
        )
    config = Config(str(ini))
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", get_settings().resolved_db_url())
    return config


def upgrade_to_head() -> None:
    command.upgrade(alembic_config(), "head")
