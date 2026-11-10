"""FR-17 (SDD v0.13): bảng daily_activity_stats - thống kê hoạt động theo ngày, người dùng, chỉ số.

Bảng tổng hợp do Celery beat tính từ audit_logs, processing_jobs, documents; không bị xóa khi dọn audit (FR-14).
Thêm index audit_logs(action, created_at) cho truy vấn tổng hợp.

Revision ID: 0113
Revises: 0112
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0113"
down_revision: str | None = "0112"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "daily_activity_stats",
        sa.Column("day", sa.Date(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("metric", sa.String(50), primary_key=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("value", sa.Float(), nullable=False),
    )
    op.create_index("ix_daily_activity_stats_department_id", "daily_activity_stats", ["department_id"])
    op.create_index("idx_audit_logs_action_created_at", "audit_logs", ["action", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_audit_logs_action_created_at", table_name="audit_logs")
    op.drop_index("ix_daily_activity_stats_department_id", table_name="daily_activity_stats")
    op.drop_table("daily_activity_stats")
