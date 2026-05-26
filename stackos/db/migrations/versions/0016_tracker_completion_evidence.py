"""add tracker completion evidence fields

Revision ID: 0016_tracker_completion_evidence
Revises: 0015_stackos_task_tracker
Create Date: 2026-05-26

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0016_tracker_completion_evidence"
down_revision: str | None = "0015_stackos_task_tracker"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tracker_tasks",
        sa.Column("completion_evidence_json", sa.JSON(), nullable=True),
    )
    op.add_column(
        "tracker_tickets",
        sa.Column("completion_evidence_json", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tracker_tickets", "completion_evidence_json")
    op.drop_column("tracker_tasks", "completion_evidence_json")
