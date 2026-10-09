"""P2-04 extraction: document_extracted_fields + UNIQUE(document_id, field_name) (SDD mục 5, P2-04).

Revision ID: 0103
Revises: 0102
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0103"
down_revision: str | None = "0102"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "document_extracted_fields",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("field_name", sa.String(100), nullable=False),
        sa.Column("field_value", sa.Text()),
        sa.Column("extracted_method", sa.String(30), nullable=False),
        sa.Column("is_verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.UniqueConstraint("document_id", "field_name", name="uq_extracted_fields_document_field"),
    )


def downgrade() -> None:
    op.drop_table("document_extracted_fields")
