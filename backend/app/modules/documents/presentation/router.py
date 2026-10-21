"""API documents (SDD mục 7.1).

POST   /api/documents                       multipart -> 201 {document_id, job_id}; 400/413/415/422
GET    /api/documents                       phân trang; lọc danh mục/trạng thái; lifecycle_status=deleted = thùng rác
GET    /api/documents/{id}                  chi tiết (kiểm quyền)
PATCH  /api/documents/{id}                  sửa metadata; DELETE xóa mềm
POST   /api/documents/{id}/restore          khôi phục trong hạn; quá hạn 410; đã purge 404
GET    /api/documents/{id}/pages            danh sách trang
GET    /api/documents/{id}/file             file gốc (người quản lý được tài liệu)
GET    /api/documents/{id}/pages/{p}/image  ảnh trang (người xem được tài liệu)
"""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Form, Path, Query, Response, UploadFile, status
from fastapi.responses import FileResponse

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession
from app.modules.documents.application import files, manage, sharing, upload
from app.modules.documents.application.queries import ensure_can_view, list_pages
from app.modules.documents.domain.lifecycle import ApprovalStatus, LifecycleStatus
from app.modules.documents.presentation.schemas import (
    DocumentOut,
    DocumentPatch,
    PageSummary,
    SharingIn,
    SharingOut,
    UploadOut,
    document_out,
    sharing_out,
)
from app.shared.http import page_params
from app.shared.pagination import Page, PageParams

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("", response_model=UploadOut, status_code=status.HTTP_201_CREATED)
def upload_document(
    db: DbSession,
    principal: CurrentPrincipal,
    ctx: Ctx,
    file: Annotated[UploadFile, File(description="PDF, PNG hoặc JPG")],
    category_id: Annotated[int | None, Form(description="Bắt buộc khi category_mode = user")] = None,
    category_mode: Annotated[
        Literal["user", "auto"],
        Form(
            description="D-10 (v0.9): user = người dùng chọn; auto = Danh mục gợi ý (tự phân loại sau OCR, cần P2-05)"
        ),
    ] = "user",
    title: Annotated[str | None, Form(max_length=255)] = None,
    is_handwritten: Annotated[bool, Form(description="P2-03 (khi cờ handwriting bật)")] = False,
) -> UploadOut:
    doc, job = upload.upload_document(
        db,
        principal,
        stream=file.file,
        filename=file.filename,
        title=title,
        category_id=category_id,
        is_handwritten=is_handwritten,
        ctx=ctx,
        category_mode=category_mode,
    )
    return UploadOut(
        document_id=doc.id, job_id=job.id, lifecycle_status=str(doc.lifecycle_status), job_status=str(job.status)
    )


@router.get("", response_model=Page[DocumentOut])
def list_documents(
    db: DbSession,
    principal: CurrentPrincipal,
    params: Annotated[PageParams, Depends(page_params)],
    q: Annotated[str | None, Query(max_length=200)] = None,
    category_id: int | None = None,
    status: Annotated[str | None, Query(pattern="^(queued|processing|completed|failed|needs_review)$")] = None,
    lifecycle_status: LifecycleStatus = LifecycleStatus.ACTIVE,
    approval_status: ApprovalStatus | None = None,
    shared: Annotated[str | None, Query(pattern="^with_me$")] = None,
) -> Page[DocumentOut]:
    views, total = manage.list_documents(
        db,
        principal,
        params,
        q=q,
        category_id=category_id,
        status=status,
        lifecycle_status=lifecycle_status,
        approval_status=approval_status,
        shared_with_me=shared == "with_me",
    )
    return Page(items=[document_out(v) for v in views], total=total, page=params.page, page_size=params.page_size)


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> DocumentOut:
    return document_out(manage.get_document_view(db, principal, document_id))


@router.patch("/{document_id}", response_model=DocumentOut)
def update_document(
    document_id: uuid.UUID, data: DocumentPatch, db: DbSession, principal: CurrentPrincipal, ctx: Ctx
) -> DocumentOut:
    manage.update_document(db, principal, document_id, data.model_dump(exclude_unset=True), ctx)
    return document_out(manage.get_document_view(db, principal, document_id))


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> Response:
    manage.soft_delete(db, principal, document_id, ctx)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{document_id}/restore", response_model=DocumentOut)
def restore_document(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> DocumentOut:
    doc = manage.restore(db, principal, document_id, ctx)
    return document_out(manage.build_views(db, principal, [doc])[0])


@router.get("/{document_id}/sharing", response_model=SharingOut)
def get_sharing(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> SharingOut:
    """FR-13: cấu hình chia sẻ - chủ sở hữu, Admin."""
    return sharing_out(sharing.get_sharing(db, principal, document_id))


@router.put("/{document_id}/sharing", response_model=SharingOut)
def update_sharing(
    document_id: uuid.UUID, data: SharingIn, db: DbSession, principal: CurrentPrincipal, ctx: Ctx
) -> SharingOut:
    """FR-13: thay toàn bộ cấu hình chia sẻ; 409 DOCUMENT_NOT_PUBLISHED khi chưa xuất bản."""
    view = sharing.update_sharing(
        db,
        principal,
        document_id,
        share_mode=data.share_mode,
        department_ids=data.department_ids,
        user_ids=data.user_ids,
        ctx=ctx,
    )
    return sharing_out(view)


@router.get("/{document_id}/pages", response_model=list[PageSummary])
def get_pages(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> list[PageSummary]:
    ensure_can_view(db, principal, document_id)
    return [
        PageSummary(page_number=p.page_number, width=p.width, height=p.height, ocr_status=str(p.ocr_status))
        for p in list_pages(db, document_id)
    ]


@router.get("/{document_id}/file", response_class=FileResponse)
def download_original(document_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> FileResponse:
    path, name, mime = files.open_original(db, principal, document_id, ctx)
    return FileResponse(path, media_type=mime, filename=name)


@router.get("/{document_id}/pages/{page_number}/image", response_class=FileResponse)
def page_image(
    document_id: uuid.UUID,
    page_number: Annotated[int, Path(ge=1)],
    db: DbSession,
    principal: CurrentPrincipal,
) -> FileResponse:
    path = files.page_image_path(db, principal, document_id, page_number)
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})
