"""P2-07/P2-01 notifications: thêm message, link_url (SDD v0.6 mục 6, ERD file 3 v0.6).

Trước v0.6 nội dung bị gộp vào title và React tự suy link từ type; hai cột nullable,
chỉ thêm (NFR-09, R10).

Revision ID: 0106
Revises: 0105
Create Date: 2026-10-16
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0106"
down_revision: str | None = "0105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.add_column(sa.Column("message", sa.Text(), nullable=True))
        batch.add_column(sa.Column("link_url", sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch:
        batch.drop_column("link_url")
        batch.drop_column("message")
