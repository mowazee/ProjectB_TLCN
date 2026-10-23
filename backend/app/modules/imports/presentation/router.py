"""API imports (SDD 7.2, P2-08):
POST /api/imports            multipart nhiều file/ZIP + category_mode/category_id (+ metadata.csv) -> 202 job_id
GET  /api/imports/{job_id}   tiến độ + báo cáo từng file
"""

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from pydantic import BaseModel

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession, require_feature
from app.modules.imports.application import batch

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
    files: Annotated[list[UploadFile], File(description="PDF/PNG/JPG hoặc ZIP")],
    category_id: Annotated[int | None, Form(description="Bắt buộc khi category_mode = user")] = None,
    category_mode: Annotated[
        Literal["user", "auto"], Form(description="D-10: auto = Danh mục gợi ý cho cả lô (cần P2-05)")
    ] = "user",
    metadata: Annotated[
        UploadFile | None, File(description="metadata.csv: file_name, title, category (mã), document_code")
    ] = None,
    is_handwritten: Annotated[bool, Form()] = False,
) -> ImportAccepted:
    job = batch.start_import(
        db,
        principal,
        files=[batch.StagedFile(f.filename or "", f.file) for f in files],
        metadata=batch.StagedFile(metadata.filename or "metadata.csv", metadata.file) if metadata else None,
        category_id=category_id,
        category_mode=category_mode,
        is_handwritten=is_handwritten,
        ctx=ctx,
    )
    return ImportAccepted(job_id=job.id, status=str(job.status), files=len(files))


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
