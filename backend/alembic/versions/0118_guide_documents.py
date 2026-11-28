"""FR-21 (v0.16): bảng guide_documents - tài liệu hướng dẫn sử dụng do Admin tải lên.

Revision ID: 0118
Revises: 0117
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0118"
down_revision: str | None = "0117"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "guide_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(150), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_guide_documents_created_at", "guide_documents", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_guide_documents_created_at", table_name="guide_documents")
    op.drop_table("guide_documents")
