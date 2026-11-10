"""FR-19 (SDD v0.14, D-14): hiệu lực tài liệu - 5 cột ở documents; tài liệu cũ là Không quy định.

Revision ID: 0116
Revises: 0115
Create Date: 2026-11-11
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0116"
down_revision: str | None = "0115"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.add_column(
            sa.Column(
                "validity_status",
                sa.Enum(
                    "unspecified",
                    "effective",
                    "effective_until",
                    "expired",
                    name="ck_documents_validity_status",
                    native_enum=False,
                    create_constraint=True,
                    length=30,
                ),
                server_default="unspecified",
                nullable=False,
            )
        )
        batch.add_column(sa.Column("valid_until", sa.Date(), nullable=True))
        batch.add_column(sa.Column("validity_updated_by", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("validity_updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("validity_reminded_on", sa.Date(), nullable=True))
        batch.create_foreign_key(
            "fk_documents_validity_updated_by", "users", ["validity_updated_by"], ["id"], ondelete="SET NULL"
        )
        batch.create_index("ix_documents_validity", ["validity_status", "valid_until"])


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch:
        batch.drop_index("ix_documents_validity")
        batch.drop_constraint("fk_documents_validity_updated_by", type_="foreignkey")
        batch.drop_constraint("ck_documents_validity_status", type_="check")
        for col in ("validity_reminded_on", "validity_updated_at", "validity_updated_by", "valid_until", "validity_status"):
            batch.drop_column(col)
