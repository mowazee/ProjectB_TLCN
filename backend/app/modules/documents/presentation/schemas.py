"""DTO API của documents. JSON snake_case theo tên cột SDD mục 6; không có storage_key."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.modules.documents.application.manage import DocumentView
from app.modules.documents.application.sharing import SharingView
from app.modules.documents.domain.lifecycle import ShareMode


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
    category_source: str = Field(description="D-10: user | auto | pending (nguồn danh mục)")
    share_mode: str = Field(description="FR-13: private | internal | public; chỉ có hiệu lực khi đã xuất bản")
    can_share: bool = Field(description="FR-13: người dùng hiện tại đổi được cấu hình chia sẻ")
    permissions: list[str] = Field(
        default_factory=list,
        description="D-11 (v0.12): edit, reprocess, delete, restore, cancel_job, submit, withdraw, share",
    )
    edit_lock_reason: str | None = Field(default=None, description="D-11: vì sao người dùng không sửa được")


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
        category_source=v.category_source,
        share_mode=v.share_mode,
        can_share=v.can_share,
        can_edit=v.can_edit,
        permissions=v.permissions,
        edit_lock_reason=v.edit_lock_reason,
    )


# ---------------------------------------------------------------- FR-13 chia sẻ (v0.8)
class DepartmentRefOut(BaseModel):
    id: int
    name: str


class ShareUserOut(BaseModel):
    id: uuid.UUID
    username: str
    full_name: str
    department_name: str | None


class SharingOut(BaseModel):
    document_id: uuid.UUID
    share_mode: str
    is_published: bool = Field(description="False: cấu hình tạm ngưng, phạm vi xem theo D-02")
    owner_department: DepartmentRefOut | None = Field(
        description="Phòng ban của tài liệu - luôn có quyền ở chế độ Nội bộ"
    )
    departments: list[DepartmentRefOut]
    users: list[ShareUserOut]


class SharingIn(BaseModel):
    share_mode: ShareMode
    department_ids: list[int] = Field(default_factory=list, max_length=100)
    user_ids: list[uuid.UUID] = Field(default_factory=list, max_length=200)


def sharing_out(v: SharingView) -> SharingOut:
    return SharingOut(
        document_id=v.document_id,
        share_mode=v.share_mode,
        is_published=v.is_published,
        owner_department=DepartmentRefOut(id=v.owner_department.id, name=v.owner_department.name)
        if v.owner_department
        else None,
        departments=[DepartmentRefOut(id=d.id, name=d.name) for d in v.departments],
        users=[
            ShareUserOut(id=u.id, username=u.username, full_name=u.full_name, department_name=u.department_name)
            for u in v.users
        ],
    )
