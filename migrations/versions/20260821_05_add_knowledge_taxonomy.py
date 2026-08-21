"""Add knowledge taxonomy and weighted search metadata.

Revision ID: 20260821_05
Revises: 20260819_04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260821_05"
down_revision: str | None = "20260819_04"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("ix_knowledge_articles_search_vector", table_name="knowledge_articles")
    op.drop_column("knowledge_articles", "search_vector")
    op.add_column(
        "knowledge_articles",
        sa.Column(
            "categories",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )
    op.execute(
        "CREATE FUNCTION knowledge_taxonomy_text(items text[]) RETURNS text "
        "LANGUAGE sql IMMUTABLE PARALLEL SAFE "
        "RETURN array_to_string(items, ' ')"
    )
    op.add_column(
        "knowledge_articles",
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'::text[]"),
            nullable=False,
        ),
    )
    op.add_column(
        "knowledge_articles",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
                "setweight(to_tsvector('english', knowledge_taxonomy_text(categories)), 'A') || "
                "setweight(to_tsvector('english', knowledge_taxonomy_text(tags)), 'A') || "
                "setweight(to_tsvector('english', coalesce(content, '')), 'B')",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_knowledge_articles_search_vector",
        "knowledge_articles",
        ["search_vector"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    op.drop_index("ix_knowledge_articles_search_vector", table_name="knowledge_articles")
    op.drop_column("knowledge_articles", "search_vector")
    op.drop_column("knowledge_articles", "tags")
    op.drop_column("knowledge_articles", "categories")
    op.execute("DROP FUNCTION knowledge_taxonomy_text(text[])")
    op.add_column(
        "knowledge_articles",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed(
                "setweight(to_tsvector('english', coalesce(title, '')), 'A') || "
                "setweight(to_tsvector('english', coalesce(content, '')), 'B')",
                persisted=True,
            ),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_knowledge_articles_search_vector",
        "knowledge_articles",
        ["search_vector"],
        postgresql_using="gin",
    )
