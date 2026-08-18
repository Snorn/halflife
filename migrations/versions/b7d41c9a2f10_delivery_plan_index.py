"""delivery plan index

Records which series-plan entry an issue actually took, so the plan block can
mark written and rejected entries by fact rather than by position.

Revision ID: b7d41c9a2f10
Revises: e82053c13046
Create Date: 2026-08-18 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7d41c9a2f10'
down_revision: Union[str, None] = 'e82053c13046'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable with no backfill: existing rows genuinely do not know which entry
    # they took, and a guessed value would be indistinguishable from a reported
    # one. Null means exactly that, and only those rows fall back to position;
    # rows written from here on store 0 when the issue took no plan entry.
    with op.batch_alter_table('delivery', schema=None) as batch_op:
        batch_op.add_column(sa.Column('plan_index', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('delivery', schema=None) as batch_op:
        batch_op.drop_column('plan_index')
