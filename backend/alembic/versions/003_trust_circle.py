"""trust circle (elder<->guardian pairing + alert log)

Revision ID: 003
Revises: 002
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = '003'
down_revision: str | None = '002'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('trust_circles',
    sa.Column('elder_channel', sa.Enum('whatsapp', 'telegram', 'email', name='circle_channel'), nullable=False),
    sa.Column('elder_external_id', sa.String(length=200), nullable=False),
    sa.Column('pairing_code', sa.String(length=6), nullable=False),
    sa.Column('pairing_code_expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('guardian_name', sa.String(length=80), nullable=True),
    sa.Column('guardian_email', sa.String(length=255), nullable=True),
    sa.Column('guardian_channel', sa.Enum('whatsapp', 'telegram', 'email', name='circle_channel'), nullable=True),
    sa.Column('guardian_channel_external_id', sa.String(length=200), nullable=True),
    sa.Column('circle_token', sa.String(length=64), nullable=True),
    sa.Column('status', sa.Enum('pending', 'active', 'revoked', name='circle_status'), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('circle_token')
    )
    op.create_index('ix_trust_circles_elder', 'trust_circles', ['elder_channel', 'elder_external_id'], unique=False)
    op.create_table('circle_alerts',
    sa.Column('circle_id', sa.UUID(), nullable=False),
    sa.Column('verdict', sa.String(length=40), nullable=False),
    sa.Column('plain_headline', sa.String(length=300), nullable=False),
    sa.Column('campaign', sa.String(length=120), nullable=True),
    sa.Column('delivered_via', sa.String(length=20), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['circle_id'], ['trust_circles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('circle_alerts')
    op.drop_index('ix_trust_circles_elder', table_name='trust_circles')
    op.drop_table('trust_circles')
    for enum_name in ('circle_channel', 'circle_status'):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
