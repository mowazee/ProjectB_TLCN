"""P2-07 (v0.16): gỡ yêu cầu mượn đang treo của tài liệu đã xóa mềm - chuyển 'pending' sang 'rejected'.

Trước v0.16 xóa tài liệu không xử lý yêu cầu mượn chờ duyệt nên chúng treo mãi (Kiểm duyệt viên không thấy, không thao
tác được). Từ v0.16 module borrowing tự từ chối khi nhận event DocumentDeleted; migration này dọn dữ liệu cũ. Chỉ đổi
dữ liệu, không đổi cấu trúc; downgrade không khôi phục (không phân biệt được với yêu cầu bị từ chối thật).

Revision ID: 0117
Revises: 0116
Create Date: 2026-11-28
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0117"
down_revision: str | None = "0116"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE borrow_requests SET status = 'rejected' WHERE status = 'pending' AND document_id IN "
            "(SELECT id FROM documents WHERE lifecycle_status = 'deleted')"
        )
    )


def downgrade() -> None:
    pass
