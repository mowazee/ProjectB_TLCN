"""Thực thi job chung cho mọi kind (task duy nhất của worker, R6).

claim (queued -> processing, khóa hàng, nhận lại job treo) -> handler theo kind ->
completed | retry (về queued, attempt < max) | failed. Retry giữ nguyên job_id nên kết quả
ghi đè theo khóa (page_id, job_id): không tạo bản ghi trùng (FR-04).
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.jobs.application import registry
from app.modules.jobs.domain.model import JobError, JobOutcome, JobStatus
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.shared.config import settings
from app.shared.context import SYSTEM_CONTEXT
from app.shared.db import SessionLocal, aware, utcnow

logger = logging.getLogger(__name__)


@dataclass
class JobContext:
    """Thứ handler nhận được: session riêng của worker và bản ghi job đang chạy."""

    db: Session
    job: ProcessingJob

    @property
    def job_id(self) -> uuid.UUID:
        return self.job.id

    @property
    def document_id(self) -> uuid.UUID | None:
        return self.job.document_id

    @property
    def payload(self) -> dict[str, Any]:
        return dict(self.job.payload or {})

    def progress(self, pct: int) -> None:
        """Cập nhật tiến độ và commit để giao diện poll thấy ngay."""
        self.job.progress = max(0, min(99, int(pct)))
        self.db.commit()

    def set_result(self, data: dict[str, Any]) -> None:
        self.job.result = data


def claim(db: Session, job_id: uuid.UUID, worker_id: str) -> ProcessingJob | None:
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update())
    if job is None:
        return None
    now = utcnow()
    started = aware(job.started_at)
    stale = (
        job.status == JobStatus.PROCESSING
        and started is not None
        and started < now - timedelta(seconds=settings.JOB_STALE_SECONDS)
    )
    if job.status != JobStatus.QUEUED and not stale:
        db.rollback()
        return None
    if job.attempt >= job.max_attempts:
        _mark_failed(db, job, "MAX_ATTEMPTS_EXCEEDED", "Hết số lần thử khi nhận lại job")
        db.commit()
        return None
    job.status = JobStatus.PROCESSING
    job.attempt += 1
    job.started_at = now
    job.finished_at = None
    job.worker_id = worker_id[:100]
    job.progress = 0
    db.commit()
    return job


def _audit(db: Session, job: ProcessingJob, success: bool, extra: dict[str, Any]) -> None:
    record(
        db,
        action=f"run_{job.kind.lower()}",
        module="jobs",
        actor_id=None,
        ctx=SYSTEM_CONTEXT,
        entity_type="job",
        entity_id=job.id,
        document_id=job.document_id,
        success=success,
        after={"attempt": job.attempt, **extra},
    )


def _mark_failed(db: Session, job: ProcessingJob, code: str, detail: str) -> None:
    job.status = JobStatus.FAILED
    job.error_code = code
    job.error_detail = detail[:2000]
    job.finished_at = utcnow()
    _audit(db, job, False, {"error_code": code})


def _handle_failure(db: Session, job_id: uuid.UUID, code: str, detail: str, retryable: bool) -> JobOutcome:
    db.rollback()
    job = db.get(ProcessingJob, job_id)
    if job is None:
        return JobOutcome.FAILED
    if retryable and job.attempt < job.max_attempts:
        job.status = JobStatus.QUEUED
        job.error_code = code
        job.error_detail = detail[:2000]
        db.commit()
        return JobOutcome.RETRY
    _mark_failed(db, job, code, detail)
    db.commit()
    return JobOutcome.FAILED


def run_job(job_id: uuid.UUID, *, worker_id: str = "local") -> JobOutcome:
    with SessionLocal() as db:
        job = claim(db, job_id, worker_id)
        if job is None:
            return JobOutcome.SKIPPED
        handler = registry.get_handler(job.kind)
        if handler is None:
            return _handle_failure(db, job_id, "NO_HANDLER", f"Không có handler cho kind {job.kind}", False)
        try:
            handler(JobContext(db, job))
        except JobError as exc:
            logger.warning("Job %s lỗi %s: %s", job_id, exc.code, exc)
            return _handle_failure(db, job_id, exc.code, str(exc), exc.retryable)
        except Exception as exc:
            logger.exception("Job %s lỗi không xác định", job_id)
            return _handle_failure(db, job_id, "INTERNAL_ERROR", repr(exc), True)
        job.status = JobStatus.COMPLETED
        job.progress = 100
        job.finished_at = utcnow()
        job.error_code = job.error_detail = None
        _audit(db, job, True, {"result": job.result})
        db.commit()
        return JobOutcome.COMPLETED
