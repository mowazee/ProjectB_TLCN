"""P2: thêm giá trị processing_jobs.kind (SDD mục 6): EXTRACT (P2-04), CLASSIFY (P2-05), BULK_IMPORT (P2-08).

Revision ID: 0105
Revises: 0104
Create Date: 2026-10-04
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0105"
down_revision: str | None = "0104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

P2_KINDS = "kind IN ('OCR', 'EXTRACT', 'CLASSIFY', 'BULK_IMPORT')"
MVP_KINDS = "kind IN ('OCR')"


def _replace(condition: str) -> None:
    with op.batch_alter_table("processing_jobs") as batch:
        batch.drop_constraint("ck_jobs_kind", type_="check")
        batch.create_check_constraint("ck_jobs_kind", condition)


def upgrade() -> None:
    _replace(P2_KINDS)


def downgrade() -> None:
    op.execute("DELETE FROM processing_jobs WHERE kind <> 'OCR'")
    _replace(MVP_KINDS)
