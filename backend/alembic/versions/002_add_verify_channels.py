"""add telegram + email verify_channel enum values

Revision ID: 002
Revises: 001
"""
from collections.abc import Sequence

from alembic import op

revision: str = '002'
down_revision: str | None = '001'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Postgres can't use a new enum value in the same transaction that added
    # it, and won't let ALTER TYPE ... ADD VALUE run inside an open
    # transaction block either — autocommit_block() is alembic's documented
    # way around both restrictions.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE verify_channel ADD VALUE IF NOT EXISTS 'telegram'")
        op.execute("ALTER TYPE verify_channel ADD VALUE IF NOT EXISTS 'email'")


def downgrade() -> None:
    # Postgres has no ALTER TYPE ... DROP VALUE. A true reverse migration
    # would mean rebuilding the enum type and remapping every
    # verifications.channel row using it — not worth it for a hackathon
    # project with no production data. `make demo-reset` already does
    # `alembic downgrade base && alembic upgrade head` (a full rebuild via
    # 001), which is the actual reset path used in this repo.
    raise NotImplementedError(
        "Postgres can't DROP VALUE from an enum. Use "
        "`alembic downgrade base && alembic upgrade head` (full rebuild) "
        "instead of downgrading past this revision."
    )
