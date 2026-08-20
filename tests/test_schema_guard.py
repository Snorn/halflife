"""A database left behind the code must say so.

From a real report: a work laptop pulled new code twice in one session and both
times the first tool call raised an opaque OperationalError from inside
SQLAlchemy — once for delivery.plan_index, once for the missing signal table.
Nothing said "run halflife init", so it read as a bug in the tool rather than
as an upgrade that had not been run.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine

from halflife.migrations_runner import (
    SchemaOutOfDate,
    assert_at_head,
    current_revision,
    head_revision,
)

PREVIOUS_REVISION = "b7d41c9a2f10"  # delivery plan index, one before the signal table


def _engine_at(tmp_path, revision: str | None):
    from alembic import command

    from halflife.migrations_runner import alembic_config

    url = f"sqlite:///{tmp_path / 'probe.db'}"
    config = alembic_config()
    config.set_main_option("sqlalchemy.url", url)
    if revision is not None:
        command.upgrade(config, revision)
    return create_engine(url, future=True)


def test_a_database_at_head_passes(tmp_path):
    engine = _engine_at(tmp_path, "head")

    assert_at_head(engine)
    assert current_revision(engine) == head_revision()


def test_a_database_behind_the_code_names_the_remedy(tmp_path):
    """The whole point: the message has to contain the command to run."""
    engine = _engine_at(tmp_path, PREVIOUS_REVISION)

    with pytest.raises(SchemaOutOfDate) as caught:
        assert_at_head(engine)

    message = str(caught.value)
    assert "halflife init" in message
    assert PREVIOUS_REVISION in message
    assert head_revision() in message


def test_an_empty_database_is_told_to_initialise(tmp_path):
    engine = _engine_at(tmp_path, None)

    with pytest.raises(SchemaOutOfDate, match="halflife init"):
        assert_at_head(engine)


def test_a_database_ahead_of_the_code_is_not_told_to_upgrade(tmp_path):
    """Upgrading cannot help when the database was written by newer code, and
    telling somebody to run init would send them in the wrong direction."""
    engine = _engine_at(tmp_path, "head")
    with engine.begin() as connection:
        from sqlalchemy import text

        connection.execute(text("UPDATE alembic_version SET version_num = 'from-the-future'"))

    with pytest.raises(SchemaOutOfDate) as caught:
        assert_at_head(engine)

    message = str(caught.value)
    assert "update the checkout" in message
    assert "halflife init" not in message


def test_init_can_still_run_against_a_stale_database():
    """The check must never block its own remedy: `init` upgrades through
    alembic directly and never asks for the checked engine."""
    import inspect

    from halflife import cli

    source = inspect.getsource(cli.init)

    assert "upgrade_to_head" in source
    assert "session_scope" not in source
    assert "init" in cli._NEEDS_NO_SCHEMA
