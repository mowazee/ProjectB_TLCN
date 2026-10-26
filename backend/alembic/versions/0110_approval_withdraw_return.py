"""D-11 (SDD v0.12): document_approvals.action thêm 'withdraw' (chủ sở hữu rút lại) và 'return' (trả lại chủ sở hữu).

Chỉ đổi ràng buộc CHECK, không đổi cột. Hạ cấp: bỏ các dòng lịch sử withdraw/return (không biểu diễn được ở bản cũ).

Revision ID: 0110
Revises: 0109
Create Date: 2026-10-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0110"
down_revision: str | None = "0109"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NAME = "ck_document_approvals_action"
OLD = "action IN ('submit', 'approve', 'reject', 'publish', 'unpublish')"
NEW = "action IN ('submit', 'approve', 'reject', 'publish', 'unpublish', 'withdraw', 'return')"


def upgrade() -> None:
    with op.batch_alter_table("document_approvals") as batch:
        batch.drop_constraint(NAME, type_="check")
        batch.create_check_constraint(NAME, NEW)


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM document_approvals WHERE action IN ('withdraw', 'return')"))
    with op.batch_alter_table("document_approvals") as batch:
        batch.drop_constraint(NAME, type_="check")
        batch.create_check_constraint(NAME, OLD)
