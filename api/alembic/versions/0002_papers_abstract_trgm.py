"""GIN trgm index on paper abstract (coalesced) for fuzzy search.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS papers_abstract_trgm
        ON papers USING gin ((COALESCE(abstract, '')) gin_trgm_ops)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS papers_abstract_trgm")
