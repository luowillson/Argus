"""citation graph metadata

Revision ID: 0005_citation_graph
Revises: 0003
Create Date: 2026-04-29
"""

from alembic import op

revision = "0005_citation_graph"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE papers ALTER COLUMN openreview_url DROP NOT NULL")
    op.execute("ALTER TABLE papers ADD COLUMN references_count INT")
    op.execute(
        "ALTER TABLE papers ADD COLUMN citation_metadata JSONB NOT NULL DEFAULT '{}'::jsonb"
    )
    op.execute("ALTER TABLE papers ADD COLUMN citation_enriched_at TIMESTAMPTZ")

    op.execute(
        """
        CREATE TABLE paper_identifiers (
            paper_id    TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
            namespace   TEXT NOT NULL,
            value       TEXT NOT NULL,
            confidence  NUMERIC(4,3) NOT NULL DEFAULT 1.0,
            source      TEXT NOT NULL,
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (paper_id, namespace, value)
        )
        """
    )
    op.execute(
        "CREATE UNIQUE INDEX paper_identifiers_lookup_idx "
        "ON paper_identifiers(namespace, value)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS paper_identifiers")
    op.execute("ALTER TABLE papers DROP COLUMN IF EXISTS citation_enriched_at")
    op.execute("ALTER TABLE papers DROP COLUMN IF EXISTS citation_metadata")
    op.execute("ALTER TABLE papers DROP COLUMN IF EXISTS references_count")
    op.execute("ALTER TABLE papers ALTER COLUMN openreview_url SET NOT NULL")
