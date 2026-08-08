"""sms channel + trust circle auto-guard token

Revision ID: 004
Revises: 003
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = '004'
down_revision: str | None = '003'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ALTER TYPE ... ADD VALUE cannot run inside Alembic's default
    # transactional-DDL block on Postgres (and even where it technically can,
    # the new value isn't usable until the transaction that added it
    # commits) — autocommit_block() is the documented way to do this safely.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE verify_channel ADD VALUE IF NOT EXISTS 'sms'")
        op.execute("ALTER TYPE circle_channel ADD VALUE IF NOT EXISTS 'sms'")

    op.add_column(
        'trust_circles',
        sa.Column('guard_token', sa.String(length=64), nullable=True),
    )
    op.create_unique_constraint('uq_trust_circles_guard_token', 'trust_circles', ['guard_token'])


def downgrade() -> None:
    # Same limitation 002 already documents: Postgres has no ALTER TYPE ...
    # DROP VALUE, so the two 'sms' enum values added above can't be reverted
    # by this function no matter what it does. Rather than leave a downgrade
    # that silently drops the column while quietly leaving stray enum values
    # behind, this fails the same way 002 does — full rebuild is the only
    # honest reverse path, and `make demo-reset` already does that.
    raise NotImplementedError(
        "Postgres can't DROP VALUE from an enum. Use "
        "`alembic downgrade base && alembic upgrade head` (full rebuild) "
        "instead of downgrading past this revision."
    )
