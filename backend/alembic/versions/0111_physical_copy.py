"""D-12 (SDD v0.13): bản cứng và Kho chung.

- storage_locations.is_virtual (mặc định false) + dòng hệ thống KHO-CHUNG "Kho chung (không có bản cứng)".
- documents.has_physical_copy: true/false/NULL = chưa khai báo. Tài liệu cũ có vị trí → true; còn lại NULL.

Revision ID: 0111
Revises: 0110
Create Date: 2026-11-10
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0111"
down_revision: str | None = "0110"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("storage_locations") as batch:
        batch.add_column(sa.Column("is_virtual", sa.Boolean(), nullable=False, server_default=sa.false()))
    with op.batch_alter_table("documents") as batch:
        batch.add_column(sa.Column("has_physical_copy", sa.Boolean(), nullable=True))
    op.execute(
        sa.text(
            "INSERT INTO storage_locations (name, code, is_virtual) "
            "VALUES ('Kho chung (không có bản cứng)', 'KHO-CHUNG', true)"
        )
    )
    op.execute(sa.text("UPDATE documents SET has_physical_copy = true WHERE storage_location_id IS NOT NULL"))


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE documents SET storage_location_id = NULL WHERE storage_location_id IN "
            "(SELECT id FROM storage_locations WHERE is_virtual = true)"
        )
    )
    op.execute(sa.text("DELETE FROM storage_locations WHERE is_virtual = true"))
    with op.batch_alter_table("documents") as batch:
        batch.drop_column("has_physical_copy")
    with op.batch_alter_table("storage_locations") as batch:
        batch.drop_column("is_virtual")
