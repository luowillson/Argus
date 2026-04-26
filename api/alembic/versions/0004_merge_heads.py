"""merge trgm and pathway branches

Revision ID: 0004_merge_heads
Revises: 0002_papers_abstract_trgm, 0003_pathway_enrichment
Create Date: 2026-04-25
"""

revision = "0004_merge_heads"
down_revision = ("0002_papers_abstract_trgm", "0003_pathway_enrichment")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
