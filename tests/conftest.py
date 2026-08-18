"""Test fixtures.

Everything here is offline and deterministic — no API calls. Anything that
asserts on real model output belongs in evals/, not here.

The database fixture runs the real Alembic migrations rather than
``create_all``, so a migration that does not actually produce the schema the
code expects fails the test suite.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy.orm import Session

from halflife import db
from halflife.generation.client import GenerationResult
from halflife.generation.schemas import GeneratedIssue, PlannedIssue, SeriesPlan

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def migrated_db(tmp_path) -> str:
    """A migrated, empty database, with the process pointed at it.

    No session is held open, so callers that open their own (the CLI) do not
    contend with the fixture for SQLite's write lock.
    """
    url = f"sqlite+pysqlite:///{tmp_path / 'test.db'}"

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")

    db.reset_for_testing(url)
    return url


@pytest.fixture
def session(migrated_db) -> Iterator[Session]:
    with db.session_scope() as db_session:
        yield db_session


class FakeClient:
    """Stands in for GenerationClient. Records prompts, returns canned output."""

    def __init__(self, responses: list[GeneratedIssue | SeriesPlan]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, str]] = []

    def generate(self, *, system: str, user: str, output_model):
        self.calls.append({"system": system, "user": user, "model": output_model.__name__})
        if not self._responses:
            raise AssertionError("FakeClient ran out of canned responses.")
        parsed = self._responses.pop(0)
        assert isinstance(parsed, output_model), (
            f"Canned response {type(parsed).__name__} does not match "
            f"requested {output_model.__name__}."
        )
        return GenerationResult(
            parsed=parsed,
            model_id="claude-opus-5",
            effort="high",
            input_tokens=1234,
            output_tokens=567,
        )

    @property
    def last_user_prompt(self) -> str:
        return self.calls[-1]["user"]


def make_plan(count: int = 3) -> SeriesPlan:
    return SeriesPlan(
        arc_summary="Starts at the request path and ends at failure modes under load.",
        issues=[
            PlannedIssue(index=i, title=f"Planned issue {i}", focus=f"Establishes thing {i}.")
            for i in range(1, count + 1)
        ],
    )


def make_issue(
    n: int,
    *,
    points: list[str] | None = None,
    threads: list[str] | None = None,
    plan_index: int = 0,
) -> GeneratedIssue:
    return GeneratedIssue(
        title=f"Issue {n}",
        body_markdown=f"Body of issue {n}.",
        covered_points_added=points if points is not None else [f"point-{n}a", f"point-{n}b"],
        open_threads=threads if threads is not None else [],
        next_suggested=f"Cover thing {n + 1}.",
        plan_index=plan_index,
    )
