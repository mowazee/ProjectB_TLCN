"""API Hướng dẫn sử dụng (FR-21, v0.16):
GET    /api/guides?q=&page=        mọi người dùng đã đăng nhập; tìm theo tiêu đề/mô tả
POST   /api/guides                 Admin; multipart file + title + description -> 201
PATCH  /api/guides/{id}            Admin; sửa tiêu đề/mô tả
DELETE /api/guides/{id}            Admin
GET    /api/guides/{id}/file       mọi người dùng đã đăng nhập; PDF/ảnh/video xem trực tiếp, Office tải về
"""

import uuid
from datetime import datetime
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession
from app.modules.guides.application import manage
from app.shared.http import page_params
from app.shared.pagination import Page, PageParams

router = APIRouter(prefix="/api/guides", tags=["guides"])


class GuideOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    file_name: str
    mime_type: str
    bytes: int
    inline: bool = Field(description="Mở trực tiếp trên trình duyệt (PDF, ảnh, video) hay tải về")
    uploaded_by: str | None
    created_at: datetime
    updated_at: datetime


class GuidePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)


@router.get("", response_model=Page[GuideOut])
def list_guides(
    db: DbSession,
    principal: CurrentPrincipal,
    params: Annotated[PageParams, Depends(page_params)],
    q: Annotated[str | None, Query(max_length=200)] = None,
) -> Page[GuideOut]:
    items, total = manage.list_guides(db, params, q)
    return Page(
        items=[GuideOut(**v.__dict__) for v in items], total=total, page=params.page, page_size=params.page_size
    )


@router.post("", response_model=GuideOut, status_code=status.HTTP_201_CREATED)
def upload_guide(
    db: DbSession,
    principal: CurrentPrincipal,
    ctx: Ctx,
    file: Annotated[UploadFile, File(description="PDF, Word, Excel, PowerPoint, PNG/JPG, MP4")],
    title: Annotated[str | None, Form(max_length=255, description="Trống = tên file")] = None,
    description: Annotated[str | None, Form(max_length=2000)] = None,
) -> GuideOut:
    view = manage.create_guide(
        db, principal, file_name=file.filename or "", stream=file.file, title=title, description=description, ctx=ctx
    )
    return GuideOut(**view.__dict__)


@router.patch("/{guide_id}", response_model=GuideOut)
def update_guide(
    guide_id: uuid.UUID, data: GuidePatch, db: DbSession, principal: CurrentPrincipal, ctx: Ctx
) -> GuideOut:
    view = manage.update_guide(db, principal, guide_id, data.model_dump(exclude_unset=True), ctx)
    return GuideOut(**view.__dict__)


@router.delete("/{guide_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_guide(guide_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> Response:
    manage.delete_guide(db, principal, guide_id, ctx)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{guide_id}/file", response_class=FileResponse)
def guide_file(guide_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> FileResponse:
    path, name, mime, inline = manage.open_file(db, guide_id)
    kind = "inline" if inline else "attachment"
    return FileResponse(
        path,
        media_type=mime,
        headers={
            "Content-Disposition": f"{kind}; filename*=UTF-8''{quote(name)}",
            "X-Content-Type-Options": "nosniff",
        },
    )
