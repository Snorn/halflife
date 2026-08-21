"""delivery fetched_at

Splits what read_at was trying to be into two facts, and re-attributes the
existing rows to whichever of them they actually recorded.

Every read_at written before this migration was set by `halflife read` or by the
MCP read tool, at the moment the text left the database — a fetch, whoever or
whatever was on the other end. So fetched_at inherits all of them unchanged.

read_at survives only where the delivery also carries feedback. That is the one
event on record that cannot happen without a person: a rating is an act, and
nothing fetches one by accident. Rows fetched but never rated have their read_at
cleared and return to the inbox, which is correct under the new meaning — they
are awaiting an acknowledgement that was never given, and the old column was
only ever asserting otherwise.

Revision ID: 64cec47ead2f
Revises: ef7b40c8752b
Create Date: 2026-08-21 23:19:07.259185
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '64cec47ead2f'
down_revision: Union[str, None] = 'ef7b40c8752b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('delivery', schema=None) as batch_op:
        batch_op.add_column(sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=True))

    op.execute("UPDATE delivery SET fetched_at = read_at WHERE read_at IS NOT NULL")
    op.execute("UPDATE delivery SET read_at = NULL WHERE feedback IS NULL")


def downgrade() -> None:
    # read_at absorbs fetched_at again, because the single-column world could
    # not tell them apart and this is the value it would have held.
    op.execute(
        "UPDATE delivery SET read_at = fetched_at "
        "WHERE read_at IS NULL AND fetched_at IS NOT NULL"
    )

    with op.batch_alter_table('delivery', schema=None) as batch_op:
        batch_op.drop_column('fetched_at')
