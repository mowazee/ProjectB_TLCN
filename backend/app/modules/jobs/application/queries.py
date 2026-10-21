"""API công khai của module jobs: đọc job, trạng thái job mới nhất, retry, tác vụ beat."""

import functools
import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session

from app.modules.audit.application.recorder import record
from app.modules.jobs.application.create import send_or_fail
from app.modules.jobs.domain.model import ACTIVE_STATUSES, CANCELLED, OCR, JobStatus
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.shared.config import settings
from app.shared.context import Principal, RequestContext
from app.shared.db import SessionLocal, aware, utcnow
from app.shared.errors import ConflictError, NotFoundError
from app.shared.events import after_commit
from app.shared.pagination import PageParams


def get_job(db: Session, job_id: uuid.UUID) -> ProcessingJob:
    job = db.get(ProcessingJob, job_id)
    if job is None:
        raise NotFoundError("Không tìm thấy job")
    return job


REQUEUE_COUNT = "requeue_count"  # payload: số lần beat phải gửi lại job queued (FR-11 đánh dấu job chờ quá lâu)


def is_stale(job: ProcessingJob) -> bool:
    """FR-11: job queued quá JOB_REQUEUE_AFTER_SECONDS hoặc đã bị beat gửi lại mà vẫn chưa chạy (vd. chưa bật worker
    chữ viết tay); job processing quá JOB_STALE_SECONDS (worker chết). Beat đặt lại queued_at mỗi lần gửi lại nên
    phải dựa thêm vào requeue_count."""
    now = utcnow()
    if job.status == JobStatus.QUEUED:
        queued = aware(job.queued_at)
        waited = (now - queued).total_seconds() if queued else 0
        return waited > settings.JOB_REQUEUE_AFTER_SECONDS or int((job.payload or {}).get(REQUEUE_COUNT, 0)) > 0
    if job.status == JobStatus.PROCESSING:
        started = aware(job.started_at)
        return started is not None and (now - started).total_seconds() > settings.JOB_STALE_SECONDS
    return False


def list_jobs(
    db: Session,
    *,
    document_ids_select: Any,
    batch_owner: str | None,
    params: PageParams,
    status: JobStatus | None = None,
    kind: str | None = None,
) -> tuple[list[ProcessingJob], int]:
    """FR-11: job của tài liệu trong document_ids_select + job cấp lô (không gắn tài liệu) do batch_owner tạo
    (batch_owner=None: mọi job cấp lô - chỉ Admin). Phạm vi do presentation tính (documents.visible_document_ids)."""
    batch: ColumnElement[bool] = ProcessingJob.document_id.is_(None)
    if batch_owner is not None:
        batch = and_(batch, ProcessingJob.payload["user_id"].as_string() == batch_owner)
    stmt = select(ProcessingJob).where(or_(ProcessingJob.document_id.in_(document_ids_select), batch))
    if status is not None:
        stmt = stmt.where(ProcessingJob.status == status)
    if kind:
        stmt = stmt.where(ProcessingJob.kind == kind)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(
        stmt.order_by(ProcessingJob.queued_at.desc(), ProcessingJob.id).offset(params.offset).limit(params.page_size)
    ).all()
    return list(rows), total


def latest_job(db: Session, document_id: uuid.UUID, kind: str | None = None) -> ProcessingJob | None:
    stmt = select(ProcessingJob).where(ProcessingJob.document_id == document_id)
    if kind:
        stmt = stmt.where(ProcessingJob.kind == kind)
    return db.scalar(stmt.order_by(ProcessingJob.queued_at.desc()).limit(1))


def latest_status_subquery(kind: str = "OCR") -> Any:
    """(document_id, status, job_id) của job mới nhất mỗi tài liệu theo kind."""
    ranked = (
        select(
            ProcessingJob.document_id,
            ProcessingJob.status,
            ProcessingJob.id.label("job_id"),
            func.row_number()
            .over(partition_by=ProcessingJob.document_id, order_by=ProcessingJob.queued_at.desc())
            .label("rn"),
        )
        .where(ProcessingJob.kind == kind)
        .subquery()
    )
    return select(ranked.c.document_id, ranked.c.status, ranked.c.job_id).where(ranked.c.rn == 1).subquery()


def latest_status_map(db: Session, document_ids: list[uuid.UUID], kind: str = "OCR") -> dict[uuid.UUID, str]:
    return {d: s for d, (_, s) in latest_job_map(db, document_ids, kind).items()}


def latest_job_map(
    db: Session, document_ids: list[uuid.UUID], kind: str = "OCR"
) -> dict[uuid.UUID, tuple[uuid.UUID, str]]:
    """document_id -> (job_id, status) của job mới nhất (React poll tiến độ / retry theo job_id)."""
    if not document_ids:
        return {}
    sub = latest_status_subquery(kind)
    rows = db.execute(
        select(sub.c.document_id, sub.c.job_id, sub.c.status).where(sub.c.document_id.in_(document_ids))
    ).all()
    return {d: (j, str(s)) for d, j, s in rows}


def has_running_jobs(db: Session, document_id: uuid.UUID) -> bool:
    return (
        db.scalar(
            select(func.count()).where(
                ProcessingJob.document_id == document_id, ProcessingJob.status.in_(ACTIVE_STATUSES)
            )
        )
        or 0
    ) > 0


def status_counts(db: Session, document_ids_select: Any, kind: str = OCR) -> dict[str, int]:
    """Đếm job theo trạng thái (mặc định job OCR: số liệu dashboard không đổi khi bật job P2)."""
    rows = db.execute(
        select(ProcessingJob.status, func.count(ProcessingJob.id))
        .where(ProcessingJob.document_id.in_(document_ids_select), ProcessingJob.kind == kind)
        .group_by(ProcessingJob.status)
    ).all()
    return {str(s): n for s, n in rows}


def latest_completed_result(db: Session, document_id: uuid.UUID, kind: str) -> dict[str, Any] | None:
    job = db.scalar(
        select(ProcessingJob)
        .where(
            ProcessingJob.document_id == document_id,
            ProcessingJob.kind == kind,
            ProcessingJob.status == JobStatus.COMPLETED,
        )
        .order_by(ProcessingJob.finished_at.desc())
        .limit(1)
    )
    return dict(job.result or {}) if job else None


def retry_job(db: Session, actor: Principal, job_id: uuid.UUID, ctx: RequestContext) -> ProcessingJob:
    """Chạy lại job failed (D-03). Giữ nguyên job_id: kết quả ghi đè, không tạo bản ghi trùng.
    Quyền trên tài liệu do tầng presentation kiểm trước khi gọi."""
    job = get_job(db, job_id)
    if job.status != JobStatus.FAILED:
        raise ConflictError("Chỉ chạy lại được job đã thất bại", code="JOB_NOT_FAILED")
    before = {"status": str(job.status), "attempt": job.attempt, "error_code": job.error_code}
    job.status = JobStatus.QUEUED
    job.attempt = 0
    job.progress = 0
    if job.payload and REQUEUE_COUNT in job.payload:
        job.payload = {k: v for k, v in job.payload.items() if k != REQUEUE_COUNT}
    job.error_code = job.error_detail = None
    job.started_at = job.finished_at = None
    job.queued_at = utcnow()
    record(
        db,
        action="retry_job",
        module="jobs",
        actor_id=actor.id,
        ctx=ctx,
        entity_type="job",
        entity_id=job.id,
        document_id=job.document_id,
        before=before,
        after={"status": "queued"},
    )
    jid, queue = job.id, job.queue_name
    after_commit(db, lambda: send_or_fail(jid, queue))
    db.commit()
    return job


def cancel_job(db: Session, actor: Principal, job_id: uuid.UUID, ctx: RequestContext) -> ProcessingJob:
    """FR-04 (v0.10): dừng job đang chờ/đang chạy. Job chờ: worker bỏ qua khi nhận message. Job đang chạy: worker
    dừng sau đơn vị việc hiện tại (trang OCR). Trạng thái failed + CANCELLED nên Chạy lại (D-03) dùng được.
    Quyền do tầng presentation kiểm (như retry)."""
    job = db.scalar(select(ProcessingJob).where(ProcessingJob.id == job_id).with_for_update())
    if job is None:
        raise NotFoundError("Không tìm thấy job")
    if job.status not in ACTIVE_STATUSES:
        raise ConflictError("Chỉ dừng được job đang chờ hoặc đang xử lý", code="JOB_NOT_ACTIVE")
    before = {"status": str(job.status), "progress": job.progress}
    job.status = JobStatus.FAILED
    job.error_code = CANCELLED
    job.error_detail = f"Dừng bởi {actor.username}"
    job.finished_at = utcnow()
    record(
        db,
        action="cancel_job",
        module="jobs",
        actor_id=actor.id,
        ctx=ctx,
        entity_type="job",
        entity_id=job.id,
        document_id=job.document_id,
        before=before,
        after={"status": "failed", "error_code": CANCELLED},
    )
    db.commit()
    return job


def fail_pending_jobs(db: Session, document_id: uuid.UUID, code: str) -> int:
    jobs = db.scalars(
        select(ProcessingJob).where(ProcessingJob.document_id == document_id, ProcessingJob.status == JobStatus.QUEUED)
    ).all()
    for job in jobs:
        job.status = JobStatus.FAILED
        job.error_code = code
        job.finished_at = utcnow()
    return len(jobs)


def requeue_stuck_jobs() -> int:
    """Celery beat (NFR-03): gửi lại
    - job queued quá JOB_REQUEUE_AFTER_SECONDS (mất message);
    - job processing quá JOB_STALE_SECONDS (worker chết hẳn, không khởi động lại): runner.claim nhận lại job treo.
    Không có bước này, message chưa ack chỉ quay lại hàng đợi sau visibility timeout của Redis (≥ 1 giờ)."""
    now = utcnow()
    queued_limit = now - timedelta(seconds=settings.JOB_REQUEUE_AFTER_SECONDS)
    stale_limit = now - timedelta(seconds=settings.JOB_STALE_SECONDS)
    count = 0
    with SessionLocal() as db:
        jobs = db.scalars(
            select(ProcessingJob).where(ProcessingJob.status.in_([JobStatus.QUEUED, JobStatus.PROCESSING]))
        ).all()
        for job in jobs:
            if job.status == JobStatus.QUEUED:
                queued = aware(job.queued_at)
                if queued is None or queued >= queued_limit:
                    continue
                job.queued_at = now
                payload = dict(job.payload or {})  # gán dict mới: cột JSON không theo dõi sửa tại chỗ
                payload[REQUEUE_COUNT] = int(payload.get(REQUEUE_COUNT, 0)) + 1
                job.payload = payload
            else:
                started = aware(job.started_at)
                if started is None or started >= stale_limit:
                    continue
            after_commit(db, functools.partial(send_or_fail, job.id, job.queue_name))
            count += 1
        db.commit()
    return count


def release_orphaned_jobs(host: str) -> int:
    """Worker vừa khởi động: job còn 'processing' mang worker_id của chính host này là job bị bỏ dở khi worker
    trước đó chết (kill, OOM, restart container). Đưa về queued và gửi lại ngay thay vì chờ JOB_STALE_SECONDS.

    Điều kiện đúng: mỗi host (container) chỉ một tiến trình worker - compose bảo đảm điều này (scale = nhiều
    container, mỗi container hostname riêng); chạy nhiều worker trên cùng máy thì đặt WORKER_NAME khác nhau."""
    prefix = f"{host}:"
    count = 0
    with SessionLocal() as db:
        jobs = db.scalars(
            select(ProcessingJob).where(
                ProcessingJob.status == JobStatus.PROCESSING, ProcessingJob.worker_id.startswith(prefix)
            )
        ).all()
        for job in jobs:
            job.status = JobStatus.QUEUED
            job.queued_at = utcnow()
            job.started_at = None
            job.error_code = "WORKER_LOST"
            after_commit(db, functools.partial(send_or_fail, job.id, job.queue_name))
            count += 1
        db.commit()
    return count
