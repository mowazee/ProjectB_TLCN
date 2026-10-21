"""D-10 (SDD v0.9): documents.category_source và danh mục hệ thống "Chưa phân loại" (CHUA-PHAN-LOAI).

Dữ liệu cũ có category_source = 'user' (người dùng đã chọn danh mục khi tải lên).

Revision ID: 0109
Revises: 0108
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0109"
down_revision: str | None = "0108"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.add_column(
            sa.Column(
                "category_source",
                sa.Enum(
                    "user",
                    "auto",
                    "pending",
                    name="ck_documents_category_source",
                    native_enum=False,
                    create_constraint=True,
                    length=30,
                ),
                server_default="user",
                nullable=False,
            )
        )
    op.execute(
        sa.text(
            "INSERT INTO categories (name, code, description, is_active) "
            "SELECT 'Chưa phân loại', 'CHUA-PHAN-LOAI', "
            "'Danh mục hệ thống: tài liệu chờ tự phân loại sau OCR (D-10)', true "
            "WHERE NOT EXISTS (SELECT 1 FROM categories WHERE code = 'CHUA-PHAN-LOAI')"
        )
    )


def downgrade() -> None:
    # Tài liệu còn ở "Chưa phân loại" giữ nguyên danh mục (không xóa được vì khóa ngoại RESTRICT)
    op.execute(
        sa.text(
            "DELETE FROM categories WHERE code = 'CHUA-PHAN-LOAI' "
            "AND NOT EXISTS (SELECT 1 FROM documents d WHERE d.category_id = categories.id)"
        )
    )
    with op.batch_alter_table("documents") as batch:
        batch.drop_constraint("ck_documents_category_source", type_="check")
        batch.drop_column("category_source")
