"""Engine and session factory.

SQLite locally (step 1), Postgres from step 3. Nothing in models/ may use a
dialect-specific type — see CLAUDE.md.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from halflife.config import get_settings
from halflife.migrations_runner import assert_at_head

_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def _on_connect(dbapi_connection, _record) -> None:
    """SQLite does not enforce foreign keys unless asked."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


def get_engine() -> Engine:
    """The process engine, verified to match the migrations on first use.

    The check runs once per process and costs one query. It is here rather than
    at the MCP server's startup so that the remedy reaches the user where they
    are: a stale database answers a tool call with the instruction to run
    `halflife init`, instead of failing to attach and leaving them to find the
    harness's log.
    """
    global _engine
    if _engine is None:
        url = get_settings().resolved_db_url()
        _engine = create_engine(url, future=True)
        if _engine.dialect.name == "sqlite":
            event.listen(_engine, "connect", _on_connect)
        assert_at_head(_engine)
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transaction boundary. Repositories never open their own."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_for_testing(url: str) -> None:
    """Point the process at a different database. Used by tests only."""
    global _engine, _session_factory
    _engine = create_engine(url, future=True)
    if _engine.dialect.name == "sqlite":
        event.listen(_engine, "connect", _on_connect)
    _session_factory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
