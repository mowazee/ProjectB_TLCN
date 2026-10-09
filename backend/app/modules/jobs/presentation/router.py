"""API jobs (SDD mục 7.1): GET /api/jobs/{id}; POST /api/jobs/{id}/retry.

Quyền theo tài liệu của job (xem để đọc, quản lý để retry). Job cấp lô (BULK_IMPORT, chưa có
document_id) chỉ người tạo hoặc Admin được xem/retry.
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.modules.auth.presentation.deps import Ctx, CurrentPrincipal, DbSession
from app.modules.documents.application.queries import ensure_can_manage, ensure_can_view
from app.modules.jobs.application import queries as jobs
from app.modules.jobs.domain.model import public_error_message
from app.shared.context import Principal
from app.shared.errors import PermissionDeniedError

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID | None
    kind: str
    status: str
    progress: int = Field(ge=0, le=100)
    attempt: int
    max_attempts: int
    error_code: str | None
    error_message: str | None = Field(description="Thông điệp an toàn theo error_code")
    result: dict[str, Any] | None
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


def job_out(job: Any) -> JobOut:
    return JobOut(
        id=job.id,
        document_id=job.document_id,
        kind=job.kind,
        status=str(job.status),
        progress=job.progress,
        attempt=job.attempt,
        max_attempts=job.max_attempts,
        error_code=job.error_code,
        error_message=public_error_message(job.error_code),
        result=job.result,
        queued_at=job.queued_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def authorize(db: Session, principal: Principal, job: Any, *, manage: bool) -> None:
    if job.document_id is not None:
        (ensure_can_manage if manage else ensure_can_view)(db, principal, job.document_id)
        return
    owner = (job.payload or {}).get("user_id")
    if not principal.is_admin and owner != str(principal.id):
        raise PermissionDeniedError("Bạn không có quyền với job này")


@router.get("/{job_id}", response_model=JobOut)
def get_job(job_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal) -> JobOut:
    job = jobs.get_job(db, job_id)
    authorize(db, principal, job, manage=False)
    return job_out(job)


@router.post("/{job_id}/retry", response_model=JobOut)
def retry_job(job_id: uuid.UUID, db: DbSession, principal: CurrentPrincipal, ctx: Ctx) -> JobOut:
    job = jobs.get_job(db, job_id)
    authorize(db, principal, job, manage=True)
    return job_out(jobs.retry_job(db, principal, job_id, ctx))
