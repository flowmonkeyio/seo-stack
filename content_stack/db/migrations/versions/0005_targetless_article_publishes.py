"""allow targetless article publish records

Revision ID: 0005_targetless_article_publishes
Revises: 0004_workspace_bindings
Create Date: 2026-05-20

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_targetless_article_publishes"
down_revision: str | None = "0004_workspace_bindings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("article_publishes") as batch_op:
        batch_op.alter_column(
            "target_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
    op.create_index(
        "uq_article_publishes_external",
        "article_publishes",
        ["article_id", "version_published"],
        unique=True,
        sqlite_where=sa.text("target_id IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_article_publishes_external", table_name="article_publishes")
    with op.batch_alter_table("article_publishes") as batch_op:
        batch_op.alter_column(
            "target_id",
            existing_type=sa.Integer(),
            nullable=False,
        )
