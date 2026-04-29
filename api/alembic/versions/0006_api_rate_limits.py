"""api provider rate limits

Revision ID: 0006_api_rate_limits
Revises: 0005_citation_graph
Create Date: 2026-04-29
"""

from alembic import op

revision = "0006_api_rate_limits"
down_revision = "0005_citation_graph"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE api_rate_limits (
            provider        TEXT PRIMARY KEY,
            last_request_at TIMESTAMPTZ NOT NULL DEFAULT '-infinity'::timestamptz
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS api_rate_limits")
