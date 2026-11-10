"""API imports (SDD 7.2, P2-08):
POST /api/imports            multipart nhiều file/ZIP kèm manifest.csv (bắt buộc) + category_mode/category_id -> 202
GET  /api/imports/template.zip  file mẫu: manifest.csv + HUONG-DAN.txt (v0.15)
GET  /api/imports/{job_id}   tiến độ + báo cáo từng file
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from pydantic import BaseModel

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession, require_feature
from app.modules.imports.application import batch, template

router = APIRouter(prefix="/api/imports", tags=["imports"], dependencies=[Depends(require_feature("imports"))])


class ImportAccepted(BaseModel):
    job_id: uuid.UUID
    status: str
    files: int


class FileReport(BaseModel):
    name: str
    status: str | None
    document_id: uuid.UUID | None = None
    job_id: uuid.UUID | None = None
    code: str | None = None
    message: str | None = None
    category_name: str | None = None  # danh mục hiện tại của tài liệu đã nhập
    category_source: str | None = None  # D-10: user | auto | pending
    attachments: int | None = None  # FR-15 (v0.13): số tài liệu đi kèm của bộ


class ImportReport(BaseModel):
    job_id: uuid.UUID
    status: str
    progress: int
    error_code: str | None
    queued_at: datetime
    finished_at: datetime | None
    total: int
    imported: int
    errors: int
    files: list[FileReport]


@router.post("", response_model=ImportAccepted, status_code=status.HTTP_202_ACCEPTED)
def start_import(
    db: DbSession,
    principal: CurrentPrincipal,
    ctx: Ctx,
    files: Annotated[
        list[UploadFile],
        File(description="manifest.csv (bắt buộc, hoặc ở gốc ZIP) + file chính/đi kèm, hoặc ZIP chứa tất cả"),
    ],
    category_id: Annotated[int | None, Form(description="Bắt buộc khi category_mode = user")] = None,
    category_mode: Annotated[
        Literal["user", "auto"], Form(description="D-10: auto = Danh mục gợi ý cho cả lô (cần P2-05)")
    ] = "user",
    is_handwritten: Annotated[bool, Form()] = False,
) -> ImportAccepted:
    job = batch.start_import(
        db,
        principal,
        files=[batch.StagedFile(f.filename or "", f.file) for f in files],
        category_id=category_id,
        category_mode=category_mode,
        is_handwritten=is_handwritten,
        ctx=ctx,
    )
    return ImportAccepted(job_id=job.id, status=str(job.status), files=len(files))


@router.get("/template.zip", response_class=Response)
def download_template(db: DbSession, principal: CurrentPrincipal) -> Response:
    """File mẫu: ZIP gồm manifest.csv mẫu và HUONG-DAN.txt (v0.15)."""
    return Response(
        content=template.build_template(db),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="mau-nhap-hang-loat.zip"'},
    )


@router.get("/{job_id}", response_model=ImportReport)
def get_report(job_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> ImportReport:
    r: dict[str, Any] = batch.get_report(db, principal, job_id)
    job = r["job"]
    return ImportReport(
        job_id=job.id,
        status=str(job.status),
        progress=job.progress,
        error_code=job.error_code,
        queued_at=job.queued_at,
        finished_at=job.finished_at,
        total=r["total"],
        imported=r["imported"],
        errors=r["errors"],
        files=[FileReport(**f) for f in r["files"]],
    )
