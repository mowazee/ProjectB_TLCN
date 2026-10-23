"""Tạo job và gửi sang hàng đợi SAU KHI COMMIT (NFR-03).

Idempotency: idempotency_key UNIQUE theo (document, kind, số thứ tự). Không tạo job mới khi
tài liệu còn job cùng kind đang queued/processing (FR-04, UC-02 1a) -> 409.
"""

import logging
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.jobs.application import registry
from app.modules.jobs.domain.model import ACTIVE_STATUSES, OCR, JobStatus
from app.modules.jobs.infrastructure import dispatcher
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.shared.config import settings
from app.shared.db import SessionLocal, utcnow
from app.shared.errors import ConflictError
from app.shared.events import after_commit

logger = logging.getLogger(__name__)


def has_active_job(db: Session, document_id: uuid.UUID, kind: str) -> bool:
    return (
        db.scalar(
            select(func.count()).where(
                ProcessingJob.document_id == document_id,
                ProcessingJob.kind == kind,
                ProcessingJob.status.in_(ACTIVE_STATUSES),
            )
        )
        or 0
    ) > 0


def create_job(
    db: Session,
    *,
    kind: str,
    document_id: uuid.UUID | None,
    queue: str = "default",
    payload: dict[str, Any] | None = None,
    idempotency_key: str | None = None,
    allow_parallel: bool = False,
) -> ProcessingJob:
    """Tạo job trong transaction hiện tại (chưa commit) và hẹn gửi sang hàng đợi sau commit."""
    if document_id is not None and not allow_parallel and has_active_job(db, document_id, kind):
        raise ConflictError("Tài liệu đang có job cùng loại đang chạy", code="JOB_ALREADY_ACTIVE")
    if idempotency_key is None:
        seq = (
            db.scalar(select(func.count()).where(ProcessingJob.document_id == document_id, ProcessingJob.kind == kind))
            or 0
        )
        idempotency_key = f"{kind}:{document_id or uuid.uuid4()}:{seq + 1}"
    job = ProcessingJob(
        document_id=document_id,
        kind=kind,
        queue_name=queue,
        idempotency_key=idempotency_key,
        status=JobStatus.QUEUED,
        max_attempts=settings.JOB_MAX_ATTEMPTS,
        payload=payload or {},
    )
    db.add(job)
    db.flush()
    enqueue_after_commit(db, job)
    return job


def create_ocr_job(
    db: Session,
    document_id: uuid.UUID,
    *,
    is_handwritten: bool = False,
    profile: str | None = None,
    origin: dict[str, str] | None = None,
) -> ProcessingJob:
    """Job OCR: profile 'print' (MVP) hoặc profile do module P2-03 đăng ký. origin: nguồn tạo tài liệu ghi vào
    payload (vd. {"import_job_id": ...} khi nhập hàng loạt) để module sau OCR biết ngữ cảnh."""
    profile = profile or registry.resolve_ocr_profile(is_handwritten)
    queue = registry.ocr_profiles().get(profile, "ocr")
    return create_job(
        db, kind=OCR, document_id=document_id, queue=queue, payload={"profile": profile, **(origin or {})}
    )


def enqueue_after_commit(db: Session, job: ProcessingJob) -> None:
    job_id, queue = job.id, job.queue_name
    after_commit(db, lambda: send_or_fail(job_id, queue))


def send_or_fail(job_id: uuid.UUID, queue: str, countdown: int | None = None) -> None:
    """Broker lỗi: đánh dấu job failed QUEUE_UNAVAILABLE để người dùng retry; API không treo."""
    try:
        dispatcher.send(job_id, queue, countdown=countdown)
    except Exception:
        logger.exception("Không gửi được job %s vào hàng đợi %s", job_id, queue)
        with SessionLocal() as db:
            job = db.get(ProcessingJob, job_id)
            if job is not None and job.status == JobStatus.QUEUED:
                job.status = JobStatus.FAILED
                job.error_code = "QUEUE_UNAVAILABLE"
                job.finished_at = utcnow()
                db.commit()
