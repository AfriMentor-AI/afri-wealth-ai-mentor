"""initial schema

Revision ID: a1b2c3d4e5f6
Revises:
Create Date: 2026-08-06 00:00:00.000000
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "insight_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("media_type", sa.String(10), nullable=False, server_default="text"),
        sa.Column("duration_seconds", sa.Integer, nullable=False),
        sa.Column("language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("difficulty", sa.String(12), nullable=False, server_default="beginner"),
        sa.Column("media_url", sa.String(500), nullable=True),
        sa.Column("thumbnail_url", sa.String(500), nullable=True),
        sa.Column("transcript_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_insight_items_category", "insight_items", ["category"])
    op.create_index("ix_insight_items_media_type", "insight_items", ["media_type"])
    op.create_index("ix_insight_items_language", "insight_items", ["language"])
    op.create_index("ix_insight_items_difficulty", "insight_items", ["difficulty"])

    op.create_table(
        "insight_favorites",
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column(
            "insight_id",
            sa.String(36),
            sa.ForeignKey("insight_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "insight_progress",
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column(
            "insight_id",
            sa.String(36),
            sa.ForeignKey("insight_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("position_seconds", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completed", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("insight_progress")
    op.drop_table("insight_favorites")
    op.drop_index("ix_insight_items_difficulty", table_name="insight_items")
    op.drop_index("ix_insight_items_language", table_name="insight_items")
    op.drop_index("ix_insight_items_media_type", table_name="insight_items")
    op.drop_index("ix_insight_items_category", table_name="insight_items")
    op.drop_table("insight_items")
