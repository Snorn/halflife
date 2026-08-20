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


class SchemaOutOfDate(RuntimeError):
    """The database does not match the migrations this code ships with."""


def head_revision() -> str | None:
    """The revision this checkout expects."""
    from alembic.script import ScriptDirectory

    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def current_revision(engine) -> str | None:
    """The revision the database is actually at, or None if it has no schema."""
    from alembic.runtime.migration import MigrationContext

    with engine.connect() as connection:
        return MigrationContext.configure(connection).get_current_revision()


def assert_at_head(engine) -> None:
    """Fail with the remedy rather than with an OperationalError later.

    A database left behind the code does not announce itself. The first tool
    call touching a new column raises an opaque "no such column" from deep in
    SQLAlchemy, which reads as a bug in the tool rather than as a missing
    upgrade. This has happened twice on a real install, once for
    delivery.plan_index and once for the signal table, so the check is worth
    the one query it costs.

    Called from get_engine, which the CLI's `init` deliberately does not use --
    the check must never be able to block its own remedy.
    """
    from alembic.script import ScriptDirectory

    head = head_revision()
    current = current_revision(engine)
    if current == head:
        return

    if current is None:
        raise SchemaOutOfDate(
            "This database has no schema yet. Run:\n\n    halflife init\n"
        )

    known = {script.revision for script in ScriptDirectory.from_config(alembic_config()).walk_revisions()}
    if current in known:
        raise SchemaOutOfDate(
            f"The database schema is behind this code: it is at revision {current}, "
            f"and {head} is expected. Nothing is lost by upgrading. Run:\n\n    halflife init\n"
        )

    raise SchemaOutOfDate(
        f"The database is at revision {current}, which this checkout does not contain "
        f"(it expects {head}). The database was written by newer code than this, so "
        "upgrading will not help — update the checkout instead."
    )
