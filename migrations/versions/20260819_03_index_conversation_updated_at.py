"""Index conversations by update time.

Revision ID: 20260819_03
Revises: 20260806_02
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260819_03"
down_revision: str | None = "20260806_02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_conversations_updated_at", "conversations", ["updated_at"])


def downgrade() -> None:
    op.drop_index("ix_conversations_updated_at", table_name="conversations")
