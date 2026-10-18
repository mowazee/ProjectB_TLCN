"""FR-13 (SDD v0.8, D-09): chia sẻ tài liệu đã xuất bản - documents.share_mode và bảng document_shares.

Module lõi documents (không phải P2). Mặc định 'internal' = phòng ban của tài liệu, đúng hành vi trước v0.8,
nên dữ liệu cũ không cần chuyển đổi.

Revision ID: 0108
Revises: 0107
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0108"
down_revision: str | None = "0107"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.add_column(
            sa.Column(
                "share_mode",
                sa.Enum(
                    "private",
                    "internal",
                    "public",
                    name="ck_documents_share_mode",
                    native_enum=False,
                    create_constraint=True,
                    length=30,
                ),
                server_default="internal",
                nullable=False,
            )
        )
    op.create_table(
        "document_shares",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=True),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("(department_id IS NULL) <> (user_id IS NULL)", name="ck_document_shares_target"),
        sa.UniqueConstraint("document_id", "department_id", name="uq_document_shares_department"),
        sa.UniqueConstraint("document_id", "user_id", name="uq_document_shares_user"),
    )
    op.create_index("ix_document_shares_document_id", "document_shares", ["document_id"])
    op.create_index("ix_document_shares_department_id", "document_shares", ["department_id"])
    op.create_index("ix_document_shares_user_id", "document_shares", ["user_id"])


def downgrade() -> None:
    op.drop_table("document_shares")
    with op.batch_alter_table("documents") as batch:
        # SQLite dựng lại bảng: phải bỏ CHECK của cột trước, nếu không CHECK còn trỏ tới cột đã xóa
        batch.drop_constraint("ck_documents_share_mode", type_="check")
        batch.drop_column("share_mode")
