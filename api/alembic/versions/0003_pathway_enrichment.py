"""pathway enrichment metadata

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-25
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE learning_pathways "
        "ADD COLUMN enrichment_notes JSONB NOT NULL DEFAULT '{}'::jsonb"
    )
    op.execute(
        "ALTER TABLE learning_pathway_items "
        "ALTER COLUMN paper_id DROP NOT NULL"
    )
    op.execute(
        "ALTER TABLE learning_pathway_items "
        "ADD COLUMN match_quality TEXT NOT NULL DEFAULT 'strong'"
    )
    op.execute(
        "ALTER TABLE learning_pathway_items "
        "ADD COLUMN search_query TEXT"
    )
    op.execute(
        "ALTER TABLE learning_pathway_items "
        "ADD COLUMN anchor_concepts JSONB NOT NULL DEFAULT '[]'::jsonb"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE learning_pathway_items DROP COLUMN anchor_concepts")
    op.execute("ALTER TABLE learning_pathway_items DROP COLUMN search_query")
    op.execute("ALTER TABLE learning_pathway_items DROP COLUMN match_quality")
    op.execute(
        "ALTER TABLE learning_pathway_items "
        "ALTER COLUMN paper_id SET NOT NULL"
    )
    op.execute("ALTER TABLE learning_pathways DROP COLUMN enrichment_notes")
