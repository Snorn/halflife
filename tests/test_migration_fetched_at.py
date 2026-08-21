"""The 64cec47ead2f backfill, tested against a real database at the old revision.

The split of `read_at` into `fetched_at` + `read_at` re-attributes rows that
already exist, and that re-attribution is a judgement rather than a rename: every
old value recorded a fetch, and only the rows carrying feedback have any evidence
a person read anything. Getting it wrong is silent — the column types are
identical and nothing downstream would complain — so it is asserted here rather
than trusted.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from tests.conftest import ROOT

BEFORE = "ef7b40c8752b"
AFTER = "64cec47ead2f"

_ROWS = """
INSERT INTO delivery (
    id, tenant_id, subscription_id, series_id, issue_number, title, body_markdown,
    next_suggested, depth, duration_minutes, source, depth_rubric_version,
    generation_prompt_version, read_at, feedback, created_at, updated_at
) VALUES
 ('rated',   't', 's', 'se', 1, 'Rated',   'b', 'n', 3, 5, 'api', '6', '4',
  '2026-08-20 08:00:00', 'just_right', '2026-08-20 07:00:00', '2026-08-20 08:00:00'),
 ('fetched', 't', 's', 'se', 2, 'Fetched', 'b', 'n', 3, 5, 'api', '6', '4',
  '2026-08-20 09:00:00', NULL,         '2026-08-20 07:00:00', '2026-08-20 09:00:00'),
 ('neither', 't', 's', 'se', 3, 'Neither', 'b', 'n', 3, 5, 'api', '6', '4',
  NULL,                 NULL,         '2026-08-20 07:00:00', '2026-08-20 07:00:00')
"""


def _config(url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", url)
    return config


def _state(engine) -> dict[str, tuple]:
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text("SELECT id, fetched_at, read_at FROM delivery ORDER BY id")
        ).all()
    return {r[0]: (r[1], r[2]) for r in rows}


def test_the_backfill_reattributes_each_row_to_the_fact_it_recorded(tmp_path):
    url = f"sqlite+pysqlite:///{tmp_path / 'old.db'}"
    config = _config(url)
    command.upgrade(config, BEFORE)

    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(sa.text(_ROWS))

    command.upgrade(config, AFTER)
    state = _state(engine)

    fetched, read = state["rated"]
    assert fetched is not None, "the old value recorded a fetch, so it carries over"
    assert read is not None, "feedback is the evidence a person read it"

    fetched, read = state["fetched"]
    assert fetched is not None
    assert read is None, "fetched and never rated: back to the inbox, which is honest"

    assert state["neither"] == (None, None)


def test_the_downgrade_puts_the_two_facts_back_into_one_column(tmp_path):
    """The single-column world could not tell them apart, so it takes the fetch."""
    url = f"sqlite+pysqlite:///{tmp_path / 'round.db'}"
    config = _config(url)
    command.upgrade(config, BEFORE)

    engine = sa.create_engine(url)
    with engine.begin() as conn:
        conn.execute(sa.text(_ROWS))

    command.upgrade(config, AFTER)
    command.downgrade(config, BEFORE)

    with engine.connect() as conn:
        rows = dict(
            conn.execute(sa.text("SELECT id, read_at FROM delivery ORDER BY id")).all()
        )

    assert rows["rated"] is not None
    assert rows["fetched"] is not None, "the fetch is what the old column held"
    assert rows["neither"] is None
