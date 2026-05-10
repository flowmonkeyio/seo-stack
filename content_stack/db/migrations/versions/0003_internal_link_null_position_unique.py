"""treat NULL internal-link positions as one uniqueness bucket

Revision ID: 0003_internal_link_null_position_unique
Revises: 0002_initial_schema
Create Date: 2026-05-09

"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_internal_link_null_position_unique"
down_revision: str | None = "0002_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_internal_links_unique")
    op.execute(
        "CREATE UNIQUE INDEX uq_internal_links_unique "
        "ON internal_links(from_article_id, to_article_id, anchor_text, COALESCE(position, -1)) "
        "WHERE status != 'dismissed'"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_internal_links_unique")
    op.execute(
        "CREATE UNIQUE INDEX uq_internal_links_unique "
        "ON internal_links(from_article_id, to_article_id, anchor_text, position) "
        "WHERE status != 'dismissed'"
    )
