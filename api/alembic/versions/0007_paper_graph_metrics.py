"""paper graph metrics

Revision ID: 0007_paper_graph_metrics
Revises: 0006_api_rate_limits
Create Date: 2026-04-29
"""

from alembic import op

revision = "0007_paper_graph_metrics"
down_revision = "0006_api_rate_limits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE paper_graph_metrics (
            paper_id     TEXT PRIMARY KEY REFERENCES papers(id) ON DELETE CASCADE,
            pagerank     NUMERIC(18,12) NOT NULL,
            in_degree    INTEGER NOT NULL DEFAULT 0,
            out_degree   INTEGER NOT NULL DEFAULT 0,
            computed_at  TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX paper_graph_metrics_pagerank_idx
        ON paper_graph_metrics (pagerank DESC)
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS paper_graph_metrics")
