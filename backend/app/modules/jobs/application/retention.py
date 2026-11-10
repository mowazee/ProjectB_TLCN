"""Hàng đợi xử lý chỉ lưu JOB_RETENTION_DAYS ngày (mặc định 30) - Celery beat.

Xóa job đã kết thúc (completed/failed) có finished_at cũ hơn mốc. Giữ lại job mới nhất của mỗi (tài liệu, loại job)
vì trang chi tiết dùng nó để hiện trạng thái OCR và gợi ý danh mục (P2-05 đọc processing_jobs.result). Job cấp lô
(document_id NULL: nhập hàng loạt, gửi email) xóa theo mốc. ocr_results.job_id ON DELETE SET NULL nên kết quả OCR
không mất.
"""

from datetime import timedelta

from sqlalchemy import delete, func, select

from app.modules.jobs.domain.model import JobStatus
from app.modules.jobs.infrastructure.models import ProcessingJob
from app.shared.config import settings
from app.shared.db import SessionLocal, utcnow


def purge_old_jobs() -> int:
    with SessionLocal() as db:
        cutoff = utcnow() - timedelta(days=settings.JOB_RETENTION_DAYS)
        ranked = (
            select(
                ProcessingJob.id,
                func.row_number()
                .over(
                    partition_by=(ProcessingJob.document_id, ProcessingJob.kind),
                    order_by=(ProcessingJob.queued_at.desc(), ProcessingJob.id.desc()),
                )
                .label("rn"),
            )
            .where(ProcessingJob.document_id.is_not(None))
            .subquery()
        )
        latest = select(ranked.c.id).where(ranked.c.rn == 1)
        result = db.execute(
            delete(ProcessingJob)
            .where(
                ProcessingJob.status.in_([JobStatus.COMPLETED, JobStatus.FAILED]),
                ProcessingJob.finished_at < cutoff,
                ProcessingJob.id.not_in(latest),
            )
            .execution_options(synchronize_session=False)
        )
        db.commit()
        return int(getattr(result, "rowcount", 0) or 0)
