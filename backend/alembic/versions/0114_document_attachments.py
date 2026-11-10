"""FR-15 (SDD v0.13): bảng document_attachments - tài liệu đi kèm (không OCR) của một tài liệu chính.

Revision ID: 0114
Revises: 0113
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0114"
down_revision: str | None = "0113"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_attachments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_document_attachments_document_id", "document_attachments", ["document_id"])


def downgrade() -> None:
    op.drop_index("ix_document_attachments_document_id", table_name="document_attachments")
    op.drop_table("document_attachments")
