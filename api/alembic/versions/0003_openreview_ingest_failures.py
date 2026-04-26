"""Track permanent OpenReview ingest failures.

Revision ID: 0003
Revises: 0004_merge_heads
"""

from alembic import op

revision = "0003"
down_revision = "0004_merge_heads"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS openreview_ingest_failures (
            paper_id    TEXT PRIMARY KEY,
            attempts    INT NOT NULL,
            error       TEXT NOT NULL,
            failed_at   TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS openreview_ingest_failures")
