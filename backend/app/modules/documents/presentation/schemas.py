"""DTO API của documents. JSON snake_case theo tên cột SDD mục 6; không có storage_key."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.documents.application.manage import DocumentView


class CategoryRef(BaseModel):
    id: int
    name: str | None


class OwnerRef(BaseModel):
    id: uuid.UUID
    full_name: str | None


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    document_code: str | None
    file_name: str
    file_type: str
    mime_type: str
    bytes: int
    lifecycle_status: str
    approval_status: str
    is_handwritten: bool
    category: CategoryRef
    owner: OwnerRef | None
    department_id: int | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    restore_deadline: datetime | None = Field(description="Hạn khôi phục khi đang trong thùng rác (D-05)")
    total_pages: int
    needs_review_pages: int
    job_status: str | None = Field(description="Trạng thái job OCR mới nhất")
    job_id: uuid.UUID | None = Field(default=None, description="Job OCR mới nhất (poll tiến độ / retry)")
    can_edit: bool


class DocumentPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    category_id: int | None = None
    document_code: str | None = Field(default=None, max_length=100)
    is_handwritten: bool | None = None


class UploadOut(BaseModel):
    document_id: uuid.UUID
    job_id: uuid.UUID
    lifecycle_status: str
    job_status: str


class PageSummary(BaseModel):
    page_number: int
    width: int
    height: int
    ocr_status: str


def document_out(v: DocumentView) -> DocumentOut:
    d = v.doc
    return DocumentOut(
        id=d.id,
        title=d.title,
        document_code=d.document_code,
        file_name=d.file_name,
        file_type=d.file_type,
        mime_type=d.mime_type,
        bytes=d.bytes,
        lifecycle_status=str(d.lifecycle_status),
        approval_status=str(d.approval_status),
        is_handwritten=d.is_handwritten,
        category=CategoryRef(id=d.category_id, name=v.category_name),
        owner=OwnerRef(id=d.owner_id, full_name=v.owner_name) if d.owner_id else None,
        department_id=d.department_id,
        created_at=d.created_at,
        updated_at=d.updated_at,
        deleted_at=d.deleted_at,
        restore_deadline=v.restore_deadline,
        total_pages=v.total_pages,
        needs_review_pages=v.needs_review_pages,
        job_status=v.job_status,
        job_id=v.job_id,
        can_edit=v.can_edit,
    )
