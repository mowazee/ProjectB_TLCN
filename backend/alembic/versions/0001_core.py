"""Lõi MVP (SDD v0.5 mục 6, ERD file 3 v0.5 - 11 bảng MVP).

departments, roles, users, user_roles, categories, documents, document_pages, processing_jobs,
ocr_results, ocr_corrections, audit_logs. Bảng P2 nằm ở revision 01xx của từng module.

- processing_jobs.kind: CHECK chỉ 'OCR'; P2 mở rộng ở revision 0105 (EXTRACT, CLASSIFY, BULK_IMPORT).
- processing_jobs.document_id cho phép NULL (job cấp lô BULK_IMPORT chưa gắn tài liệu).
- audit_logs.document_id/user_id ON DELETE SET NULL (FR-07: purge giữ audit).
- PostgreSQL: trigger append-only cho audit_logs; chỉ cho phép UPDATE do ON DELETE SET NULL.

Revision ID: 0001
Revises:
Create Date: 2026-10-04
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")
NOW = sa.text("CURRENT_TIMESTAMP")

AUDIT_APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION fn_audit_logs_append_only() RETURNS trigger AS $$
BEGIN
    -- Cho phép duy nhất UPDATE do khóa ngoại ON DELETE SET NULL (purge tài liệu, FR-07):
    -- chỉ user_id/document_id đổi sang NULL, mọi cột khác giữ nguyên.
    IF TG_OP = 'UPDATE'
       AND (NEW.user_id IS NULL OR NEW.user_id IS NOT DISTINCT FROM OLD.user_id)
       AND (NEW.document_id IS NULL OR NEW.document_id IS NOT DISTINCT FROM OLD.document_id)
       AND (to_jsonb(NEW) - 'user_id' - 'document_id') = (to_jsonb(OLD) - 'user_id' - 'document_id')
    THEN
        RETURN NEW;
    END IF;
    RAISE EXCEPTION 'audit_logs chỉ cho phép thêm mới (append-only)';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_audit_logs_append_only
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION fn_audit_logs_append_only();
"""

ROLES = [
    {"name": "ADMIN", "description": "Quản trị viên hệ thống"},
    {"name": "OFFICER", "description": "Nhân viên nghiệp vụ"},
    {"name": "APPROVER", "description": "Kiểm duyệt viên"},
]
DEFAULT_DEPARTMENT = {"name": "Phòng Hành chính - Tổng hợp", "code": "HC-TH", "description": "Đơn vị mặc định"}


def _enum(name: str, *values: str) -> sa.Enum:
    return sa.Enum(*values, name=name, native_enum=False, create_constraint=True, length=30)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), server_default=None if nullable else NOW, nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.Text()),
        _ts("created_at"),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(50), nullable=False, unique=True),
        sa.Column("description", sa.String(255)),
        _ts("created_at"),
    )
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("parent_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="CASCADE")),
        sa.Column("retention_period_years", sa.Integer()),
        sa.Column("description", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        _ts("created_at"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL"), index=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(100), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(20)),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        _ts("last_login_at", nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Integer(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
        _ts("assigned_at"),
    )
    op.create_table(
        "documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "category_id", sa.Integer(), sa.ForeignKey("categories.id", ondelete="RESTRICT"), nullable=False, index=True
        ),
        sa.Column("owner_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), index=True),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL"), index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("document_code", sa.String(100)),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("storage_key", sa.String(500), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("bytes", sa.BigInteger(), nullable=False),
        sa.Column(
            "lifecycle_status",
            _enum("ck_documents_lifecycle_status", "active", "deleted"),
            server_default="active",
            nullable=False,
            index=True,
        ),
        sa.Column(
            "approval_status",
            _enum(
                "ck_documents_approval_status",
                "draft",
                "pending_review",
                "approved",
                "rejected",
                "published",
                "unpublished",
            ),
            server_default="draft",
            nullable=False,
        ),
        sa.Column("is_handwritten", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=NOW, nullable=False, index=True),
        _ts("updated_at"),
        _ts("deleted_at", nullable=True),
    )
    op.create_table(
        "document_pages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("image_key", sa.String(500), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column(
            "ocr_status",
            _enum("ck_document_pages_ocr_status", "pending", "completed", "failed", "needs_review"),
            server_default="pending",
            nullable=False,
        ),
        sa.UniqueConstraint("document_id", "page_number", name="uq_document_page"),
    )
    op.create_table(
        "processing_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="CASCADE"), index=True),
        sa.Column("page_id", sa.Uuid(), sa.ForeignKey("document_pages.id", ondelete="CASCADE")),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("queue_name", sa.String(50), server_default="default", nullable=False),
        sa.Column(
            "status",
            _enum("ck_jobs_status", "queued", "processing", "completed", "failed"),
            server_default="queued",
            nullable=False,
        ),
        sa.Column("schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("progress", sa.Integer(), server_default="0", nullable=False),
        sa.Column("priority", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attempt", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("worker_id", sa.String(100)),
        sa.Column("payload", JSON),
        sa.Column("result", JSON),
        sa.Column("error_code", sa.String(50)),
        sa.Column("error_detail", sa.Text()),
        _ts("queued_at"),
        _ts("started_at", nullable=True),
        _ts("finished_at", nullable=True),
        sa.CheckConstraint("attempt <= max_attempts", name="chk_job_attempt"),
        sa.CheckConstraint("progress BETWEEN 0 AND 100", name="chk_job_progress"),
        sa.CheckConstraint("kind IN ('OCR')", name="ck_jobs_kind"),
    )
    op.create_index("idx_jobs_kind_status", "processing_jobs", ["kind", "status"])
    op.create_table(
        "ocr_results",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "page_id", sa.Uuid(), sa.ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("job_id", sa.Uuid(), sa.ForeignKey("processing_jobs.id", ondelete="SET NULL")),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("boxes", JSON),
        sa.Column("confidence", sa.Numeric(5, 2)),
        sa.Column("engine_version", sa.String(50), nullable=False),
        sa.Column("search_vector", postgresql.TSVECTOR().with_variant(sa.Text(), "sqlite")),
        _ts("created_at"),
        sa.UniqueConstraint("page_id", "job_id", name="uq_ocr_results_page_job"),
    )
    op.create_index("idx_ocr_results_search_vector", "ocr_results", ["search_vector"], postgresql_using="gin")
    op.create_table(
        "ocr_corrections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "page_id", sa.Uuid(), sa.ForeignKey("document_pages.id", ondelete="CASCADE"), nullable=False, index=True
        ),
        sa.Column("edited_by", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("corrected_text", sa.Text(), nullable=False),
        sa.Column("base_version", sa.Integer(), nullable=False),
        _ts("edited_at"),
        sa.UniqueConstraint("page_id", "version", name="uq_ocr_corrections_page_version"),
    )
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), index=True),
        sa.Column("document_id", sa.Uuid(), sa.ForeignKey("documents.id", ondelete="SET NULL"), index=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("module", sa.String(50), nullable=False),
        sa.Column("entity_type", sa.String(50)),
        sa.Column("entity_id", sa.String(100)),
        sa.Column("result", _enum("ck_audit_logs_result", "success", "failure"), nullable=False),
        sa.Column("ip_address", sa.String(45)),
        sa.Column("user_agent", sa.Text()),
        sa.Column("request_id", sa.String(64)),
        sa.Column("state_before", JSON),
        sa.Column("state_after", JSON),
        _ts("created_at"),
    )
    op.create_index("idx_audit_logs_created_at", "audit_logs", ["created_at"])

    if op.get_bind().dialect.name == "postgresql":
        op.execute(AUDIT_APPEND_ONLY_SQL)

    roles = sa.table("roles", sa.column("name", sa.String), sa.column("description", sa.String))
    departments = sa.table(
        "departments", sa.column("name", sa.String), sa.column("code", sa.String), sa.column("description", sa.Text)
    )
    op.bulk_insert(roles, ROLES)
    op.bulk_insert(departments, [DEFAULT_DEPARTMENT])


def downgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_append_only ON audit_logs")
        op.execute("DROP FUNCTION IF EXISTS fn_audit_logs_append_only()")
    for table in (
        "audit_logs",
        "ocr_corrections",
        "ocr_results",
        "processing_jobs",
        "document_pages",
        "documents",
        "user_roles",
        "users",
        "categories",
        "roles",
        "departments",
    ):
        op.drop_table(table)
