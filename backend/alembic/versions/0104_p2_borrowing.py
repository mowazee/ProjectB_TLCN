"""P2-07 borrowing: storage_locations, borrow_requests, documents.storage_location_id
("chỉ thêm khi P2-07 triển khai", SDD mục 6).

Revision ID: 0104
Revises: 0103
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0104"
down_revision: str | None = "0103"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "storage_locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
    )
    op.create_table(
        "borrow_requests",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("requester_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), index=True),
        sa.Column("approver_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("status", sa.String(20), server_default="pending", nullable=False),
        sa.Column("from_date", sa.Date(), nullable=False),
        sa.Column("to_date", sa.Date(), nullable=False),
        sa.Column("purpose", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("status IN ('pending', 'approved', 'rejected', 'returned')", name="ck_borrow_requests_status"),
        sa.CheckConstraint("from_date <= to_date", name="ck_borrow_requests_dates"),
    )
    op.create_index("ix_borrow_requests_document_status", "borrow_requests", ["document_id", "status"])
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("storage_location_id", sa.Integer(), nullable=True))
        batch.create_foreign_key(
            "fk_documents_storage_location_id", "storage_locations", ["storage_location_id"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_documents_storage_location_id", ["storage_location_id"])


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.drop_index("ix_documents_storage_location_id")
        batch.drop_constraint("fk_documents_storage_location_id", type_="foreignkey")
        batch.drop_column("storage_location_id")
    op.drop_table("borrow_requests")
    op.drop_table("storage_locations")
