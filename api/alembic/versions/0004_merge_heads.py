"""Compatibility no-op for existing local databases.

Revision ID: 0004_merge_heads
Revises: 0002
"""

revision = "0004_merge_heads"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
