"""FR-12 (SDD v0.7): thêm vai trò hệ thống VIEWER - Người dùng thông thường (chỉ xem, tìm kiếm, tải).

Chỉ thêm dữ liệu (một dòng roles), không đổi cấu trúc bảng.

Revision ID: 0107
Revises: 0106
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0107"
down_revision: str | None = "0106"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "INSERT INTO roles (name, description) SELECT 'VIEWER', 'Người dùng thông thường' "
            "WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = 'VIEWER')"
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM user_roles WHERE role_id IN (SELECT id FROM roles WHERE name = 'VIEWER')"))
    op.execute(sa.text("DELETE FROM roles WHERE name = 'VIEWER'"))
