"""FR-18 (SDD v0.13, D-13): bảng share_links (chia sẻ ra ngoài bằng link + OTP) và job kind EMAIL.

Revision ID: 0115
Revises: 0114
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0115"
down_revision: str | None = "0114"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OLD_KINDS = "kind IN ('OCR', 'EXTRACT', 'CLASSIFY', 'BULK_IMPORT')"
NEW_KINDS = "kind IN ('OCR', 'EXTRACT', 'CLASSIFY', 'BULK_IMPORT', 'EMAIL')"


def _kinds(condition: str) -> None:
    with op.batch_alter_table("processing_jobs") as batch:
        batch.drop_constraint("ck_jobs_kind", type_="check")
        batch.create_check_constraint("ck_jobs_kind", condition)


def upgrade() -> None:
    op.create_table(
        "share_links",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("recipient_email", sa.String(255), nullable=False),
        sa.Column("allow_download", sa.Boolean(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("access_count", sa.Integer(), nullable=False),
    )
    op.create_index("ix_share_links_document_id", "share_links", ["document_id"])
    _kinds(NEW_KINDS)


def downgrade() -> None:
    op.execute("DELETE FROM processing_jobs WHERE kind = 'EMAIL'")
    _kinds(OLD_KINDS)
    op.drop_index("ix_share_links_document_id", table_name="share_links")
    op.drop_table("share_links")
