"""open threads carry their source

Series.open_threads was a list of strings, and whether a thread came from the
reader was decided by matching a prefix on the text. Nothing verified that on
the way in, and record_issue replaces the list wholesale from harness-supplied
strings — so a harness could mark its own text as reader-requested and inherit
the authority the prompt grants those. Issue #8.

Each entry becomes {"text": ..., "source": "issue" | "reader"}. The column type
does not change; JSON held strings and now holds objects.

Existing rows are converted by the rule the old code used to read them, which is
the only evidence available: a string carrying the prefix was written by
add_thread and nothing else could write it, so it becomes a reader thread with
the prefix stripped. Everything else came from a generation.

Revision ID: 617368818ce8
Revises: 64cec47ead2f
Create Date: 2026-08-23 01:52:00.000000
"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '617368818ce8'
down_revision: Union[str, None] = '64cec47ead2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PREFIX = "Asked for by the reader:"


def _rows(conn):
    return conn.execute(sa.text("SELECT id, open_threads FROM series")).all()


def upgrade() -> None:
    conn = op.get_bind()
    for series_id, raw in _rows(conn):
        threads = json.loads(raw) if raw else []
        converted = []
        for entry in threads:
            if isinstance(entry, dict):  # already converted
                converted.append(entry)
                continue
            text = str(entry)
            if text.startswith(PREFIX):
                converted.append(
                    {"text": text[len(PREFIX):].strip(), "source": "reader"}
                )
            else:
                converted.append({"text": text, "source": "issue"})
        conn.execute(
            sa.text("UPDATE series SET open_threads = :v WHERE id = :i"),
            {"v": json.dumps(converted), "i": series_id},
        )


def downgrade() -> None:
    conn = op.get_bind()
    for series_id, raw in _rows(conn):
        threads = json.loads(raw) if raw else []
        flattened = []
        for entry in threads:
            if not isinstance(entry, dict):
                flattened.append(str(entry))
                continue
            text = entry.get("text", "")
            # The prefix goes back on, because it is what the old renderer read.
            flattened.append(
                f"{PREFIX} {text}" if entry.get("source") == "reader" else text
            )
        conn.execute(
            sa.text("UPDATE series SET open_threads = :v WHERE id = :i"),
            {"v": json.dumps(flattened), "i": series_id},
        )
