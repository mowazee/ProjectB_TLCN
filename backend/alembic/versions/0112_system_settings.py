"""FR-14 (SDD v0.13): bảng system_settings - cấu hình hệ thống dạng key-value (thời gian lưu thùng rác, audit log).

Chưa có dòng thì ứng dụng dùng mặc định từ môi trường (SOFT_DELETE_RETENTION_DAYS, AUDIT_RETENTION_DAYS).

Revision ID: 0112
Revises: 0111
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0112"
down_revision: str | None = "0111"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(100), primary_key=True),
        sa.Column("value", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=True),
        sa.Column("updated_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
